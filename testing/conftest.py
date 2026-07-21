"""
Reusable test fixtures and async test helpers.

21_System_Contracts.md §23.8 — Common fixtures live in ``testing/conftest.py``.
21_System_Contracts.md §23.7 — Async tests use ``pytest.mark.asyncio`` with
per-test event loops.

Module-level helpers
--------------------
- ``AsyncContext`` — context manager that wraps async generators as sync fixtures
- ``await_until`` — poll an async predicate until it returns True or times out
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from pathlib import Path
from typing import Any, TypeVar
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from backend.modules.settings._config import AppConfig
from backend.modules.settings._env import EnvironmentSnapshot
from backend.modules.utils.di import DIContainer
from backend.orchestrator import EventBus, FSMState, Orchestrator

_T = TypeVar("_T")

# ---------------------------------------------------------------------------
# AppConfig fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_config() -> AppConfig:
    """Provide a default ``AppConfig`` with all built-in defaults.

    Uses the dataclass ``field`` defaults directly — no config files,
    no disk I/O.
    """
    return AppConfig()


@pytest.fixture
def app_config_factory() -> Callable[[dict[str, Any]], AppConfig]:
    """Factory fixture: build an ``AppConfig`` with selective overrides.

    Usage
    -----
    >>> def test_something(app_config_factory):
    ...     config = app_config_factory({"log": {"level": "DEBUG"}})
    ...     assert config.log.level == "DEBUG"
    """
    from backend.modules.settings._config import build_app_config

    def _build(overrides: dict[str, Any]) -> AppConfig:
        return build_app_config(overrides)

    return _build


# ---------------------------------------------------------------------------
# EnvironmentSnapshot fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env_snapshot_direct() -> EnvironmentSnapshot:
    """Construct an ``EnvironmentSnapshot`` directly (no ``.env`` file).

    Preferred fixture for tests that need a valid environment snapshot
    without depending on disk state.
    """
    return EnvironmentSnapshot(naira_api_key="test-api-key")


@pytest.fixture
def env_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> EnvironmentSnapshot:
    """Load an ``EnvironmentSnapshot`` via ``.load()`` with a fake ``.env``.

    Writes a minimal ``.env`` to a temp directory so the snapshot is
    loaded through the production code path.  The ``NAIRA_API_KEY``
    env var is also set as a fallback.

    Use this fixture when you specifically want to exercise the full
    ``EnvironmentSnapshot.load()`` pipeline.
    """
    monkeypatch.setenv("NAIRA_API_KEY", "test-api-key")
    dotenv = tmp_path / ".env"
    dotenv.write_text('NAIRA_API_KEY="test-api-key"\n', encoding="utf-8")
    return EnvironmentSnapshot.load(env_file=dotenv)


# ---------------------------------------------------------------------------
# DIContainer fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def di_container() -> DIContainer:
    """Provide a fresh ``DIContainer`` with no registered services."""
    return DIContainer()


# ---------------------------------------------------------------------------
# EventBus fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def event_bus() -> AsyncGenerator[EventBus, None]:
    """Provide an ``EventBus`` instance with lifecycle teardown.

    Yields the bus and calls ``shutdown()`` after the test completes.
    """
    bus = EventBus()
    yield bus
    await bus.shutdown()


# ---------------------------------------------------------------------------
# Orchestrator fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def orchestrator(
    event_bus: EventBus,
    app_config: AppConfig,
    env_snapshot_direct: EnvironmentSnapshot,
) -> AsyncGenerator[Orchestrator, None]:
    """Provide a fully wired ``Orchestrator`` in the ``BOOTING`` state.

    Dependencies
    ------------
    - ``EventBus`` (fresh per test)
    - ``AppConfig`` (defaults)
    - ``EnvironmentSnapshot`` (direct construction)

    The orchestrator is yielded in ``BOOTING`` state and shut down
    during teardown.
    """
    orch = Orchestrator(event_bus=event_bus, config=app_config, env=env_snapshot_direct)
    orch.state = FSMState.BOOTING
    yield orch
    orch.state = FSMState.SHUTDOWN
    await orch.shutdown()


# ---------------------------------------------------------------------------
# Logger fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_logger() -> MagicMock:
    """Provide a ``MagicMock`` logger that records all log calls.

    Replaces the real logger to prevent log output during tests and
    to allow assertions on log messages.

    Usage
    -----
    >>> def test_something(mock_logger):
    ...     module = SomeModule(logger=mock_logger)
    ...     module.do_something()
    ...     mock_logger.info.assert_called_once_with("Did something")
    """
    return MagicMock(spec=logging.Logger)


# ---------------------------------------------------------------------------
# Async test helpers
# ---------------------------------------------------------------------------


class AsyncContext:
    """Wrap an async generator fixture so it can be used as a sync context manager.

    Useful when a test needs an async fixture but the test function itself
    is synchronous and you want to manage the lifecycle manually.

    Example
    -------
    >>> async def gen():
    ...     yield "value"
    ...     await cleanup()
    ...
    >>> async with AsyncContext(gen()) as value:
    ...     print(value)
    """

    def __init__(self, async_gen: AsyncGenerator[_T, None]) -> None:
        self._gen = async_gen

    async def __aenter__(self) -> _T:
        return await self._gen.__anext__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        with contextlib.suppress(StopAsyncIteration):
            await self._gen.__anext__()


async def await_until(
    predicate: Callable[[], bool | Coroutine[Any, Any, bool]],
    timeout: float = 5.0,
    interval: float = 0.05,
) -> bool:
    """Poll *predicate* every *interval* seconds until it returns ``True``.

    Parameters
    ----------
    predicate : Callable[[], bool | Coroutine[Any, Any, bool]]
        A synchronous or async callable that returns a bool.
    timeout : float
        Maximum wall-clock time to wait (seconds).
    interval : float
        Polling interval (seconds).

    Returns
    -------
    bool
        ``True`` if the predicate became truthy within the timeout,
        ``False`` otherwise.

    Example
    -------
    >>> async def test(orchestrator):
    ...     await orchestrator.some_async_op()
    ...     assert await await_until(lambda: orchestrator.state == FSMState.IDLE)
    """
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        result = predicate()
        if isinstance(result, Coroutine):
            result = await result
        if result:
            return True
        await asyncio.sleep(interval)
    return False
