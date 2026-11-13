"""Python 重写器：tokenize 级重写（架构 §1.1：不用 ast.unparse，避免丢注释/排版）。

两遍流水线（每遍都可被等价校验兜底）：
1. Pass 1 —— 标识符重命名 + 缩进单位转换（保留原始行内空白）；
2. Pass 2 —— 运算符/逗号空白规范化（跳过字符串/注释掩码区）+ 空行规范化。

重命名范围（架构 §5-4）：函数/类/赋值目标/参数定义点 + 同名 NAME 令牌引用；
导入名、属性访问（obj.attr）、关键字参数名不改写，避免改变 API 调用语义。
"""

from __future__ import annotations

import ast
import io
import re
import tokenize as py_tokenize
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from app.core.naming import Naming
from app.core.rewriter.base import BaseRewriter
from app.models.profile import Language, StyleProfile

# ---------------------------------------------------------------------------
# Pass 2 空白正则
# ---------------------------------------------------------------------------

_RE_SPACE_BEFORE_COMMA = re.compile(r" +,")
_RE_COMMA_NO_SPACE = re.compile(r",(?=[^\s\)\]\}])")
_RE_COMMA_MULTI = re.compile(r", {2,}")

_MULTI_OPS = (
    "==", "!=", "<=", ">=", "//=", "**=", "<<=", ">>=",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", ":=", "->",
)
_RE_MULTI_OP_SPACED = re.compile(
    r"(?<![<>=!:+\-*/%&|^]) *(" + "|".join(re.escape(op) for op in _MULTI_OPS) + r") *"
)
_RE_POW_BINARY = re.compile(r"(?<=[\w\)\]]) *(\*\*) *(?=[\w(\[{])")
_RE_ASSIGN = re.compile(r"(?<![<>=!:+\-*/%&|^]) *= *(?![=>])")
_RE_BINARY = re.compile(r"(?<=[\w\)\]]) *([+\-*/%<>]) *(?=[\w(\[{])")

_TOP_DEF_RE = re.compile(r"^(?:async\s+def|def|class)\b")
_TOP_IMPORT_RE = re.compile(r"^(?:import|from)\b")

_SKIP_RENAME_NAMES = {"self", "cls"}


