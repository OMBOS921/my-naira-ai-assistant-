"""API vault endpoints.  Keys are accepted only for verification and storage."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.modules.llm.llm_config_store import LLMConfigStore
from backend.modules.llm.providers.deepseek_provider import DeepSeekProvider
from backend.modules.llm.providers.gemini_provider import GeminiProvider

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_MODELS = {"gemini": "gemini-1.5-flash", "deepseek": "deepseek-v4-flash-free"}


class VaultSaveRequest(BaseModel):
    provider: Literal["gemini", "deepseek"]
    api_key: str = Field(min_length=1, max_length=1024)
    model: str | None = Field(default=None, max_length=128)


@router.get("/status")
async def vault_status() -> dict[str, object]:
    config = LLMConfigStore().get_active_config()
    return {"configured": config is not None, "provider": config.provider if config else None, "model": config.model if config else None}


@router.post("/vault", status_code=status.HTTP_201_CREATED)
async def save_vault(payload: VaultSaveRequest, request: Request) -> dict[str, str | bool]:
    api_key = payload.api_key.strip()
    model = (payload.model or DEFAULT_MODELS[payload.provider]).strip()
    try:
        provider = (
            GeminiProvider(api_key=api_key, model=model)
            if payload.provider == "gemini"
            else DeepSeekProvider(api_key=api_key, model=model)
        )
        is_valid = await provider.verify_key()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API verification failed: {exc}",
        ) from exc

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The {payload.provider.upper()} provider rejected this key.",
        )

    config = LLMConfigStore().save(provider=payload.provider, model=model, api_key=api_key)
    manager = getattr(request.app.state, "llm_manager", None)
    if manager is not None:
        try:
            await manager.configure_from_vault(config)
        except AttributeError:
            pass
    return {"configured": True, "provider": config.provider, "model": config.model}
