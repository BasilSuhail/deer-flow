from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deerflow.config import get_app_config

router = APIRouter(prefix="/api", tags=["models"])


class ModelResponse(BaseModel):
    """Response model for model information."""

    name: str = Field(..., description="Unique identifier for the model")
    model: str = Field(..., description="Actual provider model identifier")
    display_name: str | None = Field(None, description="Human-readable name")
    description: str | None = Field(None, description="Model description")
    supports_thinking: bool = Field(default=False, description="Whether model supports thinking mode")
    supports_reasoning_effort: bool = Field(default=False, description="Whether model supports reasoning effort")


class ModelsListResponse(BaseModel):
    """Response model for listing all models."""

    models: list[ModelResponse]


class ModelUpdateRequest(BaseModel):
    """Request model for updating a model configuration."""
    model: str = Field(..., description="The new provider model identifier (e.g., llama3.1)")


@router.get(
    "/models",
    response_model=ModelsListResponse,
    summary="List All Models",
    description="Retrieve a list of all available AI models configured in the system.",
)
async def list_models() -> ModelsListResponse:
    """List all available models from configuration."""
    config = get_app_config()
    models = [
        ModelResponse(
            name=model.name,
            model=model.model,
            display_name=model.display_name,
            description=model.description,
            supports_thinking=model.supports_thinking,
            supports_reasoning_effort=model.supports_reasoning_effort,
        )
        for model in config.models
    ]
    return ModelsListResponse(models=models)


@router.get(
    "/models/{model_name}",
    response_model=ModelResponse,
    summary="Get Model Details",
)
async def get_model(model_name: str) -> ModelResponse:
    """Get a specific model by name."""
    config = get_app_config()
    model = config.get_model_config(model_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")

    return ModelResponse(
        name=model.name,
        model=model.model,
        display_name=model.display_name,
        description=model.description,
        supports_thinking=model.supports_thinking,
        supports_reasoning_effort=model.supports_reasoning_effort,
    )


@router.patch(
    "/models/{role_name}",
    response_model=ModelResponse,
    summary="Update Role Model",
    description="Assign a specific model identifier to a configured role (e.g., Lead Agent)."
)
async def update_model(role_name: str, request: ModelUpdateRequest) -> ModelResponse:
    """Update the model identifier for a specific role."""
    config = get_app_config()
    model_config = config.get_model_config(role_name)
    if model_config is None:
        raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")

    # Update the identifier
    model_config.model = request.model
    
    # Save back to file
    try:
        config.to_file()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {e}")

    return ModelResponse(
        name=model_config.name,
        model=model_config.model,
        display_name=model_config.display_name,
        description=model_config.description,
        supports_thinking=model_config.supports_thinking,
        supports_reasoning_effort=model_config.supports_reasoning_effort,
    )
