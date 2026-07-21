"""
Unit tests — mirror the ``backend/modules/`` structure.

21_System_Contracts.md §23.4:
- No external I/O. All network, database, and subprocess calls must be mocked.
- Test the module's public API (the class exported from ``__init__.py``).
- One test file per production file.
"""

from __future__ import annotations
