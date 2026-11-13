"""Python 风格提取器：基于 ast（命名/类型提示/docstring）+ tokenize（缩进/空白/空行/注释）。

语法非法的样例跳过；全部非法时回落默认规则（meta 置信度为 0）。
"""

from __future__ import annotations

import ast
import io
import tokenize as py_tokenize
from math import gcd
from typing import List

from app.core.extractor.base import BaseExtractor, Sample, VoteBag
from app.core.naming import Naming
from app.models.profile import Language, StyleProfile

# 参与空白统计的双目/赋值运算符
_BINARY_OPS = {
    "=", "+", "-", "*", "/", "//", "%", "**", "==", "!=", "<", ">", "<=", ">=",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", ":=", "->",
}


class PythonExtractor(BaseExtractor):
    """Python 规则归纳器。"""

    language = Language.python

    def extract(self, samples: List[Sample], profile_name: str) -> StyleProfile:
        bag = VoteBag()
        total_lines = 0
        for sample in samples:
            lines = sample.content.splitlines()
            total_lines += len(lines)
            try:
                tree = ast.parse(sample.content)
            except (SyntaxError, ValueError):
                continue  # 非法样例不参与统计
            self._ast_stats(tree, bag)
            self._token_stats(sample.content, lines, bag, tree)
        return self._build_profile(bag, profile_name, total_lines)

    # ------------------------------------------------------------------
    # ast 层统计：命名 / 类型提示 / docstring
    # ------------------------------------------------------------------

    def _ast_stats(self, tree: ast.Module, bag: VoteBag) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not (node.name.startswith("__") and node.name.endswith("__")):
                    style = Naming.detect_style(node.name)
                    bag.add("naming.functions", style, node.name)
                    prefix = "_" if node.name.startswith("_") else ""
                    bag.add("naming.private_prefix", prefix, node.name)
                # 类型提示覆盖率（逐函数投票）
                args = node.args
                all_args = args.posonlyargs + args.args + args.kwonlyargs
                annotated = sum(1 for a in all_args if a.annotation is not None)
                has_hints = bool(all_args) and (
                    annotated == len(all_args) or node.returns is not None
                )
                bag.add("declarations.python_type_hints", has_hints, node.name)
            elif isinstance(node, ast.ClassDef):
                style = Naming.detect_style(node.name)
                bag.add("naming.classes", style, node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if not isinstance(target, ast.Name):
                        continue
                    name = target.id
                    if name.startswith("__") and name.endswith("__"):
                        continue
                    _, stem = Naming.split_affixes(name)
                    if stem.isupper() and any(c.isalpha() for c in stem):
                        bag.add("naming.constants", Naming.detect_style(name), name)
                    else:
                        bag.add("naming.variables", Naming.detect_style(name), name)

        # docstring 风格
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node)
                if not doc:
                    continue
                fmt = self._docstring_format(doc)
                bag.add("comments.docstring_format", fmt, doc.strip().splitlines()[0][:40])

    @staticmethod
    def _docstring_format(doc: str) -> str:
        if ":param" in doc or ":return" in doc:
            return "sphinx"
        if "Parameters" in doc and "----------" in doc:
            return "numpy"
        if "Args:" in doc or "Returns:" in doc or "Raises:" in doc:
            return "google"
        return "none"

    # ------------------------------------------------------------------
    # tokenize 层统计：缩进 / 空白 / 空行 / 注释
    # ------------------------------------------------------------------

    def _token_stats(
        self, code: str, lines: List[str], bag: VoteBag, tree: ast.Module
    ) -> None:
        try:
            tokens = list(
                py_tokenize.generate_tokens(io.StringIO(code).readline)
            )
        except (py_tokenize.TokenError, IndentationError):
            return

        indent_widths: List[int] = []
        significant = [t for t in tokens if t.type not in (
            py_tokenize.INDENT, py_tokenize.DEDENT, py_tokenize.NEWLINE,
            py_tokenize.NL, py_tokenize.COMMENT, py_tokenize.ENCODING,
            py_tokenize.ENDMARKER,
        )]

        # -- 缩进 -------------------------------------------------------
        for tok in tokens:
            if tok.type == py_tokenize.INDENT:
                text = tok.string
                if "\t" in text:
                    bag.add("indent.style", "tab", repr(text))
                else:
                    bag.add("indent.style", "space", repr(text))
                    indent_widths.append(len(text))
        if indent_widths:
            unit = 0
            for w in indent_widths:
                unit = gcd(unit, w)
            if unit in (2, 4, 8):
                bag.add("indent.size", unit)

        # -- 运算符 / 逗号空白 ------------------------------------------
        for idx, tok in enumerate(significant):
            if tok.type != py_tokenize.OP:
                continue
            row = tok.start[0] - 1
            if row < 0 or row >= len(lines):
                continue
            line_text = lines[row]
            if tok.string in _BINARY_OPS and tok.string not in ("->",):
                # 跳过单行首尾，避免越界
                col_s, col_e = tok.start[1], tok.end[1]
                if col_s > 0 and col_e < len(line_text):
                    left = line_text[col_s - 1] == " "
                    right = line_text[col_e] == " "
                    bag.add(
                        "spacing.space_around_operators",
                        left and right,
                        line_text.strip()[:40],
                    )
            elif tok.string == ",":
                col_e = tok.end[1]
                if col_e < len(line_text) and line_text[col_e] != "\n":
                    has_space = line_text[col_e] == " "
                    bag.add("spacing.space_after_comma", has_space, line_text.strip()[:40])

        # -- 行尾空白 -----------------------------------------------------
        if lines:
            trailing = sum(1 for ln in lines if ln != ln.rstrip())
            bag.add(
                "spacing.trim_trailing_whitespace",
                trailing <= max(1, len(lines) // 20),
            )

        # -- 行尾注释间距 --------------------------------------------------
        code_end_by_line = {}
        for tok in significant:
            code_end_by_line[tok.end[0]] = tok.end[1]
        for tok in tokens:
            if tok.type != py_tokenize.COMMENT:
                continue
            row, col = tok.start
            if row in code_end_by_line and code_end_by_line[row] < col:
                spaces = col - code_end_by_line[row]
                bag.add("comments.inline_min_spaces", min(spaces, 4), tok.string[:30])

        # -- 空行 ---------------------------------------------------------
        blank_runs: List[int] = []
        run = 0
        for ln in lines:
            if ln.strip() == "":
                run += 1
            else:
                if run:
                    blank_runs.append(run)
                run = 0
        if blank_runs:
            bag.add("blank_lines.max_consecutive", min(max(blank_runs), 4))

        # 顶层函数/类之间空行
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.lineno
                if node.decorator_list:
                    start = node.decorator_list[0].lineno
                blanks = 0
                row = start - 2  # 转为 0-based 上一行
                while row >= 0 and lines[row].strip() == "":
                    blanks += 1
                    row -= 1
                if row >= 0:  # 文件第一个定义前的空行不算
                    bag.add("blank_lines.between_functions", min(blanks, 4))

        # import 块后空行
        import_end = 0
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_end = max(import_end, node.end_lineno or node.lineno)
            elif import_end:
                break
        if import_end and import_end < len(lines):
            blanks = 0
            row = import_end  # 0-based 下一行
            while row < len(lines) and lines[row].strip() == "":
                blanks += 1
                row += 1
            bag.add("blank_lines.after_imports", min(blanks, 4))
