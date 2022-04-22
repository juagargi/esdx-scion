from inspect import signature
from django.test import TestCase
from django_grpc_framework.test import Channel
from market.models import Offer, BW_PERIOD
from django.utils import timezone as tz
import pytz
import market_pb2, market_pb2_grpc

# Create your tests here.
class TestWhiteboard(TestCase):
    def test_list(self):
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            response = stub.ListOffers(market_pb2.ListRequest())
            print(f'response={response}')



class TestOffer(TestCase):
    def setUp(self):
        notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        notafter = notbefore + tz.timedelta(seconds=4*BW_PERIOD)
        Offer.objects.create(iaid=1, iscore=True, signature=b"",
                             reachable_paths="",
                             notbefore=notbefore,
                             notafter=notafter,
                             qos_class=1,
                             price_per_nanounit=10,
                             bw_profile="2,2,2,2")

    def test_multiple_of_bw_period(self):
        o = Offer.objects.get(iaid=1)
        o.notafter = o.notbefore + tz.timedelta(seconds=BW_PERIOD)
        o.bw_profile = "2"
        o.save()
        # period of 1.33 seconds (should fail)
        o.notafter = o.notbefore + tz.timedelta(seconds=1.33)
        self.assertRaises(ValueError, o.save)

    def test_bw_profile_length(self):
        o = Offer.objects.get(iaid=1)
        o.notafter = o.notbefore + tz.timedelta(seconds=3*BW_PERIOD)
        o.bw_profile = "2,3,4"
        o.save()
        # 2 periods now
        o.bw_profile = "2,2"
        self.assertRaises(ValueError, o.save)

    def test_contains(self):
        o = Offer()
        o.bw_profile="2,2,2,2"
        starting_at = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        self.assertTrue(o.contains_profile("2,2,1", starting_at))
