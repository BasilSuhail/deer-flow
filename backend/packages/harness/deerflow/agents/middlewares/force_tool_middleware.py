"""Middleware to orchestrate the two-phase subagent flow with cross-validation.

Phase 1 — DELEGATION: Skip the model entirely. Directly create 3 task
tool calls so subagents are spawned immediately.

Phase 2 — SCORING & SYNTHESIS: After subagent results return, score each
result using cross-validation, stream scores to the frontend, then trim
context and let the model write the final answer (weighted by scores).

For non-subagent mode (subagent_enabled=False): forces tool_choice on
the first N turns so small models call web_search instead of hallucinating.
"""

import json
import logging
import os
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.scoring import CrossValidator, ResearchScore
from deerflow.subagents.executor import clear_all_background_tasks

logger = logging.getLogger(__name__)

# System prompt for synthesis.
# IMPORTANT: "Do not use <think> tags" prevents Qwen 3.5 from hiding
# the entire answer inside a thinking block and returning empty content.
_SYNTHESIS_SYSTEM = (
    "You are a research synthesizer. Write factual, well-structured answers "
    "using only the research results provided. Cite which result supports each "
    "claim. Do not use <think> tags."
)

# Template is formatted with {query} at build time.
_SYNTHESIS_INSTRUCTION_TEMPLATE = """Answer this question: {query}

Using the research results above, write a comprehensive response with this structure:

**Summary** — 1-2 sentences that directly answer the question.

## Key Findings
Bullet points of the most important facts. For each, note which result it came from — e.g. "Result 1 reports that..." or "According to Result 2...".

## [Add 2-3 section headings relevant to the topic]
Detailed breakdown with specific numbers, dates, names, and comparisons pulled from the results.

## Confirmed by multiple results
Facts that appear in 2 or more results — these are the most reliable findings.

## Sources
Any URLs or named sources mentioned in the results.

Rules:
- Every specific claim must reference a result: "Result 1 states...", "Result 2 found..."
- Where results contradict each other, present both: "Result 1 says X; Result 2 says Y"
- Do NOT add information not present in the results above
- Do NOT mention agents, scoring, or how this system works
- Do NOT use <think> tags — write your answer directly"""

# Research aspects for the 3 subagents
_ASPECTS = [
    ("", ""),
    (" (performance & tech)",
     "\n\n**FOCUS AREA: Performance & Technical Details**\n"
     "Focus specifically on: technical capabilities, performance benchmarks, "
     "comparisons, scalability, and technical limitations. Provide concrete data."),
    (" (community & adoption)",
     "\n\n**FOCUS AREA: Community, Ecosystem & Real-World Adoption**\n"
     "Focus specifically on: community size, ecosystem maturity, real-world "
     "case studies, company adoption, and long-term viability."),
]

_scorer = CrossValidator()

_SCORES_FILE = os.environ.get("RESEARCH_SCORES_FILE", "/app/logs/research_scores.json")


def _write_json_file(path: str, payload: dict) -> None:
    """Atomically write a JSON payload to a shared file."""
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, path)
    except Exception:
        logger.debug("Failed to write %s", path, exc_info=True)


