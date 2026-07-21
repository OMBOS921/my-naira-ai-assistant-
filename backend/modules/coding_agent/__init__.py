"""
Coding Agent module — production-grade coding assistant.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §4.2 — ModuleInterface protocol.

Architecture
------------
CodingAgentManager follows the same Port/Adapter + ModuleInterface pattern
as BrowserManager, LLMManager, VisionManager, VoiceManager, and PCControlManager.

All configuration is injected through constructor parameters.  No os.environ
or .env file is ever read inside the module — all environment data comes
through ``SettingsManager`` / ``EnvironmentSnapshot``.

Public API
----------
- ``CodingAgentManager`` — central coding agent manager
- All port classes for dependency injection
- All provider classes for concrete implementations
- Internal services: AgentMemory, RetryEngine, ReflectionEngine, etc.
"""

from __future__ import annotations

from backend.modules.coding_agent.coding_agent_module import CodingAgentManager
from backend.modules.coding_agent.ports import (
    AgentRuntimePort,
    CommandExecutorPort,
    FileManagerPort,
    GitExecutorPort,
    LanguageDetectorPort,
    MultiFileEditorPort,
    ProjectAnalyzerPort,
    SafetyLayerPort,
    TaskPlannerPort,
    ToolSelectionPort,
    WorkspaceManagerPort,
)

__all__ = [
    "CodingAgentManager",
    "AgentRuntimePort",
    "CommandExecutorPort",
    "FileManagerPort",
    "GitExecutorPort",
    "LanguageDetectorPort",
    "MultiFileEditorPort",
    "ProjectAnalyzerPort",
    "SafetyLayerPort",
    "TaskPlannerPort",
    "ToolSelectionPort",
    "WorkspaceManagerPort",
]
