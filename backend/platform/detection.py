import platform
from enum import Enum, auto

class Platform(Enum):
    WINDOWS = auto()
    MACOS = auto()
    LINUX_UBUNTU = auto()
    LINUX_FEDORA = auto()
    LINUX_ARCH = auto()
    LINUX_KALI = auto()
    UNKNOWN = auto()

def detect_platform() -> Platform:
    sys_name = platform.system()
    if sys_name == 'Windows':
        return Platform.WINDOWS
    elif sys_name == 'Darwin':
        return Platform.MACOS
    elif sys_name == 'Linux':
        try:
            with open('/etc/os-release') as f:
                content = f.read().lower()
                if 'kali' in content:
                    return Platform.LINUX_KALI
                elif 'ubuntu' in content:
                    return Platform.LINUX_UBUNTU
                elif 'fedora' in content:
                    return Platform.LINUX_FEDORA
                elif 'arch' in content:
                    return Platform.LINUX_ARCH
        except FileNotFoundError:
            pass
        return Platform.LINUX_UBUNTU  # Fallback for generic linux
    return Platform.UNKNOWN
