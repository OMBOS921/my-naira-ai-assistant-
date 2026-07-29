"""
Application configuration data model — typed, frozen dataclass tree.

21_System_Contracts.md §7.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LogConfig:
    """Logging subsystem configuration."""

    level: str = "INFO"
    directory: str = "logs"
    max_bytes: int = 10_485_760
    backup_count: int = 30


@dataclass(frozen=True)
class SecurityConfig:
    """Security module configuration — policy, sandbox, audit, and approval."""

    enabled: bool = False
    sandbox_enabled: bool = True
    audit_enabled: bool = True
    default_policy: str = "allow"
    approval_timeout: float = 60.0
    max_risk: str = "critical"
    allow_network: bool = True
    allow_filesystem: bool = True
    allow_browser: bool = True
    allow_pc_control: bool = True
    allow_voice: bool = True
    allow_vision: bool = True
    max_input_length: int = 32768
    allowed_paths: tuple[str, ...] = ()
    blocked_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextConfig:
    """Context window (sliding window) configuration."""

    max_tokens: int = 4096


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration.

    Mirrors VisionConfig and VoiceConfig patterns: active_provider,
    fallback_chain, retry policy, provider-specific settings.
    """

    # Provider selection
    active_provider: str = "deepseek"
    provider_mode: str = "automatic"  # automatic, manual
    fallback_chain: tuple[str, ...] = ("deepseek",)

    # Timeout and retry
    timeout: int = 30
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_exponential_base: float = 2.0

    # Generation defaults
    default_model: str = "gemini-3.5-flash"
    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 40
    max_output_tokens: int = 8192

    # Features
    streaming_enabled: bool = True
    json_mode_enabled: bool = True

    # Provider-specific models
    gemini_model: str = "gemini-3.5-flash"
    ollama_model: str = "llama3"

    # Safety
    enable_safety_filters: bool = True

    # Metrics
    enable_metrics: bool = True
    enable_cost_tracking: bool = True


@dataclass(frozen=True)
class ModulesConfig:
    """Lazy-loading module lifecycle configuration.

    18_Boot_Sequence.md §3.
    """

    unload_after_seconds: int = 300
    lazy_load_timeout: int = 30


@dataclass(frozen=True)
class ConversationConfig:
    """Conversation engine configuration."""

    session_timeout: float = 300.0
    idle_cleanup_interval: float = 60.0
    max_tokens: int = 4096


@dataclass(frozen=True)
class ToolConfig:
    """Tool execution configuration."""

    default_timeout: float = 30.0
    max_concurrent: int = 10
    max_retries: int = 3


@dataclass(frozen=True)
class BrowserConfig:
    """Browser module configuration."""

    default_timeout: float = 30.0
    enabled: bool = False


@dataclass(frozen=True)
class VoiceConfig:
    """Voice module configuration.

    Mirrors LLMConfig and VisionConfig patterns: active_provider,
    fallback_chain, retry policy, provider-specific settings.
    """

    default_timeout: float = 30.0
    enabled: bool = False
    default_language: str = "en"
    default_voice_id: str = ""

    # Provider architecture
    active_stt_provider: str = "faster-whisper"
    active_tts_provider: str = "rvc"
    active_wake_word_provider: str = "porcupine"

    stt_fallback_chain: tuple[str, ...] = ("faster-whisper", "whisper")
    tts_fallback_chain: tuple[str, ...] = ("rvc", "edge-tts", "piper", "coqui", "elevenlabs")

    # Audio configuration
    sample_rate: int = 16000
    audio_format: str = "wav"
    channels: int = 1

    # TTS-specific
    speech_speed: float = 1.0

    # Retry policy
    max_retries: int = 2
    retry_base_delay: float = 0.5
    retry_max_delay: float = 10.0

    # Provider-specific settings (models, paths, etc.)
    whisper_model: str = "base"
    faster_whisper_model: str = "base"
    piper_voice: str = "en_US-jenny-medium"
    coqui_model: str = "tts_models/en/ljspeech/tacotron2-DDC"
    porcupine_keywords: tuple[str, ...] = ("naira",)
    porcupine_sensitivity: float = 0.5
    rvc_model_path: str = "backend/modules/voice/rvc_model/naira.pth"
    rvc_index_path: str = "backend/modules/voice/rvc_model/naira.index"
    rvc_pitch_shift: int = 0
    rvc_f0_method: str = "rmvpe"


