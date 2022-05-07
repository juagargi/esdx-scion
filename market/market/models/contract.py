from django.db import models
from django.core import validators
from django.utils.timezone import is_naive
from django.db.models.signals import pre_save
from django.dispatch import receiver

from util.conversion import csv_to_intlist

from market.models.purchase import PurchaseOrder


class Contract(models.Model):
    """
    Contract signed by the broker (IXP) when a purchase order is created.
    """
    class Meta:
        verbose_name = "Contract"

    purchase_order = models.OneToOneField(
        PurchaseOrder,
        related_name='contract',
        on_delete=models.CASCADE,
    )
    timestamp = models.DateTimeField(auto_now=True)
    signature_broker = models.BinaryField()

    def _pre_save(self):
        if not self.validate_signature():
            raise ValueError("invalid contract signature")

    def validate_signature(self):
        return True  # TODO(juagargi) do it

@receiver(pre_save, sender=Contract, dispatch_uid="contract_pre_save")
def _contract_pre_save(sender, instance, **kwargs):
    """ signal for pre_save validates instance before saving it """
    instance._pre_save()
