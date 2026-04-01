import json
import logging
import os
import re

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ollama", tags=["ollama"])

_OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")


class PullRequest(BaseModel):
    model: str


@router.get("/models")
async def list_models():
    """Proxy a list request to the local Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{_OLLAMA_BASE}/api/tags")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Ollama error while listing models")
            return response.json()
    except httpx.RequestError as e:
        logger.error("Failed to connect to Ollama: %s", e)
        raise HTTPException(status_code=503, detail="Failed to connect to Ollama service.")


@router.delete("/delete")
async def delete_model(request: PullRequest):
    """Proxy a delete request to the local Ollama instance."""
    model_name = request.model.strip().lower()
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name is required")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use build_request to ensure method is exactly DELETE with JSON body
            req = client.build_request(
                "DELETE",
                f"{_OLLAMA_BASE}/api/delete",
                json={"name": model_name}
            )
            response = await client.send(req)
            if response.status_code not in (200, 204):
                error_text = await response.aread()
                raise HTTPException(status_code=response.status_code, detail=f"Ollama error: {error_text.decode('utf-8', errors='ignore')}")
            return {"status": "deleted", "model": model_name}
    except httpx.RequestError as e:
        logger.error("Failed to connect to Ollama for delete: %s", e)
        raise HTTPException(status_code=503, detail="Failed to connect to Ollama service.")


@router.post("/run")
async def run_model(request: PullRequest):
    """Force load a model by sending a minimal generation request."""
    model_name = request.model.strip()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Sending a request with stream: false and a tiny prompt forces loading
            response = await client.post(
                f"{_OLLAMA_BASE}/api/generate",
                json={
                    "model": model_name,
                    "prompt": " ",
                    "stream": False,
                    "options": {"num_predict": 1}
                }
            )
            if response.status_code != 200:
                error_text = await response.aread()
                raise HTTPException(status_code=response.status_code, detail=f"Ollama error: {error_text.decode('utf-8', errors='ignore')}")
            return {"status": "success", "model": model_name}
    except httpx.RequestError as e:
        logger.error("Failed to connect to Ollama for run: %s", e)
        raise HTTPException(status_code=503, detail="Failed to connect to Ollama service.")


@router.post("/pull")
async def pull_model(request: PullRequest):
    """Proxy a pull request to the local Ollama instance and stream the response."""
    model_name = request.model.strip().lower()
    model_name = re.sub(r'\s+', '', model_name)

    if not model_name:
        raise HTTPException(status_code=400, detail="Model name is required")

    if ":" not in model_name:
        model_name += ":latest"

    async def generate():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                req = client.build_request(
                    "POST",
                    f"{_OLLAMA_BASE}/api/pull",
                    json={"name": model_name, "stream": True},
                )
                response = await client.send(req, stream=True)
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield json.dumps({"error": f"Ollama error {response.status_code}: {error_text.decode('utf-8', errors='ignore')}"}) + "\n"
                    return

                async for line in response.aiter_lines():
                    if line:
                        yield line + "\n"
        except httpx.RequestError as e:
            logger.error("Failed to connect to Ollama: %s", e)
            yield json.dumps({"error": "Failed to connect to Ollama service."}) + "\n"
        except Exception as e:
            logger.exception("Unexpected error during model pull")
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
