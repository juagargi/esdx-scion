#!/usr/bin/env python

# Create one provider with a big offer (N units)


from util.experiments import Runner, MarketClient
import sys


def provider(ia: str):
    p = MarketClient(ia, "localhost:50051")
    for i in range(10):
        o = p.create_simplified_offer("20000")
        saved = p.sell_offer(o)
        print(f"provider created offer with id {saved.id}")
    return 0


def main():
    r = Runner(
        provider,
        [
            ("1-ff00:0:110", ),
        ],
        None,[],
    )
    ret = r.run(True)
    if ret != 0:
        raise RuntimeError(f"experiment1 failed with {ret} for N = {N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
