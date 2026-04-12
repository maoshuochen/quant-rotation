"""
统一配置加载器。

当前正式配置固定为拆分后的：
- universe.yaml
- strategy.yaml
- runtime.yaml
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML object in {path}")
    return data


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_app_config(root_dir: Path | None = None) -> Dict[str, Any]:
    root_dir = root_dir or Path(__file__).parent.parent
    config_dir = root_dir / "config"

    split_files = [
        config_dir / "universe.yaml",
        config_dir / "strategy.yaml",
        config_dir / "runtime.yaml",
    ]

    missing = [path.name for path in split_files if not path.exists()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing required config files: {missing_list}")

    config: Dict[str, Any] = {}
    for path in split_files:
        config = _deep_merge(config, _read_yaml(path))
    return _normalize_config(config)


def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(config)
    indices = normalized.get("indices", [])
    if isinstance(indices, list):
        active_indices = []
        inactive_indices = []
        for item in indices:
            if not isinstance(item, dict):
                continue
            if item.get("enabled", True):
                active_indices.append(item)
            else:
                inactive_indices.append(item)
        normalized["indices"] = active_indices
        if inactive_indices:
            normalized["inactive_indices"] = inactive_indices
    return normalized
