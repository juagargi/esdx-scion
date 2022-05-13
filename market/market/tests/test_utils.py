from django.test import TestCase
from django.core.exceptions import ValidationError
from util.conversion import ia_validator, ia_str_to_int


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
