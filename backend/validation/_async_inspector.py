from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.validation._types import AsyncIssue

_LOG = logging.getLogger("naira.validation.async_inspector")


@dataclass
class AsyncInspector:
    source_dirs: tuple[str, ...] = ("backend",)
    exclude_patterns: tuple[str, ...] = (
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
    )
    _project_root: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )

    def inspect(self) -> list[AsyncIssue]:
        issues: list[AsyncIssue] = []
        for src_dir in self.source_dirs:
            root = self._project_root / src_dir
            if not root.is_dir():
                continue
            for py_file in sorted(root.rglob("*.py")):
                if any(p in str(py_file) for p in self.exclude_patterns):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                except Exception:
                    continue
                try:
                    tree = ast.parse(source, filename=str(py_file))
                except SyntaxError:
                    continue
                issues.extend(self._check_file(py_file, tree, source))
        return issues

    def _check_file(
        self,
        file_path: Path,
        tree: ast.AST,
        source: str,
    ) -> list[AsyncIssue]:
        issues: list[AsyncIssue] = []
        rel = file_path.relative_to(self._project_root)
        rel_str = str(rel.as_posix())

        async_funcs = set[str]()
        sync_methods_with_await = set[str]()

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                async_funcs.add(node.name)

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_await = any(
                    isinstance(child, ast.Await) for child in ast.walk(node)
                )
                if isinstance(node, ast.FunctionDef) and has_await:
                    sync_methods_with_await.add(node.name)
                calls = self._find_blocking_calls(node)
                for call_name, lineno in calls:
                    if isinstance(node, ast.AsyncFunctionDef):
                        issues.append(
                            AsyncIssue(
                                kind="blocking_call_in_async",
                                file_path=rel_str,
                                line_number=lineno,
                                description=f"Potential blocking call `{call_name}` "
                                    f"in async function `{node.name}`",
                            )
                        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Await):
                continue
            if isinstance(node, ast.Call):
                func = self._get_call_name(node)
                if func and func.endswith(".create_task") or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "create_task"
                ):
                    pass
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "_run_async"
                ):
                    pass

        fire_forget = self._find_fire_and_forget(tree)
        for ff in fire_forget:
            issues.append(ff)

        return issues

    def _find_blocking_calls(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[tuple[str, int]]:
        calls: list[tuple[str, int]] = []
        blocking_keywords = {
            "time.sleep",
            "subprocess.run",
            "subprocess.call",
            "subprocess.check_output",
            "requests.get",
            "requests.post",
            "urllib.request",
            "socket.connect",
            "socket.recv",
            "socket.send",
            "os.popen",
            "concurrent.futures",
        }
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = self._get_call_name(child)
                if name:
                    for bk in blocking_keywords:
                        if name.startswith(bk) or bk in name:
                            calls.append((name, child.lineno))
                            break
        return calls

    def _find_fire_and_forget(self, tree: ast.AST) -> list[AsyncIssue]:
        issues: list[AsyncIssue] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if child.func.attr == "create_task":
                                if not self._is_awaited(child, node):
                                    pass
        return issues

    def _is_awaited(
        self, target: ast.Call, func_node: ast.AsyncFunctionDef
    ) -> bool:
        for node in ast.walk(func_node):
            if isinstance(node, ast.Await):
                if (
                    isinstance(node.value, ast.Call)
                    and node.value.func == target.func
                ):
                    return True
        return False

    def _get_call_name(self, node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Attribute):
            parts: list[str] = []
            curr: Any = node.func
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
            elif isinstance(curr, ast.Call):
                return None
            else:
                return None
            return ".".join(reversed(parts))
        if isinstance(node.func, ast.Name):
            return node.func.id
        return None
