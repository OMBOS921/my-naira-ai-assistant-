#!/usr/bin/env python3
"""
Naira-OS CLI Entrypoint — Interactive Terminal Loop.

Initializes the Naira-OS core orchestrator and runtime pipeline, and provides
a direct local terminal interface for chat & control interactions.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Final

ROOT_DIR: Final[Path] = Path(__file__).resolve().parent
ENV_PATH: Final[Path] = ROOT_DIR / ".env"

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
    if gemini_key and not os.getenv("NAIRA_API_KEY"):
        os.environ["NAIRA_API_KEY"] = gemini_key
        os.environ["API_KEY"] = gemini_key
except ImportError:
    pass

from backend import __version__
from backend.boot import boot_core_modules, shutdown_modules
from backend.eventbus import EventBus
from backend.modules.settings import AppConfig, EnvironmentSnapshot
from backend.modules.utils.di import DIContainer
from backend.modules.utils.log import install_excepthook, setup_logging
from backend.orchestrator import FSMState, Orchestrator
from backend.runtime.proactive_watchdog import ProactiveWatchdog
from backend.types import UserRequest, UserResponse
async def run_cli_loop() -> None:
    """Initialize Naira-OS engine and execute interactive CLI loop."""
    try:
        env = EnvironmentSnapshot.load()
    except SystemExit:
        print("[FATAL] Missing required environment variables. Please check your .env configuration.")
        return

    config = AppConfig.load()
    logger = setup_logging(ROOT_DIR / config.log.directory, config.log.level)
    install_excepthook(logger)
    logger.info("[CLI] Naira-OS v%s booting in CLI mode...", __version__)

    event_bus = EventBus()
    container = DIContainer()
    container.register("env", env)
    container.register("config", config)
    container.register("event_bus", event_bus)

    orchestrator = Orchestrator(event_bus=event_bus, config=config, env=env)
    container.register("orchestrator", orchestrator)

    modules = {}
    try:
        modules = await boot_core_modules(
            container=container,
            orchestrator=orchestrator,
            config=config,
            root_dir=ROOT_DIR,
            event_bus=event_bus,
        )
    except Exception as exc:
        logger.critical("[CLI] Core module boot failed: %s", exc)
        container.shutdown()
        return

    orchestrator.state = FSMState.IDLE
    logger.info("[CLI] System initialized — %d modules booted successfully.", len(modules))

    await orchestrator.start_autonomous_loop()

    watchdog = ProactiveWatchdog(check_interval=60.0, logger=logger)
    await watchdog.start()

    print("\n" + "=" * 60)
    print(f"      Naira-OS v{__version__} CLI Terminal Interface")
    print("=" * 60)
    print("Type 'exit' or 'quit' to terminate the CLI session.\n")

    session_id = f"cli_{uuid.uuid4().hex[:8]}"

    try:
        while True:
            try:
                user_text = await asyncio.to_thread(input, "You: ")
            except (EOFError, KeyboardInterrupt):
                print("\n[CLI] Exit signal received.")
                break

            user_text = user_text.strip()
            if not user_text:
                continue

            if user_text.lower() in ("exit", "quit"):
                print("[CLI] Exiting Naira-OS Terminal...")
                break

            request = UserRequest(
                id=uuid.uuid4(),
                source="cli",
                text=user_text,
                session_id=session_id,
                timestamp=time.time(),
            )

            try:
                response = await orchestrator.process_user_request(request)
                print(f"\nNaira: {response.text}\n")
            except Exception as exc:
                logger.error("[CLI] Request processing error: %s", exc)
                print(f"\nNaira: [System Error]: {exc}\n")

    finally:
        print("[CLI] Initiating shutdown sequence...")
        await watchdog.stop()
        await orchestrator.stop_autonomous_loop()
        await shutdown_modules(modules)
        container.shutdown()
        logging.shutdown()
        print("[CLI] Shutdown complete. Goodbye!")


def main() -> None:
    """CLI Entrypoint launcher."""
    try:
        asyncio.run(run_cli_loop())
    except KeyboardInterrupt:
        print("\n[CLI] Interrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
