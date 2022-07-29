#!/usr/bin/env python3

import sys


def main():
    for line in sys.stdin.readlines():
        #   10:                    0.063181735
        pair = line.strip().split(":")
        if len(pair) != 2:
            raise RuntimeError(f"""bad line: "{line}" """)
        x,y = pair[0].strip(), pair[1].strip()
        print(f"({x},{y})")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
