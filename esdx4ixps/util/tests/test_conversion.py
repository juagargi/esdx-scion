from ipaddress import ip_address
from unittest import TestCase
from util import conversion

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
