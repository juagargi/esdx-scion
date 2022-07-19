from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase
from django.utils import timezone as tz
from market.models.ases import AS
from market.models.broker import Broker
from market.models.contract import Contract
from market.models.offer import Offer, BW_PERIOD
from market.models.purchase_order import PurchaseOrder
from market.purchases import purchase_offer, find_available_br_address
from pathlib import Path
from util import crypto
from util import serialize
from util.test import test_data

import datetime


class TestOffer(TestCase):
    @staticmethod
    def _create_offer(periods: float):
        notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        profile = ",".join(["2" for i in range(int(periods))])
        notafter = notbefore + tz.timedelta(seconds=periods*BW_PERIOD)
        return Offer.objects.create(iaid="1-ff00:0:110",
                                    signature=b"",
                                    reachable_paths="",
                                    notbefore=notbefore,
                                    notafter=notafter,
                                    qos_class=1,
                                    price_per_unit=0.000001,
                                    bw_profile=profile,
                                    br_address_template="10.1.1.1:50000-50010",
                                    br_mtu=1500,
                                    br_link_to="PARENT")

    def test_pre_save(self):
        """ test that the pre save hook works """
        # bad interval
        o = self._create_offer(3)
        o.notafter = datetime.datetime.now()
        self.assertRaises(
            ValueError,
            o.save
        )
        # bad interval
        o = self._create_offer(3)
        o.notbefore = o.notafter + tz.timedelta(seconds=1)
        self.assertRaises(
            ValueError,
            o.save
        )
        # bad profile or bad interval
        o = self._create_offer(3)
        o.bw_profile = "2"
        self.assertRaises(
            ValueError,
            o.save
        )
        # bad br_address_template
        o = self._create_offer(3)
        o.br_address_template = "1.1.1.1:12"
        self.assertRaises(
            ValueError,
            o.save
        )
        # okay IPv6 br_address_template
        o = self._create_offer(3)
        o.br_address_template = "[fd00:f00d:cafe::7f00:9]:31018-31020"
        o.save()
        # bad br_mtu
        o = self._create_offer(3)
        o.br_mtu = 0
        self.assertRaises(
            ValueError,
            o.save
        )
        # bad br_mtu
        o = self._create_offer(3)
        o.br_mtu = 65535
        self.assertRaises(
            ValueError,
            o.save
        )
        # bad link_to
        o = self._create_offer(3)
        o.br_link_to = "P"
        self.assertRaises(
            ValueError,
            o.save
        )

    def test_multiple_of_bw_period(self):
        o = self._create_offer(1)
        o.save()
        # period of 1.33 seconds (should fail)
        o.notafter = o.notbefore + tz.timedelta(seconds=1.33)
        self.assertRaises(ValueError, o.save)

    def test_bw_profile_length(self):
        o = self._create_offer(3)
        o.bw_profile = "2,3,4"
        o.save()
        # 2 periods now
        o.bw_profile = "2,2"
        self.assertRaises(ValueError, o.save)

    def test_contains(self):
        o = self._create_offer(4)
        o.bw_profile="2, 2, 2, 2"
        starting_at = o.notbefore - tz.timedelta(seconds=2*BW_PERIOD)
        # negative starting point
        self.assertFalse(o.contains_profile("1", starting_at))
        starting_at = o.notbefore + tz.timedelta(seconds=2*BW_PERIOD)
        # too long regardless of starting point
        self.assertFalse(o.contains_profile("2,2,2,2,2", starting_at))
        # too long wrt starting point
        self.assertFalse(o.contains_profile("2,2,2", starting_at))
        # exact size wrt starting point
        self.assertTrue(o.contains_profile("2,2", starting_at))
        # too much BW
        self.assertFalse(o.contains_profile("3,2", starting_at))

    def test_purchase(self):
        o = self._create_offer(6)  # 2,2,2,2,2,2
        # buying -,-,1,2,2,1
        starting_at = o.notbefore + tz.timedelta(seconds=2*BW_PERIOD)
        new_profile = o.purchase("1,2,2,1", starting_at)
        self.assertEqual(new_profile, "2,2,1,0,0,1")
        # buying 2,1,2,0,0,0
        o = self._create_offer(6)  # 2,2,2,2,2,2
        starting_at = o.notbefore
        new_profile = o.purchase("2,1,2", starting_at)
        self.assertEqual(new_profile, "0,1,0,2,2,2")
        # buying 3,2
        o = self._create_offer(6)  # 2,2,2,2,2,2
        starting_at = o.notbefore
        new_profile = o.purchase("3,2", starting_at)
        self.assertEqual(new_profile, None)
        # buying 0,0,0
        o = self._create_offer(6)  # 2,2,2,2,2,2
        starting_at = o.notbefore
        new_profile = o.purchase("0,0,0", starting_at)
        self.assertEqual(new_profile, None)
        # buying 2,-1
        o = self._create_offer(6)  # 2,2,2,2,2,2
        starting_at = o.notbefore
        new_profile = o.purchase("2,-1", starting_at)
        self.assertEqual(new_profile, None)
        # we have now a shorter profile for sale 2,2,2
        # buying 0,0,0,1
        o = self._create_offer(3)  # 2,2,2
        starting_at = o.notbefore
        new_profile = o.purchase("0,0,0,1", starting_at)
        self.assertEqual(new_profile, None)
        # buying -,-,-,1
        o = self._create_offer(3)  # 2,2,2
        starting_at = o.notbefore + tz.timedelta(seconds=3*BW_PERIOD)
        new_profile = o.purchase("1", starting_at)
        self.assertEqual(new_profile, None)
        # buying -,-,1,1
        o = self._create_offer(3)  # 2,2,2
        starting_at = o.notbefore + tz.timedelta(seconds=2*BW_PERIOD)
        new_profile = o.purchase("1,1", starting_at)
        self.assertEqual(new_profile, None)

    def test_fields_serialize_to_bytes(self):
        t0 = datetime.datetime.utcfromtimestamp(11)
        t1 = datetime.datetime.utcfromtimestamp(12)
        b = serialize.offer_fields_serialize_to_bytes(
            "1-ff00:0:111",
            int(t0.timestamp()),
            int(t1.timestamp()),
            "path1,path2",
            1,
            100,
            "2,2,2,2",
            "1.1.1.1:42-45",
            1500,
            "PARENT",
            b"",
        )
        self.assertEqual(("ia:1-ff00:0:1111112reachable:path1,path211.000000e+02profile:2,2,2,2"+\
            "br_address_template:1.1.1.1:42-45br_mtu:1500br_link_to:PARENTsignature:").encode("ascii"), b)


