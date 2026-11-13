"""C++/Java 不安全构造黑名单单元测试（core/blacklist.py）。"""

from app.core.blacklist import Blacklist
from app.models.profile import Language


class TestCppBlacklist:
    def test_function_like_macro_hit(self):
        code = "#define MAX(a, b) ((a) > (b) ? (a) : (b))\nint x;\n"
        reason = Blacklist.scan(code, Language.cpp)
        assert reason is not None
        assert "宏" in reason

    def test_object_like_macro_safe(self):
        # 对象式宏（无参数）不在黑名单内
        code = "#define MAX_SIZE 100\nint x = MAX_SIZE;\n"
        assert Blacklist.scan(code, Language.cpp) is None

    def test_template_specialization_hit(self):
        code = "template <> struct Foo<int> {};\n"
        reason = Blacklist.scan(code, Language.cpp)
        assert reason is not None
        assert "模板特化" in reason

    def test_normal_template_safe(self):
        code = "template <typename T> T add(T a, T b) { return a + b; }\n"
        assert Blacklist.scan(code, Language.cpp) is None

    def test_ifdef_hit(self):
        code = "#ifdef DEBUG\nint x = 1;\n#endif\n"
        reason = Blacklist.scan(code, Language.cpp)
        assert reason is not None
        assert "预处理条件块" in reason

    def test_if_hit(self):
        code = "#if defined(WIN32)\n#endif\n"
        assert Blacklist.scan(code, Language.cpp) is not None

    def test_elif_hit(self):
        code = "#define A 1\n#if A\n#elif B\n#endif\n"
        assert Blacklist.scan(code, Language.cpp) is not None

    def test_include_and_define_safe(self):
        code = "#include <vector>\n#define PI 3.14\nint main() { return 0; }\n"
        assert Blacklist.scan(code, Language.cpp) is None


class TestJavaBlacklist:
    def test_java_never_blocked(self):
        # Java 词法层安全，即使包含类似文本也不应命中
        code = "class A { /* #define X(1) */ void f() {} }\n"
        assert Blacklist.scan(code, Language.java) is None

    def test_java_normal_code(self):
        code = "public class A { public static void main(String[] a) {} }\n"
        assert Blacklist.scan(code, Language.java) is None
