from django.db import models
from django.core import validators
from django.utils.timezone import is_naive
from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from defs import BW_PERIOD, BW_UNIT

from util.conversion import csv_to_intlist, ia_validator
from datetime import datetime


class OfferManager(models.Manager):
    def available(self, *args, **kwargs):
        return self.filter(purchase_order=None, *args, **kwargs)

    def get_available(self, *args, **kwargs):
        l = self.available(*args, **kwargs)
        if len(l) == 0:
            raise Offer.DoesNotExist()
        elif len(l) > 1:
            raise Offer.MultipleObjectsReturned()
        else:
            return l[0]

class Offer(models.Model):
    class Meta:
        verbose_name = "Bandwidth Offer by AS"

    objects = OfferManager()

    iaid = models.CharField(blank=False,
                            max_length=255,
                            verbose_name="The IA id like 1-ff00:1:1",
                            validators=[ia_validator()])
    iscore = models.BooleanField()
    signature = models.TextField()  # in the DB, this is signed by the IXP
    notbefore = models.DateTimeField()
    notafter = models.DateTimeField()  # the difference notafter - notbefore is len(bw_profile)
    # this will be a '\n' separated list of comma separated lists of ISD-AS#IF,IF sequences
    reachable_paths = models.TextField()
    qos_class = models.IntegerField()  # TRD
    # bw per period, e.g. 3,3,2,4,4 means 3 BW_UNIT during the first BW_PERIOD, then 3, then 2, etc
    price_per_nanounit = models.IntegerField()
    bw_profile = models.TextField(validators=[validators.int_list_validator()])

    def _pre_save(self):
        """ Checks validity, profile length """
        # TODO(juagargi) add test checking this function
        if is_naive(self.notbefore) or is_naive(self.notafter):
            raise ValueError("naive (without timezone) datetime objects not supported")
        if self.notafter < self.notbefore:
            raise ValueError("notafter must happen after notbefore")
        # check that the lifespan of the offer is a multiple of BW_PERIOD
        lifespan = self.notafter - self.notbefore
        if lifespan.total_seconds() % BW_PERIOD != 0:
            raise ValueError("the life span of the offer must be a multiple of BW_PERIOD "+
                             f"({BW_PERIOD} secs)")
        # check that there are enough values in the bw_profile
        profile = csv_to_intlist(self.bw_profile)
        if len(profile) != lifespan.total_seconds() // BW_PERIOD:
            raise ValueError(f"bw_profile should contain exactly "+
                             f"{lifespan.total_seconds() // BW_PERIOD} values; contains {len(profile)}")

    def validate_signature(self):
        return True  # TODO(juagargi) do it

    def contains_profile(self, bw_profile: str, starting: datetime) -> bool:
        return self.purchase(bw_profile, starting) != None

    def purchase(self, bw_profile: str, starting: datetime) -> str:
        """
        returns a new bw profile or None if not possible to purchase
        Cannot purchase negative bw, or total of zero bw, or before/after the profile
        """
        that_prof = csv_to_intlist(bw_profile)
        orig_prof = csv_to_intlist(self.bw_profile)
        offset = (starting - self.notbefore).total_seconds()
        if offset % BW_PERIOD != 0 or offset < 0:
            return None
        offset = int(offset // BW_PERIOD)
        this_prof = orig_prof[offset:]
        if len(that_prof) > len(this_prof):
            return None
        new_prof = []
        total_bought = 0
        for bw, other in zip(this_prof, that_prof):
            if other > bw or other < 0:
                return None
            new_prof.append(bw - other)
            total_bought += other
        if total_bought == 0:
            return None
        # save the new_prof chunk after the offset
        orig_prof[offset:offset+len(new_prof)] = new_prof
        return ",".join([str(i) for i in orig_prof])


@receiver(pre_save, sender=Offer, dispatch_uid="offer_pre_save")
def _offer_pre_save(sender, instance, **kwargs):
    """ signal for pre_save validates instance before saving it """
    instance._pre_save()

@receiver(pre_delete, sender=Offer, dispatch_uid="offer_pre_delete")
def _offer_pre_delete(sender, instance, **kwargs):
    """
    Signal for pre_delete always raises an exception
    The reason is that offers are never deleted, as they are needed to verify
    existing or past contracts.
    """
    raise RuntimeError("logic error: pre_delete: not allowed to delete any Offer object")


def fields_serialize_to_bytes(
    iaid: str,
    iscore:bool,
    notbefore: int,
    notafter: int,
    reachable_paths: str,
    qos_class: int,
    price_per_nanounit: int,
    bw_profile: str) -> bytes:
    """
    Fields:
    notbefore, notafter: in seconds from UTC epoch
    """
    s = "ia:" + iaid + ("1" if iscore else "0") + str(notbefore) + str(notafter) + \
        "reachable:" + reachable_paths + str(qos_class) + str(price_per_nanounit) + \
        "profile:" + bw_profile
    return s.encode("ascii")
