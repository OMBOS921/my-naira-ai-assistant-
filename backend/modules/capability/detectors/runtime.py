"""
RuntimeDetector — Discovers language runtimes (Python, Node, Java, Docker).
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from backend.modules.capability.detectors.base import BaseDetector
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)


class RuntimeDetector(BaseDetector):
    """Detector for programming runtimes and container engines."""

    name = "runtime_detector"
    category = CapabilityCategory.RUNTIME

    def detect(self) -> dict[str, CapabilityInfo]:
        results: dict[str, CapabilityInfo] = {}
        now = time.time()

        # 1. Python installations
        pythons = self._find_pythons()
        results["python"] = CapabilityInfo(
            name="python",
            category=CapabilityCategory.RUNTIME,
            status=CapabilityStatus.AVAILABLE if pythons else CapabilityStatus.UNAVAILABLE,
            confidence=CapabilityConfidence.VERIFIED,
            details={
                "active_executable": sys.executable,
                "active_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "installations": pythons,
            },
            last_updated=now,
            ttl=300.0,
        )

        # 2. Node.js runtime
        node_path = shutil.which("node")
        results["node"] = CapabilityInfo(
            name="node",
            category=CapabilityCategory.RUNTIME,
            status=CapabilityStatus.AVAILABLE if node_path else CapabilityStatus.UNAVAILABLE,
            confidence=CapabilityConfidence.VERIFIED if node_path else CapabilityConfidence.HIGH,
            details={"executable": node_path} if node_path else {},
            last_updated=now,
            ttl=300.0,
        )

        # 3. Java runtime
        java_path = shutil.which("java")
        java_home = os.environ.get("JAVA_HOME")
        results["java"] = CapabilityInfo(
            name="java",
            category=CapabilityCategory.RUNTIME,
            status=CapabilityStatus.AVAILABLE if java_path else CapabilityStatus.UNAVAILABLE,
            confidence=CapabilityConfidence.VERIFIED if java_path else CapabilityConfidence.HIGH,
            details={
                "executable": java_path,
                "java_home": java_home,
            },
            last_updated=now,
            ttl=300.0,
        )

        # 4. Docker runtime
        docker_path = shutil.which("docker")
        results["docker"] = CapabilityInfo(
            name="docker",
            category=CapabilityCategory.RUNTIME,
            status=CapabilityStatus.AVAILABLE if docker_path else CapabilityStatus.UNAVAILABLE,
            confidence=CapabilityConfidence.VERIFIED if docker_path else CapabilityConfidence.HIGH,
            details={"executable": docker_path},
            last_updated=now,
            ttl=120.0,
        )

        return results

    def _find_pythons(self) -> list[dict[str, str]]:
        found: list[dict[str, str]] = [
            {
                "path": sys.executable,
                "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "type": "current",
            }
        ]

        seen_paths = {os.path.normpath(sys.executable)}

        candidates = ["python", "python3", "py"]
        for cand in candidates:
            p = shutil.which(cand)
            if p:
                norm_p = os.path.normpath(p)
                if norm_p not in seen_paths:
                    seen_paths.add(norm_p)
                    found.append({"path": p, "type": "system"})

        return found
