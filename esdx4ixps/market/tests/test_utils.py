from django.test import TestCase
from django.core.exceptions import ValidationError
from util.conversion import ia_validator, ia_str_to_int
from pathlib import Path
from market.models.ases import AS
from util import crypto


class TestConversions(TestCase):
    def test_ia_str_to_int(self):
        def _build_from_ia(i, a):
            return (i << 48) | a

        cases = (
            ("", None),
            ("a", None),
            ("1a-2b", None),
            ("-", None),
            ("1-", None),
            ("-1", None),
            ("-1-", None),
            ("1--1", None),
            ("0-0", _build_from_ia(0, 0)),
            ("1-1", _build_from_ia(1, 1)),
            ("65535-1", _build_from_ia(65535, 1)),
            ("65536-1", None),
            ("1-4294967295", _build_from_ia(1, (1<<32) - 1)),
            ("1-4294967296", None),
            ("1-1:0:0", _build_from_ia(1, 0x000100000000)),
            ("1-1:fcd1:1", _build_from_ia(1, 0x0001fcd10001)),
            ("1-ffff:ffff:10000", None),
            ("65535-ffff:ffff:ffff", _build_from_ia(65535, (1<<48) - 1)),
        )
        for s, val in cases:
            if val is None:
                self.assertRaises(ValueError, ia_str_to_int, s)
            else:
                self.assertEqual(ia_str_to_int(s), val)


class TestValidators(TestCase):
    def test_ia_validator(self):
        v = ia_validator()
        self.assertRaises(ValidationError, v, "")
        self.assertRaises(ValidationError, v, "1-1-1")
        self.assertRaises(ValidationError, v, "1")
        self.assertRaises(ValidationError, v, "f-1")
        self.assertRaises(ValidationError, v, " 1 - 1 ")
        self.assertRaises(ValidationError, v, " 1 - ff : 0 : 1 ")
        self.assertRaises(ValidationError, v, "1 -1 1")
        self.assertRaises(ValidationError, v, "1-ff : 0:1")
        # the following cases should not throw anything:
        v("1-1")
        v("1-ff:0:1")


class TestSignatures(TestCase):
    fixtures = ["testdata"]
    def test_create_signature(self):
        # load private key
        with open(Path(__file__).parent.joinpath("data", "broker.key"), "r") as f:
            key = crypto.load_key(f.read())
        # load certificate
        with open(Path(__file__).parent.joinpath("data", "broker.crt"), "r") as f:
            cert = crypto.load_certificate(f.read())
        # sign something
        data = "hello world".encode("ascii")
        signature = crypto.signature_create(key, data)
        # validate signature
        crypto.signature_validate(cert, signature, data)
        # modify contents and validate signature
        bad_data = b'1' + data[1:]
        self.assertRaises(
            ValueError,
            crypto.signature_validate,
            cert, signature, bad_data
        )
        # revert and validate signature
        crypto.signature_validate(cert, signature, data)
        # modify signature and validate signature
        self.assertNotEqual(signature[0], b'1') # if equal, change the b'1' to something else below
        bad_signature = b'1' + signature[1:]
        self.assertRaises(
            ValueError,
            crypto.signature_validate,
            cert, bad_signature, data
        )

    def test_validate_with_as(self):
        # load private key
        with open(Path(__file__).parent.joinpath("data", "1-ff00_0_111.key"), "r") as f:
            key = crypto.load_key(f.read())
        # get certificate from AS
        cert = crypto.load_certificate(AS.objects.get(iaid="1-ff00:0:111").certificate_pem)
        # sign
        data = "hello world".encode("ascii")
        signature = crypto.signature_create(key, data)
        # validate
        crypto.signature_validate(cert, signature, data)
