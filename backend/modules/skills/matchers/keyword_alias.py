"""
Keyword & Alias Matcher — Exact ID/Name, Alias, Tag, and Token Similarity matching.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set

from backend.modules.skills.matchers.base import BaseSkillMatcher
from backend.modules.skills.models import Skill, SkillMatch, SkillMatchConfig


def _normalize(text: str) -> str:
    """Normalize string for robust token matching."""
    text = text.lower().strip()
    return re.sub(r"[^\w\s]", " ", text)


def _get_tokens(text: str) -> Set[str]:
    """Extract set of normalized tokens."""
    return set(_normalize(text).split())


def _jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Compute Jaccard token set similarity."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / float(union) if union > 0 else 0.0


class KeywordAliasSkillMatcher(BaseSkillMatcher):
    """Matcher that scores skills based on ID, name, aliases, tags, and token similarity."""

    def match(
        self,
        intent: str,
        skills: List[Skill],
        config: Optional[SkillMatchConfig] = None,
    ) -> List[SkillMatch]:
        cfg = config or SkillMatchConfig()
        norm_intent = _normalize(intent)
        intent_tokens = _get_tokens(intent)

        if not norm_intent or not skills:
            return []

        matches: List[SkillMatch] = []

        for skill in skills:
            reasons: List[str] = []
            confidence = 0.0

            norm_id = _normalize(skill.id)
            norm_name = _normalize(skill.name)
            name_tokens = _get_tokens(skill.name)

            # 1. Exact ID or Exact Name match
            if norm_intent == norm_id or norm_intent == norm_name:
                confidence = cfg.exact_match_score
                reasons.append("Exact name or ID match")
            # 2. Substring match in ID or Name
            elif norm_intent in norm_name or norm_name in norm_intent:
                confidence = max(confidence, 0.9)
                reasons.append("Name substring match")
            
            # 3. Aliases match
            for alias in skill.aliases:
                norm_alias = _normalize(alias)
                if norm_intent == norm_alias:
                    if cfg.alias_match_score > confidence:
                        confidence = cfg.alias_match_score
                        reasons.append(f"Exact alias match ('{alias}')")
                elif norm_intent in norm_alias or norm_alias in norm_intent:
                    score = 0.85
                    if score > confidence:
                        confidence = score
                        reasons.append(f"Alias substring match ('{alias}')")

            # 4. Tags match
            for tag in skill.tags:
                norm_tag = _normalize(tag)
                if norm_tag and norm_tag in norm_intent:
                    score = cfg.tag_match_score
                    if score > confidence:
                        confidence = score
                        reasons.append(f"Tag match ('{tag}')")

            # 5. Token set overlap / Jaccard similarity
            sim = _jaccard_similarity(intent_tokens, name_tokens)
            if sim > 0.0:
                token_score = round(sim * 0.85, 3)
                if token_score > confidence:
                    confidence = token_score
                    reasons.append(f"Token overlap similarity ({sim:.2f})")

            # 6. Description keyword match bonus
            if confidence < 0.7 and skill.description:
                desc_tokens = _get_tokens(skill.description)
                desc_sim = _jaccard_similarity(intent_tokens, desc_tokens)
                if desc_sim > 0.3 and desc_sim * 0.7 > confidence:
                    confidence = round(desc_sim * 0.7, 3)
                    reasons.append("Description relevance match")

            if confidence >= cfg.min_confidence:
                matches.append(
                    SkillMatch(
                        skill=skill,
                        confidence=confidence,
                        matching_reasons=reasons,
                    )
                )

        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[: cfg.top_k]
