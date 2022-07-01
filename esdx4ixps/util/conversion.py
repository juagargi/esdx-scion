from ipaddress import IPv4Address, IPv6Address, AddressValueError, NetmaskValueError
from django.utils import timezone as tz
from django.utils import dateparse
from django.core.exceptions import ValidationError
from google.protobuf.timestamp_pb2 import Timestamp
from typing import List, Tuple, Union
import pytz
import re


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
    return pb_timestamp_from_seconds(int(time.timestamp()))


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


def _ip_and_string_from_str(s:str) -> Tuple[Union[IPv4Address, IPv6Address], str]:
    try:
        parts = re.search("(.*):(.*)", s).groups()
    except Exception as ex:
        raise ValueError(f"invalid address {s}") from ex
    if len(parts) != 2:
        raise ValueError(f"invalid address {s}")
    # IP address must be written as IPv4 or [IPv6]
    try:
        ip = IPv4Address(parts[0])
    except (AddressValueError, NetmaskValueError):
        addr = parts[0].strip("[]")
        if addr == parts[0]:
            raise ValueError(f"invalid address {s}") # missing []
        ip = IPv6Address(addr)
    return ip, parts[1]

def ip_port_from_str(s: str) -> Tuple[Union[IPv4Address, IPv6Address], int]:
    ip, port = _ip_and_string_from_str(s)
    port = int(port)
    if port < 0 or port > 65534:
        raise ValueError(f"invalid address {s}")
    return (ip, port)

def ip_port_range_from_str(s: str) -> Tuple[Union[IPv4Address, IPv6Address], int, int]:
    """ returns the IP, the min port and the max port """
    ip, port_range = _ip_and_string_from_str(s)
    port_range = port_range.split("-")
    if len(port_range) != 2:
        raise ValueError(f"invalid port range in {s}")
    [min, max] = sorted([int(port_range[0]), int(port_range[1])])
    if max > 65534:
        raise ValueError(f"invalid port range in {s} (max out of range)")
    return ip, min, max

def ip_port_to_str(ip: Union[IPv4Address,IPv6Address], port: int) -> str:
    ip = f"[{ip}]" if ip.version == 6 else f"{ip}"
    return f"{ip}:{port}"