class TestAS(TestCase):
    def test_as_creation(self):
        # create a key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        # create a self-signed cert
        issuer = subject = crypto.create_x509_name("CH", "Netsec", "ETH", "1-ff00:0:111")
        cert = crypto.create_certificate(
            issuer,
            subject,
            key,
            datetime.datetime.utcnow(),
            datetime.datetime.utcnow() + datetime.timedelta(days=1),
        )
        thisas = AS.objects.create(
            iaid="1-ff00:0:111",
            cert=cert,
        )
        self.assertEqual(
            crypto.certificate_to_pem(cert),
            thisas.certificate_pem,
        )
        self.assertRaises(
            ValueError,
            AS.objects.create,
            iaid="1-ff00:0:112", # the IA is different
            cert=cert,
        )


class TestBroker(TestCase):
    fixtures = ["testdata"]
    def assertEqualKeys(self, k1, k2):
        self.assertEqual(k1.private_numbers(), k2.private_numbers())

    def assertNotEqualKeys(self, k1, k2):
        self.assertNotEqual(k1.private_numbers(), k2.private_numbers())

    def test_internal_equal_keys(self):
        k1 = crypto.create_key()
        k2 = crypto.create_key()
        self.assertNotEqualKeys(k1, k2)
        k2 = crypto.load_key(crypto.key_to_pem(k1))
        self.assertEqualKeys(k1, k2)


    def test_get_broker_key(self):
        # manually load the key and compare
        expected = crypto.load_key(Broker.objects.get().key_pem)
        got = Broker.objects.get_broker_key()
        self.assertEqualKeys(expected, got)
        # modify broker
        expected = crypto.create_key()
        broker = Broker.objects.get()
        broker.key_pem = crypto.key_to_pem(expected)
        broker.save()
        got = Broker.objects.get_broker_key()
        self.assertEqualKeys(expected, got)
        # remove broker
        Broker.objects.all().delete()
        self.assertRaises(
            Broker.DoesNotExist,
            Broker.objects.get_broker_key,
        )
        # create new broker
        Broker.objects.create(
            key_pem=broker.key_pem,
            certificate_pem=broker.certificate_pem,
        )
        expected = crypto.load_key(Broker.objects.get().key_pem)
        got = Broker.objects.get_broker_key()
        self.assertEqualKeys(expected, got)

    def test_get_broker_certificate(self):
        # compare the cached cert with the manually loaded one
        expected = crypto.load_certificate(Broker.objects.get().certificate_pem)
        got = Broker.objects.get_broker_certificate()
        self.assertEqual(expected, got)
        # modify broker
        key = crypto.create_key()
        subj = issuer = crypto.create_x509_name("CH", "Netsec", "ETH", "broker")
        cert = crypto.create_certificate(
            issuer,
            subj,
            key,
            datetime.datetime.utcnow(),
            datetime.datetime.utcnow() + datetime.timedelta(days=365))
        broker = Broker.objects.get()
        broker.key_pem=crypto.key_to_pem(key)
        broker.certificate_pem=crypto.certificate_to_pem(cert)
        broker.save()
        expected = crypto.load_certificate(Broker.objects.get().certificate_pem)
        got = Broker.objects.get_broker_certificate()
        self.assertEqual(expected, got)
        # remove broker
        Broker.objects.all().delete()
        self.assertRaises(
            Broker.DoesNotExist,
            Broker.objects.get_broker_certificate,
        )
        # create new broker
        Broker.objects.create(
            key_pem=broker.key_pem,
            certificate_pem=broker.certificate_pem,
        )
        expected = crypto.load_certificate(Broker.objects.get().certificate_pem)
        got = Broker.objects.get_broker_certificate()
        self.assertEqual(expected, got)


