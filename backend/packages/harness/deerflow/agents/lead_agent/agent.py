"""Lead agent factory — simplified for local deep research with Ollama."""

import logging

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig

from deerflow.agents.lead_agent.prompt import apply_prompt_template
from deerflow.agents.middlewares.force_tool_middleware import ForceToolMiddleware
from deerflow.agents.middlewares.loop_detection_middleware import LoopDetectionMiddleware
from deerflow.agents.middlewares.tool_error_handling_middleware import build_lead_runtime_middlewares
from deerflow.agents.thread_state import ThreadState
from deerflow.config.app_config import get_app_config
from deerflow.models import create_chat_model

logger = logging.getLogger(__name__)


def _resolve_model_name(requested: str | None = None) -> str:
    """Resolve model name, falling back to first configured model."""
    app_config = get_app_config()
    if not app_config.models:
        raise ValueError("No models configured in config.yaml.")

    default = app_config.models[0].name
    if requested and app_config.get_model_config(requested):
        return requested

    if requested and requested != default:
        logger.warning(f"Model '{requested}' not found; using '{default}'.")
    return default


def _build_middlewares():
    """Build a minimal middleware chain for deep research."""
    middlewares = build_lead_runtime_middlewares(lazy_init=True)

    # ForceToolMiddleware: skips model for delegation, spawns 3 subagents directly.
    # During synthesis: trims context, lets model write final answer.
    middlewares.append(ForceToolMiddleware(subagent_enabled=True))

    # Safety net for infinite loops
    middlewares.append(LoopDetectionMiddleware())

    return middlewares


def make_lead_agent(config: RunnableConfig):
    """Create the lead research agent."""
    from deerflow.tools import get_available_tools

    cfg = config.get("configurable", {})
    requested_model = cfg.get("model_name") or cfg.get("model")
    model_name = _resolve_model_name(requested_model)

    logger.info(f"Creating lead agent with model: {model_name}, subagents: enabled")

    model = create_chat_model(name=model_name, thinking_enabled=False)
    tools = get_available_tools(subagent_enabled=True)
    middlewares = _build_middlewares()

    return create_agent(
        model=model,
        tools=tools,
        middleware=middlewares,
        system_prompt=apply_prompt_template(),
        state_schema=ThreadState,
    )
