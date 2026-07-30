"""Python syntax validator implementation for Syntax Master."""

from __future__ import annotations

import ast
from typing import Any, Dict


class PythonValidator:
    """Validates Python source code syntax using Python's built-in ast module."""

    def validate_syntax(self, code_string: str) -> Dict[str, Any]:
        """Parses and validates the given Python source code string.

        Args:
            code_string: The raw Python source code string to validate.

        Returns:
            A dictionary containing:
            - "is_valid": True if syntax is valid, False otherwise.
            - "error": Formatted error message string if invalid, None if valid.
            - "line": Line number of syntax error if invalid (1-based int), omitted or None.
            - "offset": Offset position of syntax error if invalid (1-based int), omitted or None.
        """
        try:
            ast.parse(code_string)
            return {
                "is_valid": True,
                "error": None,
            }
        except SyntaxError as err:
            formatted_msg = f"SyntaxError: {err.msg}"
            return {
                "is_valid": False,
                "error": formatted_msg,
                "line": err.lineno,
                "offset": err.offset,
            }
