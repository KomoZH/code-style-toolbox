"""pytest 公共配置：把 backend/ 加入 sys.path，并提供共用辅助与 fixtures。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_EXAMPLE_FILES = {
    "python": "sample_python/messy_demo.py",
    "cpp": "sample_cpp/messy_demo.cpp",
    "java": "sample_java/MessyDemo.java",
}


def read_example(language: str) -> Tuple[str, str]:
    """读取内置示例文件，返回 (文件名, 内容)。"""
    path = EXAMPLES_DIR / _EXAMPLE_FILES[language]
    return path.name, path.read_text(encoding="utf-8")


@pytest.fixture()
def python_example() -> Tuple[str, str]:
    return read_example("python")


@pytest.fixture()
def cpp_example() -> Tuple[str, str]:
    return read_example("cpp")


@pytest.fixture()
def java_example() -> Tuple[str, str]:
    return read_example("java")


@pytest.fixture()
def make_profile():
    """StyleProfile 工厂：可按需覆盖规则字段。"""
    from app.models.profile import StyleProfile

    def _make(language: str = "python", **rule_overrides) -> "StyleProfile":
        profile = StyleProfile(name="test_profile", language=language)
        for group, fields in rule_overrides.items():
            sub = getattr(profile.rules, group)
            for key, value in fields.items():
                setattr(sub, key, value)
        return profile

    return _make
