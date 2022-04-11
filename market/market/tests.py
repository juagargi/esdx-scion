from django.test import TestCase
from django_grpc_framework.test import Channel
from market.models import Offer
from datetime import datetime
import market_pb2, market_pb2_grpc

# Create your tests here.
class TestWhiteboard(TestCase):
    def test_list(self):
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            response = stub.ListOffers(market_pb2.ListRequest())
            print(f'response={response}')



class TestOffer(TestCase):
    def test_contains(self):
        o = Offer()
        o.bw_profile="2,2,2,2"
        print("\n#######################--------------##############")
        print(o)
        print("#######################--------------##############")
        self.assertTrue(o.contains_profile("2,2,1", datetime()))