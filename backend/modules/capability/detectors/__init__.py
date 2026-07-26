"""
Capability detector plugins for local machine capabilities.
"""

from backend.modules.capability.detectors.ai import AIDetector
from backend.modules.capability.detectors.base import BaseDetector
from backend.modules.capability.detectors.browser import BrowserDetector
from backend.modules.capability.detectors.gpu import GPUDetector
from backend.modules.capability.detectors.network import NetworkDetector
from backend.modules.capability.detectors.peripheral import PeripheralDetector
from backend.modules.capability.detectors.runtime import RuntimeDetector
from backend.modules.capability.detectors.software import SoftwareDetector
from backend.modules.capability.detectors.system import SystemDetector

__all__ = [
    "BaseDetector",
    "SoftwareDetector",
    "BrowserDetector",
    "RuntimeDetector",
    "AIDetector",
    "SystemDetector",
    "PeripheralDetector",
    "NetworkDetector",
    "GPUDetector",
]
