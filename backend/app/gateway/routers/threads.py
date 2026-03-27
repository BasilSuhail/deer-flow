import json
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from deerflow.config.paths import Paths, get_paths

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["threads"])

_STATUS_FILE = os.environ.get("SUBAGENT_STATUS_FILE", "/app/logs/subagent_status.json")
_SCORES_FILE = os.environ.get("RESEARCH_SCORES_FILE", "/app/logs/research_scores.json")


class ThreadDeleteResponse(BaseModel):
    """Response model for thread cleanup."""

    success: bool
    message: str


def _delete_thread_data(thread_id: str, paths: Paths | None = None) -> ThreadDeleteResponse:
    """Delete local persisted filesystem data for a thread."""
    path_manager = paths or get_paths()
    try:
        path_manager.delete_thread_dir(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to delete thread data for %s", thread_id)
        raise HTTPException(status_code=500, detail="Failed to delete local thread data.") from exc

    logger.info("Deleted local thread data for %s", thread_id)
    return ThreadDeleteResponse(success=True, message=f"Deleted local thread data for {thread_id}")


@router.get("/research-scores")
async def get_research_scores() -> dict:
    """Return the latest cross-validation scores from the shared scores file."""
    try:
        with open(_SCORES_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"scores": [], "query": None, "updated_at": None}
    except Exception:
        logger.debug("Failed to read scores file", exc_info=True)
        return {"scores": [], "query": None, "updated_at": None}


@router.get("/subagent-status")
async def get_subagent_status() -> dict:
    """Return current subagent execution status from the shared status file.

    The LangGraph container writes this file; the Gateway reads it.
    This powers the agent status cards in the frontend dashboard.
    """
    try:
        with open(_STATUS_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"tasks": [], "updated_at": None}
    except Exception:
        logger.debug("Failed to read subagent status file", exc_info=True)
        return {"tasks": [], "updated_at": None}


@router.delete("/{thread_id}", response_model=ThreadDeleteResponse)
async def delete_thread_data(thread_id: str) -> ThreadDeleteResponse:
    """Delete local persisted filesystem data for a thread.

    This endpoint only cleans DeerFlow-managed thread directories. LangGraph
    thread state deletion remains handled by the LangGraph API.
    """
    return _delete_thread_data(thread_id)
