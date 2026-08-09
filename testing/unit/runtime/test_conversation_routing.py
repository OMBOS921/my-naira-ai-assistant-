"""Regression tests for the conversation-routing bug fix.

Verifies:
1. is_fast_command() uses allow-list (False for conversation, True for commands)
2. _execute_conversation() never leaks internal reasoning/classifier fields
3. RuntimeManager.process_request() routes CONVERSATION intent to the LLM pipeline
4. RuntimeManager.process_request_stream() does the same for streaming
"""

import asyncio
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.runtime.fast_command_router import CommandIntent, FastCommandRouter
from backend.runtime._runtime_manager import RuntimeManager
from backend.types import LLMResponse, TokenUsage, UserRequest


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

@pytest.fixture
def fcr():
    """Bare FastCommandRouter with no managers wired."""
    return FastCommandRouter(api_key="test-key")


@pytest.fixture
def mock_llm_manager():
    mgr = AsyncMock()
    mgr.generate.return_value = LLMResponse(
        text="Hi there! How can I help you today?",
        tool_calls=None,
        finish_reason="stop",
        token_usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        provider="test",
        duration_ms=50.0,
    )
    return mgr


def _make_runtime(llm_manager=None, **kwargs):
    """Build a RuntimeManager with minimal wiring for testing."""
    # Provide a no-op reasoning gateway that always says llm_required=True
    mock_gw = MagicMock()
    mock_gw.evaluate.return_value = SimpleNamespace(
        category="GENERAL",
        llm_required=True,
        complexity_score=1,
        reasoning="test",
        clarification_required=False,
        memory_lookup=False,
        web_search_only=False,
    )
    return RuntimeManager(
        llm_manager=llm_manager,
        reasoning_gateway=mock_gw,
        **kwargs,
    )


# ---------------------------------------------------------------
# 1. is_fast_command() allow-list tests
# ---------------------------------------------------------------

class TestIsFastCommandAllowList:
    """Assert is_fast_command returns False for conversation, True for commands."""

    @pytest.mark.parametrize("text", [
        "hello",
        "how are you",
        "thank you",
        "what is the meaning of life",
        "tell me a joke",
        "good morning",
        "I appreciate your help",
        "who are you",
        "nice to meet you",
    ])
    def test_conversational_phrases_return_false(self, fcr, text):
        assert fcr.is_fast_command(text) is False, (
            f"is_fast_command('{text}') should be False for conversational input"
        )

    @pytest.mark.parametrize("text,expected", [
        ("open notepad", True),
        ("search for weather", True),
        ("delete the folder test", True),
        ("shutdown the pc", True),
        ("set volume to 50", True),
        ("take a screenshot", True),
        ("create file test.txt", True),
        ("lock the pc", True),
        ("open chrome", True),
        ("restart the computer", True),
        ("youtube", True),
        ("open https://google.com", True),
        ("write a python script", True),
        ("debug this error", True),
    ])
    def test_command_phrases_return_true(self, fcr, text, expected):
        assert fcr.is_fast_command(text) is expected, (
            f"is_fast_command('{text}') should be {expected}"
        )

    def test_empty_and_whitespace_return_false(self, fcr):
        assert fcr.is_fast_command("") is False
        assert fcr.is_fast_command("   ") is False


# ---------------------------------------------------------------
# 2. _execute_conversation() never leaks reasoning
# ---------------------------------------------------------------

class TestExecuteConversationNoLeaks:
    """Assert _execute_conversation never returns internal classifier fields."""

    def test_reasoning_not_in_response(self, fcr):
        intent_data = {
            "intent": "CONVERSATION",
            "reasoning": "User initiated a greeting",
            "confidence": 0.95,
            "operations": [{"action": "chat", "target": "", "parameters": {}}],
        }
        result = fcr._execute_conversation(intent_data, "hello")
        assert "[CONVERSATION]" not in result
        assert "User initiated a greeting" not in result

    def test_generic_fallback_always_returned(self, fcr):
        result = fcr._execute_conversation({"intent": "CONVERSATION"}, "hi there")
        assert "hi there" in result
        assert "[CONVERSATION]" not in result

    def test_no_classifier_field_leaks(self, fcr):
        intent_data = {
            "intent": "CONVERSATION",
            "reasoning": "This looks like chit-chat",
            "confidence": 0.99,
            "operations": [{"action": "chat", "target": "", "parameters": {}}],
        }
        result = fcr._execute_conversation(intent_data, "how are you")
        # Must not contain reasoning or any [TAG] prefix
        assert "chit-chat" not in result
        assert not result.startswith("[")


