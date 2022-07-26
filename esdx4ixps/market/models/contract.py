from urllib import request
from django.db import models
from django.utils import timezone as tz

from market.models.broker import Broker
from market.models.offer import Offer
from market.models.purchase_order import PurchaseOrder
from util import conversion
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
    br_address = models.TextField()
    signature_broker = models.BinaryField()  # signature from the broker (the IXP)

    def validate_signature(self, requested_offer: Offer):
        # get certificate
        cert = Broker.objects.get_broker_certificate()
        # serialize purchase order
        data = self.serialize_to_bytes(requested_offer)
        # validate signature
        crypto.signature_validate(cert, self.signature_broker, data)

    def serialize_to_bytes(self, requested_offer: Offer) -> bytes:
        return serialize.contract_fields_serialize_to_bytes(
            self.purchase_order.serialize_to_bytes(requested_offer),
            self.purchase_order.signature,
            int(self.timestamp.timestamp()),
            self.br_address,
        )

    def stamp_signature(self, requested_offer: Offer):
        """ uses now as the timestamp, and the broker as the signer """
        self.timestamp = tz.now()
        # get broker's private key
        key = Broker.objects.get_broker_key()
        # serialize contract
        data = self.serialize_to_bytes(requested_offer)
        # sign
        self.signature_broker = crypto.signature_create(key, data)
