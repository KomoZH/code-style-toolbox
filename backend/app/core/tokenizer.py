"""C++/Java 通用令牌化扫描器（架构 §1.1）。

风格转换只改空白/括号位置/命名等表层形式，令牌流 + 作用域启发足以支撑，
不需要完整语法树。令牌保留行/列位置供提取器统计空白特征。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from app.models.profile import Language


class TokenKind(str, Enum):
    IDENT = "ident"
    NUMBER = "number"
    STRING = "string"
    CHAR = "char"
    COMMENT_LINE = "comment_line"
    COMMENT_BLOCK = "comment_block"
    PREPROC = "preproc"  # 整行预处理指令（仅 cpp 出现）
    OP = "op"  # 运算符（多字符优先）
    PUNCT = "punct"  # 单字符标点 (){}[];,. 等


@dataclass
class Token:
    kind: TokenKind
    value: str
    line: int  # 1-based
    col: int  # 0-based 字符偏移
    end_col: int = 0  # 令牌结束列（多行令牌为首行结束列）

    def __post_init__(self) -> None:
        if not self.end_col:
            self.end_col = self.col + len(self.value)


# 多字符运算符，长串优先匹配
_MULTI_OPS = [
    "<<=", ">>=", "...", "->*", "::", "->", "++", "--", "+=", "-=", "*=", "/=",
    "%=", "&=", "|=", "^=", "==", "!=", "<=", ">=", "&&", "||", "<<", ">>",
    ".*",
]

_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUMBER_RE = re.compile(
    r"(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d[\d']*(?:\.\d[\d']*)?(?:[eE][+-]?\d+)?)[uUlLfF]*"
)

_CPP_KEYWORDS = {
    "if", "else", "for", "while", "do", "switch", "case", "default", "break",
    "continue", "return", "goto", "class", "struct", "union", "enum", "namespace",
    "template", "typename", "using", "typedef", "const", "constexpr", "static",
    "extern", "inline", "virtual", "override", "final", "public", "private",
    "protected", "friend", "operator", "new", "delete", "this", "try", "catch",
    "throw", "noexcept", "auto", "void", "int", "long", "short", "char", "float",
    "double", "bool", "unsigned", "signed", "size_t", "wchar_t", "mutable",
    "volatile", "register", "explicit", "export", "asm", "true", "false", "nullptr",
    "decltype", "concept", "requires", "co_await", "co_yield", "co_return",
}

_JAVA_KEYWORDS = {
    "if", "else", "for", "while", "do", "switch", "case", "default", "break",
    "continue", "return", "class", "interface", "enum", "extends", "implements",
    "package", "import", "public", "private", "protected", "static", "final",
    "abstract", "synchronized", "volatile", "transient", "native", "strictfp",
    "new", "this", "super", "instanceof", "try", "catch", "finally", "throw",
    "throws", "void", "int", "long", "short", "byte", "char", "float", "double",
    "boolean", "var", "record", "sealed", "permits", "yield", "true", "false",
    "null", "assert",
}


class Tokenizer:
    """C++/Java 令牌化扫描器。"""

    @staticmethod
    def keywords(lang: Language) -> set:
        return _JAVA_KEYWORDS if lang == Language.java else _CPP_KEYWORDS

    @staticmethod
    def tokenize(code: str, lang: Language) -> List[Token]:
        """把源码切为令牌流。不做语法校验，词法层面永不失败。"""
        tokens: List[Token] = []
        i = 0
        line = 1
        line_start = 0  # 当前行起始字符下标
        n = len(code)
        at_line_start = True  # 行首（之前只有空白）

        while i < n:
            ch = code[i]
            col = i - line_start

            # 换行
            if ch == "\n":
                i += 1
                line += 1
                line_start = i
                at_line_start = True
                continue
            # 空白
            if ch in " \t\r\f\v":
                i += 1
                continue

            # 预处理指令：行首 # 开头（仅 cpp；java 无预处理）
            if ch == "#" and at_line_start and lang == Language.cpp:
                j = i
                # 处理反斜杠续行
                while j < n:
                    nl = code.find("\n", j)
                    if nl == -1:
                        j = n
                        break
                    if code[nl - 1] == "\\":
                        j = nl + 1
                    else:
                        j = nl
                        break
                text = code[i:j].rstrip()
                tokens.append(Token(TokenKind.PREPROC, text, line, col, col + len(text)))
                # 更新行号（续行可能跨行）
                line += text.count("\n")
                if "\n" in text:
                    line_start = i + text.rfind("\n") + 1
                i = i + len(text)
                at_line_start = False
                continue

            at_line_start = False

            # 行注释
            if code.startswith("//", i):
                j = code.find("\n", i)
                j = n if j == -1 else j
                text = code[i:j].rstrip()
                tokens.append(Token(TokenKind.COMMENT_LINE, text, line, col, col + len(text)))
                i = j
                continue

            # 块注释
            if code.startswith("/*", i):
                end = code.find("*/", i + 2)
                end = n - 2 if end == -1 else end
                text = code[i : end + 2]
                tokens.append(Token(TokenKind.COMMENT_BLOCK, text, line, col, col + len(text)))
                line += text.count("\n")
                if "\n" in text:
                    line_start = i + text.rfind("\n") + 1
                i = end + 2
                continue

            # 字符串 / 字符 / 原始字符串 / Java 文本块
            if ch == '"' or ch == "'":
                if code.startswith('"""', i) and lang == Language.java:
                    end = code.find('"""', i + 3)
                    end = n - 3 if end == -1 else end
                    text = code[i : end + 3]
                    tokens.append(Token(TokenKind.STRING, text, line, col, col + len(text)))
                    line += text.count("\n")
                    if "\n" in text:
                        line_start = i + text.rfind("\n") + 1
                    i = end + 3
                    continue
                quote = ch
                j = i + 1
                while j < n:
                    if code[j] == "\\":
                        j += 2
                        continue
                    if code[j] == quote or code[j] == "\n":
                        break
                    j += 1
                j = min(j + 1, n)
                text = code[i:j]
                kind = TokenKind.STRING if quote == '"' else TokenKind.CHAR
                tokens.append(Token(kind, text, line, col, col + len(text)))
                i = j
                continue
            # C++ 原始字符串 R"(...)"
            if lang == Language.cpp and ch == "R" and code.startswith('R"', i):
                m = re.match(r'R"([A-Za-z0-9_]*)\(', code[i:])
                if m:
                    delim = m.group(1)
                    close = ")" + delim + '"'
                    end = code.find(close, i + m.end())
                    end = n - len(close) if end == -1 else end
                    text = code[i : end + len(close)]
                    tokens.append(Token(TokenKind.STRING, text, line, col, col + len(text)))
                    line += text.count("\n")
                    if "\n" in text:
                        line_start = i + text.rfind("\n") + 1
                    i = end + len(close)
                    continue

            # Java 注解
            if ch == "@" and lang == Language.java:
                m = _IDENT_RE.match(code, i + 1)
                if m:
                    text = "@" + m.group(0)
                    tokens.append(Token(TokenKind.IDENT, text, line, col, col + len(text)))
                    i = m.end()
                    continue

            # 标识符 / 关键字
            m = _IDENT_RE.match(code, i)
            if m:
                text = m.group(0)
                tokens.append(Token(TokenKind.IDENT, text, line, col, col + len(text)))
                i = m.end()
                continue

            # 数字
            m = _NUMBER_RE.match(code, i)
            if m and m.group(0):
                text = m.group(0)
                tokens.append(Token(TokenKind.NUMBER, text, line, col, col + len(text)))
                i = m.end()
                continue

            # 多字符运算符
            matched = False
            for op in _MULTI_OPS:
                if code.startswith(op, i):
                    tokens.append(Token(TokenKind.OP, op, line, col, col + len(op)))
                    i += len(op)
                    matched = True
                    break
            if matched:
                continue

            # 单字符：运算符或标点
            if ch in "+-*/%=&|^!~<>?:":
                tokens.append(Token(TokenKind.OP, ch, line, col, col + 1))
            else:
                tokens.append(Token(TokenKind.PUNCT, ch, line, col, col + 1))
            i += 1

        return tokens

    @staticmethod
    def strip_trivia(tokens: List[Token]) -> List[Token]:
        """剔除注释令牌（等价校验用；预处理指令保留，因其影响语义）。"""
        return [
            t
            for t in tokens
            if t.kind not in (TokenKind.COMMENT_LINE, TokenKind.COMMENT_BLOCK)
        ]

    @staticmethod
    def check_bracket_balance(tokens: List[Token]) -> Optional[str]:
        """括号配平校验（错误码 1002 用）；不配平时返回原因字符串。"""
        pairs = {")": "(", "]": "[", "}": "{"}
        opens = set(pairs.values())
        stack: List[Token] = []
        for tok in tokens:
            if tok.kind not in (TokenKind.PUNCT, TokenKind.OP):
                continue
            if tok.value in opens:
                stack.append(tok)
            elif tok.value in pairs:
                if not stack or stack[-1].value != pairs[tok.value]:
                    return f"第 {tok.line} 行存在不配平的括号 '{tok.value}'"
                stack.pop()
        if stack:
            tok = stack[-1]
            return f"第 {tok.line} 行括号 '{tok.value}' 未闭合"
        return None
