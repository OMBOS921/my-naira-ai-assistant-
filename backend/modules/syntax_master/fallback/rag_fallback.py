"""RAG Fallback System implementation for Syntax Master."""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.modules.syntax_master.logician.schema import TaskLogic


class SyntaxKnowledgeBase:
    """Knowledge base storing syntax blueprints for unsupported languages."""

    BLUEPRINTS: Dict[str, str] = {
        "rust": (
            "Language: Rust. Rules: Use `fn` for functions, `let` / `let mut` for variable bindings. "
            "Use `match` or `if let` for control flow and pattern matching. Use `Result<T, E>` or `Option<T>` "
            "for error handling and avoid exceptions. Return values explicitly or via implicit last-expression without a semicolon."
        ),
        "go": (
            "Language: Go (Golang). Rules: Use `func` for function definitions. Use `:=` for short variable declarations "
            "and `var` for explicit types. Use `if` and `for` without parentheses around conditions. "
            "Use multi-value returns `(T, error)` and explicit `if err != nil` error handling."
        ),
        "ruby": (
            "Language: Ruby. Rules: Use `def` for methods and `end` to close blocks. Use `@` for instance variables "
            "and `@@` for class variables. Return last evaluated expression implicitly. Use `begin...rescue...end` for error handling."
        ),
        "cpp": (
            "Language: C++. Rules: Include required headers (#include <iostream>). Declare strict types. "
            "Use `int main()` as entry point. Use `std::cout` / `std::cin` for I/O. End statements with semicolons."
        ),
        "c": (
            "Language: C. Rules: Include stdio.h. Explicit pointer dereferencing and memory allocation (malloc/free). "
            "Strict imperative flow with semicolons."
        ),
    }

    GENERIC_BLUEPRINT: str = (
        "Language: Generic / Unspecified. Rules: Standard clean C-style syntax expected. "
        "Use modular function definitions, clear variable declarations, and standard control flow structures."
    )

    def get_syntax_blueprint(self, language: str) -> str:
        """Retrieves syntax rules and blueprint for specified target language.

        Args:
            language: Target programming language identifier.

        Returns:
            A string containing target language syntax blueprint rules.
        """
        lang_key = language.strip().lower()
        return self.BLUEPRINTS.get(lang_key, self.GENERIC_BLUEPRINT)


class RAGFallbackEngine:
    """Fallback engine generating LLM prompt directives for unsupported target languages."""

    def __init__(self, knowledge_base: Optional[SyntaxKnowledgeBase] = None) -> None:
        """Initializes RAGFallbackEngine with optional SyntaxKnowledgeBase instance."""
        self.knowledge_base = knowledge_base or SyntaxKnowledgeBase()

    def generate_fallback_prompt(self, task_logic: TaskLogic) -> str:
        """Generates a targeted LLM prompt with language blueprint and JSON logical steps.

        Args:
            task_logic: Validated TaskLogic schema.

        Returns:
            Formatted prompt string directive for LLM code generation.
        """
        target_lang = task_logic.target_language.strip()
        blueprint = self.knowledge_base.get_syntax_blueprint(target_lang)
        json_logic = task_logic.model_dump_json(indent=2)

        prompt = (
            f"You are the Fallback Syntax Generator for Naira-OS Syntax Master.\n"
            f"We do not have a local syntax builder for '{target_lang}'. You must write the raw code.\n"
            f"Here are the exact logical steps you MUST follow:\n{json_logic}\n\n"
            f"Here are the syntax rules for this language:\n{blueprint}\n\n"
            f"Output ONLY the raw, perfectly indented code without markdown."
        )
        return prompt

    def handle_fallback(self, task_logic: TaskLogic) -> Dict[str, Any]:
        """Handles fallback workflow generation for an unsupported language task.

        Args:
            task_logic: Validated TaskLogic schema.

        Returns:
            Dictionary containing fallback status, target language, and generated LLM prompt.
        """
        target_lang = task_logic.target_language.strip()
        fallback_prompt = self.generate_fallback_prompt(task_logic)

        return {
            "status": "fallback_required",
            "language": target_lang,
            "fallback_prompt": fallback_prompt,
        }
