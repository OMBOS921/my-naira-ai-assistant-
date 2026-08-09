import asyncio
from typing import List, Any
import psutil

from backend.platform.ports.process_port import ProcessPort
from backend.modules.pc_control._types import ProcessInfo, SystemMetrics

class WindowsProcessAdapter(ProcessPort):
    async def process_list(self) -> List[ProcessInfo]:
        def _list_procs() -> List[ProcessInfo]:
            attrs = ["pid", "name", "status", "cpu_percent", "memory_info"]
            processes = []
            for proc in psutil.process_iter(attrs):
                try:
                    pinfo = proc.info
                    mem = pinfo.get("memory_info")
                    processes.append(
                        ProcessInfo(
                            pid=int(pinfo["pid"]),
                            name=str(pinfo.get("name", "") or ""),
                            status=str(pinfo.get("status", "running") or "running"),
                            cpu_percent=float(pinfo.get("cpu_percent", 0.0) or 0.0),
                            memory_bytes=int(mem.rss if mem else 0),
                        )
                    )
                except (OSError, PermissionError):
                    continue
            return processes
        return await asyncio.to_thread(_list_procs)

    async def process_kill(self, pid: int, force: bool = False) -> None:
        def _kill() -> None:
            try:
                proc = psutil.Process(pid)
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                proc.wait(timeout=5)
            except psutil.NoSuchProcess:
                raise RuntimeError(f"Process {pid} does not exist")
            except psutil.AccessDenied as exc:
                raise PermissionError(f"Cannot kill process {pid}: access denied") from exc
            except psutil.TimeoutExpired:
                raise TimeoutError(f"Process {pid} did not terminate within timeout")
        await asyncio.to_thread(_kill)

    async def get_system_metrics(self) -> Any:
        def _metrics() -> Any:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            # Create a basic dictionary or dummy SystemMetrics if _types.SystemMetrics requires kwargs
            # Return dict for now to satisfy Any if SystemMetrics is not strictly validated
            return {
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "memory_used_bytes": mem.used,
                "memory_total_bytes": mem.total,
                "disk_percent": disk.percent,
                "disk_used_bytes": disk.used,
                "disk_total_bytes": disk.total,
            }
        return await asyncio.to_thread(_metrics)

    async def get_open_ports(self) -> List[int]:
        def _ports() -> List[int]:
            open_ports = set()
            try:
                for conn in psutil.net_connections(kind='inet'):
                    if conn.status == 'LISTEN' and conn.laddr:
                        open_ports.add(conn.laddr.port)
            except psutil.AccessDenied:
                pass
            return sorted(list(open_ports))
        return await asyncio.to_thread(_ports)
