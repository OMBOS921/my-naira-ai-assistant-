from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.validation._types import ValidationReport, ValidationResult

_LOG = logging.getLogger("naira.validation.history")


@dataclass
class ValidationHistory:
    db_path: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
        / "validation_history.db"
    )
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _conn: sqlite3.Connection | None = None

    def __post_init__(self) -> None:
        self._connect()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS validation_runs (
                run_id TEXT PRIMARY KEY,
                started_at REAL,
                finished_at REAL,
                total_passed INTEGER,
                total_failed INTEGER,
                total_skipped INTEGER,
                total_duration_s REAL,
                coverage_pct REAL,
                report_json TEXT
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS validation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                kind TEXT,
                name TEXT,
                passed INTEGER,
                duration_s REAL,
                failures_json TEXT,
                auto_fix_status TEXT
            )"""
        )
        self._conn.commit()

    def store_report(self, report: ValidationReport) -> None:
        with self._lock:
            if self._conn is None:
                return
            finished = report.finished_at
            finished_ts = finished.timestamp() if finished else 0.0
            self._conn.execute(
                """INSERT OR REPLACE INTO validation_runs
                   (run_id, started_at, finished_at, total_passed, total_failed,
                    total_skipped, total_duration_s, coverage_pct, report_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    report.run_id,
                    report.started_at.timestamp(),
                    finished_ts,
                    report.total_passed,
                    report.total_failed,
                    report.total_skipped,
                    report.total_duration_s,
                    report.coverage_pct or 0.0,
                    json.dumps({
                        "results": [
                            {
                                "kind": r.kind,
                                "name": r.name,
                                "passed": r.passed,
                                "duration_s": r.duration_s,
                                "failures": list(r.failures),
                            }
                            for r in report.results
                        ],
                    }),
                ),
            )
            for r in report.results:
                self._conn.execute(
                    """INSERT INTO validation_results
                       (run_id, kind, name, passed, duration_s, failures_json, auto_fix_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        report.run_id,
                        r.kind,
                        r.name,
                        1 if r.passed else 0,
                        r.duration_s,
                        json.dumps(list(r.failures)),
                        r.auto_fix_status,
                    ),
                )
            self._conn.commit()

    def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            if self._conn is None:
                return []
            cursor = self._conn.execute(
                """SELECT run_id, started_at, finished_at, total_passed, total_failed,
                          total_duration_s, coverage_pct
                   FROM validation_runs
                   ORDER BY started_at DESC
                   LIMIT ?""",
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "run_id": r[0],
                    "started_at": r[1],
                    "finished_at": r[2],
                    "total_passed": r[3],
                    "total_failed": r[4],
                    "total_duration_s": r[5],
                    "coverage_pct": r[6],
                }
                for r in rows
            ]

    @property
    def last_run_passed(self) -> bool | None:
        runs = self.get_recent_runs(1)
        if not runs:
            return None
        return runs[0]["total_failed"] == 0

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
