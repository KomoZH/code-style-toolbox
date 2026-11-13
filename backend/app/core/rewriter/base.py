"""BaseRewriter：黑名单扫描 → 语法校验 → rewrite → 等价 verify → 回退 编排（安全铁律）。

任何重写路径必须经过 safe_convert；禁止任何 API 直接返回未经 verify 的重写结果。
结构性变换（idioms/prefer_early_return/自动折行/header_block）本期不参与自动重写。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

from app.api.schemas import (
    CODE_BLACKLIST,
    CODE_INTERNAL,
    CODE_SYNTAX_INVALID,
    CODE_VERIFY_FAILED,
    ConvertResult,
    DiffOp,
)
from app.core.blacklist import Blacklist
from app.core.differ import compute_diff
from app.core.tokenizer import Tokenizer
from app.core.verifier import Verifier
from app.models.profile import Language, StyleProfile


class BaseRewriter(ABC):
    """重写器抽象基类。"""

    language: Language = Language.python

    @abstractmethod
    def rewrite(self, code: str, profile: StyleProfile) -> Tuple[str, Dict[str, str]]:
        """执行重写，返回 (新代码, 正向重命名映射 旧名→新名)。

        实现只允许做令牌/空白层变换；不得改变任何非空白令牌序列。
        """

    @abstractmethod
    def check_syntax(self, code: str) -> Optional[str]:
        """语法校验；非法返回原因字符串，合法返回 None。"""

    def _verify(self, orig: str, new: str, rename_map: Dict[str, str]) -> bool:
        """等价校验分派。"""
        if self.language == Language.python:
            return Verifier.verify_python(orig, new, rename_map)
        return Verifier.verify_tokens(orig, new, self.language, rename_map)

    def safe_convert(
        self, code: str, filename: str, profile: StyleProfile
    ) -> ConvertResult:
        """安全转换编排（架构 §4.2）。

        黑名单命中 → skipped；语法非法/等价校验失败/异常 → failed；
        任何失败路径 converted == original（P0-6 可回退）。
        """
        # 1. 黑名单检测（C++ 宏/模板特化/预处理条件块）
        reason = Blacklist.scan(code, self.language)
        if reason is not None:
            return ConvertResult(
                filename=filename,
                status="skipped",
                original=code,
                converted=code,
                reason=f"[{CODE_BLACKLIST}] {reason}",
            )

        # 2. 转换前语法校验（P0-6）
        syntax_error = self.check_syntax(code)
        if syntax_error is not None:
            return ConvertResult(
                filename=filename,
                status="failed",
                original=code,
                converted=code,
                reason=f"[{CODE_SYNTAX_INVALID}] 语法校验未通过：{syntax_error}",
            )

        # 3. 重写 + 等价校验
        try:
            new_code, rename_map = self.rewrite(code, profile)
        except Exception as exc:  # noqa: BLE001 - 任何重写异常都必须回退
            return ConvertResult(
                filename=filename,
                status="failed",
                original=code,
                converted=code,
                reason=f"[{CODE_INTERNAL}] 重写过程异常：{exc}",
            )

        if not self._verify(code, new_code, rename_map):
            return ConvertResult(
                filename=filename,
                status="failed",
                original=code,
                converted=code,
                reason=f"[{CODE_VERIFY_FAILED}] 等价校验失败，已保留原始代码",
            )

        diff = [DiffOp(**op) for op in compute_diff(code, new_code)]
        return ConvertResult(
            filename=filename,
            status="converted",
            original=code,
            converted=new_code,
            reason="",
            diff=diff,
            rename_map=rename_map,
        )


class BracketSyntaxMixin:
    """C++/Java 语法校验：令牌流括号配平（错误码 1002）。"""

    language: Language

    def check_syntax(self, code: str) -> Optional[str]:
        tokens = Tokenizer.tokenize(code, self.language)
        return Tokenizer.check_bracket_balance(tokens)
