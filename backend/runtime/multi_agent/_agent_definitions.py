"""
Multi-Agent Persona Definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentPersona:
    """Descriptor for a specialized agent persona."""

    name: str
    role: str
    system_prompt: str
    allowed_tools: list[str] = field(default_factory=list)
    description: str = ""


PLANNER_AGENT = AgentPersona(
    name="Planner",
    role="planner",
    system_prompt=(
        "You are a master task planner. Break down complex user requests into a clear, "
        "ordered list of sequential sub-tasks. Each sub-task must be clear, actionable, "
        "and assigned a target persona: 'coder', 'researcher', or 'executor'."
    ),
    allowed_tools=[],
    description="Decomposes complex requests into sequential sub-tasks.",
)

CODER_AGENT = AgentPersona(
    name="Coder",
    role="coder",
    system_prompt=(
        "You are an expert software engineer. Write high quality, robust code, fix bugs, "
        "and explain technical implementations concisely."
    ),
    allowed_tools=["python_interpreter", "file_write", "file_read", "terminal"],
    description="Handles code generation, refactoring, and technical execution.",
)

RESEARCHER_AGENT = AgentPersona(
    name="Researcher",
    role="researcher",
    system_prompt=(
        "You are a detailed web and knowledge researcher. Gather accurate facts, synthesize information, "
        "and summarize key findings clearly."
    ),
    allowed_tools=["web_search", "fetch_webpage", "file_read"],
    description="Searches for information and synthesizes web/document knowledge.",
)

EXECUTOR_AGENT = AgentPersona(
    name="Executor",
    role="executor",
    system_prompt=(
        "You are a system action executor. Run system commands, manipulate files, and carry out "
        "action-oriented operations accurately."
    ),
    allowed_tools=["terminal", "file_write", "file_read", "app_launcher"],
    description="Executes file and system operations.",
)

BUILTIN_AGENTS: dict[str, AgentPersona] = {
    "planner": PLANNER_AGENT,
    "coder": CODER_AGENT,
    "researcher": RESEARCHER_AGENT,
    "executor": EXECUTOR_AGENT,
}
