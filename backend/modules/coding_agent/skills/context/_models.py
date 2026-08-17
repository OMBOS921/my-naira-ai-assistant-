"""
Any models — all context types consumed by Skill Packs.

Each Skill Pack receives:
- Project Any
- MCP Any
- Reflection Any
- Conversation Any
- Current File
- Neighbour Files
- Dependency Graph
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FileInfo:
    """Information about a single file in the project."""

    path: str
    content: str = ""
    language: str = ""
    size: int = 0
    lines: int = 0
    extension: str = ""
    modified_at: float = 0.0


@dataclass
class DependencyGraph:
    """Represents the dependency graph of the project."""

    nodes: dict[str, list[str]] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def has_node(self, name: str) -> bool:
        return name in self.nodes

    def dependencies_of(self, name: str) -> list[str]:
        return self.nodes.get(name, [])


@dataclass
class ProjectContext:
    """Information about the current project."""

    root_path: str = ""
    project_type: str = ""
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    build_system: str = ""
    package_manager: str = ""
    test_framework: str = ""
    lint_system: str = ""
    formatter: str = ""
    ci_provider: str = ""
    is_monorepo: bool = False
    file_count: int = 0
    directory_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPContext:
    """Model Any Protocol context passed to skills."""

    tools: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    server_info: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflectionContext:
    """Previous reflection data passed to skills."""

    previous_results: list[dict[str, Any]] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    iteration_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Conversation history context passed to skills."""

    history: list[dict[str, str]] = field(default_factory=list)
    user_intent: str = ""
    recent_messages: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillContext:
    """Unified context passed to every Skill Pack operation.

    This is the single context object that flows through:
    analyse, plan, review, generate, refactor, debug, explain.
    """

    project: ProjectContext = field(default_factory=ProjectContext)
    mcp: MCPContext = field(default_factory=MCPContext)
    reflection: ReflectionContext = field(default_factory=ReflectionContext)
    conversation: ConversationContext = field(default_factory=ConversationContext)
    current_file: FileInfo | None = None
    neighbour_files: list[FileInfo] = field(default_factory=list)
    dependency_graph: DependencyGraph = field(default_factory=DependencyGraph)
    query: str = ""
    additional: dict[str, Any] = field(default_factory=dict)
