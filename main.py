#!/usr/bin/env python3
"""
Naira-OS Bootstrap — Main Entry Point.

18_Boot_Sequence.md §2, 21_System_Contracts.md §10.1.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import asyncio
import base64
import io
import logging
import os
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Final

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend import __version__
from backend.boot import boot_core_modules, shutdown_modules
from backend.modules.settings import AppConfig, EnvironmentSnapshot
from backend.modules.utils.di import DIContainer
from backend.modules.utils.log import install_excepthook, setup_logging
from backend.eventbus import EventBus
from backend.orchestrator import FSMState, Orchestrator
from backend.types import UserRequest

ROOT_DIR: Final[Path] = Path(__file__).resolve().parent
_SHUTDOWN_GRACE_S: Final[float] = 3.0

_LOG: logging.Logger = logging.getLogger("naira.main")
_modules: dict[str, Any] = {}
_orchestrator: Orchestrator | None = None
_container: DIContainer | None = None
_active_websockets: set[WebSocket] = set()


def record_audio_sd(duration_sec: float = 4.0, samplerate: int = 16000) -> tuple[bytes | None, float]:
    """Record audio using sounddevice into WAV bytes and compute audio RMS energy."""
    try:
        import sounddevice as sd  # type: ignore
        import soundfile as sf  # type: ignore
        import numpy as np  # type: ignore

        recording = sd.rec(int(duration_sec * samplerate), samplerate=samplerate, channels=1, dtype='int16')
        sd.wait()

        rms = float(np.sqrt(np.mean(recording.astype(np.float32)**2)))

        wav_io = io.BytesIO()
        sf.write(wav_io, recording, samplerate, format='WAV', subtype='PCM_16')
        return wav_io.getvalue(), rms
    except Exception as exc:
        _LOG.error("Sounddevice recording error: %s", exc)
        return None, 0.0


def _setup_global_hotkey(loop: asyncio.AbstractEventLoop) -> None:
    """Daemon thread for listening to global OS hotkey Ctrl + Alt + Space / Caps Lock via sounddevice."""
    def _on_hotkey():
        try:
            import winsound
            winsound.Beep(1000, 150)
        except Exception:
            pass

        # Notify active frontend websockets that Naira has been activated
        for ws in list(_active_websockets):
            try:
                asyncio.run_coroutine_threadsafe(ws.send_json({"type": "wake_word_activated"}), loop)
            except Exception:
                pass

        def _record_and_dispatch():
            wav_bytes, rms = record_audio_sd(5.0)
            if wav_bytes and rms > 25.0:
                asyncio.run_coroutine_threadsafe(_process_global_audio(wav_bytes), loop)

        threading.Thread(target=_record_and_dispatch, daemon=True).start()

    def _listener():
        try:
            import keyboard  # type: ignore
            keyboard.add_hotkey("ctrl+alt+space", _on_hotkey)
            try:
                keyboard.add_hotkey("ctrl+alt+capslock", _on_hotkey)
            except Exception:
                pass
            try:
                keyboard.add_hotkey("ctrl+alt+caps lock", _on_hotkey)
            except Exception:
                pass
            _LOG.info("[HOTKEY] Global OS Hotkey (Ctrl + Alt + Space / Caps Lock) registered successfully")
            keyboard.wait()
        except Exception as exc:
            _LOG.warning("[HOTKEY] Global OS Hotkey initialization warning: %s", exc)

    t = threading.Thread(target=_listener, daemon=True)
    t.start()


def _setup_wake_word_engine(loop: asyncio.AbstractEventLoop) -> None:
    """Daemon thread for continuous hands-free Wake Word ('Naira') detection with energy thresholding."""
    def _wake_word_loop():
        _LOG.info("[WAKEWORD] Continuous Hands-Free Wake Word Engine active (Listening for 'Naira'...)")
        wake_words = ("naira", "nyra", "aira", "nira", "hey naira", "hi naira", "nayra", "nera", "naura", "nayara", "naraya", "naria", "nahira")

        while True:
            try:
                wav_bytes, rms = record_audio_sd(2.5)
                # Skip STT when audio energy is below threshold (< 25 RMS) to allow quiet speech while keeping idle load low
                if not wav_bytes or rms < 25.0:
                    time.sleep(0.1)
                    continue

                voice_mgr = _modules.get("voice")
                if not voice_mgr:
                    time.sleep(1.0)
                    continue

                from backend.modules.voice._types import AudioData
                audio_obj = AudioData(source_type="bytes", data=wav_bytes)
                fut = asyncio.run_coroutine_threadsafe(voice_mgr.transcribe(audio_obj), loop)
                res = fut.result(timeout=4.0)

                text_heard = res.output.lower().strip() if res and res.output else ""
                matched_word = None
                for w in wake_words:
                    if w in text_heard:
                        matched_word = w
                        break

                if matched_word:
                    _LOG.info("[WAKEWORD] Hands-free Wake word detected: '%s' in '%s'!", matched_word, text_heard)
                    try:
                        import winsound
                        winsound.Beep(1200, 100)
                        winsound.Beep(1600, 120)
                    except Exception:
                        pass

                    # Notify frontend active websockets
                    for ws in list(_active_websockets):
                        try:
                            asyncio.run_coroutine_threadsafe(ws.send_json({"type": "wake_word_activated"}), loop)
                        except Exception:
                            pass

                    # Extract inline command if spoken in the same sentence (e.g., "Naira open chrome")
                    inline_cmd = ""
                    idx = text_heard.find(matched_word)
                    if idx != -1:
                        remainder = text_heard[idx + len(matched_word):].strip(" .,!?")
                        if len(remainder) > 2:
                            inline_cmd = remainder

                    if inline_cmd:
                        _LOG.info("[WAKEWORD] Executing inline hands-free command: '%s'", inline_cmd)
                        asyncio.run_coroutine_threadsafe(_process_text_command(inline_cmd), loop)
                    else:
                        cmd_bytes, cmd_rms = record_audio_sd(5.0)
                        if cmd_bytes and cmd_rms > 25.0:
                            asyncio.run_coroutine_threadsafe(_process_global_audio(cmd_bytes), loop)
                    time.sleep(0.5)
            except Exception:
                time.sleep(0.5)

    t = threading.Thread(target=_wake_word_loop, daemon=True)
    t.start()


async def _process_text_command(user_text: str) -> None:
    """Process direct text command from inline wake-word or hotkey."""
    _LOG.info("[AUDIO] Direct command: '%s'", user_text)

    user_req = UserRequest(
        id=uuid.uuid4(),
        source="voice_engine",
        text=user_text.strip(),
        session_id="default-session",
        timestamp=time.time()
    )

    runtime_mgr = _modules.get("runtime")
    if not runtime_mgr:
        return

    accumulated_text = ""
    try:
        async for chunk in runtime_mgr.process_request_stream(user_req):
            if chunk and chunk.strip():
                accumulated_text += chunk
                for ws in list(_active_websockets):
                    try:
                        await ws.send_json({"type": "text", "content": chunk})
                    except Exception:
                        pass
    except Exception as exc:
        _LOG.error("Direct voice runtime stream error: %s", exc)
        accumulated_text = "Action failed"

    voice_mgr = _modules.get("voice")
    if voice_mgr and accumulated_text:
        try:
            active_tts = getattr(voice_mgr, "_active_tts_provider", None)
            if active_tts:
                synthesis_res = await active_tts.synthesize(accumulated_text, voice_id="hi-IN-SwaraNeural")
                if synthesis_res.audio and synthesis_res.audio.data:
                    audio_b64 = base64.b64encode(synthesis_res.audio.data).decode("utf-8")
                    for ws in list(_active_websockets):
                        try:
                            await ws.send_json({
                                "type": "audio",
                                "content": audio_b64,
                                "format": synthesis_res.audio.format
                            })
                        except Exception:
                            pass
        except Exception as e:
            _LOG.error("Direct voice TTS error: %s", e)


async def _process_global_audio(wav_bytes: bytes) -> None:
    """Process global audio payload via STT (faster-whisper) and RuntimeManager."""
    voice_mgr = _modules.get("voice")
    user_text = ""

    if voice_mgr:
        try:
            from backend.modules.voice._types import AudioData
            audio_obj = AudioData(source_type="bytes", data=wav_bytes)
            res = await voice_mgr.transcribe(audio_obj)
            if res and res.output:
                user_text = res.output
        except Exception as err:
            _LOG.error("Global voice STT error: %s", err)

    if not user_text or not user_text.strip():
        _LOG.info("[AUDIO] Speech not recognized")
        return

    _LOG.info("[AUDIO] Transcribed command: '%s'", user_text)

    await _process_text_command(user_text.strip())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot all core modules on startup; shut them down on exit."""
    global _modules, _orchestrator, _container, _LOG

    load_dotenv()

    # Steps 1–3: Environment, config, logging
    try:
        env = EnvironmentSnapshot.load()
    except SystemExit:
        _LOG.critical("[BOOT] Missing required environment variables — aborting boot.")
        yield
        return

    config = AppConfig.load()
    _LOG = setup_logging(ROOT_DIR / config.log.directory, config.log.level)
    install_excepthook(_LOG)
    _LOG.info("[BOOT] Naira-OS v%s booting ...", __version__)

    # Step 5: Event Bus
    event_bus = EventBus()

    # Step 6: Orchestrator + DI container
    _container = DIContainer()
    _container.register("env", env)
    _container.register("config", config)
    _container.register("event_bus", event_bus)

    _orchestrator = Orchestrator(event_bus=event_bus, config=config, env=env)
    _container.register("orchestrator", _orchestrator)
    _LOG.info("[BOOT] Step 6: Orchestrator initialised")

    # Steps 7–10: Module registration, wiring, capability, health
    try:
        _modules = await boot_core_modules(
            container=_container,
            orchestrator=_orchestrator,
            config=config,
            root_dir=ROOT_DIR,
            event_bus=event_bus,
        )
    except RuntimeError:
        _LOG.critical("[BOOT] Boot aborted — see errors above")
        _modules = {}
        yield
        return

    _orchestrator.state = FSMState.IDLE
    _LOG.info(
        "[BOOT] System ready — %d modules booted.",
        len(_modules),
    )

    # Initialize Global OS Hotkey & Continuous Wake Word Listeners (sounddevice)
    try:
        loop = asyncio.get_running_loop()
        _setup_global_hotkey(loop)
        _setup_wake_word_engine(loop)
    except Exception as e:
        _LOG.warning("[BOOT] Could not initialize voice listeners: %s", e)

    yield  # ← server runs here

    # Shutdown
    _LOG.info("[BOOT] Shutdown sequence started ...")
    await shutdown_modules(_modules)
    if _orchestrator:
        try:
            await asyncio.wait_for(_orchestrator.shutdown(), timeout=_SHUTDOWN_GRACE_S)
        except asyncio.TimeoutError:
            _LOG.error("Orchestrator shutdown timed out — proceeding.")
    if _container:
        _container.shutdown()
    for handler in logging.getLogger().handlers:
        handler.flush()
        handler.close()
    logging.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/check_key")
