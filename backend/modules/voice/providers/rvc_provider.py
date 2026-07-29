"""RVCProvider — Retrieval-based Voice Conversion (RVC) TTS provider.

Uses EdgeTTSProvider as the base audio generator (with Indian/English accent support)
and transforms speech using an RVC inference model (.pth + .index) for realistic voice synthesis.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from backend.modules.voice._exceptions import (
    VoiceSynthesisError,
    VoiceTimeoutError,
)
from backend.modules.voice._types import AudioData, SynthesisResult
from backend.modules.voice.providers._tts_port import TTSPort
from backend.modules.voice.providers.edge_tts_provider import EdgeTTSProvider, _HAS_EDGE_TTS

_LOG = logging.getLogger("naira.voice.rvc")

_HAS_RVC_PYTHON = False
try:
    import rvc_python  # type: ignore # noqa: F401
    _HAS_RVC_PYTHON = True
except ImportError:
    _HAS_RVC_PYTHON = False

TTSProvider = TTSPort


class RVCProvider(TTSPort):
    """RVC-powered Text-to-Speech provider.

    Pipeline:
    1. Base speech synthesis using EdgeTTSProvider (default 'en-IN-NeerjaNeural' or 'en-US-JennyNeural').
    2. Pitch and timbre conversion using RVC inference engine (.pth + .index).
    """

    def __init__(
        self,
        *,
        base_voice: str = "en-IN-NeerjaNeural",
        model_path: str | Path = "backend/modules/voice/rvc_model/naira.pth",
        index_path: str | Path = "backend/modules/voice/rvc_model/naira.index",
        pitch_shift: int = 0,
        f0_method: str = "rmvpe",
        device: str = "cpu",
        timeout: float = 30.0,
        base_provider: EdgeTTSProvider | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._base_voice = base_voice
        self._model_path = Path(model_path)
        self._index_path = Path(index_path)
        self._pitch_shift = pitch_shift
        self._f0_method = f0_method
        self._device = device
        self._timeout = timeout
        self._logger = logger or _LOG
        self._base_tts = base_provider or EdgeTTSProvider(
            voice=self._base_voice,
            timeout=timeout,
            logger=self._logger,
        )

    def _resolve_model_path(self) -> Path:
        """Resolve model path, with fallback checks for directory models if using default path."""
        if self._model_path.exists():
            return self._model_path

        is_default = (
            self._model_path.name == "naira.pth"
            or "rvc_model" in str(self._model_path)
            or "models/rvc" in str(self._model_path)
        )
        if not is_default:
            return self._model_path

        search_dirs = [Path("backend/modules/voice/rvc_model"), Path("models/rvc")]
        for d in search_dirs:
            if d.exists() and d.is_dir():
                pth_files = list(d.glob("*.pth"))
                if pth_files:
                    return pth_files[0]

        return self._model_path

    def _resolve_index_path(self) -> Path:
        """Resolve index path, with fallback checks for directory index files if using default path."""
        if self._index_path.exists():
            return self._index_path

        is_default = (
            self._index_path.name == "naira.index"
            or "rvc_model" in str(self._index_path)
            or "models/rvc" in str(self._index_path)
        )
        if not is_default:
            return self._index_path

        search_dirs = [Path("backend/modules/voice/rvc_model"), Path("models/rvc")]
        for d in search_dirs:
            if d.exists() and d.is_dir():
                idx_files = list(d.glob("*.index"))
                if idx_files:
                    return idx_files[0]

        return self._index_path

    @property
    def is_available(self) -> bool:
        """Available if base TTS provider is available."""
        return self._base_tts.is_available

    @property
    def provider_name(self) -> str:
        return "rvc"

    def _run_rvc_inference_sync(self, input_path: str, output_path: str) -> None:
        """Synchronous RVC inference worker function to run in a thread pool."""
        model_file = self._resolve_model_path()
        index_file = self._resolve_index_path()

        if _HAS_RVC_PYTHON:
            from rvc_python.infer import RVCInference  # type: ignore
            rvc = RVCInference(device=self._device)
            rvc.load_model(str(model_file))
            idx_str = str(index_file) if index_file.exists() else ""
            rvc.infer_file(
                input_path=input_path,
                output_path=output_path,
                pitch_shift=self._pitch_shift,
                f0_method=self._f0_method,
                index_path=idx_str,
            )
        else:
            import subprocess
            cmd = [
                "python", "-m", "rvc_python.infer",
                "-i", input_path,
                "-o", output_path,
                "-m", str(model_file),
                "-k", str(self._pitch_shift),
                "-f", self._f0_method,
            ]
            if index_file.exists():
                cmd.extend(["-x", str(index_file)])

            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                raise RuntimeError(f"RVC CLI process failed ({res.returncode}): {res.stderr}")

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        language: str = "en",
        timeout: float = 30.0,
    ) -> SynthesisResult:
        """Synthesize text into RVC-transformed speech audio."""
        if not self.is_available:
            raise VoiceSynthesisError(
                "RVC provider unavailable: edge-tts dependency missing",
                context={"provider": "rvc"},
            )

        start_time = time.monotonic()
        eff_timeout = timeout or self._timeout
        effective_base_voice = voice_id or self._base_voice

        # Step 1: Base Audio Generation via EdgeTTSProvider
        self._logger.debug("Generating base audio with EdgeTTSProvider (%s)...", effective_base_voice)
        base_result = await self._base_tts.synthesize(
            text,
            voice_id=effective_base_voice,
            language=language,
            timeout=eff_timeout,
        )

        resolved_model = self._resolve_model_path()

        # Step 2: Check if RVC model file exists
        if not resolved_model.exists():
            self._logger.warning(
                "RVC model file not found at %s. Returning base EdgeTTS audio.",
                resolved_model,
            )
            return base_result

        # Step 3: Write base audio to temporary file and execute RVC conversion
        input_tmp_path = ""
        output_tmp_path = ""
        try:
            input_ext = ".mp3" if base_result.audio.format == "mp3" else ".wav"
            with tempfile.NamedTemporaryFile(suffix=input_ext, delete=False) as f_in:
                f_in.write(base_result.audio.data or b"")
                input_tmp_path = f_in.name

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_out:
                output_tmp_path = f_out.name

            # Run inference using thread pool to avoid blocking event loop
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._run_rvc_inference_sync,
                    input_tmp_path,
                    output_tmp_path,
                ),
                timeout=eff_timeout,
            )

            # Step 4: Read transformed audio
            with open(output_tmp_path, "rb") as f_res:
                transformed_bytes = f_res.read()

            duration_ms = (time.monotonic() - start_time) * 1000

            transformed_audio = AudioData(
                source_type="bytes",
                format="wav",
                sample_rate=24000,
                channels=1,
                duration_ms=duration_ms,
                size_bytes=len(transformed_bytes),
                data=transformed_bytes,
            )

            return SynthesisResult(
                audio=transformed_audio,
                text=text,
                voice_id=str(resolved_model),
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            raise VoiceTimeoutError(
                f"RVC voice conversion timed out after {eff_timeout}s",
                context={"provider": "rvc", "timeout": eff_timeout},
            ) from None
        except Exception as exc:
            self._logger.error("RVC synthesis failed: %s", exc)
            raise VoiceSynthesisError(
                f"RVC synthesis failed: {exc}",
                context={"provider": "rvc"},
            ) from exc
        finally:
            # Step 5: Safely delete temporary files
            for p in (input_tmp_path, output_tmp_path):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    async def close(self) -> None:
        await self._base_tts.close()


RvcTTSProvider = RVCProvider
