"""
Expanded Structured Data & JSON Domain Generator for Dataset A.
Generates comprehensive valid JSON payloads covering Kubernetes specs, OpenAPI paths, database execution plans, and configuration manifests.
"""

from __future__ import annotations

import json
from typing import Any


def get_structured_expanded_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Expanded structured JSON payload and schema specification",
            },
        })

    add(
        "sem_json_009",
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "naira-inference-gateway",
                "namespace": "production",
                "labels": {
                    "app.kubernetes.io/name": "inference-gateway",
                    "app.kubernetes.io/part-of": "naira-os-platform",
                    "app.kubernetes.io/version": "1.5.0",
                },
            },
            "spec": {
                "replicas": 4,
                "selector": {
                    "matchLabels": {
                        "app.kubernetes.io/name": "inference-gateway"
                    }
                },
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {
                        "maxSurge": "25%",
                        "maxUnavailable": 0,
                    },
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/name": "inference-gateway"
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "gateway",
                                "image": "registry.naira-os.org/core/gateway:v1.5.0",
                                "ports": [{"containerPort": 8080, "protocol": "TCP"}],
                                "resources": {
                                    "requests": {"cpu": "1000m", "memory": "2Gi"},
                                    "limits": {"cpu": "4000m", "memory": "8Gi"},
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/health/ready", "port": 8080},
                                    "initialDelaySeconds": 10,
                                    "periodSeconds": 5,
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health/live", "port": 8080},
                                    "initialDelaySeconds": 15,
                                    "periodSeconds": 10,
                                },
                            }
                        ]
                    },
                },
            },
        },
        "Kubernetes Deployment specification JSON representation",
    )

    add(
        "sem_json_010",
        {
            "openapi": "3.0.3",
            "info": {
                "title": "Naira OS Device Control API",
                "version": "1.5.0",
                "description": "RESTful endpoints for querying and controlling host operating system resources.",
            },
            "paths": {
                "/api/v1/system/battery": {
                    "get": {
                        "summary": "Retrieve battery state and charging telemetry",
                        "operationId": "getBatteryState",
                        "responses": {
                            "200": {
                                "description": "Battery telemetry retrieved successfully",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "percentage": {"type": "number", "minimum": 0, "maximum": 100},
                                                "is_charging": {"type": "boolean"},
                                                "time_remaining_minutes": {"type": "integer", "nullable": True},
                                                "health_status": {"type": "string", "enum": ["good", "degraded", "critical"]},
                                            },
                                            "required": ["percentage", "is_charging", "health_status"],
                                        }
                                    }
                                },
                            }
                        },
                    }
                }
            },
        },
        "OpenAPI 3.0 path schema definition for system battery status",
    )

    add(
        "sem_json_011",
        {
            "name": "naira-os-core",
            "version": "1.5.0",
            "private": True,
            "type": "module",
            "scripts": {
                "dev": "vite dev --port 3000",
                "build": "tsc && vite build",
                "preview": "vite preview",
                "test": "vitest run --coverage",
                "lint": "eslint . --ext .ts,.tsx --max-warnings 0",
            },
            "dependencies": {
                "@tanstack/react-query": "^5.28.0",
                "clsx": "^2.1.0",
                "lucide-react": "^0.359.0",
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "zustand": "^4.5.2",
            },
            "devDependencies": {
                "@types/node": "^20.11.24",
                "@types/react": "^18.2.61",
                "@vitejs/plugin-react": "^4.2.1",
                "typescript": "^5.3.3",
                "vite": "^5.1.4",
                "vitest": "^1.3.1",
            },
        },
        "Node.js package.json project manifest and dependency map",
    )

    add(
        "sem_json_012",
        {
            "Plan": {
                "Node Type": "Hash Join",
                "Parallel Aware": False,
                "Async Capable": False,
                "Join Type": "Inner",
                "Startup Cost": 42.50,
                "Total Cost": 1842.10,
                "Plan Rows": 850,
                "Plan Width": 64,
                "Actual Startup Time": 0.412,
                "Actual Total Time": 8.914,
                "Actual Rows": 834,
                "Actual Loops": 1,
                "Hash Cond": "(orders.customer_id = customers.id)",
                "Plans": [
                    {
                        "Node Type": "Seq Scan",
                        "Parent Relationship": "Outer",
                        "Relation Name": "orders",
                        "Alias": "orders",
                        "Startup Cost": 0.00,
                        "Total Cost": 980.00,
                        "Plan Rows": 12500,
                        "Plan Width": 32,
                        "Actual Rows": 12500,
                        "Filter": "(created_at >= '2026-01-01'::date)",
                        "Rows Removed by Filter": 3400,
                    },
                    {
                        "Node Type": "Hash",
                        "Parent Relationship": "Inner",
                        "Startup Cost": 25.00,
                        "Total Cost": 25.00,
                        "Plan Rows": 1400,
                        "Plan Width": 32,
                        "Actual Rows": 1400,
                        "Plans": [
                            {
                                "Node Type": "Index Scan",
                                "Relation Name": "customers",
                                "Index Name": "customers_pkey",
                                "Startup Cost": 0.28,
                                "Total Cost": 25.00,
                                "Actual Rows": 1400,
                            }
                        ],
                    },
                ],
            }
        },
        "PostgreSQL EXPLAIN (ANALYZE, FORMAT JSON) query plan output",
    )

    return samples
