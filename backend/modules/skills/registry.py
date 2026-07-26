"""
Skill Registry — Central catalog of executable intelligence in Naira OS.

Provides thread-safe storage, lazy-loading of handlers, fast multi-index discovery APIs,
and intent matching with caching.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from backend.modules.skills.matchers import (
    BaseSkillMatcher,
    EmbeddingSkillMatcher,
    KeywordAliasSkillMatcher,
    MultilingualSkillMatcher,
)
from backend.modules.skills.models import Skill, SkillCategory, SkillMatch, SkillMatchConfig

_LOG = logging.getLogger("naira.skills.registry")


class IntentCache:
    """Thread-safe TTL/LRU cache for intent matching queries."""

    def __init__(self, max_size: int = 256, ttl_seconds: float = 60.0) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[float, List[SkillMatch]]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[List[SkillMatch]]:
        with self._lock:
            if key not in self._cache:
                return None
            ts, result = self._cache[key]
            if time.time() - ts > self._ttl_seconds:
                del self._cache[key]
                return None
            return list(result)

    def put(self, key: str, result: List[SkillMatch]) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evict oldest entry
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
            self._cache[key] = (time.time(), list(result))

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class SkillRegistry:
    """Central catalog of executable intelligence.

    Maintains fast indexes for skill lookup by ID, name, category, capability, and alias.
    Thread-safe and supports lazy loading of skill handler executors.
    """

    def __init__(
        self,
        event_bus: Any | None = None,
        matchers: Optional[List[BaseSkillMatcher]] = None,
    ) -> None:
        self._skills: Dict[str, Skill] = {}
        self._name_index: Dict[str, str] = {}  # norm(name) -> skill_id
        self._alias_index: Dict[str, str] = {}  # norm(alias) -> skill_id
        self._category_index: Dict[str, Set[str]] = {}  # category -> set(skill_id)
        self._capability_index: Dict[str, Set[str]] = {}  # capability -> set(skill_id)
        
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._cache = IntentCache(max_size=256, ttl_seconds=60.0)

        # Default matchers pipeline: Multilingual (wrapping KeywordAlias) and optional Embedding matcher
        self._matchers: List[BaseSkillMatcher] = matchers or [
            MultilingualSkillMatcher(KeywordAliasSkillMatcher()),
            EmbeddingSkillMatcher(),
        ]

    # ------------------------------------------------------------------
    # Registration & Lifecycle
    # ------------------------------------------------------------------

    def register_skill(self, skill: Skill) -> None:
        """Register a new skill in the catalog.

        Parameters
        ----------
        skill : Skill
            Skill descriptor to register.
        """
        with self._lock:
            if skill.id in self._skills:
                _LOG.debug("Overwriting registered skill: %s", skill.id)
                self.unregister_skill(skill.id)

            self._skills[skill.id] = skill

            # Index by normalized name
            norm_name = skill.name.lower().strip()
            self._name_index[norm_name] = skill.id

            # Index by aliases
            for alias in skill.aliases:
                norm_alias = alias.lower().strip()
                self._alias_index[norm_alias] = skill.id

            # Index by category
            cat = skill.category.lower().strip()
            if cat not in self._category_index:
                self._category_index[cat] = set()
            self._category_index[cat].add(skill.id)

            # Index by required capabilities
            for cap in skill.required_capabilities:
                norm_cap = cap.lower().strip()
                if norm_cap not in self._capability_index:
                    self._capability_index[norm_cap] = set()
                self._capability_index[norm_cap].add(skill.id)

            self._cache.clear()
            _LOG.info("Registered skill '%s' (%s)", skill.name, skill.id)

            if self._event_bus:
                try:
                    if hasattr(self._event_bus, "publish"):
                        self._event_bus.publish("SKILL_REGISTERED", {"skill_id": skill.id, "skill_name": skill.name})
                    elif hasattr(self._event_bus, "emit"):
                        res = self._event_bus.emit("SKILL_REGISTERED", {"skill_id": skill.id, "skill_name": skill.name})
                        if hasattr(res, "__await__"):
                            try:
                                import asyncio
                                loop = asyncio.get_running_loop()
                                loop.create_task(res)
                            except RuntimeError:
                                pass
                except Exception as err:
                    _LOG.warning("Failed publishing SKILL_REGISTERED event: %s", err)

    def unregister_skill(self, skill_id: str) -> Optional[Skill]:
        """Remove a skill from the catalog by ID."""
        with self._lock:
            if skill_id not in self._skills:
                return None

            skill = self._skills.pop(skill_id)

            # Remove from indexes
            norm_name = skill.name.lower().strip()
            if self._name_index.get(norm_name) == skill_id:
                del self._name_index[norm_name]

            for alias in skill.aliases:
                norm_alias = alias.lower().strip()
                if self._alias_index.get(norm_alias) == skill_id:
                    del self._alias_index[norm_alias]

            cat = skill.category.lower().strip()
            if cat in self._category_index:
                self._category_index[cat].discard(skill_id)

            for cap in skill.required_capabilities:
                norm_cap = cap.lower().strip()
                if norm_cap in self._capability_index:
                    self._capability_index[norm_cap].discard(skill_id)

            self._cache.clear()
            _LOG.info("Unregistered skill '%s'", skill_id)

            if self._event_bus:
                try:
                    if hasattr(self._event_bus, "publish"):
                        self._event_bus.publish("SKILL_UNREGISTERED", {"skill_id": skill_id})
                    elif hasattr(self._event_bus, "emit"):
                        res = self._event_bus.emit("SKILL_UNREGISTERED", {"skill_id": skill_id})
                        if hasattr(res, "__await__"):
                            try:
                                import asyncio
                                loop = asyncio.get_running_loop()
                                loop.create_task(res)
                            except RuntimeError:
                                pass
                except Exception as err:
                    _LOG.warning("Failed publishing SKILL_UNREGISTERED event: %s", err)

            return skill

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Retrieve skill descriptor by ID."""
        with self._lock:
            return self._skills.get(skill_id)

    def list_skills(self) -> List[Skill]:
        """List all registered skills."""
        with self._lock:
            return list(self._skills.values())

    # ------------------------------------------------------------------
    # Discovery APIs
    # ------------------------------------------------------------------

    def find_skill_by_name(self, name: str) -> Optional[Skill]:
        """Find a skill by exact name or alias (case-insensitive)."""
        with self._lock:
            norm = name.lower().strip()
            # 1. Check ID directly
            if norm in self._skills:
                return self._skills[norm]
            # 2. Check Name index
            if norm in self._name_index:
                return self._skills.get(self._name_index[norm])
            # 3. Check Alias index
            if norm in self._alias_index:
                return self._skills.get(self._alias_index[norm])

            # 4. Fallback search across names
            for skill in self._skills.values():
                if skill.name.lower().strip() == norm:
                    return skill
            return None

    def find_skills_by_category(self, category: Union[SkillCategory, str]) -> List[Skill]:
        """Find all skills belonging to a given category."""
        cat_str = category.value if isinstance(category, SkillCategory) else str(category)
        norm_cat = cat_str.lower().strip()
        with self._lock:
            skill_ids = self._category_index.get(norm_cat, set())
            return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def find_skills_by_capability(self, capability_name: str) -> List[Skill]:
        """Find all skills that require a specific capability."""
        norm_cap = capability_name.lower().strip()
        with self._lock:
            skill_ids = self._capability_index.get(norm_cap, set())
            return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def find_skill_by_intent(
        self,
        intent: str,
        min_confidence: float = 0.4,
        available_capabilities: Optional[List[str]] = None,
    ) -> List[SkillMatch]:
        """Match user intent against all registered skills using matchers pipeline and caching."""
        if not intent:
            return []

        cache_key = f"{intent.lower().strip()}::min={min_confidence}"
        if available_capabilities is not None:
            cache_key += f"::caps={','.join(sorted(available_capabilities))}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        with self._lock:
            all_skills = list(self._skills.values())

        if not all_skills:
            return []

        config = SkillMatchConfig(min_confidence=min_confidence)
        matched_dict: Dict[str, SkillMatch] = {}

        for matcher in self._matchers:
            try:
                results = matcher.match(intent, all_skills, config)
                for res in results:
                    if res.skill.id not in matched_dict or res.confidence > matched_dict[res.skill.id].confidence:
                        matched_dict[res.skill.id] = res
            except Exception as err:
                _LOG.warning("Matcher '%s' failed during intent query: %s", matcher.__class__.__name__, err)

        candidates = list(matched_dict.values())

        # Validate capabilities if supplied
        if available_capabilities is not None:
            caps_set = {c.lower().strip() for c in available_capabilities}
            for candidate in candidates:
                missing = [
                    cap for cap in candidate.skill.required_capabilities
                    if cap.lower().strip() not in caps_set
                ]
                candidate.missing_capabilities = missing
                candidate.is_executable = len(missing) == 0
                if missing:
                    # Penalize confidence if missing required capabilities
                    candidate.confidence *= 0.5

        # Sort by executable status first, then highest confidence
        candidates.sort(key=lambda m: (m.is_executable, m.confidence), reverse=True)
        filtered = [c for c in candidates if c.confidence >= min_confidence]

        self._cache.put(cache_key, filtered)
        return filtered

    def find_best_skill(
        self,
        intent: str,
        available_capabilities: Optional[List[str]] = None,
    ) -> Optional[Skill]:
        """Find the single best executable skill for a given user intent."""
        matches = self.find_skill_by_intent(
            intent=intent,
            min_confidence=0.4,
            available_capabilities=available_capabilities,
        )
        if not matches:
            return None

        # Prefer highest confidence executable candidate
        for m in matches:
            if m.is_executable:
                return m.skill

        return matches[0].skill if matches else None
