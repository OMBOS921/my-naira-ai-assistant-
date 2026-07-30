"""HTML/CSS code builder implementation for Syntax Master."""

from __future__ import annotations

from typing import List

from backend.modules.syntax_master.builders.base_builder import BaseBuilder
from backend.modules.syntax_master.logician.schema import StepDefinition, StepType, TaskLogic


class HTMLBuilder(BaseBuilder):
    """Translates TaskLogic schema instances into syntactically structured HTML/Jinja template code."""

    SUPPORTED_LANGUAGES = {"html", "htm", "css"}

    def __init__(self, indent_size: int = 2) -> None:
        """Initializes HTMLBuilder with default 2-space indentation."""
        super().__init__(indent_size=indent_size, indent_char=" ")

    def build_code(self, task_logic: TaskLogic) -> str:
        """Translates a TaskLogic instance into HTML/Jinja2 template source code.

        Args:
            task_logic: Validated TaskLogic schema containing variables and logic steps.

        Returns:
            An HTML/Jinja source code string.

        Raises:
            ValueError: If target_language is not supported.
        """
        lang = task_logic.target_language.strip().lower()
        if lang not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"HTMLBuilder cannot handle target_language '{task_logic.target_language}'. Supported: {self.SUPPORTED_LANGUAGES}"
            )

        code_lines: List[str] = []

        # 1. Document Header & Comments
        code_lines.append(f"<!-- Task Summary: {task_logic.task_summary.strip()} -->")

        # 2. Variable declarations / Context comments
        if task_logic.variables:
            code_lines.append("<!-- Variables Context -->")
            for var in task_logic.variables:
                code_lines.append(f"<!-- {var.name}: {var.type} = {var.initial_value} -->")
            code_lines.append("")

        # 3. HTML Structure
        code_lines.append("<!DOCTYPE html>")
        code_lines.append('<html lang="en">')
        code_lines.append("<head>")
        code_lines.append('  <meta charset="UTF-8">')
        code_lines.append(f"  <title>{task_logic.task_summary.strip()}</title>")
        code_lines.append("</head>")
        code_lines.append("<body>")

        # 4. Step Execution Logic
        for step in task_logic.steps:
            code_lines.extend(self._translate_step(step, indent_level=1))

        code_lines.append("</body>")
        code_lines.append("</html>")

        return "\n".join(code_lines) + "\n"

    def _translate_step(self, step: StepDefinition, indent_level: int) -> List[str]:
        """Recursively translates a single StepDefinition into HTML/Jinja elements."""
        lines: List[str] = []
        indent = self.get_indent(indent_level)

        if step.type == StepType.IO:
            content = ", ".join(step.arguments) if step.arguments else step.description
            lines.append(f"{indent}<div>{content}</div>")

        elif step.type == StepType.CONDITION:
            cond = step.condition or step.description
            if cond.lower().startswith("if "):
                cond = cond[3:].strip()
            if cond.endswith(":"):
                cond = cond[:-1].strip()
            lines.append(f"{indent}{{% if {cond} %}}")
            if step.body:
                for child in step.body:
                    lines.extend(self._translate_step(child, indent_level + 1))
            lines.append(f"{indent}{{% endif %}}")

        elif step.type == StepType.LOOP:
            cond = step.condition or step.description
            if cond.lower().startswith("for "):
                cond = cond[4:].strip()
            if cond.endswith(":"):
                cond = cond[:-1].strip()
            lines.append(f"{indent}{{% for {cond} %}}")
            if step.body:
                for child in step.body:
                    lines.extend(self._translate_step(child, indent_level + 1))
            lines.append(f"{indent}{{% endfor %}}")

        elif step.type == StepType.ASSIGNMENT:
            val = ", ".join(step.arguments) if step.arguments else step.description
            target = step.target_variable or "var"
            lines.append(f"{indent}{{% set {target} = {val} %}}")

        elif step.type in (StepType.EXPRESSION, StepType.FUNCTION_CALL):
            expr = ", ".join(step.arguments) if step.arguments else step.description
            lines.append(f"{indent}<script>{expr}</script>")

        elif step.type == StepType.RETURN:
            ret_val = step.target_variable or (", ".join(step.arguments) if step.arguments else step.description)
            lines.append(f"{indent}<span>{{{{ {ret_val} }}}}</span>")

        else:
            lines.append(f"{indent}<!-- Step {step.step_id}: {step.description} -->")

        return lines
