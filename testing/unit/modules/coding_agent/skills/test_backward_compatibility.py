"""Backward compatibility tests.

These tests verify that the new Skill Pack architecture does not break
existing public APIs or the existing CodingAgentManager behaviour.
"""

from __future__ import annotations

from backend.modules.coding_agent import (
    AgentRuntimePort,
    CodingAgentManager,
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
from backend.modules.coding_agent.coding_agent_module import (
    CodingAgentManager as CodingAgentManagerAlias,
)


class TestBackwardCompatCodingAgent:
    """Verify CodingAgentManager public API is unchanged."""

    def test_coding_agent_manager_is_exported(self) -> None:
        assert CodingAgentManager is CodingAgentManagerAlias

    def test_all_ports_are_exported(self) -> None:
        """All 11 ports must remain exported from coding_agent package."""
        ports = [
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
        ]
        for port in ports:
            assert port is not None, f"Port {port} should be exported"

    def test_coding_agent_manager_constructor_same_params(self) -> None:
        """Verify constructor signature hasn't changed."""
        import inspect
        sig = inspect.signature(CodingAgentManager.__init__)
        params = list(sig.parameters.keys())
        # Core params that must exist
        for param in ["config", "logger", "event_bus", "capability_manager",
                       "tool_manager", "context_manager", "conversation_manager"]:
            assert param in params or param in [p for p in params]

    def test_coding_agent_module_still_importable(self) -> None:
        """Full module import chain must still work."""
        from backend.modules.coding_agent.coding_agent_module import (
            CodingAgentManager,
        )
        assert CodingAgentManager is not None

    def test_skills_subsystem_isolated(self) -> None:
        """Skills module imports must not affect coding agent imports."""
        from backend.modules.coding_agent.skills import SkillManager
        assert SkillManager is not None


class TestBackwardCompatSkillImports:
    """Verify all new skill module exports work."""

    def test_skill_port_import(self) -> None:
        from backend.modules.coding_agent.skills._skill_port import SkillPort
        assert SkillPort is not None

    def test_skill_manager_import(self) -> None:
        from backend.modules.coding_agent.skills._manager import SkillManager
        assert SkillManager is not None

    def test_skill_registry_import(self) -> None:
        from backend.modules.coding_agent.skills._registry import SkillRegistry
        assert SkillRegistry is not None

    def test_skill_config_import(self) -> None:
        from backend.modules.coding_agent.skills._config import SkillConfig
        assert SkillConfig is not None

    def test_skill_types_import(self) -> None:
        from backend.modules.coding_agent.skills._types import (
            SkillCapability,
            SkillHealthReport,
            SkillMetadata,
            SkillResult,
            SkillStatistics,
        )
        assert SkillMetadata is not None
        assert SkillResult is not None
        assert SkillCapability is not None
        assert SkillStatistics is not None
        assert SkillHealthReport is not None

    def test_context_models_import(self) -> None:
        from backend.modules.coding_agent.skills.context._models import (
            SkillContext,
        )
        assert SkillContext is not None

    def test_detection_import(self) -> None:
        from backend.modules.coding_agent.skills.detection._capability import CapabilityDetector
        from backend.modules.coding_agent.skills.detection._project import ProjectDetector
        assert ProjectDetector is not None
        assert CapabilityDetector is not None

    def test_routing_import(self) -> None:
        from backend.modules.coding_agent.skills.routing._router import SkillRouter
        assert SkillRouter is not None

    def test_composition_import(self) -> None:
        from backend.modules.coding_agent.skills.composition._composer import SkillComposer
        assert SkillComposer is not None

    def test_all_skill_packs_importable(self) -> None:
        """All 24 skill packs must be importable."""
        from backend.modules.coding_agent.skills.packs.ai_ml_expert import AIMLExpertPack
        from backend.modules.coding_agent.skills.packs.c_expert import CExpertPack
        from backend.modules.coding_agent.skills.packs.competitive_programming_expert import (
            CompetitiveProgrammingExpertPack,
        )
        from backend.modules.coding_agent.skills.packs.cpp_expert import CppExpertPack
        from backend.modules.coding_agent.skills.packs.devops_expert import DevOpsExpertPack
        from backend.modules.coding_agent.skills.packs.django_expert import DjangoExpertPack
        from backend.modules.coding_agent.skills.packs.docker_expert import DockerExpertPack
        from backend.modules.coding_agent.skills.packs.dsa_expert import DSAExpertPack
        from backend.modules.coding_agent.skills.packs.express_expert import ExpressExpertPack
        from backend.modules.coding_agent.skills.packs.fastapi_expert import FastAPIExpertPack
        from backend.modules.coding_agent.skills.packs.git_expert import GitExpertPack
        from backend.modules.coding_agent.skills.packs.java_expert import JavaExpertPack
        from backend.modules.coding_agent.skills.packs.javascript_expert import JavaScriptExpertPack
        from backend.modules.coding_agent.skills.packs.kubernetes_expert import KubernetesExpertPack
        from backend.modules.coding_agent.skills.packs.linux_expert import LinuxExpertPack
        from backend.modules.coding_agent.skills.packs.mongodb_expert import MongoDBExpertPack
        from backend.modules.coding_agent.skills.packs.nextjs_expert import NextJsExpertPack
        from backend.modules.coding_agent.skills.packs.nodejs_expert import NodeJsExpertPack
        from backend.modules.coding_agent.skills.packs.postgresql_expert import PostgreSQLExpertPack
        from backend.modules.coding_agent.skills.packs.python_expert import PythonExpertPack
        from backend.modules.coding_agent.skills.packs.react_expert import ReactExpertPack
        from backend.modules.coding_agent.skills.packs.sql_expert import SQlExpertPack
        from backend.modules.coding_agent.skills.packs.typescript_expert import TypeScriptExpertPack
        from backend.modules.coding_agent.skills.packs.web_security_expert import (
            WebSecurityExpertPack,
        )

        assert CExpertPack is not None
        assert CppExpertPack is not None
        assert PythonExpertPack is not None
        assert JavaExpertPack is not None
        assert JavaScriptExpertPack is not None
        assert TypeScriptExpertPack is not None
        assert ReactExpertPack is not None
        assert NextJsExpertPack is not None
        assert NodeJsExpertPack is not None
        assert ExpressExpertPack is not None
        assert DjangoExpertPack is not None
        assert FastAPIExpertPack is not None
        assert SQlExpertPack is not None
        assert MongoDBExpertPack is not None
        assert PostgreSQLExpertPack is not None
        assert GitExpertPack is not None
        assert DockerExpertPack is not None
        assert KubernetesExpertPack is not None
        assert LinuxExpertPack is not None
        assert DSAExpertPack is not None
        assert CompetitiveProgrammingExpertPack is not None
        assert WebSecurityExpertPack is not None
        assert DevOpsExpertPack is not None
        assert AIMLExpertPack is not None


class TestBackwardCompatPublicAPI:
    """Verify the public __init__.py exports are correct."""

    def test_skills_init_exports(self) -> None:
        from backend.modules.coding_agent.skills import (
            AggregatedStatistics,
            BaseSkillPack,
            CapabilityDetector,
            CExpertPack,
            DockerExpertPack,
            ProjectDetector,
            PythonExpertPack,
            SkillCapability,
            SkillComposer,
            SkillConfig,
            SkillContext,
            SkillHealthReport,
            SkillManager,
            SkillMetadata,
            SkillPort,
            SkillRegistry,
            SkillResult,
            SkillRouter,
            SkillStatistics,
        )
        assert SkillManager is not None
        assert SkillPort is not None
        assert SkillRegistry is not None
        assert SkillConfig is not None
        assert SkillMetadata is not None
        assert SkillResult is not None
        assert SkillCapability is not None
        assert SkillHealthReport is not None
        assert SkillStatistics is not None
        assert AggregatedStatistics is not None
        assert SkillRouter is not None
        assert SkillComposer is not None
        assert ProjectDetector is not None
        assert CapabilityDetector is not None
        assert SkillContext is not None
        assert BaseSkillPack is not None
        assert CExpertPack is not None
        assert PythonExpertPack is not None
        assert DockerExpertPack is not None
