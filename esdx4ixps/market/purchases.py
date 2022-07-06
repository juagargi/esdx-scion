from datetime import datetime
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


def purchase_offer(offer: Offer,
                   buyer_iaid: str,
                   buyer_starting_on: datetime,
                   buyer_bw_profile: str,
                   buyer_signature: bytes) -> Tuple[Contract, Offer]:
    """
    Returns the contract and the new offer
    """
    with transaction.atomic():
        # find buyer
        buyer = AS.objects.get(iaid=buyer_iaid)
        new_profile = offer.purchase(buyer_bw_profile, buyer_starting_on)
        if new_profile is None:
            raise RuntimeError("offer does not contain the requested BW profile")

        # create purchase order will already validate the signature:
        purchase_order = PurchaseOrder.objects.create(
            offer_id=offer.id,
            buyer=buyer,
            signature=buyer_signature,
            bw_profile=buyer_bw_profile,
            starting_on=buyer_starting_on)        

        # create contract
        contract = Contract(
            purchase_order=purchase_order,
        )
        contract.br_address = find_available_br_address(offer)
        contract.stamp_signature()
        contract.save()
        # create new offer
        new_offer = copy.deepcopy(offer)
        new_offer.id = None
        new_offer.deprecates = offer
        new_offer.bw_profile = new_profile
        new_offer.sign_with_broker()
        new_offer.save()
        return contract, new_offer


def sign_purchase_order(
    buyer_key: rsa.RSAPrivateKey,
    o: Offer,
    starting_on: datetime,
    bw_profile: str) -> str:
    """ creates a signature for the fields of a purchase order """
    data = serialize.purchase_order_fields_serialize_to_bytes(
        o.serialize_to_bytes(True),
        bw_profile,
        int(starting_on.timestamp())
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
