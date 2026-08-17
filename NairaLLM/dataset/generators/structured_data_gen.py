"""
Structured Data & JSON Formats Domain Generator for Dataset A.
Generates comprehensive, diverse, valid JSON schemas, API responses, configuration objects, telemetry payloads, and metadata definitions.
"""

from __future__ import annotations

import json
from typing import Any


def get_structured_data_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, payload: dict[str, Any], notes: str = "") -> None:
        formatted_json = json.dumps(payload, indent=2, ensure_ascii=False)
        samples.append({
            "id": sample_id,
            "domain": "structured_data",
            "language": "en",
            "text": formatted_json.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Valid structured JSON schema and payload specification",
            },
        })

    add(
        "sem_json_003",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "UserProfile",
            "type": "object",
            "required": ["user_id", "email", "created_at", "roles"],
            "properties": {
                "user_id": {"type": "string", "format": "uuid"},
                "username": {"type": "string", "minLength": 3, "maxLength": 30},
                "email": {"type": "string", "format": "email"},
                "is_active": {"type": "boolean", "default": True},
                "roles": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["admin", "editor", "viewer"]},
                    "uniqueItems": True,
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "last_login_ip": {"type": "string", "format": "ipv4"},
                        "two_factor_enabled": {"type": "boolean"},
                    },
                },
            },
        },
        "JSON Schema specification for UserProfile entity",
    )

    add(
        "sem_json_004",
        {
            "status": "success",
            "code": 200,
            "pagination": {
                "page": 1,
                "per_page": 20,
                "total_records": 1420,
                "total_pages": 71,
                "has_next_page": True,
                "has_prev_page": False,
            },
            "data": [
                {
                    "item_id": "item_90214",
                    "sku": "SSD-NVME-2TB",
                    "name": "UltraSpeed 2TB PCIe 4.0 NVMe M.2 SSD",
                    "price_cents": 14999,
                    "currency": "USD",
                    "in_stock": True,
                    "inventory_count": 84,
                    "tags": ["storage", "pcie4", "nvme", "hardware"],
                    "rating": 4.85,
                },
                {
                    "item_id": "item_90215",
                    "sku": "RAM-DDR5-32GB",
                    "name": "Performance 32GB (2x16GB) DDR5-6000 RAM",
                    "price_cents": 11999,
                    "currency": "USD",
                    "in_stock": True,
                    "inventory_count": 42,
                    "tags": ["memory", "ddr5", "hardware"],
                    "rating": 4.92,
                },
            ],
            "timestamp": "2026-08-16T14:30:00Z",
        },
        "REST API paginated catalog response payload",
    )

    add(
        "sem_json_005",
        {
            "server": {
                "host": "0.0.0.0",
                "port": 8080,
                "tls": {
                    "enabled": True,
                    "cert_file": "/etc/ssl/certs/server.crt",
                    "key_file": "/etc/ssl/private/server.key",
                    "min_version": "TLSv1.3",
                    "ciphers": [
                        "TLS_AES_256_GCM_SHA384",
                        "TLS_CHACHA20_POLY1305_SHA256",
                    ],
                },
                "timeouts": {
                    "read_timeout_seconds": 15,
                    "write_timeout_seconds": 30,
                    "idle_timeout_seconds": 120,
                },
            },
            "database": {
                "connection_pool": {
                    "max_connections": 50,
                    "min_idle": 10,
                    "max_lifetime_minutes": 30,
                    "connection_timeout_ms": 5000,
                },
                "replica_nodes": [
                    {"host": "db-replica-01.internal", "port": 5432, "weight": 100},
                    {"host": "db-replica-02.internal", "port": 5432, "weight": 100},
                ],
            },
            "telemetry": {
                "prometheus_metrics_enabled": True,
                "otlp_endpoint": "http://otel-collector.monitoring:4317",
                "sample_rate": 0.1,
            },
        },
        "Server and database connection pool configuration file",
    )

    add(
        "sem_json_006",
        {
            "event_id": "evt_998124_webhook",
            "event_type": "payment.transaction.settled",
            "attempt": 1,
            "created_at": 1786968000,
            "payload": {
                "transaction_id": "txn_88412_card",
                "amount": 4500,
                "currency": "usd",
                "customer": {
                    "id": "cust_33214",
                    "name": "Sarah Jenkins",
                    "email": "sarah.j@example.com",
                },
                "payment_method": {
                    "type": "card",
                    "brand": "visa",
                    "last4": "4242",
                    "exp_month": 12,
                    "exp_year": 2028,
                },
                "fee_details": {
                    "gateway_fee": 161,
                    "net_amount": 4339,
                },
                "refunded": False,
            },
        },
        "Webhook payment transaction settled event payload",
    )

    add(
        "sem_json_007",
        {
            "timestamp": "2026-08-16T14:35:12.891Z",
            "level": "ERROR",
            "service": "order-fulfillment-service",
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "span_id": "00f067aa0ba902b7",
            "error": {
                "type": "InventoryReservationException",
                "message": "Insufficient stock for SKU 'GPU-RTX-5090' (Requested: 1, Available: 0)",
                "code": "ERR_INSUFFICIENT_STOCK",
                "retryable": False,
                "stack_trace": [
                    "at InventoryManager.reserveStock(inventory_manager.py:142)",
                    "at OrderPipeline.processOrder(order_pipeline.py:88)",
                    "at RouteHandler.handlePost(routes.py:34)",
                ],
            },
            "context": {
                "order_id": "ord_77192",
                "user_id": "usr_55019",
                "warehouse_id": "wh_us_east_1",
            },
        },
        "Structured JSON error log with OpenTelemetry distributed trace context",
    )

    add(
        "sem_json_008",
        {
            "node_metrics": {
                "hostname": "k8s-worker-node-04",
                "ip_address": "10.240.0.14",
                "uptime_seconds": 1842910,
                "cpu": {
                    "cores": 32,
                    "usage_percent": 44.8,
                    "load_average": [14.2, 12.8, 11.5],
                    "temperature_celsius": 52.4,
                },
                "memory": {
                    "total_bytes": 137438953472,
                    "used_bytes": 68719476736,
                    "free_bytes": 68719476736,
                    "swap_total_bytes": 17179869184,
                    "swap_used_bytes": 0,
                    "utilization_percent": 50.0,
                },
                "disk": [
                    {
                        "mount": "/",
                        "device": "/dev/nvme0n1p2",
                        "total_gb": 1024,
                        "used_gb": 412,
                        "available_gb": 612,
                        "use_percent": 40.2,
                    }
                ],
                "network": {
                    "rx_bytes_per_sec": 84920140,
                    "tx_bytes_per_sec": 124902100,
                    "dropped_packets": 0,
                },
            }
        },
        "Node telemetry diagnostic metrics JSON specification",
    )

    return samples
