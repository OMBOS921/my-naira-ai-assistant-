"""
PersonalityEngine — JARVIS-like character memory and adaptive personality.

Remembers user preferences, learns communication style, adapts tone
across sessions. Injects personality context into the prompt system.

Conforms to ``ModuleInterface`` (``backend/types.py``).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.modules.personality.sentiment_analyzer import SentimentAnalyzer, SentimentResult

_LOG = logging.getLogger("naira.personality")


@dataclass
class UserPreferences:
    """Persistent user personality preferences."""
    preferred_language: str = "hinglish"  # hindi, english, hinglish
    formality_level: str = "casual"  # formal, casual, adaptive
    humor_enabled: bool = True
    verbosity: str = "balanced"  # brief, balanced, detailed
    preferred_name: str = ""
    interests: list[str] = field(default_factory=list)
    communication_style: str = "friendly"  # friendly, professional, playful
    last_updated: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_language": self.preferred_language,
            "formality_level": self.formality_level,
            "humor_enabled": self.humor_enabled,
            "verbosity": self.verbosity,
            "preferred_name": self.preferred_name,
            "interests": self.interests,
            "communication_style": self.communication_style,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserPreferences:
        return cls(
            preferred_language=data.get("preferred_language", "hinglish"),
            formality_level=data.get("formality_level", "casual"),
            humor_enabled=data.get("humor_enabled", True),
            verbosity=data.get("verbosity", "balanced"),
            preferred_name=data.get("preferred_name", ""),
            interests=data.get("interests", []),
            communication_style=data.get("communication_style", "friendly"),
            last_updated=data.get("last_updated", 0.0),
        )


@dataclass
class InteractionStats:
    """Tracks interaction patterns for learning."""
    total_messages: int = 0
    average_message_length: float = 0.0
    common_topics: dict[str, int] = field(default_factory=dict)
    active_hours: dict[int, int] = field(default_factory=dict)  # hour -> count
    session_count: int = 0
    last_session: float = 0.0

    def record_message(self, text: str) -> None:
        """Record a new message for pattern learning."""
        self.total_messages += 1
        msg_len = len(text.split())
        # Running average
        self.average_message_length = (
            (self.average_message_length * (self.total_messages - 1) + msg_len) / self.total_messages
        )
        # Track active hours
        import datetime
        hour = datetime.datetime.now().hour
        self.active_hours[hour] = self.active_hours.get(hour, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_messages": self.total_messages,
            "average_message_length": round(self.average_message_length, 1),
            "common_topics": dict(self.common_topics),
            "active_hours": {str(k): v for k, v in self.active_hours.items()},
            "session_count": self.session_count,
            "last_session": self.last_session,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InteractionStats:
        stats = cls(
            total_messages=data.get("total_messages", 0),
            average_message_length=data.get("average_message_length", 0.0),
            common_topics=data.get("common_topics", {}),
            session_count=data.get("session_count", 0),
            last_session=data.get("last_session", 0.0),
        )
        hours = data.get("active_hours", {})
        stats.active_hours = {int(k): v for k, v in hours.items()}
        return stats


class PersonalityEngine:
    """JARVIS-like personality layer with memory and adaptation.

    Conforms to ``ModuleInterface`` for boot integration.
    """

    def __init__(
        self,
        personality_dir: Path | None = None,
        event_bus: Any = None,
    ) -> None:
        self._personality_dir = personality_dir
        self._event_bus = event_bus
        self._logger = _LOG
        self._preferences = UserPreferences()
        self._stats = InteractionStats()
        self._sentiment = SentimentAnalyzer(history_size=30)
        self._initialized = False
        self._degraded = False

        # JARVIS character traits
        self._character = {
            "name": "Naira",
            "role": "Personal AI Assistant",
            "personality_traits": [
                "witty", "intelligent", "loyal", "proactive",
                "slightly sarcastic when appropriate", "protective",
            ],
            "speaking_style": "Uses Hinglish naturally, mixes Hindi and English seamlessly",
            "relationship": "Trusted AI companion who knows user deeply",
        }

    # ------------------------------------------------------------------
    # ModuleInterface compliance
    # ------------------------------------------------------------------

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self, reason: str = "") -> None:
        self._degraded = True
        self._logger.warning("PersonalityEngine degraded: %s", reason)

    async def async_init(self) -> None:
        """Load persisted personality data."""
        try:
            if self._personality_dir:
                self._personality_dir.mkdir(parents=True, exist_ok=True)
                self._load_preferences()
                self._load_stats()
            self._initialized = True
            self._logger.info("[PERSONALITY] Engine initialized with %d messages tracked", self._stats.total_messages)
        except Exception as exc:
            self._logger.error("[PERSONALITY] Init failed: %s", exc)
            self.degrade(str(exc))
            self._initialized = True  # Still mark as initialized

    async def async_shutdown(self) -> None:
        """Persist personality data."""
        try:
            if self._personality_dir:
                self._save_preferences()
                self._save_stats()
            self._logger.info("[PERSONALITY] Engine shut down, data persisted.")
        except Exception as exc:
            self._logger.error("[PERSONALITY] Shutdown save failed: %s", exc)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def process_message(self, text: str) -> SentimentResult:
        """Process a user message: analyze sentiment and record stats."""
        self._stats.record_message(text)
        result = self._sentiment.analyze(text)
        self._logger.debug(
            "[PERSONALITY] Mood=%s valence=%.2f arousal=%.2f keywords=%s",
            result.mood.value, result.valence, result.arousal, result.keywords_matched,
        )
        return result

    def get_personality_context(self) -> str:
        """Generate personality context string for prompt injection."""
        prefs = self._preferences
        tone = self._sentiment.get_tone_adjustment()
        name_ref = f" Their name is {prefs.preferred_name}." if prefs.preferred_name else ""

        ctx_parts = [
            f"## Personality Context",
            f"You are {self._character['name']}, a {self._character['role']}.",
            f"Personality: {', '.join(self._character['personality_traits'])}.",
            f"Style: {self._character['speaking_style']}.",
            f"Relationship: {self._character['relationship']}.{name_ref}",
            f"",
            f"## User Preferences",
            f"- Language: {prefs.preferred_language}",
            f"- Communication: {prefs.communication_style}",
            f"- Formality: {prefs.formality_level}",
            f"- Humor: {'enabled' if prefs.humor_enabled else 'disabled'}",
            f"- Verbosity: {prefs.verbosity}",
        ]

        if prefs.interests:
            ctx_parts.append(f"- Interests: {', '.join(prefs.interests)}")

        # Add emotional intelligence context
        ctx_parts.extend([
            f"",
            f"## Emotional Context",
            f"- Current mood trend: {self._sentiment.mood_trend.value}",
            f"- Tone guidance: {tone['instruction']}",
            f"- Response tone: {tone['tone']}",
        ])

        if self._stats.total_messages > 10:
            ctx_parts.extend([
                f"",
                f"## Interaction History",
                f"- Total interactions: {self._stats.total_messages}",
                f"- User typically writes {'short' if self._stats.average_message_length < 8 else 'detailed'} messages",
            ])

        return "\n".join(ctx_parts)

    def update_preferences(self, **kwargs: Any) -> None:
        """Update user preferences."""
        for key, value in kwargs.items():
            if hasattr(self._preferences, key):
                setattr(self._preferences, key, value)
        self._preferences.last_updated = time.time()
        if self._personality_dir:
            self._save_preferences()

    def get_greeting(self) -> str:
        """Generate a contextual greeting based on time and mood."""
        import datetime
        hour = datetime.datetime.now().hour

        name = self._preferences.preferred_name or "Sir"

        if hour < 5:
            time_greeting = f"Late night, {name}? Aap abhi tak jage hain"
        elif hour < 12:
            time_greeting = f"Good morning, {name}"
        elif hour < 17:
            time_greeting = f"Good afternoon, {name}"
        elif hour < 21:
            time_greeting = f"Good evening, {name}"
        else:
            time_greeting = f"Raat ho gayi, {name}"

        if self._stats.session_count == 0:
            return f"{time_greeting}. Main Naira hoon — aapki personal AI assistant. Kaise madad kar sakti hoon?"
        elif self._sentiment.is_user_frustrated:
            return f"{time_greeting}. Pichli baar kuch issues the — aaj sab sorted kar dete hain."
        else:
            return f"{time_greeting}. Kya karna hai aaj?"

    @property
    def sentiment_analyzer(self) -> SentimentAnalyzer:
        """Access the sentiment analyzer."""
        return self._sentiment

    def health_report(self) -> dict[str, Any]:
        """Generate health report."""
        return {
            "initialized": self._initialized,
            "degraded": self._degraded,
            "preferences": self._preferences.to_dict(),
            "stats": self._stats.to_dict(),
            "sentiment": self._sentiment.to_dict(),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_preferences(self) -> None:
        """Load preferences from disk."""
        if not self._personality_dir:
            return
        prefs_file = self._personality_dir / "preferences.json"
        if prefs_file.is_file():
            try:
                data = json.loads(prefs_file.read_text(encoding="utf-8"))
                self._preferences = UserPreferences.from_dict(data)
                self._logger.debug("[PERSONALITY] Preferences loaded from %s", prefs_file)
            except Exception as exc:
                self._logger.warning("[PERSONALITY] Failed to load preferences: %s", exc)

    def _save_preferences(self) -> None:
        """Save preferences to disk."""
        if not self._personality_dir:
            return
        prefs_file = self._personality_dir / "preferences.json"
        try:
            prefs_file.write_text(
                json.dumps(self._preferences.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            self._logger.warning("[PERSONALITY] Failed to save preferences: %s", exc)

    def _load_stats(self) -> None:
        """Load interaction stats from disk."""
        if not self._personality_dir:
            return
        stats_file = self._personality_dir / "interaction_stats.json"
        if stats_file.is_file():
            try:
                data = json.loads(stats_file.read_text(encoding="utf-8"))
                self._stats = InteractionStats.from_dict(data)
                self._logger.debug("[PERSONALITY] Stats loaded: %d messages tracked", self._stats.total_messages)
            except Exception as exc:
                self._logger.warning("[PERSONALITY] Failed to load stats: %s", exc)

    def _save_stats(self) -> None:
        """Save interaction stats to disk."""
        if not self._personality_dir:
            return
        stats_file = self._personality_dir / "interaction_stats.json"
        try:
            stats_file.write_text(
                json.dumps(self._stats.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            self._logger.warning("[PERSONALITY] Failed to save stats: %s", exc)
