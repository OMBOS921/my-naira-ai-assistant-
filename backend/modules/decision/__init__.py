"""
Decision Module — Naira-OS intelligent request routing engine.

21_System_Contracts.md §4.2 — Decision contracts.
"""

from __future__ import annotations

from backend.modules.decision._routes import RouteDecision, RouteTarget
from backend.modules.decision.decision_module import DecisionManager

__all__ = [
    "DecisionManager",
    "RouteDecision",
    "RouteTarget",
]
