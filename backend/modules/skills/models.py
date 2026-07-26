"""
Skill Data Models — Core schema definitions for Naira OS Skill System.

Provides lightweight, thread-safe dataclasses and enums for skills,
matching results, capability satisfaction, and matching configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Union


class SkillCategory(str, Enum):
    """Standard categories for skills in Naira OS."""

    WEB = "web"
    CODING = "coding"
    VCS = "vcs"
    MOBILE = "mobile"
    SYSTEM = "system"
    DOCUMENT = "document"
    DEVOPS = "devops"
    DIAGNOSTICS = "diagnostics"
    GENERAL = "general"


@dataclass
class Skill:
    """Central Skill descriptor representing executable intelligence in Naira OS.

    Attributes
    ----------
    id : str
        Unique identifier (e.g. "skill.web.open_website")
    name : str
        Human-readable name (e.g. "Open Website")
    description : str
        Detailed description of what the skill performs.
    category : Union[SkillCategory, str]
        Category grouping.
    required_capabilities : List[str]
        Capabilities the machine MUST satisfy for this skill to be executable.
    optional_capabilities : List[str]
        Capabilities that enhance or unlock optional features of this skill.
    supported_platforms : List[str]
        Operating systems supported (e.g. ["windows", "linux", "darwin"] or ["*"]).
    required_permissions : List[str]
        Permissions required (e.g. ["network", "file_system"]).
    complexity_score : float
        Difficulty/complexity score between 0.0 and 1.0.
    estimated_duration : float
        Estimated execution time in seconds.
    executor : Union[Callable[..., Any], str, None]
        Function, coroutine, or target handler reference for execution.
    verifier : Optional[Union[Callable[..., Any], str]]
        Optional verification logic to run after execution.
    rollback_support : bool
        Whether this skill supports automated rollback steps.
    tags : List[str]
        Keywords and tags for search and intent matching.
    aliases : List[str]
        Synonyms and alternative titles.
    version : str
        Semantic version string (e.g. "1.0.0").
    metadata : Dict[str, Any]
        Additional arbitrary metadata.
    """

    __slots__ = (
        "id",
        "name",
        "description",
        "category",
        "required_capabilities",
        "optional_capabilities",
        "supported_platforms",
        "required_permissions",
        "complexity_score",
        "estimated_duration",
        "executor",
        "verifier",
        "rollback_support",
        "tags",
        "aliases",
        "version",
        "metadata",
    )

    id: str
    name: str
    description: str
    category: Union[SkillCategory, str]
    required_capabilities: List[str]
    optional_capabilities: List[str]
    supported_platforms: List[str]
    required_permissions: List[str]
    complexity_score: float
    estimated_duration: float
    executor: Union[Callable[..., Any], str, None]
    verifier: Optional[Union[Callable[..., Any], str]]
    rollback_support: bool
    tags: List[str]
    aliases: List[str]
    version: str
    metadata: Dict[str, Any]

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        category: Union[SkillCategory, str] = SkillCategory.GENERAL,
        required_capabilities: Optional[List[str]] = None,
        optional_capabilities: Optional[List[str]] = None,
        supported_platforms: Optional[List[str]] = None,
        required_permissions: Optional[List[str]] = None,
        complexity_score: float = 0.5,
        estimated_duration: float = 1.0,
        executor: Union[Callable[..., Any], str, None] = None,
        verifier: Optional[Union[Callable[..., Any], str]] = None,
        rollback_support: bool = False,
        tags: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.category = category.value if isinstance(category, SkillCategory) else str(category)
        self.required_capabilities = list(required_capabilities or [])
        self.optional_capabilities = list(optional_capabilities or [])
        self.supported_platforms = list(supported_platforms or ["*"])
        self.required_permissions = list(required_permissions or [])
        self.complexity_score = float(complexity_score)
        self.estimated_duration = float(estimated_duration)
        self.executor = executor
        self.verifier = verifier
        self.rollback_support = bool(rollback_support)
        self.tags = list(tags or [])
        self.aliases = list(aliases or [])
        self.version = str(version)
        self.metadata = dict(metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        """Serialize skill model to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "required_capabilities": self.required_capabilities,
            "optional_capabilities": self.optional_capabilities,
            "supported_platforms": self.supported_platforms,
            "required_permissions": self.required_permissions,
            "complexity_score": self.complexity_score,
            "estimated_duration": self.estimated_duration,
            "rollback_support": self.rollback_support,
            "tags": self.tags,
            "aliases": self.aliases,
            "version": self.version,
            "metadata": self.metadata,
        }


@dataclass
class SkillMatch:
    """Result of intent matching for a skill candidate."""

    skill: Skill
    confidence: float
    matching_reasons: List[str] = field(default_factory=list)
    missing_capabilities: List[str] = field(default_factory=list)
    is_executable: bool = True


@dataclass
class SkillMatchConfig:
    """Configuration for intent matching thresholds."""

    min_confidence: float = 0.4
    exact_match_score: float = 1.0
    alias_match_score: float = 0.95
    tag_match_score: float = 0.8
    fuzzy_match_threshold: float = 0.5
    top_k: int = 5
    require_capabilities: bool = True
