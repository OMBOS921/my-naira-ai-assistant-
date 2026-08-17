"""
Unit tests for Tool Protocol and Security Layer.
"""

from __future__ import annotations

import pytest
from backend.types import ToolCall, ToolResult
from NairaLLM.integration.tool_protocol.protocol import ToolProtocol, ToolProtocolError


def test_validate_tool_call_valid() -> None:
    proto = ToolProtocol()
    call_dict = {
        "name": "pc_system_settings",
        "arguments": {"setting": "volume", "value": 50},
    }
    tool_call = proto.validate_tool_call(call_dict)
    assert tool_call.name == "pc_system_settings"
    assert tool_call.arguments["value"] == 50


def test_validate_tool_call_invalid_argument() -> None:
    proto = ToolProtocol()
    call_dict = {
        "name": "pc_system_settings",
        "arguments": {"setting": "unsupported_setting", "value": 50},
    }
    with pytest.raises(ToolProtocolError):
        proto.validate_tool_call(call_dict)


@pytest.mark.asyncio
async def test_tool_protocol_security_check() -> None:
    # Security function that denies volume > 90
    def security_gate(name: str, args: dict) -> bool:
        if name == "pc_system_settings" and args.get("value", 0) > 90:
            return False
        return True

    proto = ToolProtocol(
        tool_executor_fn=lambda tc, ctx: ToolResult(status="success", output="Executed"),
        security_checker_fn=security_gate,
    )

    tc_safe = ToolCall(id="1", name="pc_system_settings", arguments={"setting": "volume", "value": 50})
    res_safe = await proto.execute_validated_call(tc_safe)
    assert res_safe.status == "success"

    tc_risky = ToolCall(id="2", name="pc_system_settings", arguments={"setting": "volume", "value": 95})
    res_risky = await proto.execute_validated_call(tc_risky)
    assert res_risky.status == "error"
    assert "denied by security policy" in res_risky.error
