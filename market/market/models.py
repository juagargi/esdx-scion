# from multiprocessing.sharedctypes import Value
from django.db import models
from django.core import validators
from django.utils.timezone import is_naive
from django.db.models.signals import pre_save
from django.dispatch import receiver

from util.conversion import csv_to_intlist
from datetime import datetime


# define constants
BW_UNIT = 1000000000  # 1 Gbps
BW_PERIOD = 600  # 600 seconds = 10 minutes


class Offer(models.Model):
    class Meta:
        verbose_name = "Bandwidth Offer by AS"

    iaid = models.BigIntegerField()
    iscore = models.BooleanField()
    signature = models.BinaryField()
    notbefore = models.DateTimeField()
    notafter = models.DateTimeField()
    # this will be a '\n' separated list of comma separated lists of ISD-AS#IF,IF sequences
    reachable_paths = models.TextField()
    qos_class = models.IntegerField()  # TRD
    # bw per period, e.g. 3,3,2,4,4 means 3 BW_UNIT during the first BW_PERIOD, then 3, then 2, etc
    price_per_nanounit = models.IntegerField()
    bw_profile = models.TextField(validators=[validators.int_list_validator()])

    def _pre_save(self):
        """ Checks validity, profile length """
        if is_naive(self.notbefore) or is_naive(self.notafter):
            raise ValueError("naive (without timezone) datetime objects not supported")
        if self.notafter < self.notbefore:
            raise ValueError("notafter must happen after notbefore")
        # check that the lifespan of the offer is a multiple of BW_PERIOD
        lifespan = self.notafter - self.notbefore
        if lifespan.seconds % BW_PERIOD != 0:
            raise ValueError("the life span of the offer must be a multiple of BW_PERIOD "+
                             f"({BW_PERIOD} secs)")
        # check that there are enough values in the bw_profile
        profile = csv_to_intlist(self.bw_profile)
        if len(profile) != lifespan.seconds // BW_PERIOD:
            raise ValueError(f"bw_profile should contain exactly {lifespan.seconds // BW_PERIOD} values")

    def contains_profile(self, bw_profile: str, starting: datetime) -> bool:
        if len(bw_profile) > len(self.bw_profile):
            return False
        this_prof = csv_to_intlist(self.bw_profile)
        that_prof = csv_to_intlist(bw_profile)
        for bw,other in zip(this_prof, that_prof):
            if other>bw:
                return False
        return True


@receiver(pre_save, sender=Offer, dispatch_uid="offer_pre_save")
def _offer_pre_save(sender, instance, **kwargs):
    """ signal for pre_save validates instance before saving it """
    instance._pre_save()
