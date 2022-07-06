#include "builtins.h"
#include "scion.h"
#include "types.h"

#include "bpf_helpers.h"

#include <linux/if_ether.h>
#include <linux/bpf.h>
#include <linux/ip.h>
#include <linux/ipv6.h>
#include <linux/in.h>
#include <linux/udp.h>

#include <stdbool.h>
#include <stddef.h>

char _license[] SEC("license") = "Dual MIT/GPL";


#define MAX_PORTS 32
#define MAX_HOPS 1024
#define RINGBUF_SIZE (4 * 4096)

#define UPSTREAM 0
#define DOWNSTREAM 1


/////////////
// Structs //
/////////////

struct config
{
    u32 role; // upstream or downstream from provider AS
    u16 firstScionPort;
    u16 lastScionPort;
};

struct counter
{
    u64 bytes;
    u64 packets;
};

struct port
{
    u32 direction;  // towards downstream customer or upstream provider
    u32 forward_to; // corresponding egress port
};

struct headers
{
    struct ethhdr *eth;
    union {
        struct iphdr *v4;
        struct ipv6hdr *v6;
    } ip;
    struct udphdr *udp;
    struct scionhdr *scion;
    struct hopfield *hf;
};


//////////
// Maps //
//////////

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __type(key, u32);
    __type(value, struct config);
    __uint(max_entries, 1);
} config_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_LRU_PERCPU_HASH);
    __type(key, u32);
    __type(value, struct counter);
    __uint(max_entries, MAX_HOPS);
} counters SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, RINGBUF_SIZE);
} event_ringbuf SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __type(key, u32);
    __type(value, struct port);
    __uint(max_entries, MAX_PORTS);
} port_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_DEVMAP);
    __type(key, u32);
    __type(value, u32);
    __uint(max_entries, MAX_PORTS);
} tx_port SEC(".maps");


//////////////////////
// Inline Functions //
//////////////////////

static inline bool parse_underlay(struct headers *hdr, void **pdata, void *data_end);
static inline bool parse_scion(struct headers *hdr, void **pdata, void *data_end, bool prev_hf);
static inline int parse_scion_path(struct headers *hdr, void **pdata, void *data_end, bool prev_hf);
static inline void report_new_hop(u32 hop);
static inline void count(struct config *config, void *data, void *data_end, bool prev_hf);

// Parse the Ethernet header and IP/UDP underlay
__attribute__((__always_inline__))
static inline bool parse_underlay(struct headers *hdr, void **pdata, void *data_end)
{
    void *data = *pdata;

    // Ethernet
    hdr->eth = data;
    data += sizeof(*hdr->eth);
    if (data > data_end) return false;
    // IP
    switch (hdr->eth->h_proto)
    {
    case htons(ETH_P_IP):
        hdr->ip.v4 = data;
        data += sizeof(*hdr->ip.v4);
        if (data > data_end) return false;
        // Skip options
        size_t skip = 4 * (size_t)hdr->ip.v4->ihl - sizeof(*hdr->ip.v4);
        if (skip > 40) return false;
        data += skip;
        if (hdr->ip.v4->protocol != IPPROTO_UDP) return false;
        break;

    case htons(ETH_P_IPV6):
        hdr->ip.v6 = data;
        data += sizeof(*hdr->ip.v6);
        if (data > data_end) return false;
        if (hdr->ip.v6->nexthdr != IPPROTO_UDP) return false;
        break;

    default:
        return false;
    }

    // UDP
    hdr->udp = data;
    data += sizeof(*hdr->udp);
    if (data > data_end) return false;

    *pdata = data;
    return true;
};

// Parse the SCION headers
__attribute__((__always_inline__))
static inline bool parse_scion(struct headers *hdr, void **pdata, void *data_end, bool prev_hf)
{
    void *data = *pdata;

    // SCION common and address header
    hdr->scion = data;
    data += sizeof(*hdr->scion);
    if (data > data_end) return false;
    if (SC_GET_VER(hdr->scion) != 0)
        return false;

    // Skip over AS-internal addresses
    data += 8 + 4 * SC_GET_DL(hdr->scion) + 4 * SC_GET_SL(hdr->scion);
    if (data > data_end) return false;

    // Path
    switch (hdr->scion->type)
    {
    case SC_PATH_TYPE_SCION:
        if (!parse_scion_path(hdr, &data, data_end, prev_hf)) return false;
        break;
    default:
        return false;
    }

    *pdata = data;
    return true;
}

// Parse standard SCION path
__attribute__((__always_inline__))
static inline int parse_scion_path(struct headers *hdr, void **pdata, void *data_end, bool prev_hf)
{
    void *data = *pdata;

    // Meta header
    u32 *meta_hdr = data;
    data += sizeof(*meta_hdr);
    if (data > data_end) return false;
    u32 meta = ntohl(*meta_hdr);

    // Calculate number of info fields
    u32 num_inf = (PATH_GET_SEG0_HOST(meta) > 0)
        + (PATH_GET_SEG1_HOST(meta) > 0)
        + (PATH_GET_SEG2_HOST(meta) > 0);

    // Current an d previous hop field
    u32 curr_hf = PATH_GET_CURR_HF_HOST(meta);
    void *first_hf = data + num_inf * sizeof(struct infofield);

    hdr->hf = first_hf + curr_hf * sizeof(struct hopfield);
    if (((void*)hdr->hf + sizeof(struct hopfield)) > data_end)
        return false;

    if (prev_hf) hdr->hf = hdr->hf - 1;

    *pdata = data;
    return true;
}

__attribute__((__always_inline__))
static inline void report_new_hop(u32 hop)
{
    u32 *buf = bpf_ringbuf_reserve(&event_ringbuf, sizeof(u32), 0);
    if (buf)
    {
        memcpy(buf, &hop, sizeof(u32));
        bpf_ringbuf_submit(buf, BPF_RB_FORCE_WAKEUP);
    }
}

__attribute__((__always_inline__))
static inline void count(struct config *config, void *data, void *data_end, bool prev_hf)
{
    struct headers hdr = {};
    u64 pkt_size = data_end - data;

    if (!parse_underlay(&hdr, &data, data_end))
        return; // not SCION

    if (hdr.udp->dest < config->firstScionPort || hdr.udp->dest > config->lastScionPort)
        return; // not SCION

    if (!parse_scion(&hdr, &data, data_end, prev_hf))
        return; // invalid or unsupported SCION header

    u32 hop = (u32)hdr.hf->ingress | ((u32)hdr.hf->egress << 16);
    struct counter *ctr = bpf_map_lookup_elem(&counters, &hop);
    if (ctr)
    {
        ctr->bytes += pkt_size;
        ctr->packets++;
    }
    else
    {
        struct counter new_counter = {
            .bytes = pkt_size,
            .packets = 1,
        };
        bpf_map_update_elem(&counters, &hop, &new_counter, BPF_NOEXIST);
        report_new_hop(hop);
    }
}


//////////////////////
// Global Functions //
//////////////////////

SEC("xdp")
int esdx_monitor(struct xdp_md *ctx)
{
    void *data = (void*)(long)ctx->data;
    void *data_end = (void*)(long)ctx->data_end;

    u32 key = 0;
    struct config *config = bpf_map_lookup_elem(&config_map, &key);
    if (!config) return XDP_ABORTED;

    u32 ingress_port = ctx->ingress_ifindex;
    struct port *port = bpf_map_lookup_elem(&port_map, &ingress_port);
    if (!port) return XDP_ABORTED;

    count(config, data, data_end, config->role == port->direction);

    return bpf_redirect_map(&tx_port, port->forward_to, 0);
}
