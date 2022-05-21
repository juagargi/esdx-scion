from datetime import datetime
from django.db import transaction
from market.models.offer import Offer
from market.models.purchase_order import PurchaseOrder
from market.models.contract import Contract



def purchase_offer(offer: Offer,
                   buyer_id: int,
                   buyer_starting_on: datetime,
                   buyer_bw_profile: str,
                   buyer_signature: bytes) -> (Contract, Offer):
    """
    Returns the contract and the new offer
    """
    with transaction.atomic():
        new_profile = offer.purchase(buyer_bw_profile, buyer_starting_on)
        if new_profile is None:
            raise RuntimeError("offer does not contain the requested BW profile")

        # create purchse order will already validate the signature:
        purchase_order = PurchaseOrder.objects.create(
            offer_id=offer.id,
            buyer_id=buyer_id,
            signature=buyer_signature,
            bw_profile=buyer_bw_profile,
            starting_on=buyer_starting_on)        

        # create contract
        contract = Contract.objects.create(
            purchase_order=purchase_order,
            signature_broker=b"",  # TODO(juagargi) implement signing the contract
        )
        # create new offer
        offer.id = None
        offer.bw_profile = new_profile
        offer.save()
        return contract, offer