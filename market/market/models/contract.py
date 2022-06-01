from django.db import models
from django.utils import timezone as tz
from django.db.models.signals import pre_save
from django.dispatch import receiver

from market.models.purchase_order import PurchaseOrder
from market.models.broker import Broker
from util import crypto
from util import serialize


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
    timestamp = models.DateTimeField()
    signature_broker = models.TextField()

    def _pre_save(self):
        try:
            self.validate_signature()
        except ValueError as ex:
            raise ValueError("invalid contract signature") from ex

    def validate_signature(self):
        # get certificate
        cert = crypto.load_certificate(Broker.objects.get().certificate_pem)
        # serialize purchase order
        data = self.serialize_to_bytes()
        # validate signature
        crypto.signature_validate(cert, self.signature_broker, data)

    def serialize_to_bytes(self) -> bytes:
        return serialize.contract_fields_serialize_to_bytes(
            self.purchase_order.serialize_to_bytes(),
            self.purchase_order.signature,
            self.timestamp
        )

    def stamp_signature(self):
        """ uses now as the timestamp, and the broker as the signer """
        self.timestamp = tz.now()
        # get private key
        key = crypto.load_key(Broker.objects.get().key_pem)
        # serialize contract
        data = self.serialize_to_bytes()
        # sign
        self.signature_broker = crypto.signature_create(key, data)


@receiver(pre_save, sender=Contract, dispatch_uid="contract_pre_save")
def _contract_pre_save(sender, instance, **kwargs):
    """ signal for pre_save validates instance before saving it """
    instance._pre_save()
