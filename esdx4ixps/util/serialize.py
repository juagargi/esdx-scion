import market_pb2


def offer_fields_serialize_to_bytes(
    iaid: str,
    notbefore: int,
    notafter: int,
    reachable_paths: str,
    qos_class: int,
    price_per_unit: float,
    bw_profile: str,
    br_address_template: str,
    br_mtu: int,
    br_link_to: str,
    signature: bytes) -> bytes:
    """
    Fields:
    notbefore, notafter: in seconds from UTC epoch
    """
    s = "ia:" + iaid + str(notbefore) + str(notafter) + \
        "reachable:" + reachable_paths + str(qos_class) + "{:e}".format(price_per_unit) + \
        "profile:" + bw_profile + "br_address_template:" + br_address_template + \
        "br_mtu:" + str(br_mtu) + "br_link_to:" + br_link_to + "signature:"
    return s.encode("ascii") + signature


def offer_specification_serialize_to_bytes(
    s: market_pb2.OfferSpecification, include_signature: bool) -> bytes:
    return offer_fields_serialize_to_bytes(
        s.iaid,
        s.notbefore.seconds,
        s.notafter.seconds,
        s.reachable_paths,
        s.qos_class,
        s.price_per_unit,
        s.bw_profile,
        s.br_address_template,
        s.br_mtu,
        s.br_link_to,
        s.signature if include_signature else b"",
    )


def offer_serialize_to_bytes(o: market_pb2.Offer, include_signature: bool) -> bytes:
    return offer_specification_serialize_to_bytes(o.specs, include_signature)


def purchase_order_fields_serialize_to_bytes(
    offer_bytes: bytes,
    ia_id: str,
    bw_profile: str,
    starting_on: int) -> bytes:
    """
    Fields:
    offer: offer serialized to bytes, without signature
    starting_on: in seconds from UTC epoch
    """
    return b"offer:" + offer_bytes + b"bw_profile:" + bw_profile.encode("ascii") + \
        b"buyer:" + ia_id.encode("ascii") + b"starting_on:" + str(starting_on).encode("ascii")


def contract_fields_serialize_to_bytes(
    purchase_order_bytes: bytes,
    buyer_signature: bytes,
    timestamp: int,
    br_address: str,
) -> bytes:
    """
    Fields:
    buyer_signature: signature of the purchase order, by the buyer, base64 encoded
    timestamp: in seconds since UTC epoch
    """
    return b"order:" + purchase_order_bytes + \
        b"signature_buyer:" + buyer_signature + b"timestamp:" + str(timestamp).encode("ascii") + \
        b"br_address:" + br_address.encode("ascii")


def get_contract_request_serialize(
    contract_id: int,
    requester_iaid: str,
    signature: bytes,
    ):
    """ This ALSO serializes the signature """
    if signature is None:
        signature = b""
    return b"contract_id:" + str(contract_id).encode("ascii") + b"signature:" + signature + \
        b"requester_ia:" + requester_iaid.encode("ascii")
