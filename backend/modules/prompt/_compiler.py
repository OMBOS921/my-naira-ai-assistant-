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

try:
    import jinja2
except ImportError:
    jinja2 = None

_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


class PromptCompileError(ValueError):
    """Raised when a template cannot be compiled (missing variables, etc.)."""


def _expand_dots(d: dict[str, object]) -> dict[str, object]:
    res: dict[str, object] = {}
    for k, v in d.items():
        res[k] = v
        if "." in k:
            parts = k.split(".")
            curr: dict[str, object] = res
            for part in parts[:-1]:
                if part not in curr or not isinstance(curr[part], dict):
                    new_d: dict[str, object] = {}
                    curr[part] = new_d
                    curr = new_d
                else:
                    curr = curr[part]  # type: ignore[assignment]
            curr[parts[-1]] = v
    return res


class PromptCompiler:
    """Compiles ``PromptTemplate`` instances by substituting placeholders.

    Recognises ``{{ variable_name }}`` patterns (dots allowed in names)
    and Jinja2 logic templates, replacing them with values from *variables*.
    """

    @staticmethod
    def compile(
        template: PromptTemplate,
        variables: dict[str, str] | None = None,
    ) -> str:
        vars_dict: dict[str, object] = dict(variables or {})

        if jinja2 is not None:
            try:
                env = jinja2.Environment(
                    undefined=jinja2.StrictUndefined,
                    autoescape=False,
                )
                j2_template = env.from_string(template.content)
                return j2_template.render(**_expand_dots(vars_dict))
            except jinja2.UndefinedError as exc:
                msg = f"Missing variable '{exc}' in template '{template.name}'"
                raise PromptCompileError(msg) from exc
            except jinja2.TemplateError as exc:
                msg = f"Failed to compile template '{template.name}': {exc}"
                raise PromptCompileError(msg) from exc

        content = template.content

        # Handle {% set ... %} statements
        content = re.sub(r"\{%\s*set\s+[\w.]+\s*=.*?%\}\n?", "", content)

        # Handle {% if ... %}...{% else %}...{% endif %} blocks
        def _eval_if(m: re.Match[str]) -> str:
            expr = m.group(1).strip()
            if_body = m.group(2)
            else_body = m.group(3) if m.group(3) is not None else ""

            var_name = expr.split("|")[0].strip()
            val = vars_dict.get(var_name)
            is_truthy = bool(val) and str(val).strip() != "" and str(val).lower() != "false"
            return if_body if is_truthy else else_body

        content = re.sub(
            r"\{%\s*if\s+(.*?)\s*%\}(.*?)(?:\{%\s*else\s*%\}(.*?))?\{%\s*endif\s*%\}",
            _eval_if,
            content,
            flags=re.DOTALL,
        )

        # Handle {{ var | default('val') }} and {{ var }}
        def _replace_var(m: re.Match[str]) -> str:
            expr = m.group(1).strip()
            if "|" in expr:
                parts = expr.split("|", 1)
                var_name = parts[0].strip()
                filter_part = parts[1].strip()
                val = vars_dict.get(var_name)
                if val is not None and str(val) != "":
                    return str(val)
                default_m = re.search(r"default\((['\"]?)(.*?)\1\)", filter_part)
                if default_m:
                    return default_m.group(2)
                return ""
            else:
                var_name = expr
                if var_name not in vars_dict:
                    msg = f"Missing variable '{var_name}' in template '{template.name}'"
                    raise PromptCompileError(msg)
                return str(vars_dict[var_name])

        result = re.sub(r"\{\{\s*(.*?)\s*\}\}", _replace_var, content)
        return result
