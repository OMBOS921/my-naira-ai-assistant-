"""
Core Systems Reasoning & Multilingual Depth Domain Generator for Dataset A.
Generates comprehensive technical prose on memory consistency models, ARIES recovery, CLOCK page replacement, and Devanagari collation.
"""

from __future__ import annotations

from typing import Any


def get_core_reasoning_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, domain: str, lang: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": domain,
            "language": lang,
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Core systems reasoning and technical architecture exposition",
            },
        })

    add(
        "sem_rsn_001",
        "computer_architecture",
        "en",
        "Memory consistency models define the architectural contract between hardware and multithreaded software regarding the observable order of memory reads and writes across multiple CPU cores. Under Sequential Consistency (SC), all processors observe a globally uniform interleaving of memory operations where each core's operations execute in strict program order. Because strict SC severely limits hardware optimizations, modern processors implement relaxed memory models: x86-64 enforces Total Store Order (TSO), allowing Store-Load reordering via store buffers, while ARM64 and RISC-V implement weakly ordered memory models requiring explicit memory barrier instructions (such as `DMB` on ARM or `FENCE` on RISC-V) to enforce ordering constraints.",
        "Memory consistency models (Sequential Consistency, TSO, Weak Ordering, Barriers)",
    )

    add(
        "sem_rsn_002",
        "operating_systems",
        "en",
        "The CLOCK (Second-Chance) page replacement algorithm provides an efficient O(1) approximation of the ideal Least Recently Used (LRU) policy without maintaining complex linked lists or timestamps. Operating system memory managers arrange physical frame descriptors in a circular logical buffer with a scanning hand pointer. Each frame descriptor includes a hardware-updated Reference Bit (Usage Bit). When a page fault occurs and a page must be evicted, the pointer inspects the current frame: if the reference bit is 1, the kernel clears the bit to 0 (granting a second chance) and advances the pointer; if the bit is 0, that frame is selected for immediate eviction.",
        "CLOCK (Second-Chance) page replacement algorithm and reference bit mechanics",
    )

    add(
        "sem_rsn_003",
        "databases",
        "en",
        "The ARIES (Algorithm for Recovery and Isolation Exploiting Semantics) crash recovery protocol restores database consistency following an unexpected system failure through three distinct phases: Analysis, REDO, and UNDO. During the Analysis phase, the recovery manager scans the Write-Ahead Log (WAL) forward from the last checkpoint to identify dirty buffer pages in memory and active uncommitted transactions. During the REDO phase, the system repeats history forward, reapplying all logged operations to bring disk state up to the exact moment of the crash. During the UNDO phase, the system scans the log backward, reversing the modifications of all active loser transactions that failed to commit prior to the crash, writing Compensation Log Records (CLRs) to prevent cascading rollbacks during repeated failures.",
        "ARIES database crash recovery protocol (Analysis, REDO, UNDO, CLRs)",
    )

    add(
        "sem_rsn_004",
        "networking",
        "en",
        "HPACK is the header compression standard designed specifically for HTTP/2 to prevent vulnerability to CRIME and BREACH compression side-channel attacks while drastically reducing HTTP header overhead. Unlike HTTP/1.1 where verbose ASCII header strings (e.g., User-Agent, Cookie, Accept) are retransmitted redundantly with every HTTP request, HPACK maintains two synchronized state tables between client and server: a Static Table containing 61 pre-indexed common HTTP headers, and a dynamic FIFO Table containing newly observed headers. Headers are encoded either as compact integer table indices or compressed using a static Huffman code table.",
        "HTTP/2 HPACK header compression, static/dynamic tables, and Huffman coding",
    )

    add(
        "sem_rsn_005",
        "security",
        "en",
        "The Diffie-Hellman Key Exchange (DHKE) protocol allows two communicating parties to establish a shared cryptographic secret over an insecure public channel without any prior shared secrets. Grounded in the computational hardness of the Discrete Logarithm Problem in finite cyclic groups, both parties agree upon a large prime modulus p and a generator base g. Alice chooses secret integer a and transmits A = g^a mod p; Bob chooses secret integer b and transmits B = g^b mod p. Alice computes s = B^a mod p and Bob computes s = A^b mod p, resulting in identical shared secret s = g^(ab) mod p, which is subsequently passed into a Key Derivation Function (HKDF) to derive symmetric AES session keys.",
        "Diffie-Hellman Key Exchange (DHKE) mathematical derivation and discrete log problem",
    )

    add(
        "sem_rsn_006",
        "hindi_linguistics",
        "hi",
        "कंप्यूटर विज्ञान में देवनागरी लिपि के पाठ प्रसंस्करण (Text Processing) के लिए यूनिकोड मानक (Unicode Standard) में 'देवनागरी ब्लॉक' (U+0900 से U+097F) समर्पित किया गया है। देवनागरी वर्णमाला का क्रम अत्यंत वैज्ञानिक है, जिसमें स्वरों (अ, आ, इ, ई, उ, ऊ, ऋ, ए, ऐ, ओ, औ) के उपरांत व्यंजनों को उनके उच्चारण स्थान के अनुसार पांच प्रमुख वर्गों में विभाजित किया गया है: कण्ठ्य (क-वर्ग), तालव्य (च-वर्ग), मूर्धन्य (ट-वर्ग), दन्त्य (त-वर्ग), और ओष्ठ्य (प-वर्ग)। इसके पश्चात अन्तःस्थ (य, र, ल, व) और ऊष्म (श, ष, स, ह) व्यंजन आते हैं। यह व्यवस्थित ध्वन्यात्मक वर्गीकरण प्राकृतिक भाषा प्रसंस्करण में उच्चारण नियमों और लिप्यंतरण (Transliteration) एल्गोरिदम को सहज बनाता है।",
        "Unicode Devanagari character block and phonetic categorization in Hindi",
    )

    add(
        "sem_rsn_007",
        "hinglish_discourse",
        "hinglish",
        "Micro-frontend architecture me large enterprise web applications ko independently deployable frontend modules me break kiya jata hai. Webpack 5 Module Federation use karke runtime pe remote micro-apps ko host shell me dynamically load kiya jata hai bina iframe overhead ke. Shared libraries (jaise React, React-DOM, design system UI components) ko singleton package specify kiya jata hai taaki duplicate JS bundles load na hon, aur cross-app communication ke liye browser CustomEvents ya shared event bus use kiye jaate hain.",
        "Micro-frontend architecture with Webpack Module Federation in Hinglish",
    )

    add(
        "sem_rsn_008",
        "programming",
        "en",
        "WebAssembly (WASM) is a low-level, binary instruction format designed as a portable compilation target for programming languages like C, C++, Rust, and Go, enabling near-native execution performance on the web. WASM executes within a memory-safe, sandboxed stack-based virtual machine embedded inside modern browser engines alongside the JavaScript runtime. WebAssembly modules share a contiguous Linear Memory array with JavaScript, allowing compute-intensive workloads (such as 3D graphics rendering, video encoding, cryptography, and client-side machine learning inference) to achieve deterministic high performance.",
        "WebAssembly (WASM) binary format, linear memory, and browser execution",
    )

    return samples
