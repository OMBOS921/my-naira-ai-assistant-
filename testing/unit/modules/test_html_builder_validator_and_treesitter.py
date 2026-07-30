"""Unit tests for HTMLBuilder, HTMLValidator, TreeSitterEngine, and expanded LanguageRouter."""

from __future__ import annotations

import pytest

from backend.modules.syntax_master.ast_engine.tree_sitter_wrapper import TreeSitterEngine
from backend.modules.syntax_master.builders.html_builder import HTMLBuilder
from backend.modules.syntax_master.logician.schema import (
    StepDefinition,
    StepType,
    TaskLogic,
    VariableDefinition,
)
from backend.modules.syntax_master.router.language_router import LanguageRouter
from backend.modules.syntax_master.validators.html_validator import HTMLValidator


def test_html_builder_generation():
    builder = HTMLBuilder()
    task = TaskLogic(
        target_language="html",
        task_summary="User profile dashboard",
        variables=[
            VariableDefinition(name="username", type="str", initial_value="NairaUser"),
            VariableDefinition(name="is_admin", type="bool", initial_value=True),
        ],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.IO,
                description="Welcome header",
                arguments=["Welcome back, {{ username }}"],
            ),
            StepDefinition(
                step_id="2",
                type=StepType.CONDITION,
                description="Check if admin",
                condition="is_admin",
                body=[
                    StepDefinition(
                        step_id="2.1",
                        type=StepType.IO,
                        description="Admin panel link",
                        arguments=['<a href="/admin">Admin Panel</a>'],
                    )
                ],
            ),
            StepDefinition(
                step_id="3",
                type=StepType.LOOP,
                description="Iterate over items",
                condition="for item in items",
                body=[
                    StepDefinition(
                        step_id="3.1",
                        type=StepType.IO,
                        description="Display item",
                        arguments=["{{ item }}"],
                    )
                ],
            ),
        ],
    )

    code = builder.build_code(task)
    assert "<!DOCTYPE html>" in code
    assert "<title>User profile dashboard</title>" in code
    assert "{% if is_admin %}" in code
    assert "{% endif %}" in code
    assert "{% for item in items %}" in code
    assert "{% endfor %}" in code
    assert "<div>Welcome back, {{ username }}</div>" in code


def test_html_validator_valid():
    validator = HTMLValidator()
    html_code = "<!DOCTYPE html><html><head><title>Test</title></head><body><div><p>Hello</p></div></body></html>"
    res = validator.validate_syntax(html_code)
    assert res["is_valid"] is True
    assert res["error"] is None


def test_html_validator_unclosed_tag():
    validator = HTMLValidator()
    html_code = "<div><p>Unclosed paragraph</div>"
    res = validator.validate_syntax(html_code)
    assert res["is_valid"] is False
    assert "Mismatched closing tag </div>" in res["error"] or "Unclosed HTML tag" in res["error"]


def test_language_router_html_flow():
    router = LanguageRouter()
    task = TaskLogic(
        target_language="html",
        task_summary="HTML Card Component",
        variables=[],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.IO,
                description="Card content",
                arguments=["<h1>Card Title</h1>"],
            )
        ],
    )

    res = router.generate_and_validate(task)
    assert res["is_valid"] is True
    assert res["error"] is None
    assert "<h1>Card Title</h1>" in res["code"]


def test_tree_sitter_engine_foundation():
    engine = TreeSitterEngine()
    parse_res = engine.parse_code(code="int main() { return 0; }", language="cpp")
    assert parse_res["status"] == "not_implemented"
    assert "Tree-sitter AST engine is ready for Phase 3" in parse_res["message"]

    val_res = engine.validate_tree(None)
    assert val_res["is_valid"] is False
    assert "Tree-sitter validation pending" in val_res["error"]
