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
