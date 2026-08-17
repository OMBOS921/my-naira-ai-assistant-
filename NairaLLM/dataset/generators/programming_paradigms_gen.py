"""
Programming Language Paradigms & Concepts Domain Generator for Dataset A.
Generates comprehensive technical prose on compiler pipelines, type systems, memory management, functional vs OOP paradigms, and async execution.
"""

from __future__ import annotations

from typing import Any


def get_programming_paradigms_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "programming",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Programming language theory and runtime execution models",
            },
        })

    add(
        "sem_prog_001",
        "The compiler pipeline translates high-level source code into optimized machine instructions through distinct sequential phases. Lexical Analysis (scanning) converts raw character streams into a sequence of meaningful tokens (keywords, identifiers, operators). Syntax Analysis (parsing) organizes tokens into an Abstract Syntax Tree (AST) according to Context-Free Grammar (CFG) rules. Semantic Analysis verifies type compatibility, scope bindings, and identifier declarations. Intermediate Representation (IR) generation transforms the AST into target-independent intermediate code (such as LLVM IR or three-address code) for global dead code elimination and constant propagation optimizations before final target code generation.",
        "Compiler pipeline phases from Lexical Analysis to IR Code Generation",
    )

    add(
        "sem_prog_002",
        "Type systems in programming languages enforce invariants and prevent runtime type errors. Static type systems check type constraints at compile time, eliminating an entire category of runtime errors and enabling aggressive compiler optimizations (e.g., Rust, C++, Haskell). Dynamic type systems defer type checks to runtime, offering greater flexibility and rapid prototyping (e.g., Python, JavaScript). Nominal typing establishes type compatibility through explicit name declarations (Java classes), whereas Structural typing considers two types compatible if they share the same shape and method signatures (TypeScript interfaces, Go interfaces).",
        "Static vs Dynamic and Nominal vs Structural type systems",
    )

    add(
        "sem_prog_003",
        "Automatic memory management via Tracing Garbage Collection periodically scans the heap to identify and reclaim memory allocated to objects that are no longer reachable from root references (stack frames, global registers). The classic Mark-and-Sweep algorithm traverses the object graph starting from roots, setting a mark bit on live objects, and subsequently sweeping unmarked objects into a free list. Generational Garbage Collectors build upon the weak generational hypothesis—that most objects die young—by partitioning memory into Young (Eden/Survivor) and Old generations, collecting transient short-lived objects with lightweight minor GC cycles.",
        "Tracing garbage collection (Mark-and-Sweep, Generational GC)",
    )

    add(
        "sem_prog_004",
        "Functional programming (FP) treats computation as the evaluation of mathematical functions, avoiding mutable state and side effects. Pure functions produce identical outputs given identical inputs and cause no observable side effects (such as modifying global variables, performing I/O, or mutating argument structures). Immutability guarantees thread safety by design, eliminating race conditions in concurrent multithreaded execution. High-order functions accept other functions as arguments or return them as values (map, filter, fold/reduce), enabling declarative data transformation pipelines.",
        "Functional programming principles (Purity, Immutability, Higher-Order Functions)",
    )

    add(
        "sem_prog_005",
        "Coroutines and the async/await syntax provide cooperative multitasking within a single thread. When an asynchronous function awaits an uncompleted non-blocking operation (such as a database query or network socket read), the compiler transforms the coroutine into a state machine. The state machine saves local variable frame state and yields control back to the central event loop, which immediately schedules other pending tasks. Once the awaited I/O completes, the event loop resumes the coroutine from its exact suspension point without the heavy overhead of OS thread context switching.",
        "Coroutines, async-await state machines, and event loop mechanics",
    )

    add(
        "sem_prog_006",
        "Rust's ownership and borrowing model achieves memory safety without a garbage collector. Every value in Rust has a single owner variable; when the owner goes out of scope, the memory is automatically dropped. Values can be borrowed via immutable references (&T, multiple allowed simultaneously) or mutable references (&mut T, only one allowed at a time). The compile-time Borrow Checker strictly enforces that mutable borrows are mutually exclusive with all other borrows, mathematically preventing data races and dangling pointer bugs at compile time.",
        "Rust ownership, borrowing rules, and compile-time Borrow Checker",
    )

    add(
        "sem_prog_007",
        "Monads in functional programming provide a formalized algebraic structure for encapsulating side effects, handling errors, and composing sequential computations. A Monad defines a type constructor and two fundamental operations: `return` (or `unit`, which lifts a plain value into the monadic context) and `bind` (`>>=`, which chains a function producing a monadic value onto an existing monadic value). Classic monads include Maybe/Option (encapsulating potential null absence without NullPointerExceptions), Either/Result (encapsulating success or detailed error payloads), and IO (sequencing side-effecting operations pure functionally).",
        "Monads in functional programming (Option, Result, IO)",
    )

    add(
        "sem_prog_008",
        "Just-In-Time (JIT) compilation combines the rapid startup of interpreters with the raw execution speed of ahead-of-time compiled native machine code. In virtual machines like V8 and Java HotSpot, an interpreter initially executes bytecode while lightweight profiling counters track hot execution paths (frequently called functions and loops). When an execution counter exceeds a predefined threshold, the JIT tier compiles the bytecode into highly optimized native CPU machine code, applying speculative inline caching, loop unrolling, and method devirtualization.",
        "Just-In-Time (JIT) compilation tiers and inline caching in V8/JVM",
    )

    return samples
