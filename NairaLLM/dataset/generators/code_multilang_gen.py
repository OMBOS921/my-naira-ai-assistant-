"""
Multi-Language Code Snippets & Architecture Domain Generator for Dataset A.
Generates valid code implementations across Python, JavaScript, TypeScript, C, SQL, HTML/CSS, and Shell.
"""

from __future__ import annotations

from typing import Any


def get_code_multilang_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Multi-language code snippet and implementation pattern",
            },
        })

    add(
        "sem_code_005",
        """```python
import asyncio
from typing import AsyncIterator, TypeVar

T = TypeVar("T")

async def batch_stream(
    async_iterator: AsyncIterator[T],
    batch_size: int,
) -> AsyncIterator[list[T]]:
    \"\"\"Yield batches of items from an asynchronous stream.\"\"\"
    batch: list[T] = []
    async for item in async_iterator:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch
```
This Python async generator utility partitions an incoming asynchronous data stream into fixed-size chunks, reducing processing overhead for bulk database writes and network transmissions.""",
        "Python asynchronous stream batching generator",
    )

    add(
        "sem_code_006",
        """```typescript
interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

export class TTLCache<K, V> {
  private store = new Map<K, CacheEntry<V>>();

  constructor(private readonly defaultTtlMs: number = 60000) {}

  set(key: K, value: V, ttlMs?: number): void {
    const expiresAt = Date.now() + (ttlMs ?? this.defaultTtlMs);
    this.store.set(key, { value, expiresAt });
  }

  get(key: K): V | undefined {
    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return undefined;
    }
    return entry.value;
  }
}
```
This TypeScript generic class implements an in-memory cache with Time-To-Live (TTL) automatic expiration and strong type safety.""",
        "TypeScript generic in-memory TTL cache implementation",
    )

    add(
        "sem_code_007",
        """```c
#include <stdio.h>
#include <stdlib.h>

typedef struct Node {
    int data;
    struct Node* next;
} Node;

Node* push_front(Node* head, int new_data) {
    Node* new_node = (Node*)malloc(sizeof(Node));
    if (new_node == NULL) {
        perror("Memory allocation failed");
        exit(EXIT_FAILURE);
    }
    new_node->data = new_data;
    new_node->next = head;
    return new_node;
}

void free_list(Node* head) {
    Node* current = head;
    while (current != NULL) {
        Node* temp = current->next;
        free(current);
        current = temp;
    }
}
```
This C program defines a dynamic singly-linked list with manual heap memory allocation via malloc and recursive pointer traversal deallocation via free.""",
        "C singly-linked list with manual dynamic memory allocation",
    )

    add(
        "sem_code_008",
        """```sql
WITH monthly_revenue AS (
    SELECT
        DATE_TRUNC('month', created_at) AS order_month,
        user_id,
        SUM(amount_cents) AS total_spent
    FROM orders
    WHERE status = 'completed'
    GROUP BY DATE_TRUNC('month', created_at), user_id
),
ranked_customers AS (
    SELECT
        order_month,
        user_id,
        total_spent,
        DENSE_RANK() OVER (
            PARTITION BY order_month 
            ORDER BY total_spent DESC
        ) as revenue_rank
    FROM monthly_revenue
)
SELECT 
    order_month,
    user_id,
    total_spent / 100.0 AS revenue_usd,
    revenue_rank
FROM ranked_customers
WHERE revenue_rank <= 3
ORDER BY order_month DESC, revenue_rank ASC;
```
This PostgreSQL query utilizes Common Table Expressions (CTEs) and the DENSE_RANK() window function to calculate top 3 revenue-generating users per month.""",
        "SQL window functions, Common Table Expressions (CTE), and analytical rankings",
    )

    add(
        "sem_code_009",
        """```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>System Performance Dashboard</title>
  <style>
    :root { --bg: #0f172a; --card: #1e293b; --accent: #38bdf8; --text: #f8fafc; }
    body { margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); padding: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }
    .metric-card { background: var(--card); border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
    .metric-value { font-size: 2rem; font-weight: 700; color: var(--accent); margin-top: 0.5rem; }
  </style>
</head>
<body>
  <main class="grid">
    <section class="metric-card">
      <h2>CPU Utilization</h2>
      <div class="metric-value">42.8%</div>
    </section>
  </main>
</body>
</html>
```
This HTML5 and CSS snippet demonstrates semantic page layout, CSS Custom Properties (variables), and responsive CSS Grid design for dark-themed operational dashboards.""",
        "HTML5 semantic layout and CSS Grid responsive dashboard styling",
    )

    add(
        "sem_code_010",
        """```bash
#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="/var/log/naira-os"
BACKUP_DIR="/mnt/backups/logs"
RETENTION_DAYS=14
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "Starting automated log compression for ${LOG_DIR} at ${TIMESTAMP}"
mkdir -p "${BACKUP_DIR}"

# Find, archive, and compress logs older than 1 day
find "${LOG_DIR}" -type f -name "*.log" -mtime +1 | while read -r log_file; do
    base_name=$(basename "${log_file}")
    tar_dest="${BACKUP_DIR}/${base_name}_${TIMESTAMP}.tar.gz"
    echo "Archiving ${log_file} -> ${tar_dest}"
    tar -czf "${tar_dest}" "${log_file}" && rm -f "${log_file}"
done

# Prune archives older than retention threshold
find "${BACKUP_DIR}" -type f -name "*.tar.gz" -mtime "+${RETENTION_DAYS}" -exec rm -f {} +
echo "Log maintenance routine completed successfully."
```
This production-grade Bash automation script uses `set -euo pipefail` strict mode, parameterized variables, and file find pipelines for log rotation and archive pruning.""",
        "Bash shell automation script with strict error handling and log pruning",
    )

    return samples
