"""
Expanded Systems & Architecture Domain Generator for Dataset A.
Generates comprehensive deep dives into kernel scheduling, lockless data structures, SIMD vectorization, and network stacks.
"""

from __future__ import annotations

from typing import Any


def get_systems_expanded_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "operating_systems",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Expanded systems and kernel architecture deep dive",
            },
        })

    add(
        "sem_os_015",
        "The Linux Completely Fair Scheduler (CFS) models an ideal multi-tasking CPU on real hardware using red-black trees. Instead of relying on rigid time-slice heuristics, CFS tracks each task's virtual runtime (vruntime)—a metric reflecting the amount of execution time the thread has consumed scaled inversely by its nice priority weight. The scheduler always selects the leftmost node in the red-black tree (the task with minimal vruntime) to execute next. When executed, its vruntime increases, and the kernel re-inserts it into the tree in O(log N) time, guaranteeing proportional CPU fairness.",
        "Linux Completely Fair Scheduler (CFS) vruntime and red-black tree mechanics",
    )

    add(
        "sem_os_016",
        "Lockless programming leverages hardware atomic instructions—such as Compare-And-Swap (CAS), Fetch-And-Add, and memory barriers—to synchronize concurrent threads without acquiring operating system mutexes. In a lock-free Single-Producer Single-Consumer (SPSC) ring buffer, the producer thread updates the write pointer with release memory semantics, while the consumer thread reads with acquire memory semantics. This enforces memory ordering across out-of-order CPU cores without invoking expensive kernel-level thread sleep and wakeup transitions.",
        "Lock-free concurrency, Compare-And-Swap (CAS), and acquire-release semantics",
    )

    add(
        "sem_os_017",
        "eBPF (Extended Berkeley Packet Filter) is a revolutionary in-kernel virtual machine technology that allows developers to run sandboxed custom bytecode programs inside the Linux kernel without modifying kernel source code or loading dangerous kernel modules. An in-kernel static bytecode verifier guarantees that eBPF programs terminate (no infinite loops) and cannot access illegal memory boundaries. eBPF is widely utilized for ultra-high-speed network packet filtering (XDP), deep kernel observability, security policy enforcement (Cilium), and runtime tracing.",
        "eBPF in-kernel programmable sandbox architecture and verifier rules",
    )

    add(
        "sem_os_018",
        "Zero-Copy I/O techniques eliminate redundant memory copying between kernel space buffers and user space memory during high-throughput file network transfers. In traditional read/write pipelines, data is copied from disk to kernel page cache, from page cache to user application buffer, from user buffer back to kernel socket buffer, and finally to the network card DMA buffer (4 copies). Using the Linux `sendfile()` or `splice()` system calls, data transfers directly from page cache to socket buffers, bypassing user space and dramatically reducing CPU cache misses.",
        "Zero-Copy I/O architecture (sendfile, splice) vs traditional buffer copying",
    )

    return samples
