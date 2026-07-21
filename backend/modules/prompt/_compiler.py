"""
Prompt compiler — renders ``{{ variable }}`` placeholders in templates.

No Jinja2 dependency is required.  A minimal ``{{ ... }}`` parser handles
the simple substitution patterns used by this project.  The ``.j2`` file
extension is used per 21_System_Contracts.md §19.10 to distinguish templates
from plain text, even though the parser is custom.
"""

from __future__ import annotations

import re
from typing import Final

from backend.modules.prompt._template import PromptTemplate

_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


class PromptCompileError(ValueError):
    """Raised when a template cannot be compiled (missing variables, etc.)."""


class PromptCompiler:
    """Compiles ``PromptTemplate`` instances by substituting placeholders.

    Recognises ``{{ variable_name }}`` patterns (dots allowed in names)
    and replaces them with values from the *variables* dict.  Unresolved
    placeholders after substitution are treated as an error.
    """

    @staticmethod
    def compile(
        template: PromptTemplate,
        variables: dict[str, str] | None = None,
    ) -> str:
        """Render *template* with *variables* and return the result.

        Parameters
        ----------
        template : PromptTemplate
            The template to render.
        variables : dict[str, str] | None
            Mapping of placeholder name → replacement text.

        Returns
        -------
        str
            The fully compiled prompt text.

        Raises
        ------
        PromptCompileError
            If any required placeholder is missing from *variables*.
        """
        vars_dict: dict[str, str] = variables or {}

        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in vars_dict:
                msg = f"Missing variable '{name}' in template '{template.name}'"
                raise PromptCompileError(msg)
            return vars_dict[name]

        result = _PLACEHOLDER_RE.sub(_replace, template.content)

        remaining = _PLACEHOLDER_RE.findall(result)
        if remaining:
            msg = f"Unresolved placeholders in compiled prompt: {', '.join(remaining)}"
            raise PromptCompileError(msg)

        return result
