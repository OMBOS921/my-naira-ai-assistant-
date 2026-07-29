"""Unit tests for RVCProvider in rvc_provider.py."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.modules.voice._exceptions import VoiceSynthesisError
from backend.modules.voice._types import AudioData, SynthesisResult
from backend.modules.voice.providers.rvc_provider import RVCProvider


@pytest.fixture
def mock_edge_tts():
    provider = MagicMock()
    provider.is_available = True
    provider.synthesize = AsyncMock(
        return_value=SynthesisResult(
            audio=AudioData(
                source_type="bytes",
                format="mp3",
                sample_rate=24000,
                channels=1,
                duration_ms=1000.0,
                size_bytes=10,
                data=b"fake-mp3-bytes",
            ),
            text="Namaste Naira",
            voice_id="en-IN-NeerjaNeural",
            duration_ms=1000.0,
        )
    )
    provider.close = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_rvc_provider_properties(mock_edge_tts) -> None:
    provider = RVCProvider(base_provider=mock_edge_tts)
    assert provider.provider_name == "rvc"
    assert provider.is_available is True
    assert provider._base_voice == "en-IN-NeerjaNeural"


@pytest.mark.asyncio
async def test_rvc_fallback_when_model_missing(mock_edge_tts, tmp_path) -> None:
    missing_model = tmp_path / "non_existent.pth"
    provider = RVCProvider(
        model_path=missing_model,
        base_provider=mock_edge_tts,
    )

    res = await provider.synthesize("Namaste Naira")
    assert res.audio.data == b"fake-mp3-bytes"
    mock_edge_tts.synthesize.assert_called_once()


@pytest.mark.asyncio
async def test_rvc_synthesize_success_and_cleanup(mock_edge_tts, tmp_path) -> None:
    fake_model = tmp_path / "naira.pth"
    fake_model.write_bytes(b"dummy-model-weights")
    fake_index = tmp_path / "naira.index"
    fake_index.write_bytes(b"dummy-index")

    provider = RVCProvider(
        model_path=fake_model,
        index_path=fake_index,
        base_provider=mock_edge_tts,
    )

    captured_temp_files = []

    def mock_worker(input_path: str, output_path: str) -> None:
        captured_temp_files.append(input_path)
        captured_temp_files.append(output_path)
        with open(output_path, "wb") as f:
            f.write(b"rvc-converted-wav-bytes")

    with patch.object(provider, "_run_rvc_inference_sync", side_effect=mock_worker):
        res = await provider.synthesize("Namaste Naira")
        assert res.audio.data == b"rvc-converted-wav-bytes"
        assert res.audio.format == "wav"
        assert res.text == "Namaste Naira"

    # Verify temp files were cleaned up
    for tmp_file in captured_temp_files:
        assert not os.path.exists(tmp_file)


@pytest.mark.asyncio
async def test_rvc_close(mock_edge_tts) -> None:
    provider = RVCProvider(base_provider=mock_edge_tts)
    await provider.close()
    mock_edge_tts.close.assert_called_once()
