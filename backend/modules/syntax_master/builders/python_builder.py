"""Python code builder implementation for Syntax Master."""

from __future__ import annotations

import re
from typing import Any, List, Optional

from backend.modules.syntax_master.builders.base_builder import BaseBuilder
from backend.modules.syntax_master.logician.schema import StepDefinition, StepType, TaskLogic, VariableDefinition


class PythonBuilder(BaseBuilder):
    """Translates TaskLogic schema instances into syntactically valid Python source code."""

    SUPPORTED_LANGUAGES = {"python", "python3", "py"}

    def __init__(self, indent_size: int = 4) -> None:
        super().__init__(indent_size=indent_size, indent_char=" ")

    def build_code(self, task_logic: TaskLogic) -> str:
        """Translates a TaskLogic instance into formatted, valid Python code.

        Args:
            task_logic: Validated TaskLogic schema containing variables and logic steps.

        Returns:
            A clean Python source code string.

        Raises:
            ValueError: If target_language is not Python.
        """
        lang = task_logic.target_language.strip().lower()
        if lang not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"PythonBuilder cannot handle target_language '{task_logic.target_language}'. Supported: {self.SUPPORTED_LANGUAGES}")

        code_lines: List[str] = []

        # 1. Module Docstring / Header
        code_lines.append(f'"""{task_logic.task_summary.strip()}"""')
        code_lines.append("")

        # 2. Variable Initializations
        if task_logic.variables:
            code_lines.append("# Variable declarations & initializations")
            for var in task_logic.variables:
                code_lines.append(self._format_variable_init(var))
            code_lines.append("")

        # 3. Step Execution Logic
        code_lines.append("# Main logic execution flow")
        for step in task_logic.steps:
            code_lines.extend(self._translate_step(step, indent_level=0))

        return "\n".join(code_lines) + "\n"

    def _format_variable_init(self, var: VariableDefinition) -> str:
        """Formats variable declaration and default initialization for Python."""
        var_name = self._clean_identifier(var.name)
        type_str = var.type.strip()
        val_repr = self._get_initial_value_repr(var.initial_value, type_str)
        return f"{var_name}: {type_str} = {val_repr}"

    def _get_initial_value_repr(self, val: Optional[Any], type_str: str) -> str:
        """Returns Python string representation for initial variable values."""
        if val is not None:
            if isinstance(val, str):
                # Check if val is already a raw python literal like "0", "[]", "True"
                if val.strip() in ("[]", "{}", "0", "0.0", "True", "False", "None"):
                    return val.strip()
                return repr(val)
            return repr(val)

        # Infer fallback default value based on abstract data type
        t_lower = type_str.lower()
        if "int" in t_lower:
            return "0"
        elif "float" in t_lower:
            return "0.0"
        elif "bool" in t_lower:
            return "False"
        elif "list" in t_lower or "array" in t_lower:
            return "[]"
        elif "dict" in t_lower or "map" in t_lower:
            return "{}"
        elif "str" in t_lower:
            return '""'
        return "None"

    def _translate_step(self, step: StepDefinition, indent_level: int) -> List[str]:
        """Recursively translates a single StepDefinition into indented Python statements."""
        lines: List[str] = []
        indent = self.get_indent(indent_level)

        if step.type == StepType.CONDITION:
            cond_expr = self._clean_condition(step.condition or step.description)
            if not cond_expr.lower().startswith("if "):
                header = f"if {cond_expr}:"
            else:
                header = cond_expr if cond_expr.endswith(":") else f"{cond_expr}:"
            
            lines.append(f"{indent}{header}")
            
            if step.body and len(step.body) > 0:
                for child in step.body:
                    lines.extend(self._translate_step(child, indent_level + 1))
            else:
                lines.append(f"{self.get_indent(indent_level + 1)}pass")

        elif step.type == StepType.LOOP:
            loop_expr = self._clean_condition(step.condition or step.description)
            cond_stripped = loop_expr.strip()
            
            if cond_stripped.lower().startswith(("while ", "for ")):
                header = cond_stripped if cond_stripped.endswith(":") else f"{cond_stripped}:"
            else:
                header = f"while {cond_stripped}:"

            lines.append(f"{indent}{header}")

            if step.body and len(step.body) > 0:
                for child in step.body:
                    lines.extend(self._translate_step(child, indent_level + 1))
            else:
                lines.append(f"{self.get_indent(indent_level + 1)}pass")

        elif step.type == StepType.ASSIGNMENT:
            target = self._clean_identifier(step.target_variable or "result")
            if step.arguments and len(step.arguments) > 0:
                expr = step.arguments[0]
            elif step.condition:
                expr = step.condition
            else:
                expr = self._clean_expression_text(step.description)
            
            lines.append(f"{indent}{target} = {expr}")

        elif step.type == StepType.IO:
            desc_lower = step.description.lower()
            is_input = any(kw in desc_lower for kw in ("input", "read", "prompt", "get user", "request"))
            
            if is_input:
                prompt_arg = repr(step.description) if not step.arguments else repr(step.arguments[0])
                if step.target_variable:
                    target = self._clean_identifier(step.target_variable)
                    lines.append(f"{indent}{target} = input({prompt_arg})")
                else:
                    lines.append(f"{indent}input({prompt_arg})")
            else:
                if step.arguments:
                    args_str = ", ".join(step.arguments)
                    lines.append(f"{indent}print({args_str})")
                elif step.target_variable:
                    lines.append(f"{indent}print({self._clean_identifier(step.target_variable)})")
                else:
                    lines.append(f"{indent}print({repr(step.description)})")

        elif step.type == StepType.FUNCTION_CALL:
            args_str = ", ".join(step.arguments) if step.arguments else ""
            func_name = self._extract_function_name(step.description, step.arguments)
            call_expr = f"{func_name}({args_str})"
            
            if step.target_variable:
                target = self._clean_identifier(step.target_variable)
                lines.append(f"{indent}{target} = {call_expr}")
            else:
                lines.append(f"{indent}{call_expr}")

        elif step.type == StepType.RETURN:
            if step.target_variable:
                lines.append(f"{indent}return {self._clean_identifier(step.target_variable)}")
            elif step.arguments and len(step.arguments) > 0:
                lines.append(f"{indent}return {', '.join(step.arguments)}")
            elif step.condition:
                lines.append(f"{indent}return {step.condition}")
            else:
                lines.append(f"{indent}return")

        elif step.type == StepType.ERROR_HANDLING:
            lines.append(f"{indent}try:")
            if step.body and len(step.body) > 0:
                for child in step.body:
                    lines.extend(self._translate_step(child, indent_level + 1))
            else:
                lines.append(f"{self.get_indent(indent_level + 1)}pass")
            lines.append(f"{indent}except Exception as e:")
            lines.append(f"{self.get_indent(indent_level + 1)}print(f\"Error executing step {step.step_id}: {{e}}\")")

        elif step.type == StepType.EXPRESSION:
            if step.target_variable and step.arguments:
                target = self._clean_identifier(step.target_variable)
                lines.append(f"{indent}{target} = {step.arguments[0]}")
            elif step.arguments and len(step.arguments) > 0:
                lines.append(f"{indent}{step.arguments[0]}")
            else:
                lines.append(f"{indent}# {step.description}")

        return lines

    @staticmethod
    def _clean_identifier(name: str) -> str:
        """Sanitizes text into a valid Python identifier variable name."""
        cleaned = re.sub(r"[^\w]", "_", name.strip())
        if cleaned and cleaned[0].isdigit():
            cleaned = f"var_{cleaned}"
        return cleaned or "var"

    @staticmethod
    def _clean_condition(cond: str) -> str:
        """Cleans and formats condition strings for Python if/while headers."""
        text = cond.strip()
        # Remove trailing colon if present
        if text.endswith(":"):
            text = text[:-1].strip()
        return text

    @staticmethod
    def _clean_expression_text(desc: str) -> str:
        """Converts logic step descriptions into Python-compatible values or comments."""
        desc_clean = desc.strip()
        # If it looks like a valid python literal or expression, use it
        if desc_clean in ("True", "False", "None") or desc_clean.isdigit():
            return desc_clean
        return repr(desc_clean)

    @classmethod
    def _extract_function_name(cls, description: str, arguments: Optional[List[str]]) -> str:
        """Extracts or derives a valid function name from step descriptions."""
        words = description.strip().split()
        for word in words:
            # Look for function-like names (e.g. process_data, math.sqrt, calculate_total)
            clean_w = word.strip("(),;:'\"")
            if re.match(r"^[a-zA-Z_][a-zA-Z0-0_.]*$", clean_w) and clean_w not in ("Call", "Invoke", "Run", "Execute", "the", "function", "with"):
                return clean_w
        return "execute_function"
