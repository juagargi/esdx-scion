from typing import List
from django.utils import timezone as tz
from django.utils import dateparse
from django.core.exceptions import ValidationError
from google.protobuf.timestamp_pb2 import Timestamp
import pytz


def csv_to_intlist(csv: str) -> List[int]:
    l = csv.split(",")
    return list(map(int, l))  # do int("4") for each component


def time_from_str(s: str):
    return dateparse.parse_datetime(s)


def time_from_pb_timestamp(timestamp):
    t = tz.datetime.fromtimestamp(timestamp.seconds + timestamp.nanos / 1e9)
    return t.replace(tzinfo=pytz.utc)

def pb_timestamp_from_seconds(s: int):
    return Timestamp(seconds=s)

def pb_timestamp_from_time(time):
    return pb_timestamp_from_seconds(time.timestamp())


def pb_timestamp_from_str(s: str):
    return pb_timestamp_from_time(time_from_str(s))


def ia_str_to_int(ia: str) -> int:
    ia = str(ia)
    # inspired from scionproto's python.lib.scion_addr parse routines
    parts = ia.split("-")
    if len(parts) != 2:
        raise ValueError("expected ISD-AS")
    if parts[0].strip() != parts[0]:
        raise ValueError("ISD part contains blanks")
    if parts[1].strip() != parts[1]:
        raise ValueError("AS part contains blanks")
    isd = int(parts[0])
    if isd > 65535:
        raise ValueError(f"ISD out of range: {isd}")

    as_parts = parts[1].split(":")
    if len(as_parts) == 1:
        if as_parts[0].strip() != as_parts[0]:
            raise ValueError("AS part contains blanks")
        # it must be a decimal number (BGP AS)
        as_value = int(as_parts[0])
        if as_value > (1 << 32) - 1:
            raise ValueError(f"decimal value for AS is too big {as_value}")
    elif len(as_parts) != 3:
        raise ValueError("expected 3 parts in AS")
    else:
        as_value = 0
        for i, s in enumerate(as_parts):
            if s.strip() != s:
                raise ValueError("AS part contains blanks")
            as_value <<= 16
            v = int(s, base=16)
            if v > 65535:
                raise ValueError(f"AS part too big {v}")
            as_value |= v
        if as_value > (1 << 48) - 1:
            raise ValueError("AS value is too large")
    return (isd << 48) | as_value


def _ia_validator(ia: str):
    try:
        ia_str_to_int(ia)
    except ValueError as ex:
        raise ValidationError(f"not a valid IA value: {str(ex)}")


def ia_validator():
    """ returns a validator that validates IA of the form 1-ff00:0:111 """
    return _ia_validator
