from __future__ import annotations

import asyncio
import pytest
from pathlib import Path

from backend.modules.memory.memory_module import MemoryManager
from backend.modules.memory.engines.user_profile_engine import UserProfileEngine
from backend.runtime.fast_command_router import FastCommandRouter, _fetch_instant_web_search
from backend.modules.llm.provider_base import ProviderBase, RetryPolicy
from backend.modules.pc_control.pc_control_module import PCControlManager
from backend.modules.security._command_validator import CommandValidator


@pytest.mark.asyncio
async def test_area_1_voice_memory_extraction(tmp_path: Path) -> None:
    """Test voice-driven memory update extraction and persona preservation."""
    mem_mgr = MemoryManager(db_path=tmp_path / "test_mem.db", index_path=tmp_path / "index.json")
    await mem_mgr.async_init()

    # 1. Voice directive extraction check
    facts = mem_mgr._extract_facts_heuristically("Naira, remember this detail: my favorite programming language is Python")
    assert any(topic == "voice_fact" for topic, _ in facts)

    # 2. Sparse profile summary persona preservation
    summary = mem_mgr.user_profile.get_summary_for_prompt()
    assert "Naira-OS" in summary or "assistant_persona" in summary

    await mem_mgr.async_shutdown()


@pytest.mark.asyncio
async def test_area_2_fcr_instant_web_search() -> None:
    """Test instant web search data retrieval in FCR."""
    fcr = FastCommandRouter()
    
    # 1. Real-time queries accepted as fast command
    assert fcr.is_fast_command("search the web for Python 3.12 release notes")

    # 2. Fetch instant web result
    res = _fetch_instant_web_search("Python programming language")
    assert "Python" in res or "INSTANT WEB SEARCH" in res or "SUCCESS" in res


@pytest.mark.asyncio
async def test_area_3_llm_dynamic_timeout() -> None:
    """Test ProviderBase dynamic timeout configuration."""
    class DummyProvider(ProviderBase):
        def __init__(self) -> None:
            super().__init__(provider_name="dummy", timeout=60)
        async def _call_provider(self, prompt, context, tools):
            from backend.types import LLMResponse, TokenUsage
            return LLMResponse("OK", None, "stop", TokenUsage(1, 1, 2), "dummy", 1.0)
        async def _count_tokens_internal(self, text: str) -> int:
            return len(text)

    prov = DummyProvider()
    assert prov._timeout == 60
    resp = await prov.generate("Hello", [])
    assert resp.text == "OK"


from backend.modules.pc_control._production_adapter import ProductionPCControlAdapter


@pytest.mark.asyncio
async def test_area_4_pc_control_pro_utilities(tmp_path: Path) -> None:
    """Test archiving zip/unzip, safe process termination, and security blocks."""
    # 1. Test zip and unzip filesystem operations
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    (src_dir / "test.txt").write_text("Hello Naira OS", encoding="utf-8")
    
    zip_path = tmp_path / "archive.zip"
    extract_dir = tmp_path / "extracted"

    adapter = ProductionPCControlAdapter()
    mgr = PCControlManager(adapter=adapter)
    await mgr.async_init()

    # Zip
    zip_res = await mgr.filesystem_zip_directory(str(src_dir), str(zip_path))
    assert zip_res.status == "success"
    assert zip_path.is_file()

    # Extract
    ext_res = await mgr.filesystem_extract_archive(str(zip_path), str(extract_dir))
    assert ext_res.status == "success"
    assert (extract_dir / "test.txt").is_file()

    # 2. Security block check for dangerous commands
    validator = CommandValidator()
    sec_check = await validator.validate("format c:")
    assert sec_check.denied is True

    await mgr.async_shutdown()
