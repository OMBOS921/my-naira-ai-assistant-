from __future__ import annotations

import logging
from pathlib import Path

from backend.modules.coding_agent._exceptions import LanguageDetectionError
from backend.modules.coding_agent.ports.language_detector_port import LanguageDetectorPort

_LOG = logging.getLogger("naira.coding_agent.language_detector")

_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".cs": "csharp",
    ".fs": "fsharp",
    ".swift": "swift",
    ".scala": "scala",
    ".r": "r",
    ".m": "objective-c",
    ".mm": "objective-c",
    ".pl": "perl",
    ".pm": "perl",
    ".lua": "lua",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".fish": "fish",
    ".ps1": "powershell",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".rst": "restructuredtext",
    ".tex": "latex",
    ".dart": "dart",
    ".lisp": "lisp",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".hrl": "erlang",
    ".hs": "haskell",
    ".lhs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".vue": "vue",
    ".svelte": "svelte",
    ".astro": "astro",
    ".zig": "zig",
    ".nim": "nim",
    ".cr": "crystal",
}

_LANGUAGE_EXTENSIONS: dict[str, list[str]] = {}
for ext, lang in _EXTENSION_MAP.items():
    _LANGUAGE_EXTENSIONS.setdefault(lang, []).append(ext)


class FileExtensionLanguageDetectorProvider(LanguageDetectorPort):
    """Default provider for the Language Detector port.

    Detects programming languages using file extensions and
    basic code heuristics.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "file_extension_language_detector"

    async def detect_file(
        self,
        path: str,
    ) -> str:
        ext = Path(path).suffix.lower()
        lang = _EXTENSION_MAP.get(ext)
        if lang is None:
            raise LanguageDetectionError(f"Unknown language for file: {path}")
        return lang

    async def detect_code(
        self,
        code: str,
    ) -> str:
        if not code.strip():
            raise LanguageDetectionError("Cannot detect language from empty code")
        first_line = code.strip().split("\n")[0].strip()
        if first_line.startswith("#!"):
            shebang_map = {
                "python": ("python", "python3"),
                "bash": ("bash", "sh"),
                "node": ("node", "nodejs"),
                "perl": ("perl"),
                "ruby": ("ruby"),
            }
            for lang, interpreters in shebang_map.items():
                if isinstance(interpreters, str):
                    interpreters = (interpreters,)
                for interp in interpreters:
                    if interp in first_line:
                        return lang
        ext = Path(first_line).suffix.lower() if "." in first_line else ""
        if ext and ext in _EXTENSION_MAP:
            return _EXTENSION_MAP[ext]
        for keyword, lang in [
            ("import ", "python"),
            ("package ", "go"),
            ("fn ", "rust"),
            ("func ", "go"),
            ("def ", "python"),
            ("class ", "python"),
            ("#include", "c"),
            ("using ", "csharp"),
            ("namespace ", "csharp"),
            ("console.log", "javascript"),
            ("function ", "javascript"),
            ("const ", "javascript"),
            ("let ", "javascript"),
            ("var ", "javascript"),
            ("<html", "html"),
            ("<!DOCTYPE", "html"),
            ("SELECT ", "sql"),
            ("CREATE ", "sql"),
        ]:
            if keyword in code:
                return lang
        if code.count("def ") > 0 or code.count("import ") > 0 or code.count("class ") > 0:
            return "python"
        return "unknown"

    async def detect_directory(
        self,
        path: str,
    ) -> dict[str, int]:
        lang_counts: dict[str, int] = {}
        root = Path(path)
        if not root.is_dir():
            raise LanguageDetectionError(f"Not a directory: {path}")
        for f in root.rglob("*"):
            if f.is_file() and f.suffix.lower() in _EXTENSION_MAP:
                lang = _EXTENSION_MAP[f.suffix.lower()]
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
        return lang_counts or {"unknown": 0}

    async def get_extensions(
        self,
        language: str,
    ) -> list[str]:
        return _LANGUAGE_EXTENSIONS.get(language.lower(), [])

    async def close(self) -> None:
        self._available = False
        self._logger.info("Language detector provider closed")
