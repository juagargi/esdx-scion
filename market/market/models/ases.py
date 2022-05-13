from django.db import models
from django.core import validators
from django.utils.timezone import is_naive
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from defs import BW_PERIOD, BW_UNIT

from util.conversion import csv_to_intlist, ia_validator
from datetime import datetime



class AS(models.Model):
    class Meta:
        verbose_name = "AS in the IXP"

    iaid = models.CharField(primary_key=True,
                            blank=False,
                            max_length=255,
                            verbose_name="The IA id like 1-ff00:1:1",
                            validators=[ia_validator()])
    certificate_pem = models.TextField()
    key_pem = models.TextField()
