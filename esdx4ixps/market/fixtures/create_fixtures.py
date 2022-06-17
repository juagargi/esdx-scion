from market.models.ases import AS
from market.models.broker import Broker
from util import crypto
from pathlib import Path


def _ases():
    ases = ["1-ff00:0:110", "1-ff00:0:111", "1-ff00:0:112"]
    for iaid in ases:
        # load certificate
        cert = iaid.replace(":", "_") + ".crt"
        p = Path(__file__).parent.parent.joinpath("tests", "data", cert)
        with open(p, "r") as f:
            cert = crypto.load_certificate(f.read())
        # create AS
        AS.objects.create(
            iaid=iaid,
            cert=cert,
        )


def _broker():
    # load key
    with open(Path(__file__).parent.parent.joinpath("tests", "data", "broker.key"), "r") as f:
        key = crypto.load_key(f.read())
    # load certificate
    with open(Path(__file__).parent.parent.joinpath("tests", "data", "broker.crt"), "r") as f:
        cert = crypto.load_certificate(f.read())
    # create broker
    Broker.objects.create(
        certificate_pem=crypto.certificate_to_pem(cert),
        key_pem=crypto.key_to_pem(key)
    )


def create_fixtures():
    _ases()
    _broker()
    pass
