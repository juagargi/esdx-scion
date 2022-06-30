from market_pb2 import Contract, OfferSpecification
from pathlib import Path
from reloader.topology import Topology
from tempfile import TemporaryDirectory
from unittest import TestCase
from util import conversion


DATADIR = Path(__file__).parent.joinpath("data")


class TestTopology(TestCase):
    @staticmethod
    def _mock_contract() -> Contract:
        return Contract(
            offer=OfferSpecification(
                iaid="1-ff00:0:110",
                is_core=False,
                notbefore=conversion.pb_timestamp_from_seconds(1),
                notafter=conversion.pb_timestamp_from_seconds(3),
                reachable_paths="*",
                qos_class=1,
                price_per_unit=0.001,
                bw_profile="3,3",
                br_address="1.1.1.1:50000",
                br_mtu=1500,
                br_link_to="PARENT",
            ),
            contract_timestamp=conversion.pb_timestamp_from_seconds(0),
            buyer_iaid="1-ff00:0:111",
            buyer_starting_on=conversion.pb_timestamp_from_seconds(1),
            buyer_bw_profile="3,3",
        )

    def test_init(self):
        Topology(Path(DATADIR, "topo.json"))

    def test_lock(self):
        with TemporaryDirectory() as temp:
            r1 = Topology(Path(temp, "topo.json"))
            r2 = Topology(Path(temp, "topo.json"))
            r1._lock()
            self.assertRaises(
                RuntimeError,
                r2._lock,
            )
            r1._unlock()
            r2._lock()
            r2._unlock()

    def test_unlock(self):
        with TemporaryDirectory() as temp:
            r1 = Topology(Path(temp, "topo.json"))
            self.assertRaises(
                RuntimeError,
                r1._unlock,
            )

    def test_contract_as_seller(self):
        c = self._mock_contract()
        info = Topology(Path())._contract_as_seller(c)
        self.assertEqual(info.remote_ia, c.buyer_iaid)
        self.assertEqual(info.remote_underlay, c.offer.br_address)
        self.assertEqual(info.mtu, c.offer.br_mtu)
        self.assertEqual(info.link_to, c.offer.br_link_to)

    def test_contract_as_buyer(self):
        c = self._mock_contract()
        info = Topology(Path())._contract_as_buyer(c)
        self.assertEqual(info.remote_ia, c.offer.iaid)
        self.assertEqual(info.remote_underlay, c.offer.br_address)
        self.assertEqual(info.mtu, c.offer.br_mtu)
        self.assertEqual(info.link_to, c.offer.br_link_to)

    def test_activate(self):
        r = Topology(Path(DATADIR, "topo.json"))
        r.activate(None)