Bandwidth Monitor
=================

The bandwidth monitor counts the number of bytes forwarded between two SCION ASes. Counts are
grouped by the ingress and egress interface pair found in the hop field.

### Usage
The bandwidth monitor is invoked with a role (either upstream or downstream) and a pair of network
interfaces between which traffic is forwarded. Additionally, the range of UDP ports used for SCION
and the bandwidth logging interval can be specified.

```
Usage of ./monitor:
  -down string
    	(Required) Device interface in the downstream direction.
  -i int
    	Update interval in seconds. (default 10)
  -ports string
    	Underlay ports used by SCION. Given as a colon-separated range of first and last port (both inclusive). (default "30042-30051")
  -role string
    	[upstream|downstream] (Required) Position of the monitor relative to the provider AS.
  -up string
    	(Required) Device interface in the upstream direction.
```

Bandwidth logs are written to stderr and contain the total number of bytes and packets observed
for each known interface pair. A log message is only generated for pairs that had activity since the
last report. The byte and packet count do not necessarily start from zero, to get meaningful
bandwidth values, the difference between to log messages has to be used.


Contract Monitoring
-------------------
To monitor ESDX contract fulfillment, an instance of the bandwidth monitor is placed on either side
of the provider AS as a 'bump in the wire'. We refer to the instance on the upstream provider side
as upstream monitor and the instance on the side of the customer AS as downstream monitor. The
upstream and downstream monitors parse the path header of all (SCION) packets passing through them
and extract the hop field belonging to the provider hop. The ingress and egress interface IDs in the
provider hop field uniquely identify any active ESDX contract of the provider.

![Monitor application](doc/esdx_monitor.png)

The monitors count and log the number of bytes forwarded for each interface pair. The logs can be
used to proof that:
1. The customer AS did not use more bandwidth than agreed upon on any path enabled by the contract.
2. The provider AS delivered the guaranteed bandwidth between the IXP and the upstream interfaces.

### Limitations
1. The monitor cannot check hop field and overall packet validity. Invalid packets are legitimately
not forwarded by the provider AS. On the other hand, invalid packets originating from the buyer or
seller itself should not be counted against the bandwidth limit.
2. There is no way of knowing whether the application payloads have actually been forwarded by the
provider AS. The provider could create new packets with arbitrary payload at the egress border
router to match the ingress traffic profile.


Development
-----------
Make sure the `libbpf` submodule is initialized, as we need some libbpf headers to compile the BPF
part of the monitor. Since we only need the headers, it is not necessary to build libbpf.

Compile the BPF/XDP code and generate Go bindings:
```bash
go generate
```

Build the host application:
```bash
go build
```

There is an example SCION topology mirroring the figure above in [test/topology](./test/topology).
It requires Docker and docker-compose, as well as a copy of
[SCION](https://github.com/netsec-ethz/scion) and
[SCION-Apps](https://github.com/netsec-ethz/scion-apps).

Set environment variables `SCION_ROOT` (default: `$HOME/scion`) and `SCION_APPS`
(default: `$HOME/scion-apps`) to point to the SCION and scion-apps source trees, respectively.

The topology can be run by typing
```bash
cd test/topology
./test_topo run
```

The monitor log files are stored in `test/topology/log`.


Implementation Details
----------------------
The monitor consists of a host application written in Go and an XDP data path written in C. The C
code is compiled through bpf2go which embeds the XDP program in the final executable.

The XDP program is attached to a pair of interfaces and used the `bpf_redirect_map` helper function
to forward all packets entering on interface to the other. As result, the monitor is completely
transparent to the border routers. The actual monitoring function is realized by attempting to parse
each packet as IP/UDP. If we have a UDP packet, the UDP destination port is compared to a range of
expected SCION ports. We can only rely on the destination port as some border routers (namely
Anapaya's HSR) randomize the source port. If the destination port indicates a SCION packet, the
SCION common header and path header is parsed. At the moment only standard SCION paths are supported
(no Colibri). Depending on the position of the monitor (upstream or downstream) and the direction
of the packet, the monitor either extracts the interface IDs of the current or previous hop field
to make sure we capture the hop traversing the IXP and provider AS.

Byte and packet counters are stored int a BPF LRU hash map. The concatenation of ingress and egress
interface ID from the hop field is used as key. Since an LRU hash map automatically evicts the least
recently used entry once it run out of space, care must be taken to set a sufficient capacity
(`MAX_HOPS`). In regular intervals, the host application reads the current counter values from the
hash map. Since it is not possible to reliably iterate over the map from userspace as entries can
be inserted or deleted asynchronously, the host application maintains a set of known valid keys.
The XDP data path notifies the host application of new map entries through a ring buffer. If the
host application finds a key is no longer in the map (because it has been replaced by new keys), it
is deleted from the host applications's set.
