"""语言识别（架构 §1.1 裁决 2）。

扩展名优先；无扩展名/未知扩展名时用关键字与语法特征打分器。
置信度低于阈值返回 language="unknown" 且 manual_required=True，
前端允许用户手动指定语言。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.models.profile import Language

# 文件扩展名映射（架构 §8）
EXTENSION_MAP = {
    ".py": Language.python,
    ".cpp": Language.cpp,
    ".cc": Language.cpp,
    ".cxx": Language.cpp,
    ".h": Language.cpp,
    ".hpp": Language.cpp,
    ".java": Language.java,
}

MANUAL_THRESHOLD = 0.5  # 低于该置信度要求手动指定


@dataclass
class DetectResult:
    """语言识别结果。"""

    language: str  # python | cpp | java | unknown
    confidence: float
    manual_required: bool = False
    scores: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 特征规则：(正则, 权重)
# ---------------------------------------------------------------------------

_PY_FEATURES = [
    (r"^\s*def\s+\w+\s*\(", 3),
    (r"^\s*(from\s+\w+\s+)?import\s+\w+", 2),
    (r"^\s*class\s+\w+.*:\s*$", 2),
    (r"\bself\b", 2),
    (r":\s*$", 1),
    (r"^\s*#", 1),
    (r"\bprint\s*\(", 1),
    (r"\bNone\b|\bTrue\b|\bFalse\b", 1),
]

_CPP_FEATURES = [
    (r"^\s*#include\s*[<\"]", 4),
    (r"\bstd::", 2),
    (r"\bcout\b|\bcin\b|\bendl\b", 2),
    (r"\btemplate\s*<", 2),
    (r"->", 1),
    (r"\bnamespace\b", 2),
    (r"\bnullptr\b", 2),
    (r"\bvoid\s+\w+\s*\(", 1),
]

_JAVA_FEATURES = [
    (r"\bpublic\s+(final\s+)?class\b", 4),
    (r"\bSystem\.out\.", 3),
    (r"\bpublic\s+static\s+void\s+main\b", 3),
    (r"\bprivate\s+\w+\s+\w+\s*;", 1),
    (r"\bimplements\b|\bextends\b", 1),
    (r"\b@Override\b", 2),
    (r"\bString\s+\w+\s*[;=)]", 1),
    (r"^\s*package\s+[\w.]+\s*;", 3),
]


def _score(code: str, rules: list) -> float:
    total = 0.0
    for pattern, weight in rules:
        hits = len(re.findall(pattern, code, flags=re.MULTILINE))
        if hits:
            total += weight * min(hits, 5)
    return total


class LanguageDetector:
    """语言识别器。"""

    @staticmethod
    def detect(filename: Optional[str], code: str) -> DetectResult:
        """识别代码语言。扩展名命中时直接高置信度返回。"""
        if filename:
            dot = filename.rfind(".")
            if dot >= 0:
                ext = filename[dot:].lower()
                if ext in EXTENSION_MAP:
                    lang = EXTENSION_MAP[ext]
                    return DetectResult(language=lang.value, confidence=0.99)

        scores = {
            Language.python.value: _score(code, _PY_FEATURES),
            Language.cpp.value: _score(code, _CPP_FEATURES),
            Language.java.value: _score(code, _JAVA_FEATURES),
        }
        best = max(scores, key=lambda k: scores[k])
        total = sum(scores.values())
        if total <= 0 or scores[best] <= 0:
            return DetectResult(
                language="unknown", confidence=0.0, manual_required=True, scores=scores
            )
        confidence = scores[best] / total
        # 领先幅度不足时同样要求手动确认
        sorted_scores = sorted(scores.values(), reverse=True)
        margin = (sorted_scores[0] - sorted_scores[1]) / (sorted_scores[0] or 1)
        confidence = round(min(confidence, 0.5 + margin / 2), 3)
        manual = confidence < MANUAL_THRESHOLD
        return DetectResult(
            language="unknown" if manual else best,
            confidence=confidence,
            manual_required=manual,
            scores=scores,
        )
