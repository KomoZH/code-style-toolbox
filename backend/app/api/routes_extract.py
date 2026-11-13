"""语言识别 + 风格提取 + 内置示例（架构 §3.3 / §4.1）。"""

from __future__ import annotations

from typing import Dict, Type

from fastapi import APIRouter

from app.api.schemas import (
    CODE_DETECT_FAILED,
    CODE_PROFILE_ERROR,
    DetectRequest,
    ExtractRequest,
    err,
    ok,
)
from app.core.detector import LanguageDetector
from app.core.extractor.base import BaseExtractor, Sample
from app.core.extractor.cpp_extractor import CppExtractor
from app.core.extractor.java_extractor import JavaExtractor
from app.core.extractor.python_extractor import PythonExtractor
from app.core.profile_store import ProfileStore
from app.config import EXAMPLES_DIR
from app.models.profile import Language

router = APIRouter(tags=["extract"])

EXTRACTORS: Dict[Language, Type[BaseExtractor]] = {
    Language.python: PythonExtractor,
    Language.cpp: CppExtractor,
    Language.java: JavaExtractor,
}

_store = ProfileStore()


@router.post("/detect")
def detect_language(req: DetectRequest) -> dict:
    """语言识别；manual_required=true 时前端弹手动选择。"""
    result = LanguageDetector.detect(req.filename, req.code)
    return ok(
        {
            "language": result.language,
            "confidence": result.confidence,
            "manual_required": result.manual_required,
            "scores": result.scores,
        }
    )


@router.post("/extract")
def extract_profile(req: ExtractRequest) -> dict:
    """风格提取并自动落盘；返回含 meta 置信度的完整 StyleProfile。"""
    if not req.samples:
        return err(CODE_PROFILE_ERROR, "样例列表为空")

    # 1. 逐样本语言识别（显式 language 优先，裁决 2 允许手动指定）
    target_language: Language | None = None
    if req.language:
        try:
            target_language = Language(req.language)
        except ValueError:
            return err(CODE_PROFILE_ERROR, f"不支持的语言: {req.language}")
    else:
        votes: Dict[str, int] = {}
        for sample in req.samples:
            result = LanguageDetector.detect(sample.filename, sample.content)
            if result.manual_required:
                continue
            votes[result.language] = votes.get(result.language, 0) + 1
        if not votes:
            return err(
                CODE_DETECT_FAILED,
                "语言识别失败，请手动指定语言后重试",
                {"manual_required": True},
            )
        best = max(votes, key=lambda k: votes[k])
        target_language = Language(best)

    # 2. 过滤出与目标语言一致的样本（混传时只统计同类文件）
    usable = []
    for sample in req.samples:
        if not sample.content.strip():
            continue
        result = LanguageDetector.detect(sample.filename, sample.content)
        if req.language or result.language == target_language.value:
            usable.append(Sample(filename=sample.filename, content=sample.content))
    if not usable:
        return err(CODE_PROFILE_ERROR, "无有效样例（内容为空或与目标语言不一致）")

    # 3. 提取并落盘
    extractor = EXTRACTORS[target_language]()
    profile = extractor.extract(usable, req.profile_name or "untitled")
    saved = _store.save(profile)
    return ok(saved.model_dump(mode="json"))


@router.get("/examples")
def list_examples() -> dict:
    """内置示例读取（P1-3 一键演示）。"""
    examples = []
    mapping = [
        ("python", "sample_python"),
        ("cpp", "sample_cpp"),
        ("java", "sample_java"),
    ]
    for language, dirname in mapping:
        dirpath = EXAMPLES_DIR / dirname
        if not dirpath.exists():
            continue
        files = [
            {"filename": f.name, "content": f.read_text(encoding="utf-8")}
            for f in sorted(dirpath.iterdir())
            if f.is_file()
        ]
        if files:
            examples.append({"language": language, "files": files})
    return ok(examples)
