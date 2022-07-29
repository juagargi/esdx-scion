from datetime import datetime
from django.core.exceptions import ValidationError
from ipaddress import ip_address
from unittest import TestCase
from util import conversion


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
                self.assertRaises(ValueError, conversion.ia_str_to_int, s)
            else:
                self.assertEqual(conversion.ia_str_to_int(s), val)


class TestIPConversion(TestCase):
    cases = [ # tuples of (string, raises?, ip, port)
        (
            "1.1.1.1:42",
            False,
            ip_address("1.1.1.1"),
            42,
        ),
        (
            "1.1.1.1:0",
            False,
            ip_address("1.1.1.1"),
            0,
        ),
        (
            "[fd00:f00d:cafe::7f00:9]:42",
            False,
            ip_address("fd00:f00d:cafe::7f00:9"),
            42,
        ),
        (
            "1.1.1:42",
            True,
            None,
            None,
        ),
        (
            "1.1.1.1",
            True,
            None,
            None,
        ),
        (
            "1.1.1.1:65535", # port too big
            True,
            None,
            None,
        ),
        (
            "1.1.1.1:-1", # port negative
            True,
            None,
            None,
        ),
        (
            "1.1.1.1:1 1",
            True,
            None,
            None,
        ),
        (
            "fd00:f00d:cafe::7f00:9:42",
            True,
            None,
            None,
        ),
    ]
    def test_ip_port_from_str(self):
        for c in self.cases:
            with self.subTest():
                if c[1]:
                    self.assertRaises(
                        ValueError,
                        conversion.ip_port_from_str,
                        c[0]
                    )
                else:
                    ip, port = conversion.ip_port_from_str(c[0])
                    self.assertEqual(ip, c[2])
                    self.assertEqual(port, c[3])

    def test_ip_port_to_str(self):
        for c in self.cases:
            with self.subTest():
                if c[1]:
                    continue
                got = conversion.ip_port_to_str(c[2], c[3])
                self.assertEqual(got, c[0])

    def test_ip_port_range_from_str(self):
        cases = [ # tuples of (string, raises?, ip, min_port, max_port)
            (
                "1.1.1.1:42-44",
                False,
                ip_address("1.1.1.1"),
                42, 44,
            ),
            (
                "1.1.1.1:42-42",
                False,
                ip_address("1.1.1.1"),
                42, 44,
            ),
            (
                "[fd00:f00d:cafe::7f00:9]:50-42",
                False,
                ip_address("fd00:f00d:cafe::7f00:9"),
                42, 50,
            ),
            (
                "1.1.1.1:42",
                True,
                None,
                None, None,
            ),
            (
                "1.1.1.1:42-",
                True,
                None,
                None, None,
            ),
            (
                "1.1.1.1:1-65535", # port too big
                True,
                None,
                None, None,
            ),
            (
                "1.1.1.1:1 1",
                True,
                None,
                None, None,
            ),
            (
                "fd00:f00d:cafe::7f00:9:42-44",
                True,
                None,
                None, None,
            ),
        ]
        for c in cases:
            with self.subTest():
                raises = c[1]
                s = c[0]
                ip = c[2]
                min_port = c[3]
                max_port = c[4]
                if raises:
                    print(s)
                    self.assertRaises(
                        ValueError,
                        conversion.ip_port_range_from_str,
                        s,
                    )
                else:
                    got_ip, got_min_port, got_max_port = conversion.ip_port_range_from_str(s)


class TestTimeConversion(TestCase):
    def test_pb_timestamp_from_seconds(self):
        t = conversion.pb_timestamp_from_seconds(0)
        self.assertEqual(t.seconds, 0)
        t = conversion.pb_timestamp_from_seconds(42)
        self.assertEqual(t.seconds, 42)

    def test_time_from_pb_timestamp(self):
        ts = conversion.pb_timestamp_from_seconds(123456789)
        t = conversion.time_from_pb_timestamp(ts)
        self.assertEqual(int(t.timestamp()), ts.seconds)


class TestValidators(TestCase):
    def test_ia_validator(self):
        v = conversion.ia_validator()
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
