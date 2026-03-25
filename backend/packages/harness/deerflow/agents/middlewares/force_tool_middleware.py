"""Middleware to force small/local models to use tools instead of answering from memory.

When subagent mode is active, the first model call after each new user message
restricts the visible tool set to only the ``task`` tool so the model is forced
to delegate to subagents. The SubagentExpandMiddleware then expands that single
call into multiple parallel subagent calls.

After ``task`` has been called for the current user turn, constraints are released
and a synthesis instruction is injected so the model writes a proper report.
"""

import logging
import sys
import uuid
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

# Synthesis instruction injected after subagent results return.
# This replaces the missing "reporter node" from DeerFlow v1.
_SYNTHESIS_INSTRUCTION = SystemMessage(content="""You have received results from your research subagents above.
Your job now is to SYNTHESIZE these results into a comprehensive, well-structured answer.

RULES:
1. Write your answer DIRECTLY as markdown text in your response
2. DO NOT call any tools — just write the answer
3. DO NOT write files or reference file paths
4. DO NOT ask follow-up questions — answer with what you have
5. Structure your response with clear headings (##), bullet points, and comparisons
6. Include specific data points, numbers, and examples from the subagent research
7. If a subagent failed, work with the results you DO have
8. Keep your response focused and informative — no filler or self-congratulation

Write your synthesis now:""")


def _has_task_call_since_last_human(messages: list) -> bool:
    """Return True if any AI message AFTER the last HumanMessage called ``task``."""
    last_human_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_idx = i
            break

    if last_human_idx < 0:
        return False

    for m in messages[last_human_idx + 1:]:
        if not isinstance(m, AIMessage):
            continue
        for tc in getattr(m, "tool_calls", None) or []:
            if tc.get("name") == "task":
                return True
    return False


def _get_user_query(messages: list) -> str:
    """Extract the last user message text for use in synthetic task calls."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            content = m.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
                    if isinstance(block, str):
                        return block
            return str(content)
    return "Research task"


class ForceToolMiddleware(AgentMiddleware[AgentState]):
    """Forces tool usage on small local models and guides synthesis.

    When ``subagent_enabled=True``:
        Phase 1 (delegation): Restrict tools to ``task`` only + ``tool_choice='required'``
        Phase 1b (fallback): If model ignores tool_choice, inject synthetic task call
        Phase 2 (synthesis): Strip all tools + inject synthesis instruction

    When ``subagent_enabled=False``:
        Turns 0..force_turns: ``tool_choice='required'`` with full tool set.
        After force_turns: no constraints.
    """

    def __init__(self, force_turns: int = 2, *, subagent_enabled: bool = False):
        super().__init__()
        self.force_turns = force_turns
        self.subagent_enabled = subagent_enabled
        self._delegation_attempted = False  # Track if we tried to force delegation

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
            if _has_task_call_since_last_human(messages):
                # SYNTHESIS PHASE: subagents have returned results.
                print(f"[DEERFLOW] ForceToolMiddleware: SYNTHESIS phase — injecting reporter instruction, stripping tools", file=sys.stderr, flush=True)
                self._delegation_attempted = False

                updated_messages = list(messages) + [_SYNTHESIS_INSTRUCTION]
                request = request.override(
                    tools=[],
                    messages=updated_messages,
                )
                return await handler(request)

            # DELEGATION PHASE: force model to call the task tool
            task_tools = [
                t for t in request.tools
                if getattr(t, "name", None) == "task"
            ]
            if task_tools:
                print(f"[DEERFLOW] ForceToolMiddleware: DELEGATION phase — forcing task tool only", file=sys.stderr, flush=True)
                self._delegation_attempted = True
                request = request.override(
                    tools=task_tools,
                    tool_choice="required",
                )
            else:
                logger.warning("ForceToolMiddleware: task tool not found in tool list")
                self._delegation_attempted = True
                request = request.override(tool_choice="required")

        else:
            self._delegation_attempted = False
            if tool_call_turns < self.force_turns:
                request = request.override(tool_choice="required")

        return await handler(request)

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._maybe_inject_task_call(state)

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._maybe_inject_task_call(state)

    def _maybe_inject_task_call(self, state: AgentState) -> dict | None:
        """If we forced delegation but model ignored tool_choice, inject a synthetic task call."""
        if not self.subagent_enabled or not self._delegation_attempted:
            return None

        self._delegation_attempted = False  # Reset for next turn

        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage):
            return None

        # Check if model actually produced a tool call
        tool_calls = getattr(last_msg, "tool_calls", None) or []
        if tool_calls:
            # Model obeyed — SubagentExpandMiddleware will handle expansion
            return None

        # Model ignored tool_choice="required" and produced text only.
        # Inject a synthetic task call so subagents still fire.
        user_query = _get_user_query(messages)
        print(f"[DEERFLOW] ForceToolMiddleware: model ignored tool_choice! Injecting synthetic task call for: {user_query[:60]}", file=sys.stderr, flush=True)

        synthetic_tool_call = {
            "name": "task",
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "args": {
                "description": user_query[:80],
                "prompt": user_query,
                "subagent_type": "general-purpose",
            },
        }

        # Replace the last message with one that has the tool call
        updated_msg = last_msg.model_copy(update={
            "tool_calls": [synthetic_tool_call],
            "content": "",  # Clear text since we're converting to a tool call
        })
        return {"messages": [updated_msg]}
