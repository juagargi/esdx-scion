from django.db import models
from django.core import validators
from market.models.offer import Offer
from util import crypto
from util import serialize


class PurchaseOrder(models.Model):
    """
    Represents a signed (by the buyer) and valid purchase order.
    PurchaseOrder is saved only when it is actuated to create a contract and remove the Offer.
    """
    class Meta:
        verbose_name = "Signed Purchase Order"

    offer = models.OneToOneField(
        Offer,
        related_name='purchase_order',
        on_delete=models.CASCADE,
    )
    buyer = models.ForeignKey(
        'AS',
        on_delete=models.PROTECT
    )
    signature = models.BinaryField()
    bw_profile = models.TextField(validators=[validators.int_list_validator()])
    starting_on = models.DateTimeField()

    def serialize_to_bytes(self, requested_offer) -> bytes:
        offerbytes = requested_offer.serialize_to_bytes(True)
        return serialize.purchase_order_fields_serialize_to_bytes(
            offerbytes,
            self.buyer.iaid,
            self.bw_profile,
            int(self.starting_on.timestamp())
        )

    def validate_signature(self, requested_offer: Offer):
        # get certificate
        cert = crypto.load_certificate(self.buyer.certificate_pem)
        # serialize purchase order
        data = self.serialize_to_bytes(requested_offer)
        # validate signature
        crypto.signature_validate(cert, self.signature, data)
