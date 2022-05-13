#!/usr/bin/env python

# This test runs Django gRPC, a provider, and two clients.
# The provider adds an offer and the clients list and attempt to buy it.
# The profile that the clients buy is exactly half of the offer, so the
# aggregation of the purchases should fit. Because the first client to
# buy the offer will destroy the original offer (as its bandwidth is now halved),
# the second client will need to list and buy again.

# The test ends terminating Django gRPC.
# The test exits with 0 if okay, non zero otherwise.


from django.utils import timezone as tz
from google.protobuf.timestamp_pb2 import Timestamp
from concurrent.futures import ThreadPoolExecutor
from defs import BW_PERIOD
from util.conversion import pb_timestamp_from_time

import sys
import os
import subprocess
import time
import grpc
import market_pb2
import market_pb2_grpc


def _list(channel):
    stub = market_pb2_grpc.MarketControllerStub(channel)
    response = stub.ListOffers(market_pb2.ListRequest())
    offers = [o for o in response]
    return offers


def _buy(channel, buyer_id, offer_id):
    stub = market_pb2_grpc.MarketControllerStub(channel)
    request = market_pb2.PurchaseRequest(
        offer_id=offer_id,
        buyer_id=buyer_id,
        signature=b"",
        bw_profile="1,1,1,1",
        starting_on=pb_timestamp_from_time(tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")))
    return stub.Purchase(request)


def run_django():
    if os.path.exists("db.sqlite3"):
        os.remove("db.sqlite3")
    p = subprocess.Popen(["./manage.py", "migrate"], stdout=subprocess.DEVNULL)
    p.wait()
    p = subprocess.Popen(["./manage.py", "grpcrunserver"])
    time.sleep(1)
    return p


def provider():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = market_pb2_grpc.MarketControllerStub(channel)
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
        stub.AddOffer(o)


def client(id: int, wait: int):
    for _ in range(2):
        with grpc.insecure_channel('localhost:50051') as channel:
            offers = _list(channel)
            time.sleep(wait)
            o = offers[0]
            response = _buy(channel, id, o.id)
            if response.contract_id > 0:
                print(f"Client with ID: {id} got contract with ID: {response.contract_id}")
                return
            print(f"Client with ID: {id} could not buy")
    print(f"Client with ID: {id} too many attempts")
    sys.exit(1)


def main():
    django = run_django()
    provider()
    with ThreadPoolExecutor() as executor:
        tasks = [
            executor.submit(lambda: client(1, 1)),
            executor.submit(lambda: client(2, 0)),
        ]
    for t in tasks:
        t.result()
    django.terminate()
    try:
        django.wait(timeout=1)
    except:
        django.kill()
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
