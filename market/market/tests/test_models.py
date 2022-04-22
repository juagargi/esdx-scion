from django.test import TestCase
from market.models import Offer, BW_PERIOD
from django.utils import timezone as tz


class TestOffer(TestCase):
    def _create_offer(self, periods: float):
        notbefore = tz.datetime.fromisoformat("2022-04-01T20:00:00.000000+00:00")
        profile = ",".join(["2" for i in range(int(periods))])
        notafter = notbefore + tz.timedelta(seconds=periods*BW_PERIOD)
        return Offer.objects.create(iaid=1, iscore=True, signature=b"",
                                    reachable_paths="",
                                    notbefore=notbefore,
                                    notafter=notafter,
                                    qos_class=1,
                                    price_per_nanounit=10,
                                    bw_profile=profile)

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
