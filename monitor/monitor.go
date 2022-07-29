//go:build linux
// +build linux

package main

import (
	"encoding/binary"
	"errors"
	"flag"
	"fmt"
	"log"
	"math/bits"
	"net"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/ringbuf"
	"github.com/vishvananda/netlink"
)

//go:generate go run github.com/cilium/ebpf/cmd/bpf2go -cc clang -cflags "-O2 -g" Esdx bpf/monitor.c -- -I./libbpf/src -I/usr/include/x86_64-linux-gnu

const (
	UPSTREAM   = 0
	DOWNSTREAM = 1
)

// Monitor configuration
type Config struct {
	role             int            // UPSTREAM or DOWNSTREAM
	scion_port_range [2]uint16      // SCION underlay ports as closed interval
	up_port          *net.Interface // Interface in provider direction
	down_port        *net.Interface // Interface in customer direction
	update_interval  time.Duration  // Bandwidth log time interval
}

// Hop identifier. Since we are only dealing with a single AS, we can identify all hop(field)s by
// their ingress and egress interface ID.
type Hop struct {
	ingress uint16 // In beaconing direction
	egress  uint16 // In beaconing direction
}

func (h Hop) String() string {
	return fmt.Sprintf("%d -> %d", h.ingress, h.egress)
}

// Returns a key suitable for lookups in the BPF counters map.
func (h Hop) ToMapKey() uint32 {
	return uint32(bits.ReverseBytes16(h.ingress)) | (uint32(bits.ReverseBytes16(h.egress)) << 16)
}

// Parse command line arguments.
func parse_args() (Config, error) {
	var conf Config
	var role = flag.String("role", "",
		"[upstream|downstream] (Required) Position of the monitor relative to the provider AS.")
	var ports = flag.String("ports", "30042-30051",
		"Underlay ports used by SCION. Given as a colon-separated range of first and last port"+
			" (both inclusive).")
	var up_port_name = flag.String("up", "",
		"(Required) Device interface in the upstream direction.")
	var down_port_name = flag.String("down", "",
		"(Required) Device interface in the downstream direction.")
	var interval = flag.Int("i", 10, "Update interval in seconds.")
	flag.Parse()

	// Role
	if *role == "" {
		return conf, errors.New("role must be specified")
	}
	switch *role {
	case "upstream":
		conf.role = UPSTREAM
	case "downstream":
		conf.role = DOWNSTREAM
	default:
		return conf, errors.New("invalid monitor role")
	}

	// Underlay port range
	var port_slice = strings.Split(*ports, ":")
	if len(port_slice) != 2 {
		return conf, errors.New("invalid underlay port range")
	}
	for i := 0; i < 2; i++ {
		port, err := strconv.ParseUint(port_slice[i], 0, 16)
		if err != nil {
			return conf, errors.New("invalid underlay port")
		}
		conf.scion_port_range[i] = uint16(port)
	}

	// Device ports
	if *up_port_name == "" || *down_port_name == "" {
		return conf, errors.New("both the up-port and the down-port must be specified")
	}
	var err error = nil
	conf.up_port, err = net.InterfaceByName(*up_port_name)
	if err != nil {
		return conf, fmt.Errorf("interface not found: %s", *up_port_name)
	}
	conf.down_port, err = net.InterfaceByName(*down_port_name)
	if err != nil {
		return conf, fmt.Errorf("interface not found: %s", *up_port_name)
	}

	// Update interval
	conf.update_interval = time.Duration(*interval) * time.Second

	return conf, nil
}

func updateMapElem(bpf_map *ebpf.Map, name string, key interface{}, value interface{}) {
	err := bpf_map.Update(key, value, ebpf.UpdateAny)
	if err != nil {
		log.Printf("Update of map %s failed: %v\n", name, err)
	}
}

// Initialize the 'static configuration' BPF maps.
func initMaps(conf *Config, objs *EsdxObjects) {
	var ifaces = [2]uint32{uint32(conf.up_port.Index), uint32(conf.down_port.Index)}

	// config_map:  Global configuration
	var bpf_conf = EsdxConfig{
		Role:           uint32(conf.role),
		FirstScionPort: bits.ReverseBytes16(conf.scion_port_range[0]),
		LastScionPort:  bits.ReverseBytes16(conf.scion_port_range[1]),
	}
	updateMapElem(objs.ConfigMap, "config_map", uint32(0), bpf_conf)

	// port_map : Ingress to egress port mapping
	updateMapElem(objs.PortMap, "port_map", ifaces[0], EsdxPort{
		Direction: DOWNSTREAM,
		ForwardTo: ifaces[1],
	})
	updateMapElem(objs.PortMap, "port_map", ifaces[1], EsdxPort{
		Direction: UPSTREAM,
		ForwardTo: ifaces[0],
	})

	// tx_port : Egress interface mapping
	for _, iface := range ifaces {
		updateMapElem(objs.TxPort, "tx_port", iface, iface)
	}
}

