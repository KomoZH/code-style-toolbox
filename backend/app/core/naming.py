"""命名风格判定与转换（架构 §8：本模块为唯一判定/转换实现）。

支持风格：snake_case | camelCase | PascalCase | UPPER_SNAKE。
转换时保留前导下划线（私有前缀）与成员前缀（如 m_），只改词干部分。
"""

from __future__ import annotations

import re
from typing import List, Optional

STYLE_SNAKE = "snake_case"
STYLE_CAMEL = "camelCase"
STYLE_PASCAL = "PascalCase"
STYLE_UPPER = "UPPER_SNAKE"

VALID_STYLES = (STYLE_SNAKE, STYLE_CAMEL, STYLE_PASCAL, STYLE_UPPER)

_WORD_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")


class Naming:
    """命名风格工具（全部为无状态静态方法）。"""

    @staticmethod
    def split_affixes(name: str) -> tuple[str, str]:
        """拆出前导下划线/成员前缀与词干。

        Returns:
            (prefix, stem)：prefix 为前导下划线或 "m_"/"s_" 等成员前缀。
        """
        prefix = ""
        stem = name
        while stem.startswith("_"):
            prefix += "_"
            stem = stem[1:]
        if not prefix and len(stem) > 2 and stem[:2] in ("m_", "s_") and stem[2].isalpha():
            prefix, stem = stem[:2], stem[2:]
        return prefix, stem

    @staticmethod
    def split_words(stem: str) -> List[str]:
        """把词干切为小写词列表，兼容 snake / camel / Pascal / UPPER。"""
        if not stem:
            return []
        if "_" in stem:
            words = [w for w in stem.split("_") if w]
        else:
            words = _WORD_RE.findall(stem)
        return [w.lower() for w in words if w]

    @staticmethod
    def detect_style(name: str) -> Optional[str]:
        """判定单个标识符的命名风格；无法判定返回 None。

        忽略前导下划线与成员前缀，仅依据词干判定。
        """
        _, stem = Naming.split_affixes(name)
        if not stem:
            return None
        if "_" in stem:
            body = stem.replace("_", "")
            if body.isupper():
                return STYLE_UPPER
            if body.islower() or body.isdigit():
                return STYLE_SNAKE
            return None  # 混合下划线风格，无法归类
        if stem.isupper():
            # 全大写无下划线（如 MAX）视为 UPPER_SNAKE 的退化形态
            return STYLE_UPPER
        if stem[0].islower():
            return STYLE_CAMEL if any(c.isupper() for c in stem) else STYLE_SNAKE
        if stem[0].isupper():
            return STYLE_PASCAL
        return None

    @staticmethod
    def convert(name: str, target: str) -> str:
        """把标识符转换为目标风格，保留前缀；非法目标原样返回。"""
        if target not in VALID_STYLES:
            return name
        prefix, stem = Naming.split_affixes(name)
        words = Naming.split_words(stem)
        if not words:
            return name
        if target == STYLE_SNAKE:
            body = "_".join(words)
        elif target == STYLE_UPPER:
            body = "_".join(words).upper()
        elif target == STYLE_CAMEL:
            body = words[0] + "".join(w.capitalize() for w in words[1:])
        else:  # PascalCase
            body = "".join(w.capitalize() for w in words)
        return prefix + body
