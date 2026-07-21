from __future__ import annotations

import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

_LOG = logging.getLogger("naira.coding_agent.cicd")


class PipelineStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class PipelineRun:
    id: str
    pipeline_name: str
    commit_sha: str
    branch: str
    status: PipelineStatus
    started_at: float
    finished_at: float | None = None
    duration_ms: float = 0.0
    stages: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CICDStatus:
    pipeline_name: str
    last_run_status: PipelineStatus
    last_run_duration_ms: float
    total_runs: int
    success_count: int
    failure_count: int
    success_rate: float
    recent_runs: list[PipelineRun]


class CICDMonitor:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
        event_bus: object | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._event_bus = event_bus
        self._pipeline_runs: dict[str, list[PipelineRun]] = {}
        self._listeners: dict[str, list[Callable[[PipelineRun], None]]] = {}
        self._total_runs = 0
        self._success_count = 0
        self._failure_count = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("CICDMonitor marked degraded")

    def register_pipeline(self, pipeline_name: str) -> None:
        if pipeline_name not in self._pipeline_runs:
            self._pipeline_runs[pipeline_name] = []
            self._logger.debug("Registered pipeline: %s", pipeline_name)

    def start_run(
        self,
        pipeline_name: str,
        commit_sha: str = "",
        branch: str = "",
    ) -> PipelineRun:
        self.register_pipeline(pipeline_name)
        run = PipelineRun(
            id=str(uuid.uuid4()),
            pipeline_name=pipeline_name,
            commit_sha=commit_sha,
            branch=branch or "main",
            status=PipelineStatus.RUNNING,
            started_at=time.time(),
        )
        self._pipeline_runs[pipeline_name].append(run)
        self._total_runs += 1
        self._notify_listeners(pipeline_name, run)
        return run

    def complete_run(
        self,
        run_id: str,
        status: PipelineStatus,
        stages: dict[str, str] | None = None,
        artifacts: list[str] | None = None,
    ) -> PipelineRun | None:
        run = self._find_run(run_id)
        if run is None:
            return None
        run.status = status
        run.finished_at = time.time()
        run.duration_ms = (run.finished_at - run.started_at) * 1000
        if stages:
            run.stages = stages
        if artifacts:
            run.artifacts = artifacts

        if status == PipelineStatus.SUCCESS:
            self._success_count += 1
        elif status == PipelineStatus.FAILED:
            self._failure_count += 1

        self._notify_listeners(run.pipeline_name, run)

        if self._event_bus is not None:
            emit = getattr(self._event_bus, "emit", None)
            if emit is not None:
                import asyncio
                with contextlib.suppress(Exception):
                    asyncio.ensure_future(emit("cicd.run_complete", {
                        "pipeline": run.pipeline_name,
                        "run_id": run.id,
                        "status": status.value,
                        "duration_ms": run.duration_ms,
                    }))

        return run

    def _find_run(self, run_id: str) -> PipelineRun | None:
        for runs in self._pipeline_runs.values():
            for run in runs:
                if run.id == run_id:
                    return run
        return None

    def get_pipeline_status(self, pipeline_name: str) -> CICDStatus | None:
        runs = self._pipeline_runs.get(pipeline_name)
        if not runs:
            return None
        last = runs[-1]
        total = len(runs)
        success_count = sum(1 for r in runs if r.status == PipelineStatus.SUCCESS)
        failure_count = sum(1 for r in runs if r.status == PipelineStatus.FAILED)
        return CICDStatus(
            pipeline_name=pipeline_name,
            last_run_status=last.status,
            last_run_duration_ms=last.duration_ms,
            total_runs=total,
            success_count=success_count,
            failure_count=failure_count,
            success_rate=round((success_count / max(total, 1)) * 100, 1),
            recent_runs=runs[-10:],
        )

    def get_all_statuses(self) -> dict[str, CICDStatus]:
        return {
            name: status
            for name in self._pipeline_runs
            if (status := self.get_pipeline_status(name)) is not None
        }

    def on_status_change(
        self, pipeline_name: str, callback: Callable[[PipelineRun], None],
    ) -> None:
        if pipeline_name not in self._listeners:
            self._listeners[pipeline_name] = []
        self._listeners[pipeline_name].append(callback)

    def _notify_listeners(self, pipeline_name: str, run: PipelineRun) -> None:
        listeners = self._listeners.get(pipeline_name, []) + self._listeners.get("*", [])
        for cb in listeners:
            try:
                cb(run)
            except Exception as exc:
                self._logger.warning("CICD listener error: %s", exc)

    def metrics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "degraded": self._degraded,
            "pipelines_registered": len(self._pipeline_runs),
            "total_runs": self._total_runs,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
