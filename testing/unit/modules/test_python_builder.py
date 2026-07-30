"""Unit tests for BaseBuilder and PythonBuilder (Phase 5: Syntax Master)."""

from __future__ import annotations

import pytest

from backend.modules.syntax_master.builders.python_builder import PythonBuilder
from backend.modules.syntax_master.logician.schema import (
    StepDefinition,
    StepType,
    TaskLogic,
    VariableDefinition,
)


def test_python_builder_rejects_non_python_language():
    builder = PythonBuilder()
    task = TaskLogic(
        target_language="rust",
        task_summary="Calculate area",
        variables=[],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.RETURN,
                description="Return zero",
            )
        ],
    )
    with pytest.raises(ValueError, match="PythonBuilder cannot handle target_language"):
        builder.build_code(task)


def test_python_builder_variables_and_simple_flow():
    builder = PythonBuilder()
    task = TaskLogic(
        target_language="python",
        task_summary="Basic variable initialization and print task",
        variables=[
            VariableDefinition(name="user_name", type="str", initial_value="Alice"),
            VariableDefinition(name="user_age", type="int", initial_value=30),
            VariableDefinition(name="is_active", type="bool", initial_value=True),
        ],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.IO,
                description="Print welcome message",
                arguments=["user_name"],
            ),
            StepDefinition(
                step_id="2",
                type=StepType.RETURN,
                description="Return age",
                target_variable="user_age",
            ),
        ],
    )

    code = builder.build_code(task)
    assert '"""Basic variable initialization and print task"""' in code
    assert "user_name: str = 'Alice'" in code
    assert "user_age: int = 30" in code
    assert "is_active: bool = True" in code
    assert "print(user_name)" in code
    assert "return user_age" in code


test_nested_indentation_data = TaskLogic(
    target_language="python",
    task_summary="Process scores list with nested condition and loop",
    variables=[
        VariableDefinition(name="scores", type="list", initial_value="[10, 20, 30]"),
        VariableDefinition(name="total", type="int", initial_value=0),
    ],
    steps=[
        StepDefinition(
            step_id="1",
            type=StepType.CONDITION,
            description="Check if scores is non-empty",
            condition="len(scores) > 0",
            body=[
                StepDefinition(
                    step_id="1.1",
                    type=StepType.LOOP,
                    description="Iterate over each score in scores",
                    condition="for score in scores",
                    body=[
                        StepDefinition(
                            step_id="1.1.1",
                            type=StepType.ASSIGNMENT,
                            description="Add score to total",
                            target_variable="total",
                            arguments=["total + score"],
                        ),
                        StepDefinition(
                            step_id="1.1.2",
                            type=StepType.IO,
                            description="Print current score",
                            arguments=["score"],
                        ),
                    ],
                )
            ],
        ),
        StepDefinition(
            step_id="2",
            type=StepType.RETURN,
            description="Return final total",
            target_variable="total",
        ),
    ],
)


def test_python_builder_nested_indentation():
    builder = PythonBuilder(indent_size=4)
    code = builder.build_code(test_nested_indentation_data)

    lines = code.splitlines()

    # Check top-level condition
    assert "if len(scores) > 0:" in lines

    # Check level 1 loop (4 spaces)
    assert "    for score in scores:" in lines

    # Check level 2 statements (8 spaces)
    assert "        total = total + score" in lines
    assert "        print(score)" in lines

    # Check return statement at top level (0 spaces)
    assert "return total" in lines


def test_python_builder_io_input_and_print():
    builder = PythonBuilder()
    task = TaskLogic(
        target_language="python",
        task_summary="IO input prompt test",
        variables=[],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.IO,
                description="Prompt user to enter user input name",
                target_variable="user_input_name",
            ),
            StepDefinition(
                step_id="2",
                type=StepType.IO,
                description="Display greeting to user",
                target_variable="user_input_name",
            ),
        ],
    )

    code = builder.build_code(task)
    assert "user_input_name = input(" in code
    assert "print(user_input_name)" in code


def test_python_builder_error_handling_and_func_call():
    builder = PythonBuilder()
    task = TaskLogic(
        target_language="python",
        task_summary="Error handling test",
        variables=[],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.ERROR_HANDLING,
                description="Safely fetch user record",
                body=[
                    StepDefinition(
                        step_id="1.1",
                        type=StepType.FUNCTION_CALL,
                        description="Call fetch_user_record with user_id",
                        target_variable="record",
                        arguments=["user_id"],
                    )
                ],
            )
        ],
    )

    code = builder.build_code(task)
    assert "try:" in code
    assert "    record = fetch_user_record(user_id)" in code
    assert "except Exception as e:" in code
