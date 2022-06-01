from django.db import models


class BrokerManager(models.Manager):
    def create(self, *args, **kwargs):
        if super().all().count() > 0:
            raise RuntimeError("only one broker allowed (creating one but one already exists)")
        return super().create(*args, **kwargs)

    def get(self, **kwargs):
        if super().all().count() > 0:
            raise RuntimeError("only one broker allowed (creating one but one already exists)")
        return super().get(**kwargs)


class Broker(models.Model):
    class Meta:
        verbose_name = "Broker is the IXP"

    certificate_pem = models.TextField()  # the IXP's certificate, in PEM format
    key_pem = models.TextField()  # the IXP's key in PEM format
