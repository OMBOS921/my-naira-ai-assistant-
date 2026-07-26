"""Comprehensive tests for the browser module.

Covers:
- BrowserPage, BrowserTab, BrowserSearchResult, BrowserSearchResponse dataclasses
- BrowserSession (tab lifecycle, state updates, switching, clear)
- BrowserNavigation (URL validation, same-origin check)
- BrowserContentExtractor (text extraction, word count, reading time, link extraction)
- BrowserSearch (placeholder mode returns empty)
- LocalBrowserAdapter (is_available=False, all operations raise BrowserNotImplementedError)
- BrowserExecutor (navigate, search, extract with timeout/error isolation)
- BrowserManager (ModuleInterface lifecycle, navigate, search, extract, session access)
- BrowserPort ABC
- ModuleInterface protocol conformance
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.browser import (
    BrowserManager,
    BrowserPage,
    BrowserPort,
    BrowserSearchResponse,
    BrowserSearchResult,
    BrowserTab,
)
from backend.modules.browser._content_extractor import BrowserContentExtractor
from backend.modules.browser._exceptions import (
    BrowserNavigationError,
    BrowserNotImplementedError,
)
from backend.modules.browser._executor import BrowserExecutor
from backend.modules.browser._local_adapter import LocalBrowserAdapter
from backend.modules.browser._navigation import BrowserNavigation
from backend.modules.browser._search import BrowserSearch
from backend.modules.browser._session import BrowserSession
from backend.types import ModuleInterface, ToolResult

# =========================================================================
# BrowserPage, BrowserTab, BrowserSearchResult, BrowserSearchResponse
# =========================================================================


class TestBrowserPage:
    def test_minimal(self) -> None:
        page = BrowserPage(url="https://example.com", title="Example")
        assert page.url == "https://example.com"
        assert page.title == "Example"
        assert page.content is None
        assert page.html is None
        assert page.status_code == 0
        assert page.headers == {}
        assert page.duration_ms == 0.0

    def test_all_fields(self) -> None:
        page = BrowserPage(
            url="https://example.com",
            title="Example",
            content="Hello",
            html="<html/>",
            status_code=200,
            headers={"content-type": "text/html"},
            duration_ms=150.0,
        )
        assert page.content == "Hello"
        assert page.status_code == 200
        assert page.headers["content-type"] == "text/html"
        assert page.duration_ms == 150.0

    def test_frozen(self) -> None:
        page = BrowserPage(url="https://a.com", title="A")
        with pytest.raises(AttributeError):
            page.url = "other"  # type: ignore[misc]


class TestBrowserTab:
    def test_minimal(self) -> None:
        tab = BrowserTab(
            id="abc", url="https://a.com", title="A", created_at=1.0, last_active_at=1.0
        )
        assert tab.id == "abc"
        assert tab.history == ()

    def test_frozen(self) -> None:
        tab = BrowserTab(id="a", url="https://a.com", title="A", created_at=1.0, last_active_at=1.0)
        with pytest.raises(AttributeError):
            tab.id = "b"  # type: ignore[misc]


class TestBrowserSearchResult:
    def test_all_fields(self) -> None:
        r = BrowserSearchResult(title="Title", url="https://a.com", snippet="Snippet")
        assert r.title == "Title"
        assert r.url == "https://a.com"
        assert r.snippet == "Snippet"


class TestBrowserSearchResponse:
    def test_defaults(self) -> None:
        resp = BrowserSearchResponse(query="test")
        assert resp.query == "test"
        assert resp.results == ()
        assert resp.total_estimate == 0
        assert resp.duration_ms == 0.0

    def test_with_results(self) -> None:
        results = (
            BrowserSearchResult(title="A", url="https://a.com", snippet="Snippet A"),
            BrowserSearchResult(title="B", url="https://b.com", snippet="Snippet B"),
        )
        resp = BrowserSearchResponse(
            query="test", results=results, total_estimate=100, duration_ms=50.0
        )
        assert len(resp.results) == 2
        assert resp.total_estimate == 100
        assert resp.duration_ms == 50.0


# =========================================================================
# BrowserSession
# =========================================================================


class TestBrowserSession:
    def test_create_tab(self) -> None:
        session = BrowserSession()
        tab = session.create_tab(url="https://a.com", title="A")
        assert tab.url == "https://a.com"
        assert session.active_tab is tab
        assert session.tab_count == 1

    def test_create_tab_blank(self) -> None:
        session = BrowserSession()
        tab = session.create_tab()
        assert tab.url == ""
        assert session.active_tab is tab

    def test_close_tab(self) -> None:
        session = BrowserSession()
        tab = session.create_tab()
        assert session.close_tab(tab.id) is True
        assert session.tab_count == 0
        assert session.active_tab is None

    def test_close_tab_nonexistent(self) -> None:
        session = BrowserSession()
        assert session.close_tab("nonexistent") is False

    def test_close_active_switches_to_other(self) -> None:
        session = BrowserSession()
        tab1 = session.create_tab(url="https://a.com", title="A")
        tab2 = session.create_tab(url="https://b.com", title="B")
        assert session.active_tab_id == tab2.id
        session.close_tab(tab2.id)
        assert session.active_tab_id == tab1.id

    def test_get_tab(self) -> None:
        session = BrowserSession()
        tab = session.create_tab()
        assert session.get_tab(tab.id) is tab

    def test_get_tab_nonexistent(self) -> None:
        session = BrowserSession()
        assert session.get_tab("nonexistent") is None

    def test_list_tabs(self) -> None:
        session = BrowserSession()
        session.create_tab()
        session.create_tab()
        assert len(session.list_tabs()) == 2

    def test_update_tab(self) -> None:
        session = BrowserSession()
        tab = session.create_tab(url="https://a.com", title="A")
        assert session.update_tab(tab.id, url="https://b.com", title="B") is True
        updated = session.get_tab(tab.id)
        assert updated is not None
        assert updated.url == "https://b.com"
        assert updated.title == "B"

    def test_update_tab_nonexistent(self) -> None:
        session = BrowserSession()
        assert session.update_tab("nonexistent", url="https://b.com") is False

    def test_update_tab_history(self) -> None:
        session = BrowserSession()
        tab = session.create_tab(url="https://a.com", title="A")
        session.update_tab(tab.id, url="https://b.com")
        session.update_tab(tab.id, url="https://c.com")
        updated = session.get_tab(tab.id)
        assert updated is not None
        assert updated.history == ("https://b.com", "https://c.com")

    def test_switch_to_tab(self) -> None:
        session = BrowserSession()
        tab1 = session.create_tab(url="https://a.com", title="A")
        tab2 = session.create_tab(url="https://b.com", title="B")
        assert session.active_tab_id == tab2.id
        session.switch_to_tab(tab1.id)
        assert session.active_tab_id == tab1.id

    def test_switch_to_tab_nonexistent(self) -> None:
        session = BrowserSession()
        assert session.switch_to_tab("nonexistent") is False

    def test_clear(self) -> None:
        session = BrowserSession()
        session.create_tab()
        session.create_tab()
        assert session.tab_count == 2
        session.clear()
        assert session.tab_count == 0
        assert session.active_tab is None

    def test_active_tab_id_none_when_empty(self) -> None:
        session = BrowserSession()
        assert session.active_tab_id is None


# =========================================================================
# BrowserNavigation
# =========================================================================


class TestBrowserNavigation:
    def test_validate_url_adds_https(self) -> None:
        result = BrowserNavigation.validate_url("example.com")
        assert result == "https://example.com"

    def test_validate_url_keeps_scheme(self) -> None:
        result = BrowserNavigation.validate_url("http://example.com")
        assert result == "http://example.com"

    def test_validate_url_empty_raises(self) -> None:
        with pytest.raises(BrowserNavigationError, match="empty"):
            BrowserNavigation.validate_url("")

    def test_validate_url_bad_scheme_raises(self) -> None:
        with pytest.raises(BrowserNavigationError, match="scheme"):
            BrowserNavigation.validate_url("ftp://example.com")

    def test_validate_url_no_hostname_raises(self) -> None:
        with pytest.raises(BrowserNavigationError, match="hostname"):
            BrowserNavigation.validate_url("https://")

    def test_is_same_origin(self) -> None:
        assert BrowserNavigation.is_same_origin(
            "https://example.com/page1", "https://example.com/page2"
        ) is True
        assert BrowserNavigation.is_same_origin(
            "https://a.com", "https://b.com"
        ) is False


# =========================================================================
# BrowserContentExtractor
# =========================================================================


class TestBrowserContentExtractor:
    def test_extract_text_strips_tags(self) -> None:
        extractor = BrowserContentExtractor()
        result = extractor.extract_text("<html><body><p>Hello <b>World</b></p></body></html>")
        assert result == "Hello World"

    def test_extract_text_removes_script(self) -> None:
        extractor = BrowserContentExtractor()
        result = extractor.extract_text("<script>alert(1)</script><p>Text</p>")
        assert result == "Text"

    def test_word_count(self) -> None:
        assert BrowserContentExtractor.word_count("hello world") == 2
        assert BrowserContentExtractor.word_count("") == 0

    def test_reading_time_minutes(self) -> None:
        text = "word " * 200
        rt = BrowserContentExtractor.reading_time_minutes(text, words_per_minute=200)
        assert rt == 1.0

    def test_reading_time_minimum(self) -> None:
        rt = BrowserContentExtractor.reading_time_minutes("hi", words_per_minute=200)
        assert rt == 0.1

    def test_extract_links(self) -> None:
        html = '<a href="https://a.com">Link A</a><a href="https://b.com">Link B</a>'
        links = BrowserContentExtractor.extract_links(html)
        assert len(links) == 2
        assert links[0]["href"] == "https://a.com"
        assert links[0]["text"] == "Link A"

    def test_extract_links_skips_anchors(self) -> None:
        html = '<a href="#section">Skip</a><a href="https://a.com">Real</a>'
        links = BrowserContentExtractor.extract_links(html)
        assert len(links) == 1
        assert links[0]["href"] == "https://a.com"

    def test_extract_links_skips_javascript(self) -> None:
        html = '<a href="javascript:void(0)">JS</a>'
        links = BrowserContentExtractor.extract_links(html)
        assert len(links) == 0


# =========================================================================
# BrowserSearch (placeholder)
# =========================================================================


class TestBrowserSearch:
    @pytest.mark.asyncio
    async def test_search_returns_empty(self) -> None:
        searcher = BrowserSearch()
        result = await searcher.search("test query")
        assert result.query == "test query"
        assert result.results == ()


# =========================================================================
# LocalBrowserAdapter
# =========================================================================


class TestLocalBrowserAdapter:
    def test_is_available_false(self) -> None:
        adapter = LocalBrowserAdapter()
        assert adapter.is_available is False

    @pytest.mark.asyncio
    async def test_navigate_raises(self) -> None:
        adapter = LocalBrowserAdapter()
        with pytest.raises(BrowserNotImplementedError):
            await adapter.navigate("https://example.com")

    @pytest.mark.asyncio
    async def test_search_raises(self) -> None:
        adapter = LocalBrowserAdapter()
        with pytest.raises(BrowserNotImplementedError):
            await adapter.search("test")

    @pytest.mark.asyncio
    async def test_extract_raises(self) -> None:
        adapter = LocalBrowserAdapter()
        with pytest.raises(BrowserNotImplementedError):
            await adapter.extract("https://example.com")

    @pytest.mark.asyncio
    async def test_screenshot_raises(self) -> None:
        adapter = LocalBrowserAdapter()
        with pytest.raises(BrowserNotImplementedError):
            await adapter.screenshot("https://example.com")

    @pytest.mark.asyncio
    async def test_close_is_noop(self) -> None:
        adapter = LocalBrowserAdapter()
        await adapter.close()


# =========================================================================
# BrowserExecutor
# =========================================================================


class _MockAdapter:
    """Test double that implements BrowserPort with controllable behaviour."""

    def __init__(
        self,
        available: bool = True,
        navigate_result: ToolResult | None = None,
        search_result: ToolResult | None = None,
        extract_result: ToolResult | None = None,
    ) -> None:
        self._available = available
        self._navigate_result = navigate_result
        self._search_result = search_result
        self._extract_result = extract_result

    @property
    def is_available(self) -> bool:
        return self._available

    async def navigate(
        self, url: str, timeout: float = 30.0, extract_content: bool = True
    ) -> BrowserPage:
        if self._navigate_result is not None:
            raise BrowserNotImplementedError()
        return BrowserPage(url=url, title="Mock Page", content="Mock content", status_code=200)

    async def search(
        self, query: str, max_results: int = 10, timeout: float = 30.0
    ) -> BrowserSearchResponse:
        if self._search_result is not None:
            raise BrowserNotImplementedError()
        result = BrowserSearchResult(title="Result", url="https://example.com", snippet="Snippet")
        return BrowserSearchResponse(
            query=query,
            results=(result,),
            total_estimate=1,
            duration_ms=10.0,
        )

    async def extract(self, url: str, timeout: float = 30.0) -> BrowserPage:
        if self._extract_result is not None:
            raise BrowserNotImplementedError()
        return BrowserPage(url=url, title="Extracted", content="Extracted content", status_code=200)

    async def click(self, selector: str, timeout: float | None = None) -> None:
        pass

    async def fill(self, selector: str, value: str, timeout: float | None = None) -> None:
        pass

    async def scroll(self, delta_x: int = 0, delta_y: int = 500) -> None:
        pass

    async def get_visible_text(self) -> str:
        return "Mock visible page text"

    async def execute_js(self, script: str, *args: Any) -> Any:
        return "Mock element text"

    async def close(self) -> None:
        pass



class TestBrowserExecutor:
    @pytest.mark.asyncio
    async def test_navigate_success(self) -> None:
        adapter = _MockAdapter()
        exe = BrowserExecutor(adapter=adapter)
        result = await exe.navigate("https://example.com")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_navigate_not_implemented(self) -> None:
        adapter = LocalBrowserAdapter()
        exe = BrowserExecutor(adapter=adapter)
        result = await exe.navigate("https://example.com")
        assert result.status == "error"
        assert "not configured" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_search_success(self) -> None:
        adapter = _MockAdapter()
        exe = BrowserExecutor(adapter=adapter)
        result = await exe.search("test")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_search_not_implemented(self) -> None:
        adapter = LocalBrowserAdapter()
        exe = BrowserExecutor(adapter=adapter)
        result = await exe.search("test")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_extract_success(self) -> None:
        adapter = _MockAdapter()
        exe = BrowserExecutor(adapter=adapter)
        result = await exe.extract("https://example.com")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_extract_not_implemented(self) -> None:
        adapter = LocalBrowserAdapter()
        exe = BrowserExecutor(adapter=adapter)
        result = await exe.extract("https://example.com")
        assert result.status == "error"

    def test_is_available_true(self) -> None:
        adapter = _MockAdapter(available=True)
        exe = BrowserExecutor(adapter=adapter)
        assert exe.is_available is True

    def test_is_available_false(self) -> None:
        adapter = LocalBrowserAdapter()
        exe = BrowserExecutor(adapter=adapter)
        assert exe.is_available is False


# =========================================================================
# BrowserManager — ModuleInterface lifecycle
# =========================================================================


class TestBrowserManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = BrowserManager()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_async_init_sets_up(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        assert mgr.degraded is False
        assert mgr.is_available is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        mgr.session.create_tab(url="https://a.com", title="A")
        assert mgr.session.tab_count == 1
        await mgr.async_shutdown()
        assert mgr.session.tab_count == 0

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_degrade_clears_session(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        mgr.session.create_tab()
        mgr.degrade()
        assert mgr.session.tab_count == 0

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = BrowserManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        logger = MagicMock()
        mgr = BrowserManager(logger=logger)
        assert mgr._logger is logger

    @pytest.mark.asyncio
    async def test_with_adapter_injection(self) -> None:
        adapter = LocalBrowserAdapter()
        mgr = BrowserManager(adapter=adapter)
        assert mgr._adapter is adapter


# =========================================================================
# BrowserManager — navigation
# =========================================================================


class TestBrowserManagerNavigation:
    @pytest.mark.asyncio
    async def test_navigate_with_valid_url(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.navigate("https://example.com")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_navigate_with_invalid_url(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        result = await mgr.navigate("")
        assert result.status == "error"
        assert "Invalid URL" in (result.error or "")

    @pytest.mark.asyncio
    async def test_navigate_with_bad_scheme(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        result = await mgr.navigate("ftp://example.com")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_navigate_degraded_raises(self) -> None:
        mgr = BrowserManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.navigate("https://example.com")


# =========================================================================
# BrowserManager — search
# =========================================================================


class TestBrowserManagerSearch:
    @pytest.mark.asyncio
    async def test_search_success(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.search("test")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_search_no_adapter(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        result = await mgr.search("test")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_search_degraded_raises(self) -> None:
        mgr = BrowserManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.search("test")


# =========================================================================
# BrowserManager — extract
# =========================================================================


class TestBrowserManagerExtract:
    @pytest.mark.asyncio
    async def test_extract_success(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.extract("https://example.com")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_extract_invalid_url(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.extract("")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_extract_degraded_raises(self) -> None:
        mgr = BrowserManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.extract("https://example.com")


# =========================================================================
# BrowserManager — session access
# =========================================================================


class TestBrowserManagerSession:
    @pytest.mark.asyncio
    async def test_session_property(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        session = mgr.session
        assert session.tab_count == 0
        session.create_tab()
        assert mgr.session.tab_count == 1

    @pytest.mark.asyncio
    async def test_is_available(self) -> None:
        mgr = BrowserManager()
        assert mgr.is_available is False


# =========================================================================
# BrowserPort — ABC
# =========================================================================


class TestBrowserPortAbc:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            BrowserPort()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_adapter(self) -> None:
        adapter = LocalBrowserAdapter()
        assert isinstance(adapter, BrowserPort)
        assert adapter.is_available is False


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_browser_manager_conforms_to_protocol(self) -> None:
        assert isinstance(BrowserManager(), ModuleInterface)

    def test_browser_manager_has_required_methods(self) -> None:
        mgr = BrowserManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")


# =========================================================================
# Deep Web Automation Actions & Tool Registration
# =========================================================================


class TestBrowserManagerDeepWeb:
    @pytest.mark.asyncio
    async def test_click_success(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        res = await mgr.click("button#submit")
        assert res.status == "success"
        assert "button#submit" in res.output

    @pytest.mark.asyncio
    async def test_click_no_adapter(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        res = await mgr.click("button#submit")
        assert res.status == "error"

    @pytest.mark.asyncio
    async def test_fill_success(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        res = await mgr.fill("input#username", "testuser")
        assert res.status == "success"
        assert "input#username" in res.output

    @pytest.mark.asyncio
    async def test_fill_no_adapter(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        res = await mgr.fill("input#username", "testuser")
        assert res.status == "error"

    @pytest.mark.asyncio
    async def test_scroll_success(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        res = await mgr.scroll(delta_x=0, delta_y=300)
        assert res.status == "success"

    @pytest.mark.asyncio
    async def test_scroll_no_adapter(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        res = await mgr.scroll(delta_x=0, delta_y=300)
        assert res.status == "error"

    @pytest.mark.asyncio
    async def test_extract_text_success(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        res = await mgr.extract_text()
        assert res.status == "success"
        assert "Mock visible page text" in res.output

    @pytest.mark.asyncio
    async def test_extract_text_with_selector(self) -> None:
        adapter = _MockAdapter()
        mgr = BrowserManager(adapter=adapter)
        await mgr.async_init()
        res = await mgr.extract_text(selector="div.content")
        assert res.status == "success"
        assert "Mock element text" in res.output

    @pytest.mark.asyncio
    async def test_extract_text_no_adapter(self) -> None:
        mgr = BrowserManager()
        await mgr.async_init()
        res = await mgr.extract_text()
        assert res.status == "error"


class TestBrowserToolRegistration:
    @pytest.mark.asyncio
    async def test_registers_all_deep_web_tools(self) -> None:
        tool_manager = MagicMock()
        registered_tools: dict[str, Any] = {}

        def mock_register(tool_def: Any, handler: Any) -> None:
            registered_tools[tool_def.name] = (tool_def, handler)

        tool_manager.register_tool = mock_register

        mgr = BrowserManager(tool_manager=tool_manager)
        await mgr.async_init()

        expected_tools = {
            "browser_navigate",
            "browser_search",
            "browser_click",
            "browser_fill",
            "browser_scroll",
            "browser_extract_text",
        }
        assert expected_tools.issubset(set(registered_tools.keys()))
        for name in expected_tools:
            tool_def, handler = registered_tools[name]
            assert tool_def.category == "browser"
            assert callable(handler)

