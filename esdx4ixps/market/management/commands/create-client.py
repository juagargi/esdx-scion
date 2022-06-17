from django.core.management.base import BaseCommand
from django.db import transaction
from market.models.ases import AS
from util.conversion import ia_validator
from util.crypto import load_certificate

import argparse
import sys


class Command(BaseCommand):
    help = "Creates or replaces a client/provider in this IXP"

    def add_arguments(self, parser):
        parser.add_argument("-c", "--cert", type=argparse.FileType("rb"), required=True,
                            help="The certificate for this client")
        parser.add_argument("--ia", type=str, required=True,
                            help="The IA of the client")
        parser.add_argument("--name", type=str, required=False,
                            help="A common name for this client")
        parser.add_argument("--force", required=False, action="store_true",
                            help="If the IA exists, remove the previous one")

    def handle(self, *args, **options):
        ia = options["ia"].strip()
        ia_validator()(ia)
        if "name" not in options:
            options["name"] = options["ia"]
        with transaction.atomic():
            # find an existing client, and remove
            if AS.objects.filter(iaid=ia).count() > 0:
                if options["force"]:
                    AS.objects.filter(iaid=ia).delete()
                else:
                    print("IA exists already. Use --force")
                    sys.exit(1)
            # load cert
            cert = load_certificate(options["cert"].read())
            # create new AS
            AS.objects.create(iaid=ia, cert=cert, name=options["name"])
        print("done")
