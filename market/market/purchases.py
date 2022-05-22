from datetime import datetime
from django.db import transaction
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import rsa
from market.models.offer import Offer
from market.models.ases import AS
from market.models.purchase_order import PurchaseOrder
from market.models.contract import Contract
from util import crypto
from util import serialize



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

        # create purchse order will already validate the signature:
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
        contract.stamp_signature()
        contract.save()
        # create new offer
        offer.id = None
        offer.bw_profile = new_profile
        offer.save()
        return contract, offer


def sign_purchase_order(
    buyer_key: rsa.RSAPrivateKey,
    o: Offer,
    starting_on: datetime,
    bw_profile: str) -> str:
    """ creates a signature for the fields of a purchase order """
    data = serialize.purchase_order_fields_serialize_to_bytes(
        o.serialize_to_bytes(),
        bw_profile,
        int(starting_on.timestamp())
    )
    return crypto.signature_create(buyer_key, data)
