from ipaddress import ip_address
from market_pb2 import Contract, OfferSpecification
from pathlib import Path
from reloader.topology import Topology
from tempfile import TemporaryDirectory
from unittest import TestCase
from util import conversion
import copy
import json
import shutil


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
                br_address_template="1.1.1.1:50000-50100",
                br_mtu=1500,
                br_link_to="PARENT",
            ),
            contract_timestamp=conversion.pb_timestamp_from_seconds(0),
            buyer_iaid="1-ff00:0:111",
            buyer_starting_on=conversion.pb_timestamp_from_seconds(1),
            buyer_bw_profile="3,3",
            br_address="1.1.1.1:50000"
        )

    def test_init(self):
        Topology(Path(DATADIR, "topo.json"))

    def test_lock(self):
        with TemporaryDirectory() as temp:
            r = Topology(Path(temp, "topo.json"), attempts=2)
            r2 = Topology(Path(temp, "topo2.json"), attempts=2)
            filename = r.lockfile
            # check that lock file exists only during context
            with r._lock():
                f = open(filename)
                f.close()
            self.assertRaises(
                FileNotFoundError,
                open,
                filename
            )
            # check two lock files can be opened if not the same
            with r._lock():
                f = open(filename)
                f.close()
                with r2._lock():
                    f = open(r2.lockfile)
                    f.close()
            # check that the same lock file cannot be opened twice
            with r._lock():
                r2 = Topology(Path(temp, "topo.json"), attempts=2)  # same as r1
                self.assertEqual(r2.lockfile, filename)
                with self.assertRaises(RuntimeError) as raised:
                    with r2._lock():  # we need to call it as a context manager
                        pass
        # check that throwing an exception in the body of the handled context is no problem
        with TemporaryDirectory() as temp:
            r = Topology(Path(temp, "topo.json"))
            filename = r.lockfile
            class myException(Exception):
                pass
            try:
                with r._lock():
                    f = open(filename)
                    f.close()
                    raise myException()
            except myException:
                pass
            self.assertRaises(  # the lock file should have been removed
                FileNotFoundError,
                open,
                filename
            )

    def test_contract_as_seller(self):
        c = self._mock_contract()
        info = Topology(Path())._contract_as_seller(c)
        self.assertEqual(info.remote_ia, c.buyer_iaid)
        self.assertEqual(info.remote_underlay, c.br_address)
        self.assertEqual(info.mtu, c.offer.br_mtu)
        self.assertEqual(info.link_to, c.offer.br_link_to)

    def test_contract_as_buyer(self):
        c = self._mock_contract()
        info = Topology(Path())._contract_as_buyer(c)
        self.assertEqual(info.remote_ia, c.offer.iaid)
        self.assertEqual(info.remote_underlay, c.br_address)
        self.assertEqual(info.mtu, c.offer.br_mtu)
        self.assertEqual(info.link_to, c.offer.br_link_to)

    def test_find_lowest_free_id(self):
        cases = [ # tuples of ( [elements], expected_next )
            (
                [1,2,3],
                4,
            ),
            (
                [],
                1,
            ),
            (
                [2,3,4],
                1,
            ),
            (
                [1,2,4,5],
                3,
            ),
            (
                [41,1],
                2,
            ),
        ]
        r = Topology(Path())
        for c in cases:
            with self.subTest():
                got = r._find_lowest_free_id(c[0])
                self.assertEqual(got, c[1])

    def test_generate_esdx_br_name(self):
        cases = [ # tuples of ( dict, expected_str )
            (
                {"isd_as": "1-ff00:0:111"},
                "br1-ff00_0_111-1111",
            ),
            (
                {"isd_as": "1-442"},
                "br1-442-1111",
            ),
        ]
        r = Topology(Path())
        for c in cases:
            with self.subTest():
                got = r._generate_esdx_br_name(c[0])
                self.assertEqual(got, c[1])

    def test_find_avail_public_addr(self):
        cases = [ # tuples of ( raises?, DICT[ip]:port_list, expected_str )
            (
                False,
                {ip_address("1.1.1.1"): [1,2,3]},
                "1.1.1.1:4",
            ),
            (
                False,
                {ip_address("1.1.1.1"): [50,51,55]},
                "1.1.1.1:52",
            ),
            (
                False,
                {ip_address("1.1.1.1"): []}, # this case should never happen anyways
                "1.1.1.1:1",
            ),
            (
                False,
                {ip_address("fd00:f00d:cafe::7f00:9"): [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,17,18]},
                "[fd00:f00d:cafe::7f00:9]:16",
            ),
            (
                True,
                {},
                "",
            ),
            (
                True,
                {
                    ip_address("1.1.1.1"): [1],
                    ip_address("1.1.1.2"): [1],
                },
                "",
            ),
        ]
        r = Topology(Path())
        for c in cases:
            with self.subTest():
                if c[0]:
                    self.assertRaises(
                        RuntimeError,
                        r._find_avail_public_addr,
                        c[1]
                    )
                else:
                    got = r._find_avail_public_addr(c[1])
                    self.assertEqual(got, c[2])

    def test_add_contract_to_topo(self):
        topo_111_stock = { # 1-ff00:0:111 stock (kind of)
            "isd_as": "1-ff00:0:111",
            "border_routers": {
                "br1-ff00_0_111-1": {
                    "internal_addr": "127.0.0.17:31012",
                    "interfaces": {
                        "41": {
                            "underlay": {
                                "public": "127.0.0.5:50000",
                                "remote": "127.0.0.4:50000"
                            },
                            "isd_as": "1-ff00:0:110",
                            "link_to": "PARENT",
                            "mtu": 1280,
                        },
                    },
                },
            },
            "foobar": [1,2,3,4],
        }
        topo_110_stock = { # 1-ff00:0:110 almost stock 
            "isd_as": "1-ff00:0:110",
            "border_routers": {
                "br1-ff00_0_110-1": {
                    "internal_addr": "127.0.0.9:31004",
                    "interfaces": {
                        "1": {
                            "underlay": {
                                "public": "127.0.0.4:50000",
                                "remote": "127.0.0.5:50000",
                            },
                            "isd_as": "1-ff00:0:111",
                            "link_to": "CHILD",
                            "mtu": 1280,
                        },
                    },
                },
                "br1-ff00_0_110-2": {
                    "internal_addr": "127.0.0.9:31006",
                    "interfaces": {
                        "2": {
                            "underlay": {
                                # TODO(juagargi) uncomment this once we have settings for public_addrs instead of guessing them
                                # "public": "[fd00:f00d:cafe::7f00:4]:50000",
                                # "remote": "[fd00:f00d:cafe::7f00:5]:50000",
                                "public": "127.0.0.4:50001",
                                "remote": "127.0.0.6:50000",
                            },
                            "isd_as": "1-ff00:0:112",
                            "link_to": "CHILD",
                            "mtu": 1472,
                        },
                    },
                },
            },
        }
        topo_111_with_esdx = {
            "isd_as": "1-ff00:0:111",
            "border_routers": {
                "br1-ff00_0_111-1": {
                    "internal_addr": "127.0.0.17:31012",
                    "interfaces": {
                        "41": {
                            "underlay": {
                                "public": "127.0.0.5:50000",
                                "remote": "127.0.0.4:50000"
                            },
                            "isd_as": "1-ff00:0:110",
                            "link_to": "PARENT",
                            "mtu": 1280,
                        },
                    },
                },
                "br1-ff00_0_111-1111": {
                    "internal_addr": "127.0.0.17:31013",
                    "interfaces": {
                        "1": {
                            "underlay": {
                                "public": "127.0.0.5:50001",
                                "remote": "127.0.0.4:55555"
                            },
                            "isd_as": "1-ff00:0:110",
                            "link_to": "PARENT",
                            "mtu": 1200,
                        },
                    },
                },
            },
            "foobar": [1,2,3,4],
        }
        info_111_buys = Topology.TopoInfoFromContract(
            remote_ia="1-ff00:0:110",
            remote_underlay="127.0.0.4:55555",
            mtu=1200,
            link_to="PARENT",
        )
        info_110_sells = Topology.TopoInfoFromContract(
            remote_ia="1-ff00:0:111",
            remote_underlay="127.0.0.5:55555",
            mtu=1200,
            link_to="PARENT",
        )
        info_111_buys_again = Topology.TopoInfoFromContract(
            remote_ia="1-ff00:0:110",
            remote_underlay="127.0.0.4:55556",
            mtu=1200,
            link_to="PARENT",
        )

        cases = [ # tuples of (raises? topo, info, exp_internal_addr, exp_iface, exp_public_addr)
            (
                False,
                topo_111_stock,
                info_111_buys,
                "127.0.0.17:31013",
                "1",
                "127.0.0.5:50001",
            ),
            (
                False,
                topo_110_stock,
                info_110_sells,
                "127.0.0.9:31007",
                "3",
                "127.0.0.4:50002",
            ),
            (
                False,
                topo_111_with_esdx,
                info_111_buys_again,
                "127.0.0.17:31013",
                "2",
                "127.0.0.5:50002",
            ),
        ]
        r = Topology(Path())
        for c in cases:
            with self.subTest():
                raises = c[0]
                topo = c[1]
                info_111_buys = c[2]
                interal_addr = c[3]
                ifid = c[4]
                public_addr = c[5]
                if raises:
                    self.assertRaises(
                        RuntimeError,
                        r._add_cotract_to_topo,
                        topo, info_111_buys
                    )
                else:
                    r._add_cotract_to_topo(topo, info_111_buys)
                    esdx_br = r._generate_esdx_br_name(topo)
                    br = topo["border_routers"][esdx_br]
                    self.assertIsNotNone(br)
                    self.assertEqual(br["internal_addr"], interal_addr)
                    self.assertIn(ifid, br["interfaces"])
                    iface = br["interfaces"][ifid]
                    self.assertEqual(iface["isd_as"], info_111_buys.remote_ia)
                    self.assertEqual(iface["mtu"], info_111_buys.mtu)
                    self.assertEqual(iface["link_to"], info_111_buys.link_to)
                    self.assertEqual(iface["underlay"]["public"], public_addr)
                    self.assertEqual(iface["underlay"]["remote"], info_111_buys.remote_underlay)

    def test_remove_interface(self):
        topo_base = { # 111 with one empty esdx br
            "isd_as": "1-ff00:0:111",
            "border_routers": {
                "br1-ff00_0_111-1": {
                    "internal_addr": "127.0.0.17:31012",
                    "interfaces": {
                        "41": {
                            "underlay": {
                                "public": "127.0.0.5:50000",
                                "remote": "127.0.0.4:50000"
                            },
                            "isd_as": "1-ff00:0:110",
                            "link_to": "PARENT",
                            "mtu": 1280,
                        },
                    },
                },
                "br1-ff00_0_111-1111": {
                    "internal_addr": "127.0.0.17:31013",
                    "interfaces": {},
                },
            },
            "foobar": [1,2,3,4],
        }
        topo1 = copy.deepcopy(topo_base)
        topo1["border_routers"]["br1-ff00_0_111-1111"]["interfaces"] = {
            "1": {
                "underlay": {
                    "public": "127.0.0.5:50001",
                    "remote": "127.0.0.4:55555"
                },
                "isd_as": "1-ff00:0:110",
                "link_to": "PARENT",
                "mtu": 1200,
            },
        }
        topo2 = copy.deepcopy(topo_base)
        topo2["border_routers"]["br1-ff00_0_111-1111"]["interfaces"] = {
            "1": {
                "underlay": {
                    "public": "127.0.0.5:50002",
                    "remote": "127.0.0.4:55556"
                },
                "isd_as": "1-ff00:0:110",
                "link_to": "PARENT",
                "mtu": 1200,
            },
            "2": {
                "underlay": {
                    "public": "127.0.0.5:50001",
                    "remote": "127.0.0.4:55555"
                },
                "isd_as": "1-ff00:0:110",
                "link_to": "PARENT",
                "mtu": 1200,
            },
        }
        topo3 = copy.deepcopy(topo_base)
        topo3["border_routers"]["br1-ff00_0_111-1111"]["interfaces"] = {
            "1": {
                "underlay": {
                    "public": "127.0.0.5:50001",
                    "remote": "127.0.0.4:55555"
                },
                "isd_as": "1-ff00:0:110",
                "link_to": "PARENT",
                "mtu": 1200,
            },
            "2": {
                "underlay": {
                    "public": "127.0.0.5:50002",
                    "remote": "127.0.0.4:55556"
                },
                "isd_as": "1-ff00:0:110",
                "link_to": "PARENT",
                "mtu": 1200,
            },
        }
        info = Topology.TopoInfoFromContract(
            remote_ia="1-ff00:0:110",
            remote_underlay="127.0.0.4:55555",
            mtu=1200,
            link_to="PARENT",
        )
        cases = [ # tuples of ( raises?, topo, info, exp_esdx_br?, exp_ifid_not_in )
            (
                False,
                topo1,
                info,
                False,
                "1",
            ),
            (
                False,
                topo2,
                info,
                True,
                "2",
            ),
            (
                False,
                topo3,
                info,
                True,
                "1",
            ),
        ]
        r = Topology(Path())
        for c in cases:
            with self.subTest():
                raises = c[0]
                topo = c[1]
                info = c[2]
                esdx_br_in = c[3]
                ifid = c[4]
                if raises:
                    self.assertRaises(
                        RuntimeError,
                        r._remove_interface,
                        topo, info
                    )
                else:
                    r._remove_interface(topo, info)
                    br_name = r._generate_esdx_br_name(topo)
                    brs = topo["border_routers"]
                    if esdx_br_in:
                        self.assertIn(br_name, brs)
                        self.assertNotIn(ifid, brs[br_name]["interfaces"])
                    else:
                        self.assertNotIn(br_name, brs)

    def test_activate(self):
        with TemporaryDirectory() as temp:
            shutil.copyfile(Path(DATADIR, "topo.json"), Path(temp, "topo.json"))
            c = self._mock_contract()
            # r = Topology(Path(DATADIR, "topo.json"))
            r = Topology(Path(temp, "topo.json"))
            r.activate(c)
            # load the json and check that our contract is inside
            with open(Path(temp, "topo.json")) as f:
                topo = json.load(f)
        self.assertIn("br1-ff00_0_111-1111", topo["border_routers"])
        br = topo["border_routers"]["br1-ff00_0_111-1111"]
        self.assertIn("1", br["interfaces"])
        iface = br["interfaces"]["1"]
        self.assertEqual(iface["isd_as"], c.offer.iaid)
        self.assertEqual(iface["underlay"]["remote"], c.br_address)

    def test_deactivate(self):
        with TemporaryDirectory() as temp:
            shutil.copyfile(Path(DATADIR, "topo.json"), Path(temp, "topo.json"))
            c1 = self._mock_contract()
            # r = Topology(Path(DATADIR, "topo.json"))
            r = Topology(Path(temp, "topo.json"))
            r.activate(c1)
            # activate another contract:
            c2 = self._mock_contract()
            c2.br_address = "1.1.1.1:50001"
            r.activate(c2)
            # load the json with the two esdx interfaces
            with open(Path(temp, "topo.json")) as f:
                topo = json.load(f)
            self.assertIn("br1-ff00_0_111-1111", topo["border_routers"])
            br = topo["border_routers"]["br1-ff00_0_111-1111"]
            self.assertEqual(len(br["interfaces"]), 2)
            self.assertIn("1", br["interfaces"]) # with port 50000
            self.assertEqual(br["interfaces"]["1"]["underlay"]["remote"], "1.1.1.1:50000")
            self.assertIn("2", br["interfaces"]) # with port 50001
            self.assertEqual(br["interfaces"]["2"]["underlay"]["remote"], "1.1.1.1:50001")

            # remove the last added esdx interface
            r.deactivate(c2)
            with open(Path(temp, "topo.json")) as f:
                topo = json.load(f)
            self.assertIn("br1-ff00_0_111-1111", topo["border_routers"])
            br = topo["border_routers"]["br1-ff00_0_111-1111"]
            self.assertEqual(len(br["interfaces"]), 1)
            self.assertIn("1", br["interfaces"]) # with port 50000
            self.assertEqual(br["interfaces"]["1"]["underlay"]["remote"], "1.1.1.1:50000")

            # remove the first added esdx interface
            r.deactivate(c1)
            with open(Path(temp, "topo.json")) as f:
                topo = json.load(f)
            self.assertNotIn("br1-ff00_0_111-1111", topo["border_routers"])
