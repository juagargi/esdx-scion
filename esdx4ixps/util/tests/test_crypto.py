from unittest import TestCase
from util import crypto
from util.test import test_data

import time


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

        # test to verify a signature created from the go client.
        data = b'hello'
        with open(test_data("broker.crt"), "r") as f:
            cert = crypto.load_certificate(f.read())
        signature = bytes.fromhex(
            "3a8e26762dac7bb2cc56b977d5af2153514df660589dfac37670e2e69a0b1c327cd8efa246bb5923e5" + \
            "bb97904806dd993d69a8d06e91da121ff7401d637b39400e368b8d5e30e442031541a1f2aef0b3c39f" + \
            "54664dbd5038ce7bd7a79c1e7e505d47a45af6adb61478fa5b0fcb74de005a9e88c7065e15d1b45d86" + \
            "2a5838cff7dda9109aabf5e04be692d8dd1f0538298d9cbe220e4ddc1b570fb83d338939419c51f90b" + \
            "e47358707d13d01ce5051c7b4714f10c9e2218868bcaee9f8d341a6fa3c0ff196d9ee697a9dc123c6f" + \
            "aba9fb739ebbe9555687f13d042a2cdc7e17ce3a3bb992230d26adb30bbc191e0e622a02a5006e6f1c" + \
            "3704d35510d7a828397ef10ed8981dcdfa0c8858e79a3f9e36a828e99ba88a53ee602e3e57af27aa0e" + \
            "b8c275cdb2e1d29763a1d15db73ffaa63063fffbb2c2edb5ccdf6ebcd6d4069e0a4face62e9836632e" + \
            "6a9e7bd81e4aff895edd0497d3342fb93a4c3ecc62a1e169ff4852aa2e8042b83b9478f6098c2cee2f" + \
            "cf4756f1d96bd58e17d62ceac37508c0f1e32caa2dd14ec823ea220e28ff7b265170584d2595830fe2" + \
            "6644c902b4c5b48d1fc0c73ed4d57e8787eab4161094b00ece2d1687c039697105b3bb87a4991bdd07" + \
            "4dbcdd103c44533f89cd2bd2f578744073c3c08614eeb03701ccfbbfb8441fb628131e94633f087d10" + \
            "d783143667df17ecf1cc57e26fbbd56a0c1ac580"
        )
        crypto.signature_validate(cert, signature, data)


class BenchmarkSignatures(TestCase):
    def test_signature_create(self):
        with open(test_data("broker.key")) as f:
            key = crypto.load_key(f.read())
        data = b"a" * 200
        t0 = time.time()
        crypto.signature_create(key, data)
        t1 = time.time()
        print(f"time to sign {len(data)} bytes: {t1-t0}")

    def test_load_key(self):
        # load PEM bytes
        with open(test_data("broker.key")) as f:
            data = f.read()
        data = data.encode("ascii")
        # load key
        t0 = time.time()
        key = crypto.load_key(data)
        t1 = time.time()
        print(f"time to load key: {t1-t0}")
