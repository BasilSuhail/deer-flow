"""Middleware to force small/local models to use tools instead of answering from memory.

When subagent mode is active, the first turn restricts the visible tool set to
only the ``task`` tool so that the model is forced to call it at least once.
The SubagentExpandMiddleware then handles expanding that single call into
multiple parallel subagent calls.

After the first ``task`` call, all constraints are released so the model can
synthesize the subagent results into a final answer.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


def _has_task_call(messages: list) -> bool:
    """Return True if any AI message in the history called the ``task`` tool."""
    for m in messages:
        if not isinstance(m, AIMessage):
            continue
        for tc in getattr(m, "tool_calls", None) or []:
            if tc.get("name") == "task":
                return True
    return False


class ForceToolMiddleware(AgentMiddleware[AgentState]):
    """Forces tool usage on small local models.

    When ``subagent_enabled=True``:
        Turn 0: Restrict tools to only ``task`` + ``ask_clarification``,
        set ``tool_choice='required'`` so the model MUST call task.
        After task has been called: release all constraints for synthesis.

    When ``subagent_enabled=False``:
        Turns 0..force_turns: ``tool_choice='required'`` with full tool set.
        After force_turns: no constraints.
    """

    def __init__(self, force_turns: int = 2, *, subagent_enabled: bool = False):
        super().__init__()
        self.force_turns = force_turns
        self.subagent_enabled = subagent_enabled

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        messages = request.state.get("messages", [])
        tool_call_turns = sum(
            1 for m in messages
            if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
        )

        if self.subagent_enabled:
            if _has_task_call(messages):
                # Task already called — let model synthesize freely
                logger.info("ForceToolMiddleware: task already called — model can answer freely")
                return await handler(request)

            # First turn: restrict to task tool only
            task_tools = [
                t for t in request.tools
                if getattr(t, "name", None) in ("task", "ask_clarification")
            ]
            if task_tools:
                logger.info(
                    "ForceToolMiddleware: forcing task tool (%d tools hidden)",
                    len(request.tools) - len(task_tools),
                )
                request = request.override(
                    tools=task_tools,
                    tool_choice="required",
                )
            else:
                logger.warning("ForceToolMiddleware: task tool not found")
                request = request.override(tool_choice="required")

        else:
            if tool_call_turns < self.force_turns:
                logger.info(
                    "ForceToolMiddleware: turn %d/%d — forcing tool_choice='required'",
                    tool_call_turns + 1, self.force_turns,
                )
                request = request.override(tool_choice="required")

        return await handler(request)
