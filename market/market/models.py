from django.db import models
from django.core import validators
from util.conversion import csv_to_intlist
from datetime import datetime


# define constants
BW_UNIT = 1000000000  # 1 Gbps
BW_PERIOD = 600  # 600 seconds = 10 minutes

# class DateTimeRangeField(models.Field):
#     description = "A datetime range (start-end)"
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)


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
    bw_profile = models.TextField(validators=[validators.int_list_validator()])
    price_per_nanounit = models.IntegerField()

    def contains_profile(self, bw_profile: str, starting: datetime) -> bool:
        if len(bw_profile) > len(self.bw_profile):
            return False
        this_prof = csv_to_intlist(self.bw_profile)
        that_prof = csv_to_intlist(bw_profile)
        for bw,other in zip(this_prof, that_prof):
            if other>bw:
                return False
        return True

