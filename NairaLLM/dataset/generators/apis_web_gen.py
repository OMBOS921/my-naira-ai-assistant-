"""
APIs, HTTP Protocols, & Web Technologies Domain Generator for Dataset A.
Generates comprehensive technical prose on REST conventions, GraphQL, WebSockets, browser rendering engines, and API security.
"""

from __future__ import annotations

from typing import Any


def get_apis_web_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "apis_http",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "API design, HTTP protocols, and web browser engineering",
            },
        })

    add(
        "sem_api_001",
        "Representational State Transfer (REST) is an architectural style for distributed hypermedia systems defined by Roy Fielding. RESTful APIs adhere to six core architectural constraints: Client-Server separation of concerns, Statelessness (each request from client to server must contain all contextual information necessary to understand and process the request), Cacheability (responses must explicitly declare whether they are cacheable), Uniform Interface (identification of resources via URIs, manipulation of resources through representations, self-descriptive messages, and HATEOAS), Layered System architecture, and optional Code on Demand.",
        "REST architectural constraints and Fielding design principles",
    )

    add(
        "sem_api_002",
        "HTTP status codes are three-digit integers grouped into five semantic classes communicating the outcome of an HTTP request. 1xx informational responses indicate request receipt. 2xx successful responses include 200 OK (standard success), 201 Created (resource creation with Location header), and 204 No Content (action succeeded with empty payload). 3xx redirection codes include 301 Moved Permanently and 304 Not Modified (conditional GET cache hit). 4xx client errors include 400 Bad Request (syntax/validation failure), 401 Unauthorized (missing authentication), 403 Forbidden (authenticated but lacking permission), 404 Not Found, and 429 Too Many Requests. 5xx server errors include 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, and 504 Gateway Timeout.",
        "HTTP status codes semantics across 1xx, 2xx, 3xx, 4xx, 5xx classes",
    )

    add(
        "sem_api_003",
        "GraphQL is a declarative query language and runtime for APIs developed by Facebook. Unlike REST APIs where endpoints return fixed data structures requiring multiple network roundtrips (under-fetching) or returning superfluous data (over-fetching), GraphQL allows clients to define the exact shape and nested fields of the data they require in a single query. The backend GraphQL engine parses the query AST against a strongly typed Schema Definition Language (SDL) and executes modular resolver functions to fulfill data graphs efficiently.",
        "GraphQL declarative querying, schemas, and resolver execution",
    )

    add(
        "sem_api_004",
        "Web browser rendering engines (such as Chromium Blink and WebKit) translate HTML, CSS, and JavaScript into interactive visual pixels through a deterministic rendering pipeline. The parser processes raw HTML bytes to construct the Document Object Model (DOM) tree while simultaneously parsing CSS stylesheets to build the CSS Object Model (CSSOM) tree. Combining the DOM and CSSOM produces the Render Tree, containing only visually active nodes. The Layout (Reflow) stage calculates the exact geometric coordinates and bounding boxes of every element, followed by the Paint stage which converts vector geometry into bitmap pixels, and the Compositing stage which layers GPU textures for screen display.",
        "Browser rendering pipeline (DOM, CSSOM, Render Tree, Layout, Paint, Composite)",
    )

    add(
        "sem_api_005",
        "Cross-Origin Resource Sharing (CORS) is a security mechanism enforced by web browsers that restricts cross-origin HTTP requests initiated from scripts. When a web application on `https://client.example.com` attempts to fetch data from `https://api.external.com`, the browser automatically executes a CORS preflight check using the HTTP OPTIONS method with `Access-Control-Request-Method` and `Origin` headers. The server must respond with appropriate `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, and `Access-Control-Allow-Headers` headers before the actual request is permitted.",
        "CORS security mechanism, preflight OPTIONS checks, and response headers",
    )

    add(
        "sem_api_006",
        "API idempotency ensures that executing an identical request multiple times produces the exact identical server state as executing it once. In HTTP semantics, GET, PUT, and DELETE methods are defined as idempotent by specification, whereas POST is non-idempotent because consecutive requests create distinct new resources. For critical financial or payment APIs, servers implement Idempotency-Key request headers: the server caches the result of the initial operation keyed by the UUID and returns the cached response upon detecting duplicate submissions.",
        "HTTP method idempotency and Idempotency-Key headers in financial APIs",
    )

    add(
        "sem_api_007",
        "Webhooks provide an asynchronous, push-based communication pattern where a server sends an HTTP POST payload to an external client's configured webhook URL whenever a specific business event occurs (such as payment completion or repository push). To guarantee payload integrity and authenticity, webhook providers compute a cryptographic HMAC signature of the JSON payload body using a shared secret key (e.g., using SHA-256) and attach the signature in a header such as `X-Hub-Signature-256`, enabling the receiver to verify the payload before processing.",
        "Webhook push architecture and HMAC SHA-256 signature verification",
    )

    add(
        "sem_api_008",
        "OpenAPI Specification (formerly Swagger) provides a standardized, language-agnostic interface description format for RESTful APIs. Written in YAML or JSON, an OpenAPI 3.0 document defines API base servers, path endpoints, supported HTTP operations, parameter schemas (path, query, header, cookie), request bodies, response status codes with JSON schema schemas, and security schemes (Bearer JWT, OAuth2, API Keys), enabling automated client SDK generation, interactive documentation, and contract testing.",
        "OpenAPI 3.0 specification format and automated client generation",
    )

    return samples
