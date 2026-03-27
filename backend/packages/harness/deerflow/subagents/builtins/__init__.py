"""Built-in subagent configurations."""

from .general_purpose import GENERAL_PURPOSE_CONFIG

__all__ = ["GENERAL_PURPOSE_CONFIG"]

BUILTIN_SUBAGENTS = {
    "general-purpose": GENERAL_PURPOSE_CONFIG,
}
