"""
Networking & Distributed Systems Domain Generator for Dataset A.
Generates comprehensive technical prose on TCP/IP, HTTP protocols, DNS, BGP, distributed consensus, and network security.
"""

from __future__ import annotations

from typing import Any


def get_networking_dist_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "networking",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Computer networking and distributed systems architecture",
            },
        })

    add(
        "sem_net_001",
        "Transmission Control Protocol (TCP) establishes a reliable, bidirectional, connection-oriented byte stream between networked hosts via a standard three-way handshake. The initiating client sends a SYN packet with an initial sequence number (ISN); the server responds with a SYN-ACK packet confirming receipt and declaring its own ISN; finally, the client returns an ACK packet. This exchange synchronizes sequence numbers, establishes initial buffer windows, and prepares both endpoints for sliding-window data transmission.",
        "TCP 3-way handshake mechanics and sequence number synchronization",
    )

    add(
        "sem_net_002",
        "TCP congestion control algorithms prevent network buffer bloat and packet collapse across congested internet links. Classical loss-based algorithms like TCP Reno and TCP Cubic interpret packet loss as an indicator of congestion, halving their congestion window upon detecting dropped packets. In contrast, modern delay-based algorithms like Google's BBR (Bottleneck Bandwidth and Round-trip propagation time) model the physical bottleneck bandwidth and minimum RTT to maximize throughput without bloating intermediate router queues.",
        "TCP congestion control algorithms (Cubic vs BBR)",
    )

    add(
        "sem_net_003",
        "HTTP/3 represents a fundamental evolution in web transport protocols by transitioning from TCP to QUIC (Quick UDP Internet Connections). While HTTP/2 introduced binary framing and stream multiplexing over a single TCP connection, it suffered from Head-of-Line (HoL) blocking—if a single TCP packet was dropped, all multiplexed HTTP streams were delayed until retransmission. Because QUIC operates over UDP with independent stream encryption and congestion tracking, packet loss on one stream does not impact concurrent streams.",
        "HTTP/3 and QUIC protocol advantages over TCP HTTP/2",
    )

    add(
        "sem_net_004",
        "The Domain Name System (DNS) is a hierarchical, distributed naming system that translates human-readable domain names (such as api.example.com) into numerical IP addresses. When a recursive DNS resolver receives a query, it traverses the DNS hierarchy starting at the Root Name Servers, proceeding to Top-Level Domain (TLD) name servers (e.g., .com), and finally querying the Authoritative Name Server for the domain. Caching at each layer with Time-To-Live (TTL) expiration drastically reduces global lookup latency.",
        "DNS hierarchical resolution and recursive caching architecture",
    )

    add(
        "sem_net_005",
        "Border Gateway Protocol (BGP) is the standardized exterior gateway routing protocol that binds the global Internet together. Operating as a path-vector routing protocol, BGP routes packets between autonomous systems (AS)—large networks administered by internet service providers, tech enterprises, and universities. BGP routers exchange Network Layer Reachability Information (NLRI), applying administrative routing policies, AS path lengths, and BGP community attributes to determine optimal inter-domain paths.",
        "Border Gateway Protocol (BGP) and Autonomous System routing",
    )

    add(
        "sem_net_006",
        "Transport Layer Security (TLS 1.3) establishes cryptographic privacy and data integrity over untrusted networks. In TLS 1.3, the handshake was streamlined from two round-trips (in TLS 1.2) down to a single 1-RTT exchange. The client transmits a ClientHello with supported cryptographic cipher suites and an ephemeral Diffie-Hellman key share; the server responds with ServerHello, its own key share, and encrypted digital certificates. This establishes forward secrecy while mitigating eavesdropping and tampering.",
        "TLS 1.3 1-RTT cryptographic handshake and forward secrecy",
    )

    add(
        "sem_net_007",
        "The Raft consensus algorithm provides an understandable, fault-tolerant mechanism for managing a replicated log across a distributed cluster of nodes. Raft decomposes distributed consensus into three distinct sub-problems: Leader Election, Log Replication, and Safety. A cluster elects a single leader via randomized election timers and majority voting; the leader accepts client commands, appends entries to its local log, broadcasts AppendEntries RPCs to follower nodes, and commits entries once acknowledged by a quorum.",
        "Raft distributed consensus algorithm and leader election",
    )

    add(
        "sem_net_008",
        "The CAP theorem states that any distributed data store can simultaneously guarantee at most two out of three fundamental properties: Consistency (every read receives the most recent write or an error), Availability (every non-failing node returns a non-error response without guarantee of latest write), and Partition Tolerance (the system continues operating despite network packet loss or partitions). Because physical network partitions are unavoidable, real distributed systems must be designed as either CP or AP architectures.",
        "CAP theorem trade-offs in distributed systems design",
    )

    add(
        "sem_net_009",
        "WebSockets provide full-duplex, bidirectional, persistent communication channels over a single long-lived TCP connection. Initiated via an HTTP Upgrade handshake, WebSockets bypass the request-response overhead of HTTP headers on subsequent transmissions, allowing real-time servers to push instantaneous updates to connected clients. In contrast, Server-Sent Events (SSE) provide lightweight, unidirectional text streaming from server to client over standard HTTP.",
        "WebSockets vs Server-Sent Events (SSE) real-time protocols",
    )

    add(
        "sem_net_010",
        "gRPC is a high-performance, open-source universal RPC framework developed by Google. Utilizing HTTP/2 as its underlying transport layer and Protocol Buffers (Protobuf) as its Interface Definition Language (IDL) and binary serialization mechanism, gRPC offers strict contract generation across diverse programming languages, bidirectional streaming, client-side load balancing, deadlines/timeouts, and efficient binary wire payloads superior to JSON-based REST APIs.",
        "gRPC framework, Protocol Buffers binary serialization, and HTTP/2 transport",
    )

    return samples
