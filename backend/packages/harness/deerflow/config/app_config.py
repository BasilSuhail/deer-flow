"""Application configuration — simplified for deep research engine."""

import logging
import os
from pathlib import Path
from typing import Any, Self

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from deerflow.config.checkpointer_config import CheckpointerConfig, load_checkpointer_config_from_dict
from deerflow.config.model_config import ModelConfig
from deerflow.config.subagents_config import load_subagents_config_from_dict
from deerflow.config.tool_config import ToolConfig, ToolGroupConfig

load_dotenv()

logger = logging.getLogger(__name__)


class AppConfig(BaseModel):
    """Config for the deep research engine."""

    models: list[ModelConfig] = Field(default_factory=list, description="Available models")
    tools: list[ToolConfig] = Field(default_factory=list, description="Available tools")
    tool_groups: list[ToolGroupConfig] = Field(default_factory=list, description="Tool groups")
    checkpointer: CheckpointerConfig | None = Field(default=None, description="Checkpointer config")
    subagents: dict[str, Any] | None = Field(default=None, description="Subagent system config")
    model_config = ConfigDict(extra="allow", frozen=False)

    @classmethod
    def resolve_config_path(cls, config_path: str | None = None) -> Path:
        """Resolve config file path."""
        if config_path:
            path = Path(config_path)
            if not path.exists():
                raise FileNotFoundError(f"Config file not found at {path}")
            return path
        elif os.getenv("DEER_FLOW_CONFIG_PATH"):
            path = Path(os.getenv("DEER_FLOW_CONFIG_PATH"))
            if not path.exists():
                raise FileNotFoundError(f"Config file not found at {path}")
            return path
        else:
            path = Path(os.getcwd()) / "config.yaml"
            if not path.exists():
                path = Path(os.getcwd()).parent / "config.yaml"
                if not path.exists():
                    raise FileNotFoundError("config.yaml not found")
            return path

    @classmethod
    def from_file(cls, config_path: str | None = None) -> Self:
        """Load config from YAML file."""
        resolved_path = cls.resolve_config_path(config_path)
        with open(resolved_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        config_data = cls.resolve_env_variables(config_data)

        if "subagents" in config_data:
            load_subagents_config_from_dict(config_data["subagents"])

        if "checkpointer" in config_data:
            load_checkpointer_config_from_dict(config_data["checkpointer"])

        return cls.model_validate(config_data)

    @classmethod
    def resolve_env_variables(cls, config: Any) -> Any:
        """Recursively resolve $ENV_VAR references."""
        if isinstance(config, str):
            if config.startswith("$"):
                env_value = os.getenv(config[1:])
                if env_value is None:
                    raise ValueError(f"Environment variable {config[1:]} not found")
                return env_value
            return config
        elif isinstance(config, dict):
            return {k: cls.resolve_env_variables(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [cls.resolve_env_variables(item) for item in config]
        return config

    def get_model_config(self, name: str) -> ModelConfig | None:
        return next((m for m in self.models if m.name == name), None)

    def get_tool_config(self, name: str) -> ToolConfig | None:
        return next((t for t in self.tools if t.name == name), None)

    def to_file(self, config_path: str | None = None) -> None:
        """Save current config to YAML file."""
        resolved_path = self.resolve_config_path(config_path)
        
        # We want to preserve comments and structure as much as possible, 
        # but safe_dump will rewrite the file.
        # For now, simple dump is sufficient for this tool.
        data = self.model_dump(exclude_none=True)
        
        # Clean up data for YAML (convert enums/paths if needed)
        with open(resolved_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, indent=2)
        
        # Update cache info
        global _app_config_mtime
        _app_config_mtime = resolved_path.stat().st_mtime


# Singleton cache
_app_config: AppConfig | None = None
_app_config_path: Path | None = None
_app_config_mtime: float | None = None
_app_config_is_custom = False


def _get_config_mtime(config_path: Path) -> float | None:
    try:
        return config_path.stat().st_mtime
    except OSError:
        return None


def _load_and_cache_app_config(config_path: str | None = None) -> AppConfig:
    global _app_config, _app_config_path, _app_config_mtime, _app_config_is_custom
    resolved_path = AppConfig.resolve_config_path(config_path)
    _app_config = AppConfig.from_file(str(resolved_path))
    _app_config_path = resolved_path
    _app_config_mtime = _get_config_mtime(resolved_path)
    _app_config_is_custom = False
    return _app_config


def get_app_config() -> AppConfig:
    """Get cached config, auto-reloading on file changes."""
    global _app_config, _app_config_path, _app_config_mtime

    if _app_config is not None and _app_config_is_custom:
        return _app_config

    resolved_path = AppConfig.resolve_config_path()
    current_mtime = _get_config_mtime(resolved_path)

    should_reload = (
        _app_config is None
        or _app_config_path != resolved_path
        or _app_config_mtime != current_mtime
    )
    if should_reload:
        _load_and_cache_app_config(str(resolved_path))
    return _app_config


def reload_app_config(config_path: str | None = None) -> AppConfig:
    return _load_and_cache_app_config(config_path)


def reset_app_config() -> None:
    global _app_config, _app_config_path, _app_config_mtime, _app_config_is_custom
    _app_config = None
    _app_config_path = None
    _app_config_mtime = None
    _app_config_is_custom = False


def set_app_config(config: AppConfig) -> None:
    global _app_config, _app_config_path, _app_config_mtime, _app_config_is_custom
    _app_config = config
    _app_config_path = None
    _app_config_mtime = None
    _app_config_is_custom = True
