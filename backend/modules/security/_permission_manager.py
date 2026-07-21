from __future__ import annotations

from backend.modules.security._types import PermissionMode


class PermissionManager:
    def __init__(self) -> None:
        self._permissions: dict[str, PermissionMode] = {}

    def set_permission(
        self,
        tool_name: str,
        mode: PermissionMode,
    ) -> None:
        self._permissions[tool_name] = mode

    def get_permission(self, tool_name: str) -> PermissionMode:
        return self._permissions.get(tool_name, PermissionMode.ALLOW)

    def remove_permission(self, tool_name: str) -> None:
        self._permissions.pop(tool_name, None)

    def clear(self) -> None:
        self._permissions.clear()

    def list_permissions(self) -> dict[str, PermissionMode]:
        return dict(self._permissions)

    def check_permission(self, tool_name: str) -> bool:
        mode = self.get_permission(tool_name)
        if mode == PermissionMode.DENY:
            return False
        if mode == PermissionMode.CONFIRM:
            return True
        if mode == PermissionMode.ADMIN:
            return True
        return True

    def requires_confirmation(self, tool_name: str) -> bool:
        return self.get_permission(tool_name) == PermissionMode.CONFIRM

    def requires_admin(self, tool_name: str) -> bool:
        return self.get_permission(tool_name) == PermissionMode.ADMIN
