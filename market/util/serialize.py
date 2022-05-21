import market_pb2


def offer_fields_serialize_to_bytes(
    iaid: str,
    iscore:bool,
    notbefore: int,
    notafter: int,
    reachable_paths: str,
    qos_class: int,
    price_per_nanounit: int,
    bw_profile: str) -> bytes:
    """
    Fields:
    notbefore, notafter: in seconds from UTC epoch
    """
    s = "ia:" + iaid + ("1" if iscore else "0") + str(notbefore) + str(notafter) + \
        "reachable:" + reachable_paths + str(qos_class) + str(price_per_nanounit) + \
        "profile:" + bw_profile
    return s.encode("ascii")


def offer_serialize_to_bytes(o: market_pb2.Offer) -> bytes:
    return offer_fields_serialize_to_bytes(
        o.iaid,
        o.iscore,
        o.notbefore.seconds,
        o.notafter.seconds,
        o.reachable_paths,
        o.qos_class,
        o.price_per_nanounit,
        o.bw_profile
    )
