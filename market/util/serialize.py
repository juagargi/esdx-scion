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


def purchase_order_fields_serialize_to_bytes(
    offer_bytes: bytes,
    bw_profile: str,
    starting_on: int) -> bytes:
    """
    Fields:
    offer: offer serialized to bytes, without signature
    starting_on: in seconds from UTC epoch
    """
    return b"offer:" + offer_bytes + b"bw_profile:" + bw_profile.encode("ascii") + \
        b"starting_on:" + str(starting_on).encode("ascii")


def contract_fields_serialize_to_bytes(
    purchase_order_bytes: bytes,
    buyer_signature: str,
    timestamp: int,
) -> bytes:
    """
    Fields:
    buyer_signature: signature of the purchase order, by the buyer, base64 encoded
    timestamp: in seconds since UTC epoch
    """
    return b"order:" + purchase_order_bytes + \
        b"signature_buyer:" + buyer_signature.encode("ascii") + \
        b"timestamp:" + str(timestamp).encode("ascii")
