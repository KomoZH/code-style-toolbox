"""C++/Java 不安全构造黑名单检测（架构 §1.1 裁决 1，错误码 2001）。

命中即跳过文件（status=skipped）并返回明确原因，绝不尝试重写。
Java 词法层可安全处理，无黑名单项。
"""

from __future__ import annotations

import re
from typing import Optional

from app.models.profile import Language

# (正则, 原因说明)
_CPP_RULES = [
    (
        re.compile(r"^\s*#\s*define\s+\w+\s*\(", re.MULTILINE),
        "检测到函数式宏 (#define X(...))，宏展开无法保证令牌级等价，已跳过",
    ),
    (
        re.compile(r"\btemplate\s*<\s*>", re.MULTILINE),
        "检测到模板特化 (template<>)，特化语义超出令牌层重写安全边界，已跳过",
    ),
    (
        re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif)\b", re.MULTILINE),
        "检测到预处理条件块 (#if/#ifdef/#ifndef/#elif)，条件分支无法安全重写，已跳过",
    ),
]

_JAVA_RULES: list = []


class Blacklist:
    """不安全构造扫描器。"""

    @staticmethod
    def scan(code: str, lang: Language) -> Optional[str]:
        """扫描源码；命中黑名单返回原因字符串，否则返回 None。"""
        rules = _JAVA_RULES if lang == Language.java else _CPP_RULES
        for pattern, reason in rules:
            if pattern.search(code):
                return reason
        return None
