"""Java 重写器：复用令牌流重建逻辑，覆盖 Java 关键字差异。

Java 无预处理器与 const 位置问题（_apply_const_style 对 java 恒无操作，
因为 _CONST_TYPES 中的词在 Java 里不会与 const 相邻出现——Java 无 const 关键字用法，
即使有也会因令牌流不等价触发回退，安全）。
"""

from __future__ import annotations

from typing import List

from app.core.rewriter.cpp_rewriter import TokenRewriter
from app.core.tokenizer import Token
from app.models.profile import Language, Rules


class JavaRewriter(TokenRewriter):
    """Java 令牌流重写器。"""

    language = Language.java
    class_keywords = ("class", "interface", "enum", "record")
    paren_keywords = ("if", "for", "while", "switch", "catch", "synchronized")
    brace_join_keywords = ("else", "catch", "finally", "while")

    def _apply_const_style(self, tokens: List[Token], rules: Rules) -> List[Token]:
        # Java 无 const 位置规则，直接返回
        return tokens
