"""Runtime LLM settings — persist to /app/data/llm_config.json.

Allows the frontend to read and update the LLM provider configuration
(model name, base URL, API key) without restarting the container.
"""

import os
import json

CONFIG_PATH = os.environ.get("LLM_CONFIG_PATH", "/app/data/llm_config.json")

# Env-var defaults (used when config file doesn't set a value)
_ENV_DEFAULTS = {
    "base_url": os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
    "api_key": os.environ.get("LLM_API_KEY", ""),
    "model": os.environ.get("LLM_MODEL", "gpt-4o-mini"),
}


def _read_file() -> dict:
    """Read the JSON config file. Returns {} if missing or corrupt."""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_file(data: dict) -> None:
    """Atomically write the JSON config file."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CONFIG_PATH)


def get_config() -> dict:
    """Return the merged config: file values override env defaults."""
    cfg = dict(_ENV_DEFAULTS)
    cfg.update(_read_file())
    return cfg


def update_config(**kwargs) -> dict:
    """Update one or more config keys and persist.

    Only non-None, non-empty-string values are written.  Passing
    ``api_key=""`` clears the saved key (env fallback still applies).
    Returns the full merged config after the update.
    """
    current = _read_file()
    for k, v in kwargs.items():
        if v is not None:
            current[k] = v
    _write_file(current)
    return get_config()
