from django.test import TestCase
from django_grpc_framework.test import Channel
from django.utils import timezone as tz
from google.protobuf.timestamp_pb2 import Timestamp
from pathlib import Path
from market.serializers import OfferProtoSerializer
from market.models.offer import Offer, BW_PERIOD
from market.models.contract import Contract
from market.purchases import sign_purchase_order, sign_get_contract_request
from util import crypto
from util import serialize

import market_pb2, market_pb2_grpc

class TestWhiteboard(TestCase):
    fixtures = ['testdata']
    def setUp(self):
        notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        notafter = notbefore + tz.timedelta(seconds=4*BW_PERIOD)
        self.offers = {}
        for iaid in ["1-ff00:0:110", "1-ff00:0:111", "1-ff00:0:112"]:
            self.offers[iaid] = Offer.objects.create(
                iaid=iaid,
                is_core=True,
                signature=b"1",
                reachable_paths="",
                notbefore=notbefore,
                notafter=notafter,
                qos_class=1,
                price_per_unit=0.000000001,
                bw_profile="2,2,2,2"
            )

    def test_serialize_offer(self):
        offer = next(iter(self.offers.values()))
        serializer = OfferProtoSerializer(offer)
        msg = serializer.message
        self.assertEqual(offer.id, msg.id)
        self.assertEqual(offer.iaid, msg.specs.iaid)
        self.assertEqual(offer.is_core, msg.specs.is_core)
        self.assertEqual(int(offer.notbefore.timestamp()), msg.specs.notbefore.seconds)
        self.assertEqual(int(offer.notafter.timestamp()), msg.specs.notafter.seconds)
        self.assertEqual(offer.qos_class, msg.specs.qos_class)
        self.assertEqual(offer.price_per_unit, msg.specs.price_per_unit)
        self.assertEqual(offer.bw_profile, msg.specs.bw_profile)
        # self.assertEqual(offer.signature, msg.specs.signature)

    def test_list(self):
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            offers = stub.ListOffers(market_pb2.ListRequest())
        offers = [o for o in offers]
        self.assertEqual(len(offers), len(self.offers))
        for o in offers:
            self.assertTrue(o.specs.iaid in self.offers)
            g = self.offers[o.specs.iaid]
            fs = Offer._meta.fields
            for f in fs:
                expected = getattr(g, f.name)
                got = getattr(g, f.name)
                self.assertEqual(got, expected)

    def test_add(self):
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
            notafter = notbefore + tz.timedelta(seconds=4*BW_PERIOD)
            specs=market_pb2.OfferSpecification(
                iaid="1-ff00:0:111",
                is_core=True,
                notbefore=Timestamp(seconds=int(notbefore.timestamp())),
                notafter=Timestamp(seconds=int(notafter.timestamp())),
                reachable_paths="*",
                qos_class=1,
                price_per_unit=0.000000123,
                bw_profile="2,2,2,2",
            )
            # load private key
            with open(Path(__file__).parent.joinpath("data", "1-ff00_0_111.key"), "r") as f:
                key = crypto.load_key(f.read())
            # sign with private key
            data = serialize.offer_specification_serialize_to_bytes(specs)
            specs.signature = crypto.signature_create(key, data)
            # call RPC
            saved_offer = stub.AddOffer(specs)
            self.assertEqual(Offer.objects.all().count(), len(self.offers)+1)
            # get the created offer
            saved = Offer.objects.get(id=saved_offer.id)
            # verify it's signed by the broker
            saved.validate_signature()

    def test_purchase(self):
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            matched_offer = next(iter(self.offers.values()))
            starting_on = matched_offer.notbefore
            # create a signature for the purchase order
            with open(Path(__file__).parent.joinpath("data", "1-ff00_0_112.key"), "r") as f:
                key = crypto.load_key(f.read()) # load private key
            signature = sign_purchase_order(
                key,
                matched_offer,
                starting_on,
                "2"
            )

            request = market_pb2.PurchaseRequest(
                offer_id=matched_offer.id,
                buyer_iaid="1-ff00:0:112",
                signature=signature,
                bw_profile="2",
                starting_on=Timestamp(seconds=int(starting_on.timestamp())))
            response = stub.Purchase(request)
            self.assertGreater(response.new_offer_id, 0, response.message)
            self.assertGreater(response.contract_id, 0, response.message)
            self.assertEqual(Offer.objects.available(id=matched_offer.id).count(), 0) # sold already
            # new offer:
            newoffer = Offer.objects.get_available(id=response.new_offer_id)
            self.assertEqual(newoffer.bw_profile, "0,2,2,2")
            self.assertEqual(newoffer.notbefore, matched_offer.notbefore)
            self.assertEqual(newoffer.notafter, matched_offer.notafter)

            # contract and purchase order:
            contract = Contract.objects.get(id=response.contract_id)
            self.assertAlmostEqual(contract.timestamp, tz.localtime(), delta=tz.timedelta(seconds=1))
            order = contract.purchase_order
            self.assertEqual(order.buyer.iaid, "1-ff00:0:112")
            self.assertEqual(order.bw_profile, "2")
            return response

    def test_get_contract(self):
        purchase_response = self.test_purchase() # buys self.offers[0]
        # get the contract
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            request = market_pb2.GetContractRequest(
                contract_id=purchase_response.contract_id,
                requester_iaid="1-ff00:0:112",
            )
            # create a signature for the get contract request
            with open(Path(__file__).parent.joinpath("data", "1-ff00_0_112.key"), "r") as f:
                key = crypto.load_key(f.read()) # load private key
            signature = sign_get_contract_request(
                key,
                request.requester_iaid,
                request.contract_id,
            )
            request.requester_signature = signature
            response = stub.GetContract(request)
            print(f"deleteme test_get_contract, type(response) = {type(response)}")