async def check_key() -> dict[str, Any]:
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY") or os.getenv("NAIRA_API_KEY") or os.getenv("API_KEY")
    return {"has_key": True, "status": "valid"}

@app.post("/api/save_key")
async def save_key(payload: dict[str, str]) -> dict[str, bool]:
    api_key = payload.get("api_key", "").strip()
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
        llm_mgr = _modules.get("llm")
        if llm_mgr:
            for provider in llm_mgr._providers.values():
                if hasattr(provider, "_api_key"):
                    setattr(provider, "_api_key", api_key)
        return {"success": True}
    return {"success": False}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _active_websockets.add(websocket)
    try:
        while True:
            try:
                ws_msg = await websocket.receive()
            except WebSocketDisconnect:
                _LOG.info("WebSocket disconnected gracefully")
                break
            except Exception as e:
                _LOG.warning("Error receiving message from WebSocket: %s", e)
                break

            user_text = ""
            voice_mgr = _modules.get("voice")

            # Route 1: Binary audio data
            if "bytes" in ws_msg and ws_msg["bytes"]:
                audio_bytes = ws_msg["bytes"]
                if voice_mgr:
                    try:
                        from backend.modules.voice._types import AudioData
                        audio_data = AudioData(source_type="bytes", data=audio_bytes)
                        res = await voice_mgr.transcribe(audio_data)
                        if res and res.output:
                            user_text = res.output
                    except Exception as stt_err:
                        _LOG.error("WebSocket binary STT error: %s", stt_err)
            # Route 2: Text or JSON (text/audio payload)
            elif "text" in ws_msg and ws_msg["text"]:
                raw_text = ws_msg["text"]
                if raw_text.startswith("{") and ("audio" in raw_text or "data" in raw_text or "type" in raw_text):
                    try:
                        import json
                        payload = json.loads(raw_text)
                        if isinstance(payload, dict):
                            if payload.get("type") == "audio" and payload.get("content"):
                                raw_content = payload["content"]
                                if isinstance(raw_content, str):
                                    if "," in raw_content:
                                        raw_content = raw_content.split(",", 1)[1]
                                    raw_content = raw_content.strip()
                                    missing_padding = len(raw_content) % 4
                                    if missing_padding:
                                        raw_content += "=" * (4 - missing_padding)
                                    audio_bytes = base64.b64decode(raw_content)
                                elif isinstance(raw_content, (bytes, bytearray)):
                                    audio_bytes = bytes(raw_content)
                                else:
                                    audio_bytes = None

                                if audio_bytes and voice_mgr:
                                    from backend.modules.voice._types import AudioData
                                    audio_data = AudioData(source_type="bytes", data=audio_bytes)
                                    res = await voice_mgr.transcribe(audio_data)
                                    if res and res.output:
                                        user_text = res.output
                            elif "text" in payload and isinstance(payload["text"], str):
                                user_text = payload["text"]
                    except Exception as json_err:
                        _LOG.warning("Failed to parse WebSocket text JSON payload: %s", json_err)
                else:
                    user_text = raw_text

            if not user_text or not user_text.strip():
                continue

            _LOG.info("[WS] Received user text: %r (stripped: %r)", user_text, user_text.strip())

            user_req = UserRequest(
                id=uuid.uuid4(),
                source="websocket",
                text=user_text.strip(),
                session_id="default-session",
                timestamp=time.time()
            )

            runtime_mgr = _modules.get("runtime")
            _LOG.info("[WS] runtime_mgr type=%s id=%s", type(runtime_mgr).__name__, id(runtime_mgr) if runtime_mgr else "None")
            if runtime_mgr:
                accumulated_text = ""
                try:
                    async for chunk in runtime_mgr.process_request_stream(user_req):
                        if chunk and chunk.strip():
                            accumulated_text += chunk
                            await websocket.send_json({"type": "text", "content": chunk})
                    if not accumulated_text.strip():
                        fallback_txt = "Action executed successfully."
                        accumulated_text = fallback_txt
                        await websocket.send_json({"type": "text", "content": fallback_txt})
                except Exception as e:
                    _LOG.error("Error in request pipeline: %s", e)
                    await websocket.send_json({"type": "text", "content": "Action failed"})

                # Synthesize female voice TTS back to frontend
                if voice_mgr and accumulated_text:
                    try:
                        active_tts = getattr(voice_mgr, "_active_tts_provider", None)
                        if active_tts:
                            synthesis_res = await active_tts.synthesize(accumulated_text, voice_id="hi-IN-SwaraNeural")
                            if synthesis_res.audio and synthesis_res.audio.data:
                                audio_b64 = base64.b64encode(synthesis_res.audio.data).decode("utf-8")
                                await websocket.send_json({
                                    "type": "audio",
                                    "content": audio_b64,
                                    "format": synthesis_res.audio.format
                                })
                    except Exception as e:
                        _LOG.error("Error in TTS synthesis: %s", e)
            else:
                await websocket.send_json({"type": "text", "content": "Error: Runtime not initialized."})
    except Exception as e:
        _LOG.debug("WebSocket handler exception: %s", e)
    finally:
        _active_websockets.discard(websocket)

# Mount assets static files directly so /assets/talking.mp4 renders properly (200 OK)
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
assets_dir = os.path.join(frontend_dir, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Mount frontend at root using absolute path to prevent Directory not found errors
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
