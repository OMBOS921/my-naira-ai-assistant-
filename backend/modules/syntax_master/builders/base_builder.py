"""Abstract Base Builder module for Syntax Master code generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from backend.modules.syntax_master.logician.schema import TaskLogic


class BaseBuilder(ABC):
    """Abstract base class for all language-specific code builders."""

    def __init__(self, indent_size: int = 4, indent_char: str = " ") -> None:
        """Initializes the base builder with indentation parameters.

        Args:
            indent_size: Number of indent characters per nesting level (default 4).
            indent_char: Character used for indentation (default single space ' ').
        """
        self.indent_size = indent_size
        self.indent_char = indent_char

    def get_indent(self, level: int) -> str:
        """Generates indentation prefix string for specified nesting level."""
        return (self.indent_char * self.indent_size) * level

    def format_comment(self, text: str, level: int = 0, comment_symbol: str = "#") -> str:
        """Formats a single line comment with appropriate indentation."""
        indent = self.get_indent(level)
        clean_text = text.strip().replace("\n", " ")
        return f"{indent}{comment_symbol} {clean_text}"

    @abstractmethod
    def build_code(self, task_logic: TaskLogic) -> str:
        """Translates language-agnostic TaskLogic into clean, executable source code.

        Args:
            task_logic: Fully validated TaskLogic instance.

        Returns:
            Generated target language code string.
        """
        pass
