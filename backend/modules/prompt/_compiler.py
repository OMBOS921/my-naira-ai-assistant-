"""
Prompt compiler — renders Jinja2 templates for Naira-OS prompts.

Uses the official ``jinja2`` library to compile and render templates,
handling variables, logic blocks ({% if %}, {% elif %}, {% else %}),
and filters gracefully without crashing on missing context variables per
jinja2's Undefined settings.
"""

from __future__ import annotations

from typing import Any

import jinja2

from backend.modules.prompt._template import PromptTemplate


class PromptCompileError(ValueError):
    """Raised when a template cannot be compiled due to syntax errors or invalid template structure."""


def _expand_dots(d: dict[str, Any]) -> dict[str, Any]:
    """Expand flat keys containing dots (e.g., 'user.name': 'Alice') into nested dictionaries."""
    res: dict[str, Any] = {}
    for k, v in d.items():
        res[k] = v
        if "." in k:
            parts = k.split(".")
            curr: dict[str, Any] = res
            for part in parts[:-1]:
                if part not in curr or not isinstance(curr[part], dict):
                    new_d: dict[str, Any] = {}
                    curr[part] = new_d
                    curr = new_d
                else:
                    curr = curr[part]  # type: ignore[assignment]
            curr[parts[-1]] = v
    return res


class PromptCompiler:
    """Compiles ``PromptTemplate`` instances using Jinja2.

    Uses ``jinja2.Environment`` and ``from_string()`` to compile and render templates.
    Gracefully handles missing variables in the context dictionary using Jinja2's
    Undefined setting so the app doesn't crash if a variable is missing at runtime.
    """

    _env: jinja2.Environment = jinja2.Environment(
        undefined=jinja2.Undefined,
        autoescape=False,
    )

    @classmethod
    def compile(
        cls,
        template: PromptTemplate,
        variables: dict[str, Any] | None = None,
    ) -> str:
        """Compile and render a prompt template with the provided variables.

        Parameters
        ----------
        template : PromptTemplate
            The prompt template containing content and metadata.
        variables : dict[str, Any] | None
            Runtime context variables for substitution.

        Returns
        -------
        str
            The rendered system prompt string.

        Raises
        ------
        PromptCompileError
            If the template contains invalid Jinja2 syntax or fails compilation.
        """
        vars_dict: dict[str, Any] = dict(variables or {})
        expanded_vars = _expand_dots(vars_dict)

        try:
            j2_template = cls._env.from_string(template.content)
            return j2_template.render(**expanded_vars)
        except jinja2.TemplateError as exc:
            msg = f"Failed to compile template '{template.name}': {exc}"
            raise PromptCompileError(msg) from exc
