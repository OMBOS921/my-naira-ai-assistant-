"""
Software Engineering & Design Patterns Domain Generator for Dataset A.
Generates comprehensive technical prose on SOLID design principles, Clean Architecture, Domain-Driven Design, microservices, and design patterns.
"""

from __future__ import annotations

from typing import Any


def get_software_engineering_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "software_engineering",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Software engineering principles and architectural patterns exposition",
            },
        })

    add(
        "sem_swe_001",
        "The SOLID principles establish foundational guidelines for maintainable object-oriented software design. Single Responsibility Principle (SRP) states that a class should have only one reason to change. Open/Closed Principle (OCP) requires software entities to be open for extension but closed for modification. Liskov Substitution Principle (LSP) dictates that derived classes must be substitutable for their base types without altering program correctness. Interface Segregation Principle (ISP) prevents clients from depending on interfaces they do not use. Dependency Inversion Principle (DIP) mandates that high-level business modules must depend on abstractions rather than low-level concrete implementations.",
        "SOLID principles detailed technical breakdown",
    )

    add(
        "sem_swe_002",
        "Hexagonal Architecture (Ports and Adapters), pioneered by Alistair Cockburn, isolates core domain business logic from external delivery mechanisms, infrastructure frameworks, and databases. The core domain defines inbound Ports (interfaces through which external use-case drivers interact with the application) and outbound Ports (interfaces through which the application queries persistence or external messaging services). Adapters wrap specific technologies (such as HTTP REST controllers, CLI interfaces, PostgreSQL database repositories, or Kafka event consumers), ensuring the core domain remains completely technology-agnostic and unit-testable.",
        "Hexagonal Architecture (Ports and Adapters) decoupling",
    )

    add(
        "sem_swe_003",
        "Domain-Driven Design (DDD) aligns software architecture directly with real-world business domains and complex domain terminology. Central concepts include the Ubiquitous Language (a shared, rigorous vocabulary co-created by domain experts and developers), Bounded Contexts (explicit conceptual boundaries within which a domain model possesses singular, unambiguous meaning), Entities (objects defined by their persistent identity rather than attributes), Value Objects (immutable descriptors possessing no conceptual identity), and Aggregates (clusters of associated objects treated as a single transactional unit with a designated Aggregate Root).",
        "Domain-Driven Design (DDD) concepts: Aggregates, Entities, Bounded Contexts",
    )

    add(
        "sem_swe_004",
        "The Twelve-Factor App methodology provides best practices for building scalable, cloud-native Software-as-a-Service applications. Key tenets include: maintaining one codebase tracked in revision control with multiple deployments (I. Codebase); explicitly declaring and isolating dependencies via package manifests (II. Dependencies); storing configuration in the runtime environment rather than checking credentials into source code (III. Config); treating backing services such as databases, caches, and message queues as attached resources (IV. Backing services); and maintaining strict separation between build, release, and run stages (V. Build, release, run).",
        "Twelve-Factor App methodology for cloud-native software",
    )

    add(
        "sem_swe_005",
        "Design patterns provide battle-tested solutions to recurring software engineering design challenges. Creational patterns (such as Factory Method, Abstract Factory, and Builder) decouple object instantiation logic from client code. Structural patterns (such as Adapter, Decorator, and Facade) compose classes and objects into larger, flexible structures while maintaining clear boundaries. Behavioral patterns (such as Strategy, Observer, Command, and State) define flexible communication protocols and dynamic algorithmic delegation between collaborating runtime objects.",
        "GoF design pattern taxonomy (Creational, Structural, Behavioral)",
    )

    add(
        "sem_swe_006",
        "Test-Driven Development (TDD) is an iterative software development technique structured around a tight 'Red-Green-Refactor' cycle. A developer initially writes an automated unit test specifying a single discrete requirement before writing any production code; the test fails (Red). Next, the developer writes the minimal production code necessary to satisfy the test condition (Green). Finally, the developer refactors the implementation to eliminate code duplication, improve naming, and enhance structure while continuously running the test suite to guarantee regression freedom.",
        "Test-Driven Development (TDD) Red-Green-Refactor methodology",
    )

    add(
        "sem_swe_007",
        "Continuous Integration and Continuous Deployment (CI/CD) automates the integration of code changes from multiple developers into a single shared repository. In CI, every commit triggers automated linting, security vulnerability scanning, and unit/integration test suites to identify integration defects immediately. In CD, verified artifacts that successfully pass all pipeline quality gates are automatically packaged into immutable container images and deployed progressively (via Canary or Blue-Green deployment strategies) to staging and production environments.",
        "CI/CD automated pipeline architecture and Blue-Green deployments",
    )

    add(
        "sem_swe_008",
        "The Saga pattern manages distributed transactions across multiple microservices without requiring blocking two-phase commits. A Saga consists of a sequence of local transactions where each service updates its internal database and publishes an event or message to trigger the next transaction in the chain. If a local transaction fails due to business rule violations or technical faults, the Saga orchestrator or choreography network executes a series of compensating transactions in reverse order to undo changes and restore data consistency.",
        "Saga pattern for distributed transactions and compensating workflows",
    )

    return samples
