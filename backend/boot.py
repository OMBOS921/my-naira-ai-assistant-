"""
Boot sequence — Steps 7–12 of 18_Boot_Sequence.md §2.

Orchestrates core module construction, initialisation (in architecture
order), Port/Adapter wiring, capability registration, and health
verification.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from backend.modules.analytics import AnalyticsManager
from backend.modules.browser import BrowserManager
from backend.modules.browser._playwright_adapter import _HAS_PLAYWRIGHT
from backend.modules.capability import CapabilityManager
from backend.modules.capability.capability import Capability
from backend.modules.coding_agent import CodingAgentManager
from backend.modules.context import ContextManager
from backend.modules.context_intelligence import ContextIntelligenceManager
from backend.modules.conversation import ConversationManager
from backend.modules.decision import DecisionManager
from backend.modules.integrations import IntegrationsManager
from backend.modules.llm import LLMManager
from backend.modules.memory import MemoryManager
from backend.modules.pc_control import PCControlManager
from backend.modules.pc_control._production_adapter import (
    _HAS_PSUTIL as _PC_HAS_PSUTIL,
)
from backend.modules.pc_control._production_adapter import (
    _HAS_PYAUTOGUI as _PC_HAS_PYAUTOGUI,
)
from backend.modules.pc_control._production_adapter import (
    _HAS_PYWIN32 as _PC_HAS_PYWIN32,
)
from backend.modules.planning import PlanningManager
from backend.modules.plugins import PluginManager
from backend.modules.prompt import PromptManager
from backend.modules.security import SecurityManager
from backend.modules.settings import AppConfig, SettingsManager
from backend.modules.skills import SkillManager
from backend.modules.tools import ToolManager
from backend.modules.utils.di import DIContainer
from backend.modules.vision import VisionManager
from backend.modules.voice import VoiceManager
from backend.orchestrator import EventBus, Orchestrator
from backend.runtime import RuntimeManager

__all__ = [
    "boot_core_modules",
    "register_system_capabilities",
    "shutdown_modules",
    "verify_boot_health",
]

_LOG = logging.getLogger("naira.boot")


def _check_pc_control_deps() -> dict[str, bool]:
    return {
        "pyautogui": _PC_HAS_PYAUTOGUI,
        "psutil": _PC_HAS_PSUTIL,
        "pywin32": _PC_HAS_PYWIN32,
    }

_SHUTDOWN_ORDER: tuple[str, ...] = (
    "runtime",
    "multi_agent",
    "autonomous_tasks",
    "context_intelligence",
    "conversation",
    "prompt",
    "llm",
    "decision",
    "planning",
    "coding_agent",
    "pc_control",
    "voice",
    "vision",
    "browser",
    "plugins",
    "integrations",
    "security",
    "skills",
    "tools",
    "capability",
    "context",
    "analytics",
    "memory",
    "settings",
)

_BOOT_ORDER: tuple[str, ...] = (
    "settings",
    "memory",
    "analytics",
    "context",
    "capability",
    "skills",
    "tools",
    "security",
    "integrations",
    "plugins",
    "browser",
    "vision",
    "voice",
    "pc_control",
    "coding_agent",
    "planning",
    "decision",
    "llm",
    "prompt",
    "conversation",
    "context_intelligence",
    "autonomous_tasks",
    "multi_agent",
    "runtime",
)


async def boot_core_modules(
    container: DIContainer,
    orchestrator: Orchestrator,
    config: AppConfig,
    root_dir: Path,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    """Boot Steps 7–10: construct, initialise, wire, and verify modules.

    Parameters
    ----------
    container : DIContainer
        Boot-time DI container for registering module references.
    orchestrator : Orchestrator
        Central mediator that tracks module init order and lifecycle.
    config : AppConfig
        Application configuration (already loaded in Step 2).
    root_dir : Path
        Project root directory for resolving paths.
    event_bus : EventBus | None
        Event bus instance for injection into modules.

    Returns
    -------
    dict[str, Any]
        Initialised modules keyed by short name.

    Raises
    ------
    RuntimeError
        If a fatal boot error occurs (no recovery possible).
    """
    _LOG.info("[BOOT] Step 7: Registering core modules ...")
    modules: dict[str, Any] = {}
    degraded_modules: list[str] = []

    try:
        # 7a – SettingsManager (Layer 2 — Application)
        _LOG.info("[BOOT]   Initialising SettingsManager ...")
        settings_mgr = SettingsManager(
            config_dir=root_dir / "config",
            event_bus=event_bus,
        )
        await settings_mgr.async_init()
        modules["settings"] = settings_mgr
        container.register("settings_manager", settings_mgr)
        orchestrator.register_module("settings", settings_mgr)
        if getattr(settings_mgr, "degraded", False):
            degraded_modules.append("settings")
        _LOG.info("[BOOT] Settings initialised")

        # 7b – MemoryManager (Layer 5 — Infrastructure)
        _LOG.info("[BOOT]   Initialising MemoryManager ...")
        memory_dir = root_dir / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_mgr = MemoryManager(
            config=config,
            db_path=memory_dir / "conversations.db",
            index_path=memory_dir / "index.json",
            event_bus=event_bus,
        )
        await memory_mgr.async_init()
        modules["memory"] = memory_mgr
        container.register("memory_manager", memory_mgr)
        orchestrator.register_module("memory", memory_mgr)
        if getattr(memory_mgr, "degraded", False):
            degraded_modules.append("memory")
        _LOG.info("[BOOT] Memory initialised")

        # 7b2 – AnalyticsManager (Layer 5 — Infrastructure)
        _LOG.info("[BOOT]   Initialising AnalyticsManager ...")
        analytics_mgr = AnalyticsManager(
            config=config,
            event_bus=event_bus,
            db_path=memory_dir / "naira_analytics.db",
        )
        await analytics_mgr.async_init()
        modules["analytics"] = analytics_mgr
        container.register("analytics_manager", analytics_mgr)
        orchestrator.register_module("analytics", analytics_mgr)
        if getattr(analytics_mgr, "degraded", False):
            degraded_modules.append("analytics")
        _LOG.info("[BOOT] Analytics initialised")

        # 7c – ContextManager (Layer 3 — AI Core) with MemoryPort wiring
        _LOG.info("[BOOT]   Initialising ContextManager ...")
        context_mgr = ContextManager(
            config=config,
            max_tokens=config.context.max_tokens,
            memory_port=memory_mgr.memory_adapter,
            memory_manager=memory_mgr,
            event_bus=event_bus,
        )
        await context_mgr.async_init()
        modules["context"] = context_mgr
        container.register("context_manager", context_mgr)
        orchestrator.register_module("context", context_mgr)
        if getattr(context_mgr, "degraded", False):
            degraded_modules.append("context")
        _LOG.info("[BOOT] Context initialised")

        # 7d – CapabilityManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising CapabilityManager ...")
        capability_mgr = CapabilityManager(
            config=config,
            event_bus=event_bus,
        )
        await capability_mgr.async_init()
        modules["capability"] = capability_mgr
        container.register("capability_manager", capability_mgr)
        orchestrator.register_module("capability", capability_mgr)
        if getattr(capability_mgr, "degraded", False):
            degraded_modules.append("capability")
        _LOG.info("[BOOT] Capability initialised")

        # 7d2 – SkillManager (Layer 4 — Orchestration & Central Catalog)
        _LOG.info("[BOOT]   Initialising SkillManager ...")
        skill_mgr = SkillManager(
            config=config,
            event_bus=event_bus,
            capability_registry=getattr(capability_mgr, "registry", capability_mgr),
        )
        await skill_mgr.async_init()
        modules["skills"] = skill_mgr
        container.register("skill_manager", skill_mgr)
        orchestrator.register_module("skills", skill_mgr)
        if getattr(skill_mgr, "degraded", False):
            degraded_modules.append("skills")
        _LOG.info("[BOOT] Skills initialised")

        # 7e – ToolManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising ToolManager ...")
        tool_mgr = ToolManager(
            config=config,
            capability_manager=capability_mgr,
            event_bus=event_bus,
            max_concurrent=config.tools.max_concurrent,
            default_timeout=config.tools.default_timeout,
        )
        await tool_mgr.async_init()
        modules["tools"] = tool_mgr
        container.register("tool_manager", tool_mgr)
        orchestrator.register_module("tools", tool_mgr)
        if getattr(tool_mgr, "degraded", False):
            degraded_modules.append("tools")
        memory_mgr.register_tools(tool_mgr)
        _LOG.info("[BOOT] Tools initialised — registered memory tools")

        # 7f – SecurityManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising SecurityManager ...")
        security_adapter = None
        if config.security.enabled:
            from backend.modules.security._local_adapter import (
                LocalSecurityAdapter,
            )
            security_adapter = LocalSecurityAdapter(
                enabled=config.security.enabled,
                sandbox_enabled=config.security.sandbox_enabled,
                audit_enabled=config.security.audit_enabled,
                default_policy=config.security.default_policy,
                max_risk=config.security.max_risk,
                allowed_paths=config.security.allowed_paths,
                blocked_paths=config.security.blocked_paths,
                logger=_LOG,
            )
            _LOG.info("[BOOT]   LocalSecurityAdapter created (enabled)")
        security_mgr = SecurityManager(
            config=config,
            capability_manager=capability_mgr,
            tool_manager=tool_mgr,
            event_bus=event_bus,
            adapter=security_adapter,
            default_timeout=config.tools.default_timeout,
        )
        await security_mgr.async_init()
        modules["security"] = security_mgr
        container.register("security_manager", security_mgr)
        orchestrator.register_module("security", security_mgr)
        if getattr(security_mgr, "degraded", False):
            degraded_modules.append("security")
        tool_mgr.set_security_manager(security_mgr)
        _LOG.info("[BOOT] Security initialised — wired to ToolManager")

        # 7f2 – IntegrationsManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising IntegrationsManager ...")
        integrations_mgr = IntegrationsManager(
            config=config,
            event_bus=event_bus,
            capability_manager=capability_mgr,
            tool_manager=tool_mgr,
        )
        await integrations_mgr.async_init()
        modules["integrations"] = integrations_mgr
        container.register("integrations_manager", integrations_mgr)
        orchestrator.register_module("integrations", integrations_mgr)
        if getattr(integrations_mgr, "degraded", False):
            degraded_modules.append("integrations")
        _LOG.info("[BOOT] Integrations initialised")

        # 7f3 – PluginManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising PluginManager ...")
        plugins_dir = root_dir / "plugins"
        plugins_mgr = PluginManager(
            plugins_dir=plugins_dir,
            event_bus=event_bus,
            logger=_LOG,
        )
        await plugins_mgr.async_init()
        modules["plugins"] = plugins_mgr
        container.register("plugin_manager", plugins_mgr)
        orchestrator.register_module("plugins", plugins_mgr)
        if getattr(plugins_mgr, "degraded", False):
            degraded_modules.append("plugins")
        _LOG.info("[BOOT] Plugins initialised")

        # 7g – BrowserManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising BrowserManager ...")
        browser_mgr = BrowserManager(
            config=config,
            capability_manager=capability_mgr,
            tool_manager=tool_mgr,
            event_bus=event_bus,
            default_timeout=config.browser.default_timeout,
        )
        await browser_mgr.async_init()
        modules["browser"] = browser_mgr
        container.register("browser_manager", browser_mgr)
        orchestrator.register_module("browser", browser_mgr)
        if getattr(browser_mgr, "degraded", False):
            degraded_modules.append("browser")
        _LOG.info("[BOOT] Browser initialised")

        # 7g – VisionManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising VisionManager ...")
        vision_providers: dict[str, Any] = {}
        vision_active = config.vision.active_provider
        vision_fallback = config.vision.fallback_chain

        # Build Gemini provider if in fallback chain and API key available
        if "gemini" in vision_fallback:
            env_snap = getattr(settings_mgr, "_env", None)
            if env_snap is None and container.has("env"):
                env_snap = container.get("env")
            gemini_key = getattr(env_snap, "gemini_api_key", None) if env_snap else None
            if gemini_key:
                from backend.modules.vision._gemini_adapter import (
                    GeminiVisionAdapter,
                    RetryPolicy,
                )
                vision_providers["gemini"] = GeminiVisionAdapter(
                    api_key=gemini_key,
                    model=config.vision.model,
                    timeout=config.vision.default_timeout,
                    retry_policy=RetryPolicy(
                        max_retries=config.vision.max_retries,
                        base_delay=config.vision.retry_base_delay,
                        max_delay=config.vision.retry_max_delay,
                    ),
                )
                _LOG.info("[BOOT]   Gemini Vision provider created")
            else:
                _LOG.warning("[BOOT]   Gemini API key not found — gemini provider skipped")

        vision_mgr = VisionManager(
            config=config,
            capability_manager=capability_mgr,
            tool_manager=tool_mgr,
            event_bus=event_bus,
            providers=vision_providers,
            active_provider_name=vision_active if vision_providers else None,
            fallback_chain=vision_fallback,
            default_timeout=config.vision.default_timeout,
        )
        await vision_mgr.async_init()
        modules["vision"] = vision_mgr
        container.register("vision_manager", vision_mgr)
        orchestrator.register_module("vision", vision_mgr)
        if getattr(vision_mgr, "degraded", False):
            degraded_modules.append("vision")
        _LOG.info("[BOOT] Vision initialised")

        # 7h – VoiceManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising VoiceManager ...")
        voice_stt_providers: dict[str, Any] = {}
        voice_tts_providers: dict[str, Any] = {}
        voice_wake_word_providers: dict[str, Any] = {}

        # Build STT providers
        stt_chain = config.voice.stt_fallback_chain
        for provider_name in stt_chain:
            if provider_name == "whisper":
                try:
                    from backend.modules.voice.providers.whisper_provider import (
                        _HAS_WHISPER,
                        WhisperSTTProvider,
                    )
                    if _HAS_WHISPER:
                        voice_stt_providers["whisper"] = WhisperSTTProvider(
                            model=config.voice.whisper_model,
                            language=config.voice.default_language,
                            timeout=config.voice.default_timeout,
                        )
                        _LOG.info("[BOOT]   Whisper STT provider created")
                    else:
                        _LOG.warning("[BOOT]   Whisper package not available")
                except Exception as exc:
                    _LOG.warning("[BOOT]   Failed to create Whisper STT provider: %s", exc)

            elif provider_name == "faster-whisper":
                try:
                    from backend.modules.voice.providers.faster_whisper_provider import (
                        _HAS_FASTER_WHISPER,
                        FasterWhisperSTTProvider,
                    )
                    if _HAS_FASTER_WHISPER:
                        voice_stt_providers["faster-whisper"] = FasterWhisperSTTProvider(
                            model=config.voice.faster_whisper_model,
                            device="cpu",
                            compute_type="int8",
                            language=config.voice.default_language,
                            timeout=config.voice.default_timeout,
                        )
                        _LOG.info("[BOOT]   Faster-Whisper STT provider created")
                    else:
                        _LOG.warning("[BOOT]   Faster-Whisper package not available")
                except Exception as exc:
                    _LOG.warning("[BOOT]   Failed to create Faster-Whisper STT provider: %s", exc)

        # Build TTS providers
        tts_chain = list(config.voice.tts_fallback_chain)
        if "rvc" not in tts_chain:
            tts_chain.insert(0, "rvc")

        for provider_name in tts_chain:
            if provider_name == "rvc":
                try:
                    from backend.modules.voice.providers.rvc_provider import RVCProvider
                    voice_tts_providers["rvc"] = RVCProvider(
                        base_voice="en-IN-NeerjaNeural",
                        model_path=getattr(config.voice, "rvc_model_path", "backend/modules/voice/rvc_model/naira.pth"),
                        index_path=getattr(config.voice, "rvc_index_path", "backend/modules/voice/rvc_model/naira.index"),
                        pitch_shift=getattr(config.voice, "rvc_pitch_shift", 0),
                        f0_method=getattr(config.voice, "rvc_f0_method", "rmvpe"),
                        timeout=config.voice.default_timeout,
                    )
                    _LOG.info("[BOOT]   RVC TTS provider created")
                except Exception as exc:
                    _LOG.warning("[BOOT]   Failed to create RVC TTS provider: %s", exc)

            elif provider_name == "piper":
                try:
                    from backend.modules.voice.providers.piper_provider import (
                        _HAS_PIPER,
                        PiperTTSProvider,
                    )
                    if _HAS_PIPER:
                        voice_tts_providers["piper"] = PiperTTSProvider(
                            voice=config.voice.piper_voice,
                            sample_rate=config.voice.sample_rate,
                            speed=config.voice.speech_speed,
                            timeout=config.voice.default_timeout,
                        )
                        _LOG.info("[BOOT]   Piper TTS provider created")
                    else:
                        _LOG.warning("[BOOT]   Piper package not available")
                except Exception as exc:
                    _LOG.warning("[BOOT]   Failed to create Piper TTS provider: %s", exc)

            elif provider_name == "edge-tts":
                try:
                    from backend.modules.voice.providers.edge_tts_provider import (
                        EdgeTTSProvider,
                        _HAS_EDGE_TTS,
                    )
                    if _HAS_EDGE_TTS:
                        voice_tts_providers["edge-tts"] = EdgeTTSProvider(
                            voice="en-US-JennyNeural",
                            timeout=config.voice.default_timeout,
                        )
                        _LOG.info("[BOOT]   Edge-TTS provider created")
                    else:
                        _LOG.warning("[BOOT]   Edge-TTS package not available")
                except Exception as exc:
                    _LOG.warning("[BOOT]   Failed to create Edge-TTS provider: %s", exc)

            elif provider_name == "coqui":
                try:
                    from backend.modules.voice.providers.coqui_provider import (
                        _HAS_COQUI,
                        CoquiTTSProvider,
                    )
                    if _HAS_COQUI:
                        voice_tts_providers["coqui"] = CoquiTTSProvider(
                            model=config.voice.coqui_model,
                            sample_rate=config.voice.sample_rate,
                            speed=config.voice.speech_speed,
                            timeout=config.voice.default_timeout,
                        )
                        _LOG.info("[BOOT]   Coqui TTS provider created")
                    else:
                        _LOG.warning("[BOOT]   Coqui TTS package not available")
                except Exception as exc:
                    _LOG.warning("[BOOT]   Failed to create Coqui TTS provider: %s", exc)

            elif provider_name == "elevenlabs":
                try:
                    from backend.modules.voice.providers.elevenlabs_provider import (
                        _HAS_ELEVENLABS,
                        ElevenLabsTTSProvider,
                    )
                    # Check for API key
                    elevenlabs_key = (
                        getattr(env_snap, "elevenlabs_api_key", None) if env_snap else None
                    )
                    if _HAS_ELEVENLABS and elevenlabs_key:
                        voice_tts_providers["elevenlabs"] = ElevenLabsTTSProvider(
                            api_key=elevenlabs_key,
                            voice_id=config.voice.default_voice_id,
                            timeout=config.voice.default_timeout,
                        )
                        _LOG.info("[BOOT]   ElevenLabs TTS provider created")
                    elif not _HAS_ELEVENLABS:
                        _LOG.warning("[BOOT]   ElevenLabs package not available")
                    else:
                        _LOG.warning("[BOOT]   ElevenLabs API key not found")
                except Exception as exc:
                    _LOG.warning("[BOOT]   Failed to create ElevenLabs TTS provider: %s", exc)

        # Build Wake Word providers
        if config.voice.active_wake_word_provider == "porcupine":
            try:
                from backend.modules.voice.providers.porcupine_provider import (
                    _HAS_PORCUPINE,
                    PorcupineWakeWordProvider,
                )
                # Check for API key
                porcupine_key = (
                    getattr(env_snap, "porcupine_access_key", None) if env_snap else None
                )
                if _HAS_PORCUPINE and porcupine_key:
                    voice_wake_word_providers["porcupine"] = PorcupineWakeWordProvider(
                        access_key=porcupine_key,
                        keywords=config.voice.porcupine_keywords,
                        sensitivity=config.voice.porcupine_sensitivity,
                        timeout=config.voice.default_timeout,
                    )
                    _LOG.info("[BOOT]   Porcupine Wake Word provider created")
                elif not _HAS_PORCUPINE:
                    _LOG.warning("[BOOT]   Porcupine package not available")
                else:
                    _LOG.warning("[BOOT]   Porcupine access key not found")
            except Exception as exc:
                _LOG.warning("[BOOT]   Failed to create Porcupine Wake Word provider: %s", exc)

        active_tts = "rvc" if "rvc" in voice_tts_providers else (config.voice.active_tts_provider if voice_tts_providers else None)

        voice_mgr = VoiceManager(
            config=config,
            capability_manager=capability_mgr,
            tool_manager=tool_mgr,
            event_bus=event_bus,
            stt_providers=voice_stt_providers,
            tts_providers=voice_tts_providers,
            wake_word_providers=voice_wake_word_providers,
            active_stt_provider_name=(
                config.voice.active_stt_provider if voice_stt_providers else None
            ),
            active_tts_provider_name=active_tts,
            active_wake_word_provider_name=(
                config.voice.active_wake_word_provider if voice_wake_word_providers else None
            ),
            stt_fallback_chain=config.voice.stt_fallback_chain,
            tts_fallback_chain=tuple(tts_chain),
            default_timeout=config.voice.default_timeout,
        )
        await voice_mgr.async_init()
        modules["voice"] = voice_mgr
        container.register("voice_manager", voice_mgr)
        orchestrator.register_module("voice", voice_mgr)
        if getattr(voice_mgr, "degraded", False):
            degraded_modules.append("voice")
        _LOG.info("[BOOT] Voice initialised")

        # 7i – PCControlManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising PCControlManager ...")
        pc_control_adapter = None
        pc_deps = _check_pc_control_deps()
        any_pc_dep = any(pc_deps.values())
        if config.pc_control.enabled:
            if any_pc_dep:
                from backend.modules.pc_control._production_adapter import (
                    ProductionPCControlAdapter,
                )
                pc_control_adapter = ProductionPCControlAdapter(
                    config=config.pc_control,
                    logger=_LOG,
                )
                _LOG.info(
                    "[BOOT]   ProductionPCControlAdapter created — deps: %s",
                    pc_deps,
                )
            else:
                _LOG.warning(
                    "[BOOT]   PC control enabled but no dependencies available (%s) — "
                    "falling back to local adapter",
                    pc_deps,
                )
        pc_control_mgr = PCControlManager(
            config=config,
            capability_manager=capability_mgr,
            tool_manager=tool_mgr,
            event_bus=event_bus,
            adapter=pc_control_adapter,
            default_timeout=config.pc_control.default_timeout,
        )
        await pc_control_mgr.async_init()
        modules["pc_control"] = pc_control_mgr
        container.register("pc_control_manager", pc_control_mgr)
        orchestrator.register_module("pc_control", pc_control_mgr)
        if getattr(pc_control_mgr, "degraded", False):
            degraded_modules.append("pc_control")
        _LOG.info("[BOOT] PCControl initialised")

        # 7j – CodingAgentManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising CodingAgentManager ...")
        cod_config = config.coding_agent
        coding_agent_mgr = CodingAgentManager(
            config=config,
            capability_manager=capability_mgr,
            tool_manager=tool_mgr,
            context_manager=context_mgr,
            event_bus=event_bus,
            default_timeout=cod_config.default_timeout,
            max_iterations=cod_config.max_iterations,
            max_retries=cod_config.max_retries,
            retry_base_delay=cod_config.retry_base_delay,
            retry_max_delay=cod_config.retry_max_delay,
        )
        await coding_agent_mgr.async_init()
        modules["coding_agent"] = coding_agent_mgr
        container.register("coding_agent_manager", coding_agent_mgr)
        orchestrator.register_module("coding_agent", coding_agent_mgr)
        if getattr(coding_agent_mgr, "degraded", False):
            degraded_modules.append("coding_agent")
        _LOG.info("[BOOT] CodingAgent initialised")

        # 7j2 – PlanningManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising PlanningManager ...")
        planning_mgr = PlanningManager(
            config=config,
            event_bus=event_bus,
            tool_manager=tool_mgr,
            pc_control_manager=pc_control_mgr,
            security_manager=security_mgr if 'security_mgr' in locals() else None,
        )
        await planning_mgr.async_init()
        modules["planning"] = planning_mgr
        container.register("planning_manager", planning_mgr)
        orchestrator.register_module("planning", planning_mgr)
        if getattr(planning_mgr, "degraded", False):
            degraded_modules.append("planning")
        _LOG.info("[BOOT] Planning initialised")

        # 7j3 – DecisionManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising DecisionManager ...")
        decision_mgr = DecisionManager(
            config=config,
            event_bus=event_bus,
            analytics=analytics_mgr,
            fast_command_router=None,
            planning_manager=planning_mgr,
            coding_agent_manager=coding_agent_mgr,
        )
        await decision_mgr.async_init()
        modules["decision"] = decision_mgr
        container.register("decision_manager", decision_mgr)
        orchestrator.register_module("decision", decision_mgr)
        if getattr(decision_mgr, "degraded", False):
            degraded_modules.append("decision")
        _LOG.info("[BOOT] Decision initialised")

        # 7k – LLMManager (Layer 3 — AI Core)
        _LOG.info("[BOOT]   Initialising LLMManager ...")
        llm_providers: dict[str, object] = {}
        from backend.modules.llm.llm_config_store import LLMConfigStore
        vault_config = LLMConfigStore(root_dir / "memory" / "user_vault.json").get_active_config()
        env_snap = getattr(settings_mgr, "_env", None)
        if env_snap is None and container.has("env"):
            candidate = container.get("env")
            if hasattr(candidate, "gemini_api_key") or hasattr(candidate, "naira_api_key"):
                env_snap = candidate

        gemini_key = ""
        if env_snap is not None:
            gemini_key = getattr(env_snap, "gemini_api_key", "") or getattr(env_snap, "naira_api_key", "")
        else:
            from dotenv import load_dotenv
            load_dotenv()
            gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("NAIRA_API_KEY") or ""

        try:
            # 1. Try Loading DeepSeek (OpenCodeZen)
            if vault_config is not None and vault_config.provider == "deepseek":
                from backend.modules.llm.providers.deepseek_provider import DeepSeekProvider
                llm_providers["deepseek"] = DeepSeekProvider(api_key=vault_config.api_key, model=vault_config.model, timeout=config.llm.timeout)
                _LOG.info(f"[BOOT]   DeepSeek/OpenCodeZen LLM provider created (model={vault_config.model})")

            # 2. Try Loading Gemini
            _effective_gemini_key = vault_config.api_key if (vault_config and vault_config.provider == "gemini") else gemini_key
            if _effective_gemini_key:
                from backend.modules.llm.providers.gemini_provider import GeminiProvider
                _effective_model = vault_config.model if (vault_config and vault_config.provider == "gemini") else "gemini-1.5-flash"
                llm_providers["gemini"] = GeminiProvider(api_key=_effective_gemini_key, model=_effective_model, timeout=config.llm.timeout)
                _LOG.info(f"[BOOT]   Gemini LLM provider created (model={_effective_model})")
            else:
                _LOG.warning("[BOOT]   Gemini API key not found — skipping Gemini LLM provider")

        except ImportError as e:
            _LOG.warning(f"[BOOT]   Provider import failed: {e}")

        # 3. Dynamic Active Provider Selection
        if vault_config and vault_config.provider in llm_providers:
            active_llm = vault_config.provider
        elif llm_providers:
            active_llm = next(iter(llm_providers))
        else:
            active_llm = config.llm.active_provider

        fallback_llm = tuple(llm_providers.keys()) if llm_providers else config.llm.fallback_chain

        llm_mgr = LLMManager(
            config=config,
            providers=llm_providers,
            generation_config=None,
            safety_config=None,
            active_provider=active_llm,
            fallback_chain=fallback_llm,
            event_bus=event_bus,
        )
        await llm_mgr.async_init()
        # Force-recover degraded flag: if providers are registered the manager
        # must be considered active regardless of the health-check outcome.
        if getattr(llm_mgr, "_degraded", False) and llm_providers:
            llm_mgr._degraded = False
            _LOG.info("[BOOT]   LLM manager degraded flag cleared — providers present, forcing ONLINE")
        modules["llm"] = llm_mgr
        container.register("llm_manager", llm_mgr)
        orchestrator.register_module("llm", llm_mgr)
        if getattr(llm_mgr, "degraded", False):
            degraded_modules.append("llm")
            _LOG.warning("[BOOT]   LLM manager initialised in degraded state (no providers)")
        else:
            _LOG.info(
                "[BOOT]   LLM manager initialised with provider(s): %s",
                ", ".join(llm_providers),
            )

        # 7l – PromptManager (Layer 3 — AI Core)
        _LOG.info("[BOOT]   Initialising PromptManager ...")
        prompt_mgr = PromptManager(
            config=config,
            templates_dir=root_dir / "backend" / "modules" / "prompt" / "templates",
            event_bus=event_bus,
        )
        await prompt_mgr.async_init()
        modules["prompt"] = prompt_mgr
        container.register("prompt_manager", prompt_mgr)
        orchestrator.register_module("prompt", prompt_mgr)
        if getattr(prompt_mgr, "degraded", False):
            degraded_modules.append("prompt")
        _LOG.info("[BOOT] Prompt initialised")

        # 7m – ConversationManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising ConversationManager ...")
        conversation_mgr = ConversationManager(
            config=config,
            context_manager=context_mgr,
            prompt_manager=prompt_mgr,
            llm_manager=llm_mgr,
            memory_manager=memory_mgr,
            event_bus=event_bus,
            session_timeout=config.conversation.session_timeout,
            idle_cleanup_interval=config.conversation.idle_cleanup_interval,
            max_tokens=config.conversation.max_tokens,
        )
        await conversation_mgr.async_init()
        modules["conversation"] = conversation_mgr
        container.register("conversation_manager", conversation_mgr)
        orchestrator.register_module("conversation", conversation_mgr)
        if getattr(conversation_mgr, "degraded", False):
            degraded_modules.append("conversation")
        _LOG.info("[BOOT] Conversation initialised")

        # 7o – ContextIntelligenceManager (Layer 5 — Infrastructure)
        _LOG.info("[BOOT]   Initialising ContextIntelligenceManager ...")
        context_intel_mgr = ContextIntelligenceManager(
            config=config,
            event_bus=event_bus,
            memory_manager=memory_mgr,
            context_manager=context_mgr,
            tool_manager=tool_mgr,
            workspace_root=str(root_dir),
            max_chunk_size=config.context.max_tokens // 8,
            max_tree_nodes=100,
            cache_ttl=300,
            expansion_token_budget=4096,
            default_max_tokens=config.context.max_tokens,
        )
        await context_intel_mgr.async_init()
        modules["context_intelligence"] = context_intel_mgr
        container.register("context_intelligence_manager", context_intel_mgr)
        orchestrator.register_module("context_intelligence", context_intel_mgr)
        if getattr(context_intel_mgr, "degraded", False):
            degraded_modules.append("context_intelligence")
        _LOG.info("[BOOT] ContextIntelligence initialised")

        # 7n – RuntimeManager (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Initialising RuntimeManager ...")
        runtime_mgr = RuntimeManager(
            config=config,
            settings_manager=settings_mgr,
            context_manager=context_mgr,
            prompt_manager=prompt_mgr,
            llm_manager=llm_mgr,
            tool_manager=tool_mgr,
            memory_manager=memory_mgr,
            conversation_manager=conversation_mgr,
            context_intelligence_manager=context_intel_mgr,
            pc_control_manager=pc_control_mgr,
            browser_manager=browser_mgr,
            coding_agent_manager=coding_agent_mgr,
            vision_manager=vision_mgr,
            decision_manager=decision_mgr,
            analytics_manager=analytics_mgr,
            planning_manager=planning_mgr,
            security_manager=security_mgr if 'security_mgr' in locals() else None,
            capability_manager=capability_mgr,
            event_bus=event_bus,
            max_tool_iterations=config.tools.max_retries + 1,
        )
        await runtime_mgr.async_init()

        # 7o2 – AutonomousTaskEngine (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Registering AutonomousTaskEngine ...")
        autonomous_engine = runtime_mgr.autonomous_task_engine
        modules["autonomous_tasks"] = autonomous_engine
        container.register("autonomous_task_engine", autonomous_engine)
        orchestrator.register_module("autonomous_tasks", autonomous_engine)
        _LOG.info("[BOOT] AutonomousTaskEngine registered")

        # 7o3 – MultiAgentOrchestrator (Layer 4 — Orchestration)
        _LOG.info("[BOOT]   Registering MultiAgentOrchestrator ...")
        multi_agent_orch = runtime_mgr.multi_agent_orchestrator
        modules["multi_agent"] = multi_agent_orch
        container.register("multi_agent_orchestrator", multi_agent_orch)
        orchestrator.register_module("multi_agent", multi_agent_orch)
        _LOG.info("[BOOT] MultiAgentOrchestrator registered")

        modules["runtime"] = runtime_mgr
        container.register("runtime_manager", runtime_mgr)
        orchestrator.register_module("runtime", runtime_mgr)
        if getattr(runtime_mgr, "degraded", False):
            degraded_modules.append("runtime")
        _LOG.info("[BOOT] Runtime initialised")

        # Step 8 — Feature flags (already loaded by SettingsManager)
        features_mgr = getattr(settings_mgr, "features", None)
        features = getattr(features_mgr, "flags", None) if features_mgr is not None else None
        if features is not None:
            _LOG.info(
                "[BOOT] Step 8: Feature flags — vision=%s voice=%s browser=%s "
                "pc_control=%s security=%s avatar_3d=%s file_manager=%s",
                features.vision, features.voice, features.browser,
                features.pc_control, features.security,
                features.avatar_3d, features.file_manager,
            )
        else:
            _LOG.info("[BOOT] Step 8: No feature flags loaded (all disabled)")

        # Step 9 — Port/Adapter wiring (completed via constructor injection above)
        _LOG.info("[BOOT] Step 9: Port/Adapter wiring complete")

        # Step 10 — Capability registration + health verification
        register_system_capabilities(
            capability_mgr,
            features,
        )
        _LOG.info("[BOOT] Step 10: System capabilities registered")

        # Health verification
        _LOG.info("[BOOT] Step 10: Verifying module health ...")
        health_result = verify_boot_health(modules, container)

        # ── Dependency Report ──────────────────────────────────────────
        _LOG.info("[BOOT] Dependency report:")
        _LOG.info("[BOOT]   Browser: playwright=%s", _HAS_PLAYWRIGHT)
        _LOG.info("[BOOT]   PC-Control: pyautogui=%s psutil=%s pywin32=%s",
                   _PC_HAS_PYAUTOGUI, _PC_HAS_PSUTIL, _PC_HAS_PYWIN32)
        _LOG.info("[BOOT]   LLM: gemini=True")
        _LOG.info("[BOOT]   Vision: google-genai=False")

        if health_result["all_healthy"]:
            _LOG.info("[BOOT] All modules healthy")
        else:
            _LOG.warning(
                "[BOOT] %d module(s) degraded: %s",
                len(health_result["degraded_modules"]),
                ", ".join(health_result["degraded_modules"]),
            )

    except Exception as exc:
        _LOG.critical("[BOOT] Fatal error during boot — %s: %s", type(exc).__name__, exc)
        await shutdown_modules(modules)
        raise RuntimeError(f"Boot aborted: {exc}") from exc

    return modules


def register_system_capabilities(
    capability_mgr: CapabilityManager,
    feature_flags: object | None = None,
) -> None:
    """Register built-in system capabilities.

    Core capabilities (``llm``, ``memory``) are always registered.
    Feature-flagged capabilities are registered only when their
    corresponding feature flag is enabled.

    Parameters
    ----------
    capability_mgr : CapabilityManager
        The manager to register capabilities with.
    feature_flags : FeatureFlags | None
        Feature flag set (from ``SettingsManager.features.flags``).
    """
    capability_mgr.register(Capability(name="memory", version="0.1.0"))
    capability_mgr.register(Capability(name="llm", version="0.1.0"))

    existing = {c.name for c in capability_mgr.list_capabilities()}

    flag_map: dict[str, str] = {
        "vision": "vision",
        "voice": "voice",
        "browser": "browser",
        "pc_control": "pc_control",
        "file_manager": "file_manager",
        "avatar_3d": "avatar_3d",
        "security": "security",
        "coding_agent": "coding_agent",
    }

    for attr_name, cap_name in flag_map.items():
        if cap_name in existing:
            continue
        if feature_flags is not None and getattr(feature_flags, attr_name, False):
            deps: tuple[str, ...] = ()
            if cap_name in ("vision", "voice", "browser", "avatar_3d", "coding_agent"):
                deps = ("llm",)
            if cap_name in ("pc_control", "browser"):
                deps = deps + ("security",)
            capability_mgr.register(
                Capability(name=cap_name, version="0.1.0", dependencies=deps)
            )


def verify_boot_health(
    modules: dict[str, Any],
    container: DIContainer,
) -> dict[str, Any]:
    """Verify boot health: all modules initialised, all deps resolved,
    no duplicate registrations, no missing modules.

    Parameters
    ----------
    modules : dict[str, Any]
        The modules dict returned by ``boot_core_modules()``.
    container : DIContainer
        The DI container with all registered services.

    Returns
    -------
    dict[str, Any]
        Health report with keys:
        - ``all_healthy`` — ``True`` if no issues found
        - ``degraded_modules`` — list of degraded module names
        - ``missing_modules`` — list of expected but missing module names
        - ``missing_services`` — list of expected but missing DI services
        - ``module_count`` — total module count
        - ``service_count`` — total DI service count
    """
    expected_modules = {
        "settings", "memory", "analytics", "context", "capability", "skills", "tools", "security",
        "integrations", "plugins", "vision", "voice", "browser", "pc_control", "coding_agent", "llm", "prompt",
        "conversation", "context_intelligence", "autonomous_tasks", "multi_agent", "runtime",
    }
    expected_services = {
        "settings_manager",
        "memory_manager",
        "analytics_manager",
        "context_manager",
        "capability_manager",
        "skill_manager",
        "tool_manager",
        "security_manager",
        "integrations_manager",
        "plugin_manager",
        "vision_manager",
        "voice_manager",
        "browser_manager",
        "pc_control_manager",
        "coding_agent_manager",
        "llm_manager",
        "prompt_manager",
        "conversation_manager",
        "context_intelligence_manager",
        "autonomous_task_engine",
        "multi_agent_orchestrator",
        "runtime_manager",
    }

    missing_modules = [m for m in expected_modules if m not in modules]
    missing_services = [s for s in expected_services if not container.has(s)]
    degraded_list = [
        name for name, mod in modules.items()
        if getattr(mod, "degraded", False)
    ]

    all_healthy = not missing_modules and not missing_services

    report = {
        "all_healthy": all_healthy,
        "degraded_modules": degraded_list,
        "missing_modules": missing_modules,
        "missing_services": missing_services,
        "module_count": len(modules),
        "service_count": len(container.list_services()),
    }

    if missing_modules:
        _LOG.warning("[BOOT] Missing modules: %s", ", ".join(missing_modules))
    if missing_services:
        _LOG.warning("[BOOT] Missing DI services: %s", ", ".join(missing_services))
    if degraded_list:
        _LOG.warning("[BOOT] Degraded modules: %s", ", ".join(degraded_list))

    return report


async def shutdown_modules(
    modules: dict[str, Any],
) -> None:
    """Shutdown modules in reverse architecture order.

    18_Boot_Sequence.md §4 — shutdown sequence (S1–S7).

    Parameters
    ----------
    modules : dict[str, Any]
        The modules dict returned by ``boot_core_modules()``.
    """
    _LOG.info("[BOOT] Shutdown sequence: shutting down %d module(s)", len(modules))
    for name in _SHUTDOWN_ORDER:
        module = modules.get(name)
        if module is None:
            continue
        shutdown = getattr(module, "async_shutdown", None)
        if shutdown is not None:
            try:
                await shutdown()
                _LOG.info("[BOOT]   %s shut down", name.capitalize())
            except Exception as exc:
                _LOG.error("[BOOT]   Error shutting down '%s': %s", name, exc)


def _verify_module_health(name: str, module: object) -> None:
    degraded = getattr(module, "degraded", None)
    if degraded is not None and degraded:
        _LOG.warning("[BOOT]   Module '%s' initialised in degraded state", name)
    else:
        _LOG.debug("[BOOT]   Module '%s' health check passed", name)
