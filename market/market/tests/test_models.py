from django.test import TestCase
from cryptography.hazmat.primitives.asymmetric import rsa
from market.models.offer import Offer, BW_PERIOD
from market.models.ases import AS
from django.utils import timezone as tz
from util import crypto
from util import serialize

import datetime


class TestOffer(TestCase):
    def _create_offer(self, periods: float):
        notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        profile = ",".join(["2" for i in range(int(periods))])
        notafter = notbefore + tz.timedelta(seconds=periods*BW_PERIOD)
        return Offer.objects.create(iaid="1-ff00:0:111", is_core=True, signature=b"",
                                    reachable_paths="",
                                    notbefore=notbefore,
                                    notafter=notafter,
                                    qos_class=1,
                                    price_per_picounit=10,
                                    bw_profile=profile)

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
            True,
            int(t0.timestamp()),
            int(t1.timestamp()),
            "path1,path2",
            1,
            100,
            "2,2,2,2")
        self.assertEqual("ia:1-ff00:0:11111112reachable:path1,path21100profile:2,2,2,2".encode("ascii"), b)


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
