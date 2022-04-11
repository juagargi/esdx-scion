from django.db import models


class Offer(models.Model):
    ia_id = models.BigIntegerField()
    comment = models.TextField()

    def __str__(self):
        return f'Offer ID:{self.ia_id}, Comment:{self.comment}'
