"""C++ 重写器：令牌流重建（括号风格/缩进/空白/命名/const 位置）。

重建策略：丢弃全部原始空白，按 profile 规则从令牌流重新排版；
等价性由 Verifier.verify_tokens（忽略空白/注释的令牌流 + const 归一化）保证，
任何意外不一致都会触发自动回退（安全铁律）。

本模块同时提供 TokenRewriter 供 JavaRewriter 复用。
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from app.core.naming import Naming
from app.core.rewriter.base import BaseRewriter, BracketSyntaxMixin
from app.core.tokenizer import Token, TokenKind, Tokenizer
from app.core.verifier import _CONST_TYPES
from app.models.profile import Language, Rules, StyleProfile

# 初始化列表大括号的前置上下文（不套用括号风格换行）
_INIT_BRACE_PREV = {"=", "(", ",", "{", "[", "return"}

# 双目运算符集合（空白规则适用）
_BINARY_OPS = {
    "=", "+", "-", "*", "/", "%", "==", "!=", "<=", ">=", "&&", "||",
    "<<", ">>", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "&", "|", "^", "?",
}

# 一元前缀运算符上下文：这些前置令牌出现时的 +/-/*/!/~/& 为一元
_UNARY_PREV_VALUES = {
    "(", "[", "{", ",", ";", "=", "+", "-", "*", "/", "%", "==", "!=", "<", ">",
    "<=", ">=", "&&", "||", "!", "~", "?", ":", "return", "case", "throw",
    "sizeof", "new", "delete",
}

_TYPE_WORDS = _CONST_TYPES | {"string", "var"}


class TokenRewriter(BracketSyntaxMixin, BaseRewriter):
    """C++/Java 共享的令牌流重建器。"""

    language = Language.cpp
    class_keywords: Tuple[str, ...] = ("class", "struct", "enum", "union")
    paren_keywords: Tuple[str, ...] = ("if", "for", "while", "switch", "catch")
    # `} x` 同行连接关键字（k_and_r 风格）
    brace_join_keywords: Tuple[str, ...] = ("else", "catch", "while")
    # 语句级起始关键字（出现在行首时与前行按词法 spacing）
    skip_prefix_tokens: Tuple[str, ...] = (".", "->", "::")

    # ------------------------------------------------------------------
    # 重命名映射
    # ------------------------------------------------------------------

    def _build_rename_map(
        self, tokens: List[Token], rules: Rules
    ) -> Dict[str, str]:
        naming = rules.naming
        keywords = Tokenizer.keywords(self.language)
        significant = Tokenizer.strip_trivia(tokens)

        defined: Dict[str, str] = {}
        blocked: Set[str] = set()  # 属性访问/限定名位置出现过的标识符不改
        all_idents: Set[str] = set()

        n = len(significant)
        for i, tok in enumerate(significant):
            if tok.kind != TokenKind.IDENT:
                continue
            value = tok.value
            all_idents.add(value)
            prev = significant[i - 1] if i > 0 else None
            nxt = significant[i + 1] if i + 1 < n else None

            if prev is not None and prev.value in self.skip_prefix_tokens:
                blocked.add(value)
                continue
            if nxt is not None and nxt.value == "::":
                blocked.add(value)
                continue

            # 类名定义点
            if prev is not None and prev.value in self.class_keywords:
                if not (prev.value == "enum" and value == "class"):
                    defined.setdefault(value, "classes")
                continue
            if value in keywords or value.startswith("@"):
                continue

            # 函数定义点：TYPE name ( ... ) { / : / const
            if (
                nxt is not None
                and nxt.value == "("
                and prev is not None
                and self._is_typeish(prev, keywords)
                and self._paren_followed_by_body(significant, i + 1)
            ):
                defined.setdefault(value, "functions")
                continue

            # 常量
            _, stem = Naming.split_affixes(value)
            if len(stem) > 1 and stem.isupper() and any(c.isalpha() for c in stem):
                defined.setdefault(value, "constants")
                continue

            # 变量定义点：TYPE name (= | ; | [ | , | ))，后两者覆盖函数形参
            if (
                nxt is not None
                and nxt.value in ("=", ";", "[", ",", ")")
                and prev is not None
                and self._is_typeish(prev, keywords)
            ):
                defined.setdefault(value, "variables")

        style_by_category = {
            "variables": naming.variables,
            "functions": naming.functions,
            "classes": naming.classes,
            "constants": naming.constants,
        }
        rename_map: Dict[str, str] = {}
        for name, category in defined.items():
            if name in blocked:
                continue
            new_name = Naming.convert(name, style_by_category[category])
            if new_name == name:
                continue
            if new_name in keywords:
                continue
            # 碰撞保护
            if new_name in all_idents and rename_map.get(new_name, new_name) == new_name:
                continue
            rename_map[name] = new_name
        return rename_map

    @staticmethod
    def _is_typeish(tok: Token, keywords: Set[str]) -> bool:
        if tok.value in _TYPE_WORDS:
            return True
        if tok.value in ("*", "&", ">", "::"):
            return True
        if tok.kind == TokenKind.IDENT and tok.value:
            if tok.value in keywords:
                return False
            return tok.value[0].isupper()
        return False

    @staticmethod
    def _paren_followed_by_body(tokens: List[Token], open_idx: int) -> bool:
        depth = 0
        for j in range(open_idx, len(tokens)):
            value = tokens[j].value
            if value == "(":
                depth += 1
            elif value == ")":
                depth -= 1
                if depth == 0:
                    after = tokens[j + 1].value if j + 1 < len(tokens) else ""
                    return after in ("{", ":", "const", "throws", "noexcept")
        return False

    # ------------------------------------------------------------------
    # const east/west 预处理（仅 cpp；架构 §5-3，令牌级安全）
    # ------------------------------------------------------------------

    def _apply_const_style(self, tokens: List[Token], rules: Rules) -> List[Token]:
        target = rules.declarations.cpp_const_style
        result: List[Token] = []
        i = 0
        while i < len(tokens):
            cur = tokens[i]
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            if nxt is not None and nxt.kind == TokenKind.IDENT:
                if (
                    target == "east"
                    and cur.value == "const"
                    and nxt.value in _CONST_TYPES
                ):
                    result.append(nxt)
                    result.append(cur)
                    i += 2
                    continue
                if (
                    target == "west"
                    and cur.value in _CONST_TYPES
                    and nxt.value == "const"
                ):
                    result.append(nxt)
                    result.append(cur)
                    i += 2
                    continue
            result.append(cur)
            i += 1
        return result

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def rewrite(self, code: str, profile: StyleProfile) -> Tuple[str, Dict[str, str]]:
        tokens = Tokenizer.tokenize(code, self.language)
        rename_map = self._build_rename_map(tokens, profile.rules)
        tokens = self._apply_const_style(tokens, profile.rules)
        rendered, applied = self._render(tokens, profile.rules, rename_map)
        return rendered, {k: v for k, v in rename_map.items() if k in applied}

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def _render(
        self, tokens: List[Token], rules: Rules, rename_map: Dict[str, str]
    ) -> Tuple[str, Set[str]]:
        indent_cfg = rules.indent
        brace_cfg = rules.brace_style
        spacing = rules.spacing
        min_comment_gap = rules.comments.inline_min_spaces

        unit = "\t" if indent_cfg.style == "tab" else " " * indent_cfg.size

        lines: List[str] = []
        cur = ""
        depth = 0
        paren_depth = 0
        template_depth = 0
        brace_stack: List[bool] = []  # True=代码块, False=初始化列表
        tight_next = False  # 下一个令牌前不加空格
        applied: Set[str] = set()

        keywords = Tokenizer.keywords(self.language)

        def flush() -> None:
            nonlocal cur
            if cur.strip():
                lines.append(cur.rstrip())
            cur = ""

        def indent() -> str:
            return unit * depth

        def put(text: str, space_before: bool) -> None:
            nonlocal cur
            if not cur.strip():
                cur = indent() + text
            elif space_before and not tight_next and not cur.endswith((" ", "\t")):
                cur = cur.rstrip() + " " + text
            else:
                cur += text

        def put_word(word: str) -> None:
            """放置词法单元，按上下文补空格。"""
            nonlocal cur, tight_next
            if not cur.strip():
                cur = indent() + word
            elif tight_next:
                cur += word  # 行尾可能已带空格（逗号/二元运算符后）
            elif cur.endswith((" ", "\t")):
                cur = cur.rstrip() + " " + word
            else:
                tail = cur.rstrip()
                last = tail[-1:]
                if last in ("(", "[", "<", "@", ".") or tail.endswith(("::", "->")):
                    cur = tail + word
                else:
                    cur = tail + " " + word
            tight_next = False

        i = 0
        n = len(tokens)
        while i < n:
            tok = tokens[i]
            value = tok.value
            nxt = tokens[i + 1] if i + 1 < n else None

            # -- 预处理 / 注释 ------------------------------------------
            if tok.kind == TokenKind.PREPROC:
                flush()
                lines.append(value.rstrip())
                i += 1
                tight_next = False
                continue
            if tok.kind == TokenKind.COMMENT_LINE:
                if cur.strip():
                    cur = cur.rstrip() + " " * min_comment_gap + value
                    flush()
                else:
                    cur = indent() + value
                    flush()
                i += 1
                tight_next = False
                continue
            if tok.kind == TokenKind.COMMENT_BLOCK:
                flush()
                for block_line in value.split("\n"):
                    lines.append(indent() + block_line.rstrip())
                i += 1
                tight_next = False
                continue

            # 重命名（跳过成员访问/限定名位置）
            prev_value = tokens[i - 1].value if i > 0 else ""
            if (
                tok.kind == TokenKind.IDENT
                and value in rename_map
                and prev_value not in self.skip_prefix_tokens
            ):
                value = rename_map[value]
                applied.add(tokens[i].value)

            # -- 大括号 ---------------------------------------------------
            if value == "{":
                is_init = prev_value in _INIT_BRACE_PREV
                if is_init:
                    put("{", space_before=True)
                    brace_stack.append(False)
                    tight_next = False
                else:
                    if brace_cfg.style == "allman":
                        flush()
                        cur = indent() + "{"
                        flush()
                    else:  # k_and_r
                        if cur.strip():
                            cur = cur.rstrip() + " {"
                        else:
                            cur = indent() + "{"
                        flush()
                    brace_stack.append(True)
                    depth += 1
                    tight_next = False
                i += 1
                continue

            if value == "}":
                is_block = brace_stack.pop() if brace_stack else True
                if not is_block:
                    put("}", space_before=not tight_next)
                    tight_next = False
                    i += 1
                    continue
                depth = max(0, depth - 1)
                flush()
                cur = indent() + "}"
                # 类/结构体/初始化收尾：`};` 同行
                if nxt is not None and nxt.value == ";":
                    cur += ";"
                    flush()
                    i += 2
                    tight_next = False
                    continue
                # k_and_r：`} else` / `} catch` / `} while` 同行
                if (
                    nxt is not None
                    and nxt.value in self.brace_join_keywords
                    and brace_cfg.style == "k_and_r"
                ):
                    cur += " " + nxt.value
                    i += 2  # 消费连接关键字
                    tight_next = False
                    continue
                flush()
                i += 1
                tight_next = False
                continue

            # -- 语句分隔 ---------------------------------------------------
            if value == ";":
                if paren_depth > 0:
                    cur = cur.rstrip() + ";"
                    if rules.spacing.space_after_comma:
                        cur += " "
                else:
                    cur = cur.rstrip() + ";"
                    flush()
                tight_next = False
                i += 1
                continue

            if value == ",":
                cur = cur.rstrip() + ","
                if spacing.space_after_comma:
                    cur += " "
                tight_next = True  # 逗号后空格已写入，下一令牌不再加空格
                i += 1
                continue

            # -- 圆括号 / 方括号 --------------------------------------------
            if value == "(":
                if not cur.strip():
                    cur = indent() + "("
                elif prev_value in self.paren_keywords:
                    cur = cur.rstrip() + (" (" if brace_cfg.space_before_paren else "(")
                elif tight_next or cur.endswith((" ", "\t")):
                    cur += "("
                elif prev_value in keywords:
                    cur = cur.rstrip() + " ("  # return (x) / sizeof (x)
                else:
                    cur = cur.rstrip() + "("  # 函数调用/定义/分组紧贴
                paren_depth += 1
                tight_next = True
                i += 1
                continue

            if value == ")":
                paren_depth = max(0, paren_depth - 1)
                cur = cur.rstrip() + ")"
                tight_next = False
                i += 1
                continue

            if value == "[":
                cur += "[" if cur.strip() else indent() + "["
                tight_next = True
                i += 1
                continue

            if value == "]":
                cur = cur.rstrip() + "]"
                tight_next = False
                i += 1
                continue

            # -- 紧密运算符 -------------------------------------------------
            if value in (".", "->", "::", ".*", "->*", "@"):
                cur = cur.rstrip() + value
                tight_next = True
                i += 1
                continue

            # -- 模板尖括号 -------------------------------------------------
            if value == "<" and self._looks_like_template(tokens, i):
                cur = cur.rstrip() + "<"
                template_depth += 1
                tight_next = True
                i += 1
                continue
            if template_depth > 0 and value == ">":
                cur = cur.rstrip() + ">"
                template_depth -= 1
                tight_next = False
                i += 1
                continue
            if template_depth > 0 and value == ">>":
                cur = cur.rstrip() + ">>"
                template_depth = max(0, template_depth - 2)
                tight_next = False
                i += 1
                continue

            # -- 自增自减 ---------------------------------------------------
            if value in ("++", "--"):
                postfix = bool(re.match(r"[\w\)\]]", cur.rstrip()[-1:]))
                if postfix:
                    cur = cur.rstrip() + value
                    tight_next = False
                else:
                    put_word(value)
                    tight_next = True
                i += 1
                continue

            # -- 标签冒号 ---------------------------------------------------
            if value == ":" and prev_value in (
                "case", "default", "public", "private", "protected",
            ):
                cur = cur.rstrip() + ":"
                flush()
                tight_next = False
                i += 1
                continue

            # -- 运算符 -----------------------------------------------------
            if tok.kind == TokenKind.OP:
                unary = (
                    prev_value in _UNARY_PREV_VALUES
                    or prev_value == ""
                    or not cur.strip()
                    # 声明语境：TYPE *name / TYPE &name（int& x / std::string& s）
                    or (value in ("*", "&") and (
                        prev_value in _TYPE_WORDS or prev_value in (">", "::")
                    ))
                )
                if value in ("!", "~") or (unary and value in ("+", "-", "*", "&")):
                    # 一元前缀：行内前一令牌为词时补空格，后紧贴操作数
                    if not cur.strip():
                        cur = indent() + value
                    elif cur.endswith((" ", "\t")):
                        cur += value
                    elif re.match(r"[\w\)\]]", cur.rstrip()[-1:]):
                        cur = cur.rstrip() + " " + value
                    else:
                        cur = cur.rstrip() + value
                    tight_next = True
                elif value in _BINARY_OPS:
                    if spacing.space_around_operators:
                        cur = cur.rstrip() + " " + value + " "
                        tight_next = True
                    else:
                        cur = cur.rstrip() + value
                        tight_next = True
                else:
                    # 其余单字符运算符按双目处理
                    if spacing.space_around_operators:
                        cur = cur.rstrip() + " " + value + " "
                    else:
                        cur = cur.rstrip() + value
                    tight_next = True
                i += 1
                continue

            # -- 词法单元（IDENT/NUMBER/STRING/CHAR） ------------------------
            put_word(value)
            i += 1

        flush()
        text = "\n".join(lines)
        text = self._postprocess_blank_lines(text, rules)
        return text, applied

    # ------------------------------------------------------------------
    # 渲染辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_template(tokens: List[Token], lt_idx: int) -> bool:
        """启发判断 `<` 是否为模板/泛型实参起始。"""
        prev = tokens[lt_idx - 1] if lt_idx > 0 else None
        if prev is None or prev.kind != TokenKind.IDENT:
            return False
        if prev.value in ("if", "while", "for", "return", "case", "sizeof"):
            return False
        depth = 0
        scan = 0
        for j in range(lt_idx, min(lt_idx + 40, len(tokens))):
            value = tokens[j].value
            if value in (";", "{", "}", "(", ")", "=", "&&", "||"):
                return False
            if value == "<":
                depth += 1
            elif value == ">":
                depth -= 1
                if depth == 0:
                    return True
            elif value == ">>":
                depth -= 2
                if depth <= 0:
                    return True
            scan += 1
        return False

    # ------------------------------------------------------------------
    # 空行后处理
    # ------------------------------------------------------------------

    def _postprocess_blank_lines(self, text: str, rules: Rules) -> str:
        blank_cfg = rules.blank_lines
        lines = text.split("\n")
        out: List[str] = []

        def is_include_block_line(s: str) -> bool:
            st = s.strip()
            return st.startswith("import ") or st.startswith("#include")

        def indent_units(s: str) -> int:
            """行的逻辑缩进层级（用于识别类体层级的方法间隔）。"""
            ws = s[: len(s) - len(s.lstrip(" \t"))]
            if not ws:
                return 0
            if "\t" in ws:
                return ws.count("\t")
            return len(ws) // max(rules.indent.size, 1)

        for idx, line in enumerate(lines):
            stripped = line.strip()
            prev = out[-1] if out else ""
            # 代码块结束后补空行：顶层用 between_functions，嵌套成员函数间至少 1 行
            if (
                stripped
                and out
                and prev.strip() in ("}", "};")
                and stripped not in ("}", "};")
                and not re.match(r"^(else|catch|finally|while)\b", stripped)
            ):
                top_level = not prev.startswith((" ", "\t")) and not line.startswith(
                    (" ", "\t")
                )
                if top_level:
                    count = blank_cfg.between_functions
                elif indent_units(prev) == 1 and indent_units(line) == 1:
                    count = 1  # 类体内成员函数之间
                else:
                    count = 0  # 函数内部的嵌套块后不强行加空行
                count = min(count, blank_cfg.max_consecutive)
                for _ in range(count):
                    out.append("")
            # import/#include 块结束后补空行
            elif (
                stripped
                and is_include_block_line(prev)
                and not is_include_block_line(line)
                and prev.strip().endswith((";", ">"))
            ):
                for _ in range(blank_cfg.after_imports):
                    out.append("")
            out.append(line.rstrip() if rules.spacing.trim_trailing_whitespace else line)

        # 折叠连续空行至 max_consecutive
        result: List[str] = []
        run = 0
        for line in out:
            if line.strip() == "":
                run += 1
                if run > blank_cfg.max_consecutive:
                    continue
            else:
                run = 0
            result.append(line)

        final = "\n".join(result).strip("\n")
        return final + "\n" if final else ""


class CppRewriter(TokenRewriter):
    """C++ 令牌流重写器。"""

    language = Language.cpp
    class_keywords = ("class", "struct", "enum", "union")
    paren_keywords = ("if", "for", "while", "switch", "catch")
    brace_join_keywords = ("else", "catch", "while")
