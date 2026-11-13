"""C++ 风格提取器：基于令牌化扫描器的规则归纳（多数派投票 + 置信度）。

本模块同时提供 TokenBasedExtractor 供 JavaExtractor 复用——C++/Java 的
风格特征统计逻辑一致，仅关键字表与少量规则差异。
"""

from __future__ import annotations

import re
from math import gcd
from typing import List, Optional, Sequence, Tuple

from app.core.extractor.base import BaseExtractor, Sample, VoteBag
from app.core.naming import Naming
from app.core.tokenizer import Token, TokenKind, Tokenizer
from app.core.verifier import _CONST_TYPES
from app.models.profile import Language, StyleProfile

# 参与空白统计的运算符
_BINARY_OPS = {
    "=", "+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=",
    "+=", "-=", "*=", "/=", "&&", "||", "<<", ">>",
}

# 大括号初始化上下文（这些前置令牌说明 { 是初始化列表而非代码块）
_INIT_BRACE_PREV = {"=", "(", ",", "{", "[", "return"}

_MEMBER_PREFIX_RE = re.compile(r"^m_[A-Za-z0-9_]+$")


class TokenBasedExtractor(BaseExtractor):
    """C++/Java 共享的令牌层风格统计逻辑。"""

    language = Language.cpp
    #: 类名引导关键字
    class_keywords: Tuple[str, ...] = ("class", "struct", "enum")
    #: 圆括号前空格统计关键字
    paren_keywords: Tuple[str, ...] = ("if", "for", "while", "switch", "catch")
    #: 函数定义排除前缀（这些关键字后的 ( 不是函数定义）
    call_keywords: frozenset = frozenset(
        {"if", "for", "while", "switch", "catch", "return", "sizeof", "new",
         "delete", "else", "do", "case"}
    )

    def extract(self, samples: List[Sample], profile_name: str) -> StyleProfile:
        bag = VoteBag()
        total_lines = 0
        for sample in samples:
            lines = sample.content.splitlines()
            total_lines += len(lines)
            tokens = Tokenizer.tokenize(sample.content, self.language)
            self._stats(sample.content, lines, tokens, bag)
        return self._build_profile(bag, profile_name, total_lines)

    # ------------------------------------------------------------------
    # 统计主流程
    # ------------------------------------------------------------------

    def _stats(
        self, code: str, lines: List[str], tokens: List[Token], bag: VoteBag
    ) -> None:
        significant = Tokenizer.strip_trivia(tokens)
        self._brace_stats(significant, bag)
        self._spacing_stats(significant, bag)
        self._indent_stats(lines, significant, bag)
        self._naming_stats(significant, bag)
        self._comment_stats(lines, tokens, significant, bag)
        self._blank_line_stats(lines, significant, bag)
        self._extra_stats(significant, bag)

    def _extra_stats(self, significant: List[Token], bag: VoteBag) -> None:
        """子类扩展点（C++: const 位置 / 成员前缀）。"""

    # ------------------------------------------------------------------
    # 各项规则统计
    # ------------------------------------------------------------------

    def _brace_stats(self, tokens: Sequence[Token], bag: VoteBag) -> None:
        for i, tok in enumerate(tokens):
            if tok.value != "{" or tok.kind != TokenKind.PUNCT:
                continue
            prev = tokens[i - 1] if i > 0 else None
            if prev is not None and prev.value in _INIT_BRACE_PREV:
                continue  # 初始化列表不参与括号风格统计
            if prev is not None and prev.line == tok.line:
                bag.add("brace_style.style", "k_and_r", "{")
            else:
                bag.add("brace_style.style", "allman", "{")

        for i, tok in enumerate(tokens[:-1]):
            if tok.kind != TokenKind.IDENT or tok.value not in self.paren_keywords:
                continue
            nxt = tokens[i + 1]
            if nxt.value == "(" and nxt.line == tok.line:
                bag.add(
                    "brace_style.space_before_paren",
                    nxt.col > tok.end_col,
                    f"{tok.value} (" if nxt.col > tok.end_col else f"{tok.value}(",
                )

    def _spacing_stats(self, tokens: Sequence[Token], bag: VoteBag) -> None:
        for i in range(1, len(tokens) - 1):
            prev, tok, nxt = tokens[i - 1], tokens[i], tokens[i + 1]
            if tok.kind == TokenKind.OP and tok.value in _BINARY_OPS:
                if prev.line == tok.line and nxt.line == tok.line:
                    left = tok.col > prev.end_col
                    right = nxt.col > tok.end_col
                    bag.add("spacing.space_around_operators", left and right, tok.value)
            elif tok.value == "," and nxt.line == tok.line:
                bag.add("spacing.space_after_comma", nxt.col > tok.end_col, ",")

    def _indent_stats(
        self, lines: List[str], tokens: Sequence[Token], bag: VoteBag
    ) -> None:
        widths: List[int] = []
        for ln in lines:
            if not ln.strip():
                continue
            stripped = ln.lstrip(" \t")
            if stripped == ln:
                continue  # 无缩进
            leading = ln[: len(ln) - len(stripped)]
            if "\t" in leading:
                bag.add("indent.style", "tab", repr(leading))
            else:
                bag.add("indent.style", "space", repr(leading))
                widths.append(len(leading))
        if widths:
            unit = 0
            for w in widths:
                unit = gcd(unit, w)
            if unit in (2, 4, 8):
                bag.add("indent.size", unit)

    def _naming_stats(self, tokens: Sequence[Token], bag: VoteBag) -> None:
        keywords = Tokenizer.keywords(self.language)
        n = len(tokens)
        for i, tok in enumerate(tokens):
            if tok.kind != TokenKind.IDENT:
                continue
            value = tok.value
            prev = tokens[i - 1] if i > 0 else None
            nxt = tokens[i + 1] if i + 1 < n else None

            # 类名：class/struct/enum 之后的标识符
            if prev is not None and prev.value in self.class_keywords:
                if prev.value == "enum" and value == "class":
                    continue
                bag.add("naming.classes", Naming.detect_style(value), value)
                continue

            if value in keywords:
                continue

            # 函数定义：TYPE name ( ... ) { / : / const
            if (
                nxt is not None
                and nxt.value == "("
                and prev is not None
                and self._is_typeish(prev, tokens, i)
                and prev.value not in self.call_keywords
                and self._paren_followed_by_body(tokens, i + 1)
            ):
                bag.add("naming.functions", Naming.detect_style(value), value)
                continue

            # 常量：全大写标识符
            _, stem = Naming.split_affixes(value)
            if len(stem) > 1 and stem.isupper() and any(c.isalpha() for c in stem):
                bag.add("naming.constants", Naming.detect_style(value), value)
                continue

            # 变量：TYPE name (= | ; | [)
            if (
                nxt is not None
                and nxt.value in ("=", ";", "[")
                and prev is not None
                and self._is_typeish(prev, tokens, i)
                and prev.value not in self.call_keywords
            ):
                bag.add("naming.variables", Naming.detect_style(value), value)

    def _is_typeish(self, tok: Token, tokens: Sequence[Token], idx: int) -> bool:
        """判断令牌是否像类型：primitive / PascalCase 标识符 / std:: 限定 / * & > 结尾。"""
        if tok.value in _CONST_TYPES or tok.value in ("string", "auto", "var"):
            return True
        if tok.value in ("*", "&", ">", "::"):
            return True
        if tok.kind == TokenKind.IDENT and tok.value:
            if tok.value in Tokenizer.keywords(self.language):
                return False
            # 模板参数后跟的标识符（如 vector<int> x）经由 ">" 已覆盖；
            # PascalCase 视为自定义类型
            return tok.value[0].isupper()
        return False

    @staticmethod
    def _paren_followed_by_body(tokens: Sequence[Token], open_idx: int) -> bool:
        """从 `(` 起配对扫描，若配对 `)` 后接 `{`/`:`/`const` 则视为函数定义。"""
        depth = 0
        for j in range(open_idx, len(tokens)):
            value = tokens[j].value
            if value == "(":
                depth += 1
            elif value == ")":
                depth -= 1
                if depth == 0:
                    after = tokens[j + 1].value if j + 1 < len(tokens) else ""
                    return after in ("{", ":", "const")
        return False

    def _comment_stats(
        self,
        lines: List[str],
        tokens: Sequence[Token],
        significant: Sequence[Token],
        bag: VoteBag,
    ) -> None:
        code_end_by_line = {}
        for tok in significant:
            code_end_by_line[tok.line] = tok.end_col
        for tok in tokens:
            if tok.kind != TokenKind.COMMENT_LINE:
                continue
            end = code_end_by_line.get(tok.line)
            if end is not None and end < tok.col:
                spaces = tok.col - end
                bag.add("comments.inline_min_spaces", min(spaces, 4), tok.value[:30])

    def _blank_line_stats(
        self, lines: List[str], tokens: Sequence[Token], bag: VoteBag
    ) -> None:
        # 最大连续空行
        runs: List[int] = []
        run = 0
        for ln in lines:
            if ln.strip() == "":
                run += 1
            else:
                if run:
                    runs.append(run)
                run = 0
        if runs:
            bag.add("blank_lines.max_consecutive", min(max(runs), 4))

        # 顶层函数/类之间空行：深度归 0 的 `}` 与下一个令牌之间
        depth = 0
        last_close_line: Optional[int] = None
        for tok in tokens:
            if tok.kind == TokenKind.PREPROC:
                continue
            if tok.value == "{":
                depth += 1
            elif tok.value == "}":
                depth = max(0, depth - 1)
                if depth == 0:
                    last_close_line = tok.line
            elif last_close_line is not None and tok.line > last_close_line:
                blanks = tok.line - last_close_line - 1
                bag.add("blank_lines.between_functions", min(blanks, 4))
                last_close_line = None

        # import / #include 块后空行
        self._after_imports_stats(lines, tokens, bag)

    def _after_imports_stats(
        self, lines: List[str], tokens: Sequence[Token], bag: VoteBag
    ) -> None:
        block_end = 0
        for tok in tokens:
            if tok.kind == TokenKind.PREPROC and tok.value.lstrip("# ").startswith("include"):
                block_end = max(block_end, tok.line)
            elif block_end and tok.line > block_end + 1:
                break
        if block_end and block_end < len(lines):
            blanks = 0
            row = block_end  # 0-based 下一行
            while row < len(lines) and lines[row].strip() == "":
                blanks += 1
                row += 1
            bag.add("blank_lines.after_imports", min(blanks, 4))


class CppExtractor(TokenBasedExtractor):
    """C++ 规则归纳器（追加 const 位置与成员前缀统计）。"""

    language = Language.cpp
    class_keywords = ("class", "struct", "enum", "union")

    def _extra_stats(self, significant: List[Token], bag: VoteBag) -> None:
        for i, tok in enumerate(significant):
            if tok.kind != TokenKind.IDENT:
                continue
            nxt = significant[i + 1] if i + 1 < len(significant) else None
            # const west：`const T`；east：`T const`
            if tok.value == "const" and nxt is not None and nxt.value in _CONST_TYPES:
                bag.add("declarations.cpp_const_style", "west", f"const {nxt.value}")
            elif tok.value in _CONST_TYPES and nxt is not None and nxt.value == "const":
                bag.add("declarations.cpp_const_style", "east", f"{tok.value} const")
            # 成员前缀 m_
            if _MEMBER_PREFIX_RE.match(tok.value):
                bag.add("naming.member_prefix", "m_", tok.value)
