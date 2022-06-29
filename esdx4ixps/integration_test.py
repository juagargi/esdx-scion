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


class Client:
    """a Market service client"""
    def __init__(self, ia: str, wait_seconds: int):
        self.ia = ia
        self.wait = wait_seconds
        self.key = None
        self.stub = None

    def _list(self):
        response = self.stub.ListOffers(market_pb2.ListRequest())
        offers = [o for o in response]
        return offers

    def _buy(self, offer):
        request = market_pb2.PurchaseRequest(
            offer_id=offer.id,
            buyer_iaid=self.ia,
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
            offer.specs.price_per_unit,
            offer.specs.bw_profile,
            offer.specs.br_address,
            offer.specs.br_mtu,
            offer.specs.br_link_to,
        )
        data = serialize.purchase_order_fields_serialize_to_bytes(
            offerbytes,
            request.bw_profile,
            request.starting_on.ToSeconds()
        )
        request.signature = crypto.signature_create(self.key, data)
        return self.stub.Purchase(request)

    def _get_contract(self, contract_id: int):
        data = serialize.get_contract_request_serialize(
            contract_id=contract_id,
            requester_iaid=self.ia,
            signature=None,
        )
        request = market_pb2.GetContractRequest(
            contract_id=contract_id,
            requester_iaid=self.ia,
            requester_signature=crypto.signature_create(self.key, data),
        )
        return self.stub.GetContract(request)

    def run(self):
        # load key
        iafile = self.ia.replace(":", "_")
        with open(Path(__file__).parent.joinpath("market", "tests",\
            "data", iafile + ".key"), "r") as f:
            self.key = crypto.load_key(f.read())
        # buy
        with grpc.insecure_channel('localhost:50051') as channel:
            self.stub = market_pb2_grpc.MarketControllerStub(channel)
            for _ in range(2):
                offers = self._list()
                time.sleep(self.wait)
                try:
                    pb_contract = self._buy(offers[0])
                    print(f"Client with ID: {self.ia} got contract with ID: {pb_contract.contract_id}")
                    break
                except grpc.RpcError as ex:
                    print(f"Client with ID: {self.ia} could not buy: {ex.details()}")
                    continue
            if pb_contract is None :
                print(f"Client with ID: {self.ia} too many attempts")
                return 1
            # unnecessary, but check the contract obtained independently
            pb_contract2 = self._get_contract(pb_contract.contract_id)
            if pb_contract.contract_signature != pb_contract2.contract_signature:
                raise RuntimeError("contract from get_contract: signatures are different!")
            # send contract to the topology reloader
            # TODO(juagargi)

        self.stub = None
        return 0



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
        specs=market_pb2.OfferSpecification(
            iaid="1-ff00:0:110",
            is_core=True,
            signature=b"",
            notbefore=Timestamp(seconds=int(notbefore.timestamp())),
            notafter=Timestamp(seconds=int(notafter.timestamp())),
            reachable_paths="*",
            qos_class=1,
            price_per_unit=0.000000001,
            bw_profile="2,2,2,2",
            br_address="10.1.1.1:50000",
            br_mtu=1500,
            br_link_to="PARENT",
        )
        with open(Path(__file__).parent.joinpath("market", "tests", "data",
            "1-ff00_0_110.key"), "r") as f:
            key = crypto.load_key(f.read())
        # sign with private key
        data = serialize.offer_specification_serialize_to_bytes(specs)
        specs.signature = crypto.signature_create(key, data)
        # do RPC
        saved = stub.AddOffer(specs)
        print(f"provider created offer with id {saved.id}")


def client(ia: str, wait: int):
    c = Client(ia, wait)
    return c.run()


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
        result = t.result()
        if result != 0:
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