@dataclass(frozen=True)
class VisionConfig:
    """Vision module configuration.

    Mirrors LLMConfig pattern: active_provider, fallback_chain, model,
    timeout, retry policy — all configurable, zero hardcoded values.
    """

    default_timeout: float = 30.0
    enabled: bool = False
    max_image_width: int = 2048
    max_image_height: int = 2048
    active_provider: str = "gemini"
    fallback_chain: tuple[str, ...] = ("gemini",)
    model: str = "gemini-2.0-flash"
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0


@dataclass(frozen=True)
class PCControlConfig:
    """PC Control module configuration."""

    default_timeout: float = 30.0
    enabled: bool = False
    allowed_commands: tuple[str, ...] = ()
    sandbox_enabled: bool = True
    max_retries: int = 2
    retry_base_delay: float = 0.5
    retry_max_delay: float = 30.0


@dataclass(frozen=True)
class CodingAgentConfig:
    """Coding Agent module configuration."""

    default_timeout: float = 60.0
    enabled: bool = False
    max_iterations: int = 10
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0
    workspace_dir: str = ""
    allowed_commands: tuple[str, ...] = ()
    max_file_size: int = 1_048_576
    git_enabled: bool = True
    reflection_enabled: bool = True
    safety_enabled: bool = True
    mcp_enabled: bool = True
    hitl_enabled: bool = True
    compose_mode_enabled: bool = True
    self_correction_enabled: bool = True
    tdd_enabled: bool = True
    cicd_monitoring_enabled: bool = True
    cost_tracking_enabled: bool = True
    security_scanner_enabled: bool = True
    package_installer_enabled: bool = True
    max_correction_iterations: int = 3
    max_tdd_iterations: int = 5
    approval_timeout: float = 120.0
    scanner_rules: tuple[str, ...] = (
        "secrets", "injection", "xss", "path_traversal",
    )


@dataclass(frozen=True)
class ValidationConfig:
    """Validation Agent configuration (development-only).

    All fields default to ``False`` — the Validation Agent is never
    activated in production unless explicitly configured.
    """

    enabled: bool = False
    auto_fix: bool = False
    max_auto_fix_cycles: int = 3
    async_inspection: bool = False
    leak_detection: bool = False
    performance_profiling: bool = False
    coverage: bool = False
    regression: bool = False
    concurrency: int = 2


@dataclass(frozen=True)
class EventBusConfig:
    """Event Bus queue configuration."""

    max_queue_size: int = 1000


