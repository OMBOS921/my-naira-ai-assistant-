"""
Embedding Skill Matcher — Vector embedding & semantic similarity matcher hook.

Provides an extensible vector-based intent matcher for future LLM / vector database integration
without requiring structural changes to the Skill Registry or Engine.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional

from backend.modules.skills.matchers.base import BaseSkillMatcher
from backend.modules.skills.models import Skill, SkillMatch, SkillMatchConfig

_LOG = logging.getLogger("naira.skills.matchers.embedding")


class EmbeddingSkillMatcher(BaseSkillMatcher):
    """Extensible vector embedding matcher hook.

    Parameters
    ----------
    embedding_func : Optional[Callable[[str], List[float]]]
        Optional vector embedding function generating float vectors for text.
    cosine_sim_func : Optional[Callable[[List[float], List[float]], float]]
        Optional cosine similarity function.
    """

    def __init__(
        self,
        embedding_func: Optional[Callable[[str], List[float]]] = None,
        cosine_sim_func: Optional[Callable[[List[float], List[float]], float]] = None,
    ) -> None:
        self._embedding_func = embedding_func
        self._cosine_sim_func = cosine_sim_func
        self._skill_vector_cache: dict[str, List[float]] = {}

    def is_available(self) -> bool:
        """Return True if an embedding function provider is registered."""
        return self._embedding_func is not None

    def match(
        self,
        intent: str,
        skills: List[Skill],
        config: Optional[SkillMatchConfig] = None,
    ) -> List[SkillMatch]:
        cfg = config or SkillMatchConfig()

        if not self.is_available() or not self._embedding_func or not intent:
            return []

        try:
            intent_vec = self._embedding_func(intent)
            matches: List[SkillMatch] = []

            for skill in skills:
                if skill.id not in self._skill_vector_cache:
                    text_to_embed = f"{skill.name}. {skill.description}. {' '.join(skill.tags)}"
                    self._skill_vector_cache[skill.id] = self._embedding_func(text_to_embed)

                skill_vec = self._skill_vector_cache[skill.id]
                score = 0.0

                if self._cosine_sim_func:
                    score = self._cosine_sim_func(intent_vec, skill_vec)
                else:
                    # Default dot product / normalized similarity approximation
                    dot = sum(a * b for a, b in zip(intent_vec, skill_vec))
                    score = max(0.0, min(1.0, float(dot)))

                if score >= cfg.min_confidence:
                    matches.append(
                        SkillMatch(
                            skill=skill,
                            confidence=round(score, 3),
                            matching_reasons=[f"Vector embedding similarity ({score:.3f})"],
                        )
                    )

            matches.sort(key=lambda m: m.confidence, reverse=True)
            return matches[: cfg.top_k]
        except Exception as err:
            _LOG.warning("Embedding matcher execution failed: %s", err)
            return []
