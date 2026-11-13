"""请求/响应 DTO（架构 §3.3，与前端 types.ts 一一对应）。

统一响应包装：{code, message, data}；code=0 成功，非 0 即失败（错误码见架构 §8）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 错误码（架构 §8）
# ---------------------------------------------------------------------------

CODE_OK = 0
CODE_DETECT_FAILED = 1001  # 语言识别失败（需手动指定）
CODE_SYNTAX_INVALID = 1002  # 输入语法非法 / 括号不配平
CODE_BLACKLIST = 2001  # 命中不安全构造黑名单
CODE_VERIFY_FAILED = 2002  # 等价校验失败
CODE_PROFILE_ERROR = 3001  # 规则集不存在 / schema 校验失败
CODE_INTERNAL = 5000  # 未预期服务端错误


class ApiResponse(BaseModel):
    code: int = CODE_OK
    message: str = "ok"
    data: Any = None


def ok(data: Any = None, message: str = "ok") -> Dict[str, Any]:
    return {"code": CODE_OK, "message": message, "data": data}


def err(code: int, message: str, data: Any = None) -> Dict[str, Any]:
    return {"code": code, "message": message, "data": data}


# ---------------------------------------------------------------------------
# 语言识别 / 提取
# ---------------------------------------------------------------------------


class DetectRequest(BaseModel):
    code: str
    filename: Optional[str] = None


class DetectResultDTO(BaseModel):
    language: str = "unknown"  # python | cpp | java | unknown
    confidence: float = 0.0
    manual_required: bool = False
    scores: Dict[str, float] = Field(default_factory=dict)


class SampleItem(BaseModel):
    filename: str = "snippet.txt"
    content: str


class ExtractRequest(BaseModel):
    samples: List[SampleItem]
    language: Optional[str] = None  # 手动指定（识别失败时前端重发）
    profile_name: str = "untitled"


# ---------------------------------------------------------------------------
# 转换
# ---------------------------------------------------------------------------


class ConvertItem(BaseModel):
    filename: Optional[str] = None
    content: str


class ConvertRequest(BaseModel):
    profile_id: str
    items: List[ConvertItem]
    language: Optional[str] = None  # 手动指定，覆盖逐条识别


class DiffOp(BaseModel):
    """结构化 diff 单元（架构 §8）。"""

    tag: Literal["equal", "delete", "insert", "replace"]
    old_lines: List[str] = Field(default_factory=list)
    new_lines: List[str] = Field(default_factory=list)


class ConvertResult(BaseModel):
    """单条目转换结果（skipped/failed 时 converted == original，安全回退 P0-6）。"""

    filename: str
    status: Literal["converted", "skipped", "failed"]
    original: str
    converted: str
    reason: str = ""
    diff: List[DiffOp] = Field(default_factory=list)
    rename_map: Dict[str, str] = Field(default_factory=dict)


class ConvertSummary(BaseModel):
    total: int = 0
    converted: int = 0
    skipped: int = 0
    failed: int = 0


class ConvertResponse(BaseModel):
    results: List[ConvertResult]
    summary: ConvertSummary


# ---------------------------------------------------------------------------
# 历史（P2-1）
# ---------------------------------------------------------------------------


class HistoryFileItem(BaseModel):
    filename: str
    status: str
    original: str
    converted: str


class HistoryEntry(BaseModel):
    id: str
    time: str
    profile_name: str
    files: List[HistoryFileItem] = Field(default_factory=list)


class HistorySummary(BaseModel):
    id: str
    time: str
    profile_name: str
    files: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 导入
# ---------------------------------------------------------------------------


class ImportRequest(BaseModel):
    yaml_text: str
