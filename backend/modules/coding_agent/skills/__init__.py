"""
Skills subsystem — domain-expert Skill Packs for the Coding Agent.

Architecture
------------
Skill Layer sits on top of the Coding Agent.
CodingAgentManager asks SkillManager when domain expertise is required.

Follows the same Port/Adapter + ModuleInterface pattern as LLM, Voice, Vision.

Public API
----------
- ``SkillManager`` — Central manager for all Skill Packs
- ``SkillPort`` — Abstract interface every Skill Pack must implement
- ``SkillRegistry`` — Registry for Skill Pack instances
- ``SkillConfig`` — All configuration for the skills subsystem
- ``SkillMetadata`` — Immutable metadata describing a Skill Pack
- ``SkillResult`` — Result of a single skill operation
- ``SkillCapability`` — A named capability a Skill Pack exposes
- ``SkillHealthReport`` — Health status of a Skill Pack
- ``SkillStatistics`` — Aggregated usage statistics
- ``AggregatedStatistics`` — Metrics across all skills
- ``SkillRouter`` — Automatic skill selection based on context
- ``SkillComposer`` — Composes multiple Skill Packs into execution plans
- ``ProjectDetector`` — Detects project type from file system
- ``CapabilityDetector`` — Detects project capabilities
- ``SkillContext`` — Unified context for all skill operations
- ``BaseSkillPack`` — Base implementation for all Skill Packs
- All built-in Skill Pack classes
"""

from __future__ import annotations

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._health import SkillHealthReportBuilder
from backend.modules.coding_agent.skills._manager import SkillManager
from backend.modules.coding_agent.skills._registry import SkillRegistry
from backend.modules.coding_agent.skills._skill_port import SkillPort
from backend.modules.coding_agent.skills._statistics import AggregatedStatistics
from backend.modules.coding_agent.skills._types import (
    SkillCapability,
    SkillHealthReport,
    SkillMetadata,
    SkillResult,
    SkillStatistics,
)
from backend.modules.coding_agent.skills.composition._composer import SkillComposer
from backend.modules.coding_agent.skills.context._models import (
    ConversationContext,
    DependencyGraph,
    FileInfo,
    MCPContext,
    ProjectContext,
    ReflectionContext,
    SkillContext,
)
from backend.modules.coding_agent.skills.detection._capability import CapabilityDetector
from backend.modules.coding_agent.skills.detection._project import ProjectDetector
from backend.modules.coding_agent.skills.packs._base import BaseSkillPack
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
from backend.modules.coding_agent.skills.packs.web_security_expert import WebSecurityExpertPack
from backend.modules.coding_agent.skills.routing._router import SkillRouter

__all__ = [
    "SkillManager",
    "SkillPort",
    "SkillRegistry",
    "SkillConfig",
    "SkillMetadata",
    "SkillResult",
    "SkillCapability",
    "SkillHealthReport",
    "SkillStatistics",
    "AggregatedStatistics",
    "SkillRouter",
    "SkillComposer",
    "ProjectDetector",
    "CapabilityDetector",
    "SkillContext",
    "ProjectContext",
    "MCPContext",
    "ReflectionContext",
    "ConversationContext",
    "FileInfo",
    "DependencyGraph",
    "SkillHealthReportBuilder",
    "BaseSkillPack",
    "CExpertPack",
    "CppExpertPack",
    "PythonExpertPack",
    "JavaExpertPack",
    "JavaScriptExpertPack",
    "TypeScriptExpertPack",
    "ReactExpertPack",
    "NextJsExpertPack",
    "NodeJsExpertPack",
    "ExpressExpertPack",
    "DjangoExpertPack",
    "FastAPIExpertPack",
    "SQlExpertPack",
    "MongoDBExpertPack",
    "PostgreSQLExpertPack",
    "GitExpertPack",
    "DockerExpertPack",
    "KubernetesExpertPack",
    "LinuxExpertPack",
    "DSAExpertPack",
    "CompetitiveProgrammingExpertPack",
    "WebSecurityExpertPack",
    "DevOpsExpertPack",
    "AIMLExpertPack",
]
