"""Tests for the new PC-control capabilities (system settings, software, accounts).

Covers:
- New dataclass types (WifiNetwork, BluetoothDevice, DisplaySettings,
  InstalledPackage, PackageOpResult, UserAccount)
- LocalPCControlAdapter raising PCControlNotImplementedError for all
  new operations
- ProductionPCControlAdapter per-OS dispatch (subprocess mocked), including
  permission gating and unsupported-platform errors
- PCControlManager operations and PCControlExecutor forwarding for the
  new capabilities
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.modules.pc_control import (
    BluetoothDevice,
    DisplaySettings,
    InstalledPackage,
    PackageOpResult,
    PCControlManager,
    UserAccount,
    WifiNetwork,
)
from backend.modules.pc_control._exceptions import (
    PCControlNotImplementedError,
    PCControlPermissionError,
    PCControlUnsupportedPlatformError,
)
from backend.modules.pc_control._local_adapter import LocalPCControlAdapter

# ── Helpers ─────────────────────────────────────────────────────────────


def _proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def _make_config(**overrides: object) -> MagicMock:
    """Create a mock PCControlConfig with the new ops allowed."""
    config = MagicMock()
    config.default_timeout = 30.0
    config.enabled = True
    config.allowed_commands = (
        "wifi_connect",
        "bluetooth_pair",
        "software_install",
        "software_uninstall",
        "account_create_user",
        "account_set_enabled",
        "account_modify_groups",
    )
    config.sandbox_enabled = True
    config.max_retries = 1
    config.retry_base_delay = 0.1
    config.retry_max_delay = 1.0
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


def _make_adapter(platform: str = "Linux", **overrides: object):
    from backend.modules.pc_control._production_adapter import ProductionPCControlAdapter

    adapter = ProductionPCControlAdapter(config=_make_config(**overrides))
    patchers = [
        patch(
            "backend.modules.pc_control._production_adapter.platform.system",
            return_value=platform,
        ),
        patch(
            "backend.modules.pc_control._production_adapter.subprocess.run",
            side_effect=AssertionError("subprocess.run not stubbed"),
        ),
    ]
    for p in patchers:
        p.start()
    return adapter, patchers


# =========================================================================
# Dataclass tests
# =========================================================================


class TestNewTypes:
    def test_wifi_network_minimal(self) -> None:
        n = WifiNetwork(ssid="home", signal_strength=80, secured=True)
        assert n.ssid == "home"
        assert n.signal_strength == 80
        assert n.secured is True

    def test_wifi_network_frozen(self) -> None:
        n = WifiNetwork(ssid="home")
        with pytest.raises(AttributeError):
            n.ssid = "other"  # type: ignore[misc]

    def test_bluetooth_device_minimal(self) -> None:
        b = BluetoothDevice(name="Headset", address="00:11:22")
        assert b.name == "Headset"
        assert b.paired is False

    def test_display_settings_minimal(self) -> None:
        d = DisplaySettings()
        assert d.brightness == 50
        assert d.width == 1920

    def test_installed_package_minimal(self) -> None:
        p = InstalledPackage(name="vim", version="9.0")
        assert p.name == "vim"
        assert p.version == "9.0"

    def test_package_op_result_success(self) -> None:
        r = PackageOpResult(success=True, package="vim")
        assert r.success is True
        assert r.message == ""

    def test_user_account_minimal(self) -> None:
        u = UserAccount(username="alice")
        assert u.username == "alice"
        assert u.enabled is True
        assert u.admin is False


# =========================================================================
# LocalPCControlAdapter
# =========================================================================


class TestLocalPCControlAdapterNewOps:
    @pytest.mark.parametrize(
        "method, args",
        [
            ("wifi_set_power", (True,)),
            ("wifi_get_power", ()),
            ("wifi_list_networks", ()),
            ("wifi_connect", ("home",)),
            ("bluetooth_set_power", (True,)),
            ("bluetooth_get_power", ()),
            ("bluetooth_list_devices", ()),
            ("bluetooth_pair", ("00:11:22",)),
            ("display_get_brightness", ()),
            ("display_set_brightness", (75,)),
            ("display_get_resolution", ()),
            ("display_set_resolution", (1920, 1080)),
            ("display_list_resolutions", ()),
            ("display_set_night_light", (True,)),
            ("display_get_night_light", ()),
            ("display_set_dark_mode", (True,)),
            ("display_get_dark_mode", ()),
            ("power_set_airplane_mode", (True,)),
            ("power_get_airplane_mode", ()),
            ("power_set_do_not_disturb", (True,)),
            ("power_get_do_not_disturb", ()),
            ("software_list_installed", ()),
            ("software_install", ("vim",)),
            ("software_uninstall", ("vim",)),
            ("software_check_update", ("vim",)),
            ("account_list_users", ()),
            ("account_get_current_user", ()),
            ("account_create_user", ("alice",)),
            ("account_set_enabled", ("alice", True)),
            ("account_modify_groups", ("alice", ["sudo"])),
        ],
    )
    @pytest.mark.asyncio
    async def test_all_new_operations_raise_not_implemented(self, method: str, args: tuple) -> None:
        adapter = LocalPCControlAdapter()
        m = getattr(adapter, method)
        with pytest.raises(PCControlNotImplementedError):
            await m(*args)


# =========================================================================
# ProductionPCControlAdapter — system settings
# =========================================================================


class TestProductionAdapterWifi:
    @pytest.mark.asyncio
    async def test_get_power_windows_enabled(self) -> None:
        adapter, patchers = _make_adapter(platform="Windows")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(
                    stdout="Name : Wi-Fi\nAdmin State : Enabled\nState : Connected\n"
                ),
            ):
                assert await adapter.wifi_get_power() is True
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_set_power_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(),
            ) as mock_run:
                await adapter.wifi_set_power(True)
                cmd = mock_run.call_args.args[0]
                assert cmd == ["nmcli", "radio", "wifi", "on"]
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_connect_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(),
            ) as mock_run:
                await adapter.wifi_connect("home", password="secret")
                cmd = mock_run.call_args.args[0]
                assert cmd == ["nmcli", "dev", "wifi", "connect", "home", "password", "secret"]
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_unsupported_platform(self) -> None:
        adapter, patchers = _make_adapter(platform="Solaris")
        try:
            with pytest.raises(PCControlUnsupportedPlatformError):
                await adapter.wifi_get_power()
        finally:
            for p in patchers:
                p.stop()


class TestProductionAdapterBluetooth:
    @pytest.mark.asyncio
    async def test_get_power_linux_enabled(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(stdout="Powered: yes\nDiscoverable: no\n"),
            ):
                assert await adapter.bluetooth_get_power() is True
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_list_devices_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(
                    stdout="Device 00:11:22:33:44:55 Headset\nDevice AA:BB:CC Keyboard\n"
                ),
            ):
                devices = await adapter.bluetooth_list_devices()
                assert len(devices) == 2
                assert devices[0].address == "00:11:22:33:44:55"
                assert devices[0].paired is True
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_pair_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(),
            ) as mock_run:
                await adapter.bluetooth_pair("00:11:22:33:44:55")
                cmd = mock_run.call_args.args[0]
                assert cmd == ["bluetoothctl", "pair", "00:11:22:33:44:55"]
        finally:
            for p in patchers:
                p.stop()


class TestProductionAdapterDisplay:
    @pytest.mark.asyncio
    async def test_get_brightness_darwin(self) -> None:
        adapter, patchers = _make_adapter(platform="Darwin")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(stdout="display 0: brightness 75\n"),
            ):
                assert await adapter.display_get_brightness() == 75
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_set_brightness_windows(self) -> None:
        adapter, patchers = _make_adapter(platform="Windows")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(),
            ) as mock_run:
                await adapter.display_set_brightness(80)
                cmd = mock_run.call_args.args[0]
                assert "WmiSetBrightness" in cmd[-1]
                assert "80" in cmd[-1]
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_get_dark_mode_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(stdout="prefer-dark\n"),
            ):
                assert await adapter.display_get_dark_mode() is True
        finally:
            for p in patchers:
                p.stop()


class TestProductionAdapterPowerSettings:
    @pytest.mark.asyncio
    async def test_get_do_not_disturb_windows(self) -> None:
        adapter, patchers = _make_adapter(platform="Windows")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(stdout="0x0\n"),
            ):
                assert await adapter.power_get_do_not_disturb() is True
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_set_airplane_mode_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(),
            ) as mock_run:
                await adapter.power_set_airplane_mode(True)
                cmd = mock_run.call_args.args[0]
                assert cmd == ["nmcli", "radio", "all", "on"]
        finally:
            for p in patchers:
                p.stop()


# =========================================================================
# ProductionPCControlAdapter — software management
# =========================================================================


class TestProductionAdapterSoftware:
    @pytest.mark.asyncio
    async def test_list_installed_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(stdout="vim\t9.0\npython3\t3.11\n"),
            ):
                packages = await adapter.software_list_installed()
                assert [p.name for p in packages] == ["vim", "python3"]
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_install_linux_success(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(),
            ):
                result = await adapter.software_install("vim")
                assert result.success is True
                assert result.package == "vim"
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_install_windows_failure(self) -> None:
        adapter, patchers = _make_adapter(platform="Windows")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(returncode=1, stderr="package not found"),
            ):
                result = await adapter.software_install("nonexistent")
                assert result.success is False
                assert "package not found" in result.message
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_check_update_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(stdout="vim/stable 9.1\n"),
            ):
                assert await adapter.software_check_update("vim") is True
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_install_blocked_without_permission(self) -> None:
        adapter, patchers = _make_adapter(
            platform="Linux", allowed_commands=(), sandbox_enabled=True
        )
        try:
            with pytest.raises(PCControlPermissionError):
                await adapter.software_install("vim")
        finally:
            for p in patchers:
                p.stop()


# =========================================================================
# ProductionPCControlAdapter — user accounts
# =========================================================================


class TestProductionAdapterAccounts:
    @pytest.mark.asyncio
    async def test_list_users_windows(self) -> None:
        adapter, patchers = _make_adapter(platform="Windows")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(stdout="Administrator\nGuest\nAlice\n"),
            ):
                users = await adapter.account_list_users()
                names = [u.username for u in users]
                assert "Administrator" in names
                assert "Alice" in names
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_get_current_user_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.os.getlogin",
                return_value="alice",
            ):
                user = await adapter.account_get_current_user()
                assert user.username == "alice"
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_create_user_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(),
            ) as mock_run:
                user = await adapter.account_create_user("alice")
                cmd = mock_run.call_args.args[0]
                assert cmd == ["useradd", "-m", "alice"]
                assert user.username == "alice"
                assert user.enabled is True
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_set_enabled_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                return_value=_proc(),
            ) as mock_run:
                await adapter.account_set_enabled("alice", False)
                cmd = mock_run.call_args.args[0]
                assert cmd == ["usermod", "-L", "alice"]
        finally:
            for p in patchers:
                p.stop()

    @pytest.mark.asyncio
    async def test_modify_groups_linux(self) -> None:
        adapter, patchers = _make_adapter(platform="Linux")
        try:
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs: object) -> SimpleNamespace:
                calls.append(cmd)
                return _proc()

            with patch(
                "backend.modules.pc_control._production_adapter.subprocess.run",
                side_effect=_fake_run,
            ):
                await adapter.account_modify_groups("alice", add=["sudo"], remove=["guest"])
                assert calls[0] == ["usermod", "-aG", "sudo", "alice"]
                assert calls[1] == ["gpasswd", "-d", "alice", "guest"]
        finally:
            for p in patchers:
                p.stop()


# =========================================================================
# PCControlManager operations
# =========================================================================


class _MockNewCapabilitiesAdapter:
    """Minimal adapter implementing the new capability methods."""

    @property
    def is_available(self) -> bool:
        return True

    async def wifi_get_power(self) -> bool:
        return True

    async def software_list_installed(self) -> list[InstalledPackage]:
        return [InstalledPackage(name="vim", version="9.0")]

    async def account_get_current_user(self) -> UserAccount:
        return UserAccount(username="alice")

    async def display_get_brightness(self) -> int:
        return 50


class TestPCControlManagerNewOperations:
    @pytest.mark.asyncio
    async def test_wifi_get_power(self) -> None:
        mgr = PCControlManager(adapter=_MockNewCapabilitiesAdapter())
        await mgr.async_init()
        result = await mgr.wifi_get_power()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_software_list_installed(self) -> None:
        mgr = PCControlManager(adapter=_MockNewCapabilitiesAdapter())
        await mgr.async_init()
        result = await mgr.software_list_installed()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_account_get_current_user(self) -> None:
        mgr = PCControlManager(adapter=_MockNewCapabilitiesAdapter())
        await mgr.async_init()
        result = await mgr.account_get_current_user()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_display_get_brightness(self) -> None:
        mgr = PCControlManager(adapter=_MockNewCapabilitiesAdapter())
        await mgr.async_init()
        result = await mgr.display_get_brightness()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_new_operations_no_adapter(self) -> None:
        mgr = PCControlManager()
        await mgr.async_init()
        result = await mgr.software_list_installed()
        assert result.status == "error"


# =========================================================================
# PCControlExecutor forwarding
# =========================================================================


class TestPCControlExecutorNewOperations:
    @pytest.mark.asyncio
    async def test_execute_wifi_get_power(self) -> None:
        from backend.modules.pc_control._executor import PCControlExecutor

        executor = PCControlExecutor(adapter=_MockNewCapabilitiesAdapter())
        result = await executor.wifi_get_power()
        assert result.status == "success"
        assert "True" in result.output

    @pytest.mark.asyncio
    async def test_execute_display_get_brightness(self) -> None:
        from backend.modules.pc_control._executor import PCControlExecutor

        executor = PCControlExecutor(adapter=_MockNewCapabilitiesAdapter())
        result = await executor.display_get_brightness()
        assert result.status == "success"
        assert "50" in result.output
