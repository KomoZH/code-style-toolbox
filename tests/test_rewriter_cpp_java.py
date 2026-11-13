"""C++/Java 重写器单元测试（core/rewriter/cpp_rewriter.py、java_rewriter.py）。

重点覆盖：黑名单跳过、语法（括号配平）失败回退、正常转换、
const east/west、重命名碰撞、空/纯注释输入。
"""

from app.core.rewriter.cpp_rewriter import CppRewriter
from app.core.rewriter.java_rewriter import JavaRewriter
from app.models.profile import StyleProfile


def _cpp_profile(**overrides) -> StyleProfile:
    profile = StyleProfile(name="t", language="cpp")
    for group, fields in overrides.items():
        for key, value in fields.items():
            setattr(getattr(profile.rules, group), key, value)
    return profile


def _java_profile(**overrides) -> StyleProfile:
    profile = StyleProfile(name="t", language="java")
    for group, fields in overrides.items():
        for key, value in fields.items():
            setattr(getattr(profile.rules, group), key, value)
    return profile


class TestCppBlacklistSkip:
    def test_function_macro_skipped(self):
        code = "#define MAX(a,b) ((a)>(b)?(a):(b))\nint main() { return 0; }\n"
        result = CppRewriter().safe_convert(code, "m.cpp", _cpp_profile())
        assert result.status == "skipped"
        assert result.converted == code
        assert "2001" in result.reason

    def test_ifdef_skipped(self):
        code = "#ifdef X\nint a;\n#endif\nint main() { return 0; }\n"
        result = CppRewriter().safe_convert(code, "p.cpp", _cpp_profile())
        assert result.status == "skipped"
        assert result.converted == code

    def test_template_specialization_skipped(self):
        code = "template <> struct S<int> {};\n"
        result = CppRewriter().safe_convert(code, "t.cpp", _cpp_profile())
        assert result.status == "skipped"
        assert result.converted == code


class TestCppSyntaxFailure:
    def test_unbalanced_brackets_failed(self):
        code = "int main() { return 0;\n"
        result = CppRewriter().safe_convert(code, "bad.cpp", _cpp_profile())
        assert result.status == "failed"
        assert result.converted == code
        assert "1002" in result.reason

    def test_mismatched_brackets_failed(self):
        code = "int a = (1 + 2];\n"
        result = CppRewriter().safe_convert(code, "bad.cpp", _cpp_profile())
        assert result.status == "failed"
        assert result.converted == code