def _write_scores_file(scores: list[dict], query: str) -> None:
    """Write scores to a shared JSON file for the dashboard."""
    from datetime import datetime
    _write_json_file(_SCORES_FILE, {
        "scores": scores, "query": query, "updated_at": datetime.now().isoformat(),
    })




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
    """Extract the last user message text."""
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


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from text (Qwen 3.5 thinking mode)."""
    if "<think>" not in text:
        return text
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    if cleaned:
        return cleaned
    # All content was inside <think> — extract it
    inner = re.search(r"<think>([\s\S]*?)</think>", text)
    return inner.group(1).strip() if inner else text


def _extract_tool_results(messages: list) -> list[str]:
    """Extract subagent result texts from ToolMessages."""
    results = []
    for m in messages:
        if isinstance(m, ToolMessage):
            content = m.content if isinstance(m.content, str) else str(m.content)
            content = _strip_think_tags(content)
            if content and len(content) > 20:
                results.append(content)
    return results


def _build_synthesis_messages(
    messages: list,
    scores: list[ResearchScore],
) -> list:
    """Build a trimmed message list for synthesis with scores.

    Results are ordered by score (best first) and labelled with their rank
    and score so the model knows which to trust. The synthesis instruction
    is injected directly into the HumanMessage — a trailing SystemMessage
    confuses small models and is avoided.
    """
    user_msg = None
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            user_msg = m
            break

    tool_results = _extract_tool_results(messages)
    query_text = user_msg.content if user_msg else "Research task"
    if isinstance(query_text, list):
        # Handle structured content blocks
        query_text = next(
            (b.get("text", "") for b in query_text if isinstance(b, dict) and b.get("type") == "text"),
            "Research task",
        )

    # Build result text ordered by score (best first), labelled for citation
    result_parts = []
    for rank, score in enumerate(scores):
        idx = score.agent_index
        if 0 <= idx < len(tool_results):
            result_parts.append(
                f"--- Result {rank + 1} (Score: {score.weighted_total:.0f}/100) ---\n"
                f"{tool_results[idx]}"
            )

    result_text = "\n\n".join(result_parts)
    instruction = _SYNTHESIS_INSTRUCTION_TEMPLATE.format(query=query_text)

    return [
        HumanMessage(
            content=(
                f"Research results for your question:\n\n"
                f"{result_text}\n\n"
                f"---\n\n"
                f"{instruction}"
            )
        ),
    ]


class ForceToolMiddleware(AgentMiddleware[AgentState]):
    """Two-phase orchestration with cross-validation scoring.

    When ``subagent_enabled=True``:
        DELEGATION: Skip model call → return 3 synthetic task calls directly.
        SCORING:    Score each result, cross-validate, stream scores.
        SYNTHESIS:  Trim context → let model write final answer.

    When ``subagent_enabled=False``:
        Force ``tool_choice='required'`` for the first ``force_turns`` turns.
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
    ) -> ModelResponse | AIMessage:
        messages = request.state.get("messages", [])

        if self.subagent_enabled:
            if _has_task_call_since_last_human(messages):
                # ── SCORING & SYNTHESIS PHASE ──
                user_query = _get_user_query(messages)
                tool_results = _extract_tool_results(messages)

                # Score all results
                scores = _scorer.score_results(tool_results, user_query)
                logger.info(
                    "ForceToolMiddleware: SCORING complete — %s",
                    [(s.agent_index, round(s.weighted_total, 1)) for s in scores],
                )

                # Stream scores to frontend via custom stream writer
                try:
                    from langgraph.config import get_stream_writer
                    writer = get_stream_writer()
                    writer({
                        "type": "research_scores",
                        "scores": [s.to_dict() for s in scores],
                        "query": user_query,
                    })
                except Exception:
                    logger.debug("Could not stream scores (no writer available)", exc_info=True)

                # Also write scores to shared file for the dashboard to read
                _write_scores_file([s.to_dict() for s in scores], user_query)

                # Build synthesis messages with score-ordered results
                logger.info("ForceToolMiddleware: SYNTHESIS phase")
                synthesis_messages = _build_synthesis_messages(messages, scores)
                request = request.override(
                    tools=[],
                    messages=synthesis_messages,
                    system_message=_SYNTHESIS_SYSTEM,
                )
                result = await handler(request)

                # Qwen 3.5 wraps output in <think>...</think> tags.
                # Strip from every AIMessage so the answer reaches the frontend.
                # handler() returns ModelResponse (with .result list) or AIMessage.
                msgs_to_clean: list[AIMessage] = []
                if isinstance(result, AIMessage):
                    msgs_to_clean = [result]
                elif hasattr(result, "result"):
                    msgs_to_clean = [m for m in result.result if isinstance(m, AIMessage)]

                for msg in msgs_to_clean:
                    content = msg.content or ""
                    if isinstance(content, str):
                        msg.content = _strip_think_tags(content)
                    # Fallback: if model returned empty after stripping, use best subagent result
                    if not msg.content or (isinstance(msg.content, str) and len(msg.content.strip()) == 0):
                        logger.warning("ForceToolMiddleware: SYNTHESIS returned empty — falling back to best subagent result")
                        if tool_results and scores:
                            best_idx = scores[0].agent_index
                            # Guard: agent_index must be a valid index into tool_results
                            if 0 <= best_idx < len(tool_results):
                                msg.content = _strip_think_tags(tool_results[best_idx])
                            elif tool_results:
                                # agent_index out of range — just use the first available result
                                msg.content = _strip_think_tags(tool_results[0])
                        if not msg.content or (isinstance(msg.content, str) and len(msg.content.strip()) == 0):
                            # Everything failed — give user something useful rather than blank
                            msg.content = "Research completed but synthesis failed. Please try again."
                    logger.info(
                        "ForceToolMiddleware: SYNTHESIS msg length=%d, has_tool_calls=%s",
                        len(msg.content) if isinstance(msg.content, str) else 0,
                        bool(getattr(msg, "tool_calls", None)),
                    )
                return result

            # ── DELEGATION PHASE ──
            # Clear stale data from previous queries
            _write_scores_file([], "")
            clear_all_background_tasks()

            user_query = _get_user_query(messages)
            logger.info("ForceToolMiddleware: DELEGATION phase — spawning 3 subagents directly (no model call)")

            tool_calls = []
            for label, suffix in _ASPECTS:
                tool_calls.append({
                    "name": "task",
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "args": {
                        "description": (user_query[:70] + label)[:80],
                        "prompt": user_query + suffix,
                        "subagent_type": "general-purpose",
                    },
                })

            # Return a synthetic AIMessage — the model is never called.
            return AIMessage(
                content="",
                tool_calls=tool_calls,
            )

        else:
            # Non-subagent mode: force tool usage on early turns
            tool_call_turns = sum(
                1 for m in messages
                if isinstance(m, AIMessage) and getattr(m, "tool_calls", None)
            )
            if tool_call_turns < self.force_turns:
                request = request.override(tool_choice="required")

            return await handler(request)
