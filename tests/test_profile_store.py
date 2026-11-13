"""规则集仓库单元测试（core/profile_store.py + models/profile.py）。"""

import pytest

import app.core.profile_store as store_module
from app.core.profile_store import ProfileNotFoundError, ProfileStore
from app.models.profile import StyleProfile


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """隔离的规则集仓库：profiles 指向临时目录，presets 使用真实内置预设。"""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    monkeypatch.setattr(store_module, "PROFILES_DIR", profiles_dir)
    return ProfileStore()


class TestYamlRoundTrip:
    def test_to_yaml_from_yaml(self):
        profile = StyleProfile(name="demo", language="python")
        profile.rules.indent.size = 2
        text = profile.to_yaml()
        assert "style_profile:" in text
        loaded = StyleProfile.from_yaml(text)
        assert loaded.name == "demo"
        assert loaded.rules.indent.size == 2

    def test_from_yaml_missing_root_key(self):
        with pytest.raises(ValueError, match="style_profile"):
            StyleProfile.from_yaml("foo: bar\n")

    def test_from_yaml_invalid_yaml(self):
        with pytest.raises(ValueError):
            StyleProfile.from_yaml("a: [unclosed\n")

    def test_from_yaml_schema_violation(self):
        bad = "style_profile:\n  language: rust\n"
        with pytest.raises(ValueError, match="schema"):
            StyleProfile.from_yaml(bad)


class TestCrud:
    def test_save_get_list_delete(self, store):
        profile = StyleProfile(name="mine", language="cpp")
        saved = store.save(profile)
        assert saved.id and len(saved.id) == 8

        loaded = store.get(saved.id)
        assert loaded.name == "mine"
        assert loaded.language.value == "cpp"

        summaries = store.list()
        assert any(s["id"] == saved.id for s in summaries)

        assert store.delete(saved.id) is True
        with pytest.raises(ProfileNotFoundError):
            store.get(saved.id)

    def test_get_missing_raises(self, store):
        with pytest.raises(ProfileNotFoundError):
            store.get("deadbeef")

    def test_delete_missing_returns_false(self, store):
        assert store.delete("deadbeef") is False

    def test_list_skips_corrupted_files(self, store):
        store.save(StyleProfile(name="good", language="python"))
        (store_module.PROFILES_DIR / "broken99.yaml").write_text(
            "not: a profile\n", encoding="utf-8"
        )
        summaries = store.list()
        assert len(summaries) == 1
        assert summaries[0]["name"] == "good"

    def test_summary_fields(self, store):
        saved = store.save(StyleProfile(name="s", language="java"))
        summary = [s for s in store.list() if s["id"] == saved.id][0]
        assert set(summary) == {"id", "name", "language", "source", "updated_at"}


class TestImportExport:
    def test_export_import_roundtrip(self, store):
        saved = store.save(StyleProfile(name="exp", language="python"))
        text = store.export_yaml(saved.id)
        assert "exp" in text
        imported = store.import_yaml(text)
        assert imported.id != saved.id  # 导入重新分配 id
        assert imported.name == "exp"
        assert imported.source == "manual"

    def test_import_invalid_yaml(self, store):
        with pytest.raises(ValueError):
            store.import_yaml("style_profile:\n  language: cobol\n")


class TestPresets:
    def test_builtin_presets_loadable(self, store):
        presets = store.list_presets()
        assert len(presets) == 3
        languages = {p.language.value for p in presets}
        assert languages == {"python", "cpp", "java"}
        assert all(p.source == "preset" for p in presets)

    def test_get_preset_by_id(self, store):
        pep8 = store.get("00000001")
        assert pep8.name.startswith("PEP 8")
        assert pep8.rules.indent.size == 4

    def test_preset_not_deletable(self, store):
        assert store.delete("00000001") is False

    def test_save_preset_fork_to_new_id(self, store):
        pep8 = store.get("00000001")
        forked = store.save(pep8)
        assert forked.id != pep8.id
        assert forked.source == "manual"
