"""等价校验（架构 §1.1 裁决 1，错误码 2002）。

- Python：对原始 AST 施加正向标识符重命名映射后，与重写结果的 ast.dump 比对。
- C++/Java：忽略空白/注释后的令牌流一致 + 重命名映射合法；
  const east/west 位置差异按规则归一化后再比对。
"""

from __future__ import annotations

import ast
import re
from typing import Dict, List

from app.core.tokenizer import Token, TokenKind, Tokenizer
from app.models.profile import Language

_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")

# const 归一化时可与 const 交换位置的类型词
_CONST_TYPES = {
    "void", "int", "long", "short", "char", "float", "double", "bool",
    "unsigned", "signed", "size_t", "wchar_t", "auto", "char16_t", "char32_t",
}


class _RenameTransformer(ast.NodeTransformer):
    """按正向映射（旧名 → 新名）重写 AST 中的定义点与引用点标识符。

    与 PythonRewriter 的改写范围保持一致：Name / 函数名 / 类名 / 参数名；
    属性访问（Attribute.attr）、关键字参数名、导入名不在重写范围内。
    """

    def __init__(self, rename_map: Dict[str, str]) -> None:
        self._map = rename_map

    def _r(self, name: str) -> str:
        return self._map.get(name, name)

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self._r(node.id)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.name = self._r(node.name)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        node.name = self._r(node.name)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        node.name = self._r(node.name)
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._r(node.arg)
        self.generic_visit(node)
        return node


class Verifier:
    """等价校验器（全部为无状态静态方法）。"""

    # -- Python -----------------------------------------------------------

    @staticmethod
    def verify_python(orig: str, new: str, rename_map: Dict[str, str]) -> bool:
        """AST 等价校验：orig 经正向重命名后的 ast.dump 必须与 new 一致。

        任一侧语法非法即判失败（调用方据此回退）。
        """
        try:
            orig_tree = ast.parse(orig)
            new_tree = ast.parse(new)
        except (SyntaxError, ValueError, MemoryError):
            return False
        if rename_map:
            orig_tree = _RenameTransformer(rename_map).visit(orig_tree)
            ast.fix_missing_locations(orig_tree)
        return ast.dump(orig_tree) == ast.dump(new_tree)

    # -- C++ / Java -------------------------------------------------------

    @staticmethod
    def _normalize_const(tokens: List[Token], lang: Language) -> List[str]:
        """归一化 const east/west 差异：`T const` 与 `const T` 统一为 `const T`。"""
        values = [t.value for t in tokens]
        if lang != Language.cpp:
            return values
        result: List[str] = []
        i = 0
        while i < len(values):
            cur = values[i]
            nxt = values[i + 1] if i + 1 < len(values) else None
            if nxt == "const" and cur in _CONST_TYPES:
                result.append("const")
                result.append(cur)
                i += 2
                continue
            result.append(cur)
            i += 1
        return result

    @staticmethod
    def verify_tokens(
        orig: str, new: str, lang: Language, rename_map: Dict[str, str]
    ) -> bool:
        """令牌流等价校验。

        1. 重命名映射合法性：目标名必须为合法标识符且不与原令牌冲突成关键字。
        2. orig 令牌流（剔除注释）施加正向重命名并归一化 const 后，
           必须与 new 令牌流（剔除注释）完全一致。
        """
        keywords = Tokenizer.keywords(lang)
        for old, new_name in rename_map.items():
            if not _IDENT_RE.match(new_name):
                return False
            if new_name in keywords:
                return False

        orig_tokens = Tokenizer.strip_trivia(Tokenizer.tokenize(orig, lang))
        new_tokens = Tokenizer.strip_trivia(Tokenizer.tokenize(new, lang))

        mapped: List[Token] = []
        for tok in orig_tokens:
            if tok.kind == TokenKind.IDENT and tok.value in rename_map:
                mapped.append(
                    Token(tok.kind, rename_map[tok.value], tok.line, tok.col)
                )
            else:
                mapped.append(tok)

        left = Verifier._normalize_const(mapped, lang)
        right = Verifier._normalize_const(new_tokens, lang)
        return left == right
