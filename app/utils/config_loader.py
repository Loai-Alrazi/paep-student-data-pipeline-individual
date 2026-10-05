"""Load and validate the shared pipeline configuration."""

import json
import math
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PATH_KEYS = (
    "sources.csv.path",
    "sources.database.path",
    "output.processed",
    "output.rejected",
    "logging.path",
    "incremental.state_path",
)


def load_config(config_path: str | Path | None = None) -> dict:
    """Return a validated nested dict with filesystem paths as absolute strings.

    The default is the repository's config.json. Relative explicit config paths
    are also based on the repository root, independent of the working directory.
    Paths inside a config are resolved relative to that config's parent folder.
    API settings and other non-path values are preserved.

    Raises FileNotFoundError for a missing file and ValueError for invalid JSON,
    missing required keys, or invalid required values. Other I/O errors propagate.
    """
    path = Path(config_path) if config_path is not None else Path("config.json")
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    path = path.resolve()
    try:
        with path.open(encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Configuration file not found: {path}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid JSON configuration in {path}: {exc}") from exc

    required_keys = _PATH_KEYS + ("sources.api.url", "sources.api.timeout_seconds")
    for dotted_key in required_keys:
        value = config
        for key in dotted_key.split("."):
            if not isinstance(value, dict):
                raise ValueError(f"Expected a JSON object containing {dotted_key}")
            if key not in value:
                raise ValueError(f"Missing required configuration key: {dotted_key}")
            value = value[key]
        if dotted_key == "sources.api.timeout_seconds":
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{dotted_key} must be a positive finite number")
        elif not isinstance(value, str) or not value.strip():
            raise ValueError(f"{dotted_key} must be a non-empty string")

    for dotted_key in _PATH_KEYS:
        keys = dotted_key.split(".")
        section = config
        for key in keys[:-1]:
            section = section[key]
        section[keys[-1]] = str((path.parent / section[keys[-1]]).resolve())

    _validate_optional_extensions(config)
    return config


def _validate_optional_extensions(config: dict) -> None:
    web = config.get("sources", {}).get("web")
    if web is not None:
        _validate_enabled_section(web, "sources.web")
        if web["enabled"]:
            _require_non_empty(web, "url", "sources.web.url")
            _require_positive_number(
                web.get("timeout_seconds"), "sources.web.timeout_seconds"
            )
            offset = web.get("student_id_offset", 1000)
            if isinstance(offset, bool) or not isinstance(offset, int):
                raise ValueError("sources.web.student_id_offset must be an integer")

    for dotted_name, section in (
        ("sources.mongodb", config.get("sources", {}).get("mongodb")),
        ("output.mongodb", config.get("output", {}).get("mongodb")),
    ):
        if section is None:
            continue
        _validate_enabled_section(section, dotted_name)
        if not section["enabled"]:
            continue
        for key in ("uri", "database", "collection"):
            _require_non_empty(section, key, f"{dotted_name}.{key}")
        timeout_ms = section.get("server_selection_timeout_ms", 5000)
        if (
            isinstance(timeout_ms, bool)
            or not isinstance(timeout_ms, int)
            or timeout_ms <= 0
        ):
            raise ValueError(
                f"{dotted_name}.server_selection_timeout_ms must be a positive integer"
            )


def _validate_enabled_section(section: object, dotted_name: str) -> None:
    if not isinstance(section, dict):
        raise ValueError(f"{dotted_name} must be a JSON object")
    if "enabled" not in section:
        raise ValueError(f"Missing required configuration key: {dotted_name}.enabled")
    if not isinstance(section["enabled"], bool):
        raise ValueError(f"{dotted_name}.enabled must be a boolean")


def _require_non_empty(section: dict, key: str, dotted_name: str) -> None:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{dotted_name} must be a non-empty string")


def _require_positive_number(value: object, dotted_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{dotted_name} must be a positive finite number")
