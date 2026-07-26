"""
Base Skill Matcher — Abstract interface for skill intent matchers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from backend.modules.skills.models import Skill, SkillMatch, SkillMatchConfig


class BaseSkillMatcher(ABC):
    """Abstract base class for intent matching strategies."""

    @abstractmethod
    def match(
        self,
        intent: str,
        skills: List[Skill],
        config: Optional[SkillMatchConfig] = None,
    ) -> List[SkillMatch]:
        """Score and match registered skills against user intent string.

        Parameters
        ----------
        intent : str
            Raw or normalized user intent query.
        skills : List[Skill]
            Candidates list of available skill descriptors.
        config : Optional[SkillMatchConfig]
            Matching parameters and score thresholds.

        Returns
        -------
        List[SkillMatch]
            List of match candidate objects with confidence score and reasons.
        """
        pass
