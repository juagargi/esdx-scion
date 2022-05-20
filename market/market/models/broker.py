from django.db import models
from django.core import validators
from django.utils.timezone import is_naive
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from cryptography import x509
from defs import BW_PERIOD, BW_UNIT

from util.conversion import ia_validator
from util import crypto
from datetime import datetime


class BrokerManager(models.Manager):
    def create(self, *args, **kwargs):
        if super().all().count() > 0:
            raise RuntimeError("only one broker allowed (creating one but one already exists)")
        return super().create(*args, **kwargs)


class Broker(models.Model):
    class Meta:
        verbose_name = "Broker is the IXP"

    certificate_pem = models.TextField()  # the IXP's certificate, in PEM format
    key_pem = models.TextField()  # the IXP's key in PEM format
