"""
Multi-agent framework package init.
"""

from backend.runtime.multi_agent._agent_definitions import (
    BUILTIN_AGENTS,
    CODER_AGENT,
    EXECUTOR_AGENT,
    PLANNER_AGENT,
    RESEARCHER_AGENT,
    AgentPersona,
)
from backend.runtime.multi_agent.multi_agent_orchestrator import MultiAgentOrchestrator

__all__ = [
    "AgentPersona",
    "PLANNER_AGENT",
    "CODER_AGENT",
    "RESEARCHER_AGENT",
    "EXECUTOR_AGENT",
    "BUILTIN_AGENTS",
    "MultiAgentOrchestrator",
]
