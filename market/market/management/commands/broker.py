from django.core.management.base import BaseCommand
from django.db import transaction
from market.models.broker import Broker
from util import crypto

import datetime
import sys


class Command(BaseCommand):
    help = "Creates or replaces a client/provider in this IXP"

    def add_arguments(self, parser):
        parser.add_argument("--remove", required=False, action="store_true",
                            help="Remove the broker if there is one")
        parser.add_argument("--create", required=False, action="store_true",
                            help="Create a certificate and a key and add them as a broker")
        parser.add_argument("--export", required=False, action="store_true",
                            help="export the broker's certificate and key as broker.{crt|key}")

    def handle(self, *args, **options):
        with transaction.atomic():
            if options["remove"]:
                print("removing ...")
                Broker.objects.all().delete()
            if options["create"]:
                print("creating ...")
                key = crypto.create_key()
                subj = issuer = crypto.create_x509_name("CH", "Netsec", "ETH", "broker")
                cert = crypto.create_certificate(
                    issuer,
                    subj,
                    key,
                    datetime.datetime.utcnow(),
                    datetime.datetime.utcnow() + datetime.timedelta(days=365))
                keybytes = crypto.key_to_pem(key)
                certbytes = crypto.certificate_to_pem(cert)
                Broker.objects.create(key_pem=keybytes, certificate_pem=certbytes)
            if options["export"]:
                print("exporting ...")
                b = Broker.objects.all()
                if b.count() != 1:
                    print(f"One broker needed, found {b.count()}")
                    sys.exit(1)
                b = b.first()
                with open("broker.crt", "w") as f:
                    f.write(b.certificate_pem)
                with open("broker.key", "w") as f:
                    f.write(b.key_pem)

        print("done")
