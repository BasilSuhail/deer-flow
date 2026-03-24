import json
import logging
import time
import urllib.request
from typing import Any

import psutil
from fastapi import APIRouter

from deerflow.config.app_config import get_app_config

router = APIRouter(prefix="/api/stats", tags=["health"])

logger = logging.getLogger(__name__)

# Simple in-memory tracker for agent activity
_agent_activity: dict[str, dict[str, Any]] = {}


def report_agent_activity(agent_name: str, status: str = "busy") -> None:
    """Report that an agent is active. Called from agent middleware/executor."""
    _agent_activity[agent_name] = {"status": status, "last_seen": time.time()}


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
                # Strip /v1 suffix to get the raw Ollama API URL
                url = str(base_url).rstrip("/")
                if url.endswith("/v1"):
                    url = url[:-3]
                return url
    except Exception:
        pass
    return "http://localhost:11434"


def _get_agent_statuses() -> dict[str, str]:
    """Return agent statuses based on real subagent activity and manual reports."""
    now = time.time()
    timeout = 30  # Consider idle after 30 seconds of no activity

    # Default agents shown in dashboard
    agents: dict[str, str] = {
        "Lead Agent": "idle",
        "Researcher": "idle",
        "Coder": "idle",
    }

    # Check real subagent background tasks
    try:
        from deerflow.subagents.executor import SubagentStatus, _background_tasks, _background_tasks_lock

        with _background_tasks_lock:
            running_count = sum(
                1 for t in _background_tasks.values()
                if t.status in (SubagentStatus.RUNNING, SubagentStatus.PENDING)
            )
        if running_count > 0:
            agents["Lead Agent"] = "busy"
            agents["Researcher"] = "busy"
    except ImportError:
        pass

    # Override with manual activity reports
    for name, info in _agent_activity.items():
        elapsed = now - info.get("last_seen", 0)
        if elapsed < timeout:
            agents[name] = info.get("status", "busy")

    return agents


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

    # --- Configured models ---
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

    # --- Agent status ---
    agents = _get_agent_statuses()

    return {
        "system_ram": system_ram,
        "ollama": {
            "reachable": ollama_reachable,
            "url": ollama_url,
            "models": ollama_models,
            "total_vram_used": total_vram_used,
        },
        "configured_models": configured_models,
        "agents": agents,
    }
