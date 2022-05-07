from django.db import models
from django.core import validators
from django.utils.timezone import is_naive
from django.db.models.signals import pre_save
from django.dispatch import receiver

from util.conversion import csv_to_intlist
from datetime import datetime

from market.models.offer import Offer


class PurchaseOrder(models.Model):
    """
    Represents a signed (by the buyer) and valid purchase order.
    PurchaseOrder is saved only when it is actuated to create a contract and remove the Offer.
    """
    class Meta:
        verbose_name = "Signed Purchase Order"

    # offer_id = models.BigIntegerField() # TODO(juagargi) make this a foreign key

    offer = models.OneToOneField(
        Offer,
        related_name='purchase_order',
        on_delete=models.CASCADE,
    )
    buyer_id = models.BigIntegerField() # TODO(juagargi) make this a foreign key
    signature = models.BinaryField()
    bw_profile = models.TextField(validators=[validators.int_list_validator()])
    starting_on = models.DateTimeField()

    def _pre_save(self):
        if not self.validate_signature():
            raise ValueError("invalid purchase order signature")

    def validate_signature(self):
        return True  # TODO(juagargi) do it

@receiver(pre_save, sender=PurchaseOrder, dispatch_uid="purchaseorder_pre_save")
def _purchaseorder_pre_save(sender, instance, **kwargs):
    """ signal for pre_save validates instance before saving it """
    instance._pre_save()
