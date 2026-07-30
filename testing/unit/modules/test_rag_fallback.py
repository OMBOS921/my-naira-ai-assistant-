"""Unit tests for SyntaxKnowledgeBase and RAGFallbackEngine (Phase 5 Step 8)."""

from __future__ import annotations

import pytest

from backend.modules.syntax_master.fallback.rag_fallback import RAGFallbackEngine, SyntaxKnowledgeBase
from backend.modules.syntax_master.logician.schema import (
    StepDefinition,
    StepType,
    TaskLogic,
    VariableDefinition,
)
from backend.modules.syntax_master.router.language_router import LanguageRouter


def test_syntax_knowledge_base_retrieval():
    kb = SyntaxKnowledgeBase()

    rust_bp = kb.get_syntax_blueprint("rust")
    assert "Use `fn` for functions" in rust_bp
    assert "let mut" in rust_bp

    go_bp = kb.get_syntax_blueprint("go")
    assert "func" in go_bp
    assert "err != nil" in go_bp

    ruby_bp = kb.get_syntax_blueprint("ruby")
    assert "def" in ruby_bp

    unknown_bp = kb.get_syntax_blueprint("unknown_lang")
    assert "Generic / Unspecified" in unknown_bp or "Standard clean" in unknown_bp


def test_rag_fallback_engine_prompt_and_handle():
    engine = RAGFallbackEngine()
    task = TaskLogic(
        target_language="rust",
        task_summary="Calculate factorial in Rust",
        variables=[
            VariableDefinition(name="n", type="int", initial_value=5),
        ],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.RETURN,
                description="Return factorial result",
            )
        ],
    )

    prompt = engine.generate_fallback_prompt(task)
    assert "Fallback Syntax Generator" in prompt
    assert "'rust'" in prompt
    assert '"target_language": "rust"' in prompt
    assert "Use `fn` for functions" in prompt
    assert "Output ONLY the raw" in prompt

    res = engine.handle_fallback(task)
    assert res["status"] == "fallback_required"
    assert res["language"] == "rust"
    assert res["fallback_prompt"] == prompt


def test_language_router_fallback_integration():
    router = LanguageRouter()
    task = TaskLogic(
        target_language="go",
        task_summary="Create HTTP server in Go",
        variables=[],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.FUNCTION_CALL,
                description="Listen and serve",
            )
        ],
    )

    # Without fallback -> raises NotImplementedError
    with pytest.raises(NotImplementedError):
        router.generate_and_validate(task, enable_fallback=False)

    # With fallback -> returns fallback dict
    res = router.generate_and_validate(task, enable_fallback=True)
    assert res["status"] == "fallback_required"
    assert res["language"] == "go"
    assert "Fallback Syntax Generator" in res["fallback_prompt"]
