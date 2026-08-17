"""
Expanded Multi-Language Code Implementations Domain Generator for Dataset A.
Generates comprehensive code implementations across Python, TypeScript, C, SQL, and Go.
"""

from __future__ import annotations

from typing import Any


def get_code_expanded_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Expanded multi-language implementation pattern",
            },
        })

    add(
        "sem_code_011",
        """```python
from collections import OrderedDict
from typing import Generic, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")

class LRUCache(Generic[K, V]):
    \"\"\"Least Recently Used (LRU) Cache with O(1) operations.\"\"\"

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.cache: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> Optional[V]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: K, value: V) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
```
This Python generic class implements an LRU Cache in O(1) time using a doubly-linked hash map (`OrderedDict`). When capacity is exceeded, the least recently accessed item at the front is evicted.""",
        "Python generic LRU Cache implementation with OrderedDict",
    )

    add(
        "sem_code_012",
        """```typescript
import { z } from "zod";

export const DatabaseConfigSchema = z.object({
  host: z.string().min(1),
  port: z.number().int().min(1024).max(65535).default(5432),
  database: z.string().min(1),
  user: z.string().min(1),
  password: z.string().min(8),
  ssl: z.boolean().default(true),
  poolSize: z.number().int().min(1).max(100).default(10),
});

export type DatabaseConfig = z.infer<typeof DatabaseConfigSchema>;

export function parseDatabaseConfig(env: Record<string, unknown>): DatabaseConfig {
  const result = DatabaseConfigSchema.safeParse(env);
  if (!result.success) {
    const errorDetails = result.error.format();
    throw new Error(`Invalid Database Configuration: ${JSON.stringify(errorDetails)}`);
  }
  return result.data;
}
```
This TypeScript module demonstrates runtime environment variable validation and static type inference using the Zod schema validation library.""",
        "TypeScript Zod schema validation and static type inference",
    )

    add(
        "sem_code_013",
        """```c
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

typedef struct {
    int* data;
    size_t size;
    size_t capacity;
} Vector;

Vector* vector_create(size_t initial_capacity) {
    Vector* vec = (Vector*)malloc(sizeof(Vector));
    vec->size = 0;
    vec->capacity = initial_capacity > 0 ? initial_capacity : 4;
    vec->data = (int*)malloc(vec->capacity * sizeof(int));
    return vec;
}

void vector_push_back(Vector* vec, int value) {
    if (vec->size == vec->capacity) {
        vec->capacity *= 2;
        vec->data = (int*)realloc(vec->data, vec->capacity * sizeof(int));
    }
    vec->data[vec->size++] = value;
}

void vector_free(Vector* vec) {
    if (vec != NULL) {
        free(vec->data);
        free(vec);
    }
}
```
This C implementation demonstrates a dynamic array (Vector) with geometric capacity doubling using `realloc` for amortized O(1) append operations.""",
        "C dynamic array vector implementation with geometric doubling",
    )

    add(
        "sem_code_014",
        """```sql
WITH RECURSIVE org_hierarchy AS (
    -- Anchor member: select the CEO / top-level executive
    SELECT 
        employee_id, 
        manager_id, 
        full_name, 
        job_title, 
        1 AS depth_level,
        ARRAY[employee_id] AS path
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    -- Recursive member: select direct reports of current depth
    SELECT 
        e.employee_id, 
        e.manager_id, 
        e.full_name, 
        e.job_title, 
        h.depth_level + 1,
        h.path || e.employee_id
    FROM employees e
    INNER JOIN org_hierarchy h ON e.manager_id = h.employee_id
)
SELECT 
    depth_level,
    REPEAT('  ', depth_level - 1) || full_name AS indented_name,
    job_title,
    path
FROM org_hierarchy
ORDER BY path;
```
This recursive SQL query traverses hierarchical organization trees using Common Table Expressions (CTEs), tracking traversal depth and ancestry paths.""",
        "Recursive SQL CTE query for organizational hierarchy traversal",
    )

    return samples
