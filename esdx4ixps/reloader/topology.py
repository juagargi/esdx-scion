from collections import defaultdict
from contextlib import contextmanager
from ipaddress import IPv4Address, IPv6Address, ip_address
import ipaddress
from unicodedata import name
from market_pb2 import Contract
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Union
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

    def __init__(
        self,
        topofile: Path,
        internal_addr: str,
        router: Callable[[Union[IPv4Address, IPv6Address]], Union[IPv4Address, IPv6Address]]=None,
        min_port=50000,
        max_port=51000,
        attempts=10,
        sleep=0.1):
        """
        internal_addr: e.g. "1.1.1.1:43210"
        router: a function fcn(IP)-: ip that returns the ip of the local interface to use. If None,
                then a default of 127.0.0.1 for IPv4 and ::1 for IPv6 is used.
        """
        self.topofile = topofile
        self.lockfile = Path(self.topofile).parent / Path(".lock." + topofile.name)
        self.internal_addr_ip, self.internal_addr_port = conversion.ip_port_from_str(internal_addr)
        if router is None:
            def _default_router(ip):
                if ip.version == 4:
                    return ip_address("127.0.0.1")
                elif ip.version == 6:
                    return ip_address("::1")
                else:
                    raise ValueError(f"unknown ip version in {ip}")
            router = _default_router
        self.router = router
        self.min_port = min_port
        self.max_port = max_port
        self.attempts = attempts
        self.sleep = sleep # seconds
        # check consistency of the topology and internal_addr
        topo = self._load_topo()
        for k, v in topo["border_routers"].items():
            if not k.endswith("-1111"):
                # check its internal address does not clash with the ESDX's one
                ip, port = conversion.ip_port_from_str(v["internal_addr"])
                if ip == self.internal_addr_ip and port == self.internal_addr_port:
                    raise RuntimeError(f"internal address {internal_addr} already present in a " +\
                        "non ESDX BR in the topology file")

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
    def _find_lowest_free_value(values: List[int], min_value:int=1) -> int:
        values = sorted(values)
        ret = min_value
        for id in values:
            if ret < id:
                break
            ret = id + 1
        return ret

    @staticmethod
    def _generate_esdx_br_name(topo) -> str:
        ia = topo["isd_as"]
        ia = ia.replace(":", "_")
        return f"br{ia}-1111"

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
        esdx_br_name = self._generate_esdx_br_name(topo)
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
            if k == esdx_br_name:
                esdx_br = v
        if esdx_br is None:
            esdx_br = {
                "internal_addr": conversion.ip_port_to_str(
                    self.internal_addr_ip, self.internal_addr_port),
                "interfaces": defaultdict(lambda: []),
            }

            topo["border_routers"][esdx_br_name] = esdx_br
        # add a new interface with the values from "info"
        ifid = self._find_lowest_free_value(ifid_inuse)
        remote_ip, _ = conversion.ip_port_from_str(info.remote_underlay)
        public_ip = self.router(remote_ip)
        port = self._find_lowest_free_value(public_addrs[public_ip], min_value=self.min_port)
        if port > self.max_port:
            raise RuntimeError(f"could not find a free port for public ip {public_ip}")
        public_addr = conversion.ip_port_to_str(public_ip, port)
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
