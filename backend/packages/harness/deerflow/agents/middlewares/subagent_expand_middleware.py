"""Middleware to expand a single task call into multiple subagent calls.

Small local models (7-8B) only emit one tool call per response, even when
instructed to launch multiple subagents. This middleware intercepts the
model's first ``task`` tool call and automatically creates additional calls
with different research aspects, so the full subagent pool is utilized.
"""

import logging
import uuid
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

# Aspect templates appended to the subagent prompt to diversify research
_ASPECT_SUFFIXES = [
    "",  # Original query stays as-is (index 0)
    (
        "\n\n**FOCUS AREA: Performance & Technical Comparison**\n"
        "Focus specifically on: technical capabilities, performance benchmarks, "
        "speed comparisons, scalability, supported languages/integrations, "
        "and technical limitations. Provide concrete data and numbers where possible."
    ),
    (
        "\n\n**FOCUS AREA: Community, Ecosystem & Real-World Adoption**\n"
        "Focus specifically on: community size (GitHub stars, contributors, forks), "
        "ecosystem maturity, third-party integrations, real-world case studies, "
        "company adoption, learning resources, and long-term viability."
    ),
]

# Short labels for the expanded task descriptions
_ASPECT_LABELS = [
    "",  # Original description stays as-is
    " (performance & tech)",
    " (community & adoption)",
]


class SubagentExpandMiddleware(AgentMiddleware[AgentState]):
    """Expands a single task tool call into multiple parallel subagent calls.

    After the model produces its response, if it contains exactly 1 ``task``
    tool call and this is the first time the model has called ``task`` in
    this conversation, the middleware duplicates the call with different
    focus areas to fill the subagent pool.

    This runs in ``aafter_model`` so it modifies the AIMessage's tool_calls
    before the ToolNode executes them.
    """

    def __init__(self, target_subagents: int = 3):
        super().__init__()
        self.target_subagents = min(target_subagents, len(_ASPECT_SUFFIXES))

    def _should_expand(self, state: AgentState) -> bool:
        """Return True if this is the first model response with a task call."""
        messages = state.get("messages", [])
        # Check if any PREVIOUS AI message already had a task call
        # (skip the last message which is the current one being processed)
        for m in messages[:-1]:
            if not isinstance(m, AIMessage):
                continue
            for tc in getattr(m, "tool_calls", None) or []:
                if tc.get("name") == "task":
                    return False  # Already expanded before
        return True

    def _expand_task_calls(self, state: AgentState) -> dict | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage):
            return None

        tool_calls = getattr(last_msg, "tool_calls", None)
        if not tool_calls:
            return None

        # Find task calls
        task_calls = [tc for tc in tool_calls if tc.get("name") == "task"]
        if len(task_calls) != 1:
            # Either 0 task calls (nothing to expand) or already multiple
            return None

        if not self._should_expand(state):
            return None

        original = task_calls[0]
        original_args = original.get("args", {})
        if not isinstance(original_args, dict):
            return None

        original_desc = original_args.get("description", "Research task")
        original_prompt = original_args.get("prompt", "")
        subagent_type = original_args.get("subagent_type", "general-purpose")

        # Build expanded tool_calls list: keep all non-task calls + expanded task calls
        new_tool_calls = [tc for tc in tool_calls if tc.get("name") != "task"]

        for i in range(self.target_subagents):
            suffix = _ASPECT_SUFFIXES[i] if i < len(_ASPECT_SUFFIXES) else ""
            label = _ASPECT_LABELS[i] if i < len(_ASPECT_LABELS) else f" (aspect {i + 1})"

            if i == 0:
                # Keep original call unchanged
                new_tool_calls.append(original)
            else:
                new_tool_calls.append({
                    "name": "task",
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "args": {
                        "description": (original_desc + label)[:80],
                        "prompt": original_prompt + suffix,
                        "subagent_type": subagent_type,
                    },
                })

        logger.info(
            "SubagentExpandMiddleware: expanded 1 task call → %d "
            "(descriptions: %s)",
            len([tc for tc in new_tool_calls if tc["name"] == "task"]),
            [tc["args"]["description"] for tc in new_tool_calls if tc["name"] == "task"],
        )

        updated_msg = last_msg.model_copy(update={"tool_calls": new_tool_calls})
        return {"messages": [updated_msg]}

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._expand_task_calls(state)

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._expand_task_calls(state)
