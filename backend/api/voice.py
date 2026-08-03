"""Voice management API endpoints.

Lists registered TTS providers, switches the active provider, previews
voice synthesis, and accepts audio uploads for backend STT transcription.
Follows the same ``APIRouter`` + ``Request``-based manager lookup pattern
as ``backend/api/capabilities.py`` and ``backend/api/settings.py``.
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

router = APIRouter(prefix="/api/voice", tags=["voice"])

_PREVIEW_PHRASE = "Hi, I'm Naira. Your AI assistant is ready."


class ActiveProviderRequest(BaseModel):
    name: str


def _get_voice_manager(request: Request) -> Any:
    mgr = getattr(request.app.state, "voice_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="Voice manager not available",
        )
    return mgr


@router.get("/providers")
async def list_voice_providers(request: Request) -> dict[str, Any]:
    """Return all registered TTS providers with availability and active status."""
    mgr = _get_voice_manager(request)
    providers: list[dict[str, Any]] = []
    active_name = mgr.active_tts_provider_name

    for name, provider in mgr.tts_providers.items():
        providers.append(
            {
                "name": name,
                "provider_name": provider.provider_name,
                "is_available": provider.is_available,
                "active": name == active_name,
            }
        )

    providers.sort(key=lambda p: p["name"])
    return {"providers": providers, "active": active_name}


@router.post("/active")
async def set_active_provider(
    payload: ActiveProviderRequest,
    request: Request,
) -> dict[str, Any]:
    """Set the active TTS provider by name.

    Raises ``404`` if the provider is not registered.
    """
    mgr = _get_voice_manager(request)
    try:
        mgr.set_active_tts_provider(payload.name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"active": payload.name}


@router.post("/preview")
async def preview_voice(request: Request) -> dict[str, Any]:
    """Synthesize a short preview phrase through the active TTS provider.

    Returns base64-encoded audio suitable for playback in the browser.
    """
    mgr = _get_voice_manager(request)

    result = await mgr.synthesize(_PREVIEW_PHRASE)

    if result.status != "success" or not getattr(result, "audio_bytes", None):
        raise HTTPException(
            status_code=500,
            detail=result.error or "Voice synthesis produced no audio",
        )

    audio_b64 = base64.b64encode(result.audio_bytes).decode("utf-8")

    # Determine voice source (RVC vs fallback)
    voice_source = "unknown"
    # The ToolResult from VoiceManager.synthesize() wraps the provider result;
    # we check the active provider to infer source.
    active_name = mgr.active_tts_provider_name or ""
    if "rvc" in active_name:
        voice_source = "rvc"
    else:
        voice_source = active_name or "fallback"

    return {
        "audio": audio_b64,
        "format": "mp3",
        "voice_source": voice_source,
        "text": _PREVIEW_PHRASE,
    }


@router.post("/transcribe")
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Transcribe uploaded audio through the backend STT pipeline.

    Accepts any audio format supported by faster-whisper (wav, mp3, ogg, etc.).
    Returns the transcribed text, confidence, and detected language.
    """
    mgr = _get_voice_manager(request)

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    from backend.modules.voice._types import AudioData

    audio = AudioData(
        source_type="bytes",
        format="unknown",
        data=audio_bytes,
        size_bytes=len(audio_bytes),
    )

    result = await mgr.transcribe(audio)

    if result.status != "success":
        raise HTTPException(
            status_code=500,
            detail=result.error or "Transcription failed",
        )

    return {
        "text": result.output or "",
        "status": "success",
    }
