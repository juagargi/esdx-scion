from collections import defaultdict
from contextlib import contextmanager
from unicodedata import name
from market_pb2 import Contract
from pathlib import Path
from typing import NamedTuple
from util import conversion
import json
import os
import time


# TODO(juagargi): the (re)loading task should be executed automatically from a task manager,
# such as Celery, Advanced Python Scheduler, or something else.
# To simplify development, at the moment the events are triggered manually by an admin.

class Topology:
    """ Represents the SCiON topology """

    class TopoInfoFromContract(NamedTuple):
        """ topology information derived from a Contract """
        remote_ia: str
        remote_underlay: str
        mtu: int
        link_to: str

    def __init__(self, topofile: Path, attempts=10, sleep=0.1):
        self.topofile = topofile
        self.lockfile = Path(self.topofile).parent / Path(".lock." + topofile.name)
        self.attempts = attempts
        self.sleep = sleep # seconds

    def _load_topo(self) -> dict:
        with open(self.topofile) as r:
            return json.load(r)

    @contextmanager
    def _lock(self):
        def _lock():
            ex = None
            for attempts in range(self.attempts):
                try:
                    with open(self.lockfile, "x+b"):
                        return
                except FileExistsError as e:
                    ex = e
                    attempts += 1
                    time.sleep(self.sleep)
            if attempts >= self.attempts:
                raise RuntimeError(ex) from ex
        _lock()
        try:
            yield
        finally:
            try:
                os.remove(self.lockfile)
            except FileNotFoundError as ex:
                raise RuntimeError(ex) from ex


    def _contract_as_seller(self, c: Contract) -> TopoInfoFromContract:
        """ Returns the relevant info for the seller """
        return Topology.TopoInfoFromContract(
            remote_ia=c.buyer_iaid,
            remote_underlay=c.br_address,
            mtu=c.offer.br_mtu,
            link_to=c.offer.br_link_to,
        )

    def _contract_as_buyer(self, c: Contract) -> TopoInfoFromContract:
        """ Returns the relevant info for the buyer """
        return Topology.TopoInfoFromContract(
            remote_ia=c.offer.iaid,
            remote_underlay=c.br_address,
            mtu=c.offer.br_mtu,
            link_to=c.offer.br_link_to,
        )

    def _contract_info(self, topo: dict, c: Contract) -> TopoInfoFromContract:
        # find out if we are the seller or the buyer
        if topo["isd_as"] == c.offer.iaid:
            seller=True
        elif topo["isd_as"] == c.buyer_iaid:
            seller=False
        else:
            raise RuntimeError(f"bad contract: topology indicates local AS is {topo['isd_as']}, "+\
                "and contract has seller={c.offer.iaid} and buyer={c.buyer_iaid}")
        return self._contract_as_seller(c) if seller else self._contract_as_buyer(c)

    @staticmethod
    def _find_lowest_free_id(ids):
        ids = sorted(ids)
        ret = 1
        for id in ids:
            if ret < id:
                break
            ret = id + 1
        return ret

    @staticmethod
    def _generate_esdx_br_name(topo) -> str:
        ia = topo["isd_as"]
        ia = ia.replace(":", "_")
        return f"br{ia}-1111"

    @classmethod
    def _find_avail_public_addr(cls, addrs: dict) -> str:
        """
        the same IP as the only one in the dict, and the smallest free port possible which
        is bigger than the smaller of the ports in the list
        """
        if len(addrs) != 1:
            raise RuntimeError(f"cannot determine the public address: expected one ip but got " + \
                f"{len(addrs)} instead")
        ip, ports = next(iter(addrs.items()))
        ports = sorted(ports)
        port = 65536 if len(ports) > 0 else 1
        for p in ports:
            if port < p:
                break
            port = p + 1

        return conversion.ip_port_to_str(ip, port)

    def _add_cotract_to_topo(self, topo: dict, info: TopoInfoFromContract):
        """
        The ESDX border router is one that ends in -1111. If none is found in the topology,
        this function adds one, with internal address deduced from the internal address of
        the other BRs. If there is more than one IP in the list of internal addresses,
        it raises an exception. The port is the max(ports) + 1.
        It also adds a new interface to the ESDX BR. The public address is again deduced from
        the public addresses of the other interfaces of all border routers. If more than
        one IP address exists in the list of public addresses, it raises an exception.
        The port is the first integer greater than zero not in use by other interface.
        """
        # find the ESDX BR; create it if not there.
        # The ESDX BR is the one that ends with -1111
        esdx_br = None
        internal_addrs = defaultdict(lambda: [])
        public_addrs = defaultdict(lambda: [])
        ifid_inuse = []
        for k, v in topo["border_routers"].items():
            # add its interface IDs to the list
            ifid_inuse.extend([int(k) for k in v["interfaces"].keys()])
            # add its public addresses to the list
            addrs = [interface["underlay"]["public"] for interface in v["interfaces"].values()]
            for a in addrs:
                ip, port = conversion.ip_port_from_str(a)
                public_addrs[ip].append(port)
            # is this the ESDX router?
            if k.endswith("-1111"):
                esdx_br = v
                break
            # collect its internal address
            ip, port = conversion.ip_port_from_str(v["internal_addr"])
            internal_addrs[ip].append(port)
        if esdx_br is None:
            # not found, add one. Use a similar address to those found in the topology
            # TODO(juagargi) allow to configure the internal and control addresses
            if len(internal_addrs) != 1:
                raise RuntimeError("cannot automatically create a new border router: " + \
                    "collected more than one internal address ip and don't know which " + \
                    f"one to use (collected {[str(a) for a in internal_addrs.keys()]})")
            ip, ports = next(iter(internal_addrs.items()))
            port = max(ports) + 1
            esdx_br = {
                "internal_addr": conversion.ip_port_to_str(ip, port),
                "interfaces": defaultdict(lambda: []),
            }

            topo["border_routers"][self._generate_esdx_br_name(topo)] = esdx_br
        # add a new interface with the values from "info"
        ifid = self._find_lowest_free_id(ifid_inuse)
        public_addr = self._find_avail_public_addr(public_addrs)
        esdx_br["interfaces"][str(ifid)] = {
            "underlay": {
                "public": public_addr,
                "remote": info.remote_underlay,
            },
            "isd_as": info.remote_ia,
            "mtu": info.mtu,
            "link_to": info.link_to,
        }

    @staticmethod
    def _remove_interface_from_br(topo: dict, info: TopoInfoFromContract):
        for br in topo["border_routers"].values():
            for ifid, iface in br["interfaces"].items():
                if iface["underlay"]["remote"] == info.remote_underlay:
                    del br["interfaces"][ifid]
                    return
        raise RuntimeError(f"interface with remote {info.remote_underlay} not found in topology")

    @classmethod
    def _remove_interface(cls, topo: dict, info: TopoInfoFromContract):
        cls._remove_interface_from_br(topo, info)
        # remove esdx BR if empty
        br_id = cls._generate_esdx_br_name(topo)
        if len(topo["border_routers"][br_id]["interfaces"]) == 0:
            del topo["border_routers"][br_id]

    def activate(self, c: Contract):
        """
        Creates a new topology based on the existing topology and the contract.
        The merge of the contract inside the topology is done atomically: i.e. if all manipulations
        of the topology are done through this Topology class, activating/deactivating the
        contracts should have no race conditions.
        """
        with self._lock():
            # read topology
            topo = self._load_topo()
            # add contract
            info = self._contract_info(topo, c)
            self._add_cotract_to_topo(topo, info)
            # write topology
            with open(self.topofile, "w") as w:
                raw = json.dumps(topo, indent=2) + "\n"
                w.write(raw)

    def deactivate(self, c: Contract):
        with self._lock():
            # read topology
            topo = self._load_topo()
            # find and remove interface. The remote underlay is unique; remove esdx BR if empty.
            # TODO(juagargi) is the remote underlay unique per topology?
            info = self._contract_info(topo, c)
            self._remove_interface(topo, info)

            # write topology
            with open(self.topofile, "w") as w:
                raw = json.dumps(topo, indent=2) + "\n"
                w.write(raw)
