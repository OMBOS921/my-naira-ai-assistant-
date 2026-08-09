"""
SentimentAnalyzer — Real-time sentiment scoring for emotional intelligence.

Detects user mood from text using keyword-based scoring and intensity analysis.
Tracks mood across conversation turns for trend awareness.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

_LOG = logging.getLogger("naira.personality.sentiment")


class Mood(StrEnum):
    """Detected emotional mood categories."""
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    NEUTRAL = "neutral"
    CONFUSED = "confused"
    ANXIOUS = "anxious"
    GRATEFUL = "grateful"
    SARCASTIC = "sarcastic"


@dataclass
class SentimentResult:
    """Result of sentiment analysis on a single message."""
    mood: Mood
    confidence: float  # 0.0 – 1.0
    valence: float  # -1.0 (negative) to +1.0 (positive)
    arousal: float  # 0.0 (calm) to 1.0 (intense)
    keywords_matched: list[str] = field(default_factory=list)


# Keyword → (mood, valence, arousal) mapping
_SENTIMENT_KEYWORDS: dict[str, tuple[Mood, float, float]] = {
    # Happy / Positive
    "thank": (Mood.GRATEFUL, 0.8, 0.4),
    "thanks": (Mood.GRATEFUL, 0.8, 0.4),
    "shukriya": (Mood.GRATEFUL, 0.8, 0.4),
    "dhanyavaad": (Mood.GRATEFUL, 0.8, 0.4),
    "awesome": (Mood.HAPPY, 0.9, 0.7),
    "great": (Mood.HAPPY, 0.7, 0.5),
    "amazing": (Mood.HAPPY, 0.9, 0.8),
    "love": (Mood.HAPPY, 0.9, 0.6),
    "perfect": (Mood.HAPPY, 0.8, 0.5),
    "nice": (Mood.HAPPY, 0.6, 0.3),
    "good": (Mood.HAPPY, 0.5, 0.3),
    "accha": (Mood.HAPPY, 0.5, 0.3),
    "badhiya": (Mood.HAPPY, 0.7, 0.4),
    "mast": (Mood.HAPPY, 0.7, 0.5),
    "zabardast": (Mood.EXCITED, 0.9, 0.9),
    "wow": (Mood.EXCITED, 0.8, 0.8),
    "excited": (Mood.EXCITED, 0.8, 0.9),
    "yay": (Mood.EXCITED, 0.8, 0.8),

    # Sad / Negative
    "sad": (Mood.SAD, -0.7, 0.3),
    "upset": (Mood.SAD, -0.6, 0.4),
    "disappointed": (Mood.SAD, -0.6, 0.3),
    "dukhi": (Mood.SAD, -0.7, 0.3),
    "sorry": (Mood.SAD, -0.3, 0.2),
    "miss": (Mood.SAD, -0.4, 0.3),

    # Angry / Frustrated
    "angry": (Mood.ANGRY, -0.8, 0.9),
    "annoyed": (Mood.ANGRY, -0.6, 0.6),
    "stupid": (Mood.FRUSTRATED, -0.7, 0.7),
    "useless": (Mood.FRUSTRATED, -0.8, 0.7),
    "broken": (Mood.FRUSTRATED, -0.6, 0.6),
    "kaam nahi": (Mood.FRUSTRATED, -0.7, 0.7),
    "fix": (Mood.FRUSTRATED, -0.3, 0.5),
    "error": (Mood.FRUSTRATED, -0.5, 0.6),
    "bug": (Mood.FRUSTRATED, -0.5, 0.6),
    "hate": (Mood.ANGRY, -0.9, 0.9),
    "worst": (Mood.ANGRY, -0.9, 0.8),
    "gussa": (Mood.ANGRY, -0.8, 0.9),

    # Confused
    "confused": (Mood.CONFUSED, -0.2, 0.4),
    "what": (Mood.CONFUSED, -0.1, 0.3),
    "how": (Mood.CONFUSED, -0.1, 0.3),
    "why": (Mood.CONFUSED, -0.2, 0.4),
    "samajh nahi": (Mood.CONFUSED, -0.3, 0.4),
    "kya": (Mood.CONFUSED, -0.1, 0.3),

    # Anxious
    "worried": (Mood.ANXIOUS, -0.5, 0.6),
    "nervous": (Mood.ANXIOUS, -0.4, 0.6),
    "scared": (Mood.ANXIOUS, -0.6, 0.7),
    "tension": (Mood.ANXIOUS, -0.5, 0.6),
    "dar": (Mood.ANXIOUS, -0.5, 0.6),

    # Sarcastic
    "obviously": (Mood.SARCASTIC, -0.2, 0.4),
    "sure": (Mood.SARCASTIC, 0.0, 0.3),
    "really": (Mood.SARCASTIC, -0.1, 0.3),
    "wah wah": (Mood.SARCASTIC, -0.3, 0.5),
}

# Intensifiers that amplify sentiment
_INTENSIFIERS = {"very", "bahut", "really", "so", "extremely", "super", "ekdum", "bilkul", "totally"}

# Negators that flip sentiment
_NEGATORS = {"not", "nahi", "na", "no", "never", "don't", "doesn't", "didn't", "mat", "kabhi nahi"}


class SentimentAnalyzer:
    """Analyzes text sentiment and tracks mood across turns."""

    def __init__(self, history_size: int = 20) -> None:
        self._history: list[SentimentResult] = []
        self._history_size = history_size

    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of a single message."""
        lower = text.lower().strip()
        words = re.findall(r'\b\w+\b', lower)

        matched_keywords: list[str] = []
        moods: list[Mood] = []
        valences: list[float] = []
        arousals: list[float] = []

        has_negator = bool(set(words) & _NEGATORS)
        has_intensifier = bool(set(words) & _INTENSIFIERS)

        # Check multi-word keywords first
        for keyword, (mood, valence, arousal) in _SENTIMENT_KEYWORDS.items():
            if keyword in lower:
                matched_keywords.append(keyword)
                moods.append(mood)

                # Apply intensifier
                if has_intensifier:
                    valence = min(1.0, max(-1.0, valence * 1.4))
                    arousal = min(1.0, arousal * 1.3)

                # Apply negator (flip valence)
                if has_negator:
                    valence = -valence * 0.7

                valences.append(valence)
                arousals.append(arousal)

        # Punctuation analysis
        exclamation_count = text.count("!")
        question_count = text.count("?")
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)

        # Exclamations increase arousal
        arousal_boost = min(0.3, exclamation_count * 0.1)
        # ALL CAPS indicates strong emotion
        if caps_ratio > 0.5 and len(text) > 5:
            arousal_boost += 0.2

        if not moods:
            # No keywords matched — default to neutral
            # But questions lean slightly confused
            if question_count > 0:
                mood = Mood.CONFUSED
                valence = -0.1
            else:
                mood = Mood.NEUTRAL
                valence = 0.0
            arousal = 0.2 + arousal_boost
            confidence = 0.3
        else:
            # Use the most frequent mood, or the one with highest arousal
            from collections import Counter
            mood_counts = Counter(moods)
            mood = mood_counts.most_common(1)[0][0]
            valence = sum(valences) / len(valences)
            arousal = min(1.0, sum(arousals) / len(arousals) + arousal_boost)
            confidence = min(1.0, 0.4 + len(matched_keywords) * 0.15)

        result = SentimentResult(
            mood=mood,
            confidence=round(confidence, 2),
            valence=round(valence, 2),
            arousal=round(min(1.0, arousal), 2),
            keywords_matched=matched_keywords,
        )

        # Track history
        self._history.append(result)
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size:]

        return result

    @property
    def mood_trend(self) -> Mood:
        """Return the dominant mood across recent history."""
        if not self._history:
            return Mood.NEUTRAL
        from collections import Counter
        moods = [r.mood for r in self._history[-5:]]
        return Counter(moods).most_common(1)[0][0]

    @property
    def average_valence(self) -> float:
        """Return average valence across recent history (-1 to +1)."""
        if not self._history:
            return 0.0
        recent = self._history[-5:]
        return round(sum(r.valence for r in recent) / len(recent), 2)

    @property
    def is_user_frustrated(self) -> bool:
        """Check if user shows sustained frustration."""
        recent = self._history[-3:]
        return len(recent) >= 2 and all(
            r.mood in (Mood.FRUSTRATED, Mood.ANGRY) for r in recent
        )

    @property
    def is_user_happy(self) -> bool:
        """Check if user shows sustained happiness."""
        recent = self._history[-3:]
        return len(recent) >= 2 and all(
            r.mood in (Mood.HAPPY, Mood.EXCITED, Mood.GRATEFUL) for r in recent
        )

    def get_tone_adjustment(self) -> dict[str, Any]:
        """Return tone adjustment parameters for the LLM prompt."""
        trend = self.mood_trend
        valence = self.average_valence

        if self.is_user_frustrated:
            return {
                "tone": "empathetic_and_helpful",
                "instruction": "User seems frustrated. Be extra patient, acknowledge their frustration, and provide clear actionable solutions. Avoid being overly cheerful.",
                "formality": "professional",
            }
        elif self.is_user_happy:
            return {
                "tone": "warm_and_enthusiastic",
                "instruction": "User is in a great mood! Match their energy, be warm and engaging. Feel free to use humor.",
                "formality": "casual",
            }
        elif trend == Mood.CONFUSED:
            return {
                "tone": "patient_and_clear",
                "instruction": "User seems confused. Break down explanations into simple steps. Ask clarifying questions if needed.",
                "formality": "professional",
            }
        elif trend == Mood.ANXIOUS:
            return {
                "tone": "reassuring_and_calm",
                "instruction": "User seems anxious. Be reassuring, provide concrete information, and avoid uncertainty.",
                "formality": "professional",
            }
        elif trend == Mood.SAD:
            return {
                "tone": "compassionate",
                "instruction": "User seems down. Be gentle and supportive. Offer help proactively.",
                "formality": "warm",
            }
        else:
            return {
                "tone": "balanced",
                "instruction": "Respond naturally with a balanced, helpful tone.",
                "formality": "adaptive",
            }

    def to_dict(self) -> dict[str, Any]:
        """Serialize current state for health reports."""
        return {
            "mood_trend": self.mood_trend.value,
            "average_valence": self.average_valence,
            "is_frustrated": self.is_user_frustrated,
            "is_happy": self.is_user_happy,
            "history_size": len(self._history),
        }
