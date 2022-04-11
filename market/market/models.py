from django.db import models


class Offer(models.Model):
    iaid = models.BigIntegerField()
    comment = models.TextField()  # deleteme

    def __str__(self):
        return f'Offer ID:{self.iaid}, Comment:{self.comment}'
