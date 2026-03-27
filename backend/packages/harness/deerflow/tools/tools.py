import logging

from langchain.tools import BaseTool

from deerflow.config import get_app_config
from deerflow.reflection import resolve_variable
from deerflow.tools.builtins import task_tool

logger = logging.getLogger(__name__)


def get_available_tools(
    groups: list[str] | None = None,
    subagent_enabled: bool = False,
    **_kwargs,
) -> list[BaseTool]:
    """Get all available tools from config.

    Args:
        groups: Optional list of tool groups to filter by.
        subagent_enabled: Whether to include the task (subagent) tool.

    Returns:
        List of available tools.
    """
    config = get_app_config()
    loaded_tools = [
        resolve_variable(tool.use, BaseTool)
        for tool in config.tools
        if groups is None or tool.group in groups
    ]

    builtin_tools = []
    if subagent_enabled:
        builtin_tools.append(task_tool)
        logger.info("Including subagent task tool")

    logger.info(f"Total tools loaded: {len(loaded_tools)} config + {len(builtin_tools)} builtin")
    return loaded_tools + builtin_tools
