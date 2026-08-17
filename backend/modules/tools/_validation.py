"""
ToolValidation — input/output schema validation for tools.

21_System_Contracts.md §15 — Tool contracts.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.modules.tools._definition import ToolDefinition
from backend.types import ToolResult, ValidationResult
_LOG = logging.getLogger("naira.tools")


class ToolValidation:
    """Validates tool input arguments and output results against their
    declared JSON Schema.

    Provides basic type-coercion sanitisation and required-field
    checking.  In a production deployment this would be replaced by a
    full JSON Schema validator (e.g. ``jsonschema`` or ``pydantic``).
    """

    # Simple JSON Schema type-to-Python-type mapping for basic validation
    _TYPE_MAP: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
        "array": list,
    }

    @staticmethod
    def validate_input(
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> ValidationResult:
        """Validate *arguments* against the tool's parameter schema.

        Performs basic structural checks:
        - Required properties are present.
        - Property types match the schema (coercive).
        - No unknown properties (if ``additionalProperties`` is false).

        Parameters
        ----------
        definition : ToolDefinition
            The tool descriptor containing the parameter schema.
        arguments : dict[str, Any]
            The raw input arguments to validate.

        Returns
        -------
        ValidationResult
            ``status="pass"`` if valid, ``"reject"`` if invalid, or
            ``"sanitized"`` if coercible corrections were applied.
        """
        schema = definition.parameters
        if not schema or not isinstance(schema, dict):
            return ValidationResult(status="pass")

        properties: dict[str, Any] = schema.get("properties", {})
        required: list[str] = schema.get("required", [])

        # Check required fields
        for field in required:
            if field not in arguments or arguments[field] is None:
                return ValidationResult(
                    status="reject",
                    reason=f"Missing required field: '{field}'",
                )

        sanitized = dict(arguments)
        has_corrections = False

        for field, value in list(sanitized.items()):
            if field not in properties:
                if not schema.get("additionalProperties", True):
                    del sanitized[field]
                    has_corrections = True
                continue

            field_schema = properties[field]
            expected_type_name = field_schema.get("type", "string")
            expected_type = ToolValidation._TYPE_MAP.get(expected_type_name)

            if (
                expected_type is not None
                and value is not None
                and not isinstance(value, expected_type)
            ):
                try:
                    sanitized[field] = expected_type(value)
                    has_corrections = True
                except (ValueError, TypeError):
                    return ValidationResult(
                        status="reject",
                        reason=(
                            f"Field '{field}' expected type "
                            f"'{expected_type_name}'"
                        ),
                    )

        if has_corrections:
            return ValidationResult(status="sanitized", sanitized_text=str(sanitized))

        return ValidationResult(status="pass")

    @staticmethod
    def validate_output(
        definition: ToolDefinition,
        result: ToolResult,
    ) -> ValidationResult:
        """Validate a tool's output ``ToolResult``.

        Currently performs basic sanity checks (non-empty output for
        success status).  Returns ``"pass"`` for all error/timeout
        results since those are expected failure modes.
        """
        if result.status == "success":
            if result.output is None:
                return ValidationResult(
                    status="reject",
                    reason="Success result must have non-null output",
                )
            if not result.output.strip():
                return ValidationResult(
                    status="reject",
                    reason="Success result must have non-empty output",
                )
        return ValidationResult(status="pass")

    @staticmethod
    def sanitize(
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Sanitize *arguments* by removing unknown fields and coercing
        types according to the parameter schema.

        Never raises — falls back to returning the original arguments
        if the schema is missing or malformed.
        """
        schema = definition.parameters
        if not schema or not isinstance(schema, dict):
            return dict(arguments)

        properties: dict[str, Any] = schema.get("properties", {})
        allow_extra = schema.get("additionalProperties", True)

        sanitized: dict[str, Any] = {}
        for field, value in arguments.items():
            if field not in properties and not allow_extra:
                continue
            field_schema = properties.get(field, {})
            expected_type_name = field_schema.get("type", "string")
            expected_type = ToolValidation._TYPE_MAP.get(expected_type_name)
            if (
                expected_type is not None
                and value is not None
                and not isinstance(value, expected_type)
            ):
                try:
                    sanitized[field] = expected_type(value)
                    continue
                except (ValueError, TypeError):
                    pass
            sanitized[field] = value

        return sanitized
