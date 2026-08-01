"""Capability management endpoints.

Lists registered capabilities and toggles their enabled state via the
backend's ``CapabilityManager`` (``enable``/``disable``).  This lets the
frontend Plugins panel control what Naira can actually use at runtime.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])


class CapabilityToggleRequest(BaseModel):
    enabled: bool


def _get_manager(request: Request) -> Any:
    mgr = getattr(request.app.state, "capability_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="Capability manager not available",
        )
    return mgr


@router.get("")
async def list_capabilities(request: Request) -> dict[str, list[dict[str, Any]]]:
    """Return all registered capabilities with their enabled state."""
    mgr = _get_manager(request)
    caps: list[dict[str, Any]] = []
    for cap in mgr.list_capabilities():
        metadata = cap.metadata.resolve()
        caps.append(
            {
                "name": cap.name,
                "version": cap.version,
                "enabled": cap.enabled,
                "description": metadata.description,
                "dependencies": list(cap.dependencies),
            }
        )
    caps.sort(key=lambda c: c["name"])
    return {"capabilities": caps}


@router.post("/{name}/toggle")
async def toggle_capability(
    name: str,
    payload: CapabilityToggleRequest,
    request: Request,
) -> dict[str, Any]:
    """Enable or disable a registered capability.

    Raises ``400`` when the capability does not exist or the requested
    transition violates its dependency rules.
    """
    mgr = _get_manager(request)
    try:
        if payload.enabled:
            mgr.enable(name)
        else:
            mgr.disable(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"name": name, "enabled": mgr.is_enabled(name)}
