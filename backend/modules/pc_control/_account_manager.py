"""PC Control user-account operations — placeholder component.

Provides user-account management operations (list/current/create/enable/
group membership) delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import UserAccount
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.account_manager")


class PCAccountManager:
    """User-account control operations.

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

    async def list_users(self) -> list[UserAccount]:
        """List all local user accounts."""
        return await self._port.account_list_users()

    async def get_current_user(self) -> UserAccount:
        """Return the currently logged-in user account."""
        return await self._port.account_get_current_user()

    async def create_user(self, username: str, password: str | None = None) -> UserAccount:
        """Create a new local user account."""
        return await self._port.account_create_user(username, password=password)

    async def set_enabled(self, username: str, enabled: bool) -> None:
        """Enable or disable a user account."""
        await self._port.account_set_enabled(username, enabled)

    async def modify_groups(
        self,
        username: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> None:
        """Add/remove group memberships for a user account."""
        await self._port.account_modify_groups(username, add=add, remove=remove)