class TestFindFreeBRAddress(TestCase):
    fixtures = ["testdata"]
    def setUp(self):
        # load private key for 111
        with open(test_data("1-ff00_0_111.key"), "r") as f:
            self.key = crypto.load_key(f.read())
        self.br_template = "1.1.1.1:10-12"

    def _buy_offer(self, offer: Offer):
        bw_profile = "1"
        starting_on = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        offer_bytes = offer.serialize_to_bytes(True)
        data = serialize.purchase_order_fields_serialize_to_bytes(
            offer_bytes,
            "1-ff00:0:111",
            bw_profile,
            int(starting_on.timestamp()),
        )
        return purchase_offer(
            offer,
            "1-ff00:0:111",
            starting_on,
            bw_profile,
            crypto.signature_create(self.key, data),
        )

    def test_find_available_br_address(self):
        """ checks the correct behavior of purchases.find_available_br_address """
        # original offer
        original_offer = TestOffer._create_offer(1)
        original_offer.bw_profile = "10"
        original_offer.br_address_template = self.br_template
        original_offer.save()
        # first offer signed by the broker
        o1 = TestOffer._create_offer(1)
        o1.bw_profile = "10"
        o1.br_address_template = self.br_template
        o1.deprecates = original_offer
        o1.save()

        self.assertEqual(find_available_br_address(o1), "1.1.1.1:10")
        c1,o2 = self._buy_offer(o1)
        self.assertEqual(c1.br_address, "1.1.1.1:10")

        self.assertEqual(find_available_br_address(o2), "1.1.1.1:11")
        c2,o3 = self._buy_offer(o2)
        self.assertEqual(c2.br_address, "1.1.1.1:11")

        self.assertEqual(find_available_br_address(o3), "1.1.1.1:12")
        c3,o4 = self._buy_offer(o3)
        self.assertEqual(c3.br_address, "1.1.1.1:12")

        self.assertRaises(
            RuntimeError,
            find_available_br_address,
            o4,  # port 13
        )
