"""转换（粘贴/单文件/批量）+ 历史（架构 §3.3 / §4.2，P1-1 批量报告、P2-1 历史撤销）。

安全铁律：所有重写经 BaseRewriter.safe_convert 编排；
本模块只负责分派与汇总，绝不绕过等价校验直接返回重写结果。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Type

from fastapi import APIRouter

from app.api.schemas import (
    CODE_PROFILE_ERROR,
    ConvertRequest,
    ConvertResult,
    err,
    ok,
)
from app.config import HISTORY_DIR, HISTORY_KEEP, ensure_data_dirs
from app.core.detector import LanguageDetector
from app.core.profile_store import ProfileNotFoundError, ProfileStore
from app.core.rewriter.base import BaseRewriter
from app.core.rewriter.cpp_rewriter import CppRewriter
from app.core.rewriter.java_rewriter import JavaRewriter
from app.core.rewriter.python_rewriter import PythonRewriter
from app.models.profile import Language

router = APIRouter(tags=["convert"])

REWRITERS: Dict[Language, Type[BaseRewriter]] = {
    Language.python: PythonRewriter,
    Language.cpp: CppRewriter,
    Language.java: JavaRewriter,
}

_EXT_BY_LANGUAGE = {Language.python: ".py", Language.cpp: ".cpp", Language.java: ".java"}

_store = ProfileStore()


@router.post("/convert")
def convert(req: ConvertRequest) -> dict:
    """粘贴/单文件/批量共用入口；逐项安全回退。"""
    try:
        profile = _store.get(req.profile_id)
    except ProfileNotFoundError:
        return err(CODE_PROFILE_ERROR, f"规则集不存在: {req.profile_id}")
    except ValueError as exc:
        return err(CODE_PROFILE_ERROR, str(exc))
    if not req.items:
        return err(CODE_PROFILE_ERROR, "待转换条目为空")

    rewriter = REWRITERS[profile.language]()
    results = []
    for idx, item in enumerate(req.items, start=1):
        filename = item.filename or f"snippet_{idx}{_EXT_BY_LANGUAGE[profile.language]}"

        # 语言核对：显式指定优先；否则识别结果必须与规则集语言一致
        if req.language:
            item_language = req.language
        else:
            detection = LanguageDetector.detect(item.filename, item.content)
            item_language = detection.language
        if item_language != profile.language.value:
            results.append(
                ConvertResult(
                    filename=filename,
                    status="skipped",
                    original=item.content,
                    converted=item.content,
                    reason=(
                        f"条目语言({item_language})与规则集语言"
                        f"({profile.language.value})不一致，已跳过"
                    ),
                ).model_dump(mode="json")
            )
            continue

        result = rewriter.safe_convert(item.content, filename, profile)
        results.append(result.model_dump(mode="json"))

    summary = {
        "total": len(results),
        "converted": sum(1 for r in results if r["status"] == "converted"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
    }
    _append_history(profile.name, results)
    return ok({"results": results, "summary": summary})


# ---------------------------------------------------------------------------
# 历史（P2-1）
# ---------------------------------------------------------------------------


def _append_history(profile_name: str, results: list) -> None:
    """写入一条历史快照；容量滚动保留最近 HISTORY_KEEP 条（架构 §5-6）。"""
    ensure_data_dirs()
    hid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:6]
    entry = {
        "id": hid,
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile_name": profile_name,
        "files": [
            {
                "filename": r["filename"],
                "status": r["status"],
                "original": r["original"],
                "converted": r["converted"],
            }
            for r in results
        ],
    }
    (HISTORY_DIR / f"{hid}.json").write_text(
        json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    # 滚动清理
    files = sorted(HISTORY_DIR.glob("*.json"))
    for stale in files[:-HISTORY_KEEP]:
        stale.unlink(missing_ok=True)


@router.get("/history")
def list_history() -> dict:
    """转换历史摘要列表（P2-1）。"""
    ensure_data_dirs()
    entries = []
    for path in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        entries.append(
            {
                "id": data["id"],
                "time": data["time"],
                "profile_name": data["profile_name"],
                "files": [f["filename"] for f in data.get("files", [])],
            }
        )
    return ok(entries)


@router.post("/history/{hid}/restore")
def restore_history(hid: str) -> dict:
    """还原快照：返回各文件的原始内容（由前端触发下载/覆盖）。"""
    path = HISTORY_DIR / f"{hid}.json"
    if not path.exists():
        return err(CODE_PROFILE_ERROR, f"历史记录不存在: {hid}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return err(CODE_PROFILE_ERROR, f"历史记录损坏: {exc}")
    restored = [f["filename"] for f in data.get("files", []) if f.get("status") == "converted"]
    items = [
        {"filename": f["filename"], "content": f["original"]}
        for f in data.get("files", [])
        if f.get("status") == "converted"
    ]
    return ok({"restored": restored, "items": items})
