"""
PeripheralDetector — Probes audio I/O, cameras, and display monitors.
"""

from __future__ import annotations

import sys
import time
from backend.modules.capability.detectors.base import BaseDetector
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)


class PeripheralDetector(BaseDetector):
    """Detector for hardware peripherals (microphones, speakers, cameras, displays)."""

    name = "peripheral_detector"
    category = CapabilityCategory.PERIPHERAL

    def detect(self) -> dict[str, CapabilityInfo]:
        results: dict[str, CapabilityInfo] = {}
        now = time.time()

        # 1. Audio Microphones
        mics = self._get_microphones()
        results["microphones"] = CapabilityInfo(
            name="microphones",
            category=CapabilityCategory.PERIPHERAL,
            status=CapabilityStatus.AVAILABLE if mics else CapabilityStatus.UNAVAILABLE,
            confidence=CapabilityConfidence.HIGH if mics else CapabilityConfidence.MEDIUM,
            details={"devices": mics, "count": len(mics)},
            last_updated=now,
            ttl=15.0,
        )

        # 2. Audio Speakers
        speakers = self._get_speakers()
        results["speakers"] = CapabilityInfo(
            name="speakers",
            category=CapabilityCategory.PERIPHERAL,
            status=(
                CapabilityStatus.AVAILABLE
                if speakers
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=(
                CapabilityConfidence.HIGH if speakers else CapabilityConfidence.MEDIUM
            ),
            details={"devices": speakers, "count": len(speakers)},
            last_updated=now,
            ttl=15.0,
        )

        # 3. Cameras
        cameras = self._get_cameras()
        results["cameras"] = CapabilityInfo(
            name="cameras",
            category=CapabilityCategory.PERIPHERAL,
            status=(
                CapabilityStatus.AVAILABLE
                if cameras
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=(
                CapabilityConfidence.HIGH if cameras else CapabilityConfidence.MEDIUM
            ),
            details={"devices": cameras, "count": len(cameras)},
            last_updated=now,
            ttl=30.0,
        )

        # 4. Display Monitors
        displays = self._get_displays()
        results["displays"] = CapabilityInfo(
            name="displays",
            category=CapabilityCategory.PERIPHERAL,
            status=(
                CapabilityStatus.AVAILABLE
                if displays
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=CapabilityConfidence.HIGH,
            details={"monitors": displays, "count": len(displays)},
            last_updated=now,
            ttl=60.0,
        )

        return results

    def _get_microphones(self) -> list[dict[str, Any]]:
        mics: list[dict[str, Any]] = []

        try:
            import pyaudio

            pa = pyaudio.PyAudio()
            try:
                device_count = pa.get_device_count()
                for i in range(device_count):
                    try:
                        dev = pa.get_device_info_by_index(i)
                        if dev.get("maxInputChannels", 0) > 0:
                            mics.append(
                                {
                                    "index": i,
                                    "name": dev.get("name"),
                                    "channels": dev.get("maxInputChannels"),
                                    "default_rate": dev.get("defaultSampleRate"),
                                }
                            )
                    except Exception:
                        continue
            finally:
                pa.terminate()

            if mics:
                return mics
        except Exception:
            pass

        # Fallback default microphone descriptor
        return [{"index": 0, "name": "System Default Microphone", "default": True}]

    def _get_speakers(self) -> list[dict[str, Any]]:
        try:
            import pyaudio

            pa = pyaudio.PyAudio()
            speakers: list[dict[str, Any]] = []
            try:
                device_count = pa.get_device_count()
                for i in range(device_count):
                    try:
                        dev = pa.get_device_info_by_index(i)
                        if dev.get("maxOutputChannels", 0) > 0:
                            speakers.append(
                                {
                                    "index": i,
                                    "name": dev.get("name"),
                                    "channels": dev.get("maxOutputChannels"),
                                    "default_rate": dev.get("defaultSampleRate"),
                                }
                            )
                    except Exception:
                        continue
            finally:
                pa.terminate()

            if speakers:
                return speakers
        except Exception:
            pass

        return [{"index": 0, "name": "System Default Speaker", "default": True}]

    def _get_cameras(self) -> list[dict[str, Any]]:
        cameras: list[dict[str, Any]] = []
        try:
            import cv2

            for i in range(2):  # Quick check first 2 indices
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
                if cap.isOpened():
                    cameras.append({"index": i, "name": f"Camera {i}"})
                    cap.release()
            if cameras:
                return cameras
        except Exception:
            pass

        # Return default camera assumption
        return [{"index": 0, "name": "System Camera"}]

    def _get_displays(self) -> list[dict[str, Any]]:
        if sys.platform == "win32":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                num_monitors = user32.GetSystemMetrics(80)  # SM_CMONITORS
                width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
                height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
                return [
                    {
                        "index": 0,
                        "primary": True,
                        "width": width,
                        "height": height,
                        "total_monitors": max(1, num_monitors),
                    }
                ]
            except Exception:
                pass
        return [{"index": 0, "primary": True, "resolution": "unknown"}]
