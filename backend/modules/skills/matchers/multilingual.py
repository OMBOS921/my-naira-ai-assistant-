"""
Multilingual Skill Matcher — Normalized multilingual synonym and translation intent matcher.

Provides multi-language support (English, Yoruba, Igbo, Hausa, Nigerian Pidgin,
Spanish, French, German, Chinese, etc.) by mapping non-English intents into
canonical task terms before confidence scoring.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from backend.modules.skills.matchers.base import BaseSkillMatcher
from backend.modules.skills.matchers.keyword_alias import KeywordAliasSkillMatcher
from backend.modules.skills.models import Skill, SkillMatch, SkillMatchConfig


# Multilingual canonical mappings dictionary
_MULTILINGUAL_INTENT_MAP: Dict[str, str] = {
    # Spanish
    "abrir sitio web": "open website",
    "navegar sitio": "open website",
    "buscar en la web": "search web",
    "revisar codigo": "code review",
    "revision de codigo": "code review",
    "operaciones git": "git operations",
    "diagnostico del sistema": "system diagnostics",
    "instalacion de software": "software installation",
    "analisis de pdf": "pdf analysis",
    "compilar proyecto": "project build",
    # French
    "ouvrir le site": "open website",
    "rechercher sur le web": "search web",
    "revue de code": "code review",
    "analyse pdf": "pdf analysis",
    "diagnostic systeme": "system diagnostics",
    "installation de logiciel": "software installation",
    # Yoruba
    "sii oju opo webu": "open website",
    "siestin oju opo webu": "open website",
    "wadi lori interneti": "search web",
    "yewo koodu": "code review",
    "ayewo koodu": "code review",
    "ayewo ero": "system diagnostics",
    # Hausa
    "bude gidan yanar gizo": "open website",
    "bincika yanar gizo": "search web",
    "duba lambar komputa": "code review",
    "gwada tsarin komputa": "system diagnostics",
    # Igbo
    "ghee shite webu": "open website",
    "chọọ n'intanet": "search web",
    "lọghachie koodu": "code review",
    "nyocha sistemu": "system diagnostics",
    # Nigerian Pidgin
    "open website": "open website",
    "open site": "open website",
    "search web": "search web",
    "check web": "search web",
    "check code": "code review",
    "review code": "code review",
    "build project": "project build",
    "check system": "system diagnostics",
    "install software": "software installation",
    # German
    "webseite offnen": "open website",
    "web suchen": "search web",
    "code uberprufen": "code review",
    "systemdiagnose": "system diagnostics",
    # Chinese
    "打开网站": "open website",
    "网络搜索": "search web",
    "代码审查": "code review",
    "系统诊断": "system diagnostics",
}


def _normalize(text: str) -> str:
    """Normalize string removing diacritics and special punctuation."""
    text = text.lower().strip()
    return re.sub(r"[^\w\s]", "", text)


class MultilingualSkillMatcher(BaseSkillMatcher):
    """Matcher that maps multilingual intent queries to canonical intent terms before matching."""

    def __init__(self, fallback_matcher: Optional[BaseSkillMatcher] = None) -> None:
        self._fallback_matcher = fallback_matcher or KeywordAliasSkillMatcher()

    def match(
        self,
        intent: str,
        skills: List[Skill],
        config: Optional[SkillMatchConfig] = None,
    ) -> List[SkillMatch]:
        cfg = config or SkillMatchConfig()
        norm_intent = _normalize(intent)

        # Direct evaluation with fallback matcher first
        matches = self._fallback_matcher.match(intent, skills, cfg)
        if matches and matches[0].confidence >= 0.8:
            return matches

        # Check multilingual intent translations
        canonical_intent = None
        for key, val in _MULTILINGUAL_INTENT_MAP.items():
            norm_key = _normalize(key)
            if norm_key in norm_intent or norm_intent in norm_key:
                canonical_intent = val
                break

        if canonical_intent:
            canonical_matches = self._fallback_matcher.match(canonical_intent, skills, cfg)
            for m in canonical_matches:
                # Slightly adjust confidence for translated match if needed
                m.confidence = min(m.confidence, 0.95)
                m.matching_reasons.append(f"Multilingual translation match ('{intent}' -> '{canonical_intent}')")

            # Merge results preferring highest confidence
            all_matches: Dict[str, SkillMatch] = {}
            for m in matches + canonical_matches:
                if m.skill.id not in all_matches or m.confidence > all_matches[m.skill.id].confidence:
                    all_matches[m.skill.id] = m

            sorted_matches = sorted(all_matches.values(), key=lambda x: x.confidence, reverse=True)
            return sorted_matches[: cfg.top_k]

        return matches
