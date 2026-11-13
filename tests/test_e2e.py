"""端到端演示流程测试：examples/ 三语言示例走通 提取 → 规则落盘 → 转换 → diff 对照。

走引擎层（与 API 同一代码路径），验证 PRD P1-3 演示流程可用性。
"""

import pytest

import app.core.profile_store as store_module
from app.core.detector import LanguageDetector
from app.core.extractor.base import Sample
from app.core.extractor.cpp_extractor import CppExtractor
from app.core.extractor.java_extractor import JavaExtractor
from app.core.extractor.python_extractor import PythonExtractor
from app.core.profile_store import ProfileStore
from app.core.rewriter.cpp_rewriter import CppRewriter
from app.core.rewriter.java_rewriter import JavaRewriter
from app.core.rewriter.python_rewriter import PythonRewriter
from conftest import read_example

EXTRACTORS = {
    "python": PythonExtractor,
    "cpp": CppExtractor,
    "java": JavaExtractor,
}
REWRITERS = {
    "python": PythonRewriter,
    "cpp": CppRewriter,
    "java": JavaRewriter,
}
PRESET_IDS = {"python": "00000001", "cpp": "00000002", "java": "00000003"}


@pytest.fixture()
def store(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    monkeypatch.setattr(store_module, "PROFILES_DIR", profiles_dir)
    return ProfileStore()


class TestDemoFlow:
    @pytest.mark.parametrize("language", ["python", "cpp", "java"])
    def test_extract_save_convert_diff(self, store, language):
        """完整演示流程：识别 → 提取 → 落盘 → 读取 → 转换 → diff。"""
        filename, code = read_example(language)

        # 1. 语言识别
        detection = LanguageDetector.detect(filename, code)
        assert detection.language == language

        # 2. 风格提取
        profile = EXTRACTORS[language]().extract(
            [Sample(filename=filename, content=code)], f"demo_{language}"
        )
        assert profile.rules is not None

        # 3. 规则落盘 + 重新读取
        saved = store.save(profile)
        loaded = store.get(saved.id)
        assert loaded.name == f"demo_{language}"

        # 4. 用提取到的规则转换原文件（同源风格，必须能安全转换）
        result = REWRITERS[language]().safe_convert(code, filename, loaded)
        assert result.status == "converted", result.reason

        # 5. diff 结构可供前端渲染
        for op in result.diff:
            assert op.tag in ("equal", "delete", "insert", "replace")

    @pytest.mark.parametrize("language", ["python", "cpp", "java"])
    def test_preset_conversion_flow(self, store, language):
        """用内置预设转换 messy 示例（真正的跨风格迁移场景）。"""
        filename, code = read_example(language)
        preset = store.get(PRESET_IDS[language])
        result = REWRITERS[language]().safe_convert(code, filename, preset)
        assert result.status == "converted", result.reason
        assert result.converted != code  # 风格确实发生了变化
        # 关键语义标记保留
        assert result.converted.strip() != ""


class TestSemanticSpotCheck:
    """语义等价抽查：逻辑、函数签名、API 调用未变。"""

    def test_python_logic_and_api_preserved(self, store):
        _, code = read_example("python")
        profile = store.get(PRESET_IDS["python"])
        result = PythonRewriter().safe_convert(code, "demo.py", profile)
        assert result.status == "converted"
        out = result.converted
        # API 调用与标准库未变
        assert "print(" in out
        assert "range(MAX_RETRY)" in out
        assert "__name__" in out and '"__main__"' in out
        # 字符串字面量内容未变
        assert '"user_"' in out or "'user_'" in out
        # 转换后仍可被解释器编译
        compile(out, "demo.py", "exec")

    def test_cpp_logic_and_api_preserved(self, store):
        _, code = read_example("cpp")
        profile = store.get(PRESET_IDS["cpp"])
        result = CppRewriter().safe_convert(code, "demo.cpp", profile)
        assert result.status == "converted"
        out = result.converted
        # API/库调用与控制流关键字未变
        assert "std::cout" in out
        assert "std::endl" in out
        assert "static_cast<int>" in out
        assert "push_back" in out
        assert "for" in out and "if" in out and "return" in out
        # 字符串字面量内容未变
        assert '"found: "' in out

    def test_java_logic_and_api_preserved(self, store):
        _, code = read_example("java")
        profile = store.get(PRESET_IDS["java"])
        result = JavaRewriter().safe_convert(code, "MessyDemo.java", profile)
        assert result.status == "converted"
        out = result.converted
        assert "System.out.println" in out
        assert "new ArrayList<>()" in out
        assert ".equals(" in out
        assert '"found: "' in out
        # 方法签名保留（修饰符 + 返回类型 + 参数类型不变）
        assert "public static void main(String[] args)" in out
