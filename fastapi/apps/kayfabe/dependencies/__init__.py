"""Kayfabe 의존성 조립소 (DIP 팩토리)."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "get_ple",
    "get_pleinfo",
    "get_ranking",
    "get_records",
    "get_result",
    "get_title_history",
    "get_championship",
]

_LAZY_IMPORTS: dict[str, str] = {
    "get_ple": "kayfabe.dependencies.ple_provider",
    "get_pleinfo": "kayfabe.dependencies.pleinfo_provider",
    "get_ranking": "kayfabe.dependencies.ranking_provider",
    "get_records": "kayfabe.dependencies.records_provider",
    "get_result": "kayfabe.dependencies.result_provider",
    "get_title_history": "kayfabe.dependencies.title_history_provider",
    "get_championship": "kayfabe.dependencies.championship_provider",
}


def __getattr__(name: str) -> Any:
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_path)
    return getattr(module, name)
