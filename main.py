#!/usr/bin/env python3
"""
Naira-OS Bootstrap — Main Entry Point.
Fixed: Environment Variable strict checking & Master FCR Integration.
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

# =====================================================================
# 1. SMART ENV LOADER (The Fix for Boot Crash)
# =====================================================================
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    
    # Map Gemini keys to satisfy Naira's strict EnvironmentSnapshot
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
    if gemini_key and not os.getenv("NAIRA_API_KEY"):
        os.environ["NAIRA_API_KEY"] = gemini_key
        os.environ["API_KEY"] = gemini_key
except ImportError:
    pass

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
from backend.types import UserRequest, UserResponse

_SHUTDOWN_GRACE_S: Final[float] = 3.0

_LOG: logging.Logger = logging.getLogger("naira.main")
_modules: dict[str, Any] = {}
_orchestrator: Orchestrator | None = None
_container: DIContainer | None = None
_active_websockets: set[WebSocket] = set()

# =====================================================================
# 2. CORE REQUEST ROUTER (Clean Architecture Entry Point)
# =====================================================================
async def process_user_input(user_text: str, session_id: str = "default") -> str:
    """Route input through the central Orchestrator mediator and Runtime pipeline."""
    if _orchestrator is None:
        _LOG.error("[MAIN] Orchestrator is not initialized — request rejected.")
        return "[System Error]: Orchestrator is not initialized."

    request = UserRequest(
        id=uuid.uuid4(),
        source="websocket",
        text=user_text,
        session_id=session_id,
        timestamp=time.time(),
    )
    response = await _orchestrator.process_user_request(request)
    return response.text

# =====================================================================
# 3. FASTAPI SERVER SETUP
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Boot all core modules on startup; shut them down on exit."""
    global _modules, _orchestrator, _container, _LOG

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

    event_bus = EventBus()
    _container = DIContainer()
    _container.register("env", env)
    _container.register("config", config)
    _container.register("event_bus", event_bus)

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
    except RuntimeError:
        _LOG.critical("[BOOT] Boot aborted — see errors above")
        _modules = {}
        yield
        return

    _orchestrator.state = FSMState.IDLE
    _LOG.info("[BOOT] System ready — %d modules booted.", len(_modules))

    yield  # server runs here

    _LOG.info("[BOOT] Shutdown sequence started ...")
    await shutdown_modules(_modules)
    if _container:
        _container.shutdown()
    logging.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/naira")
async def websocket_naira_endpoint(websocket: WebSocket) -> None:
    """Real-time bi-directional WebSocket endpoint for Naira chat & control."""
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
                            await websocket.send_json({
                                "sender": "naira",
                                "text": f"Identity synced to Relation Engine: Welcome, {name}."
                            })
                            continue
                        user_text = payload.get("text", payload.get("content", raw_text))
                    except Exception:
                        user_text = raw_text
                else:
                    user_text = raw_text

            if user_text:
                _LOG.info("[WS-NAIRA] Received command: %s", user_text)
                response_text = await process_user_input(user_text)
                await websocket.send_json({
                    "sender": "naira",
                    "text": response_text
                })
    finally:
        _active_websockets.discard(websocket)

# Serve Frontend
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
assets_dir = os.path.join(frontend_dir, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)