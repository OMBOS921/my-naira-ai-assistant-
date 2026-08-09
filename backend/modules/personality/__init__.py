"""
Personality Module — Character memory, adaptive tone, and sentiment analysis.

Provides JARVIS-like personality that remembers user preferences,
detects emotional context, and adapts response tone dynamically.
"""

from __future__ import annotations

from backend.modules.personality.personality_engine import PersonalityEngine
from backend.modules.personality.sentiment_analyzer import SentimentAnalyzer

__all__ = ["PersonalityEngine", "SentimentAnalyzer"]
