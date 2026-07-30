"""Language router implementation for Syntax Master."""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

from backend.modules.syntax_master.builders.html_builder import HTMLBuilder
from backend.modules.syntax_master.builders.python_builder import PythonBuilder
from backend.modules.syntax_master.fallback.rag_fallback import RAGFallbackEngine
from backend.modules.syntax_master.logician.schema import TaskLogic
from backend.modules.syntax_master.validators.html_validator import HTMLValidator
from backend.modules.syntax_master.validators.python_validator import PythonValidator


class LanguageRouter:
    """Routes TaskLogic to appropriate language builder and validator."""

    PYTHON_VARIANTS: Set[str] = {"python", "python3", "py"}
    HTML_VARIANTS: Set[str] = {"html", "htm", "css"}

    def __init__(
        self,
        python_builder: Optional[PythonBuilder] = None,
        python_validator: Optional[PythonValidator] = None,
        html_builder: Optional[HTMLBuilder] = None,
        html_validator: Optional[HTMLValidator] = None,
        fallback_engine: Optional[RAGFallbackEngine] = None,
    ) -> None:
        """Initializes LanguageRouter with optional builder, validator, and fallback overrides."""
        self.python_builder = python_builder or PythonBuilder()
        self.python_validator = python_validator or PythonValidator()
        self.html_builder = html_builder or HTMLBuilder()
        self.html_validator = html_validator or HTMLValidator()
        self.fallback_engine = fallback_engine or RAGFallbackEngine()

    def generate_and_validate(
        self, task_logic: TaskLogic, enable_fallback: bool = False, bypass_syntax_master: bool = False
    ) -> Dict[str, Any]:
        """Generates source code from TaskLogic schema and validates its syntax.

        MVP Pivot: When bypass_syntax_master is True, Phase 5 Syntax Master local
        AST building/validation is safely bypassed and raw Main LLM output is preserved.

        Args:
            task_logic: Validated TaskLogic instance defining task goals, variables, and steps.
            enable_fallback: If True, returns RAGFallback result instead of raising NotImplementedError on unsupported language.
            bypass_syntax_master: If True, bypasses local AST builders and tree-sitter.

        Returns:
            A dictionary containing code generation and validation status:
            - If valid/bypassed: {"is_valid": True, "code": <code_str>, "error": None, "bypassed": True}
        """
        if bypass_syntax_master:
            return {
                "is_valid": True,
                "code": task_logic.description if hasattr(task_logic, "description") else str(task_logic),
                "error": None,
                "bypassed": True,
                "handler": "Main_LLM",
            }

        lang = task_logic.target_language.strip().lower()

        if lang in self.PYTHON_VARIANTS:
            code_string = self.python_builder.build_code(task_logic)
            validation_result = self.python_validator.validate_syntax(code_string)

            if validation_result.get("is_valid"):
                return {
                    "is_valid": True,
                    "code": code_string,
                    "error": None,
                }
            else:
                return {
                    "is_valid": False,
                    "code": code_string,
                    "error": validation_result.get("error"),
                    "line": validation_result.get("line"),
                    "offset": validation_result.get("offset"),
                }

        if lang in self.HTML_VARIANTS:
            code_string = self.html_builder.build_code(task_logic)
            validation_result = self.html_validator.validate_syntax(code_string)

            if validation_result.get("is_valid"):
                return {
                    "is_valid": True,
                    "code": code_string,
                    "error": None,
                }
            else:
                return {
                    "is_valid": False,
                    "code": code_string,
                    "error": validation_result.get("error"),
                    "line": validation_result.get("line"),
                    "offset": validation_result.get("offset"),
                }

        if enable_fallback:
            return self.fallback_engine.handle_fallback(task_logic)

        raise NotImplementedError(
            f"Target language '{task_logic.target_language}' is currently unsupported. Fallback required."
        )
