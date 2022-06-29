from pathlib import Path
from reloader.topology import Topology
from unittest import TestCase


DATADIR = Path(__file__).parent.joinpath("data")


class TestTopology(TestCase):
    def test_init(self):
        r = Topology(Path(DATADIR, "topo.json"))

    def test_activate(self):
        r = Topology(Path(DATADIR, "topo.json"))
        r.activate(None)