"""
CodingAgentManager — the single public class for the coding agent module.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §4.2 — ModuleInterface protocol.

Orchestrates the complete coding agent lifecycle:
- Agent Runtime management
- Task planning, decomposition, and execution
- Tool selection and execution
- File operations and multi-file editing
- Git operations
- Project analysis
- Context building
- Agent memory management
- Retry, reflection, and error recovery
- Safety validation
- Model Context Protocol (MCP) integration
- Human-in-the-Loop (HITL) approval workflow
- Compose Mode / Ghost Text suggestions
- Self-Correction loop
- Test-Driven Development (TDD) loop
- CI/CD pipeline monitoring
- Cost and token usage tracking
- Code security scanning
- Package auto-installation
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from backend.exceptions import ModuleDegradedError
from backend.modules.coding_agent._cicd_monitor import CICDMonitor, PipelineStatus
from backend.modules.coding_agent._compose_mode import ComposeMode, ComposeSuggestion
from backend.modules.coding_agent._context_builder import ContextBuilder
from backend.modules.coding_agent._cost_tracker import CostTracker
from backend.modules.coding_agent._diff_generator import DiffGenerator
from backend.modules.coding_agent._exceptions import (
    CodingAgentError,
)
from backend.modules.coding_agent._executor import CodingAgentExecutor
from backend.modules.coding_agent._hitl_workflow import ApprovalRequest, HITLWorkflow
from backend.modules.coding_agent._mcp_integration import MCPIntegration
from backend.modules.coding_agent._memory import AgentMemory
from backend.modules.coding_agent._package_installer import PackageAutoInstaller
from backend.modules.coding_agent._patch_generator import PatchGenerator
from backend.modules.coding_agent._recovery import ErrorRecovery
from backend.modules.coding_agent._reflection import ReflectionEngine
from backend.modules.coding_agent._retry import RetryEngine
from backend.modules.coding_agent._security_scanner import CodeSecurityScanner, ScanResult
from backend.modules.coding_agent._self_correction import CorrectionResult, SelfCorrectionLoop
from backend.modules.coding_agent._tdd_loop import TDDLoop, TDDResult
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
from backend.modules.coding_agent.providers.vscode_integration_provider import (
    VSCodeIntegrationProvider,
)
from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._manager import SkillManager
from backend.modules.context_intelligence._types import MCPContext
from backend.types import TokenUsage, ToolResult

if TYPE_CHECKING:
    from backend.modules.coding_agent.skills.context._models import SkillContext

_LOG = logging.getLogger("naira.coding_agent")


class CodingAgentManager:
    """Central coding agent manager — operates as a coding assistant.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        ``EventBus`` instance for event emission.
    capability_manager : object | None
        ``CapabilityManager`` instance for capability registration.
    tool_manager : object | None
        ``ToolManager`` instance for tool registration.
    context_manager : object | None
        ``ContextManager`` instance for context assembly.
    conversation_manager : object | None
        ``ConversationManager`` instance for session resolution.

    -- Ports (dependency injection) --

    agent_runtime : AgentRuntimePort | None
        Agent runtime provider.
    task_planner : TaskPlannerPort | None
        Task planning provider.
    tool_selector : ToolSelectionPort | None
        Tool selection provider.
    file_manager : FileManagerPort | None
        File operations provider.
    git_executor : GitExecutorPort | None
        Git operations provider.
    command_executor : CommandExecutorPort | None
        Command execution provider.
    language_detector : LanguageDetectorPort | None
        Language detection provider.
    multi_file_editor : MultiFileEditorPort | None
        Multi-file editing provider.
    project_analyzer : ProjectAnalyzerPort | None
        Project analysis provider.
    safety_layer : SafetyLayerPort | None
        Safety validation provider.
    workspace_manager : WorkspaceManagerPort | None
        Workspace management provider.

    -- Configuration --

    default_timeout : float
        Default timeout for agent operations (default 60.0).
    max_iterations : int
        Maximum execution iterations (default 10).
    max_retries : int
        Maximum retry attempts (default 3).
    retry_base_delay : float
        Base retry delay in seconds (default 1.0).
    retry_max_delay : float
        Maximum retry delay in seconds (default 30.0).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_manager: object | None = None,
        tool_manager: object | None = None,
        context_manager: object | None = None,
        conversation_manager: object | None = None,
        context_intelligence_manager: object | None = None,

        # Ports — dependency injection
        agent_runtime: AgentRuntimePort | None = None,
        task_planner: TaskPlannerPort | None = None,
        tool_selector: ToolSelectionPort | None = None,
        file_manager: FileManagerPort | None = None,
        git_executor: GitExecutorPort | None = None,
        command_executor: CommandExecutorPort | None = None,
        language_detector: LanguageDetectorPort | None = None,
        multi_file_editor: MultiFileEditorPort | None = None,
        project_analyzer: ProjectAnalyzerPort | None = None,
        safety_layer: SafetyLayerPort | None = None,
        workspace_manager: WorkspaceManagerPort | None = None,

        # Configuration overrides
        default_timeout: float = 60.0,
        max_iterations: int = 10,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        retry_max_delay: float = 30.0,

        # Feature flags — injected or use config defaults
        mcp_enabled: bool | None = None,
        hitl_enabled: bool | None = None,
        compose_mode_enabled: bool | None = None,
        self_correction_enabled: bool | None = None,
        tdd_enabled: bool | None = None,
        cicd_monitoring_enabled: bool | None = None,
        cost_tracking_enabled: bool | None = None,
        security_scanner_enabled: bool | None = None,
        package_installer_enabled: bool | None = None,
        max_correction_iterations: int | None = None,
        max_tdd_iterations: int | None = None,
        approval_timeout: float | None = None,
        scanner_rules: tuple[str, ...] | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._tool_manager = tool_manager
        self._context_manager = context_manager
        self._conversation_manager = conversation_manager
        self._context_intelligence_manager = context_intelligence_manager
        self._degraded: bool = False
        self._initialized: bool = False

        # Store configuration
        self._default_timeout = default_timeout
        self._max_iterations = max_iterations
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._retry_max_delay = retry_max_delay

        # Resolve feature flags from config or defaults
        cod_cfg = getattr(config, "coding_agent", None) if config else None

        def _resolve(val: object, attr: str, default: object) -> object:
            if val is not None:
                return val
            if cod_cfg is not None:
                return getattr(cod_cfg, attr, default)
            return default

        self._mcp_enabled = _resolve(mcp_enabled, "mcp_enabled", True)
        self._hitl_enabled = _resolve(hitl_enabled, "hitl_enabled", True)
        self._compose_mode_enabled = _resolve(compose_mode_enabled, "compose_mode_enabled", True)
        self._self_correction_enabled = _resolve(
            self_correction_enabled, "self_correction_enabled", True,
        )
        self._tdd_enabled = _resolve(tdd_enabled, "tdd_enabled", True)
        self._cicd_monitoring_enabled = _resolve(
            cicd_monitoring_enabled, "cicd_monitoring_enabled", True,
        )
        self._cost_tracking_enabled = _resolve(
            cost_tracking_enabled, "cost_tracking_enabled", True,
        )
        self._security_scanner_enabled = _resolve(
            security_scanner_enabled, "security_scanner_enabled", True,
        )
        self._package_installer_enabled = _resolve(
            package_installer_enabled, "package_installer_enabled", True,
        )
        self._max_correction_iterations = _resolve(
            max_correction_iterations, "max_correction_iterations", 3,
        )
        self._max_tdd_iterations = _resolve(max_tdd_iterations, "max_tdd_iterations", 5)
        self._approval_timeout = _resolve(approval_timeout, "approval_timeout", 120.0)
        self._scanner_rules = _resolve(scanner_rules, "scanner_rules", (
            "secrets", "injection", "xss", "path_traversal",
        ))

        # Import default providers lazily to avoid circular imports
        self._agent_runtime: AgentRuntimePort | None = agent_runtime
        self._task_planner: TaskPlannerPort | None = task_planner
        self._tool_selector: ToolSelectionPort | None = tool_selector
        self._file_manager: FileManagerPort | None = file_manager
        self._git_executor: GitExecutorPort | None = git_executor
        self._command_executor: CommandExecutorPort | None = command_executor
        self._language_detector: LanguageDetectorPort | None = language_detector
        self._multi_file_editor: MultiFileEditorPort | None = multi_file_editor
        self._project_analyzer: ProjectAnalyzerPort | None = project_analyzer
        self._safety_layer: SafetyLayerPort | None = safety_layer
        self._workspace_manager: WorkspaceManagerPort | None = workspace_manager

        self._vscode = VSCodeIntegrationProvider(
            file_manager=self._file_manager,
            workspace_manager=self._workspace_manager,
            logger=self._logger,
        )

        # Internal services — core
        self._executor = CodingAgentExecutor(
            logger=logger,
            default_timeout=default_timeout,
        )
        self._memory = AgentMemory(logger=logger)
        self._retry_engine = RetryEngine(logger=logger)
        self._reflection_engine = ReflectionEngine(logger=logger)
        self._error_recovery = ErrorRecovery(logger=logger)
        self._context_builder = ContextBuilder(logger=logger)
        self._diff_generator = DiffGenerator(logger=logger)
        self._patch_generator = PatchGenerator(logger=logger)

        # Internal services — new capabilities
        self._mcp: MCPIntegration = MCPIntegration(
            logger=logger,
            enabled=self._mcp_enabled,
        )
        self._hitl: HITLWorkflow = HITLWorkflow(
            logger=logger,
            enabled=self._hitl_enabled,
            approval_timeout=self._approval_timeout,
        )
        self._compose_mode: ComposeMode = ComposeMode(
            logger=logger,
            enabled=self._compose_mode_enabled,
        )
        self._self_correction: SelfCorrectionLoop = SelfCorrectionLoop(
            logger=logger,
            enabled=self._self_correction_enabled,
            max_iterations=self._max_correction_iterations,
        )
        self._tdd: TDDLoop = TDDLoop(
            logger=logger,
            enabled=self._tdd_enabled,
            max_iterations=self._max_tdd_iterations,
        )
        self._cicd_monitor: CICDMonitor = CICDMonitor(
            logger=logger,
            enabled=self._cicd_monitoring_enabled,
            event_bus=event_bus,
        )
        self._cost_tracker: CostTracker = CostTracker(
            logger=logger,
            enabled=self._cost_tracking_enabled,
        )
        self._security_scanner: CodeSecurityScanner = CodeSecurityScanner(
            logger=logger,
            enabled=self._security_scanner_enabled,
            rules=self._scanner_rules,
        )
        self._package_installer: PackageAutoInstaller = PackageAutoInstaller(
            logger=logger,
            enabled=self._package_installer_enabled,
        )

        # Skill Pack subsystem
        skill_cfg = SkillConfig(
            enable_skills=True,
            auto_register_builtin_packs=True,
            enable_auto_routing=True,
            enable_composition=True,
            enable_health_reporting=True,
            enable_metrics_collection=True,
            enable_hot_reload=getattr(cod_cfg, "enable_hot_reload", False) if cod_cfg else False,
        )
        self._skill_manager: SkillManager = SkillManager(
            config=skill_cfg,
            logger=logger,
            event_bus=event_bus,
        )

        # Metrics
        self._total_tasks: int = 0
        self._successful_tasks: int = 0
        self._failed_tasks: int = 0
        self._total_duration_ms: float = 0.0

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the coding agent module.

        Loads default providers for any unset ports, registers
        capabilities and tools.
        """
        self._load_default_providers()
        await self._skill_manager.async_init()
        self._register_capability()
        self._register_tools()
        self._initialized = True
        self._logger.info(
            "CodingAgentManager initialised — %d ports, %d services, skills=%s",
            self._count_ports(),
            self._count_services(),
            self._skill_manager.initialized,
        )

    async def async_shutdown(self) -> None:
        """Release all resources."""
        await self._shutdown_ports()
        await self._skill_manager.async_shutdown()
        self._memory.clear()
        self._reflection_engine.clear_history()
        self._compose_mode.clear_suggestions()
        self._cost_tracker.reset()
        self._degraded = False
        self._initialized = False
        self._logger.info("CodingAgentManager shut down.")

    def degrade(self) -> None:
        """Mark the module as degraded."""
        self._executor.degrade()
        self._memory.degrade()
        self._mcp.degrade()
        self._hitl.degrade()
        self._compose_mode.degrade()
        self._self_correction.degrade()
        self._tdd.degrade()
        self._cicd_monitor.degrade()
        self._cost_tracker.degrade()
        self._security_scanner.degrade()
        self._package_installer.degrade()
        self._skill_manager.degrade()
        self._degraded = True
        self._logger.warning("CodingAgentManager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Port accessors  (for testing and inspection)
    # ------------------------------------------------------------------

    @property
    def agent_runtime(self) -> AgentRuntimePort | None:
        return self._agent_runtime

    @property
    def task_planner(self) -> TaskPlannerPort | None:
        return self._task_planner

    @property
    def tool_selector(self) -> ToolSelectionPort | None:
        return self._tool_selector

    @property
    def file_manager(self) -> FileManagerPort | None:
        return self._file_manager

    @property
    def git_executor(self) -> GitExecutorPort | None:
        return self._git_executor

    @property
    def command_executor(self) -> CommandExecutorPort | None:
        return self._command_executor

    @property
    def language_detector(self) -> LanguageDetectorPort | None:
        return self._language_detector

    @property
    def multi_file_editor(self) -> MultiFileEditorPort | None:
        return self._multi_file_editor

    @property
    def project_analyzer(self) -> ProjectAnalyzerPort | None:
        return self._project_analyzer

    @property
    def safety_layer(self) -> SafetyLayerPort | None:
        return self._safety_layer

    @property
    def workspace_manager(self) -> WorkspaceManagerPort | None:
        return self._workspace_manager

    @property
    def executor(self) -> CodingAgentExecutor:
        return self._executor

    @property
    def memory(self) -> AgentMemory:
        return self._memory

    @property
    def retry_engine(self) -> RetryEngine:
        return self._retry_engine

    @property
    def reflection_engine(self) -> ReflectionEngine:
        return self._reflection_engine

    @property
    def error_recovery(self) -> ErrorRecovery:
        return self._error_recovery

    @property
    def context_builder(self) -> ContextBuilder:
        return self._context_builder

    @property
    def diff_generator(self) -> DiffGenerator:
        return self._diff_generator

    @property
    def patch_generator(self) -> PatchGenerator:
        return self._patch_generator

    # New service accessors

    @property
    def mcp(self) -> MCPIntegration:
        return self._mcp

    @property
    def hitl_workflow(self) -> HITLWorkflow:
        return self._hitl

    @property
    def compose_mode(self) -> ComposeMode:
        return self._compose_mode

    @property
    def self_correction(self) -> SelfCorrectionLoop:
        return self._self_correction

    @property
    def tdd_loop(self) -> TDDLoop:
        return self._tdd

    @property
    def cicd_monitor(self) -> CICDMonitor:
        return self._cicd_monitor

    @property
    def cost_tracker(self) -> CostTracker:
        return self._cost_tracker

    @property
    def security_scanner(self) -> CodeSecurityScanner:
        return self._security_scanner

    @property
    def package_installer(self) -> PackageAutoInstaller:
        return self._package_installer

    @property
    def vscode(self) -> VSCodeIntegrationProvider:
        return self._vscode

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    async def execute_task(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a single coding task end-to-end.

        Parameters
        ----------
        task_description : str
            Description of the task to execute.
        context : dict[str, Any] | None
            Additional execution context.

        Returns
        -------
        ToolResult
            The execution result.
        """
        self._ensure_not_degraded()
        import time
        start = time.monotonic()
        task_id = f"task_{self._total_tasks + 1}"

        await self._emit_event("coding_agent.task_start", {
            "task_id": task_id,
            "description": task_description[:100],
        })

        try:
            exec_context = context or {}

            # 1. Plan the task
            if self._task_planner is not None:
                plan = await self._task_planner.plan_tasks(task_description, exec_context)
                exec_context["plan"] = plan

            # 1b. Route to Skill Packs for domain expertise
            skill_context = self._build_skill_context(exec_context)
            selected_skills = await self._skill_manager.route(skill_context, task_description)
            if selected_skills:
                skill_names = [s.metadata().name for s in selected_skills]
                self._logger.debug("Selected skills for task: %s", skill_names)
                exec_context["selected_skills"] = skill_names
                # Enrich execution context with skill-generated content
                compose = await self._skill_manager.compose_plan(
                    selected_skills, skill_context, task_description,
                )
                if compose.success and compose.content:
                    exec_context["skill_context"] = compose.content

            # 2. Build context
            full_context = self._context_builder.build_context(
                task_id=task_id,
                goal=task_description,
                additional=exec_context,
            )

            # 3. Execute via agent runtime
            if self._agent_runtime is not None:
                result = await self._agent_runtime.execute_task(
                    task_id, task_description, full_context,
                )
                status = result.get("status", "completed")
                output = result.get("output", "")
            else:
                status = "completed"
                output = f"Task '{task_description}' acknowledged (no runtime provider)"

            # 4. Reflect on execution
            if self._reflection_engine is not None:
                reflection = await self._reflection_engine.reflect(
                    task_id, result if self._agent_runtime else {"status": status}, full_context,
                )
                full_context["reflection"] = reflection

            duration_ms = (time.monotonic() - start) * 1000
            self._record_metrics(status == "completed", duration_ms)

            tool_status = "success" if status == "completed" else "error"
            await self._emit_event("coding_agent.task_complete", {
                "task_id": task_id,
                "status": tool_status,
                "duration_ms": duration_ms,
            })

            return ToolResult(status=tool_status, output=output)

        except CodingAgentError as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._record_metrics(False, duration_ms)
            await self._emit_event("coding_agent.task_error", {
                "task_id": task_id,
                "error": str(exc),
                "duration_ms": duration_ms,
            })
            return ToolResult(status="error", error=str(exc))
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._record_metrics(False, duration_ms)
            self._logger.error("Task execution error: %s", exc)
            await self._emit_event("coding_agent.task_error", {
                "task_id": task_id,
                "error": str(exc),
                "duration_ms": duration_ms,
            })
            return ToolResult(status="error", error=str(exc))

    async def analyze_project(self, path: str) -> ToolResult:
        """Analyze a project directory.

        Parameters
        ----------
        path : str
            Path to the project root.

        Returns
        -------
        ToolResult
            Analysis result with structure, dependencies, and languages.
        """
        self._ensure_not_degraded()
        if self._project_analyzer is None:
            return ToolResult(status="error", error="Project analyzer not available")
        try:
            structure = await self._project_analyzer.analyze_structure(path)
            return ToolResult(status="success", output=str(structure))
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def workspace_operation(
        self,
        operation: str,
        session_id: str,
        **kwargs: object,
    ) -> ToolResult:
        """Perform a workspace operation.

        Parameters
        ----------
        operation : str
            Operation type: "create", "get", "cleanup", "save_state", "load_state".
        session_id : str
            Session identifier.

        Returns
        -------
        ToolResult
            Operation result.
        """
        self._ensure_not_degraded()
        if self._workspace_manager is None:
            return ToolResult(status="error", error="Workspace manager not available")
        try:
            state = kwargs.get("state", {})
            if not isinstance(state, dict):
                state = {}
            op_map: dict[str, Any] = {
                "create": self._workspace_manager.create_workspace,
                "get": self._workspace_manager.get_workspace,
                "cleanup": self._workspace_manager.cleanup_workspace,
                "save_state": lambda sid: self._workspace_manager.save_state(sid, state),
                "load_state": self._workspace_manager.load_state,
                "save_skill_state": lambda sid: self._save_skill_state(sid, state),
                "load_skill_state": lambda sid: self._load_skill_state(sid),
            }
            handler = op_map.get(operation)
            if handler is None:
                return ToolResult(status="error", error=f"Unknown workspace operation: {operation}")
            result = await handler(session_id)
            return ToolResult(status="success", output=str(result))
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def detect_language(self, path: str) -> ToolResult:
        """Detect the programming language of a file.

        Parameters
        ----------
        path : str
            Path to the file.

        Returns
        -------
        ToolResult
            Detection result with language name.
        """
        self._ensure_not_degraded()
        if self._language_detector is None:
            return ToolResult(status="error", error="Language detector not available")
        try:
            language = await self._language_detector.detect_file(path)
            return ToolResult(status="success", output=language)
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def file_operation(
        self,
        operation: str,
        path: str,
        content: str | None = None,
    ) -> ToolResult:
        """Perform a file operation.

        Parameters
        ----------
        operation : str
            Operation type: "read", "write", "delete", "exists".
        path : str
            File path.
        content : str | None
            File content (for write operations).

        Returns
        -------
        ToolResult
            Operation result.
        """
        self._ensure_not_degraded()
        if self._file_manager is None:
            return ToolResult(status="error", error="File manager not available")
        try:
            if self._safety_layer is not None:
                allowed, reason = await self._safety_layer.validate_file_operation(operation, path)
                if not allowed:
                    msg = reason or "Operation denied by safety layer"
                    return ToolResult(status="error", error=msg)

            if operation == "read":
                result = await self._file_manager.read_file(path)
                return ToolResult(status="success", output=result)
            elif operation == "write":
                if content is None:
                    return ToolResult(status="error", error="Content required for write operation")
                await self._file_manager.write_file(path, content)
                msg = f"Written {len(content)} bytes to {path}"
                return ToolResult(status="success", output=msg)
            elif operation == "delete":
                await self._file_manager.delete_file(path)
                return ToolResult(status="success", output=f"Deleted {path}")
            elif operation == "exists":
                exists = await self._file_manager.file_exists(path)
                return ToolResult(status="success", output=str(exists))
            else:
                return ToolResult(status="error", error=f"Unknown operation: {operation}")
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def git_operation(
        self,
        operation: str,
        **kwargs: object,
    ) -> ToolResult:
        """Perform a Git operation.

        Parameters
        ----------
        operation : str
            Operation type: "execute", "commit", "push", "pull", "diff", "status".

        Returns
        -------
        ToolResult
            Operation result.
        """
        self._ensure_not_degraded()
        if self._git_executor is None:
            return ToolResult(status="error", error="Git executor not available")
        try:
            args = kwargs.get("args", [])
            if not isinstance(args, list):
                args = []
            cwd_val = kwargs.get("cwd")
            cwd = str(cwd_val) if cwd_val else None
            msg = str(kwargs.get("message", ""))
            remote = str(kwargs.get("remote", "origin"))
            branch = str(kwargs.get("branch", "main"))
            op_map: dict[str, Any] = {
                "execute": lambda: self._git_executor.execute(args, cwd=cwd),
                "commit": lambda: self._git_executor.commit(msg, cwd=cwd),
                "push": lambda: self._git_executor.push(remote, branch, cwd=cwd),
                "pull": lambda: self._git_executor.pull(remote, branch, cwd=cwd),
                "diff": lambda: self._git_executor.diff(cwd=cwd),
                "status": lambda: self._git_executor.status(cwd=cwd),
            }
            handler = op_map.get(operation)
            if handler is None:
                return ToolResult(status="error", error=f"Unknown git operation: {operation}")
            result = await handler()
            is_success = result.get("success", True)
            return ToolResult(
                status="success" if is_success else "error",
                output=str(result),
            )
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def vscode_open_folder(
        self, folder_path: str, new_window: bool = False
    ) -> ToolResult:
        """Open a folder in VS Code."""
        self._ensure_not_degraded()
        res = await self._vscode.open_folder(folder_path, new_window=new_window)
        if res.get("success"):
            return ToolResult(
                status="success", output=f"Opened folder '{folder_path}' in VS Code"
            )
        return ToolResult(
            status="error", error=res.get("error", "Failed to open folder")
        )

    async def vscode_open_file(
        self, file_path: str, line_number: int | None = None
    ) -> ToolResult:
        """Open a file in VS Code at optional line number."""
        self._ensure_not_degraded()
        res = await self._vscode.open_file(file_path, line_number=line_number)
        if res.get("success"):
            return ToolResult(
                status="success", output=f"Opened file '{file_path}' in VS Code"
            )
        return ToolResult(
            status="error", error=res.get("error", "Failed to open file")
        )

    async def vscode_create_project(
        self, base_path: str, structure: dict[str, Any]
    ) -> ToolResult:
        """Create project directory structure and open in VS Code."""
        self._ensure_not_degraded()
        res = await self._vscode.create_project_structure(base_path, structure)
        if res.get("success"):
            files_count = len(res.get("created_files", []))
            return ToolResult(
                status="success",
                output=(
                    f"Created project structure with {files_count} file(s) and opened"
                    " in VS Code"
                ),
            )
        return ToolResult(
            status="error",
            error=res.get("error", "Failed to create project structure"),
        )

    async def vscode_edit_file(
        self, file_path: str, new_content: str, create_backup: bool = True
    ) -> ToolResult:
        """Edit a file in a project with optional backup."""
        self._ensure_not_degraded()
        res = await self._vscode.edit_file_in_project(
            file_path, new_content, create_backup=create_backup
        )
        if res.get("success"):
            backup_msg = (
                f" (backup: {res['backup_path']})" if res.get("backup_path") else ""
            )
            return ToolResult(
                status="success", output=f"Edited file '{file_path}'{backup_msg}"
            )
        return ToolResult(
            status="error", error=res.get("error", "Failed to edit file")
        )

    async def vscode_run_command(
        self, command: str, cwd: str | None = None
    ) -> ToolResult:
        """Run a command in integrated terminal."""
        self._ensure_not_degraded()
        res = await self._vscode.run_in_integrated_terminal(command, cwd=cwd)
        if res.get("success"):
            return ToolResult(status="success", output=res.get("stdout", ""))
        return ToolResult(
            status="error",
            error=res.get("stderr") or res.get("error", "Command failed"),
        )

    async def command_operation(
        self,
        command: str | list[str],
        **kwargs: object,
    ) -> ToolResult:
        """Execute a shell command.

        Parameters
        ----------
        command : str | list[str]
            Command to execute.

        Returns
        -------
        ToolResult
            Execution result.
        """
        self._ensure_not_degraded()
        if self._command_executor is None:
            return ToolResult(status="error", error="Command executor not available")
        try:
            if self._safety_layer is not None:
                cmd_str = command if isinstance(command, str) else " ".join(command)
                args_list = []
                if isinstance(command, str):
                    import shlex
                    args_list = shlex.split(command)
                else:
                    args_list = list(command)
                allowed, reason = await self._safety_layer.validate_command(
                    args_list[0] if args_list else cmd_str,
                    args_list[1:] if len(args_list) > 1 else [],
                )
                if not allowed:
                    msg = reason or "Command denied by safety layer"
                    return ToolResult(status="error", error=msg)

            result = await self._command_executor.execute(command, **kwargs)
            status = "success" if result.get("success", False) else "error"
            return ToolResult(
                status=status,
                output=result.get("output", ""),
                error=result.get("error"),
            )
        except Exception as exc:
            return ToolResult(status="error", error=str(exc))

    async def execute_local_python(
        self,
        script_code: str,
        *,
        timeout: float | None = None,
    ) -> ToolResult:
        """Execute a Python script locally using LocalPythonExecutor.

        Parameters
        ----------
        script_code : str
            The complete Python script code string to execute.
        timeout : float | None
            Execution timeout in seconds. Defaults to self._default_timeout.

        Returns
        -------
        ToolResult
            ToolResult containing stdout if successful, or stderr/error on failure.
        """
        self._ensure_not_degraded()
        try:
            from backend.modules.coding_agent._python_executor import LocalPythonExecutor

            executor = LocalPythonExecutor(
                file_manager=self._file_manager,
                safety_layer=self._safety_layer,
                command_executor=self._command_executor,
                logger=self._logger,
            )
            eff_timeout = timeout if timeout is not None else self._default_timeout
            res = await executor.execute(script_code, timeout=eff_timeout)
            if res.success:
                return ToolResult(
                    status="success",
                    output=res.stdout,
                )
            else:
                err_msg = res.stderr or res.error or "Python script execution failed"
                return ToolResult(
                    status="error",
                    output=err_msg,
                    error=err_msg,
                )
        except Exception as exc:
            err_msg = f"Python execution error: {exc}"
            return ToolResult(
                status="error",
                output=err_msg,
                error=err_msg,
            )

    # ------------------------------------------------------------------
    # MCP Integration
    # ------------------------------------------------------------------

    def create_context(
        self,
        session_id: str,
        system_prompt: str = "",
        chunks: list[Any] | None = None,
        symbols: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MCPContext:
        """Create an MCP context payload."""
        return self._mcp.create_context(
            session_id=session_id,
            system_prompt=system_prompt,
            chunks=chunks,
            symbols=symbols,
            metadata=metadata,
        )

    def merge_contexts(self, contexts: list[MCPContext]) -> MCPContext:
        """Merge multiple MCP contexts into one."""
        return self._mcp.merge_contexts(contexts)

    # ------------------------------------------------------------------
    # Human-in-the-Loop (HITL) approval workflow
    # ------------------------------------------------------------------

    async def request_approval(
        self,
        action: str,
        description: str,
        details: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> ApprovalRequest:
        """Request human approval for an action."""
        return await self._hitl.request_approval(
            action=action,
            description=description,
            details=details,
            timeout=timeout,
        )

    def approve_request(self, req_id: str, reason: str | None = None) -> ApprovalRequest | None:
        """Approve a pending HITL request."""
        return self._hitl.approve(req_id, reason)

    def reject_request(
        self, req_id: str, reason: str = "No reason provided",
    ) -> ApprovalRequest | None:
        """Reject a pending HITL request."""
        return self._hitl.reject(req_id, reason)

    def cancel_request(self, req_id: str) -> ApprovalRequest | None:
        """Cancel a pending HITL request."""
        return self._hitl.cancel(req_id)

    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return self._hitl.get_pending()

    # ------------------------------------------------------------------
    # Compose Mode / Ghost Text
    # ------------------------------------------------------------------

    def generate_ghost_text(
        self,
        file_path: str,
        original_text: str | None,
        suggested_text: str,
        line_start: int = 1,
        line_end: int | None = None,
        description: str = "",
        confidence: float = 1.0,
    ) -> ComposeSuggestion:
        """Generate a ghost text suggestion for a file."""
        return self._compose_mode.generate_ghost_text(
            file_path=file_path,
            original_text=original_text,
            suggested_text=suggested_text,
            line_start=line_start,
            line_end=line_end,
            description=description,
            confidence=confidence,
        )

    def apply_suggestion(
        self, suggestion_id: str, modified_text: str | None = None,
    ) -> ComposeSuggestion | None:
        """Apply a ghost text suggestion."""
        return self._compose_mode.apply_suggestion(suggestion_id, modified_text)

    def dismiss_suggestion(self, suggestion_id: str) -> ComposeSuggestion | None:
        """Dismiss a ghost text suggestion."""
        return self._compose_mode.dismiss_suggestion(suggestion_id)

    def get_active_suggestions(self, file_path: str | None = None) -> list[ComposeSuggestion]:
        """Get active ghost text suggestions."""
        return self._compose_mode.get_active_suggestions(file_path)

    # ------------------------------------------------------------------
    # Self-Correction loop
    # ------------------------------------------------------------------

    async def execute_with_correction(
        self,
        task_id: str,
        task_description: str,
        execute_fn: Any,
        reflect_fn: Any,
        context: dict[str, Any] | None = None,
    ) -> CorrectionResult:
        """Execute a task with self-correction loop."""
        return await self._self_correction.execute_with_correction(
            task_id=task_id,
            task_description=task_description,
            execute_fn=execute_fn,
            reflect_fn=reflect_fn,
            context=context,
        )

    # ------------------------------------------------------------------
    # Test-Driven Development (TDD) loop
    # ------------------------------------------------------------------

    async def execute_tdd(
        self,
        feature_description: str,
        write_test_fn: Any,
        run_test_fn: Any,
        write_code_fn: Any,
        refactor_fn: Any | None = None,
    ) -> TDDResult:
        """Execute a TDD cycle."""
        return await self._tdd.execute_tdd(
            feature_description=feature_description,
            write_test_fn=write_test_fn,
            run_test_fn=run_test_fn,
            write_code_fn=write_code_fn,
            refactor_fn=refactor_fn,
        )

    # ------------------------------------------------------------------
    # CI/CD Monitoring
    # ------------------------------------------------------------------

    def register_pipeline(self, pipeline_name: str) -> None:
        """Register a CI/CD pipeline for monitoring."""
        self._cicd_monitor.register_pipeline(pipeline_name)

    def start_pipeline_run(
        self,
        pipeline_name: str,
        commit_sha: str = "",
        branch: str = "",
    ) -> Any:
        """Start a new CI/CD pipeline run."""
        return self._cicd_monitor.start_run(pipeline_name, commit_sha, branch)

    def complete_pipeline_run(
        self,
        run_id: str,
        status: str,
        stages: dict[str, str] | None = None,
        artifacts: list[str] | None = None,
    ) -> Any:
        """Complete a CI/CD pipeline run."""
        ps = PipelineStatus(status) if isinstance(status, str) else status
        return self._cicd_monitor.complete_run(run_id, ps, stages, artifacts)

    def get_pipeline_status(self, pipeline_name: str) -> Any | None:
        """Get the current status of a CI/CD pipeline."""
        return self._cicd_monitor.get_pipeline_status(pipeline_name)

    # ------------------------------------------------------------------
    # Cost and Token tracking
    # ------------------------------------------------------------------

    def track_cost(
        self,
        operation: str,
        model: str,
        token_usage: TokenUsage,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Track cost for an operation."""
        return self._cost_tracker.track(operation, model, token_usage, metadata)

    def track_tokens(
        self,
        operation: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Any:
        """Track token usage for an operation."""
        return self._cost_tracker.track_tokens(operation, model, prompt_tokens, completion_tokens)

    def get_costs(self) -> dict[str, Any]:
        """Get cost tracking summary."""
        return self._cost_tracker.get_costs()

    def get_cost_by_operation(self) -> dict[str, float]:
        """Get costs broken down by operation."""
        return self._cost_tracker.get_cost_by_operation()

    # ------------------------------------------------------------------
    # Code Security Scanner
    # ------------------------------------------------------------------

    async def scan_file(self, file_path: str) -> ScanResult:
        """Scan a single file for security vulnerabilities."""
        return await self._security_scanner.scan_file(file_path)

    async def scan_code(self, code: str, source: str = "<inline>") -> ScanResult:
        """Scan code snippet for security vulnerabilities."""
        return await self._security_scanner.scan_code(code, source)

    async def scan_project(self, project_path: str) -> ScanResult:
        """Scan an entire project for security vulnerabilities."""
        return await self._security_scanner.scan_project(project_path)

    # ------------------------------------------------------------------
    # Package Auto Installer
    # ------------------------------------------------------------------

    async def install_package(
        self,
        package_name: str,
        manager: str = "pip",
        version: str | None = None,
        timeout: float = 60.0,
    ) -> Any:
        """Install a package automatically."""
        return await self._package_installer.install_package(
            package_name, manager, version, timeout,
        )

    async def detect_requirements(self, project_path: str) -> list[str]:
        """Detect required packages from a project."""
        return await self._package_installer.detect_requirements(project_path)

    # ------------------------------------------------------------------
    # Metrics and health
    # ------------------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        """Return current metrics snapshot."""
        return {
            "total_tasks": self._total_tasks,
            "successful_tasks": self._successful_tasks,
            "failed_tasks": self._failed_tasks,
            "success_rate": round(
                (self._successful_tasks / max(self._total_tasks, 1)) * 100, 1
            ),
            "total_duration_ms": round(self._total_duration_ms, 2),
            "avg_duration_ms": round(
                self._total_duration_ms / max(self._total_tasks, 1), 2
            ),
            "memory": self._memory.metrics(),
            "retry": self._retry_engine.get_metrics(),
            "mcp": self._mcp.metrics(),
            "hitl": self._hitl.metrics(),
            "compose_mode": self._compose_mode.metrics(),
            "self_correction": self._self_correction.metrics(),
            "tdd": self._tdd.metrics(),
            "cicd": self._cicd_monitor.metrics(),
            "cost_tracker": self._cost_tracker.metrics(),
            "security_scanner": self._security_scanner.metrics(),
            "package_installer": self._package_installer.metrics(),
            "skills": self._skill_manager.metrics() if self._skill_manager.initialized else {},
        }

    def health(self) -> dict[str, Any]:
        """Return health status of the coding agent module."""
        ports_ok = sum(
            1 for p in [self._agent_runtime, self._task_planner, self._tool_selector,
                        self._file_manager, self._git_executor, self._command_executor,
                        self._language_detector, self._multi_file_editor,
                        self._project_analyzer, self._safety_layer, self._workspace_manager]
            if p is not None and getattr(p, "is_available", False)
        )
        total_ports = 11
        services_ok = sum(
            1 for s in [self._mcp, self._hitl, self._compose_mode,
                        self._self_correction, self._tdd, self._cicd_monitor,
                        self._cost_tracker, self._security_scanner, self._package_installer]
            if not s.degraded
        )
        total_services = 9
        return {
            "healthy": not self._degraded and ports_ok > 0 and services_ok == total_services,
            "degraded": self._degraded,
            "initialized": self._initialized,
            "ports_available": ports_ok,
            "ports_total": total_ports,
            "ports_ratio": f"{ports_ok}/{total_ports}",
            "services_healthy": services_ok,
            "services_total": total_services,
            "services_ratio": f"{services_ok}/{total_services}",
            "memory_usage": self._memory.metrics().get("usage_pct", 0),
            "skills": self._skill_manager.health() if self._skill_manager.initialized else {},
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_default_providers(self) -> None:
        """Load default providers for any unset ports."""
        if self._agent_runtime is None:
            from backend.modules.coding_agent.providers.agent_runtime_provider import (
                DefaultAgentRuntimeProvider,
            )
            self._agent_runtime = DefaultAgentRuntimeProvider(logger=self._logger)

        if self._task_planner is None:
            from backend.modules.coding_agent.providers.task_planner_provider import (
                DefaultTaskPlannerProvider,
            )
            self._task_planner = DefaultTaskPlannerProvider(logger=self._logger)

        if self._tool_selector is None:
            from backend.modules.coding_agent.providers.tool_selection_provider import (
                DefaultToolSelectionProvider,
            )
            self._tool_selector = DefaultToolSelectionProvider(logger=self._logger)

        if self._file_manager is None:
            allowed = []
            ws = getattr(self._config, "coding_agent", None)
            if ws:
                ws_dir = getattr(ws, "workspace_dir", "")
                if ws_dir:
                    allowed = [ws_dir]
            from backend.modules.coding_agent.providers.file_manager_provider import (
                OSFileManagerProvider,
            )
            max_fs = getattr(ws, "max_file_size", 1_048_576) if ws else 1_048_576
            self._file_manager = OSFileManagerProvider(
                allowed_paths=tuple(allowed),
                max_file_size=max_fs,
                logger=self._logger,
            )

        if self._git_executor is None:
            git_enabled = True
            if ws:
                git_enabled = getattr(ws, "git_enabled", True)
            from backend.modules.coding_agent.providers.git_executor_provider import (
                CLIGitExecutorProvider,
            )
            self._git_executor = CLIGitExecutorProvider(
                enabled=git_enabled,
                logger=self._logger,
            )

        if self._command_executor is None:
            allowed_cmds = ()
            if ws:
                allowed_cmds = getattr(ws, "allowed_commands", ())
            from backend.modules.coding_agent.providers.command_executor_provider import (
                AsyncCommandExecutorProvider,
            )
            self._command_executor = AsyncCommandExecutorProvider(
                allowed_commands=allowed_cmds,
                logger=self._logger,
            )

        if self._language_detector is None:
            from backend.modules.coding_agent.providers.language_detector_provider import (
                FileExtensionLanguageDetectorProvider,
            )
            self._language_detector = FileExtensionLanguageDetectorProvider(logger=self._logger)

        if self._multi_file_editor is None:
            from backend.modules.coding_agent.providers.multi_file_editor_provider import (
                DefaultMultiFileEditorProvider,
            )
            self._multi_file_editor = DefaultMultiFileEditorProvider(logger=self._logger)

        if self._project_analyzer is None:
            from backend.modules.coding_agent.providers.project_analyzer_provider import (
                DefaultProjectAnalyzerProvider,
            )
            self._project_analyzer = DefaultProjectAnalyzerProvider(logger=self._logger)

        if self._safety_layer is None:
            safety_enabled = True
            if ws:
                safety_enabled = getattr(ws, "safety_enabled", True)
            from backend.modules.coding_agent.providers.safety_layer_provider import (
                DefaultSafetyLayerProvider,
            )
            self._safety_layer = DefaultSafetyLayerProvider(
                enabled=safety_enabled,
                logger=self._logger,
            )

        if self._workspace_manager is None:
            ws_dir = ""
            if ws:
                ws_dir = getattr(ws, "workspace_dir", "")
            from backend.modules.coding_agent.providers.workspace_manager_provider import (
                TempWorkspaceManagerProvider,
            )
            self._workspace_manager = TempWorkspaceManagerProvider(
                base_dir=ws_dir or None,
                logger=self._logger,
            )

    async def _shutdown_ports(self) -> None:
        for port in [
            self._agent_runtime, self._task_planner, self._tool_selector,
            self._file_manager, self._git_executor, self._command_executor,
            self._language_detector, self._multi_file_editor,
            self._project_analyzer, self._safety_layer, self._workspace_manager,
        ]:
            if port is not None:
                try:
                    await port.close()
                except Exception as exc:
                    self._logger.warning("Error closing port %s: %s", type(port).__name__, exc)

    def _register_capability(self) -> None:
        if self._capability_manager is not None:
            register_cap = getattr(self._capability_manager, "register", None)
            if register_cap is not None:
                from backend.modules.capability.capability import Capability
                from backend.modules.capability.metadata import CapabilityMetadata

                # Core coding agent capability
                register_cap(Capability(
                    name="coding_agent",
                    version="0.2.0",
                    dependencies=("llm", "context"),
                    metadata=CapabilityMetadata(
                        description=(
                            "AI-powered coding assistant with MCP,"
                            " HITL, TDD, and security scanning"
                        ),
                    ),
                ))

                # Sub-capabilities for each feature
                feature_map: dict[str, tuple[str, ...]] = {
                    "coding_agent.mcp": ("coding_agent",),
                    "coding_agent.hitl": ("coding_agent",),
                    "coding_agent.compose": ("coding_agent",),
                    "coding_agent.self_correction": ("coding_agent",),
                    "coding_agent.tdd": ("coding_agent",),
                    "coding_agent.cicd": ("coding_agent",),
                    "coding_agent.cost_tracking": ("coding_agent",),
                    "coding_agent.security_scanner": ("coding_agent",),
                    "coding_agent.package_installer": ("coding_agent",),
                    "coding_agent.skills": ("coding_agent",),
                }
                for feat_name, feat_deps in feature_map.items():
                    register_cap(Capability(
                        name=feat_name,
                        version="0.1.0",
                        dependencies=feat_deps,
                    ))

    def _register_tools(self) -> None:
        if self._tool_manager is not None:
            register = getattr(self._tool_manager, "register_tool", None)
            if register is not None:
                from backend.modules.tools import ToolDefinition

                register(
                    ToolDefinition(
                        name="coding_agent_execute_task",
                        description="Execute a coding task with the coding agent",
                        parameters={
                            "type": "object",
                            "properties": {
                                "task_description": {
                                    "type": "string",
                                    "description": "Description of the task to execute",
                                },
                            },
                            "required": ["task_description"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_execute_task_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_analyze_project",
                        description="Analyze a project directory structure and dependencies",
                        parameters={
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "Path to the project root",
                                },
                            },
                            "required": ["path"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_analyze_project_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_read_file",
                        description="Read the contents of a file",
                        parameters={
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to the file"},
                            },
                            "required": ["path"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_read_file_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_write_file",
                        description="Write content to a file",
                        parameters={
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to the file"},
                                "content": {"type": "string", "description": "Content to write"},
                            },
                            "required": ["path", "content"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_write_file_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_detect_language",
                        description="Detect the programming language of a file",
                        parameters={
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Path to the file"},
                            },
                            "required": ["path"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_detect_language_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_git_status",
                        description="Get the git status of a repository",
                        parameters={
                            "type": "object",
                            "properties": {
                                "cwd": {"type": "string", "description": "Repository directory"},
                            },
                            "required": [],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_git_status_tool,
                )

                # New feature tools
                register(
                    ToolDefinition(
                        name="coding_agent_scan",
                        description="Scan code or a file for security vulnerabilities",
                        parameters={
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "Path to file or project to scan",
                                },
                                "code": {
                                    "type": "string",
                                    "description": "Code snippet to scan (inline)",
                                },
                            },
                            "required": [],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_scan_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_install_package",
                        description="Install a Python package automatically",
                        parameters={
                            "type": "object",
                            "properties": {
                                "package_name": {
                                    "type": "string",
                                    "description": "Name of the package to install",
                                },
                                "manager": {
                                    "type": "string",
                                    "description": "Package manager (pip, npm, etc.)",
                                },
                                "version": {
                                    "type": "string",
                                    "description": "Optional version specifier",
                                },
                            },
                            "required": ["package_name"],
                        },
                        category="coding_agent",
                        timeout_seconds=120.0,
                    ),
                    self._handle_install_package_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_suggest",
                        description="Generate a ghost text (compose) suggestion for a file edit",
                        parameters={
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path to the file",
                                },
                                "suggested_text": {
                                    "type": "string",
                                    "description": "Suggested replacement text",
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Description of the suggestion",
                                },
                            },
                            "required": ["file_path", "suggested_text"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_suggest_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_costs",
                        description="Get cost and token usage summary",
                        parameters={
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_costs_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_list_skills",
                        description="List available Skill Packs and their status",
                        parameters={
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_list_skills_tool,
                )

                register(
                    ToolDefinition(
                        name="coding_agent_pipeline",
                        description="Start or check a CI/CD pipeline run",
                        parameters={
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "description": "Action: start, status",
                                },
                                "pipeline_name": {
                                    "type": "string",
                                    "description": "Pipeline name",
                                },
                                "commit_sha": {
                                    "type": "string",
                                    "description": "Commit SHA",
                                },
                            },
                            "required": ["action", "pipeline_name"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_pipeline_tool,
                )

                register(
                    ToolDefinition(
                        name="vscode_open_folder",
                        description="Open a folder in VS Code",
                        parameters={
                            "type": "object",
                            "properties": {
                                "folder_path": {
                                    "type": "string",
                                    "description": "Path to the folder to open",
                                },
                                "new_window": {
                                    "type": "boolean",
                                    "description": "Whether to open in a new window",
                                },
                            },
                            "required": ["folder_path"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_vscode_open_folder_tool,
                )

                register(
                    ToolDefinition(
                        name="vscode_open_file",
                        description="Open a file in VS Code at optional line number",
                        parameters={
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path to the file to open",
                                },
                                "line_number": {
                                    "type": "integer",
                                    "description": "Line number to navigate to",
                                },
                            },
                            "required": ["file_path"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_vscode_open_file_tool,
                )

                register(
                    ToolDefinition(
                        name="vscode_create_project",
                        description="Create project directory structure and open in VS Code",
                        parameters={
                            "type": "object",
                            "properties": {
                                "base_path": {
                                    "type": "string",
                                    "description": "Base directory for the project",
                                },
                                "structure": {
                                    "type": "object",
                                    "description": "Nested dictionary representing directory layout and files",
                                },
                            },
                            "required": ["base_path", "structure"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_vscode_create_project_tool,
                )

                register(
                    ToolDefinition(
                        name="vscode_edit_file",
                        description="Edit a file in a project with optional backup",
                        parameters={
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path to the file to edit",
                                },
                                "new_content": {
                                    "type": "string",
                                    "description": "New content for the file",
                                },
                                "create_backup": {
                                    "type": "boolean",
                                    "description": "Whether to create a backup file (.bak)",
                                },
                            },
                            "required": ["file_path", "new_content"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_vscode_edit_file_tool,
                )

                register(
                    ToolDefinition(
                        name="vscode_run_command",
                        description="Run a command in integrated terminal",
                        parameters={
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "string",
                                    "description": "Command to execute",
                                },
                                "cwd": {
                                    "type": "string",
                                    "description": "Current working directory for command",
                                },
                            },
                            "required": ["command"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_vscode_run_command_tool,
                )

                register(
                    ToolDefinition(
                        name="execute_local_python",
                        description="Execute a complete Python script locally and return terminal output (stdout/stderr)",
                        parameters={
                            "type": "object",
                            "properties": {
                                "script_code": {
                                    "type": "string",
                                    "description": "The complete Python script code to execute",
                                },
                            },
                            "required": ["script_code"],
                        },
                        category="coding_agent",
                        timeout_seconds=self._default_timeout,
                    ),
                    self._handle_execute_python,
                )

    async def _handle_vscode_open_folder_tool(
        self, folder_path: str, new_window: bool = False
    ) -> ToolResult:
        return await self.vscode_open_folder(folder_path, new_window=new_window)

    async def _handle_vscode_open_file_tool(
        self, file_path: str, line_number: int | None = None
    ) -> ToolResult:
        return await self.vscode_open_file(file_path, line_number=line_number)

    async def _handle_vscode_create_project_tool(
        self, base_path: str, structure: dict[str, Any]
    ) -> ToolResult:
        return await self.vscode_create_project(base_path, structure)

    async def _handle_vscode_edit_file_tool(
        self, file_path: str, new_content: str, create_backup: bool = True
    ) -> ToolResult:
        return await self.vscode_edit_file(
            file_path, new_content, create_backup=create_backup
        )

    async def _handle_vscode_run_command_tool(
        self, command: str, cwd: str | None = None
    ) -> ToolResult:
        return await self.vscode_run_command(command, cwd=cwd)

    async def _handle_execute_python(self, script_code: str) -> ToolResult:
        return await self.execute_local_python(script_code)

    async def _handle_execute_task_tool(self, task_description: str) -> ToolResult:
        return await self.execute_task(task_description)

    async def _handle_analyze_project_tool(self, path: str) -> ToolResult:
        return await self.analyze_project(path)

    async def _handle_read_file_tool(self, path: str) -> ToolResult:
        return await self.file_operation("read", path)

    async def _handle_write_file_tool(self, path: str, content: str) -> ToolResult:
        return await self.file_operation("write", path, content)

    async def _handle_detect_language_tool(self, path: str) -> ToolResult:
        return await self.detect_language(path)

    async def _handle_git_status_tool(self, cwd: str = "") -> ToolResult:
        return await self.git_operation("status", cwd=cwd or None)

    async def _handle_scan_tool(
        self, path: str = "", code: str = "",
    ) -> ToolResult:
        if path:
            if os.path.isdir(path):
                result = await self.scan_project(path)
            else:
                result = await self.scan_file(path)
        elif code:
            result = await self.scan_code(code)
        else:
            return ToolResult(status="error", error="Either path or code is required")
        return ToolResult(
            status="success" if result.safe else "error",
            output=f"Scanned {result.files_scanned} file(s), found {result.total_issues} issue(s)",
            error=None if result.safe else str([v.message for v in result.vulnerabilities]),
        )

    async def _handle_install_package_tool(
        self, package_name: str, manager: str = "pip", version: str | None = None,
    ) -> ToolResult:
        result = await self.install_package(package_name, manager, version)
        if result.success:
            return ToolResult(
                status="success",
                output=f"Package '{package_name}' installed successfully",
            )
        return ToolResult(
            status="error",
            error=(
                f"Failed to install '{package_name}': "
                f"{result.failed[0][1] if result.failed else 'Unknown error'}"
            ),
        )

    async def _handle_suggest_tool(
        self, file_path: str, suggested_text: str, description: str = "",
    ) -> ToolResult:
        original = None
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    original = f.read()
            except OSError:
                pass
        suggestion = self.generate_ghost_text(
            file_path=file_path,
            original_text=original,
            suggested_text=suggested_text,
            description=description,
        )
        return ToolResult(
            status="success",
            output=f"Suggestion {suggestion.id} created for {file_path}",
        )

    async def _handle_costs_tool(self) -> ToolResult:
        costs = self.get_costs()
        return ToolResult(
            status="success",
            output=(
                f"Total cost: ${costs['total_cost']:.6f}, "
                f"Tokens: {costs['total_tokens']} prompt"
                f" + {costs['total_completion_tokens']} completion"
            ),
        )

    async def _handle_list_skills_tool(self) -> ToolResult:
        skills = self._skill_manager.list_skills()
        health = self._skill_manager.health() if self._skill_manager.initialized else {}
        return ToolResult(
            status="success",
            output=f"Skills ({len(skills)}): {', '.join(skills)} | Health: {health}",
        )

    async def _handle_pipeline_tool(
        self, action: str, pipeline_name: str, commit_sha: str = "",
    ) -> ToolResult:
        if action == "start":
            run = self.start_pipeline_run(pipeline_name, commit_sha)
            return ToolResult(
                status="success",
                output=f"Pipeline run {run.id} started for {pipeline_name}",
            )
        elif action == "status":
            status = self.get_pipeline_status(pipeline_name)
            if status is None:
                return ToolResult(status="error", error=f"Pipeline '{pipeline_name}' not found")
            return ToolResult(
                status="success",
                output=(
                    f"Pipeline: {status.pipeline_name}, "
                    f"Last run: {status.last_run_status.value}, "
                    f"Success rate: {status.success_rate}%"
                ),
            )
        return ToolResult(status="error", error=f"Unknown action: {action}")

    # ── Skill Pack Integration ────────────────────────────────────────

    @property
    def skill_manager(self) -> SkillManager:
        return self._skill_manager

    def _save_skill_state(self, session_id: str, state: dict[str, Any]) -> str:
        skill_data = self._skill_manager.save_state()
        import json
        persist_dir = getattr(self._config, "skill_state_dir", None) if self._config else None
        if persist_dir:
            import os
            os.makedirs(str(persist_dir), exist_ok=True)
            file_path = os.path.join(str(persist_dir), f"{session_id}_skills.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(skill_data, f, default=str)
            return f"Skill state saved for session {session_id}"
        return "Skill state captured in memory (no persist_dir configured)"

    def _load_skill_state(self, session_id: str) -> str:
        import json
        import os
        persist_dir = getattr(self._config, "skill_state_dir", None) if self._config else None
        if persist_dir:
            file_path = os.path.join(str(persist_dir), f"{session_id}_skills.json")
            if os.path.isfile(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._skill_manager.restore_state(data)
                return f"Skill state restored for session {session_id}"
        return "No persisted skill state found"

    def _build_skill_context(
        self, exec_context: dict[str, Any],
    ) -> SkillContext:
        """Build a SkillContext from the current execution context."""
        from backend.modules.coding_agent.skills.context._models import (
            ProjectContext as SkillProjectContext,
        )
        from backend.modules.coding_agent.skills.context._models import (
            SkillContext,
        )

        project = SkillProjectContext(
            root_path=exec_context.get("workspace_dir", ""),
            project_type=exec_context.get("project_type", ""),
            languages=exec_context.get("languages", []),
            frameworks=exec_context.get("frameworks", []),
        )
        return SkillContext(
            project=project,
            query=exec_context.get("goal", str(exec_context.get("task_description", ""))),
        )

    def _record_metrics(self, success: bool, duration_ms: float) -> None:
        self._total_tasks += 1
        self._total_duration_ms += duration_ms
        if success:
            self._successful_tasks += 1
        else:
            self._failed_tasks += 1

    def _count_ports(self) -> int:
        return sum(
            1 for p in [
                self._agent_runtime, self._task_planner, self._tool_selector,
                self._file_manager, self._git_executor, self._command_executor,
                self._language_detector, self._multi_file_editor,
                self._project_analyzer, self._safety_layer, self._workspace_manager,
            ]
            if p is not None
        )

    def _count_services(self) -> int:
        return 17

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "CodingAgentManager is degraded",
                context={"module": "coding_agent"},
            )

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)