@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration tree.

    Composed of section-specific frozen dataclasses.  Each section is
    populated from the merged config file hierarchy during boot Step 2.

    Backward-compatible properties (``log_level``, ``log_dir``) bridge
    code written against the Phase 0.5 flat layout.
    """

    log: LogConfig = field(default_factory=LogConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    modules: ModulesConfig = field(default_factory=ModulesConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    pc_control: PCControlConfig = field(default_factory=PCControlConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    coding_agent: CodingAgentConfig = field(default_factory=CodingAgentConfig)
    event_bus: EventBusConfig = field(default_factory=EventBusConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    # ------------------------------------------------------------------
    # Backward compatibility  (Phase 0.5 flat field access)
    # ------------------------------------------------------------------

    @property
    def log_level(self) -> str:
        return self.log.level

    @property
    def log_dir(self) -> str:
        return self.log.directory

    # ------------------------------------------------------------------
    # Bootstrap factory
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> AppConfig:
        """Load configuration from the default ``config/`` directory.

        Convenience classmethod retained for backward compatibility.
        New code should use ``SettingsManager`` instead.
        """
        from backend.modules.settings._loader import load_config

        root = Path(__file__).resolve().parent.parent.parent.parent
        raw = load_config(root / "config")
        return build_app_config(raw)


# -----------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------


def build_app_config(raw: dict[str, Any]) -> AppConfig:
    """Construct an ``AppConfig`` from a merged config dictionary.

    Unknown keys are silently ignored (forward compatibility).
    Missing sections fall back to dataclass defaults.
    """
    log_dict = _section(raw, "log")
    sec_dict = _section(raw, "security")
    ctx_dict = _section(raw, "context")
    llm_dict = _section(raw, "llm")
    mod_dict = _section(raw, "modules")
    cnv_dict = _section(raw, "conversation")
    tls_dict = _section(raw, "tools")
    brw_dict = _section(raw, "browser")
    pcc_dict = _section(raw, "pc_control")
    voc_dict = _section(raw, "voice")
    vis_dict = _section(raw, "vision")
    cod_dict = _section(raw, "coding_agent")
    evt_dict = _section(raw, "event_bus")
    val_dict = _section(raw, "validation")

    return AppConfig(
        log=LogConfig(
            level=str(log_dict.get("level", "INFO")),
            directory=str(log_dict.get("directory", "logs")),
            max_bytes=int(log_dict.get("max_bytes", 10_485_760)),
            backup_count=int(log_dict.get("backup_count", 30)),
        ),
        security=SecurityConfig(
            enabled=bool(sec_dict.get("enabled", False)),
            sandbox_enabled=bool(sec_dict.get("sandbox_enabled", True)),
            audit_enabled=bool(sec_dict.get("audit_enabled", True)),
            default_policy=str(sec_dict.get("default_policy", "allow")),
            approval_timeout=float(sec_dict.get("approval_timeout", 60.0)),
            max_risk=str(sec_dict.get("max_risk", "critical")),
            allow_network=bool(sec_dict.get("allow_network", True)),
            allow_filesystem=bool(sec_dict.get("allow_filesystem", True)),
            allow_browser=bool(sec_dict.get("allow_browser", True)),
            allow_pc_control=bool(sec_dict.get("allow_pc_control", True)),
            allow_voice=bool(sec_dict.get("allow_voice", True)),
            allow_vision=bool(sec_dict.get("allow_vision", True)),
            max_input_length=int(sec_dict.get("max_input_length", 32768)),
            allowed_paths=tuple(sec_dict.get("allowed_paths", ())),
            blocked_paths=tuple(sec_dict.get("blocked_paths", ())),
        ),
        context=ContextConfig(
            max_tokens=int(ctx_dict.get("max_tokens", 4096)),
        ),
        llm=LLMConfig(
            active_provider=str(llm_dict.get("active_provider", "gemini")),
            provider_mode=str(llm_dict.get("provider_mode", "automatic")),
            fallback_chain=tuple(llm_dict.get("fallback_chain", ("gemini",))),
            timeout=int(llm_dict.get("timeout", 30)),
            max_retries=int(llm_dict.get("max_retries", 3)),
            retry_base_delay=float(llm_dict.get("retry_base_delay", 1.0)),
            retry_max_delay=float(llm_dict.get("retry_max_delay", 60.0)),
            retry_exponential_base=float(llm_dict.get("retry_exponential_base", 2.0)),
            default_model=str(llm_dict.get("default_model", "gemini-3.5-flash")),
            temperature=float(llm_dict.get("temperature", 0.7)),
            top_p=float(llm_dict.get("top_p", 0.95)),
            top_k=int(llm_dict.get("top_k", 40)),
            max_output_tokens=int(llm_dict.get("max_output_tokens", 8192)),
            streaming_enabled=bool(llm_dict.get("streaming_enabled", True)),
            json_mode_enabled=bool(llm_dict.get("json_mode_enabled", True)),
            gemini_model=str(llm_dict.get("gemini_model", "gemini-3.5-flash")),
            ollama_model=str(llm_dict.get("ollama_model", "llama3")),
            enable_safety_filters=bool(llm_dict.get("enable_safety_filters", True)),
            enable_metrics=bool(llm_dict.get("enable_metrics", True)),
            enable_cost_tracking=bool(llm_dict.get("enable_cost_tracking", True)),
        ),
        modules=ModulesConfig(
            unload_after_seconds=int(mod_dict.get("unload_after_seconds", 300)),
            lazy_load_timeout=int(mod_dict.get("lazy_load_timeout", 30)),
        ),
        conversation=ConversationConfig(
            session_timeout=float(cnv_dict.get("session_timeout", 300.0)),
            idle_cleanup_interval=float(cnv_dict.get("idle_cleanup_interval", 60.0)),
            max_tokens=int(cnv_dict.get("max_tokens", 4096)),
        ),
        tools=ToolConfig(
            default_timeout=float(tls_dict.get("default_timeout", 30.0)),
            max_concurrent=int(tls_dict.get("max_concurrent", 10)),
            max_retries=int(tls_dict.get("max_retries", 3)),
        ),
        browser=BrowserConfig(
            default_timeout=float(brw_dict.get("default_timeout", 30.0)),
            enabled=bool(brw_dict.get("enabled", False)),
        ),
        pc_control=PCControlConfig(
            default_timeout=float(pcc_dict.get("default_timeout", 30.0)),
            enabled=bool(pcc_dict.get("enabled", False)),
            allowed_commands=tuple(pcc_dict.get("allowed_commands", ())),
            sandbox_enabled=bool(pcc_dict.get("sandbox_enabled", True)),
            max_retries=int(pcc_dict.get("max_retries", 2)),
            retry_base_delay=float(pcc_dict.get("retry_base_delay", 0.5)),
            retry_max_delay=float(pcc_dict.get("retry_max_delay", 30.0)),
        ),
        voice=VoiceConfig(
            default_timeout=float(voc_dict.get("default_timeout", 30.0)),
            enabled=bool(voc_dict.get("enabled", False)),
            default_language=str(voc_dict.get("default_language", "en")),
            default_voice_id=str(voc_dict.get("default_voice_id", "")),
            active_stt_provider=str(voc_dict.get("active_stt_provider", "faster-whisper")),
            active_tts_provider=str(voc_dict.get("active_tts_provider", "edge-tts")),
            active_wake_word_provider=str(voc_dict.get("active_wake_word_provider", "porcupine")),
            stt_fallback_chain=tuple(voc_dict.get("stt_fallback_chain", ("faster-whisper", "whisper"))),
            tts_fallback_chain=tuple(voc_dict.get("tts_fallback_chain", ("edge-tts", "piper", "coqui", "elevenlabs"))),
            sample_rate=int(voc_dict.get("sample_rate", 16000)),
            audio_format=str(voc_dict.get("audio_format", "wav")),
            channels=int(voc_dict.get("channels", 1)),
            speech_speed=float(voc_dict.get("speech_speed", 1.0)),
            max_retries=int(voc_dict.get("max_retries", 2)),
            retry_base_delay=float(voc_dict.get("retry_base_delay", 0.5)),
            retry_max_delay=float(voc_dict.get("retry_max_delay", 10.0)),
            whisper_model=str(voc_dict.get("whisper_model", "base")),
            faster_whisper_model=str(voc_dict.get("faster_whisper_model", "base")),
            piper_voice=str(voc_dict.get("piper_voice", "en_US-jenny-medium")),
            coqui_model=str(voc_dict.get("coqui_model", "tts_models/en/ljspeech/tacotron2-DDC")),
            porcupine_keywords=tuple(voc_dict.get("porcupine_keywords", ("naira",))),
            porcupine_sensitivity=float(voc_dict.get("porcupine_sensitivity", 0.5)),
        ),
        vision=VisionConfig(
            default_timeout=float(vis_dict.get("default_timeout", 30.0)),
            enabled=bool(vis_dict.get("enabled", False)),
            max_image_width=int(vis_dict.get("max_image_width", 2048)),
            max_image_height=int(vis_dict.get("max_image_height", 2048)),
            active_provider=str(vis_dict.get("active_provider", "gemini")),
            fallback_chain=tuple(
                vis_dict.get("fallback_chain", ("gemini",)),
            ),
            model=str(vis_dict.get("model", "gemini-2.0-flash")),
            max_retries=int(vis_dict.get("max_retries", 3)),
            retry_base_delay=float(vis_dict.get("retry_base_delay", 1.0)),
            retry_max_delay=float(vis_dict.get("retry_max_delay", 30.0)),
        ),
        coding_agent=CodingAgentConfig(
            default_timeout=float(cod_dict.get("default_timeout", 60.0)),
            enabled=bool(cod_dict.get("enabled", False)),
            max_iterations=int(cod_dict.get("max_iterations", 10)),
            max_retries=int(cod_dict.get("max_retries", 3)),
            retry_base_delay=float(cod_dict.get("retry_base_delay", 1.0)),
            retry_max_delay=float(cod_dict.get("retry_max_delay", 30.0)),
            workspace_dir=str(cod_dict.get("workspace_dir", "")),
            allowed_commands=tuple(cod_dict.get("allowed_commands", ())),
            max_file_size=int(cod_dict.get("max_file_size", 1_048_576)),
            git_enabled=bool(cod_dict.get("git_enabled", True)),
            reflection_enabled=bool(cod_dict.get("reflection_enabled", True)),
            safety_enabled=bool(cod_dict.get("safety_enabled", True)),
            mcp_enabled=bool(cod_dict.get("mcp_enabled", True)),
            hitl_enabled=bool(cod_dict.get("hitl_enabled", True)),
            compose_mode_enabled=bool(cod_dict.get("compose_mode_enabled", True)),
            self_correction_enabled=bool(cod_dict.get("self_correction_enabled", True)),
            tdd_enabled=bool(cod_dict.get("tdd_enabled", True)),
            cicd_monitoring_enabled=bool(cod_dict.get("cicd_monitoring_enabled", True)),
            cost_tracking_enabled=bool(cod_dict.get("cost_tracking_enabled", True)),
            security_scanner_enabled=bool(cod_dict.get("security_scanner_enabled", True)),
            package_installer_enabled=bool(cod_dict.get("package_installer_enabled", True)),
            max_correction_iterations=int(cod_dict.get("max_correction_iterations", 3)),
            max_tdd_iterations=int(cod_dict.get("max_tdd_iterations", 5)),
            approval_timeout=float(cod_dict.get("approval_timeout", 120.0)),
            scanner_rules=tuple(cod_dict.get("scanner_rules", (
                "secrets", "injection", "xss", "path_traversal",
            ))),
        ),
        event_bus=EventBusConfig(
            max_queue_size=int(evt_dict.get("max_queue_size", 1000)),
        ),
        validation=ValidationConfig(
            enabled=bool(val_dict.get("enabled", False)),
            auto_fix=bool(val_dict.get("auto_fix", False)),
            max_auto_fix_cycles=int(val_dict.get("max_auto_fix_cycles", 3)),
            async_inspection=bool(val_dict.get("async_inspection", False)),
            leak_detection=bool(val_dict.get("leak_detection", False)),
            performance_profiling=bool(val_dict.get("performance_profiling", False)),
            coverage=bool(val_dict.get("coverage", False)),
            regression=bool(val_dict.get("regression", False)),
            concurrency=int(val_dict.get("concurrency", 2)),
        ),
    )


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    data = raw.get(name, {})
    return data if isinstance(data, dict) else {}
