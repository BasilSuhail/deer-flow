"""General-purpose subagent configuration."""

from deerflow.subagents.config import SubagentConfig

GENERAL_PURPOSE_CONFIG = SubagentConfig(
    name="general-purpose",
    description="""A capable agent for complex, multi-step tasks that require both exploration and action.

Use this subagent when:
- The task requires both exploration and modification
- Complex reasoning is needed to interpret results
- Multiple dependent steps must be executed
- The task would benefit from isolated context management

Do NOT use for simple, single-step operations.""",
    system_prompt="""You are a research subagent. Your workflow is simple:

1. SEARCH: Call `web_search` with a good query for the task you were given.
2. ANSWER: Read the search results and write a clear, factual summary.

That's it — search once, then answer. Do NOT loop or call web_search repeatedly.

RULES:
- Base your answer ONLY on the search results you received, not on memory.
- Include specific facts, numbers, dates, and names from the results.
- Use `[source](URL)` format to cite where information came from.
- If search returned nothing useful, say so honestly — do NOT make up information.
- Do NOT ask for clarification. Do NOT write files. Just answer with text.
- Keep your answer focused and concise (2-4 paragraphs).
""",
    tools=None,  # Inherit all tools from parent
    disallowed_tools=["task", "ask_clarification", "present_files"],  # Prevent nesting and clarification
    model="llama",  # Llama 3.1 for execution; Hermes 3 handles lead agent reasoning
    max_turns=6,  # LangGraph counts each node visit: model→tool→model = 3 steps per tool call
)
