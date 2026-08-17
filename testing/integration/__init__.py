from typing import Any
"""
Integration tests — verify wiring between modules.

21_System_Contracts.md §23.5:
- Test the wiring between modules (e.g., Any Manager → Memory Adapter).
- Test the full Mediator path (CLI input → Orchestrator → LLM Manager → response).
- May perform real I/O to a test database (``testing/test_data/``).
- Must not call external LLM APIs. Use a mock provider.
"""

from __future__ import annotations
