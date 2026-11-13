"""规则集 CRUD / 导入导出 / 预设（架构 §3.3）。"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.api.schemas import CODE_PROFILE_ERROR, ImportRequest, err, ok
from app.core.profile_store import ProfileNotFoundError, ProfileStore
from app.models.profile import StyleProfile

router = APIRouter(tags=["profiles"])

_store = ProfileStore()


@router.get("/profiles")
def list_profiles() -> dict:
    """规则集摘要列表。"""
    return ok(_store.list())


@router.get("/profiles/{pid}")
def get_profile(pid: str) -> dict:
    """完整规则（含 meta）。"""
    try:
        return ok(_store.get(pid).model_dump(mode="json"))
    except ProfileNotFoundError:
        return err(CODE_PROFILE_ERROR, f"规则集不存在: {pid}")
    except ValueError as exc:
        return err(CODE_PROFILE_ERROR, str(exc))


@router.put("/profiles/{pid}")
def save_profile(pid: str, profile: StyleProfile) -> dict:
    """保存编辑（服务端 schema 校验由 Pydantic 完成）。预设另存为新 id。"""
    try:
        existing = _store.get(pid)
    except ProfileNotFoundError:
        return err(CODE_PROFILE_ERROR, f"规则集不存在: {pid}")
    profile.id = existing.id if existing.source != "preset" else profile.id
    if existing.source != "preset":
        profile.source = existing.source
    saved = _store.save(profile)
    return ok(saved.model_dump(mode="json"))


@router.delete("/profiles/{pid}")
def delete_profile(pid: str) -> dict:
    deleted = _store.delete(pid)
    if not deleted:
        return err(CODE_PROFILE_ERROR, f"规则集不存在或为预设: {pid}")
    return ok({"deleted": True})


@router.post("/profiles/import")
def import_profile(req: ImportRequest) -> dict:
    """导入 YAML（重新分配 id）。"""
    try:
        profile = _store.import_yaml(req.yaml_text)
    except ValueError as exc:
        return err(CODE_PROFILE_ERROR, str(exc))
    return ok(profile.model_dump(mode="json"))


@router.get("/profiles/{pid}/export")
def export_profile(pid: str) -> PlainTextResponse:
    """导出 YAML 纯文本下载。"""
    try:
        text = _store.export_yaml(pid)
    except ProfileNotFoundError:
        return PlainTextResponse(f"规则集不存在: {pid}", status_code=404)
    return PlainTextResponse(text, media_type="text/yaml; charset=utf-8")


@router.get("/presets")
def list_presets() -> dict:
    """内置预设（P2-2）。"""
    return ok([p.model_dump(mode="json") for p in _store.list_presets()])
