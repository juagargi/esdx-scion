from unittest import TestCase
from util import crypto
from util.test import test_data


class TestSignatures(TestCase):
    def test_create_signature(self):
        # load private key
        with open(test_data("broker.key"), "r") as f:
            key = crypto.load_key(f.read())
        # load certificate
        with open(test_data("broker.crt"), "r") as f:
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
