from __future__ import annotations
from typing import Any
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
- Any building
- Agent memory management
- Retry, reflection, and error recovery
- Safety validation
- Model Any Protocol (MCP) integration
- Human-in-the-Loop (HITL) approval workflow
- Compose Mode / Ghost Text suggestions
- Self-Correction loop
- Test-Driven Development (TDD) loop
- CI/CD pipeline monitoring
- Cost and token usage tracking
- Code security scanning
- Package auto-installation
"""



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
from backend.types import ToolResult
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
        """Execute a single coding task end-to-end (deterministic fallback)."""
        self._ensure_not_degraded()
        import time
        start = time.monotonic()
        task_id = f"task_{self._total_tasks + 1}"

        await self._emit_event("coding_agent.task_start", {
            "task_id": task_id,
            "description": task_description[:100],
        })

        # LLM execution removed. Returns structured failure when autonomous reasoning is requested.
        output = f"Task '{task_description}' acknowledged. Autonomous coding agent requires LLM which is disabled."
        
        self._total_tasks += 1
        self._failed_tasks += 1
        duration = (time.monotonic() - start) * 1000
        self._total_duration_ms += duration

        await self._emit_event("coding_agent.task_complete", {
            "task_id": task_id,
            "status": "error",
            "duration_ms": duration,
        })

        return ToolResult(status="error", error=output)

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
