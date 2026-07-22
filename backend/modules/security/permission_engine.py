from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class PermissionDecision(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    NEEDS_CONFIRMATION = "needs_confirmation"
    RATE_LIMITED = "rate_limited"


@dataclass
class PermissionResult:
    decision: PermissionDecision
    tool_name: str
    reason: str
    risk_level: str  # "low","medium","high","critical"
    requires_user_prompt: bool = False
    user_prompt_message: str = ""
    cached_from_scope: str = ""


RATE_LIMITS: dict[str, dict[str, Any] | None] = {
    "critical": {"max_calls": 2, "window_seconds": 60, "cooldown_seconds": 10},
    "high": {"max_calls": 5, "window_seconds": 60, "cooldown_seconds": 0},
    "medium": {"max_calls": 30, "window_seconds": 60, "cooldown_seconds": 0},
    "low": None,
}

TOOL_RISK_MAP: dict[str, str] = {
    "pc_power": "critical",
    "pc_process": "high",
    "shell_exec": "high",
    "registry_write": "critical",
    "registry_delete": "critical",
    "format_drive": "critical",
    "pc_launch_application": "medium",
    "pc_keyboard": "medium",
    "pc_clipboard": "medium",
    "pc_volume": "low",
    "browser_navigate": "medium",
    "browser_extract": "medium",
    "pc_filesystem_delete": "high",
    "pc_filesystem_write": "medium",
    "pc_filesystem_read": "low",
    "pc_filesystem_create": "low",
    "fcr_screenshot": "low",
    "fcr_system_info": "low",
    "fcr_window_minimize": "low",
    "fcr_window_maximize": "low",
    "fcr_window_close": "medium",
    "fcr_kill_process": "high",
    "fcr_web_search": "low",
    "fcr_clipboard_clear": "low",
    "fcr_run_cmd_safe": "medium",
}

DEFAULT_RISK = "medium"

RISK_MESSAGES = {
    "critical": "🚨 Critical Security Alert — Action needs user confirmation!",
    "high": "⚠️ High Risk Action — Please confirm to proceed.",
    "medium": "🔔 Permission Request — Assistant wants to perform an action.",
    "low": "ℹ️ Low Risk Action.",
}

OP_DESCRIPTIONS = {
    "pc_power": "system power state change (shutdown/restart/sleep)",
    "pc_process": "managing or terminating system processes",
    "shell_exec": "executing shell or command prompt instructions",
    "registry_write": "modifying Windows system registry entries",
    "registry_delete": "deleting Windows system registry entries",
    "format_drive": "formatting a disk drive (data destruction hazard)",
    "fcr_kill_process": "force terminating a process",
    "fcr_run_cmd_safe": "executing a safe command line operation",
    "fcr_window_close": "closing an application window",
    "pc_filesystem_delete": "deleting files or directories from filesystem",
    "pc_filesystem_write": "writing files to filesystem",
    "browser_navigate": "navigating to an external webpage",
    "browser_extract": "extracting web content",
    "pc_launch_application": "launching a desktop application",
    "pc_keyboard": "simulating keyboard input",
    "pc_clipboard": "accessing or clearing system clipboard",
}


class PermissionEngine:
    def __init__(
        self,
        db_path: str | Path,
        session_id: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._db_path = Path(db_path).resolve()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._session_id = session_id
        self._logger = logger or logging.getLogger(__name__)

        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")

        self._write_lock = threading.Lock()
        self._session_cache: dict[str, PermissionDecision] = {}

        self._init_db()

    def _init_db(self) -> None:
        with self._write_lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS permission_grants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    granted_at REAL NOT NULL,
                    expires_at REAL,
                    granted_by TEXT DEFAULT 'user',
                    reason TEXT,
                    UNIQUE(tool_name, scope)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limit_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    called_at REAL NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT,
                    decision TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    duration_ms REAL DEFAULT 0,
                    session_id TEXT,
                    called_at REAL NOT NULL,
                    result_summary TEXT
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rate_calls ON rate_limit_calls(tool_name, called_at)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_called ON audit_log(called_at DESC)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_log(tool_name, called_at DESC)"
            )
            self._conn.commit()

    def check(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        risk_level: str | None = None,
    ) -> PermissionResult:
        effective_risk = risk_level or TOOL_RISK_MAP.get(tool_name, DEFAULT_RISK)

        try:
            # STEP 2: Session cache check
            if tool_name in self._session_cache:
                decision = self._session_cache[tool_name]
                prompt_msg = (
                    self._build_prompt_message(tool_name, arguments, effective_risk)
                    if decision == PermissionDecision.NEEDS_CONFIRMATION
                    else ""
                )
                return PermissionResult(
                    decision=decision,
                    tool_name=tool_name,
                    reason=f"Cached session decision: {decision.value}",
                    risk_level=effective_risk,
                    requires_user_prompt=(decision == PermissionDecision.NEEDS_CONFIRMATION),
                    user_prompt_message=prompt_msg,
                    cached_from_scope="session",
                )

            # STEP 3: Rate limit check
            rate_limit_res = self._check_rate_limit(tool_name, effective_risk)
            if rate_limit_res is not None:
                return rate_limit_res

            # STEP 4: Permanent grant check
            grant = self._get_permanent_grant(tool_name)
            if grant is not None:
                dec_str = grant.get("decision", "allowed")
                try:
                    decision = PermissionDecision(dec_str)
                except ValueError:
                    decision = PermissionDecision.ALLOWED
                self._session_cache[tool_name] = decision
                prompt_msg = (
                    self._build_prompt_message(tool_name, arguments, effective_risk)
                    if decision == PermissionDecision.NEEDS_CONFIRMATION
                    else ""
                )
                return PermissionResult(
                    decision=decision,
                    tool_name=tool_name,
                    reason=grant.get("reason") or f"Permanent grant: {decision.value}",
                    risk_level=effective_risk,
                    requires_user_prompt=(decision == PermissionDecision.NEEDS_CONFIRMATION),
                    user_prompt_message=prompt_msg,
                    cached_from_scope="permanent",
                )

            # STEP 5: Default policy evaluation
            if effective_risk == "low":
                self._session_cache[tool_name] = PermissionDecision.ALLOWED
                return PermissionResult(
                    decision=PermissionDecision.ALLOWED,
                    tool_name=tool_name,
                    reason="Default security policy auto-allows low risk tool",
                    risk_level=effective_risk,
                    requires_user_prompt=False,
                    user_prompt_message="",
                    cached_from_scope="",
                )
            elif effective_risk == "medium":
                if tool_name.startswith("fcr_"):
                    self._session_cache[tool_name] = PermissionDecision.ALLOWED
                    return PermissionResult(
                        decision=PermissionDecision.ALLOWED,
                        tool_name=tool_name,
                        reason="Default security policy auto-allows medium risk FCR tool",
                        risk_level=effective_risk,
                        requires_user_prompt=False,
                        user_prompt_message="",
                        cached_from_scope="",
                    )
                else:
                    prompt_msg = self._build_prompt_message(tool_name, arguments, effective_risk)
                    return PermissionResult(
                        decision=PermissionDecision.NEEDS_CONFIRMATION,
                        tool_name=tool_name,
                        reason="Default security policy requires confirmation for medium risk tool",
                        risk_level=effective_risk,
                        requires_user_prompt=True,
                        user_prompt_message=prompt_msg,
                        cached_from_scope="",
                    )
            else:
                # high or critical
                prompt_msg = self._build_prompt_message(tool_name, arguments, effective_risk)
                return PermissionResult(
                    decision=PermissionDecision.NEEDS_CONFIRMATION,
                    tool_name=tool_name,
                    reason=f"Default security policy requires confirmation for {effective_risk} risk tool",
                    risk_level=effective_risk,
                    requires_user_prompt=True,
                    user_prompt_message=prompt_msg,
                    cached_from_scope="",
                )
        except Exception as exc:
            self._logger.error("Permission check crashed (failing open): %s", exc)
            return PermissionResult(
                decision=PermissionDecision.ALLOWED,
                tool_name=tool_name,
                reason=f"Fail-open exception: {exc}",
                risk_level=effective_risk,
                requires_user_prompt=False,
                user_prompt_message="",
                cached_from_scope="",
            )

    def grant(
        self,
        tool_name: str,
        decision: PermissionDecision | str,
        scope: str = "session",
        reason: str | None = None,
    ) -> None:
        try:
            if isinstance(decision, str):
                try:
                    enum_decision = PermissionDecision(decision)
                except ValueError:
                    enum_decision = PermissionDecision.ALLOWED
            else:
                enum_decision = decision

            self._session_cache[tool_name] = enum_decision

            if scope == "permanent":
                with self._write_lock:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO permission_grants 
                        (tool_name, decision, scope, granted_at, reason)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            tool_name,
                            enum_decision.value,
                            "permanent",
                            time.time(),
                            reason or f"Granted by user ({enum_decision.value})",
                        ),
                    )
                    self._conn.commit()
        except Exception as exc:
            self._logger.error("Error setting permission grant: %s", exc)

    def _check_rate_limit(
        self, tool_name: str, risk_level: str
    ) -> PermissionResult | None:
        config = RATE_LIMITS.get(risk_level)
        if not config:
            return None

        now = time.time()
        window_start = now - config["window_seconds"]

        try:
            cur = self._conn.execute(
                "SELECT COUNT(*) as count FROM rate_limit_calls WHERE tool_name = ? AND called_at > ?",
                (tool_name, window_start),
            )
            row = cur.fetchone()
            count = row["count"] if row else 0

            if count >= config["max_calls"]:
                return PermissionResult(
                    decision=PermissionDecision.RATE_LIMITED,
                    tool_name=tool_name,
                    reason=f"Rate limit exceeded: max {config['max_calls']} calls per {config['window_seconds']}s",
                    risk_level=risk_level,
                    requires_user_prompt=False,
                    user_prompt_message="",
                    cached_from_scope="",
                )

            cooldown = config.get("cooldown_seconds", 0)
            if cooldown > 0:
                cur2 = self._conn.execute(
                    "SELECT MAX(called_at) as latest FROM rate_limit_calls WHERE tool_name = ?",
                    (tool_name,),
                )
                row2 = cur2.fetchone()
                latest = row2["latest"] if row2 and row2["latest"] is not None else 0
                if (now - latest) < cooldown:
                    rem = cooldown - (now - latest)
                    return PermissionResult(
                        decision=PermissionDecision.RATE_LIMITED,
                        tool_name=tool_name,
                        reason=f"Cooldown active: wait {rem:.1f}s",
                        risk_level=risk_level,
                        requires_user_prompt=False,
                        user_prompt_message="",
                        cached_from_scope="",
                    )
        except Exception as exc:
            self._logger.error("Rate limit check error: %s", exc)

        return None

    def record_call(self, tool_name: str) -> None:
        try:
            now = time.time()
            with self._write_lock:
                self._conn.execute(
                    "INSERT INTO rate_limit_calls (tool_name, called_at) VALUES (?, ?)",
                    (tool_name, now),
                )
                self._conn.execute(
                    "DELETE FROM rate_limit_calls WHERE called_at < ?",
                    (now - 3600,),
                )
                self._conn.commit()
        except Exception as exc:
            self._logger.warning("Error recording tool call: %s", exc)

    def log_audit(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        decision: PermissionDecision | str,
        risk_level: str,
        duration_ms: float = 0,
        session_id: str | None = None,
        result_summary: str | None = None,
    ) -> None:
        try:
            now = time.time()
            args_json = json.dumps(arguments) if arguments else None
            dec_str = decision.value if isinstance(decision, PermissionDecision) else str(decision)
            sess_id = session_id or self._session_id

            with self._write_lock:
                self._conn.execute(
                    """
                    INSERT INTO audit_log 
                    (tool_name, arguments_json, decision, risk_level, duration_ms, session_id, called_at, result_summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tool_name,
                        args_json,
                        dec_str,
                        risk_level,
                        duration_ms,
                        sess_id,
                        now,
                        result_summary,
                    ),
                )
                self._conn.execute(
                    "DELETE FROM audit_log WHERE called_at < ?",
                    (now - 7 * 86400,),
                )
                self._conn.commit()
        except Exception as exc:
            self._logger.warning("Error logging audit entry: %s", exc)

    def _get_permanent_grant(self, tool_name: str) -> dict[str, Any] | None:
        try:
            now = time.time()
            cur = self._conn.execute(
                """
                SELECT * FROM permission_grants 
                WHERE tool_name = ? AND scope = 'permanent' AND (expires_at IS NULL OR expires_at > ?)
                """,
                (tool_name, now),
            )
            row = cur.fetchone()
            if row:
                return dict(row)
        except Exception as exc:
            self._logger.error("Error querying permanent grant: %s", exc)
        return None

    def _build_prompt_message(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        risk_level: str,
    ) -> str:
        header = RISK_MESSAGES.get(risk_level, RISK_MESSAGES["medium"])
        op_desc = OP_DESCRIPTIONS.get(tool_name, f"executing tool '{tool_name}'")
        arg_str = f" with args {json.dumps(arguments)}" if arguments else ""
        return f"{header}\nAction: {op_desc}{arg_str} [Risk: {risk_level.upper()}]"

    def revoke(self, tool_name: str, scope: str = "permanent") -> bool:
        self._session_cache.pop(tool_name, None)
        if scope == "permanent":
            try:
                with self._write_lock:
                    cur = self._conn.execute(
                        "DELETE FROM permission_grants WHERE tool_name = ? AND scope = 'permanent'",
                        (tool_name,),
                    )
                    self._conn.commit()
                    return cur.rowcount > 0
            except Exception as exc:
                self._logger.error("Error revoking permanent grant: %s", exc)
                return False
        return True

    def get_audit_log(
        self, limit: int = 50, tool_name: str | None = None
    ) -> list[dict[str, Any]]:
        try:
            if tool_name:
                cur = self._conn.execute(
                    "SELECT * FROM audit_log WHERE tool_name = ? ORDER BY called_at DESC LIMIT ?",
                    (tool_name, limit),
                )
            else:
                cur = self._conn.execute(
                    "SELECT * FROM audit_log ORDER BY called_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            self._logger.error("Error fetching audit log: %s", exc)
            return []

    def get_stats(self) -> dict[str, Any]:
        try:
            c1 = self._conn.execute("SELECT COUNT(*) as cnt FROM audit_log").fetchone()
            total_ops = c1["cnt"] if c1 else 0

            c2 = self._conn.execute("SELECT COUNT(*) as cnt FROM audit_log WHERE decision = 'allowed'").fetchone()
            allowed = c2["cnt"] if c2 else 0

            c3 = self._conn.execute("SELECT COUNT(*) as cnt FROM audit_log WHERE decision = 'denied'").fetchone()
            denied = c3["cnt"] if c3 else 0

            c4 = self._conn.execute("SELECT COUNT(*) as cnt FROM audit_log WHERE decision = 'rate_limited'").fetchone()
            rate_limited = c4["cnt"] if c4 else 0

            c5 = self._conn.execute(
                "SELECT tool_name, COUNT(*) as cnt FROM audit_log GROUP BY tool_name ORDER BY cnt DESC LIMIT 5"
            ).fetchall()
            top_tools = [{"tool_name": r["tool_name"], "count": r["cnt"]} for r in c5]

            c6 = self._conn.execute("SELECT COUNT(*) as cnt FROM permission_grants WHERE scope = 'permanent'").fetchone()
            perm_grants = c6["cnt"] if c6 else 0

            return {
                "total_operations": total_ops,
                "allowed": allowed,
                "denied": denied,
                "rate_limited": rate_limited,
                "top_tools": top_tools,
                "permanent_grants": perm_grants,
            }
        except Exception as exc:
            self._logger.error("Error fetching security stats: %s", exc)
            return {}

    def clear_session(self) -> None:
        self._session_cache.clear()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