// Attach 'prog' to the network interface 'iface' replacing any XDP program that was attached
// before.
func attachXdp(prog *ebpf.Program, iface *net.Interface) {
	link, err := netlink.LinkByIndex(iface.Index)
	if err != nil {
		log.Fatalf("Interface %s not found:\n%v\n", iface.Name, err)
	}
	if err := netlink.LinkSetXdpFd(link, prog.FD()); err != nil {
		log.Fatalf("Attaching program to interface %s failed:\n%v\n", iface.Name, err)
	}
}

// Detach any XDP program that is currently attached to 'iface'.
func detachXdp(iface *net.Interface) {
	link, err := netlink.LinkByIndex(iface.Index)
	if err != nil {
		log.Fatalf("Interface %s not found:\n%v\n", iface.Name, err)
	}
	if err := netlink.LinkSetXdpFd(link, -1); err != nil {
		log.Printf("Detaching program from interface %s failed:\n%v\n", iface.Name, err)
	}
}

// Look up 'key' in the 'counters' per-CPU LRU hash map and return the sum of all per-CPU counters.
func read_percpu_counters(counters *ebpf.Map, key interface{}) (EsdxCounter, error) {
	var total EsdxCounter
	var per_cpu_values = make([]EsdxCounter, 0)
	if err := counters.Lookup(key, &per_cpu_values); err != nil {
		return total, err
	}
	for _, values := range per_cpu_values {
		total.Bytes += values.Bytes
		total.Packets += values.Packets
	}
	return total, nil
}

// Log bandwidth counters of all hops in the 'hops' map.
// If a hop is no longer in the BPF counters map, it is deleted from 'hops'.
// Log messages are only generated for counters that have been updated compared to the last value
// stored in the 'hops' map to avoid filling the log with hops that are no longer active, but still
// remain in the LRU hash map.
func log_counters(counters *ebpf.Map, hops map[Hop]EsdxCounter) {
	var deleted_hops = make([]Hop, 0)
	var err error
	for hop, old_val := range hops {
		var new_val EsdxCounter
		if new_val, err = read_percpu_counters(counters, hop.ToMapKey()); err != nil {
			if errors.Is(err, ebpf.ErrKeyNotExist) {
				deleted_hops = append(deleted_hops, hop)
				log.Printf("Delete hop: %v\n", hop)
			} else {
				log.Printf("Error reading key %x from counters: %v\n", hop.ToMapKey(), err)
			}
			continue
		}
		if new_val != old_val {
			log.Printf("Hop %v: %d bytes, %d packets\n", hop, new_val.Bytes, new_val.Packets)
		}
		hops[hop] = new_val
	}
	for _, hop := range deleted_hops {
		delete(hops, hop)
	}
}

// Logs the hop counters every time 'tick' ticks.
// Manages an internal set of active hops based on the LRU counters BPF hash map and notifications
// from the 'new_hop' channel.
func poll_counters(counters *ebpf.Map, tick <-chan time.Time, new_hop <-chan Hop) {
	hops := make(map[Hop]EsdxCounter)
	for {
		select {
		case _, ok := <-tick:
			log_counters(counters, hops)
			if !ok {
				return
			}
		case hop := <-new_hop:
			log.Printf("New hop: %v\n", hop)
			hops[hop] = EsdxCounter{0, 0}
		}
	}
}

// Monitor the BPF event ring buffer via 'reader' and report all new hop events through the
// 'new_hop' channel.
func poll_ringbuf(reader *ringbuf.Reader, new_hop chan<- Hop) {
	for {
		record, err := reader.Read()
		if err != nil {
			log.Printf("Error reading from ring buffer: %v\n", err)
			break
		}
		var ingress = binary.BigEndian.Uint16(record.RawSample[:2])
		var egress = binary.BigEndian.Uint16(record.RawSample[2:4])
		new_hop <- Hop{ingress, egress}
	}
}

func main() {
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM)

	conf, err := parse_args()
	if err != nil {
		fmt.Println("Flags:")
		flag.PrintDefaults()
		fmt.Printf("Argument error: %v\n", err)
		return
	}

	// Load embedded BPF program
	objs := EsdxObjects{}
	if err := LoadEsdxObjects(&objs, nil); err != nil {
		log.Fatalf("Error loading objects: %v", err)
	}
	defer objs.Close()

	initMaps(&conf, &objs)

	// Attach to up-port
	attachXdp(objs.EsdxPrograms.EsdxMonitor, conf.up_port)
	defer detachXdp(conf.up_port)
	log.Printf("Monitor attached to %s\n", conf.up_port.Name)

	// Attach to down-port
	attachXdp(objs.EsdxPrograms.EsdxMonitor, conf.down_port)
	defer detachXdp(conf.down_port)
	log.Printf("Monitor attached to %s\n", conf.down_port.Name)

	// Start polling the counters and the ring buffer
	reader, err := ringbuf.NewReader(objs.EventRingbuf)
	if err != nil {
		log.Fatalf("Cannot open ring buffer: %v\n", err)
	}

	new_hop := make(chan Hop)
	ticker := time.NewTicker(conf.update_interval)
	go poll_ringbuf(reader, new_hop)
	go poll_counters(objs.Counters, ticker.C, new_hop)

	<-sig
	ticker.Stop()
	reader.Close()
}
