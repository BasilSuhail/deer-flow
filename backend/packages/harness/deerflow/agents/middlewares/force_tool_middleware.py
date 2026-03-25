"""Middleware to force small/local models to use tools instead of answering from memory."""

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


class ForceToolMiddleware(AgentMiddleware[AgentState]):
    """Forces tool_choice='required' on the model for the first few turns.

    Small local models (7-8B) tend to ignore available tools and answer
    from memory. This middleware sets tool_choice='required' for the first
    N turns so the model is forced to call at least one tool, then releases
    the constraint so it can produce a final answer.
    """

    def __init__(self, force_turns: int = 3):
        super().__init__()
        self.force_turns = force_turns

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        # Count how many AI messages with tool_calls already exist
        messages = request.state.get("messages", [])
        tool_call_turns = sum(
            1 for m in messages
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
        )

        if tool_call_turns < self.force_turns:
            logger.info(
                "ForceToolMiddleware: turn %d/%d — forcing tool_choice='required'",
                tool_call_turns + 1, self.force_turns,
            )
            request = request.override(tool_choice="required")
        else:
            logger.info(
                "ForceToolMiddleware: turn %d — model can answer freely",
                tool_call_turns + 1,
            )

        return await handler(request)
