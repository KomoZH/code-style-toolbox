"""difflib 结构化 diff（架构 §8 Diff 结构约定）。

DiffOp = {tag, old_lines, new_lines}，由 difflib opcodes 转换；
前端 DiffView 按 tag 渲染红/绿/灰，不再二次计算。
"""

from __future__ import annotations

import difflib
from typing import Dict, List


def compute_diff(original: str, converted: str) -> List[Dict]:
    """生成行级结构化 diff。

    Returns:
        DiffOp 列表：{tag: equal|delete|insert|replace,
                      old_lines: [str], new_lines: [str]}
    """
    old_lines = original.splitlines()
    new_lines = converted.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    ops: List[Dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        ops.append(
            {
                "tag": tag,
                "old_lines": old_lines[i1:i2],
                "new_lines": new_lines[j1:j2],
            }
        )
    return ops
