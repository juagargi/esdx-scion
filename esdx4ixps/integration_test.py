#!/usr/bin/env python

# This test runs Django gRPC, a provider, and two clients.
# The provider adds an offer and the clients list and attempt to buy it.
# The profile that the clients buy is exactly half of the offer, so the
# aggregation of the purchases should fit. Because the first client to
# buy the offer will destroy the original offer (as its bandwidth is now halved),
# the second client will need to list and buy again.

# The test ends terminating Django gRPC.
# The test exits with 0 if okay, non zero otherwise.


from util import conversion
from util.experiments import Runner, MarketClient

import sys
import time
import grpc


def provider():
    p = MarketClient("1-ff00:0:110", "localhost:50051")
    o = p.create_simplified_offer("2,2,2,2")
    saved = p.sell_offer(o)
    print(f"provider created offer with id {saved.id}")
    return 0


def client(ia: str, wait: int):
    c = MarketClient(ia, "localhost:50051")
    pb_contract = None
    for _ in range(2):
        offers = c.list()
        time.sleep(wait)
        try:
            pb_contract = c.buy_offer(
                offer=offers[0],
                bw_profile="1,1,1,1",
                starting_on=conversion.time_from_pb_timestamp(offers[0].specs.notbefore),
            )
            print(f"Client with ID: {ia} got contract with ID: {pb_contract.contract_id}")
            break
        except grpc.RpcError as ex:
            print(f"Client with ID: {ia} could not buy: {ex.details()}")
            continue
    if pb_contract is None :
        print(f"Client with ID: {ia} too many attempts")
        return 1
    # unnecessary, but check the contract obtained independently
    pb_contract2 = c.get_contract(pb_contract.contract_id)
    if pb_contract.contract_signature != pb_contract2.contract_signature:
        raise RuntimeError("contract from get_contract: signatures are different!")
    # send contract to the topology reloader
    # TODO(juagargi)
    return 0



def main():
    r = Runner(
        provider,
        [(),],
        client,
        [
            ("1-ff00:0:111", 0.2),
            ("1-ff00:0:112", 0),
        ],
    )
    ret = r.run()
    print(f"done (exits with {ret})")
    return ret



if __name__ == "__main__":
    sys.exit(main())
