from email import message
from django.test import TestCase
from django_grpc_framework.test import Channel
import market_pb2, market_pb2_grpc
from market.models import Offer, BW_PERIOD
from django.utils import timezone as tz
from market.serializers import OfferProtoSerializer
from google.protobuf.timestamp_pb2 import Timestamp

class TestWhiteboard(TestCase):
    def setUp(self):
        notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        notafter = notbefore + tz.timedelta(seconds=4*BW_PERIOD)
        o1 = Offer.objects.create(iaid=1, iscore=True, signature=b"",
                                  reachable_paths="",
                                  notbefore=notbefore,
                                  notafter=notafter,
                                  qos_class=1,
                                  price_per_nanounit=10,
                                  bw_profile="2,2,2,2")
        o2 = Offer.objects.create(iaid=2, iscore=True, signature=b"",
                                  reachable_paths="",
                                  notbefore=notbefore,
                                  notafter=notafter,
                                  qos_class=1,
                                  price_per_nanounit=10,
                                  bw_profile="2,2,2,2")
        o3 = Offer.objects.create(iaid=3, iscore=True, signature=b"",
                                  reachable_paths="",
                                  notbefore=notbefore,
                                  notafter=notafter,
                                  qos_class=1,
                                  price_per_nanounit=10,
                                  bw_profile="2,2,2,2")
        self.offers = {
            1: o1,
            2: o2,
            3: o3,
        }

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
            notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
            notafter = notbefore + tz.timedelta(seconds=4*BW_PERIOD)
            o = market_pb2.Offer(
                iaid=1,
                iscore=True,
                signature=b"",
                notbefore=Timestamp(seconds=int(notbefore.timestamp())),
                notafter=Timestamp(seconds=int(notafter.timestamp())),
                reachable_paths="*",
                qos_class=1,
                price_per_nanounit=10,
                bw_profile="2,2,2,2")
            stub = market_pb2_grpc.MarketControllerStub(channel)
            saved_offer = stub.AddOffer(o)
            self.assertEqual(Offer.objects.all().count(), len(self.offers)+1)

    def test_purchase(self):
        with Channel() as channel:
            matched_offer = self.offers[1]
            starting_on = matched_offer.notbefore
            request = market_pb2.PurchaseRequest(
                offer_id=matched_offer.id,
                buyer_id=42,
                signature=b"",
                bw_profile="1",
                starting_on=Timestamp(seconds=int(starting_on.timestamp())))
            stub = market_pb2_grpc.MarketControllerStub(channel)
            response = stub.Purchase(request)
