"""PC Control system-settings operations — placeholder component.

Provides high-level OS settings operations (Wi-Fi, Bluetooth, display,
airplane mode, do-not-disturb) delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import BluetoothDevice, WifiNetwork
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.system_settings")


class PCSystemSettings:
    """System-settings control operations.

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

    # ── Wi-Fi ───────────────────────────────────────────────────────────

    async def wifi_set_power(self, enabled: bool) -> None:
        await self._port.wifi_set_power(enabled)

    async def wifi_get_power(self) -> bool:
        return await self._port.wifi_get_power()

    async def wifi_list_networks(self) -> list[WifiNetwork]:
        return await self._port.wifi_list_networks()

    async def wifi_connect(self, ssid: str, password: str | None = None) -> None:
        await self._port.wifi_connect(ssid, password=password)

    # ── Bluetooth ───────────────────────────────────────────────────────

    async def bluetooth_set_power(self, enabled: bool) -> None:
        await self._port.bluetooth_set_power(enabled)

    async def bluetooth_get_power(self) -> bool:
        return await self._port.bluetooth_get_power()

    async def bluetooth_list_devices(self) -> list[BluetoothDevice]:
        return await self._port.bluetooth_list_devices()

    async def bluetooth_pair(self, device_address: str, pin: str | None = None) -> None:
        await self._port.bluetooth_pair(device_address, pin=pin)

    # ── Display ─────────────────────────────────────────────────────────

    async def display_get_brightness(self) -> int:
        return await self._port.display_get_brightness()

    async def display_set_brightness(self, level: int) -> None:
        await self._port.display_set_brightness(level)

    async def display_get_resolution(self) -> tuple[int, int]:
        return await self._port.display_get_resolution()

    async def display_set_resolution(self, width: int, height: int) -> None:
        await self._port.display_set_resolution(width, height)

    async def display_list_resolutions(self) -> list[tuple[int, int]]:
        return await self._port.display_list_resolutions()

    async def display_set_night_light(self, enabled: bool) -> None:
        await self._port.display_set_night_light(enabled)

    async def display_get_night_light(self) -> bool:
        return await self._port.display_get_night_light()

    async def display_set_dark_mode(self, enabled: bool) -> None:
        await self._port.display_set_dark_mode(enabled)

    async def display_get_dark_mode(self) -> bool:
        return await self._port.display_get_dark_mode()

    # ── Airplane mode / Do Not Disturb ──────────────────────────────────

    async def power_set_airplane_mode(self, enabled: bool) -> None:
        await self._port.power_set_airplane_mode(enabled)

    async def power_get_airplane_mode(self) -> bool:
        return await self._port.power_get_airplane_mode()

    async def power_set_do_not_disturb(self, enabled: bool) -> None:
        await self._port.power_set_do_not_disturb(enabled)

    async def power_get_do_not_disturb(self) -> bool:
        return await self._port.power_get_do_not_disturb()
