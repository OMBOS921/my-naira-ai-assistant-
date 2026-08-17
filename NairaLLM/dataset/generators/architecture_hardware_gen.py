"""
Computer Architecture & Hardware Domain Generator for Dataset A.
Generates comprehensive technical prose on CPU microarchitectures, cache coherence, instruction sets, memory hierarchies, and GPU computing.
"""

from __future__ import annotations

from typing import Any


def get_architecture_hardware_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "computer_architecture",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Computer architecture and hardware engineering exposition",
            },
        })

    add(
        "sem_arch_001",
        "Modern microprocessor microarchitectures utilize sophisticated instruction pipelining to increase instruction throughput. A classic RISC pipeline consists of five stages: Instruction Fetch (IF), Instruction Decode (ID), Execution (EX), Memory Access (MEM), and Write Back (WB). When structural, data, or control hazards arise, hardware hazard units inject pipeline bubbles (stalls) or use register forwarding (bypassing) to route computation results directly to dependent instructions without waiting for writeback.",
        "Instruction pipelining stages, hazards, and register forwarding",
    )

    add(
        "sem_arch_002",
        "Branch prediction is a critical microarchitectural optimization in modern deep pipelines. Because conditional branch outcomes are unknown until the execution stage, speculative execution engines use dynamic branch predictors—such as two-level adaptive branch predictors and TAGE (TAgged GEometric history length) predictors—to guess branch directions. When a prediction is correct, the CPU avoids costly pipeline stalls; if mispredicted, speculative results are squashed and the pipeline is flushed.",
        "Branch prediction algorithms and speculative execution pipeline flushes",
    )

    add(
        "sem_arch_003",
        "Cache memory hierarchies bridge the massive latency disparity between fast CPU registers (sub-nanosecond) and slower main DDR RAM (tens to hundreds of nanoseconds). Multi-level caches (L1, L2, L3) exploit spatial and temporal locality. L1 cache is typically split into dedicated Instruction and Data caches with private single-cycle access; L2 is larger and semi-private; and L3 is a shared, multi-megabyte cache connected via high-speed on-die ring or mesh interconnects.",
        "Multi-level CPU cache hierarchy and locality principles",
    )

    add(
        "sem_arch_004",
        "In multi-core shared memory systems, the MESI cache coherence protocol ensures that all CPU cores observe a consistent view of memory. A cache line can reside in one of four states: Modified (valid only in this cache, dirty), Exclusive (valid only in this cache, clean), Shared (may be present in multiple caches, clean), or Invalid (does not contain valid data). Cache controllers broadcast bus snooping signals or use directory-based tracking to invalidate or update stale cache lines across cores.",
        "MESI cache coherence protocol states and bus snooping",
    )

    add(
        "sem_arch_005",
        "Non-Uniform Memory Access (NUMA) is a multiprocessing architecture where memory access time depends on the memory's spatial location relative to the processor. In multi-socket server motherboards, each processor has high-speed direct access to its local memory banks, while accessing memory attached to remote processor sockets requires traversing inter-socket buses like AMD Infinity Fabric or Intel UPI, resulting in higher latency and lower bandwidth.",
        "NUMA architecture and remote inter-socket memory latency",
    )

    add(
        "sem_arch_006",
        "Graphics Processing Units (GPUs) differ fundamentally from Central Processing Units (CPUs) in their architectural design goals. While CPUs are optimized for low-latency serial execution of complex control logic with large caches and branch prediction units, GPUs are massively parallel throughput engines designed around Single Instruction Multiple Threads (SIMT) architectures. GPUs contain thousands of lightweight ALU cores grouped into Streaming Multiprocessors (SMs) executing warps in lockstep.",
        "CPU vs GPU architectural comparison (Latency vs Throughput)",
    )

    add(
        "sem_arch_007",
        "Out-of-Order (OoO) execution engines maximize CPU utilization by executing independent instructions as soon as their required operands become available in reservation stations, rather than following strict program assembly order. Tomasulo's algorithm and register renaming mechanisms eliminate false data dependencies (Write-After-Read and Write-After-Write hazards), while Reorder Buffers (ROB) guarantee that instructions commit in-order to preserve precise architectural exception state.",
        "Out-of-order execution, Tomasulo algorithm, and Reorder Buffer",
    )

    add(
        "sem_arch_008",
        "Single Instruction, Multiple Data (SIMD) vector extensions allow a single CPU instruction to perform the identical mathematical operation across multiple data elements simultaneously. Vector instruction sets—such as Intel AVX-512, ARM Neon, and RISC-V Vector Extensions—utilize ultra-wide 128-bit, 256-bit, or 512-bit vector registers to dramatically accelerate matrix multiplication, signal processing, image rendering, and deep learning tensor computations.",
        "SIMD vector extensions (AVX-512, ARM Neon) and parallel math",
    )

    add(
        "sem_arch_009",
        "Non-Volatile Memory Express (NVMe) is a host controller interface and storage protocol designed specifically to accelerate solid-state drives (SSDs) over high-speed PCI Express (PCIe) bus lanes. Unlike legacy SATA protocols which were engineered around spinning magnetic platters with a single command queue of 32 depth, NVMe supports up to 64,000 independent command queues, each capable of holding 64,000 commands, enabling extreme parallel I/O throughput.",
        "NVMe PCIe solid-state storage protocol vs legacy SATA",
    )

    add(
        "sem_arch_010",
        "RISC-V is an open-standard Instruction Set Architecture (ISA) based on established Reduced Instruction Set Computer principles. Unlike proprietary ISAs such as x86 and ARM which require costly licensing agreements, RISC-V provides a modular, royalty-free base integer instruction set (RV32I/RV64I) accompanied by standard modular extensions for multiplication (M), atomic operations (A), floating-point math (F/D), vector processing (V), and hypervisor support (H).",
        "RISC-V open instruction set architecture and modular extensions",
    )

    return samples
