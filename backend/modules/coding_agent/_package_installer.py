from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

from backend.modules.coding_agent._exceptions import PackageInstallError

_LOG = logging.getLogger("naira.coding_agent.package_installer")


@dataclass
class PackageInfo:
    name: str
    version: str | None = None
    manager: str = "pip"
    already_installed: bool = False


@dataclass
class InstallResult:
    success: bool
    installed: list[PackageInfo] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    already_installed: list[PackageInfo] = field(default_factory=list)
    output: str = ""


_INSTALL_COMMANDS: dict[str, tuple[str, list[str]]] = {
    "pip": ("python", ["-m", "pip", "install"]),
    "pip3": ("python", ["-m", "pip3", "install"]),
    "npm": ("npm", ["install"]),
    "yarn": ("yarn", ["add"]),
    "go": ("go", ["get"]),
    "cargo": ("cargo", ["add"]),
}


class PackageAutoInstaller:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
        auto_confirm: bool = False,
        allowed_managers: tuple[str, ...] | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._auto_confirm = auto_confirm
        self._allowed_managers = allowed_managers or ("pip", "pip3", "npm")
        self._install_history: list[PackageInfo] = []
        self._total_installed = 0
        self._failed_installs = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("PackageAutoInstaller marked degraded")

    async def install_package(
        self,
        package_name: str,
        manager: str = "pip",
        version: str | None = None,
        timeout: float = 60.0,
    ) -> InstallResult:
        if not self._enabled or self._degraded:
            return InstallResult(success=True, already_installed=[
                PackageInfo(name=package_name, manager=manager),
            ])

        if manager not in self._allowed_managers:
            raise PackageInstallError(
                f"Package manager '{manager}' is not allowed",
                context={"package": package_name, "manager": manager},
            )

        cmd_info = _INSTALL_COMMANDS.get(manager)
        if cmd_info is None:
            raise PackageInstallError(
                f"Unsupported package manager: {manager}",
                context={"package": package_name, "manager": manager},
            )

        check_result = await self._check_installed(package_name)
        if check_result:
            info = PackageInfo(
                name=package_name,
                version=check_result,
                manager=manager,
                already_installed=True,
            )
            self._install_history.append(info)
            return InstallResult(success=True, already_installed=[info])

        executable, args_base = cmd_info
        full_spec = f"{package_name}=={version}" if version else package_name
        args = args_base + [full_spec]

        self._logger.info("Installing package: %s with %s", full_spec, manager)

        try:
            proc = await asyncio.create_subprocess_exec(
                executable, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            output = (stdout or b"").decode("utf-8", errors="replace")
            error_output = (stderr or b"").decode("utf-8", errors="replace")

            if proc.returncode == 0:
                info = PackageInfo(
                    name=package_name,
                    version=version,
                    manager=manager,
                )
                self._install_history.append(info)
                self._total_installed += 1
                return InstallResult(
                    success=True,
                    installed=[info],
                    output=output,
                )
            else:
                self._failed_installs += 1
                err_msg = error_output or output
                self._logger.warning(
                    "Failed to install %s: %s", package_name, err_msg[:200],
                )
                return InstallResult(
                    success=False,
                    failed=[(package_name, err_msg[:500])],
                    output=err_msg[:500],
                )

        except asyncio.TimeoutError:
            self._failed_installs += 1
            raise PackageInstallError(
                f"Package installation timed out: {package_name}",
                context={
                    "package": package_name,
                    "manager": manager,
                    "timeout": timeout,
                },
            ) from None
        except FileNotFoundError:
            self._failed_installs += 1
            raise PackageInstallError(
                f"Package manager executable not found: {executable}",
                context={"package": package_name, "manager": manager},
            ) from None

    async def _check_installed(self, package_name: str) -> str | None:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", package_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("Version:"):
                        return line.split(":", 1)[1].strip()
        except (subprocess.SubprocessError, OSError):
            pass
        return None

    async def detect_requirements(self, project_path: str) -> list[str]:
        packages: list[str] = []
        req_files = [
            os.path.join(project_path, "requirements.txt"),
            os.path.join(project_path, "Pipfile"),
            os.path.join(project_path, "pyproject.toml"),
            os.path.join(project_path, "package.json"),
            os.path.join(project_path, "go.mod"),
            os.path.join(project_path, "Cargo.toml"),
        ]

        for req_file in req_files:
            if not os.path.isfile(req_file):
                continue
            try:
                if req_file.endswith("requirements.txt"):
                    with open(req_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith(("#", "-", "git+")):
                                packages.append(line)
                elif req_file.endswith("package.json"):
                    import json
                    with open(req_file, "r") as f:
                        data = json.load(f)
                    deps = data.get("dependencies", {})
                    packages.extend(deps.keys())
            except (OSError, json.JSONDecodeError) as exc:
                self._logger.warning("Error reading %s: %s", req_file, exc)

        return packages

    def get_install_history(self) -> list[PackageInfo]:
        return list(self._install_history)

    def metrics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "degraded": self._degraded,
            "total_installed": self._total_installed,
            "failed_installs": self._failed_installs,
            "allowed_managers": list(self._allowed_managers),
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
