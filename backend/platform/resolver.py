from typing import Type, TypeVar, Dict

from backend.platform.detection import detect_platform, Platform
from backend.platform.ports.filesystem_port import FilesystemPort
from backend.platform.ports.process_port import ProcessPort

from backend.platform.adapters.windows.filesystem_adapter import WindowsFilesystemAdapter
from backend.platform.adapters.windows.process_adapter import WindowsProcessAdapter

T = TypeVar('T')

ADAPTER_REGISTRY = {
    Platform.WINDOWS: {
        FilesystemPort: WindowsFilesystemAdapter,
        ProcessPort: WindowsProcessAdapter,
    },
    Platform.MACOS: {
        # Fallback/stubs until implemented
        FilesystemPort: WindowsFilesystemAdapter,
        ProcessPort: WindowsProcessAdapter,
    },
    Platform.LINUX_UBUNTU: {
        FilesystemPort: WindowsFilesystemAdapter,
        ProcessPort: WindowsProcessAdapter,
    },
    Platform.LINUX_FEDORA: {
        FilesystemPort: WindowsFilesystemAdapter,
        ProcessPort: WindowsProcessAdapter,
    },
    Platform.LINUX_ARCH: {
        FilesystemPort: WindowsFilesystemAdapter,
        ProcessPort: WindowsProcessAdapter,
    },
    Platform.LINUX_KALI: {
        FilesystemPort: WindowsFilesystemAdapter,
        ProcessPort: WindowsProcessAdapter,
    },
    Platform.UNKNOWN: {
        FilesystemPort: WindowsFilesystemAdapter,
        ProcessPort: WindowsProcessAdapter,
    }
}

def get_port(port_cls: Type[T]) -> T:
    platform = detect_platform()
    adapters = ADAPTER_REGISTRY.get(platform)
    
    if not adapters:
        # Fallback to windows if platform is missing
        adapters = ADAPTER_REGISTRY[Platform.WINDOWS]
        
    adapter_cls = adapters.get(port_cls)
    if not adapter_cls:
        # Fallback to windows adapter if missing
        adapter_cls = ADAPTER_REGISTRY[Platform.WINDOWS].get(port_cls)
        if not adapter_cls:
            raise NotImplementedError(f"No adapter found for {port_cls} on {platform}")
            
    return adapter_cls()
