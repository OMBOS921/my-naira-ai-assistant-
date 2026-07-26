"""
GPUDetector — Discovers dedicated GPUs, VRAM, and CUDA compute support.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from backend.modules.capability.detectors.base import BaseDetector
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)


class GPUDetector(BaseDetector):
    """Detector for graphics hardware and compute acceleration."""

    name = "gpu_detector"
    category = CapabilityCategory.HARDWARE

    def detect(self) -> dict[str, CapabilityInfo]:
        results: dict[str, CapabilityInfo] = {}
        now = time.time()

        gpu_details = self._detect_gpu()
        has_gpu = gpu_details.get("count", 0) > 0

        results["gpu"] = CapabilityInfo(
            name="gpu",
            category=CapabilityCategory.HARDWARE,
            status=(
                CapabilityStatus.AVAILABLE if has_gpu else CapabilityStatus.UNAVAILABLE
            ),
            confidence=CapabilityConfidence.HIGH if has_gpu else CapabilityConfidence.MEDIUM,
            details=gpu_details,
            last_updated=now,
            ttl=120.0,
        )

        return results

    def _detect_gpu(self) -> dict[str, Any]:
        gpus: list[dict[str, Any]] = []

        # 1. PyTorch CUDA check
        try:
            import torch

            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    name = torch.cuda.get_device_name(i)
                    mem = torch.cuda.get_device_properties(i).total_memory
                    gpus.append(
                        {
                            "name": name,
                            "type": "nvidia_cuda",
                            "vram_bytes": mem,
                            "vram_mb": mem // (1024 * 1024),
                            "cuda_available": True,
                        }
                    )
                if gpus:
                    return {"count": len(gpus), "gpus": gpus, "cuda_support": True}
        except ImportError:
            pass

        # 2. nvidia-smi CLI check
        smi_bin = shutil.which("nvidia-smi")
        if smi_bin:
            try:
                out = subprocess.check_output(
                    [
                        smi_bin,
                        "--query-gpu=name,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    timeout=1.5,
                    text=True,
                )
                for line in out.strip().splitlines():
                    if "," in line:
                        parts = line.split(",")
                        gpus.append(
                            {
                                "name": parts[0].strip(),
                                "type": "nvidia",
                                "vram_mb": int(parts[1].strip()) if parts[1].strip().isdigit() else 0,
                                "cuda_available": True,
                            }
                        )
                if gpus:
                    return {"count": len(gpus), "gpus": gpus, "cuda_support": True}
            except Exception:
                pass

        # 3. Windows WMI / PowerShell query fallback
        if sys.platform == "win32":
            try:
                import ctypes

                # Quick check via WMI / PowerShell if nvidia-smi not present
                cmd = 'powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Name, AdapterRAM"'
                out = subprocess.check_output(
                    cmd, shell=True, timeout=2.0, text=True, stderr=subprocess.DEVNULL
                )
                if out:
                    lines = [l.strip() for l in out.splitlines() if l.strip()]
                    for line in lines:
                        if "Name" in line or "----" in line:
                            continue
                        gpus.append({"name": line, "type": "display_adapter"})
                if gpus:
                    return {"count": len(gpus), "gpus": gpus, "cuda_support": False}
            except Exception:
                pass

        return {"count": 0, "gpus": [], "cuda_support": False}
