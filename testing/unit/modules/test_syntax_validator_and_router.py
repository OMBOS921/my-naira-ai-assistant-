"""Unit tests for PythonValidator and LanguageRouter (Phase 5: Syntax Master)."""

from __future__ import annotations

import pytest

from backend.modules.syntax_master.builders.python_builder import PythonBuilder
from backend.modules.syntax_master.logician.schema import (
    StepDefinition,
    StepType,
    TaskLogic,
    VariableDefinition,
)
from backend.modules.syntax_master.router.language_router import LanguageRouter
from backend.modules.syntax_master.validators.python_validator import PythonValidator


def test_python_validator_valid_code():
    validator = PythonValidator()
    code = 'def greet(name: str) -> str:\n    return f"Hello, {name}"\n'
    result = validator.validate_syntax(code)

    assert result["is_valid"] is True
    assert result["error"] is None


def test_python_validator_invalid_code_syntax_error():
    validator = PythonValidator()
    code = "def bad_function(\n    x = 10\n"
    result = validator.validate_syntax(code)

    assert result["is_valid"] is False
    assert result["error"].startswith("SyntaxError:")
    assert isinstance(result["line"], int)
    assert isinstance(result["offset"], int)


def test_language_router_python_valid_flow():
    router = LanguageRouter()
    task = TaskLogic(
        target_language="python",
        task_summary="Sum numbers from 1 to N",
        variables=[
            VariableDefinition(name="n", type="int", initial_value=5),
            VariableDefinition(name="total", type="int", initial_value=0),
        ],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.LOOP,
                description="Loop over range n",
                condition="for i in range(n)",
                body=[
                    StepDefinition(
                        step_id="1.1",
                        type=StepType.ASSIGNMENT,
                        description="Add i to total",
                        target_variable="total",
                        arguments=["total + i"],
                    )
                ],
            ),
            StepDefinition(
                step_id="2",
                type=StepType.RETURN,
                description="Return total",
                target_variable="total",
            ),
        ],
    )

    res = router.generate_and_validate(task)
    assert res["is_valid"] is True
    assert res["error"] is None
    assert "for i in range(n):" in res["code"]
    assert "return total" in res["code"]


def test_language_router_python_variant_names():
    router = LanguageRouter()
    for variant in ["py", "python3", "PYTHON"]:
        task = TaskLogic(
            target_language=variant,
            task_summary="Simple print task",
            variables=[],
            steps=[
                StepDefinition(
                    step_id="1",
                    type=StepType.IO,
                    description="Print hello",
                    arguments=['"hello"'],
                )
            ],
        )
        res = router.generate_and_validate(task)
        assert res["is_valid"] is True
        assert 'print("hello")' in res["code"]


def test_language_router_unsupported_language_raises():
    router = LanguageRouter()
    task = TaskLogic(
        target_language="cpp",
        task_summary="C++ task",
        variables=[],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.RETURN,
                description="Return 0",
            )
        ],
    )

    with pytest.raises(NotImplementedError, match="Target language 'cpp' is currently unsupported"):
        router.generate_and_validate(task)


def test_language_router_catches_invalid_syntax_if_builder_produces_bad_code(monkeypatch):
    router = LanguageRouter()

    # Create a mock PythonBuilder that returns invalid python code
    class MockBadBuilder(PythonBuilder):
        def build_code(self, task_logic: TaskLogic) -> str:
            return "def broken_func(: bad syntax"

    bad_router = LanguageRouter(python_builder=MockBadBuilder())
    task = TaskLogic(
        target_language="python",
        task_summary="Broken code task",
        variables=[],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.RETURN,
                description="Return 0",
            )
        ],
    )

    res = bad_router.generate_and_validate(task)
    assert res["is_valid"] is False
    assert "SyntaxError" in res["error"]
    assert res["code"] == "def broken_func(: bad syntax"
    assert res["line"] is not None
