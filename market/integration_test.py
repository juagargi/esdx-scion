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
from pathlib import Path
from defs import BW_PERIOD
from util.conversion import pb_timestamp_from_time
from util import crypto
from util import serialize

import sys
import os
import subprocess
import time
import grpc
import market_pb2
import market_pb2_grpc

import signal
import ctypes


def _list(channel):
    stub = market_pb2_grpc.MarketControllerStub(channel)
    response = stub.ListOffers(market_pb2.ListRequest())
    offers = [o for o in response]
    return offers


def _buy(channel, key, buyer_ia, offer):
    stub = market_pb2_grpc.MarketControllerStub(channel)
    request = market_pb2.PurchaseRequest(
        offer_id=offer.id,
        buyer_iaid=buyer_ia,
        signature=b"",
        bw_profile="1,1,1,1",
        starting_on=pb_timestamp_from_time(tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")))
    # sign the purchase request
    offerbytes = serialize.offer_fields_serialize_to_bytes(
        offer.specs.iaid,
        offer.specs.is_core,
        offer.specs.notbefore.ToSeconds(),
        offer.specs.notafter.ToSeconds(),
        offer.specs.reachable_paths,
        offer.specs.qos_class,
        offer.specs.price_per_nanounit,
        offer.specs.bw_profile
    )
    data = serialize.purchase_order_fields_serialize_to_bytes(
        offerbytes,
        request.bw_profile,
        request.starting_on.ToSeconds()
    )
    request.signature = crypto.signature_create(key, data)
    return stub.Purchase(request)


def run_django():
    if os.path.exists("db.sqlite3"):
        os.remove("db.sqlite3")
    p = subprocess.Popen(["./manage.py", "migrate"], stdout=subprocess.DEVNULL)
    p.wait()
    p = subprocess.Popen(
        ["./manage.py", "loaddata", "./market/fixtures/testdata.yaml"],
        stdout=subprocess.DEVNULL)
    p.wait()

    # from https://stackoverflow.com/questions/19447603/how-to-kill-a-python-child-process-\
    # created-with-subprocess-check-output-when-t/19448096#19448096
    libc = ctypes.CDLL("libc.so.6")
    def set_pdeathsig(sig = signal.SIGTERM):
        def callable():
            return libc.prctl(1, sig)
        return callable
    p = subprocess.Popen(["./manage.py", "grpcrunserver"],
        preexec_fn=set_pdeathsig(signal.SIGTERM))
    time.sleep(1)
    return p


def provider():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = market_pb2_grpc.MarketControllerStub(channel)
        notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        notafter = notbefore + tz.timedelta(seconds=4*BW_PERIOD)
        o = market_pb2.Offer(
            specs=market_pb2.OfferSpecification(
                iaid="1-ff00:0:110",
                is_core=True,
                signature=b"",
                notbefore=Timestamp(seconds=int(notbefore.timestamp())),
                notafter=Timestamp(seconds=int(notafter.timestamp())),
                reachable_paths="*",
                qos_class=1,
                price_per_nanounit=10,
                bw_profile="2,2,2,2",
            ),
        )
        with open(Path(__file__).parent.joinpath("market", "tests", "data",
            "1-ff00_0_110.key"), "r") as f:
            key = crypto.load_key(f.read())
        # sign with private key
        data = serialize.offer_serialize_to_bytes(o)
        o.specs.signature = crypto.signature_create(key, data)
        # do RPC
        saved = stub.AddOffer(o)
        print(f"provider created offer with id {saved.id}")


def client(ia: str, wait: int):
    # load key
    iafile = ia.replace(":", "_")
    with open(Path(__file__).parent.joinpath("market", "tests", "data", iafile + ".key"), "r") as f:
        key = crypto.load_key(f.read())
    # buy
    for _ in range(2):
        with grpc.insecure_channel('localhost:50051') as channel:
            offers = _list(channel)
            time.sleep(wait)
            o = offers[0]
            response = _buy(channel, key, ia, o)
            if response.contract_id > 0:
                print(f"Client with ID: {ia} got contract with ID: {response.contract_id}")
                return 0
            print(f"Client with ID: {ia} could not buy: {response.message}")
    print(f"Client with ID: {ia} too many attempts")
    return 1


def main():
    django = run_django()
    provider()
    with ThreadPoolExecutor() as executor:
        tasks = [
            executor.submit(lambda: client("1-ff00:0:111", 1)),
            executor.submit(lambda: client("1-ff00:0:112", 0)),
        ]
    res = 0
    for t in tasks:
        if t.result() != 0:
            res = 1
    django.terminate()
    try:
        django.wait(timeout=1)
    finally:
        django.terminate()
        django.kill()
    print(f"done (exits with {res})")
    return res


if __name__ == "__main__":
    sys.exit(main())
