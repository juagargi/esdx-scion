from django.db import models
from cryptography import x509

from util.conversion import ia_validator
from util import crypto


class ASManager(models.Manager):
    def create(self, iaid: str, cert: x509.Certificate, name: str=None):
        if name is None:
            name = iaid
        # check that the common name in the subject of the certificate is exactly equal to the iaid
        cn = crypto.get_common_name(cert)
        if cn != iaid:
            raise ValueError(f"common name doesn't match iaid ({cn} != {iaid})")
        certbytes = crypto.certificate_to_pem(cert)
        return super().create(iaid=iaid, certificate_pem=certbytes, name=name)


class AS(models.Model):
    class Meta:
        verbose_name = "AS in the IXP"

    objects = ASManager()

    iaid = models.CharField(primary_key=True,
                            blank=False,
                            max_length=255,
                            verbose_name="The IA id like 1-ff00:1:1",
                            validators=[ia_validator()])
    certificate_pem = models.TextField() # the certificate, in PEM format
    name = models.CharField(max_length=255)
