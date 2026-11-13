"""REST API 集成测试：对全部端点逐一实测，校验统一 {code,message,data} 包装。

通过 FastAPI TestClient 在进程内启动应用；profiles/history 目录隔离到 tmp。
"""

import pytest
from fastapi.testclient import TestClient

import app.api.routes_convert as routes_convert
import app.core.profile_store as store_module
from app.main import create_app
from conftest import read_example


@pytest.fixture()
def client(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    history_dir = tmp_path / "history"
    profiles_dir.mkdir()
    history_dir.mkdir()
    monkeypatch.setattr(store_module, "PROFILES_DIR", profiles_dir)
    monkeypatch.setattr(routes_convert, "HISTORY_DIR", history_dir)
    return TestClient(create_app())


def _unwrap(resp, expect_code=0):
    """校验统一响应包装并返回 data。"""
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {"code", "message", "data"}
    assert body["code"] == expect_code, body
    return body["data"]


class TestHealth:
    def test_health(self, client):
        data = _unwrap(client.get("/api/health"))
        assert data["status"] == "ok"
        assert data["version"]


class TestDetect:
    @pytest.mark.parametrize("language", ["python", "cpp", "java"])
    def test_detect_examples(self, client, language):
        filename, code = read_example(language)
        data = _unwrap(client.post("/api/detect", json={"code": code, "filename": filename}))
        assert data["language"] == language
        assert data["manual_required"] is False

    def test_detect_unrecognizable(self, client):
        data = _unwrap(client.post("/api/detect", json={"code": "???"}))
        assert data["language"] == "unknown"
        assert data["manual_required"] is True


class TestExtract:
    def test_extract_python_example(self, client):
        filename, code = read_example("python")
        data = _unwrap(
            client.post(
                "/api/extract",
                json={
                    "samples": [{"filename": filename, "content": code}],
                    "profile_name": "demo_py",
                },
            )
        )
        assert data["name"] == "demo_py"
        assert data["language"] == "python"
        assert data["source"] == "extracted"
        assert data["id"]
        # 提取后已落盘：列表中可见
        summaries = _unwrap(client.get("/api/profiles"))
        assert any(s["id"] == data["id"] for s in summaries)

    def test_extract_empty_samples_rejected(self, client):
        _unwrap(
            client.post("/api/extract", json={"samples": [], "profile_name": "x"}),
            expect_code=3001,
        )

    def test_extract_unrecognizable_requires_manual(self, client):
        body = client.post(
            "/api/extract",
            json={"samples": [{"filename": "a.txt", "content": "??? @@@"}]},
        ).json()
        assert body["code"] == 1001
        assert body["data"]["manual_required"] is True

    def test_extract_with_manual_language_override(self, client):
        """识别失败 → 手动指定语言路径可用（裁决 2）。"""
        data = _unwrap(
            client.post(
                "/api/extract",
                json={
                    "samples": [{"filename": "a.txt", "content": "x = 1"}],
                    "language": "python",
                    "profile_name": "manual",
                },
            )
        )
        assert data["language"] == "python"

    def test_extract_invalid_language_rejected(self, client):
        body = client.post(
            "/api/extract",
            json={
                "samples": [{"filename": "a.py", "content": "x = 1"}],
                "language": "rust",
            },
        ).json()
        assert body["code"] != 0


class TestProfilesCrud:
    def _create(self, client, name="crud"):
        _, code = read_example("python")
        return _unwrap(
            client.post(
                "/api/extract",
                json={
                    "samples": [{"filename": "a.py", "content": code}],
                    "profile_name": name,
                },
            )
        )

    def test_full_crud_cycle(self, client):
        created = self._create(client)
        pid = created["id"]

        # 读取
        loaded = _unwrap(client.get(f"/api/profiles/{pid}"))
        assert loaded["name"] == "crud"

        # 编辑保存：改缩进为 2
        loaded["rules"]["indent"]["size"] = 2
        saved = _unwrap(client.put(f"/api/profiles/{pid}", json=loaded))
        assert saved["rules"]["indent"]["size"] == 2
        assert _unwrap(client.get(f"/api/profiles/{pid}"))["rules"]["indent"]["size"] == 2

        # 导出
        resp = client.get(f"/api/profiles/{pid}/export")
        assert resp.status_code == 200
        assert "style_profile" in resp.text

        # 删除
        assert _unwrap(client.delete(f"/api/profiles/{pid}"))["deleted"] is True
        body = client.get(f"/api/profiles/{pid}").json()
        assert body["code"] == 3001

    def test_get_missing_profile(self, client):
        assert client.get("/api/profiles/deadbeef").json()["code"] == 3001

    def test_put_missing_profile(self, client):
        created = self._create(client, "ghost")
        assert (
            client.put("/api/profiles/deadbeef", json=created).json()["code"] == 3001
        )

    def test_import_export_roundtrip(self, client):
        created = self._create(client)
        text = client.get(f"/api/profiles/{created['id']}/export").text
        imported = _unwrap(client.post("/api/profiles/import", json={"yaml_text": text}))
        assert imported["id"] != created["id"]
        assert imported["source"] == "manual"

    def test_import_invalid(self, client):
        body = client.post(
            "/api/profiles/import", json={"yaml_text": "style_profile:\n  language: xx\n"}
        ).json()
        assert body["code"] == 3001


class TestPresets:
    def test_list_presets(self, client):
        presets = _unwrap(client.get("/api/presets"))
        assert len(presets) == 3
        assert {p["language"] for p in presets} == {"python", "cpp", "java"}


class TestConvert:
    PEP8_ID = "00000001"  # 内置预设可直接用于转换
    GOOGLE_CPP_ID = "00000002"
    GOOGLE_JAVA_ID = "00000003"

    def test_convert_single_python(self, client):
        _, code = read_example("python")
        data = _unwrap(
            client.post(
                "/api/convert",
                json={
                    "profile_id": self.PEP8_ID,
                    "items": [{"filename": "messy_demo.py", "content": code}],
                },
            )
        )
        result = data["results"][0]
        assert result["status"] == "converted"
        assert "class UserManager" in result["converted"]
        assert result["diff"]
        assert data["summary"] == {"total": 1, "converted": 1, "skipped": 0, "failed": 0}

    def test_convert_cpp_and_java_examples(self, client):
        cpp_file, cpp_code = read_example("cpp")
        java_file, java_code = read_example("java")
        for pid, filename, code, marker in [
            (self.GOOGLE_CPP_ID, cpp_file, cpp_code, "class UserManager"),
            (self.GOOGLE_JAVA_ID, java_file, java_code, "public class MessyDemo {"),
        ]:
            data = _unwrap(
                client.post(
                    "/api/convert",
                    json={"profile_id": pid, "items": [{"filename": filename, "content": code}]},
                )
            )
            result = data["results"][0]
            assert result["status"] == "converted", result["reason"]
            assert marker in result["converted"]

    def test_convert_syntax_error_fallback(self, client):
        bad = "def broken(:\n"
        data = _unwrap(
            client.post(
                "/api/convert",
                json={
                    "profile_id": self.PEP8_ID,
                    "items": [{"filename": "bad.py", "content": bad}],
                },
            )
        )
        result = data["results"][0]
        assert result["status"] == "failed"
        assert result["converted"] == bad  # P0-6 保留原始代码
        assert "1002" in result["reason"]

    def test_convert_blacklist_skipped(self, client):
        code = "#define MAX(a,b) ((a)>(b)?(a):(b))\nint main() { return 0; }\n"
        data = _unwrap(
            client.post(
                "/api/convert",
                json={
                    "profile_id": self.GOOGLE_CPP_ID,
                    "items": [{"filename": "m.cpp", "content": code}],
                },
            )
        )
        result = data["results"][0]
        assert result["status"] == "skipped"
        assert result["converted"] == code
        assert "2001" in result["reason"]

    def test_convert_mixed_batch_summary(self, client):
        """大批量混合批量：converted/skipped/failed 统计必须正确。"""
        _, good_py = read_example("python")
        bad_py = "def broken(:\n"
        _, java_code = read_example("java")
        data = _unwrap(
            client.post(
                "/api/convert",
                json={
                    "profile_id": self.PEP8_ID,
                    "items": [
                        {"filename": "good.py", "content": good_py},
                        {"filename": "bad.py", "content": bad_py},
                        {"filename": "A.java", "content": java_code},  # 语言不符 → skipped
                    ],
                },
            )
        )
        assert data["summary"] == {"total": 3, "converted": 1, "skipped": 1, "failed": 1}
        statuses = [r["status"] for r in data["results"]]
        assert statuses == ["converted", "failed", "skipped"]

    def test_convert_missing_profile(self, client):
        body = client.post(
            "/api/convert",
            json={"profile_id": "deadbeef", "items": [{"content": "x = 1"}]},
        ).json()
        assert body["code"] == 3001

    def test_convert_empty_items(self, client):
        body = client.post(
            "/api/convert", json={"profile_id": self.PEP8_ID, "items": []}
        ).json()
        assert body["code"] == 3001

    def test_convert_manual_language_override(self, client):
        data = _unwrap(
            client.post(
                "/api/convert",
                json={
                    "profile_id": self.PEP8_ID,
                    "items": [{"content": "x=1"}],  # 无文件名
                    "language": "python",
                },
            )
        )
        assert data["results"][0]["status"] == "converted"
        assert data["results"][0]["filename"].endswith(".py")


class TestHistory:
    def test_history_written_and_restorable(self, client):
        _, code = read_example("python")
        client.post(
            "/api/convert",
            json={
                "profile_id": "00000001",
                "items": [{"filename": "demo.py", "content": code}],
            },
        )
        entries = _unwrap(client.get("/api/history"))
        assert len(entries) >= 1
        entry = entries[0]
        assert "demo.py" in entry["files"]

        restored = _unwrap(client.post(f"/api/history/{entry['id']}/restore"))
        assert restored["restored"] == ["demo.py"]
        assert restored["items"][0]["content"] == code  # 还原内容为原始代码

    def test_restore_missing_history(self, client):
        body = client.post("/api/history/nope/restore").json()
        assert body["code"] == 3001


class TestExamples:
    def test_examples_endpoint(self, client):
        examples = _unwrap(client.get("/api/examples"))
        assert {e["language"] for e in examples} == {"python", "cpp", "java"}
        for e in examples:
            assert e["files"]
            assert all(f["filename"] and f["content"] for f in e["files"])
