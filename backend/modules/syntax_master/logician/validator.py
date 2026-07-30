"""Validator module for parsing, validating, and handling retry logic for Logician LLM outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ValidationError

from backend.modules.syntax_master.logician.schema import TaskLogic


class ValidationResult(BaseModel):
    """Structured result returned after validating a raw Logician LLM output."""
    is_valid: bool = Field(..., description="True if output parsed and satisfied TaskLogic schema, False otherwise")
    task_logic: Optional[TaskLogic] = Field(default=None, description="Instantiated TaskLogic Pydantic model if valid")
    raw_json: Optional[Dict[str, Any]] = Field(default=None, description="Parsed raw JSON dictionary if JSON parsing succeeded")
    error_message: Optional[str] = Field(default=None, description="Detailed error description if validation failed")
    retry_prompt: Optional[str] = Field(default=None, description="Formatted retry prompt to send back to the LLM upon failure")


class LogicianValidator:
    """Validator wrapper for parsing and verifying raw string outputs from the Logician LLM."""

    @staticmethod
    def clean_raw_output(raw_output: str) -> str:
        """Extracts JSON string from raw LLM output, removing markdown code fences if present."""
        text = raw_output.strip()
        # Look for markdown fenced blocks (```json ... ``` or ``` ... ```)
        fenced_pattern = r"```(?:json)?\s*(.*?)\s*```"
        matches = re.findall(fenced_pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()

        # If no code block fence found, attempt to locate top-level JSON object boundaries { ... }
        json_obj_pattern = r"(\{.*\})"
        obj_match = re.search(json_obj_pattern, text, re.DOTALL)
        if obj_match:
            return obj_match.group(1).strip()

        return text

    def validate(self, raw_output: str) -> ValidationResult:
        """Parses raw LLM output string and validates it against the TaskLogic schema.

        Args:
            raw_output: The raw text response from the LLM.

        Returns:
            ValidationResult object indicating success or detailing errors with a retry prompt.
        """
        if not raw_output or not raw_output.strip():
            error_msg = "LLM output was completely empty."
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                retry_prompt=self.format_retry_prompt(error_msg),
            )

        cleaned_str = self.clean_raw_output(raw_output)

        # 1. Parse JSON
        try:
            parsed_json = json.loads(cleaned_str)
        except json.JSONDecodeError as exc:
            error_msg = f"Failed to parse JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}."
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                retry_prompt=self.format_retry_prompt(error_msg, raw_output=raw_output),
            )

        if not isinstance(parsed_json, dict):
            error_msg = f"Root of JSON response must be a JSON object (dict), got {type(parsed_json).__name__}."
            return ValidationResult(
                is_valid=False,
                raw_json=None,
                error_message=error_msg,
                retry_prompt=self.format_retry_prompt(error_msg, raw_output=raw_output),
            )

        # 2. Schema Validation with Pydantic v2
        try:
            task_logic = TaskLogic.model_validate(parsed_json)
            return ValidationResult(
                is_valid=True,
                task_logic=task_logic,
                raw_json=parsed_json,
            )
        except ValidationError as val_err:
            error_details = []
            for err in val_err.errors():
                loc_str = " -> ".join(str(loc_item) for loc_item in err["loc"])
                error_details.append(f"- Location [{loc_str}]: {err['msg']}")

            formatted_errors = "\n".join(error_details)
            error_msg = f"Schema validation failed with {len(val_err.errors())} error(s):\n{formatted_errors}"

            return ValidationResult(
                is_valid=False,
                raw_json=parsed_json,
                error_message=error_msg,
                retry_prompt=self.format_retry_prompt(error_msg, raw_output=raw_output),
            )

    @staticmethod
    def format_retry_prompt(error_message: str, raw_output: Optional[str] = None) -> str:
        """Generates a structured retry prompt containing feedback for the LLM to fix its response."""
        prompt_parts = [
            "CRITICAL: Your previous JSON output for the Logician task failed validation.",
            "",
            "VALIDATION ERRORS:",
            error_message,
            "",
            "RETRY INSTRUCTIONS:",
            "1. Output ONLY valid, raw JSON matching the TaskLogic schema.",
            "2. Do NOT write any markdown text or explanations outside the JSON object.",
            "3. Ensure all required fields (target_language, task_summary, variables, steps with step_id, type, description) are provided.",
            "4. Ensure no code syntax is present in descriptions.",
        ]

        if raw_output:
            prompt_parts.extend(["", "YOUR PREVIOUS FAILING OUTPUT:", raw_output])

        return "\n".join(prompt_parts)
