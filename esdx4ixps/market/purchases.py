from datetime import datetime
import traceback
from urllib import request
from django.db import transaction
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import rsa
from market.models.offer import Offer
from market.models.ases import AS
from market.models.purchase_order import PurchaseOrder
from market.models.contract import Contract
from util import conversion
from util import crypto
from util import serialize

import copy


def find_available_br_address(offer: Offer) -> str:
    """
    returns a br_address with the ip and the first available port not in use
    by walking the offer linked list and retrieving all used addresses.
    The "offer" argument is the available offer signed by the broker.
    """
    template = offer.br_address_template
    ip, min_port, max_port = conversion.ip_port_range_from_str(template)
    # get last contract; if it exists it will contain the last port used
    port = min_port
    if offer.deprecates is not None and offer.deprecates.is_sold():
        _, port = conversion.ip_port_from_str(offer.deprecates.purchase_order.contract.br_address)
        port += 1
    if port > max_port:
        raise RuntimeError(f"cannot find a free port with template {template}")
    return conversion.ip_port_to_str(ip, port)


def purchase_offer(
    requested_offer: Offer,
    available_offer: Offer,
    buyer_iaid: str,
    buyer_starting_on: datetime,
    buyer_bw_profile: str,
    buyer_signature: bytes,
) -> Tuple[Contract, Offer]:
    """
    Returns the contract and the new offer
    requested_offer: the offer that was originally specified in the purchase order
    available_offer: the offer that being derived from the requested_offer is still available
    """
    with transaction.atomic():
        # find buyer
        buyer = AS.objects.get(iaid=buyer_iaid)
        new_profile = available_offer.purchase(buyer_bw_profile, buyer_starting_on)
        if new_profile is None:
            raise RuntimeError("offer does not contain the requested BW profile")

        # create purchase order will already validate the signature:
        purchase_order = PurchaseOrder.objects.create(
            offer_id=available_offer.id,
            buyer=buyer,
            signature=buyer_signature,
            bw_profile=buyer_bw_profile,
            starting_on=buyer_starting_on,
        )
        # validate the purchase order signature with the original requested offer
        purchase_order.validate_signature(requested_offer)

        # create contract
        contract = Contract(
            purchase_order=purchase_order,
        )
        contract.br_address = find_available_br_address(available_offer)
        contract.stamp_signature(requested_offer)
        contract.save()
        # validate the contract using the purchase order with the original requested offer:
        contract.validate_signature(requested_offer)
        # create new offer
        new_offer = available_offer.clone()
        new_offer.id = None
        new_offer.deprecates = available_offer
        new_offer.bw_profile = new_profile
        new_offer.sign_with_broker()
        new_offer.save()
    return contract, new_offer


def sign_purchase_order(
    buyer_ia: str,
    buyer_key: rsa.RSAPrivateKey,
    o: Offer,
    starting_on: datetime,
    bw_profile: str) -> str:
    """ creates a signature for the fields of a purchase order """
    data = serialize.purchase_order_fields_serialize_to_bytes(
        offer_bytes=o.serialize_to_bytes(True),
        ia_id=buyer_ia,
        bw_profile=bw_profile,
        starting_on=int(starting_on.timestamp())
    )
    return crypto.signature_create(buyer_key, data)


def sign_get_contract_request(
    requester_key: rsa.RSAPrivateKey,
    requester_iaid: str,
    contract_id: int,
    ):
    data = serialize.get_contract_request_serialize(
        contract_id,
        requester_iaid,
        b"",
    )
    return crypto.signature_create(requester_key, data)
