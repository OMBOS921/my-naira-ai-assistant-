"""Syntax Master module package for Naira-OS."""

from backend.modules.syntax_master.ast_engine.tree_sitter_wrapper import TreeSitterEngine
from backend.modules.syntax_master.builders.html_builder import HTMLBuilder
from backend.modules.syntax_master.builders.python_builder import PythonBuilder
from backend.modules.syntax_master.fallback.rag_fallback import RAGFallbackEngine, SyntaxKnowledgeBase
from backend.modules.syntax_master.router.language_router import LanguageRouter
from backend.modules.syntax_master.validators.html_validator import HTMLValidator
from backend.modules.syntax_master.validators.python_validator import PythonValidator

__all__ = [
    "PythonBuilder",
    "HTMLBuilder",
    "PythonValidator",
    "HTMLValidator",
    "LanguageRouter",
    "TreeSitterEngine",
    "SyntaxKnowledgeBase",
    "RAGFallbackEngine",
]
