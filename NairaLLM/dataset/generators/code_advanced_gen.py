"""
Advanced Code & Architecture Domain Generator for Dataset A.
Generates comprehensive code implementations across Rust, Go, Python, and C++ with detailed architectural explanations.
"""

from __future__ import annotations

from typing import Any


def get_code_advanced_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Advanced multi-language systems code pattern",
            },
        })

    add(
        "sem_code_015",
        """```rust
use std::sync::{Arc, Mutex};
use std::thread;

struct ThreadSafeCounter {
    count: Arc<Mutex<u64>>,
}

impl ThreadSafeCounter {
    fn new() -> Self {
        Self { count: Arc::new(Mutex::new(0)) }
    }

    fn increment(&self) {
        let mut num = self.count.lock().unwrap();
        *num += 1;
    }

    fn get(&self) -> u64 {
        *self.count.lock().unwrap()
    }
}
```
This Rust pattern implements thread-safe state sharing using `Arc` (Atomically Reference Counted pointer) and `Mutex` (mutual exclusion lock) across concurrent OS threads with zero data races.""",
        "Rust Arc and Mutex concurrent state management pattern",
    )

    add(
        "sem_code_016",
        """```go
package main

import (
	"context"
	"fmt"
	"time"
)

func worker(ctx context.Context, id int, jobs <-chan int, results chan<- int) {
	for {
		select {
		case <-ctx.Done():
			fmt.Printf("Worker %d exiting: %v\\n", id, ctx.Err())
			return
		case job, ok := <-jobs:
			if !ok {
				return
			}
			// Process job
			results <- job * job
		}
	}
}
```
This Go implementation demonstrates a concurrent Worker Pool pattern with `context.Context` cancellation propagation and directional channels for graceful shutdown and backpressure control.""",
        "Go worker pool with context cancellation and directional channels",
    )

    add(
        "sem_code_017",
        """```python
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

@runtime_checkable
class Serializer(Protocol):
    \"\"\"Structural Protocol for JSON and Binary serializers.\"\"\"
    def serialize(self, data: dict) -> bytes:
        ...
    def deserialize(self, payload: bytes) -> dict:
        ...

class EventPublisher(ABC):
    \"\"\"Abstract Base Class for message brokers.\"\"\"
    @abstractmethod
    def publish(self, topic: str, message: bytes) -> bool:
        pass
```
This Python snippet contrasts structural typing via `typing.Protocol` (duck typing with static verification) against nominal subtyping using `abc.ABC` abstract base classes.""",
        "Python typing.Protocol structural typing vs abc.ABC nominal subtyping",
    )

    add(
        "sem_code_018",
        """```cpp
#include <iostream>
#include <memory>

class Resource {
public:
    Resource() { std::cout << "Resource acquired\\n"; }
    ~Resource() { std::cout << "Resource released automatically\\n"; }
    void execute() { std::cout << "Executing resource task\\n"; }
};

void process_task() {
    // RAII guarantees destructor execution even if an exception is thrown
    std::unique_ptr<Resource> res = std::make_unique<Resource>();
    res->execute();
}
```
This modern C++ implementation demonstrates the RAII (Resource Acquisition Is Initialization) idiom using `std::unique_ptr` smart pointers for deterministic zero-leak memory management.""",
        "Modern C++ RAII idiom and std::unique_ptr smart pointers",
    )

    return samples
