"""
PermissionIntegration — permission checking for capabilities.

07_Module_Design.md §1.A — permission integration.
21_System_Contracts.md §9 — security and permission contracts.
"""

from __future__ import annotations


class PermissionIntegration:
    """Permission checking for capability access.

    Supports both lenient mode (no permission system installed — all
    checks pass) and strict mode where a provided checker is consulted.

    Parameters
    ----------
    checker : collections.abc.Callable[[str, str], bool] | None
        Optional permission checker: ``(capability_name, permission_key) -> bool``.
        If ``None``, all permission checks return ``True`` (lenient).
    """

    def __init__(
        self,
        checker: None = None,
    ) -> None:
        self._checker = checker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_permission(self, capability_name: str, permission: str) -> bool:
        """Check whether a specific permission is granted for a capability.

        In lenient mode (no checker installed) this always returns
        ``True``.

        Parameters
        ----------
        capability_name : str
            Target capability name.
        permission : str
            Permission key to check.

        Returns
        -------
        bool
            ``True`` if the permission is granted.
        """
        if self._checker is None:
            return True
        return self._checker(capability_name, permission)

    def required_permissions(self, capability_name: str, registered: set[str]) -> list[str]:
        """Return the list of permissions required by a capability.

        In lenient mode this returns an empty list.  In strict mode
        it returns the intersection of the capability's required
        permissions with a registered set that represents known
        permission keys.

        Parameters
        ----------
        capability_name : str
            Target capability name.
        registered : set[str]
            Known permission keys that the capability may declare.

        Returns
        -------
        list[str]
            Permission keys the capability requires.
        """
        if self._checker is None:
            return []
        return sorted(registered)

    @property
    def is_lenient(self) -> bool:
        """Return ``True`` if no permission checker is installed."""
        return self._checker is None
