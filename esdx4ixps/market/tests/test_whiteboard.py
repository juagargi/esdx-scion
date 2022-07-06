from nis import match
from django.test import TestCase
from django_grpc_framework.test import Channel
from django.utils import timezone as tz
from google.protobuf.timestamp_pb2 import Timestamp
from pathlib import Path
from market.models.offer import Offer, BW_PERIOD
from market.models.contract import Contract
from market.purchases import sign_purchase_order, sign_get_contract_request
from market.serializers import OfferProtoSerializer
from market import services
from util import conversion
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
                signature=b"1",
                reachable_paths="",
                notbefore=notbefore,
                notafter=notafter,
                qos_class=1,
                price_per_unit=0.000000001,
                bw_profile="2,2,2,2",
                br_address_template="10.1.1.1:50000-50010",
                br_mtu=1500,
                br_link_to="PARENT",
            )

    def test_serialize_offer(self):
        offer = next(iter(self.offers.values()))
        serializer = OfferProtoSerializer(offer)
        msg = serializer.message
        self.assertEqual(offer.id, msg.id)
        self.assertEqual(offer.iaid, msg.specs.iaid)
        self.assertEqual(int(offer.notbefore.timestamp()), msg.specs.notbefore.seconds)
        self.assertEqual(int(offer.notafter.timestamp()), msg.specs.notafter.seconds)
        self.assertEqual(offer.qos_class, msg.specs.qos_class)
        self.assertEqual(offer.price_per_unit, msg.specs.price_per_unit)
        self.assertEqual(offer.bw_profile, msg.specs.bw_profile)
        self.assertEqual(offer.br_address_template, msg.specs.br_address_template)
        self.assertEqual(offer.br_mtu, msg.specs.br_mtu)
        self.assertEqual(offer.br_link_to, msg.specs.br_link_to)
        self.assertEqual(offer.signature, msg.specs.signature)

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
        available_offers = list(Offer.objects.available())
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
            notafter = notbefore + tz.timedelta(seconds=4*BW_PERIOD)
            specs=market_pb2.OfferSpecification(
                iaid="1-ff00:0:111",
                notbefore=Timestamp(seconds=int(notbefore.timestamp())),
                notafter=Timestamp(seconds=int(notafter.timestamp())),
                reachable_paths="*",
                qos_class=1,
                price_per_unit=0.000000123,
                bw_profile="2,2,2,2",
                br_address_template="1.1.1.1:1-10",
                br_mtu=100,
                br_link_to="PARENT",
            )
            # load private key
            with open(Path(__file__).parent.joinpath("data", "1-ff00_0_111.key"), "r") as f:
                key = crypto.load_key(f.read())
            # sign with private key
            data = serialize.offer_specification_serialize_to_bytes(specs, False)
            specs.signature = crypto.signature_create(key, data)
            # call RPC
            saved_offer = stub.AddOffer(specs)
            # check that both offers (the original signed by the seller, and the current signed by
            # the broker) are present in the DB
            self.assertEqual(Offer.objects.all().count(), len(self.offers)+2)
            # get the created offer
            saved = Offer.objects.get(id=saved_offer.id)
            # check original specs
            def compare_offer(o):
                self.assertEqual(specs.iaid, o.iaid)
                self.assertEqual(specs.notbefore, conversion.pb_timestamp_from_time(o.notbefore))
                self.assertEqual(specs.notafter, conversion.pb_timestamp_from_time(o.notafter))
                self.assertEqual(specs.reachable_paths, o.reachable_paths)
                self.assertEqual(specs.qos_class, o.qos_class)
                self.assertEqual(specs.price_per_unit, o.price_per_unit)
                self.assertEqual(specs.bw_profile, o.bw_profile)
                self.assertEqual(specs.br_address_template, o.br_address_template)
                self.assertEqual(specs.br_mtu, o.br_mtu)
                self.assertEqual(specs.br_link_to, o.br_link_to)
            compare_offer(saved)
            # verify it's signed by the broker
            saved.validate_signature()
            # the count of available offers has changed only by 1
            available_now = Offer.objects.available()
            self.assertEqual(len(available_now), len(available_offers) + 1)
            # and I can find the original offer signed by the seller
            originals = Offer.objects._original_offers()
            self.assertEqual(len(originals), 1)
            compare_offer(originals[0])
            self.assertEqual(originals[0].signature, specs.signature)

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
            pb_contract = stub.Purchase(request)
            self.assertEqual(Offer.objects.available(id=matched_offer.id).count(), 0) # sold already
            # there must be a new offer:
            newoffer=Offer.objects.get(deprecates=matched_offer)
            self.assertEqual(newoffer.bw_profile, "0,2,2,2")
            self.assertEqual(newoffer.notbefore, matched_offer.notbefore)
            self.assertEqual(newoffer.notafter, matched_offer.notafter)

            # contract and purchase order:
            contract = Contract.objects.get(id=pb_contract.contract_id)
            self.assertAlmostEqual(contract.timestamp, tz.localtime(), delta=tz.timedelta(seconds=1))
            order = contract.purchase_order
            self.assertEqual(order.buyer.iaid, request.buyer_iaid)
            self.assertEqual(order.bw_profile, request.bw_profile)
            return contract

    def test_get_contract(self):
        contract_id = self.test_purchase().id # buys self.offers[0]
        def get_contract_request(ia:str, contract_id: int) -> market_pb2.GetContractRequest:
            """create the get contract request"""
            # create a signature for the get contract request
            with open(Path(__file__).parent.joinpath("data", ia.replace(":", "_")+".key"), "r") as f:
                key = crypto.load_key(f.read()) # load private key
            signature = sign_get_contract_request(
                key,
                ia,
                contract_id,
            )
            return market_pb2.GetContractRequest(
                contract_id=contract_id,
                requester_iaid=ia,
                requester_signature=signature,
            )
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            self.assertRaises(services.MarketServiceError, stub.GetContract,
                get_contract_request(
                    ia="1-ff00:0:111",  # this IA shouldn't get the contract (not part of it)
                    contract_id=contract_id,
                )
            )
            response = stub.GetContract(get_contract_request(
                ia="1-ff00:0:112",  # this IA is the buyer
                contract_id=contract_id)
            )
            response2 = stub.GetContract(get_contract_request(
                ia="1-ff00:0:110",  # this IA is the seller
                contract_id=contract_id)
            )
            self.assertEqual(response, response2)  # same contract for buyer and seller
            # check values of the contract
            contract = Contract.objects.get(id=contract_id)
            self.assertEqual(response.contract_id, contract_id)
            self.assertEqual(response.contract_timestamp,
                conversion.pb_timestamp_from_time(contract.timestamp))
            self.assertEqual(response.contract_signature, contract.signature_broker)
            po = contract.purchase_order
            self.assertEqual(response.buyer_iaid, po.buyer.iaid)
            self.assertEqual(response.buyer_starting_on,
                conversion.pb_timestamp_from_time(po.starting_on))
            self.assertEqual(response.buyer_bw_profile, po.bw_profile)
            self.assertEqual(response.buyer_signature, po.signature)
            # check values of the offer embedded in the contract
            o = response.offer
            self.assertEqual(o.iaid, po.offer.iaid)
            self.assertEqual(o.notbefore, conversion.pb_timestamp_from_time(po.offer.notbefore))
            self.assertEqual(o.notafter, conversion.pb_timestamp_from_time(po.offer.notafter))
            self.assertEqual(o.reachable_paths, po.offer.reachable_paths)
            self.assertEqual(o.qos_class, po.offer.qos_class)
            self.assertEqual(o.price_per_unit, po.offer.price_per_unit)
            self.assertEqual(o.bw_profile, po.offer.bw_profile)
            self.assertEqual(o.br_address_template, po.offer.br_address_template)
            self.assertEqual(o.br_mtu, po.offer.br_mtu)
            self.assertEqual(o.br_link_to, po.offer.br_link_to)
            self.assertEqual(o.signature, po.offer.signature)
