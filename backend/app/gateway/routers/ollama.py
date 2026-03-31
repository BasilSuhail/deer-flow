import json
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ollama", tags=["ollama"])

_OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")


class PullRequest(BaseModel):
    model: str


@router.post("/pull")
async def pull_model(request: PullRequest):
    """Proxy a pull request to the local Ollama instance and stream the response."""
    model_name = request.model.strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="Model name is required")

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
