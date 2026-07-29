"""Unit tests for RvcTTSProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.modules.voice._exceptions import VoiceSynthesisError
from backend.modules.voice._types import AudioData, SynthesisResult
from backend.modules.voice.providers.rvc_tts_provider import RvcTTSProvider


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
            text="Hello Naira",
            voice_id="en-US-JennyNeural",
            duration_ms=1000.0,
        )
    )
    provider.close = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_rvc_provider_properties(mock_edge_tts) -> None:
    provider = RvcTTSProvider(base_provider=mock_edge_tts)
    assert provider.provider_name == "rvc"
    assert provider.is_available is True


@pytest.mark.asyncio
async def test_rvc_fallback_when_model_missing(mock_edge_tts, tmp_path) -> None:
    missing_model = tmp_path / "non_existent.pth"
    provider = RvcTTSProvider(
        model_path=missing_model,
        base_provider=mock_edge_tts,
    )

    res = await provider.synthesize("Hello Naira")
    assert res.audio.data == b"fake-mp3-bytes"
    mock_edge_tts.synthesize.assert_called_once()


@pytest.mark.asyncio
async def test_rvc_synthesize_success(mock_edge_tts, tmp_path) -> None:
    fake_model = tmp_path / "naira.pth"
    fake_model.write_bytes(b"dummy-model-weights")
    fake_index = tmp_path / "naira.index"
    fake_index.write_bytes(b"dummy-index")

    provider = RvcTTSProvider(
        model_path=fake_model,
        index_path=fake_index,
        base_provider=mock_edge_tts,
    )

    def mock_worker(input_path: str, output_path: str) -> None:
        with open(output_path, "wb") as f:
            f.write(b"rvc-converted-wav-bytes")

    with patch.object(provider, "_run_rvc_inference_sync", side_effect=mock_worker):
        res = await provider.synthesize("Hello Naira")
        assert res.audio.data == b"rvc-converted-wav-bytes"
        assert res.audio.format == "wav"
        assert res.text == "Hello Naira"


@pytest.mark.asyncio
async def test_rvc_close(mock_edge_tts) -> None:
    provider = RvcTTSProvider(base_provider=mock_edge_tts)
    await provider.close()
    mock_edge_tts.close.assert_called_once()
