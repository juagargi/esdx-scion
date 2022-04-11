import grpc
import market_pb2, market_pb2_grpc


with grpc.insecure_channel('localhost:50051') as channel:
    stub = market_pb2_grpc.MarketControllerStub(channel)
    print('----- List -----')
    response = stub.ListOffers(market_pb2.ListRequest())
    print(f'response: {response}')
