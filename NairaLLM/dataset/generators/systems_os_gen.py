"""
Operating Systems & Low-Level Concepts Domain Generator for Dataset A.
Generates comprehensive technical prose on kernel architectures, virtual memory, scheduling, IPC, file systems, and concurrency primitives.
"""

from __future__ import annotations

from typing import Any


def get_systems_os_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Operating systems internal architecture and low-level mechanics",
            },
        })

    add(
        "sem_os_005",
        "The Translation Lookaside Buffer (TLB) is a high-speed associative hardware cache situated within the CPU's Memory Management Unit (MMU). Its dedicated purpose is to store recent translations of virtual memory page numbers to physical frame numbers. When a memory access results in a TLB hit, address translation completes in a single clock cycle without accessing physical memory. Conversely, a TLB miss forces the hardware page table walker to traverse multi-level page tables in RAM, incurring a latency penalty of dozens to hundreds of nanoseconds.",
        "Translation Lookaside Buffer (TLB) hardware mechanics",
    )

    add(
        "sem_os_006",
        "Context switching is the kernel mechanism that saves the execution state of an active thread or process—including program counter, general-purpose registers, stack pointers, and memory mapping descriptors—and restores the saved state of another ready thread. While context switches enable pre-emptive multitasking and high interactivity, they impose performance overhead due to CPU register saving, scheduler algorithm execution, and cache pollution across L1/L2 caches and the TLB.",
        "CPU context switching mechanics and performance overhead",
    )

    add(
        "sem_os_007",
        "In modern monolithic kernel architectures like Linux, system calls represent the controlled programmatic interface between unprivileged user space applications and privileged kernel space. When an application initiates a system call via CPU instructions such as SYSCALL or INT 0x80, the CPU transitions from User Mode (Ring 3) to Supervisor Mode (Ring 0). The kernel verifies argument pointers, executes the requested hardware or memory operation securely, and transitions back to user mode.",
        "System call transition from User Mode Ring 3 to Supervisor Mode Ring 0",
    )

    add(
        "sem_os_008",
        "Concurrency synchronization primitives prevent race conditions when multiple threads concurrently access shared mutable memory. A Mutex (mutual exclusion lock) guarantees that only one thread executes a critical section at any given instant. A Spinlock repeatedly polls a lock variable in a tight loop, suitable only for low-latency kernel locks where blocking sleep would be costlier than brief spinning. Semaphores maintain integer counters, allowing a specified number of concurrent accesses.",
        "Synchronization primitives (Mutex, Spinlock, Counting Semaphore)",
    )

    add(
        "sem_os_009",
        "Unix domain sockets provide high-performance, bidirectional Inter-Process Communication (IPC) for processes residing on the same host operating system. Unlike network TCP/IP sockets which traverse the full networking stack, packet framing, and checksumming routines, Unix domain sockets transfer raw byte streams or datagrams entirely in kernel memory buffers, achieving substantially higher throughput and lower latency while enforcing filesystem-based access permissions.",
        "Unix domain sockets IPC vs network sockets",
    )

    add(
        "sem_os_010",
        "Virtual File System (VFS) is an architectural abstraction layer within the operating system kernel that provides a uniform interface to disparate physical file systems such as ext4, XFS, Btrfs, and network NFS. The VFS defines standard function pointers for file operations (open, read, write, seek, close) via inode, dentry, and file object structures, allowing user applications to interact with heterogeneous storage media through standard POSIX system call abstractions.",
        "Virtual File System (VFS) abstraction layer in operating systems",
    )

    add(
        "sem_os_011",
        "Deadlocks in concurrent computing occur when a set of processes are blocked because each process holds a resource and waits for another resource held by another process in the set. Coffman's four necessary conditions for deadlock are: Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait. Operating systems prevent deadlocks by eliminating circular wait through global resource ordering or resolving deadlocks via Banker's algorithm and thread termination.",
        "Coffman conditions for deadlocks and avoidance algorithms",
    )

    add(
        "sem_os_012",
        "Direct Memory Access (DMA) is a hardware feature of modern computer architectures that allows peripheral devices (such as network interface cards, disk controllers, and graphics processors) to read from and write directly to main system RAM without continuous CPU intervention. The CPU initiates the transfer by configuring DMA controller registers with source, destination, and byte count; the DMA controller conducts the memory transfer autonomously and fires a hardware interrupt upon completion.",
        "Direct Memory Access (DMA) controllers and CPU offloading",
    )

    add(
        "sem_os_013",
        "Asynchronous I/O multiplexing allows a single thread to monitor thousands of concurrent file descriptors for read or write readiness without blocking. Classical system calls like select() and poll() suffer from O(N) scaling overhead because the kernel must scan every monitored descriptor. In contrast, Linux epoll and BSD kqueue use event-driven data structures in kernel memory, achieving O(1) performance scaling ideal for high-concurrency network servers.",
        "I/O multiplexing evolution from select and poll to epoll and kqueue",
    )

    add(
        "sem_os_014",
        "Memory fragmentation in operating systems manifests as internal or external fragmentation. Internal fragmentation occurs when allocated memory blocks are larger than the requested payload due to fixed page or chunk granularity. External fragmentation occurs when total free memory is sufficient to satisfy an allocation request, but available space is partitioned into small, non-contiguous blocks. Buddy allocators and slab allocators mitigate fragmentation for kernel objects.",
        "Memory fragmentation types and kernel slab allocators",
    )

    return samples
