"""PC Control software-management operations — placeholder component.

Provides software inventory and package management operations
(install/uninstall/update check) delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import InstalledPackage, PackageOpResult
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.software_manager")


class PCSoftwareManager:
    """Software-management control operations.

    Parameters
    ----------
    port : PCControlPort
        The active PC-control adapter.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        port: PCControlPort,
        logger: logging.Logger | None = None,
    ) -> None:
        self._port = port
        self._logger = logger or _LOG

    async def list_installed(self) -> list[InstalledPackage]:
        """List installed software packages."""
        return await self._port.software_list_installed()

    async def install(self, package: str) -> PackageOpResult:
        """Install a software package."""
        return await self._port.software_install(package)

    async def uninstall(self, package: str) -> PackageOpResult:
        """Uninstall a software package."""
        return await self._port.software_uninstall(package)

    async def check_update(self, package: str) -> bool:
        """Check whether an update is available for a package."""
        return await self._port.software_check_update(package)
