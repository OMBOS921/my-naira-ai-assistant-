"""
Technical Explanations & Systems Reasoning Domain Generator for Dataset A.
Generates comprehensive step-by-step technical narratives explaining complex computing mechanisms in depth.
"""

from __future__ import annotations

from typing import Any


def get_technical_explanations_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "technical_explanations",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Step-by-step systems reasoning and technical mechanism narratives",
            },
        })

    add(
        "sem_expl_001",
        "When a modern x86-64 computer boots, it initiates an intricate sequence of hardware and firmware transitions. Upon power-on, the CPU resets registers and executes UEFI (Unified Extensible Firmware Interface) firmware stored in SPI NOR flash. UEFI initializes motherboard memory controllers, performs Power-On Self-Test (POST), and reads the EFI System Partition (ESP) on the boot drive. UEFI loads the GRUB bootloader binary, which reads its configuration file, loads the Linux kernel binary (`vmlinuz`) and initial ramdisk (`initrd`) into RAM, and transfers control to the kernel decompression stub. The kernel initializes memory paging, discovers PCI hardware buses, mounts the temporary initramfs root, loads storage drivers, mounts the true root filesystem, and launches `/sbin/init` (systemd PID 1).",
        "Step-by-step computer boot sequence from UEFI firmware to systemd PID 1",
    )

    add(
        "sem_expl_002",
        "Understanding how a Solid-State Drive (SSD) writes data requires examining NAND flash physics and the Flash Translation Layer (FTL). NAND flash memory cannot overwrite data in place; it must write data in small Pages (typically 4 KB to 16 KB) but can only erase data in large Blocks (typically 128 to 512 pages). When an application modifies existing data, the FTL writes the updated page to an empty erased page, updates its internal logical-to-physical address mapping table in RAM, and marks the old page as obsolete (invalid). Over time, background Garbage Collection cycles read valid pages from fragmented blocks, copy them to fresh blocks, and issue high-voltage erase commands to reclaim dirty blocks.",
        "SSD NAND flash page writes, block erasures, and FTL garbage collection",
    )

    add(
        "sem_expl_003",
        "When a web browser navigates to an HTTPS URL, it coordinates a multi-layered sequence across the networking stack. First, the browser checks its local cache and queries DNS to resolve the hostname to an IP address. Second, it establishes a TCP connection via a SYN/SYN-ACK/ACK 3-way handshake on port 443. Third, it conducts a TLS 1.3 cryptographic handshake: exchanging elliptic curve Diffie-Hellman keys, validating the server's X.509 certificate against trusted root CAs, and deriving symmetric AES-GCM session keys. Fourth, the browser transmits an encrypted HTTP GET request with headers. Fifth, the web server processes the request, queries its database, and returns an HTTP 200 response with HTML payload. Finally, the browser parses the HTML, builds the DOM/CSSOM, and renders visual pixels.",
        "Step-by-step anatomy of an HTTPS web request and browser rendering lifecycle",
    )

    add(
        "sem_expl_004",
        "How a relational database executes a SQL query with JOIN and WHERE clauses: The SQL text is initially parsed by the lexer and parser into an abstract parse tree, validating SQL grammar. The semantic analyzer binds table and column identifiers against catalog schemas, checking data types and permissions. The query rewriter expands views and flattens subqueries. The cost-based optimizer generates multiple candidate execution plans—evaluating index scans vs sequential scans, and join algorithms like Hash Join vs Nested Loop—selecting the plan with minimal estimated I/O and CPU cost. The execution engine invokes the plan's iterator nodes, reading disk blocks into buffer cache pools, evaluating filter predicates, assembling joined tuple rows, and streaming result sets to the client.",
        "Step-by-step query execution lifecycle inside relational database engines",
    )

    add(
        "sem_expl_005",
        "How an event-driven async runtime executes concurrent non-blocking tasks: The central event loop maintains a ready queue of runnable coroutine tasks and polls an OS I/O multiplexer (epoll on Linux, kqueue on macOS, IOCP on Windows). When a coroutine initiates a non-blocking network read, the runtime registers the file descriptor with epoll, saves the coroutine's state frame, and removes it from the ready queue. The event loop then pops the next ready task from its queue and executes it. When the kernel detects incoming network packets on the registered socket, epoll wakes the event loop, which moves the suspended coroutine back to the ready queue with the populated buffer data for seamless resumption.",
        "Step-by-step event loop and epoll OS multiplexing mechanics",
    )

    return samples
