"""规则集落盘/加载/导入导出/预设（架构 §8 规则文件约定）。

- 用户规则集：data/profiles/<id>.yaml
- 内置预设：data/presets/*.yaml，source="preset"，只读（编辑即另存新 id）
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from app.config import PRESETS_DIR, PROFILES_DIR, ensure_data_dirs
from app.models.profile import StyleProfile, new_profile_id


class ProfileNotFoundError(KeyError):
    """规则集不存在（错误码 3001）。"""


class ProfileStore:
    """规则集仓库（YAML 文件持久化）。"""

    def __init__(self) -> None:
        ensure_data_dirs()

    # -- 内部工具 ----------------------------------------------------------

    @staticmethod
    def _load_file(path: Path) -> StyleProfile:
        return StyleProfile.from_yaml(path.read_text(encoding="utf-8"))

    @staticmethod
    def _profile_path(pid: str) -> Path:
        return PROFILES_DIR / f"{pid}.yaml"

    # -- CRUD --------------------------------------------------------------

    def list(self) -> List[Dict]:
        """全部用户规则集摘要列表。"""
        profiles: List[Dict] = []
        for path in sorted(PROFILES_DIR.glob("*.yaml")):
            try:
                profiles.append(self._load_file(path).summary())
            except ValueError:
                continue  # 跳过损坏文件
        profiles.sort(key=lambda p: p["updated_at"], reverse=True)
        return profiles

    def get(self, pid: str) -> StyleProfile:
        """按 id 读取完整规则集；不存在抛 ProfileNotFoundError。"""
        path = self._profile_path(pid)
        if not path.exists():
            # 允许按预设 id 读取（前端可直接用预设转换）
            preset = self._find_preset(pid)
            if preset is not None:
                return preset
            raise ProfileNotFoundError(pid)
        return self._load_file(path)

    def save(self, profile: StyleProfile) -> StyleProfile:
        """保存规则集。预设另存为新 id（预设只读）。"""
        if profile.source == "preset":
            profile = profile.model_copy(deep=True)
            profile.id = new_profile_id()
            profile.source = "manual"
        if not profile.id:
            profile.id = new_profile_id()
        profile.touch()
        path = self._profile_path(profile.id)
        path.write_text(profile.to_yaml(), encoding="utf-8")
        return profile

    def delete(self, pid: str) -> bool:
        """删除规则集；预设不可删除。"""
        path = self._profile_path(pid)
        if not path.exists():
            return False
        path.unlink()
        return True

    # -- 导入导出 -----------------------------------------------------------

    def export_yaml(self, pid: str) -> str:
        """导出 YAML 纯文本。"""
        return self.get(pid).to_yaml()

    def import_yaml(self, text: str) -> StyleProfile:
        """导入 YAML（重新分配 id，source 置为 manual）。"""
        profile = StyleProfile.from_yaml(text)  # 校验失败抛 ValueError
        profile.id = new_profile_id()
        profile.source = "manual"
        profile.touch()
        path = self._profile_path(profile.id)
        path.write_text(profile.to_yaml(), encoding="utf-8")
        return profile

    # -- 预设 ---------------------------------------------------------------

    def list_presets(self) -> List[StyleProfile]:
        """内置预设列表（P2-2）。"""
        presets: List[StyleProfile] = []
        for path in sorted(PRESETS_DIR.glob("*.yaml")):
            try:
                presets.append(self._load_file(path))
            except ValueError:
                continue
        return presets

    def _find_preset(self, pid: str) -> Optional[StyleProfile]:
        for preset in self.list_presets():
            if preset.id == pid:
                return preset
        return None
