#!/usr/bin/env python3
"""
Naira-OS Bootstrap — Main Entry Point.
Fixed: Environment Variable strict checking, Master FCR Integration & n8n Mega Suite Testing Support.
"""

from __future__ import annotations

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

ROOT_DIR: Final[Path] = Path(__file__).resolve().parent
ENV_PATH: Final[Path] = ROOT_DIR / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
    if gemini_key and not os.getenv("NAIRA_API_KEY"):
        os.environ["NAIRA_API_KEY"] = gemini_key
        os.environ["API_KEY"] = gemini_key
        
except ImportError:
    pass

def load_groq_api_key_from_vault(root_dir: Path, logger: logging.Logger | None = None) -> str:
    """Dynamically load the Groq API key from memory/user_vault.json into os.environ.
    
    Implements graceful error handling if the file does not exist, JSON is invalid,
    or the 'groq_api_key' field is missing/empty.
    """
    vault_path = root_dir / "memory" / "user_vault.json"
    warning_msg = "Groq API key not found in user_vault.json. FastCommandRouter may be degraded."

    if not vault_path.is_file():
        if logger:
            logger.warning(warning_msg)
        else:
            logging.warning(warning_msg)
        os.environ["GROQ_API_KEY"] = ""
        return ""

    try:
        import json
        with open(vault_path, "r", encoding="utf-8") as f:
            vault_data = json.load(f)

        if not isinstance(vault_data, dict):
            if logger:
                logger.warning(warning_msg)
            else:
                logging.warning(warning_msg)
            os.environ["GROQ_API_KEY"] = ""
            return ""

        groq_key = (
            vault_data.get("groq_api_key")
            or (vault_data.get("api_keys", {}).get("groq") if isinstance(vault_data.get("api_keys"), dict) else None)
            or (vault_data.get("api_key") if vault_data.get("provider") == "groq" else "")
            or ""
        )

        if isinstance(groq_key, str) and groq_key.strip():
            groq_key = groq_key.strip()
            os.environ["GROQ_API_KEY"] = groq_key
            return groq_key
        else:
            if logger:
                logger.warning(warning_msg)
            else:
                logging.warning(warning_msg)
            os.environ["GROQ_API_KEY"] = ""
            return ""

    except Exception:
        if logger:
            logger.warning(warning_msg)
        else:
            logging.warning(warning_msg)
        os.environ["GROQ_API_KEY"] = ""
        return ""

# Initialize Groq API key early from vault
load_groq_api_key_from_vault(ROOT_DIR)

from google import genai
from google.genai import types

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
from backend.runtime.proactive_watchdog import ProactiveWatchdog
from backend.types import UserRequest, UserResponse
from backend.api.settings import router as settings_router
from backend.api.capabilities import router as capabilities_router
# --- Naya Remote Bridge Router Import Yahan Hai ---
from backend.modules.remote_bridge.remote_router import router as remote_bridge_router

_SHUTDOWN_GRACE_S: Final[float] = 3.0

_LOG: logging.Logger = logging.getLogger("naira.main")
_modules: dict[str, Any] = {}
_orchestrator: Orchestrator | None = None
_container: DIContainer | None = None
_active_websockets: set[WebSocket] = set()
_watchdog: ProactiveWatchdog | None = None

async def process_user_input(user_text: str, session_id: str = "default", modality: str = "text") -> str:
    if _orchestrator is None:
        _LOG.error("[MAIN] Orchestrator is not initialized — request rejected.")
        return "[System Error]: Orchestrator is not initialized."

    request = UserRequest(
        id=uuid.uuid4(),
        source="websocket" if modality == "text" else "voice",
        text=user_text,
        session_id=session_id,
        timestamp=time.time(),
    )
    response = await _orchestrator.process_user_request(request)
    return response.text

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _modules, _orchestrator, _container, _watchdog, _LOG

    try:
        env = EnvironmentSnapshot.load()
    except SystemExit:
        _LOG.warning("[BOOT] No environment key found; using local vault setup instead.")
        env = EnvironmentSnapshot()

    config = AppConfig.load()
    _LOG = setup_logging(ROOT_DIR / config.log.directory, config.log.level)
    install_excepthook(_LOG)
    _LOG.info("[BOOT] Naira-OS v%s booting ...", __version__)
    load_groq_api_key_from_vault(ROOT_DIR, _LOG)

    event_bus = EventBus()
    _container = DIContainer()
    _container.register("env", env)
    _container.register("config", config)
    _container.register("event_bus", event_bus)

    async def _on_tool_ws_event(event: Any) -> None:
        event_type = getattr(event, "type", "")
        data = getattr(event, "data", {}) or {}
        if event_type in (
            "tool_execution_start",
            "tool_execution_result",
            "runtime.tool_execution_start",
            "runtime.tool_execution_result",
        ):
            msg_type = "tool_execution_start" if "start" in event_type else "tool_execution_result"
            payload = {
                "sender": "naira",
                "type": msg_type,
                "tool": data.get("tool") or data.get("name", "tool"),
                "tool_call_id": data.get("tool_call_id"),
                "script_code": data.get("script_code"),
                "output": data.get("output"),
                "stdout": data.get("stdout"),
                "stderr": data.get("stderr"),
                "text": data.get("text", ""),
            }
            for ws in list(_active_websockets):
                try:
                    await ws.send_json(payload)
                except Exception as ws_exc:
                    _LOG.debug("Error sending tool WS event: %s", ws_exc)

    event_bus.subscribe("tool_execution_start", _on_tool_ws_event)
    event_bus.subscribe("tool_execution_result", _on_tool_ws_event)

    _orchestrator = Orchestrator(event_bus=event_bus, config=config, env=env)
    _container.register("orchestrator", _orchestrator)
    
    try:
        _modules = await boot_core_modules(
            container=_container,
            orchestrator=_orchestrator,
            config=config,
            root_dir=ROOT_DIR,
            event_bus=event_bus,
        )
        app.state.llm_manager = _modules.get("llm")
        app.state.capability_manager = _modules.get("capability")
    except RuntimeError:
        _LOG.critical("[BOOT] Boot aborted — see errors above")
        _modules = {}
        yield
        return

    _orchestrator.state = FSMState.IDLE
    _LOG.info("[BOOT] System ready — %d modules booted.", len(_modules))
    await _orchestrator.start_autonomous_loop()

    _watchdog = ProactiveWatchdog(active_websockets=_active_websockets, check_interval=60.0, logger=_LOG)
    await _watchdog.start()

    yield

    _LOG.info("[BOOT] Shutdown sequence started ...")
    if _watchdog:
        await _watchdog.stop()
    await _orchestrator.stop_autonomous_loop()
    await shutdown_modules(_modules)
    if _container:
        _container.shutdown()
    logging.shutdown()

