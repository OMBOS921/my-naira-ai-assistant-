from abc import ABC, abstractmethod
from typing import List, Any
from backend.modules.pc_control._types import ProcessInfo, SystemMetrics

class ProcessPort(ABC):
    @abstractmethod
    async def process_list(self) -> List[ProcessInfo]:
        pass

    @abstractmethod
    async def process_kill(self, pid: int, force: bool = False) -> None:
        pass

    @abstractmethod
    async def get_system_metrics(self) -> Any:
        pass

    @abstractmethod
    async def get_open_ports(self) -> List[int]:
        pass
