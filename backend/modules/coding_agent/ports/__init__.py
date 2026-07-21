"""Coding Agent port definitions.

Port/Adapter pattern for extensibility.
"""

from __future__ import annotations

from backend.modules.coding_agent.ports.agent_runtime_port import AgentRuntimePort
from backend.modules.coding_agent.ports.command_executor_port import CommandExecutorPort
from backend.modules.coding_agent.ports.file_manager_port import FileManagerPort
from backend.modules.coding_agent.ports.git_executor_port import GitExecutorPort
from backend.modules.coding_agent.ports.language_detector_port import LanguageDetectorPort
from backend.modules.coding_agent.ports.multi_file_editor_port import MultiFileEditorPort
from backend.modules.coding_agent.ports.project_analyzer_port import ProjectAnalyzerPort
from backend.modules.coding_agent.ports.safety_layer_port import SafetyLayerPort
from backend.modules.coding_agent.ports.task_planner_port import TaskPlannerPort
from backend.modules.coding_agent.ports.tool_selection_port import ToolSelectionPort
from backend.modules.coding_agent.ports.workspace_manager_port import WorkspaceManagerPort

__all__ = [
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
