import json
import logging
import os
import urllib.request
from typing import Any

import psutil
from fastapi import APIRouter

from deerflow.config.app_config import get_app_config

router = APIRouter(prefix="/api/stats", tags=["health"])

logger = logging.getLogger(__name__)

# Shared status file written by LangGraph subagent executor
_STATUS_FILE = os.environ.get("SUBAGENT_STATUS_FILE", "/app/logs/subagent_status.json")


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


def _read_subagent_status() -> list[dict[str, Any]]:
    """Read subagent status from shared file written by LangGraph executor."""
    try:
        if not os.path.exists(_STATUS_FILE):
            return []
        with open(_STATUS_FILE) as f:
            data = json.load(f)
        # Only return active tasks or recently completed ones (30s window)
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(seconds=30)).isoformat()
        tasks = []
        for t in data.get("tasks", []):
            # Always show pending/running tasks
            if t.get("status") in ("pending", "running"):
                tasks.append(t)
                continue
            # For completed/failed/timed_out: only show if finished within last 30s
            completed = t.get("completed_at") or ""
            if completed >= cutoff:
                tasks.append(t)
        return tasks
    except Exception:
        logger.debug("Failed to read subagent status file", exc_info=True)
        return []


def _get_host_ram_total() -> int | None:
    """Try to get the actual host RAM total, not the Docker container limit."""
    env_ram = os.environ.get("HOST_RAM_TOTAL_BYTES")
    if env_ram:
        try:
            return int(env_ram)
        except ValueError:
            pass
    return None


@router.get("")
async def get_stats():
    # --- System RAM ---
    vm = psutil.virtual_memory()
    host_ram = _get_host_ram_total()
    if host_ram and host_ram > vm.total:
        system_ram = {
            "total": host_ram,
            "used": vm.used,
            "percent": round(vm.used / host_ram * 100, 1),
            "available": host_ram - vm.used,
        }
    else:
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

    # --- Subagent status (from shared file) ---
    subagents = _read_subagent_status()

    return {
        "system_ram": system_ram,
        "ollama": {
            "reachable": ollama_reachable,
            "url": ollama_url,
            "models": ollama_models,
            "total_vram_used": total_vram_used,
        },
        "configured_models": configured_models,
        "subagents": subagents,
    }
