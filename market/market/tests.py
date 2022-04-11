from django.test import TestCase
from django_grpc_framework.test import Channel
import market_pb2, market_pb2_grpc

# Create your tests here.
class Whiteboard(TestCase):
    def test_list(self):
        with Channel() as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            response = stub.ListOffers(market_pb2.ListRequest())
            print(f'response={response}, type={type(response)}, '+
                f'iaid={response.iaid}, comment={response.comment}')