# ---------------------------------------------------------------
# 3. RuntimeManager.process_request() -- CONVERSATION falls through
# ---------------------------------------------------------------

class TestProcessRequestConversationFallthrough:
    """Assert that when FCR classifies as CONVERSATION, the LLM pipeline runs."""

    @pytest.mark.asyncio
    async def test_conversation_routes_to_llm(self, mock_llm_manager):
        rt = _make_runtime(llm_manager=mock_llm_manager)

        # Make is_fast_command return True (simulating the old bug scenario)
        # so FCR branch is entered, then classify_intent returns CONVERSATION
        rt._fast_command_router.is_fast_command = MagicMock(return_value=True)
        rt._fast_command_router.classify_intent = AsyncMock(return_value={
            "intent": "CONVERSATION",
            "reasoning": "User said hello",
            "confidence": 0.95,
            "operations": [{"action": "chat", "target": "", "parameters": {}}],
        })

        request = UserRequest(
            id="req-1",
            session_id="sess-1",
            text="hello",
            source="test",
            timestamp=0.0,
            metadata={},
        )

        response = await rt.process_request(request)

        # The LLM should have been called (Route 3)
        mock_llm_manager.generate.assert_called()
        # Response must NOT contain leaked classifier text
        assert "[CONVERSATION]" not in response.text
        assert "User said hello" not in response.text

    @pytest.mark.asyncio
    async def test_conversation_response_has_llm_text(self, mock_llm_manager):
        rt = _make_runtime(llm_manager=mock_llm_manager)

        rt._fast_command_router.is_fast_command = MagicMock(return_value=True)
        rt._fast_command_router.classify_intent = AsyncMock(return_value={
            "intent": "CONVERSATION",
            "reasoning": "General greeting detected",
            "confidence": 0.9,
            "operations": [{"action": "chat", "target": "", "parameters": {}}],
        })

        request = UserRequest(
            id="req-2",
            session_id="sess-1",
            text="how are you",
            source="test",
            timestamp=0.0,
            metadata={},
        )

        response = await rt.process_request(request)
        # Should contain the LLM-generated text, not classifier text
        assert response.text == "Hi there! How can I help you today?"


# ---------------------------------------------------------------
# 4. RuntimeManager.process_request_stream() -- CONVERSATION falls through
# ---------------------------------------------------------------

class TestProcessRequestStreamConversationFallthrough:
    """Assert the streaming path also routes CONVERSATION to the LLM."""

    @pytest.mark.asyncio
    async def test_stream_conversation_routes_to_llm(self, mock_llm_manager):
        rt = _make_runtime(llm_manager=mock_llm_manager)

        rt._fast_command_router.is_fast_command = MagicMock(return_value=True)
        rt._fast_command_router.classify_intent = AsyncMock(return_value={
            "intent": "CONVERSATION",
            "reasoning": "User greeted the assistant",
            "confidence": 0.95,
            "operations": [{"action": "chat", "target": "", "parameters": {}}],
        })

        request = UserRequest(
            id="req-3",
            session_id="sess-1",
            text="thank you",
            source="test",
            timestamp=0.0,
            metadata={},
        )

        chunks = []
        async for chunk in rt.process_request_stream(request):
            chunks.append(chunk)

        full_response = "".join(chunks)

        # The LLM should have been called
        mock_llm_manager.generate.assert_called()
        # Response must NOT contain leaked classifier text
        assert "[CONVERSATION]" not in full_response
        assert "User greeted the assistant" not in full_response


# ---------------------------------------------------------------
# 5. Existing command routing still works
# ---------------------------------------------------------------

class TestCommandsStillRouted:
    """Verify genuine commands are still handled by FCR (no regression)."""

    @pytest.mark.asyncio
    async def test_system_control_still_routes(self):
        mock_pc = AsyncMock()
        mock_pc.launch_application.return_value = SimpleNamespace(status="success")
        fcr = FastCommandRouter(pc_control_manager=mock_pc, api_key="test-key")

        result = await fcr._execute_system_control(
            [{"action": "open_app", "target": "notepad", "parameters": {}}], ""
        )
        assert "[SUCCESS]" in result
        mock_pc.launch_application.assert_called_once()

    @pytest.mark.asyncio
    async def test_browser_control_still_routes(self):
        mock_browser = AsyncMock()
        mock_browser.navigate.return_value = SimpleNamespace(status="success")
        fcr = FastCommandRouter(browser_manager=mock_browser, api_key="test-key")

        result = await fcr._execute_browser_control(
            [{"action": "open_url", "target": "https://example.com", "parameters": {}}], ""
        )
        assert "[SUCCESS]" in result
        mock_browser.navigate.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
