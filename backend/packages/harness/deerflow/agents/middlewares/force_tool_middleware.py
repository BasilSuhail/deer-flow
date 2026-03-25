"""Middleware to force small/local models to use tools instead of answering from memory.

When subagent mode is active, the first model call after each new user message
restricts the visible tool set to only the ``task`` tool so the model is forced
to delegate to subagents. The SubagentExpandMiddleware then expands that single
call into multiple parallel subagent calls.

After ``task`` has been called for the current user turn, constraints are released
and a synthesis instruction is injected so the model writes a proper report.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

# Minimal system prompt used ONLY during synthesis.  Replaces the full
# DeerFlow system prompt so the 8B model doesn't get distracted by it.
_SYNTHESIS_SYSTEM = "You are a research assistant. Synthesize the information below into a clear, well-structured answer."

_SYNTHESIS_INSTRUCTION = SystemMessage(content="""SYNTHESIZE the research results above into a comprehensive answer.

RULES:
1. Write ONLY about the topic the user asked about — nothing else
2. Use the ACTUAL data from the research results above
3. Structure with markdown headings (##), bullet points, and comparisons
4. Include specific facts, dates, numbers, and names from the results
5. If a result mentions sources/URLs, include them as citations
6. Do NOT mention DeerFlow, agents, frameworks, or how this system works
7. Do NOT make up information that isn't in the results above

Write your answer now:""")


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


def _build_synthesis_messages(messages: list) -> list:
    """Build a trimmed message list for the synthesis call.

    Extracts only the user question and the subagent ToolMessage results,
    discarding the full conversation history so the 8B model can focus.
    """
    # Find the last user question
    user_msg = None
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            user_msg = m
            break

    # Collect subagent results (ToolMessages that follow task calls)
    tool_results = []
    for m in messages:
        if isinstance(m, ToolMessage):
            content = m.content if isinstance(m.content, str) else str(m.content)
            if content and len(content) > 20:  # Skip empty/trivial results
                tool_results.append(content)

    # Build a clean context: user question + concatenated results + synthesis instruction
    result_text = "\n\n---\n\n".join(
        f"**Research Result {i+1}:**\n{r}" for i, r in enumerate(tool_results)
    )

    return [
        HumanMessage(content=f"My question: {user_msg.content if user_msg else 'Research task'}\n\n"
                     f"Here are the research results from my subagents:\n\n{result_text}"),
        _SYNTHESIS_INSTRUCTION,
    ]


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
        self._delegation_attempted = False

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
                # Trim context to ONLY what matters: user question + subagent results.
                # This prevents the 8B model from being distracted by the long system prompt.
                logger.info("ForceToolMiddleware: SYNTHESIS phase — trimming context for synthesis")
                self._delegation_attempted = False
                synthesis_messages = _build_synthesis_messages(messages)
                request = request.override(
                    tools=[],
                    messages=synthesis_messages,
                    system_message=_SYNTHESIS_SYSTEM,
                )
                return await handler(request)

            # DELEGATION PHASE: force model to call the task tool
            task_tools = [t for t in request.tools if getattr(t, "name", None) == "task"]
            if task_tools:
                logger.info("ForceToolMiddleware: DELEGATION phase — forcing task tool")
                self._delegation_attempted = True
                request = request.override(tools=task_tools, tool_choice="required")
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

        self._delegation_attempted = False

        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage):
            return None

        tool_calls = getattr(last_msg, "tool_calls", None) or []
        if tool_calls:
            return None  # Model obeyed — SubagentExpandMiddleware will handle expansion

        # Model ignored tool_choice="required" — inject synthetic task call
        user_query = _get_user_query(messages)
        logger.info("ForceToolMiddleware: model ignored tool_choice, injecting synthetic task call")

        synthetic_tool_call = {
            "name": "task",
            "id": f"call_{uuid.uuid4().hex[:8]}",
            "args": {
                "description": user_query[:80],
                "prompt": user_query,
                "subagent_type": "general-purpose",
            },
        }

        updated_msg = last_msg.model_copy(update={
            "tool_calls": [synthetic_tool_call],
            "content": "",
        })
        return {"messages": [updated_msg]}
