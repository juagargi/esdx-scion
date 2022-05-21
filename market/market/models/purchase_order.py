from django.db import models
from django.core import validators
from django.db.models.signals import pre_save
from django.dispatch import receiver
from market.models.offer import Offer
from util import crypto


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
    signature = models.TextField()
    bw_profile = models.TextField(validators=[validators.int_list_validator()])
    starting_on = models.DateTimeField()

    def _pre_save(self):
        try:
            self.validate_signature()
        except ValueError as ex:
            raise ValueError("invalid purchase order signature") from ex

    def serialize_to_bytes(self) -> bytes:
        offerbytes = self.offer.serialize_to_bytes()
        return fields_serialize_to_bytes(
            offerbytes,
            self.bw_profile,
            int(self.starting_on.timestamp())
        )

    def validate_signature(self):
        # get certificate
        cert = crypto.load_certificate(self.buyer.certificate_pem)
        # serialize purchase order
        data = self.serialize_to_bytes()
        # validate signature
        crypto.signature_validate(cert, self.signature, data)


@receiver(pre_save, sender=PurchaseOrder, dispatch_uid="purchaseorder_pre_save")
def _purchaseorder_pre_save(sender, instance, **kwargs):
    """ signal for pre_save validates instance before saving it """
    instance._pre_save()


def fields_serialize_to_bytes(
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
