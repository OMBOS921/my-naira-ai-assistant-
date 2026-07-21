from __future__ import annotations

import gc
import logging
import os
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

_LOG = logging.getLogger("naira.validation.resource_inspector")


@dataclass
class ResourceSnapshot:
    thread_count: int
    fd_count: int
    gc_objects: int
    socket_count: int

    def __str__(self) -> str:
        return (
            f"threads={self.thread_count} fds={self.fd_count} "
            f"gc_objects={self.gc_objects} sockets={self.socket_count}"
        )


@dataclass
class ResourceInspector:
    _snapshots: list[ResourceSnapshot] = field(default_factory=list)

    def snapshot(self) -> ResourceSnapshot:
        gc.collect()
        snap = ResourceSnapshot(
            thread_count=threading.active_count(),
            fd_count=self._count_fds(),
            gc_objects=len(gc.get_objects()),
            socket_count=self._count_sockets(),
        )
        self._snapshots.append(snap)
        return snap

    def trends(self) -> dict[str, str]:
        if len(self._snapshots) < 2:
            return {}
        first = self._snapshots[0]
        last = self._snapshots[-1]
        trends: dict[str, str] = {}
        for attr in ("thread_count", "fd_count", "gc_objects", "socket_count"):
            delta = getattr(last, attr) - getattr(first, attr)
            if delta > 0:
                trends[attr] = f"+{delta} (growth)"
            elif delta < 0:
                trends[attr] = f"{delta} (decline)"
            else:
                trends[attr] = "stable"
        return trends

    def has_growth(self, threshold: int = 0) -> bool:
        if len(self._snapshots) < 2:
            return False
        trends = self.trends()
        for attr in ("thread_count", "fd_count", "gc_objects"):
            val = trends.get(attr, "stable")
            if val != "stable":
                delta_str = val.split(" ")[0]
                try:
                    delta = int(delta_str)
                    if delta > threshold:
                        return True
                except ValueError:
                    pass
        return False

    @staticmethod
    def _count_fds() -> int:
        count = 0
        if hasattr(os, "listdir"):
            try:
                count = len(os.listdir(f"/proc/{os.getpid()}/fd"))
            except (FileNotFoundError, PermissionError, NotADirectoryError):
                pass
        return count

    @staticmethod
    def _count_sockets() -> int:
        import socket as _socket_mod

        count = 0
        for obj in gc.get_objects():
            if isinstance(obj, _socket_mod.socket):
                try:
                    if obj.fileno() != -1:
                        count += 1
                except Exception:
                    pass
        return count

    def reset(self) -> None:
        self._snapshots.clear()
