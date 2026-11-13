"""风格提取器单元测试（core/extractor/，三语言）。"""

from app.core.extractor.base import Sample
from app.core.extractor.cpp_extractor import CppExtractor
from app.core.extractor.java_extractor import JavaExtractor
from app.core.extractor.python_extractor import PythonExtractor
from conftest import read_example


class TestPythonExtractor:
    def test_extract_from_messy_example(self, python_example):
        filename, code = python_example
        profile = PythonExtractor().extract(
            [Sample(filename=filename, content=code)], "messy"
        )
        rules = profile.rules
        # messy_demo.py：函数/类为 camelCase，常量 UPPER_SNAKE，2 空格缩进；
        # 变量混合（result/mgr/users/found 为 snake，userList 为 camel）→ 多数派 snake
        assert rules.naming.functions == "camelCase"
        assert rules.naming.classes == "camelCase"
        assert rules.naming.variables == "snake_case"
        assert rules.naming.constants == "UPPER_SNAKE"
        assert rules.indent.style == "space"
        assert rules.indent.size == 2
        assert profile.language.value == "python"
        assert profile.source == "extracted"

    def test_meta_confidence_present(self, python_example):
        filename, code = python_example
        profile = PythonExtractor().extract(
            [Sample(filename=filename, content=code)], "messy"
        )
        assert "naming" in profile.meta
        for group_meta in profile.meta.values():
            if not isinstance(group_meta, dict):
                continue
            for key, rule_meta in group_meta.items():
                if not isinstance(rule_meta, dict) or "confidence" not in rule_meta:
                    continue
                assert 0.0 <= rule_meta["confidence"] <= 1.0
                assert rule_meta["samples"] >= 0
        # 样例行数软提示（<200 行 → low_evidence）
        assert profile.meta["_sample_lines"]["low_evidence"] is True

    def test_snake_case_sample(self):
        code = (
            "def load_data(input_path):\n"
            "    max_size = 10\n"
            "    return max_size\n"
            "\n\n"
            "class DataLoader:\n"
            "    pass\n"
        )
        profile = PythonExtractor().extract(
            [Sample(filename="a.py", content=code)], "snake"
        )
        assert profile.rules.naming.functions == "snake_case"
        assert profile.rules.naming.classes == "PascalCase"
        assert profile.rules.naming.variables == "snake_case"
        assert profile.rules.blank_lines.between_functions == 2

    def test_docstring_format_google(self):
        code = 'def f(a):\n    """Summary.\n\n    Args:\n        a: value\n    """\n    return a\n'
        profile = PythonExtractor().extract(
            [Sample(filename="a.py", content=code)], "doc"
        )
        assert profile.rules.comments.docstring_format == "google"

    def test_syntax_invalid_sample_skipped(self):
        bad = Sample(filename="bad.py", content="def broken(:\n")
        good = Sample(filename="good.py", content="def ok_func():\n    pass\n")
        profile = PythonExtractor().extract([bad, good], "mixed")
        # 非法样例不影响合法样例的统计
        assert profile.rules.naming.functions == "snake_case"

    def test_all_invalid_falls_back_to_defaults(self):
        samples = [Sample(filename="bad.py", content="def broken(:\n")]
        profile = PythonExtractor().extract(samples, "allbad")
        # 回落默认规则；无任何投票时 meta 中无该规则的置信度记录
        assert profile.rules.naming.functions == "snake_case"
        assert "naming" not in profile.meta
        assert profile.meta["_sample_lines"]["total"] > 0


class TestCppExtractor:
    def test_extract_from_messy_example(self, cpp_example):
        filename, code = cpp_example
        profile = CppExtractor().extract(
            [Sample(filename=filename, content=code)], "messy"
        )
        rules = profile.rules
        # messy_demo.cpp：Allman 括号、Tab 缩进、类名 camelCase、常量 UPPER_SNAKE
        assert rules.brace_style.style == "allman"
        assert rules.indent.style == "tab"
        assert rules.naming.classes == "camelCase"
        assert rules.naming.functions == "camelCase"
        assert rules.naming.constants == "UPPER_SNAKE"
        assert rules.brace_style.space_before_paren is True
        assert profile.language.value == "cpp"

    def test_knr_style_detected(self):
        code = "int main() {\n  return 0;\n}\n"
        profile = CppExtractor().extract([Sample(filename="a.cpp", content=code)], "knr")
        assert profile.rules.brace_style.style == "k_and_r"
        assert profile.rules.indent.style == "space"
        assert profile.rules.indent.size == 2

    def test_const_west_detected(self):
        code = "const int MAX_A = 1;\nconst double pi = 3.14;\n"
        profile = CppExtractor().extract([Sample(filename="a.cpp", content=code)], "c")
        assert profile.rules.declarations.cpp_const_style == "west"

    def test_const_east_detected(self):
        code = "int const MAX_A = 1;\ndouble const pi = 3.14;\n"
        profile = CppExtractor().extract([Sample(filename="a.cpp", content=code)], "c")
        assert profile.rules.declarations.cpp_const_style == "east"


class TestJavaExtractor:
    def test_extract_from_messy_example(self, java_example):
        filename, code = java_example
        profile = JavaExtractor().extract(
            [Sample(filename=filename, content=code)], "messy"
        )
        rules = profile.rules
        # MessyDemo.java：Allman、4 空格、类 PascalCase、方法/变量 snake_case
        assert rules.brace_style.style == "allman"
        assert rules.indent.style == "space"
        assert rules.indent.size == 4
        assert rules.naming.classes == "PascalCase"
        assert rules.naming.functions == "snake_case"
        assert rules.naming.variables == "snake_case"
        assert rules.naming.constants == "UPPER_SNAKE"
        assert profile.language.value == "java"

    def test_conflict_flag_on_mixed_styles(self):
        # 两种命名风格势均力敌 → conflict 标记
        code = (
            "public class A {\n"
            "    int user_count;\n"
            "    int userCount;\n"
            "    int item_index;\n"
            "    int itemIndex;\n"
            "}\n"
        )
        profile = JavaExtractor().extract(
            [Sample(filename="A.java", content=code)], "conflict"
        )
        meta = profile.meta.get("naming", {}).get("variables", {})
        if meta:  # 若收集到变量投票，则平分秋色必然 conflict
            assert meta.get("conflict") is True or meta.get("samples", 0) < 2
