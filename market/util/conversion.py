
from typing import List

def csv_to_intlist(csv: str) -> List[int]:
    l = csv.split(",")
    return list(map(int, l))  # do int("4") for each component
