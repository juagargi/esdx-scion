from typing import List
from django.utils import timezone as tz
from google.protobuf.timestamp_pb2 import Timestamp
import pytz


def csv_to_intlist(csv: str) -> List[int]:
    l = csv.split(",")
    return list(map(int, l))  # do int("4") for each component


def time_from_pb_timestamp(timestamp):
    t = tz.datetime.fromtimestamp(timestamp.seconds + timestamp.nanos / 1e9)
    return t.replace(tzinfo=pytz.utc)


def pb_timestamp_from_time(time):
    return Timestamp(seconds=int(time.timestamp()))
