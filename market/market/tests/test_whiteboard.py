from django.test import TestCase
from django_grpc_framework.test import Channel
from django.utils import timezone as tz
from google.protobuf.timestamp_pb2 import Timestamp
from pathlib import Path
from market.models.offer import Offer, BW_PERIOD
from market.models.contract import Contract
from market.purchases import sign_purchase_order
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
                iscore=True,
                signature=b"1",
                reachable_paths="",
                notbefore=notbefore,
                notafter=notafter,
                qos_class=1,
                price_per_nanounit=10,
                bw_profile="2,2,2,2"
            )

    def test_list(self):
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            offers = stub.ListOffers(market_pb2.ListRequest())
        offers = [o for o in offers]
        self.assertEqual(len(offers), len(self.offers))
        for o in offers:
            self.assertTrue(o.iaid in self.offers)
            g = self.offers[o.iaid]
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
            o = market_pb2.Offer(
                iaid="1-ff00:0:111",
                iscore=True,
                notbefore=Timestamp(seconds=int(notbefore.timestamp())),
                notafter=Timestamp(seconds=int(notafter.timestamp())),
                reachable_paths="*",
                qos_class=1,
                price_per_nanounit=10,
                bw_profile="2,2,2,2")
            # load private key
            with open(Path(__file__).parent.joinpath("data", "1-ff00_0_111.key"), "r") as f:
                key = crypto.load_key(f.read())
            # sign with private key
            data = serialize.offer_serialize_to_bytes(o)
            o.signature = crypto.signature_create(key, data)
            # call RPC
            saved_offer = stub.AddOffer(o)
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
