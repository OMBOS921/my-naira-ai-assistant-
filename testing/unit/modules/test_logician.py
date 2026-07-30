"""Unit tests for the Logician module (Phase 5: Syntax Master)."""

from __future__ import annotations

import json
import pytest
from pydantic import ValidationError

from backend.modules.syntax_master.logician import (
    LOGICIAN_SYSTEM_PROMPT,
    LogicianValidator,
    StepDefinition,
    StepType,
    TaskLogic,
    ValidationResult,
    VariableDefinition,
    generate_logician_prompt,
)


def test_variable_definition_valid():
    var = VariableDefinition(name="user_count", type="int", initial_value=0)
    assert var.name == "user_count"
    assert var.type == "int"
    assert var.initial_value == 0


def test_variable_definition_empty_name_raises():
    with pytest.raises(ValidationError):
        VariableDefinition(name="  ", type="int")


def test_step_definition_valid():
    step = StepDefinition(
        step_id="1.1",
        type=StepType.CONDITION,
        description="Check if item list is non-empty",
        condition="item_count > 0",
        body=[
            StepDefinition(
                step_id="1.1.1",
                type=StepType.IO,
                description="Print message indicating item processing start",
            )
        ],
    )
    assert step.step_id == "1.1"
    assert step.type == StepType.CONDITION
    assert len(step.body) == 1
    assert step.body[0].step_id == "1.1.1"


def test_task_logic_valid():
    task = TaskLogic(
        target_language="python",
        task_summary="Calculate factorial of a non-negative integer",
        variables=[
            VariableDefinition(name="n", type="int", initial_value=5),
            VariableDefinition(name="result", type="int", initial_value=1),
        ],
        steps=[
            StepDefinition(
                step_id="1",
                type=StepType.LOOP,
                description="Loop from 1 to n inclusive",
                condition="i from 1 to n",
                body=[
                    StepDefinition(
                        step_id="1.1",
                        type=StepType.ASSIGNMENT,
                        description="Multiply current result by i",
                        target_variable="result",
                    )
                ],
            ),
            StepDefinition(
                step_id="2",
                type=StepType.RETURN,
                description="Return calculated result",
                target_variable="result",
            ),
        ],
    )
    assert task.target_language == "python"
    assert len(task.steps) == 2


def test_generate_logician_prompt():
    req = "Build a binary search function"
    prompt = generate_logician_prompt(req)
    assert LOGICIAN_SYSTEM_PROMPT in prompt
    assert req in prompt
    assert "OUTPUT (STRICT JSON ONLY):" in prompt


def test_validator_valid_plain_json():
    validator = LogicianValidator()
    valid_payload = {
        "target_language": "python",
        "task_summary": "Reverse a list of strings",
        "variables": [
            {"name": "items", "type": "list", "initial_value": ["a", "b", "c"]}
        ],
        "steps": [
            {
                "step_id": "1",
                "type": "function_call",
                "description": "Invoke built-in list reverse logic on items",
                "target_variable": "items",
            }
        ],
    }

    raw_str = json.dumps(valid_payload)
    res = validator.validate(raw_str)
    assert res.is_valid is True
    assert res.task_logic is not None
    assert res.task_logic.target_language == "python"
    assert res.error_message is None


def test_validator_valid_markdown_wrapped_json():
    validator = LogicianValidator()
    valid_payload = {
        "target_language": "typescript",
        "task_summary": "Fetch user profile",
        "variables": [],
        "steps": [
            {
                "step_id": "1",
                "type": "io",
                "description": "Perform HTTP GET request to profile endpoint",
            }
        ],
    }

    raw_markdown = f"```json\n{json.dumps(valid_payload)}\n```"
    res = validator.validate(raw_markdown)
    assert res.is_valid is True
    assert res.task_logic.target_language == "typescript"


def test_validator_invalid_json():
    validator = LogicianValidator()
    invalid_raw = "{ invalid json structure"
    res = validator.validate(invalid_raw)
    assert res.is_valid is False
    assert "Failed to parse JSON" in res.error_message
    assert res.retry_prompt is not None
    assert "CRITICAL" in res.retry_prompt


def test_validator_schema_mismatch():
    validator = LogicianValidator()
    bad_schema_payload = {
        "target_language": "python",
        # Missing task_summary and steps
    }
    raw_str = json.dumps(bad_schema_payload)
    res = validator.validate(raw_str)
    assert res.is_valid is False
    assert "Schema validation failed" in res.error_message
    assert "task_summary" in res.error_message or "steps" in res.error_message
    assert res.retry_prompt is not None
