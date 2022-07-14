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

        # test to verify a signature created from the go client.
        with open(test_data("1-ff00_0_111.key"), "r") as f:
            key = crypto.load_key(f.read())
        data = b'hello'

        with open(test_data("1-ff00_0_111.crt"), "r") as f:
            cert = crypto.load_certificate(f.read())
        signature = bytes.fromhex("aba66b3ac5d40790dc82c53846e0dd6012cc489cc039f3c72567cb81888f20cccc13e82eb477e0f4180bcaf8dfa1edb9e8a2cee3a2c63b8fbf39e568ee35f251c4dbb24ccb0214b1aab8123d75db3b2fb9b2f8bd8173da0e1351a8f4b442194a9a637158cfb563d3dccdb430eca102586463cdc5265f58a62c560976325e4be80ba8f92d004a2cb10ae89b52ba0071a3eb40e80ff34b376bf9be2dd02e917b9bb3d7fcc21e8064b649ca823b522d18b51c2f7c3c2603cacc1f3ed0307ef2e17a6b7cee7f2c61b2573affb6a7ac92db2f852d4b191345751a294413a9e06dcda47cb99747e5079177dd7afa56db502e53c6028bd5fe13f2abfc0504074c4fe5917027f4235e81e5f85285cc4bba2d8310402209bd9592f61ba45d794e973e0f073e4d334dedaf8f6616ec4e2ac438f4b4515eb8b5c59926a7f6d123b8d8c640b2918632c3c83987c3937faa92bce8b13fa014374dea53efcca046126bc1d8fa49d54f5706efe9d5b99acec36cf8d4f9983affd85c97aaac2e659970b160253f91a8d675a82fa6e278357e9df5d29794a019d983ccde70263658a89ba913c81a29852b00b08a012d5629d02c749f1bcaa3ed8342aa4100ee3bb5e5934aa8706818984f14778751a794a84d940e68c0249ea74d30acab1e44a031c79227181b1bd5937d4dc9660642476cc60fadd8f20557f55c176c096f11efbd924c25b4152001")
        crypto.signature_validate(cert, signature, data)
