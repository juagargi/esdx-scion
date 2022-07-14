from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
# from django.utils import timezone as tz
from google.protobuf.timestamp_pb2 import Timestamp
from pathlib import Path
from util import conversion
from util import crypto
from util import serialize
from util.standalone import run_django
from util.test import test_data
from typing import List
import defs
import grpc
import market_pb2
import market_pb2_grpc
import time


class Runner:
    def __init__(
        self,
        seller_fcn,  # the function to execute per seller
        sellers_data,  # list of len(sellers) tuples, each with the parameters for seller_fcn
        buyer_fcn,  # the function to execute per buyer
        buyers_data,  # list of len(buyers) tuples, each with the parameters for buyer_fcn
    ):
        """
        data_sellers: list of len(sellers) elements, each consisting on the arguments to the sellers function
        """
        self.seller_fcn = seller_fcn
        self.sellers_data = sellers_data
        self.buyer_fcn = buyer_fcn
        self.buyers_data = buyers_data
        self.timings = { # times for certain events
            "start": None,  # right after run starts
            "before_execution": None,  # before the execution of the sellers and buyers
            "after_execution": None,  # after the sellers and buyers have finished
            "end": None,  # right before returning from run
        }

    def run(self, flush_all_data: bool):
        self.timings["start"] = time.time()
        django = run_django(flush_all_data)
        self.timings["before_execution"] = time.time()
        tasks = []
        with ThreadPoolExecutor() as executor:
            # launch sellers
            for args in self.sellers_data:
                tasks.append(executor.submit(self.seller_fcn, *args))
            time.sleep(1)  # let the sellers work for a while

            # launch buyers
            for args in self.buyers_data:
                tasks.append(executor.submit(self.buyer_fcn, *args))

        res = 0
        for t in tasks:
            result = t.result()
            if result != 0:
                res = 1
        self.timings["after_execution"] = time.time()
        try:
            django.terminate()
        finally:
            django.kill()
        self.timings["end"] = time.time()
        return res


class MarketClient:
    """ a seller or buyer """
    def __init__(self, ia: str, service_address: str):
        self.ia = ia
        self.service_address = service_address
        ia_file = self.ia.replace(":", "_")
        # load key and certificate
        with open(test_data(ia_file + ".key"), "r") as f:
            self.key = crypto.load_key(f.read())
        with open(test_data(ia_file + ".crt"), "r") as f:
            self.cert = crypto.load_certificate(f.read())
        # load broker's certificate
        with open(test_data("broker.crt"), "r") as f:
            self.broker_cert = crypto.load_certificate(f.read())

    def sell_offer(self, offer: market_pb2.OfferSpecification) -> market_pb2.Offer:
        data = serialize.offer_specification_serialize_to_bytes(offer, False)
        offer.signature = crypto.signature_create(self.key, data)
        with grpc.insecure_channel(self.service_address) as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            return stub.AddOffer(offer)

    def create_simplified_offer(self, bw_profile) -> market_pb2.OfferSpecification:
        notbefore = conversion.pb_timestamp_from_time(datetime.now())
        notafter = Timestamp(
            seconds=notbefore.seconds + (len(bw_profile.split(",")) * defs.BW_PERIOD))
        specs = market_pb2.OfferSpecification(
            iaid=self.ia,
            notbefore=notbefore,
            notafter=notafter,
            bw_profile=bw_profile,
            price_per_unit=0.000000001,
            reachable_paths="*",
            br_address_template="127.0.0.1:50000-50100",
            br_mtu=1500,
            br_link_to="PARENT",
        )
        return specs

    def list(self) -> List[market_pb2.Offer]:
        with grpc.insecure_channel(self.service_address) as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            response = stub.ListOffers(market_pb2.ListRequest())
            offers = [o for o in response]
        return offers

    def buy_offer(self, offer: market_pb2.Offer, bw_profile, starting_on):
        """ returns the contract """
        # verify broker's signature
        offer_bytes = serialize.offer_serialize_to_bytes(offer, False)
        crypto.signature_validate(self.broker_cert, offer.specs.signature, offer_bytes)
        offer_bytes = serialize.offer_serialize_to_bytes(offer, True)
        request = market_pb2.PurchaseRequest(
            offer=offer,
            buyer_iaid=self.ia,
            signature=b"",
            bw_profile=bw_profile,
            starting_on=conversion.pb_timestamp_from_time(starting_on),
        )
        # sign the purchase request
        data = serialize.purchase_order_fields_serialize_to_bytes(
            offer_bytes,
            self.ia,
            request.bw_profile,
            request.starting_on.ToSeconds()
        )
        request.signature = crypto.signature_create(self.key, data)
        with grpc.insecure_channel(self.service_address) as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            return stub.Purchase(request)

    def get_contract(self, contract_id: int) -> market_pb2.Contract:
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
        with grpc.insecure_channel(self.service_address) as channel:
            stub = market_pb2_grpc.MarketControllerStub(channel)
            return stub.GetContract(request)