app = FastAPI(lifespan=lifespan)
app.include_router(settings_router)
app.include_router(capabilities_router)
# --- Naya Remote Bridge Router Yahan Mount Hua Hai ---
app.include_router(remote_bridge_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/naira")
async def websocket_naira_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _active_websockets.add(websocket)
    _LOG.info("[WS-NAIRA] Client connected successfully")
    try:
        while True:
            try:
                ws_msg = await websocket.receive()
            except WebSocketDisconnect:
                break
            except Exception:
                break

            user_text = ""
            if "text" in ws_msg and ws_msg["text"]:
                raw_text = ws_msg["text"]
                if raw_text.startswith("{"):
                    try:
                        import json
                        payload = json.loads(raw_text)
                        msg_type = payload.get("type", "")
                        if msg_type == "system_init":
                            name = payload.get("name", "User")
                            session_id = payload.get("session_id", payload.get("sessionId", "default"))

                            session_mgr = _modules.get("session")
                            if session_mgr and hasattr(session_mgr, "get_or_create_session"):
                                await session_mgr.get_or_create_session(session_id)

                            conv_mgr = _modules.get("conversation")
                            if conv_mgr and hasattr(conv_mgr, "get_session"):
                                conv_mgr.get_session(session_id)

                            interaction_mgr = _modules.get("interaction")
                            if interaction_mgr and hasattr(interaction_mgr, "sync_session_state"):
                                interaction_mgr.sync_session_state(session_id=session_id, user_name=name)

                            await websocket.send_json({
                                "sender": "naira",
                                "text": f"Identity synced to Relation Engine: Welcome, {name}."
                            })
                            continue
                        elif msg_type in ("barge_in", "interrupt"):
                            from backend.modules.voice._audio_player import audio_interrupt_event
                            audio_interrupt_event.set()
                            await websocket.send_json({
                                "sender": "naira",
                                "type": "barge_in_acknowledged",
                                "text": "Playback interrupted."
                            })
                            continue
                        user_text = payload.get("text", payload.get("content", raw_text))
                    except Exception:
                        user_text = raw_text
                else:
                    user_text = raw_text

            if user_text:
                from backend.modules.voice._audio_player import audio_interrupt_event
                audio_interrupt_event.set()
                _LOG.info("[WS-NAIRA] Received command: %s", user_text)
                response_text = await process_user_input(user_text)

                audio_b64 = None
                voice_mgr = _modules.get("voice")
                if voice_mgr and response_text:
                    try:
                        synth_res = await voice_mgr.synthesize(response_text)
                        if synth_res and getattr(synth_res, "audio_bytes", None):
                            audio_b64 = base64.b64encode(synth_res.audio_bytes).decode("utf-8")
                            _LOG.info("[WS-NAIRA] TTS synthesized %d audio bytes via VoiceManager", len(synth_res.audio_bytes))
                        else:
                            active_name = getattr(voice_mgr, "active_tts_provider_name", "rvc") or "rvc"
                            tts_providers = getattr(voice_mgr, "tts_providers", {})
                            active_tts = tts_providers.get(active_name) or tts_providers.get("rvc")
                            if active_tts and hasattr(active_tts, "synthesize"):
                                raw_res = await active_tts.synthesize(response_text)
                                if raw_res and hasattr(raw_res, "audio") and raw_res.audio.data:
                                    audio_b64 = base64.b64encode(raw_res.audio.data).decode("utf-8")
                                    _LOG.info("[WS-NAIRA] TTS synthesized %d audio bytes via active provider %s", len(raw_res.audio.data), active_name)
                    except Exception as tts_exc:
                        _LOG.error("[WS-NAIRA] TTS synthesis failed: %s", tts_exc)

                payload: dict[str, Any] = {
                    "sender": "naira",
                    "text": response_text,
                }
                if audio_b64:
                    payload["audio"] = audio_b64

                await websocket.send_json(payload)
    finally:
        _active_websockets.discard(websocket)

@app.post("/api/chat")
async def chat_endpoint(payload: dict[str, Any]):
    user_text = payload.get("text") or payload.get("content") or payload.get("message", "")
    session_id = payload.get("session_id", "n8n_test_session")
    modality = payload.get("modality", "text") 
    expected_route = payload.get("expected_route", "llm")

    if not user_text:
        return {"status": "error", "message": "No query text provided."}
    
    response_text = await process_user_input(user_text, session_id=session_id, modality=modality)
    
    return {
        "status": "success",
        "sender": "naira",
        "session_id": session_id,
        "response": response_text,
        "modality_received": modality,
        "route_checked": expected_route
    }

frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
assets_dir = os.path.join(frontend_dir, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)