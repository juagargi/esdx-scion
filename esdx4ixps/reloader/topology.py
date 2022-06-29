from pathlib import Path
from market_pb2 import Contract
import json
import os
import time


# TODO(juagargi): the (re)loading task should be executed automatically from a task manager,
# such as Celery, Advanced Python Scheduler, or something else.
# To simplify development, at the moment the events are triggered manually by an admin.

class Topology:
    """ Represents the SCiON topology """

    def __init__(self, topofile: Path):
        self.topofile = topofile
        self.lockfile = Path(self.topofile).parent / Path(".lock." + topofile.name)
        self.attempts = 10
        self.sleep = 0.1 # seconds

    def _load_topo(self):
        with open(self.topofile) as r:
            return json.load(r)

    def _lock(self):
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
            raise ex

    def _unlock(self):
        os.remove(self.lockfile)

    def activate(self, c: Contract):
        """
        Creates a new topology based on the existing topology and the contract.
        The merge of the contract inside the topology is done atomically: i.e. if all manipulations
        of the topology are done through this Topology class, activating/deactivating the
        contracts should have no race conditions.
        """
        # create lock file
        self._lock()
        # read topology
        topo = self._load_topo()
        # add contract
        # write topology
        with open(self.topofile, "w") as w:
            raw = json.dumps(topo, indent=2) + "\n"
            w.write(raw)
        # remove lock file
        self._unlock()

    def deactivate(c: Contract):
        pass