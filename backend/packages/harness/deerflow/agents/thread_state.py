"""Thread state for the deep research agent."""

from typing import NotRequired, TypedDict

from langchain.agents import AgentState


class ThreadDataState(TypedDict):
    workspace_path: NotRequired[str | None]


class ThreadState(AgentState):
    thread_data: NotRequired[ThreadDataState | None]
    title: NotRequired[str | None]