class TestCppConversion:
    def test_messy_example_to_google_style(self, cpp_example):
        filename, code = cpp_example
        # Google C++：k_and_r、2 空格、函数/常量 PascalCase、const east
        profile = _cpp_profile(
            naming={
                "functions": "PascalCase",
                "constants": "PascalCase",
            },
            indent={"style": "space", "size": 2},
            brace_style={"style": "k_and_r", "space_before_paren": True},
            declarations={"cpp_const_style": "east"},
        )
        result = CppRewriter().safe_convert(code, filename, profile)
        assert result.status == "converted", result.reason
        out = result.converted
        # 类名 camelCase → PascalCase
        assert "class UserManager" in out
        assert "class userManager" not in out
        # 括号风格 allman → k_and_r
        assert "class UserManager {" in out or "class UserManager\n{" not in out
        # 常量 UPPER_SNAKE → PascalCase
        assert "MaxItems" in out
        # const east：const int → int const
        assert "int const MaxItems" in out
        # 变量重命名（成员访问位置保持一致）
        assert "user_list" in out
        # include 预处理行保留
        assert "#include <iostream>" in out

    def test_allman_style_output(self):
        code = "int main() {\n  if (1) {\n    return 0;\n  }\n  return 1;\n}\n"
        profile = _cpp_profile(brace_style={"style": "allman"})
        result = CppRewriter().safe_convert(code, "a.cpp", profile)
        assert result.status == "converted", result.reason
        assert "\n{\n" in result.converted

    def test_const_west_conversion(self):
        code = "int const LIMIT = 5;\nint main() { return LIMIT; }\n"
        profile = _cpp_profile(declarations={"cpp_const_style": "west"})
        result = CppRewriter().safe_convert(code, "c.cpp", profile)
        assert result.status == "converted", result.reason
        assert "const int LIMIT" in result.converted

    def test_member_access_preserved(self):
        """成员访问（obj.field / obj.method）与 std:: 限定名不得改写。"""
        code = (
            "#include <string>\n"
            "struct Config {\n"
            "    int maxCount;\n"
            "};\n"
            "int readIt(Config& cfg) {\n"
            "    return cfg.maxCount;\n"
            "}\n"
        )
        result = CppRewriter().safe_convert(code, "cfg.cpp", _cpp_profile())
        assert result.status == "converted", result.reason
        # maxCount 出现于成员访问位置 → 整体不改写（保守策略）
        assert "cfg.maxCount" in result.converted

    def test_rename_collision_blocked(self):
        code = "int total_count = 1;\nint totalCount = 2;\nint main() { return total_count + totalCount; }\n"
        result = CppRewriter().safe_convert(code, "col.cpp", _cpp_profile())
        assert result.status == "converted", result.reason
        assert "totalCount" not in result.rename_map
        assert "totalCount" in result.converted

    def test_comments_preserved(self):
        code = "// header comment\nint main() {\n    return 0; // trailing\n}\n"
        result = CppRewriter().safe_convert(code, "c.cpp", _cpp_profile())
        assert result.status == "converted", result.reason
        assert "// header comment" in result.converted
        assert "// trailing" in result.converted


class TestCppEdgeInputs:
    def test_empty_file(self):
        result = CppRewriter().safe_convert("", "empty.cpp", _cpp_profile())
        assert result.status == "converted"

    def test_comment_only_file(self):
        code = "// only comment\n"
        result = CppRewriter().safe_convert(code, "c.cpp", _cpp_profile())
        assert result.status == "converted"
        assert "// only comment" in result.converted

    def test_single_char(self):
        result = CppRewriter().safe_convert("x", "one.cpp", _cpp_profile())
        assert result.status == "converted"


class TestJavaConversion:
    def test_messy_example_to_google_style(self, java_example):
        filename, code = java_example
        profile = _java_profile(
            naming={"variables": "camelCase", "functions": "camelCase"},
            indent={"style": "space", "size": 2},
            brace_style={"style": "k_and_r"},
            blank_lines={"between_functions": 1},
        )
        result = JavaRewriter().safe_convert(code, filename, profile)
        assert result.status == "converted", result.reason
        out = result.converted
        # allman → k_and_r
        assert "public class MessyDemo {" in out
        # 形参 snake → camel（定义点 + 引用点一致改写）
        assert "String userName" in out
        # 经实例调用的方法（demo.add_user）按保守策略不改写
        assert "demo.add_user" in out
        # 局部变量重命名
        assert "foundIndex" in out
        # import 保留
        assert "import java.util.ArrayList;" in out
        # API 调用不变
        assert "System.out.println" in out

    def test_unbalanced_brackets_failed(self):
        code = "class A { void f() {\n"
        result = JavaRewriter().safe_convert(code, "A.java", _java_profile())
        assert result.status == "failed"
        assert result.converted == code
        assert "1002" in result.reason

    def test_java_never_blacklisted(self):
        code = "class A { /* template<> */ void f() {} }\n"
        result = JavaRewriter().safe_convert(code, "A.java", _java_profile())
        assert result.status == "converted"

    def test_annotation_preserved(self):
        code = "class A {\n    @Override\n    public String toString() { return \"a\"; }\n}\n"
        result = JavaRewriter().safe_convert(code, "A.java", _java_profile())
        assert result.status == "converted", result.reason
        assert "@Override" in result.converted
