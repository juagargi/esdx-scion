from django.db import models
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from util import crypto


class BrokerManager(models.Manager):
    """
    The Broker Manager allows for certain optimizations such as caching the key and certificate.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.broker_key = None
        self.broker_cert = None

    def _clear_cached_key_certificate(self):
        self.broker_key = None
        self.broker_cert = None

    def get(self, **kwargs):
        if super().all().count() > 1:
            raise RuntimeError("only one broker allowed (creating one but one already exists)")
        return super().get(**kwargs)

    def get_broker_key(self):
        if self.broker_key is None:
            self.broker_key = crypto.load_key(self.get().key_pem)
        return self.broker_key

    def get_broker_certificate(self):
        if self.broker_cert is None:
            self.broker_cert = crypto.load_certificate(self.get().certificate_pem)
        return self.broker_cert


class Broker(models.Model):
    objects = BrokerManager()
    class Meta:
        verbose_name = "Broker is the IXP"

    certificate_pem = models.TextField()  # the IXP's certificate, in PEM format
    key_pem = models.TextField()  # the IXP's key in PEM format


@receiver([pre_delete, pre_save], sender=Broker, dispatch_uid="broker_clear_cached_key_cert")
def _broker_clear_cached_key_cert(sender, instance, **kwargs):
    """
    Remove the cached key and cert.
    """
    Broker.objects._clear_cached_key_certificate()