class PythonRewriter(BaseRewriter):
    """Python tokenize 级重写器。"""

    language = Language.python

    def check_syntax(self, code: str) -> Optional[str]:
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return f"第 {exc.lineno} 行：{exc.msg}"
        except (ValueError, MemoryError) as exc:
            return str(exc)
        return None

    def rewrite(self, code: str, profile: StyleProfile) -> Tuple[str, Dict[str, str]]:
        tree = ast.parse(code)  # check_syntax 已保证可解析
        rename_map = self._build_rename_map(tree, code, profile)
        intermediate, used = self._pass1_rename_and_indent(code, profile, rename_map)
        final = self._pass2_spacing_and_blank_lines(intermediate, profile)
        return final, {k: v for k, v in rename_map.items() if k in used}

    # ------------------------------------------------------------------
    # 重命名映射构建
    # ------------------------------------------------------------------

    def _build_rename_map(
        self, tree: ast.Module, code: str, profile: StyleProfile
    ) -> Dict[str, str]:
        naming = profile.rules.naming
        defined: Dict[str, str] = {}  # name -> 规则类别
        excluded: Set[str] = set(_SKIP_RENAME_NAMES)

        for node in ast.walk(tree):
            # -- 排除集合：属性名 / 关键字参数名 / 导入名 / match 捕获名 ----
            if isinstance(node, ast.Attribute):
                excluded.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                excluded.add(node.arg)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    excluded.add(alias.name)
                    if alias.asname:
                        excluded.add(alias.asname)
            elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                excluded.add(node.name)
            elif isinstance(node, ast.MatchMapping) and node.rest:
                excluded.add(node.rest)

            # -- 定义点收集 ------------------------------------------------
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not (node.name.startswith("__") and node.name.endswith("__")):
                    defined.setdefault(node.name, "functions")
                self._collect_args(node.args, defined)
            elif isinstance(node, ast.Lambda):
                self._collect_args(node.args, defined)
            elif isinstance(node, ast.ClassDef):
                defined.setdefault(node.name, "classes")
            elif isinstance(node, ast.ExceptHandler) and node.name:
                defined.setdefault(node.name, "variables")
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                _, stem = Naming.split_affixes(node.id)
                category = (
                    "constants"
                    if len(stem) > 1 and stem.isupper() and any(c.isalpha() for c in stem)
                    else "variables"
                )
                defined.setdefault(node.id, category)

        # 文件内全部标识符集合（碰撞检测用）
        all_names: Set[str] = set()
        for tok in py_tokenize.generate_tokens(io.StringIO(code).readline):
            if tok.type == py_tokenize.NAME:
                all_names.add(tok.string)

        style_by_category = {
            "variables": naming.variables,
            "functions": naming.functions,
            "classes": naming.classes,
            "constants": naming.constants,
        }
        rename_map: Dict[str, str] = {}
        for name, category in defined.items():
            if name in excluded:
                continue
            target = style_by_category[category]
            new_name = Naming.convert(name, target)
            if new_name == name:
                continue
            # 碰撞保护：目标名已存在且自身不会被改走 → 放弃该条重命名
            if new_name in all_names and rename_map.get(new_name, new_name) == new_name:
                continue
            rename_map[name] = new_name
        return rename_map

    @staticmethod
    def _collect_args(args: ast.arguments, defined: Dict[str, str]) -> None:
        all_args = args.posonlyargs + args.args + args.kwonlyargs
        if args.vararg:
            all_args.append(args.vararg)
        if args.kwarg:
            all_args.append(args.kwarg)
        for arg in all_args:
            defined.setdefault(arg.arg, "variables")

    # ------------------------------------------------------------------
    # Pass 1：重命名 + 缩进单位转换
    # ------------------------------------------------------------------

    def _pass1_rename_and_indent(
        self, code: str, profile: StyleProfile, rename_map: Dict[str, str]
    ) -> Tuple[str, Set[str]]:
        lines = code.splitlines()
        indent_cfg = profile.rules.indent
        unit = "\t" if indent_cfg.style == "tab" else " " * indent_cfg.size

        tokens = list(py_tokenize.generate_tokens(io.StringIO(code).readline))

        depth_stack: List[str] = []
        bracket_depth = 0
        row_depth: Dict[int, int] = {}  # 行号 -> 逻辑缩进深度（括号外首令牌行）
        edits: Dict[int, List[Tuple[int, int, str]]] = defaultdict(list)
        used: Set[str] = set()
        prev_significant = ""
        seen_rows: Set[int] = set()
        comment_rows: List[int] = []

        trivia = {
            py_tokenize.INDENT, py_tokenize.DEDENT, py_tokenize.NEWLINE,
            py_tokenize.NL, py_tokenize.ENCODING, py_tokenize.ENDMARKER,
        }

        for tok in tokens:
            if tok.type == py_tokenize.INDENT:
                depth_stack.append(tok.string)
                continue
            if tok.type == py_tokenize.DEDENT:
                if depth_stack:
                    depth_stack.pop()
                continue
            if tok.type in trivia:
                continue

            row, col = tok.start
            if row not in seen_rows:
                seen_rows.add(row)
                if bracket_depth == 0:
                    row_depth[row] = len(depth_stack)
                    if tok.type == py_tokenize.COMMENT:
                        # 注释行不产生 INDENT：暂记，稍后对齐到后续代码行深度
                        comment_rows.append(row)

            if tok.type == py_tokenize.OP:
                if tok.string in ("(", "[", "{"):
                    bracket_depth += 1
                elif tok.string in (")", "]", "}"):
                    bracket_depth = max(0, bracket_depth - 1)
            elif (
                tok.type == py_tokenize.NAME
                and tok.string in rename_map
                and prev_significant != "."
            ):
                edits[row].append((col, tok.end[1], rename_map[tok.string]))
                used.add(tok.string)

            if tok.type != py_tokenize.COMMENT:
                prev_significant = tok.string

        # 注释行缩进对齐：注释通常描述紧随其后的代码块，若下一代码行更深则对齐
        code_rows = sorted(r for r in row_depth if r not in comment_rows)
        for crow in comment_rows:
            deeper = [r for r in code_rows if r > crow]
            if deeper and row_depth[deeper[0]] > row_depth[crow]:
                row_depth[crow] = row_depth[deeper[0]]

        # 重建：缩进替换 + 从右往左应用重命名编辑
        out: List[str] = []
        for idx, line in enumerate(lines, start=1):
            new_line = line
            if idx in row_depth and new_line.strip():
                new_line = unit * row_depth[idx] + new_line.lstrip(" \t")
            for start, end, text in sorted(edits.get(idx, []), reverse=True):
                # 缩进替换后列偏移可能变化：重命名编辑基于原始列，
                # 因此先算缩进增量再平移
                delta = 0
                if idx in row_depth:
                    old_ws = len(line) - len(line.lstrip(" \t"))
                    new_ws = len(unit * row_depth[idx])
                    delta = new_ws - old_ws
                s, e = start + delta, end + delta
                if 0 <= s <= e <= len(new_line):
                    new_line = new_line[:s] + text + new_line[e:]
            out.append(new_line)

        result = "\n".join(out)
        if code.endswith("\n"):
            result += "\n"
        return result, used

    # ------------------------------------------------------------------
    # Pass 2：运算符/逗号空白 + 空行规范化
    # ------------------------------------------------------------------

    def _pass2_spacing_and_blank_lines(self, code: str, profile: StyleProfile) -> str:
        spacing = profile.rules.spacing
        blank_cfg = profile.rules.blank_lines
        min_comment_gap = profile.rules.comments.inline_min_spaces

        lines = code.split("\n")
        protected_rows, masks = self._build_line_masks(code)

        # -- 空白规范化 ---------------------------------------------------
        processed: List[str] = []
        for idx, line in enumerate(lines, start=1):
            if idx in protected_rows or not line.strip():
                processed.append(line.rstrip() if spacing.trim_trailing_whitespace else line)
                continue
            new_line = self._apply_spacing_masked(
                line, masks.get(idx, []), spacing, min_comment_gap
            )
            if spacing.trim_trailing_whitespace:
                new_line = new_line.rstrip()
            processed.append(new_line)

        # -- 空行规范化 ----------------------------------------------------
        return self._normalize_blank_lines(processed, protected_rows, blank_cfg)

    @staticmethod
    def _build_line_masks(
        self_code: str,
    ) -> Tuple[Set[int], Dict[int, List[Tuple[int, int]]]]:
        """构建每行掩码。

        Returns:
            (protected_rows, masks)：
            - protected_rows：被多行字符串覆盖的整行集合（空白与空行处理均跳过）；
            - masks：行号 -> [(start, end)] 单行字符串/注释区间，空白改写跳过。
        """
        protected: Set[int] = set()
        masks: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        try:
            tokens = list(py_tokenize.generate_tokens(io.StringIO(self_code).readline))
        except (py_tokenize.TokenError, IndentationError):
            return protected, masks
        for tok in tokens:
            if tok.type == py_tokenize.STRING:
                if tok.end[0] > tok.start[0]:
                    for row in range(tok.start[0], tok.end[0] + 1):
                        protected.add(row)
                else:
                    masks[tok.start[0]].append((tok.start[1], tok.end[1]))
            elif tok.type == py_tokenize.COMMENT:
                masks[tok.start[0]].append((tok.start[1], tok.end[1]))
        return protected, masks

    @classmethod
    def _apply_spacing_masked(
        cls,
        line: str,
        masks: List[Tuple[int, int]],
        spacing,
        min_comment_gap: int,
    ) -> str:
        """按掩码分段应用空白规则，掩码区（字符串/注释）逐字保留。"""
        if not masks:
            return cls._apply_spacing(line, spacing)
        masks = sorted(masks)
        parts: List[str] = []
        cursor = 0
        for start, end in masks:
            start = max(start, cursor)
            if start > cursor:
                parts.append(cls._apply_spacing(line[cursor:start], spacing))
            comment = line[start:end]
            # 行尾注释：保证注释前最少空格（P0 规则 inline_min_spaces）
            if comment.startswith("#") and parts and parts[-1].strip():
                parts[-1] = parts[-1].rstrip()
                parts.append(" " * min_comment_gap)
            parts.append(comment)
            cursor = end
        if cursor < len(line):
            parts.append(cls._apply_spacing(line[cursor:], spacing))
        return "".join(parts)

    @staticmethod
    def _apply_spacing(line: str, spacing) -> str:
        """对单行应用空白规则（该行已确认不含字符串/注释掩码）。"""
        text = line
        if spacing.space_after_comma:
            text = _RE_SPACE_BEFORE_COMMA.sub(",", text)
            text = _RE_COMMA_MULTI.sub(", ", text)
            text = _RE_COMMA_NO_SPACE.sub(", ", text)
        else:
            text = _RE_SPACE_BEFORE_COMMA.sub(",", text)
            text = re.sub(r", +", ",", text)

        if spacing.space_around_operators:
            text = _RE_MULTI_OP_SPACED.sub(r" \1 ", text)
            text = _RE_POW_BINARY.sub(r" \1 ", text)
            text = _RE_ASSIGN.sub(" = ", text)
            text = _RE_BINARY.sub(r" \1 ", text)
        else:
            text = _RE_MULTI_OP_SPACED.sub(r"\1", text)
            text = _RE_POW_BINARY.sub(r"\1", text)
            text = _RE_ASSIGN.sub("=", text)
            text = _RE_BINARY.sub(r"\1", text)
        # 折叠因替换产生的连续空格（不动行首缩进）
        stripped = text.lstrip(" \t")
        indent = text[: len(text) - len(stripped)]
        stripped = re.sub(r" {2,}", " ", stripped)
        return indent + stripped

    @staticmethod
    def _normalize_blank_lines(lines, protected_rows: Set[int], blank_cfg) -> str:
        """按规则重建空行：顶层定义间距、import 块后间距、最大连续空行。"""
        out: List[str] = []
        run = 0  # 待落盘的连续空行数
        prev_content = ""  # 上一条非空行内容

        def flush_run(required: int) -> None:
            for _ in range(required):
                out.append("")

        for idx, line in enumerate(lines, start=1):
            is_blank = line.strip() == "" and idx not in protected_rows
            if is_blank:
                run += 1
                continue

            stripped = line.lstrip(" \t")
            top_level = line == stripped  # 无缩进
            has_prior_content = bool(out)

            if not has_prior_content:
                run = 0  # 文件开头不留空行
            elif top_level and _TOP_DEF_RE.match(stripped):
                run = blank_cfg.between_functions
            elif _TOP_DEF_RE.match(stripped):
                # 类内方法/嵌套定义之间至少 1 空行（类声明行后首个方法除外）
                if not prev_content.rstrip().endswith(":"):
                    run = max(min(run, blank_cfg.max_consecutive), 1)
            elif top_level and prev_content.startswith((" ", "\t")):
                # 顶层语句紧跟在缩进块（函数体结束）之后：按顶层定义间距
                run = blank_cfg.between_functions
            elif (
                top_level
                and not _TOP_IMPORT_RE.match(stripped)
                and _TOP_IMPORT_RE.match(prev_content.strip())
            ):
                run = blank_cfg.after_imports
            else:
                run = min(run, blank_cfg.max_consecutive)

            flush_run(run)
            run = 0
            out.append(line)
            prev_content = line

        result = "\n".join(out).rstrip("\n")
        return result + "\n" if result else ""
