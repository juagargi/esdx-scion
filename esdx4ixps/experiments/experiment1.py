#!/usr/bin/env python

# Create one provider with a big offer (N units)
# Create N buyers buying a small portion. All could by their portion.
# Measure time as N increases


from util import conversion
from util.experiments import Runner, MarketClient
from provider import provider

import sys
import time
import grpc



def client(ia: str, wait: int):
    c = MarketClient(ia, "localhost:50051")
    pb_contract = None
    for _ in range(1000):
        offers = c.list()
        time.sleep(wait)
        try:
            pb_contract = c.buy_offer(
                offer=offers[0],
                bw_profile="1",
                starting_on=conversion.time_from_pb_timestamp(offers[0].specs.notbefore),
            )
            # print(f"Client with ID: {ia} got contract with ID: {pb_contract.contract_id}")
            sys.stdout.write(".")
            sys.stdout.flush()
            break
        except grpc.RpcError as ex:
            # print(f"Client with ID: {ia} could not buy: {ex.details()}")
            continue
    if pb_contract is None:
        print(f"Client with ID: {ia} too many attempts")
        return 1
    # unnecessary, but check the contract obtained independently
    pb_contract2 = c.get_contract(pb_contract.contract_id)
    if pb_contract.contract_signature != pb_contract2.contract_signature:
        raise RuntimeError("contract from get_contract: signatures are different!")
    # send contract to the topology reloader
    # TODO(juagargi)
    return 0


def experiment1(N: int) -> float:
    """ returns the elapsed time to run the experiment1 with N buyers """
    r = Runner(
        provider,
        [
            ("1-ff00:0:110", ),
        ],
        client,
        [("1-ff00:0:111", 0,)] * N,
    )
    ret = r.run(True)
    if ret != 0:
        raise RuntimeError(f"experiment1 failed with {ret} for N = {N}")
    return r.timings["after_execution"] - r.timings["before_execution"]

def main():
    results = {}
    for i in range(0, 101, 10):
        results[i] = experiment1(i)
        print(f"-------------------------- done {i}")
    print(f"done")
    print("========================================")
    print("========================================")
    for k, v in results.items():
        print(f"{k}:\t\t {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
