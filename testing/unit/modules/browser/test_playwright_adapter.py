# ruff: noqa: PLR2004

"""Comprehensive tests for PlaywrightBrowserAdapter.

Covers:
- No-Playwright mode (not installed) — all BrowserPort methods raise
- Constructor defaults and customisation
- _to_ms / _clean_search_url helpers
- Launch lifecycle (success, failure, double-launch, launch-after-close)
- Close lifecycle (idempotent, with partial init, with errors)
- All BrowserPort methods: navigate, search, extract, screenshot, close
- All public helper methods: back, forward, reload, get_current_url,
  get_title, execute_js, click, fill, press_key, scroll, upload_file,
  get_html, get_visible_text
- Tab management: new_tab, close_tab, list_tabs, switch_tab
- Cookie / storage: get/set/clear cookies, local/session storage
- wait_for_navigation (with and without url)
- Error mapping: all Playwright ``Error`` / ``TimeoutError`` correctly
  converted to domain exceptions (BrowserNavigationError,
  BrowserTimeoutError, BrowserSearchError, BrowserSessionError,
  BrowserContentError, BrowserError)
- _snapshot helper
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.modules.browser._exceptions import (
    BrowserContentError,
    BrowserError,
    BrowserNavigationError,
    BrowserNotImplementedError,
    BrowserSearchError,
    BrowserSessionError,
    BrowserTimeoutError,
)
from backend.modules.browser._playwright_adapter import (
    PlaywrightBrowserAdapter,
    _clean_search_url,
    _to_ms,
)
from backend.modules.browser._types import BrowserPage, BrowserSearchResponse

_Launched = tuple[PlaywrightBrowserAdapter, MagicMock]

# =========================================================================
# Test doubles — stand-ins for Playwright types
# =========================================================================

MODULE = "backend.modules.browser._playwright_adapter"


class MockError(Exception):
    """Stand-in for ``playwright.async_api.Error``."""


class MockTimeoutError(MockError):
    """Stand-in for ``playwright.async_api.TimeoutError``."""


class MockResponse:
    """Stand-in for ``playwright.async_api.Response``."""

    def __init__(self, status: int = 200, headers: dict | None = None) -> None:
        self.status = status
        self.headers = headers or {}


# =========================================================================
# Fixtures
# =========================================================================


def _patch_pw(**overrides: object) -> object:
    """Return a context manager that patches Playwright module globals."""
    defaults: dict[str, object] = {
        "_HAS_PLAYWRIGHT": True,
        "_PW_ERROR": MockError,
        "_PW_TIMEOUT_ERROR": MockTimeoutError,
        "_PW_RESPONSE": MockResponse,
        "_PW_ASYNC_PLAYWRIGHT": MagicMock(),
    }
    defaults.update(overrides)
    return patch.multiple(MODULE, **defaults)


@pytest.fixture
def adapter() -> PlaywrightBrowserAdapter:
    """A ``PlaywrightBrowserAdapter`` with Playwright module globals mocked."""
    pw_callable, *_ = _make_launch_chain()
    with _patch_pw(_PW_ASYNC_PLAYWRIGHT=pw_callable):
        yield PlaywrightBrowserAdapter()


@pytest.fixture
def no_pw_adapter() -> PlaywrightBrowserAdapter:
    """An adapter where Playwright is NOT installed."""
    with _patch_pw(
        _HAS_PLAYWRIGHT=False,
        _PW_ERROR=None,
        _PW_TIMEOUT_ERROR=None,
        _PW_RESPONSE=None,
        _PW_ASYNC_PLAYWRIGHT=None,
    ):
        yield PlaywrightBrowserAdapter()


def _make_launch_chain(page: MagicMock | None = None) -> object:
    """Build the nested mock chain for ``_do_launch()``.

    Returns (pw_callable, page_mock, context_mock, browser_mock, pw_instance).
    """
    page_mock = page or MagicMock()
    page_mock.url = "about:blank"
    page_mock.title = AsyncMock(return_value="")
    page_mock.content = AsyncMock(return_value="<html></html>")
    page_mock.goto = AsyncMock(return_value=MockResponse(200))
    page_mock.go_back = AsyncMock(return_value=None)
    page_mock.go_forward = AsyncMock(return_value=None)
    page_mock.reload = AsyncMock(return_value=None)
    page_mock.click = AsyncMock(return_value=None)
    page_mock.fill = AsyncMock(return_value=None)
    page_mock.press = AsyncMock(return_value=None)
    page_mock.set_input_files = AsyncMock(return_value=None)
    page_mock.inner_text = AsyncMock(return_value="Hello World")
    page_mock.evaluate = AsyncMock(return_value='{"key": "value"}')
    page_mock.query_selector_all = AsyncMock(return_value=[])
    page_mock.screenshot = AsyncMock(return_value=b"PNG-DATA")
    page_mock.wait_for_url = AsyncMock(return_value=None)
    page_mock.wait_for_load_state = AsyncMock(return_value=None)
    page_mock.close = AsyncMock(return_value=None)

    context_mock = MagicMock()
    context_mock.new_page = AsyncMock(return_value=page_mock)
    context_mock.cookies = AsyncMock(return_value=[])
    context_mock.add_cookies = AsyncMock(return_value=None)
    context_mock.clear_cookies = AsyncMock(return_value=None)
    context_mock.close = AsyncMock(return_value=None)

    browser_mock = MagicMock()
    browser_mock.new_context = AsyncMock(return_value=context_mock)
    browser_mock.close = AsyncMock(return_value=None)

    pw_instance = MagicMock()
    pw_instance.chromium.launch = AsyncMock(return_value=browser_mock)
    pw_instance.stop = AsyncMock(return_value=None)

    pw_start = AsyncMock(return_value=pw_instance)
    pw_callable_return = MagicMock(start=pw_start)
    pw_callable = MagicMock(return_value=pw_callable_return)

    return pw_callable, page_mock, context_mock, browser_mock, pw_instance


@pytest.fixture
async def launched_adapter(adapter: PlaywrightBrowserAdapter) -> _Launched:
    """Return (adapter, page_mock) after a successful mocked launch."""
    pw_callable, page_mock, *_ = _make_launch_chain()
    with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
        await adapter.launch()
    return adapter, page_mock


# =========================================================================
# Helper functions
# =========================================================================


class TestToMs:
    def test_none_uses_default(self) -> None:
        assert _to_ms(None, 30000) == 30000

    def test_zero_uses_default(self) -> None:
        assert _to_ms(0, 30000) == 30000

    def test_negative_uses_default(self) -> None:
        assert _to_ms(-1, 30000) == 30000

    def test_positive_converts(self) -> None:
        assert _to_ms(5.0, 30000) == 5000

    def test_float_rounds_down(self) -> None:
        assert _to_ms(1.234, 30000) == 1234


class TestCleanSearchUrl:
    def test_no_redirect(self) -> None:
        url = "https://example.com/page"
        assert _clean_search_url(url) == url

    def test_extracts_uddg(self) -> None:
        url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage&rut=abc"
        assert _clean_search_url(url) == "https://example.com/page"

    def test_uddg_without_param(self) -> None:
        url = "https://duckduckgo.com/l/?rut=abc"
        assert _clean_search_url(url) == url


# =========================================================================
# Constructor
# =========================================================================


class TestConstructor:
    def test_defaults(self) -> None:
        with _patch_pw():
            a = PlaywrightBrowserAdapter()
        assert a._headless is True
        assert a._slow_mo == 0
        assert a._launch_args == []
        assert a._default_timeout_ms == 30000
        assert a._closed is False
        assert a._initialized is False
        assert a._active_page_id is None
        assert a._pages == {}

    def test_custom_values(self) -> None:
        logger = MagicMock()
        with _patch_pw():
            a = PlaywrightBrowserAdapter(
                logger=logger,
                headless=False,
                slow_mo=100,
                launch_args=["--no-sandbox"],
                default_timeout=15.0,
            )
        assert a._logger is logger
        assert a._headless is False
        assert a._slow_mo == 100
        assert a._launch_args == ["--no-sandbox"]
        assert a._default_timeout_ms == 15000


# =========================================================================
# No-Playwright mode
# =========================================================================


class TestNoPlaywright:
    def test_is_available_false(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        assert no_pw_adapter.is_available is False

    @pytest.mark.asyncio
    async def test_pw_types_raises(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        with pytest.raises(BrowserNotImplementedError):
            no_pw_adapter._pw_types()

    @pytest.mark.asyncio
    async def test_check_playwright_raises(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        with pytest.raises(BrowserNotImplementedError):
            no_pw_adapter._check_playwright_available()

    @pytest.mark.asyncio
    async def test_navigate_raises(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        with pytest.raises(BrowserNotImplementedError):
            await no_pw_adapter.navigate("https://example.com")

    @pytest.mark.asyncio
    async def test_search_raises(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        with pytest.raises(BrowserNotImplementedError):
            await no_pw_adapter.search("test")

    @pytest.mark.asyncio
    async def test_extract_raises(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        with pytest.raises(BrowserNotImplementedError):
            await no_pw_adapter.extract("https://example.com")

    @pytest.mark.asyncio
    async def test_screenshot_raises(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        with pytest.raises(BrowserNotImplementedError):
            await no_pw_adapter.screenshot("https://example.com")

    @pytest.mark.asyncio
    async def test_close_is_noop(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        await no_pw_adapter.close()
        assert no_pw_adapter._closed is True

    @pytest.mark.asyncio
    async def test_launch_raises(self, no_pw_adapter: PlaywrightBrowserAdapter) -> None:
        with pytest.raises(BrowserNotImplementedError):
            await no_pw_adapter.launch()


# =========================================================================
# Launch lifecycle
# =========================================================================


class TestLaunch:
    @pytest.mark.asyncio
    async def test_launch_success(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, context_mock, browser_mock, pw_instance = _make_launch_chain()
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        assert adapter._initialized is True
        assert adapter._browser is browser_mock
        assert adapter._context is context_mock
        assert adapter._playwright is pw_instance
        assert adapter._active_page_id is not None
        assert adapter._active_page_id in adapter._pages
        assert adapter._pages[adapter._active_page_id] is page_mock
        assert adapter.is_available is True

    @pytest.mark.asyncio
    async def test_double_launch_is_idempotent(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, *_ = _make_launch_chain()
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()
            await adapter.launch()

        assert adapter._initialized is True
        assert adapter._playwright.chromium.launch.call_count == 1

    @pytest.mark.asyncio
    async def test_launch_failure_cleans_up(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, *_ = _make_launch_chain()
        pw_callable.return_value.start = AsyncMock(side_effect=MockError("launch failed"))
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable), pytest.raises(MockError):
            await adapter.launch()

        assert adapter._initialized is False
        assert adapter._browser is None
        assert adapter._context is None
        assert adapter._pages == {}

    @pytest.mark.asyncio
    async def test_launch_after_close_raises(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, *_ = _make_launch_chain()
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()
            await adapter.close()

        with pytest.raises(BrowserError, match="closed"):
            await adapter.launch()

    @pytest.mark.asyncio
    async def test_ensure_initialized_delegates_to_launch(
        self, adapter: PlaywrightBrowserAdapter
    ) -> None:
        pw_callable, *_ = _make_launch_chain()
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.ensure_initialized()

        assert adapter._initialized is True

    @pytest.mark.asyncio
    async def test_ensure_initialized_noop_when_done(
        self, adapter: PlaywrightBrowserAdapter
    ) -> None:
        pw_callable, *_ = _make_launch_chain()
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()
            await adapter.ensure_initialized()

        assert adapter._playwright.chromium.launch.call_count == 1


# =========================================================================
# Close lifecycle
# =========================================================================


class TestClose:
    @pytest.mark.asyncio
    async def test_close_releases_resources(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.close()

        assert adapter._closed is True
        assert adapter._initialized is False
        assert adapter._pages == {}
        assert adapter._active_page_id is None
        page_mock.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_double_close_is_safe(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        await adapter.close()
        await adapter.close()
        assert adapter._closed is True

    @pytest.mark.asyncio
    async def test_close_with_multiple_tabs(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, context_mock, browser_mock, pw_instance = _make_launch_chain()
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        page2 = MagicMock()
        page2.close = AsyncMock()
        context_mock.new_page = AsyncMock(return_value=page2)
        await adapter.new_tab()

        await adapter.close()
        page_mock.close.assert_awaited_once()
        page2.close.assert_awaited_once()
        context_mock.close.assert_awaited_once()
        browser_mock.close.assert_awaited_once()
        pw_instance.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_logs_errors(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, context_mock, _browser_mock, _pw_instance = _make_launch_chain()
        page_mock.close = AsyncMock(side_effect=RuntimeError("page boom"))
        context_mock.close = AsyncMock(side_effect=RuntimeError("ctx boom"))
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        logger = MagicMock()
        adapter._logger = logger
        await adapter.close()
        assert adapter._closed is True
        assert logger.warning.called

    @pytest.mark.asyncio
    async def test_close_no_browser(self, adapter: PlaywrightBrowserAdapter) -> None:
        await adapter.close()
        assert adapter._closed is True


# =========================================================================
# is_available
# =========================================================================


class TestIsAvailable:
    def test_before_launch(self, adapter: PlaywrightBrowserAdapter) -> None:
        assert adapter.is_available is False

    @pytest.mark.asyncio
    async def test_after_launch(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        assert adapter.is_available is True

    @pytest.mark.asyncio
    async def test_after_close(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        await adapter.close()
        assert adapter.is_available is False


# =========================================================================
# BrowserPort: navigate
# =========================================================================


class TestNavigate:
    @pytest.mark.asyncio
    async def test_navigate_returns_browser_page(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.navigate("https://example.com")
        assert isinstance(result, BrowserPage)
        assert result.url == "about:blank"
        assert result.status_code == 200
        assert result.html == "<html></html>"
        page_mock.goto.assert_awaited_once_with(
            "https://example.com", timeout=30000, wait_until="load",
        )

    @pytest.mark.asyncio
    async def test_navigate_no_content(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.navigate("https://example.com", extract_content=False)
        assert result.html is None
        assert result.content is None

    @pytest.mark.asyncio
    async def test_navigate_custom_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.navigate("https://example.com", timeout=10.0)
        page_mock.goto.assert_awaited_once_with(
            "https://example.com", timeout=10000, wait_until="load",
        )

    @pytest.mark.asyncio
    async def test_navigate_null_response(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, *_ = _make_launch_chain()
        page_mock.goto = AsyncMock(return_value=None)
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()
        result = await adapter.navigate("https://example.com")
        assert result.status_code == 0
        assert result.headers == {}

    @pytest.mark.asyncio
    async def test_navigate_timeout_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.goto = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.navigate("https://example.com", timeout=1.0)

    @pytest.mark.asyncio
    async def test_navigate_generic_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.goto = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserNavigationError):
            await adapter.navigate("https://example.com")


# =========================================================================
# BrowserPort: search
# =========================================================================


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_response(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.search("test query")
        assert isinstance(result, BrowserSearchResponse)
        assert result.query == "test query"

    @pytest.mark.asyncio
    async def test_search_parses_results(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, *_ = _make_launch_chain()

        link1 = MagicMock()
        link1.get_attribute = AsyncMock(return_value="https://a.com")
        link1.inner_text = AsyncMock(return_value="Result A")
        link2 = MagicMock()
        link2.get_attribute = AsyncMock(return_value="https://b.com")
        link2.inner_text = AsyncMock(return_value="Result B")
        snippet1 = MagicMock()
        snippet1.inner_text = AsyncMock(return_value="Snippet A")
        snippet2 = MagicMock()
        snippet2.inner_text = AsyncMock(return_value="Snippet B")

        page_mock.query_selector_all = AsyncMock(side_effect=[
            [link1, link2],
            [snippet1, snippet2],
        ])

        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        result = await adapter.search("test", max_results=5)
        assert len(result.results) == 2
        assert result.results[0].title == "Result A"
        assert result.results[0].url == "https://a.com"
        assert result.results[0].snippet == "Snippet A"
        assert result.results[1].title == "Result B"

    @pytest.mark.asyncio
    async def test_search_respects_max_results(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, *_ = _make_launch_chain()

        links = [MagicMock() for _ in range(5)]
        for i, link in enumerate(links):
            link.get_attribute = AsyncMock(return_value=f"https://x{i}.com")
            link.inner_text = AsyncMock(return_value=f"Result {i}")
        snippets = [MagicMock() for _ in range(5)]
        for s in snippets:
            s.inner_text = AsyncMock(return_value="Snippet")

        page_mock.query_selector_all = AsyncMock(side_effect=[links, snippets])

        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        result = await adapter.search("test", max_results=3)
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_search_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.goto = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.search("test")

    @pytest.mark.asyncio
    async def test_search_navigation_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.goto = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserSearchError):
            await adapter.search("test")

    @pytest.mark.asyncio
    async def test_search_parse_error_returns_empty(
        self, adapter: PlaywrightBrowserAdapter
    ) -> None:
        pw_callable, page_mock, *_ = _make_launch_chain()
        page_mock.query_selector_all = AsyncMock(side_effect=MockError("parse fail"))

        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        result = await adapter.search("test")
        assert len(result.results) == 0


# =========================================================================
# BrowserPort: extract
# =========================================================================


class TestExtract:
    @pytest.mark.asyncio
    async def test_extract_returns_page(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.extract("https://example.com")
        assert isinstance(result, BrowserPage)
        assert result.status_code == 200
        page_mock.goto.assert_awaited_once_with(
            "https://example.com", timeout=30000, wait_until="domcontentloaded",
        )

    @pytest.mark.asyncio
    async def test_extract_always_extracts_content(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.extract("https://example.com")
        assert result.html is not None
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_extract_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.goto = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.extract("https://example.com")

    @pytest.mark.asyncio
    async def test_extract_navigation_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.goto = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserNavigationError):
            await adapter.extract("https://example.com")


# =========================================================================
# BrowserPort: screenshot
# =========================================================================


class TestScreenshot:
    @pytest.mark.asyncio
    async def test_screenshot_returns_bytes(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.screenshot("https://example.com")
        assert isinstance(result, bytes)
        assert result == b"PNG-DATA"
        page_mock.screenshot.assert_awaited_once_with(full_page=True, type="png")

    @pytest.mark.asyncio
    async def test_screenshot_timeout_in_navigation(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.goto = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.screenshot("https://example.com")

    @pytest.mark.asyncio
    async def test_screenshot_capture_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.screenshot = AsyncMock(side_effect=MockError("capture fail"))
        with pytest.raises(BrowserError):
            await adapter.screenshot("https://example.com")


# =========================================================================
# BrowserPort: close (tested in TestClose)
# =========================================================================

# =========================================================================
# Navigation helpers: back, forward, reload
# =========================================================================


class TestBackForwardReload:
    @pytest.mark.asyncio
    async def test_back(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.back()
        assert isinstance(result, BrowserPage)
        page_mock.go_back.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_back_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.go_back = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.back()

    @pytest.mark.asyncio
    async def test_back_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.go_back = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserNavigationError):
            await adapter.back()

    @pytest.mark.asyncio
    async def test_forward(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.forward()
        assert isinstance(result, BrowserPage)
        page_mock.go_forward.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_forward_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.go_forward = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.forward()

    @pytest.mark.asyncio
    async def test_forward_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.go_forward = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserNavigationError):
            await adapter.forward()

    @pytest.mark.asyncio
    async def test_reload(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.reload()
        assert isinstance(result, BrowserPage)
        page_mock.reload.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reload_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.reload = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.reload()

    @pytest.mark.asyncio
    async def test_reload_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.reload = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserNavigationError):
            await adapter.reload()


# =========================================================================
# Page interaction: click, fill, press_key, scroll, upload_file
# =========================================================================


class TestPageInteraction:
    @pytest.mark.asyncio
    async def test_click(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.click("#btn")
        page_mock.click.assert_awaited_once_with("#btn", timeout=30000)

    @pytest.mark.asyncio
    async def test_click_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.click = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.click("#btn")

    @pytest.mark.asyncio
    async def test_click_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.click = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.click("#btn")

    @pytest.mark.asyncio
    async def test_fill(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.fill("#input", "hello")
        page_mock.fill.assert_awaited_once_with("#input", "hello", timeout=30000)

    @pytest.mark.asyncio
    async def test_fill_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.fill = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.fill("#input", "hello")

    @pytest.mark.asyncio
    async def test_fill_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.fill = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.fill("#input", "hello")

    @pytest.mark.asyncio
    async def test_press_key(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.press_key("Enter")
        page_mock.press.assert_awaited_once_with("body", "Enter")

    @pytest.mark.asyncio
    async def test_press_key_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.press = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.press_key("Enter")

    @pytest.mark.asyncio
    async def test_scroll(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.scroll(delta_x=10, delta_y=200)
        page_mock.evaluate.assert_awaited_once_with("window.scrollBy(10, 200)")

    @pytest.mark.asyncio
    async def test_scroll_defaults(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.scroll()
        page_mock.evaluate.assert_awaited_once_with("window.scrollBy(0, 500)")

    @pytest.mark.asyncio
    async def test_scroll_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.evaluate = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.scroll()

    @pytest.mark.asyncio
    async def test_upload_file_string(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.upload_file("#file", "/path/to/file.txt")
        page_mock.set_input_files.assert_awaited_once_with(
            "#file", ["/path/to/file.txt"], timeout=30000,
        )

    @pytest.mark.asyncio
    async def test_upload_file_list(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.upload_file("#file", ["/a.txt", "/b.txt"])
        page_mock.set_input_files.assert_awaited_once_with(
            "#file", ["/a.txt", "/b.txt"], timeout=30000,
        )

    @pytest.mark.asyncio
    async def test_upload_file_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.set_input_files = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.upload_file("#file", "/p.txt")

    @pytest.mark.asyncio
    async def test_upload_file_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.set_input_files = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.upload_file("#file", "/p.txt")


# =========================================================================
# Content access: get_html, get_visible_text, execute_js, get_current_url, get_title
# =========================================================================


class TestContentAccess:
    @pytest.mark.asyncio
    async def test_get_html(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        html = await adapter.get_html()
        assert html == "<html></html>"
        page_mock.content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_html_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.content = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserContentError):
            await adapter.get_html()

    @pytest.mark.asyncio
    async def test_get_visible_text(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        text = await adapter.get_visible_text()
        assert text == "Hello World"
        page_mock.inner_text.assert_awaited_once_with("body")

    @pytest.mark.asyncio
    async def test_get_visible_text_normalizes_whitespace(
        self, launched_adapter: _Launched
    ) -> None:
        adapter, page_mock = launched_adapter
        page_mock.inner_text = AsyncMock(return_value="  Hello   World\nMore  ")
        text = await adapter.get_visible_text()
        assert text == "Hello World More"

    @pytest.mark.asyncio
    async def test_get_visible_text_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.inner_text = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserContentError):
            await adapter.get_visible_text()

    @pytest.mark.asyncio
    async def test_execute_js(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.execute_js("return 1 + 1")
        assert result == '{"key": "value"}'
        page_mock.evaluate.assert_awaited_once_with("return 1 + 1")

    @pytest.mark.asyncio
    async def test_execute_js_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.evaluate = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.execute_js("bad code")

    @pytest.mark.asyncio
    async def test_get_current_url(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        url = await adapter.get_current_url()
        assert url == "about:blank"

    @pytest.mark.asyncio
    async def test_get_title(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        title = await adapter.get_title()
        assert title == ""
        page_mock.title.assert_awaited_once()


# =========================================================================
# Tab management
# =========================================================================


class TestTabManagement:
    @pytest.mark.asyncio
    async def test_new_tab(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, context_mock, *_ = _make_launch_chain()
        page2 = MagicMock()
        page2.url = "about:blank"
        context_mock.new_page = AsyncMock(return_value=page2)

        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        assert len(adapter._pages) == 1

        pid = await adapter.new_tab()
        assert len(adapter._pages) == 2
        assert adapter._active_page_id == pid
        assert adapter._pages[pid] is page2

    @pytest.mark.asyncio
    async def test_new_tab_with_url(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, context_mock, *_ = _make_launch_chain()
        page2 = MagicMock()
        page2.goto = AsyncMock(return_value=MockResponse(200))
        context_mock.new_page = AsyncMock(return_value=page2)

        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        pid = await adapter.new_tab(url="https://example.com")
        assert pid in adapter._pages
        page2.goto.assert_awaited_once_with("https://example.com", timeout=30000)

    @pytest.mark.asyncio
    async def test_new_tab_error(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        adapter._context.new_page = AsyncMock(side_effect=MockError("boom"))

        with pytest.raises(BrowserSessionError):
            await adapter.new_tab()

    @pytest.mark.asyncio
    async def test_close_tab(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        pid = adapter._active_page_id
        assert pid is not None

        await adapter.close_tab(pid)
        assert pid not in adapter._pages
        page_mock.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_tab_active(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, context_mock, *_ = _make_launch_chain()
        page2 = MagicMock()
        page2.close = AsyncMock()
        page2.url = "about:blank"

        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()
            context_mock.new_page = AsyncMock(return_value=page2)
            pid2 = await adapter.new_tab()

        await adapter.close_tab()  # closes active (pid2)
        assert pid2 not in adapter._pages
        page2.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_tab_last_creates_blank(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        pid = adapter._active_page_id
        assert len(adapter._pages) == 1

        await adapter.close_tab(pid)
        assert len(adapter._pages) == 1  # new blank auto-created
        assert adapter._active_page_id is not None
        assert adapter._active_page_id != pid

    @pytest.mark.asyncio
    async def test_close_tab_nonexistent(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        with pytest.raises(BrowserSessionError, match="not found"):
            await adapter.close_tab("bogus")

    @pytest.mark.asyncio
    async def test_list_tabs(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        tabs = adapter.list_tabs()
        assert len(tabs) == 1
        assert tabs[0]["id"] == adapter._active_page_id
        assert tabs[0]["url"] == "about:blank"

    @pytest.mark.asyncio
    async def test_switch_tab(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, context_mock, *_ = _make_launch_chain()
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        first_pid = adapter._active_page_id
        page2 = MagicMock()
        page2.url = "https://other.com"
        context_mock.new_page = AsyncMock(return_value=page2)
        await adapter.new_tab()

        assert adapter.switch_tab(first_pid) is True
        assert adapter._active_page_id == first_pid

        assert adapter.switch_tab("nonexistent") is False
        assert adapter._active_page_id == first_pid  # unchanged


# =========================================================================
# Cookie and storage
# =========================================================================


class TestCookieStorage:
    @pytest.mark.asyncio
    async def test_get_cookies(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        cookies = await adapter.get_cookies()
        adapter._context.cookies.assert_awaited_once()
        assert cookies == []

    @pytest.mark.asyncio
    async def test_get_cookies_before_init(self, adapter: PlaywrightBrowserAdapter) -> None:
        assert await adapter.get_cookies() == []

    @pytest.mark.asyncio
    async def test_get_cookies_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        adapter._context.cookies = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.get_cookies()

    @pytest.mark.asyncio
    async def test_set_cookies(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        cookies = [{"name": "x", "value": "1"}]
        await adapter.set_cookies(cookies)
        adapter._context.add_cookies.assert_awaited_once_with(cookies)

    @pytest.mark.asyncio
    async def test_set_cookies_before_init(self, adapter: PlaywrightBrowserAdapter) -> None:
        await adapter.set_cookies([])

    @pytest.mark.asyncio
    async def test_set_cookies_error(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        adapter._context.add_cookies = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.set_cookies([{"name": "x", "value": "1"}])

    @pytest.mark.asyncio
    async def test_clear_cookies(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        await adapter.clear_cookies()
        adapter._context.clear_cookies.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clear_cookies_before_init(self, adapter: PlaywrightBrowserAdapter) -> None:
        await adapter.clear_cookies()

    @pytest.mark.asyncio
    async def test_clear_cookies_error(self, launched_adapter: _Launched) -> None:
        adapter, _ = launched_adapter
        adapter._context.clear_cookies = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.clear_cookies()

    @pytest.mark.asyncio
    async def test_get_local_storage(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        data = await adapter.get_local_storage()
        assert data == '{"key": "value"}'
        page_mock.evaluate.assert_awaited_with("JSON.stringify(window.localStorage)")

    @pytest.mark.asyncio
    async def test_get_local_storage_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.evaluate = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.get_local_storage()

    @pytest.mark.asyncio
    async def test_set_local_storage(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.set_local_storage("key", "value")
        page_mock.evaluate.assert_awaited_with("window.localStorage.setItem('key', 'value')")

    @pytest.mark.asyncio
    async def test_set_local_storage_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.evaluate = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(BrowserError):
            await adapter.set_local_storage("key", "value")

    @pytest.mark.asyncio
    async def test_clear_local_storage(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.clear_local_storage()
        page_mock.evaluate.assert_awaited_with("window.localStorage.clear()")

    @pytest.mark.asyncio
    async def test_get_session_storage(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        data = await adapter.get_session_storage()
        assert data == '{"key": "value"}'
        page_mock.evaluate.assert_awaited_with("JSON.stringify(window.sessionStorage)")

    @pytest.mark.asyncio
    async def test_get_session_storage_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.evaluate = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserError):
            await adapter.get_session_storage()

    @pytest.mark.asyncio
    async def test_clear_session_storage(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        await adapter.clear_session_storage()
        page_mock.evaluate.assert_awaited_with("window.sessionStorage.clear()")

    @pytest.mark.asyncio
    async def test_clear_session_storage_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.evaluate = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(BrowserError):
            await adapter.clear_session_storage()


# =========================================================================
# wait_for_navigation
# =========================================================================


class TestWaitForNavigation:
    @pytest.mark.asyncio
    async def test_wait_default(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.wait_for_navigation()
        assert isinstance(result, BrowserPage)
        page_mock.wait_for_load_state.assert_awaited_once_with(
            "networkidle", timeout=30000,
        )

    @pytest.mark.asyncio
    async def test_wait_with_url(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        result = await adapter.wait_for_navigation(url="https://example.com")
        assert isinstance(result, BrowserPage)
        page_mock.wait_for_url.assert_awaited_once_with(
            "https://example.com", timeout=30000,
        )

    @pytest.mark.asyncio
    async def test_wait_timeout(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.wait_for_load_state = AsyncMock(side_effect=MockTimeoutError("timeout"))
        with pytest.raises(BrowserTimeoutError):
            await adapter.wait_for_navigation()

    @pytest.mark.asyncio
    async def test_wait_error(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page_mock.wait_for_load_state = AsyncMock(side_effect=MockError("boom"))
        with pytest.raises(BrowserNavigationError):
            await adapter.wait_for_navigation()


# =========================================================================
# set_default_timeout
# =========================================================================


class TestSetDefaultTimeout:
    def test_set_default_timeout(self, adapter: PlaywrightBrowserAdapter) -> None:
        adapter.set_default_timeout(15.0)
        assert adapter._default_timeout_ms == 15000

    def test_set_default_timeout_zero(self, adapter: PlaywrightBrowserAdapter) -> None:
        adapter.set_default_timeout(0)
        assert adapter._default_timeout_ms == 0


# =========================================================================
# _snapshot helper
# =========================================================================


class TestSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_returns_page(self, launched_adapter: _Launched) -> None:
        adapter, page_mock = launched_adapter
        page = await adapter._snapshot(page_mock)
        assert isinstance(page, BrowserPage)
        assert page.html == "<html></html>"
        assert page.content is not None
        assert page.status_code == 0
        page_mock.content.assert_awaited_once()
        page_mock.title.assert_awaited_once()


# =========================================================================
# _require_active_page error cases
# =========================================================================


class TestRequireActivePage:
    def test_not_initialized(self, adapter: PlaywrightBrowserAdapter) -> None:
        with pytest.raises(BrowserError, match="not initialized"):
            adapter._require_active_page()

    @pytest.mark.asyncio
    async def test_no_active_tab(self, adapter: PlaywrightBrowserAdapter) -> None:
        pw_callable, page_mock, context_mock, *_ = _make_launch_chain()
        with patch(f"{MODULE}._PW_ASYNC_PLAYWRIGHT", pw_callable):
            await adapter.launch()

        adapter._pages.clear()
        adapter._active_page_id = None
        with pytest.raises(BrowserSessionError, match="No active tab"):
            adapter._require_active_page()


# =========================================================================
# _extract_text helper
# =========================================================================


class TestExtractText:
    def test_removes_script_style(self) -> None:
        html = "<script>alert(1)</script><p>Hello</p><style>.c{}</style>"
        result = PlaywrightBrowserAdapter._extract_text(html)
        assert "alert" not in result
        assert ".c" not in result
        assert "Hello" in result

    def test_strips_tags(self) -> None:
        html = "<div><p>Hello <b>World</b></p></div>"
        result = PlaywrightBrowserAdapter._extract_text(html)
        assert result == "Hello World"

    def test_normalizes_whitespace(self) -> None:
        html = "  Hello   <br>  World\nMore  "
        result = PlaywrightBrowserAdapter._extract_text(html)
        assert result == "Hello World More"

    def test_html_entities(self) -> None:
        html = "<p>a&nbsp;b &amp; c &lt; d &gt; e</p>"
        result = PlaywrightBrowserAdapter._extract_text(html)
        assert result == "a b & c < d > e"
