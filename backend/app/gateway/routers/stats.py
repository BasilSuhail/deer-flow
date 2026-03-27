"""System stats endpoint for the frontend dashboard."""

import json
import logging
import os
import platform

import httpx
from fastapi import APIRouter

from deerflow.config.app_config import get_app_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stats", tags=["stats"])

_STATUS_FILE = os.environ.get("SUBAGENT_STATUS_FILE", "/app/logs/subagent_status.json")
_OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")


def _get_system_ram() -> dict:
    """Get system RAM usage."""
    try:
        import resource
        # Fallback: use /proc/meminfo on Linux, sysctl on macOS
        if platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=2,
            )
            total = int(result.stdout.strip())
            # macOS doesn't expose free RAM easily; estimate from vm_stat
            result2 = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=2,
            )
            lines = result2.stdout.strip().split("\n")
            page_size = 16384  # default on Apple Silicon
            free_pages = 0
            for line in lines:
                if "free" in line.lower() and ":" in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        val = parts[1].strip().rstrip(".")
                        try:
                            free_pages = int(val)
                        except ValueError:
                            pass
                        break
            free = free_pages * page_size
            used = total - free
            percent = round((used / total) * 100, 1) if total > 0 else 0
            return {"total": total, "used": used, "free": free, "percent": percent}
        else:
            # Linux: read /proc/meminfo
            with open("/proc/meminfo") as f:
                info = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        info[key] = int(val) * 1024  # Convert kB to bytes
            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            used = total - available
            percent = round((used / total) * 100, 1) if total > 0 else 0
            return {"total": total, "used": used, "free": available, "percent": percent}
    except Exception:
        logger.debug("Failed to get system RAM", exc_info=True)
        return {"total": 0, "used": 0, "free": 0, "percent": 0}


async def _get_ollama_status() -> dict:
    """Check Ollama connectivity and running models."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # Check if Ollama is reachable
            resp = await client.get(f"{_OLLAMA_BASE}/api/tags")
            if resp.status_code != 200:
                return {"reachable": False, "models": [], "total_vram_used": 0}

            # Get running models (loaded in memory)
            ps_resp = await client.get(f"{_OLLAMA_BASE}/api/ps")
            models = []
            total_vram = 0
            if ps_resp.status_code == 200:
                data = ps_resp.json()
                for m in data.get("models", []):
                    size_vram = m.get("size_vram", 0)
                    total_vram += size_vram
                    models.append({
                        "name": m.get("name", ""),
                        "size_vram": size_vram,
                        "size": m.get("size", 0),
                    })

            return {"reachable": True, "models": models, "total_vram_used": total_vram}
    except Exception:
        return {"reachable": False, "models": [], "total_vram_used": 0}


def _get_subagent_status() -> list:
    """Read subagent status from shared file."""
    try:
        with open(_STATUS_FILE) as f:
            data = json.load(f)
            return data.get("tasks", [])
    except Exception:
        return []


@router.get("")
async def get_stats() -> dict:
    """Return system stats for the frontend dashboard."""
    app_config = get_app_config()

    configured_models = [
        {
            "name": m.name,
            "display_name": m.display_name or m.name,
            "model": m.model,
        }
        for m in app_config.models
    ]

    ollama = await _get_ollama_status()
    ram = _get_system_ram()
    subagents = _get_subagent_status()

    return {
        "system_ram": ram,
        "ollama": ollama,
        "configured_models": configured_models,
        "subagents": subagents,
    }
