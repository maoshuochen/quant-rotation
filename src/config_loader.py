"""
统一配置加载器。

优先读取拆分后的 universe/strategy/runtime 配置；
若拆分配置不存在，则回退到旧版 config.yaml。
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

    if any(path.exists() for path in split_files):
        config: Dict[str, Any] = {}
        for path in split_files:
            config = _deep_merge(config, _read_yaml(path))

        legacy_path = config_dir / "config.yaml"
        if legacy_path.exists():
            config = _deep_merge(_read_yaml(legacy_path), config)
        return config

    return _read_yaml(config_dir / "config.yaml")
