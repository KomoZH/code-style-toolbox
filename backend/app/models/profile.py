"""StyleProfile Pydantic 模型（架构 §3.1 规则 schema 单一事实源）。

规则值与元数据分离：`meta` 与 `rules` 同构，承载置信度（confidence）、
样本数（samples）、样例片段（examples）与冲突标记（conflict），支撑 P1-4。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal

import yaml
from pydantic import BaseModel, Field


class Language(str, Enum):
    """语言枚举（架构 §8）。"""

    python = "python"
    cpp = "cpp"
    java = "java"


NamingStyle = Literal["snake_case", "camelCase", "PascalCase", "UPPER_SNAKE"]


# ---------------------------------------------------------------------------
# 规则子树
# ---------------------------------------------------------------------------


class NamingRules(BaseModel):
    """命名约定。"""

    variables: NamingStyle = "snake_case"
    functions: NamingStyle = "snake_case"
    classes: NamingStyle = "PascalCase"
    constants: NamingStyle = "UPPER_SNAKE"
    private_prefix: str = "_"  # python/java 私有前缀；"" 表示无
    member_prefix: str = ""  # C++ 成员前缀如 "m_"


class IndentRules(BaseModel):
    """缩进。"""

    style: Literal["space", "tab"] = "space"
    size: int = 4  # 2 | 4 | 8（space 模式生效）


class BraceRules(BaseModel):
    """括号风格（仅 cpp/java 生效）。"""

    style: Literal["k_and_r", "allman"] = "k_and_r"
    space_before_paren: bool = True  # "if (" vs "if("


class SpacingRules(BaseModel):
    """空白。"""

    space_around_operators: bool = True
    space_after_comma: bool = True
    trim_trailing_whitespace: bool = True


class BlankLineRules(BaseModel):
    """空行与排版。"""

    max_consecutive: int = 2
    between_functions: int = 2  # python 顶层 2 / cpp·java 1
    after_imports: int = 1


class CommentRules(BaseModel):
    """注释。"""

    inline_min_spaces: int = 2  # 行尾注释前最少空格
    docstring_format: Literal["google", "numpy", "sphinx", "none"] = "google"


class DeclarationRules(BaseModel):
    """类型声明（可安全提取展示，默认仅 const 位置参与重写，见架构 §5-3）。"""

    cpp_const_style: Literal["east", "west"] = "east"
    python_type_hints: bool = True


class Rules(BaseModel):
    """规则树。"""

    naming: NamingRules = Field(default_factory=NamingRules)
    indent: IndentRules = Field(default_factory=IndentRules)
    brace_style: BraceRules = Field(default_factory=BraceRules)
    spacing: SpacingRules = Field(default_factory=SpacingRules)
    blank_lines: BlankLineRules = Field(default_factory=BlankLineRules)
    comments: CommentRules = Field(default_factory=CommentRules)
    declarations: DeclarationRules = Field(default_factory=DeclarationRules)


# ---------------------------------------------------------------------------
# 元数据（与 rules 同构的子树）
# ---------------------------------------------------------------------------


class RuleMeta(BaseModel):
    """单条规则的提取元数据。"""

    confidence: float = 1.0
    samples: int = 0
    examples: List[str] = Field(default_factory=list)
    conflict: bool = False


# ---------------------------------------------------------------------------
# 顶层 Profile
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_profile_id() -> str:
    """生成 8 位十六进制短 id（架构 §8 规则文件约定）。"""
    return uuid.uuid4().hex[:8]


class StyleProfile(BaseModel):
    """风格规则集，可双向序列化为 YAML（data/profiles/<id>.yaml）。"""

    id: str = Field(default_factory=new_profile_id)
    name: str = "untitled"
    language: Language = Language.python
    version: str = "1.0"
    created_at: str = Field(default_factory=_now_iso)
    source: Literal["extracted", "preset", "manual"] = "manual"
    rules: Rules = Field(default_factory=Rules)
    meta: Dict[str, Any] = Field(default_factory=dict)

    def touch(self) -> None:
        """更新修改时间（updated_at 复用 created_at 字段语义之外的摘要展示）。"""
        self.created_at = _now_iso()

    # -- YAML 序列化 ------------------------------------------------------

    def to_yaml(self) -> str:
        """序列化为 YAML 文本（顶层包裹 style_profile 键，见架构 §3.1）。"""
        payload = {"style_profile": self.model_dump(mode="json")}
        return yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

    @classmethod
    def from_yaml(cls, text: str) -> "StyleProfile":
        """从 YAML 文本解析并做 schema 校验；非法输入抛 ValueError。"""
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"YAML 解析失败: {exc}") from exc
        if not isinstance(raw, dict) or "style_profile" not in raw:
            raise ValueError("缺少 style_profile 顶层键")
        try:
            return cls.model_validate(raw["style_profile"])
        except Exception as exc:  # pydantic ValidationError
            raise ValueError(f"规则 schema 校验失败: {exc}") from exc

    def summary(self) -> Dict[str, Any]:
        """列表页摘要（GET /api/profiles）。"""
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language.value,
            "source": self.source,
            "updated_at": self.created_at,
        }
