"""
Configuration file loader — reads, merges, and validates config files.

18_Boot_Sequence.md §2 Step 2.
21_System_Contracts.md §7.1–§7.4.

Supported file formats: JSON and YAML (when PyYAML is available).
Merge order (low → high priority): ``defaults`` → ``user``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Final

_LOG = logging.getLogger("naira.config.loader")

_CONFIG_PRIORITY: Final[list[str]] = ["defaults", "user"]
_VALID_EXTENSIONS: Final[set[str]] = {".json", ".yaml", ".yml"}


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------


def load_config(config_dir: Path) -> dict[str, Any]:
    """Load and merge configuration files from *config_dir*.

    Files are loaded in priority order (lowest first).  Later files
    override earlier ones via deep-merge.  Missing files are silently
    skipped.  A missing config directory returns an empty dict (all
    defaults).

    Parameters
    ----------
    config_dir : Path
        Path to the ``config/`` directory.

    Returns
    -------
    dict[str, Any]
        Merged configuration dictionary.
    """
    merged: dict[str, Any] = {}

    if not config_dir.is_dir():
        _LOG.warning("Config directory not found: %s — using built-in defaults", config_dir)
        return merged

    for name in _CONFIG_PRIORITY:
        data = _load_first(config_dir, name)
        if data is not None:
            merged = _deep_merge(merged, data)
            _LOG.debug("Loaded config: %s", name)

    return merged


def validate_config(
    data: dict[str, Any],
    schema_dir: Path | None = None,
) -> list[str]:
    """Validate configuration *data* against JSON Schemas.

    Parameters
    ----------
    data : dict[str, Any]
        Merged configuration data.
    schema_dir : Path | None
        Directory containing ``*.schema.json`` files.

    Returns
    -------
    list[str]
        Validation error messages.  Empty when valid or when
        no schemas exist.
    """
    if schema_dir is None or not schema_dir.is_dir():
        return []

    errors: list[str] = []

    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:
        _LOG.warning("jsonschema package not installed — config validation skipped")
        return errors

    for schema_path in sorted(schema_dir.glob("*.schema.json")):
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{schema_path.name}: failed to read schema — {exc}")
            continue

        section_name = schema_path.stem.replace(".schema", "")
        section_data = data.get(section_name, {})

        try:
            validator = jsonschema.Draft202012Validator(schema)
            for validation_error in validator.iter_errors(section_data):
                path = "/".join(str(p) for p in validation_error.absolute_path)
                errors.append(f"{schema_path.name}: {path} — {validation_error.message}")
        except Exception as exc:
            errors.append(f"{schema_path.name}: validation error — {exc}")

    return errors


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------


def _load_first(config_dir: Path, name: str) -> dict[str, Any] | None:
    """Try each extension for *name* and return the first successful parse."""
    for ext in _VALID_EXTENSIONS:
        path = config_dir / f"{name}{ext}"
        if not path.is_file():
            continue

        data = _parse_yaml(path) if ext in {".yaml", ".yml"} else _parse_json(path)

        if data is not None:
            return data

    return None


def _parse_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        _LOG.warning("Not a JSON object: %s", path)
        return None
    except (json.JSONDecodeError, OSError) as exc:
        _LOG.warning("Failed to parse JSON: %s — %s", path, exc)
        return None


def _parse_yaml(path: Path) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        _LOG.debug("PyYAML not installed — skipping YAML file: %s", path)
        return None

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        _LOG.warning("Not a YAML mapping: %s", path)
        return None
    except Exception as exc:
        _LOG.warning("Failed to parse YAML: %s — %s", path, exc)
        return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge *override* into *base* and return a new dict.

    Scalar values in *override* replace those in *base*.
    Dict values are recursively merged.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
