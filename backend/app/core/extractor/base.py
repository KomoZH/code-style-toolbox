"""BaseExtractor 抽象基类 + 置信度聚合（架构 §3.2 类图）。

提取采用"逐规则多数派投票"：每条规则收集若干投票（value, example），
取多数派为规则值；置信度 = 多数派票数 / 总票数；
冲突（次多数派占比 ≥ 30%）时打 conflict 标记。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.config import LOW_CONFIDENCE, LOW_SAMPLES, LOW_TOTAL_LINES
from app.models.profile import Language, Rules, StyleProfile

CONFLICT_RATIO = 0.3
MAX_EXAMPLES = 3  # 每条规则最多保留的样例片段数


@dataclass
class Sample:
    """一份待提取的代码样例。"""

    filename: str
    content: str


@dataclass
class Vote:
    """一条规则投票。"""

    value: Any
    example: str = ""


class VoteBag:
    """按规则路径收集投票并聚合出规则值与元数据。"""

    def __init__(self) -> None:
        self._votes: Dict[str, List[Vote]] = {}

    def add(self, path: str, value: Any, example: str = "") -> None:
        """记录一票。path 形如 "naming.variables"。"""
        if value is None:
            return
        self._votes.setdefault(path, []).append(Vote(value=value, example=example))

    def merge(self, path: str, default: Any, total_lines: int) -> Tuple[Any, Dict]:
        """聚合一条规则：返回 (规则值, RuleMeta dict)。

        置信度 = 多数派占比；无投票时回落 default 且 confidence=0。
        冲突判定：次多数派占比 ≥ 30%。
        """
        votes = self._votes.get(path, [])
        if not votes:
            meta = {
                "confidence": 0.0,
                "samples": 0,
                "examples": [],
                "conflict": False,
                "low_evidence": True,
            }
            return default, meta

        counter: Counter = Counter(str(v.value) for v in votes)
        value_by_key: Dict[str, Any] = {}
        examples_by_key: Dict[str, List[str]] = {}
        for v in votes:
            key = str(v.value)
            value_by_key[key] = v.value
            if v.example and len(examples_by_key.setdefault(key, [])) < MAX_EXAMPLES:
                examples_by_key[key].append(v.example)

        ranked = counter.most_common()
        top_key, top_count = ranked[0]
        total = len(votes)
        confidence = round(top_count / total, 3)
        conflict = len(ranked) > 1 and ranked[1][1] / total >= CONFLICT_RATIO

        meta = {
            "confidence": confidence,
            "samples": total,
            "examples": examples_by_key.get(top_key, []),
            "conflict": conflict,
            # 软提示（裁决 3）：样本不足 / 总行数过少 → 前端醒目标识
            "low_evidence": confidence < LOW_CONFIDENCE
            or total < LOW_SAMPLES
            or total_lines < LOW_TOTAL_LINES,
        }
        return value_by_key[top_key], meta


class BaseExtractor(ABC):
    """风格提取器抽象基类。"""

    language: Language = Language.python

    @abstractmethod
    def extract(self, samples: List[Sample], profile_name: str) -> StyleProfile:
        """从样例列表归纳风格规则集（含 meta 置信度）。"""

    # -- 子类共用 ----------------------------------------------------------

    def _build_profile(
        self,
        bag: VoteBag,
        profile_name: str,
        total_lines: int,
        defaults: Optional[Rules] = None,
    ) -> StyleProfile:
        """把投票结果落地为 StyleProfile（规则值 + meta 同构子树）。"""
        base = defaults or Rules()
        rules_dump = base.model_dump()
        meta: Dict[str, Dict[str, Any]] = {}

        for path in bag_paths(bag):
            value, meta_dict = bag.merge(path, get_path(rules_dump, path), total_lines)
            set_path(rules_dump, path, value)
            group, key = path.split(".", 1)
            meta.setdefault(group, {})[key] = meta_dict

        profile = StyleProfile(
            name=profile_name,
            language=self.language,
            source="extracted",
            rules=Rules.model_validate(rules_dump),
            meta=meta,
        )
        # 总行数软提示写入 meta 顶层，供前端整体提示（裁决 3）
        profile.meta["_sample_lines"] = {
            "total": total_lines,
            "low_evidence": total_lines < LOW_TOTAL_LINES,
        }
        return profile


def bag_paths(bag: VoteBag) -> List[str]:
    return sorted(bag._votes.keys())


def get_path(tree: Dict, path: str) -> Any:
    node: Any = tree
    for part in path.split("."):
        node = node[part]
    return node


def set_path(tree: Dict, path: str, value: Any) -> None:
    parts = path.split(".")
    node = tree
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value
