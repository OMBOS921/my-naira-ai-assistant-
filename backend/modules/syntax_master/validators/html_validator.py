"""HTML/CSS syntax validator implementation for Syntax Master."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any, Dict, List


class _HTMLSyntaxParser(HTMLParser):
    """Custom HTMLParser that tracks tag opening/closing balance and syntax errors."""

    VOID_ELEMENTS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    }

    def __init__(self) -> None:
        super().__init__()
        self.stack: List[str] = []
        self.errors: List[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        tag_lower = tag.lower()
        if tag_lower not in self.VOID_ELEMENTS:
            self.stack.append(tag_lower)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.VOID_ELEMENTS:
            return
        if not self.stack:
            self.errors.append(f"Unexpected closing tag </{tag}> with no matching opening tag.")
            return
        expected = self.stack.pop()
        if expected != tag_lower:
            self.errors.append(f"Mismatched closing tag </{tag}>. Expected </{expected}>.")


class HTMLValidator:
    """Validates HTML syntax and tag balance using Python's built-in html.parser."""

    def validate_syntax(self, code_string: str) -> Dict[str, Any]:
        """Parses and validates the given HTML code string.

        Args:
            code_string: The raw HTML source code string to validate.

        Returns:
            A dictionary containing:
            - "is_valid": True if HTML parsing and tag balance pass, False otherwise.
            - "error": Error message string if invalid, None if valid.
        """
        if not isinstance(code_string, str):
            return {
                "is_valid": False,
                "error": f"Invalid input type: expected str, got {type(code_string).__name__}",
            }

        parser = _HTMLSyntaxParser()
        try:
            parser.feed(code_string)
            parser.close()

            if parser.errors:
                return {
                    "is_valid": False,
                    "error": f"HTML Syntax Error: {parser.errors[0]}",
                }

            if parser.stack:
                unclosed = ", ".join(f"<{t}>" for t in reversed(parser.stack))
                return {
                    "is_valid": False,
                    "error": f"Unclosed HTML tag(s): {unclosed}",
                }

            return {
                "is_valid": True,
                "error": None,
            }
        except Exception as err:
            return {
                "is_valid": False,
                "error": f"HTML Parsing Error: {str(err)}",
            }
