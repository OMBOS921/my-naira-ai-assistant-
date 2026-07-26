"""
AIDetector — Probes Ollama service, local AI runtimes, and LLM providers.
"""

from __future__ import annotations

import json
import shutil
import socket
import time
import urllib.request
from backend.modules.capability.detectors.base import BaseDetector
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)


class AIDetector(BaseDetector):
    """Detector for local AI runtimes, Ollama server, and GPU acceleration."""

    name = "ai_detector"
    category = CapabilityCategory.AI

    def detect(self) -> dict[str, CapabilityInfo]:
        results: dict[str, CapabilityInfo] = {}
        now = time.time()

        # 1. Probe Ollama daemon & models
        ollama_info = self._probe_ollama()
        results["ollama"] = CapabilityInfo(
            name="ollama",
            category=CapabilityCategory.AI,
            status=(
                CapabilityStatus.AVAILABLE
                if ollama_info.get("running")
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=(
                CapabilityConfidence.VERIFIED
                if ollama_info.get("running")
                else CapabilityConfidence.HIGH
            ),
            details=ollama_info,
            last_updated=now,
            ttl=60.0,
        )

        # 2. Local AI Frameworks (PyTorch, Transformers, vLLM, etc.)
        frameworks = self._check_ai_frameworks()
        results["local_ai_runtimes"] = CapabilityInfo(
            name="local_ai_runtimes",
            category=CapabilityCategory.AI,
            status=(
                CapabilityStatus.AVAILABLE
                if frameworks
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=CapabilityConfidence.HIGH,
            details={"frameworks": frameworks},
            last_updated=now,
            ttl=120.0,
        )

        # 3. Best LLM Provider evaluation
        best_provider = self._evaluate_best_provider(ollama_info, frameworks)
        results["best_llm_provider"] = CapabilityInfo(
            name="best_llm_provider",
            category=CapabilityCategory.AI,
            status=(
                CapabilityStatus.AVAILABLE
                if best_provider
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=CapabilityConfidence.MEDIUM,
            details=best_provider or {},
            last_updated=now,
            ttl=60.0,
        )

        return results

    def _probe_ollama(self) -> dict[str, Any]:
        ollama_bin = shutil.which("ollama")
        host = "127.0.0.1"
        port = 11434
        running = False
        models: list[str] = []

        # Quick TCP socket check
        try:
            with socket.create_connection((host, port), timeout=0.5):
                running = True
        except (OSError, TimeoutError):
            running = False

        if running:
            try:
                req = urllib.request.Request(
                    f"http://{host}:{port}/api/tags", headers={"User-Agent": "Naira/1.0"}
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if "models" in data:
                            models = [
                                m.get("name", "")
                                for m in data["models"]
                                if isinstance(m, dict)
                            ]
            except Exception:
                pass

        return {
            "installed": ollama_bin is not None,
            "executable": ollama_bin,
            "running": running,
            "endpoint": f"http://{host}:{port}",
            "models": models,
        }

    def _check_ai_frameworks(self) -> dict[str, bool]:
        frameworks: dict[str, bool] = {}
        for fw in ["torch", "onnxruntime", "transformers", "llama_cpp"]:
            try:
                __import__(fw)
                frameworks[fw] = True
            except ImportError:
                frameworks[fw] = False
        return frameworks

    def _evaluate_best_provider(
        self, ollama_info: dict[str, Any], frameworks: dict[str, bool]
    ) -> dict[str, Any] | None:
        if ollama_info.get("running") and ollama_info.get("models"):
            return {
                "provider": "ollama",
                "type": "local_server",
                "endpoint": ollama_info.get("endpoint"),
                "models": ollama_info.get("models"),
            }
        if frameworks.get("torch"):
            return {
                "provider": "pytorch_local",
                "type": "in_process",
            }
        return None
