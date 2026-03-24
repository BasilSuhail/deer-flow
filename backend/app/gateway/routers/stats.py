import json
import logging
import urllib.request
from typing import Any

import psutil
from fastapi import APIRouter

from deerflow.config.app_config import get_app_config

router = APIRouter(prefix="/api/stats", tags=["health"])

logger = logging.getLogger(__name__)


def _get_ollama_url() -> str:
    """Get the Ollama API base URL from the first configured model, or fall back to localhost."""
    try:
        config = get_app_config()
        for m in config.models:
            base_url = getattr(m, "base_url", None)
            if not base_url:
                extra = getattr(m, "model_extra", {}) or {}
                base_url = extra.get("base_url", "")
            if base_url and "11434" in str(base_url):
                url = str(base_url).rstrip("/")
                if url.endswith("/v1"):
                    url = url[:-3]
                return url
    except Exception:
        pass
    return "http://localhost:11434"


@router.get("")
async def get_stats():
    # --- System RAM ---
    vm = psutil.virtual_memory()
    system_ram = {
        "total": vm.total,
        "used": vm.used,
        "percent": vm.percent,
        "available": vm.available,
    }

    # --- Ollama model VRAM usage ---
    ollama_url = _get_ollama_url()
    ollama_models: list[dict[str, Any]] = []
    total_vram_used = 0
    ollama_reachable = False

    try:
        req = urllib.request.Request(f"{ollama_url}/api/ps")
        with urllib.request.urlopen(req, timeout=3.0) as response:
            data = json.loads(response.read().decode())
            ollama_reachable = True
            for m in data.get("models", []):
                vram = m.get("size_vram", 0) or m.get("size", 0)
                total_vram_used += vram
                ollama_models.append({
                    "name": m.get("name", "unknown"),
                    "size": m.get("size", 0),
                    "size_vram": vram,
                    "expires_at": m.get("expires_at", ""),
                })
    except Exception as e:
        logger.debug(f"Could not reach Ollama at {ollama_url}: {e}")

    # --- Configured models (with role info) ---
    configured_models: list[dict[str, str]] = []
    try:
        config = get_app_config()
        for m in config.models:
            configured_models.append({
                "name": m.name,
                "display_name": getattr(m, "display_name", m.name),
                "model": m.model,
            })
    except Exception:
        pass

    return {
        "system_ram": system_ram,
        "ollama": {
            "reachable": ollama_reachable,
            "url": ollama_url,
            "models": ollama_models,
            "total_vram_used": total_vram_used,
        },
        "configured_models": configured_models,
    }
