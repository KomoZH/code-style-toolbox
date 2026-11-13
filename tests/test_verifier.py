"""等价校验单元测试（core/verifier.py）。"""

from app.core.verifier import Verifier
from app.models.profile import Language


class TestVerifyPython:
    def test_identical_code(self):
        code = "x = 1\nprint(x)\n"
        assert Verifier.verify_python(code, code, {}) is True

    def test_whitespace_and_comment_changes_equivalent(self):
        orig = "x=1 # c\nprint( x )\n"
        new = "x = 1  # c\nprint(x)\n"
        assert Verifier.verify_python(orig, new, {}) is True

    def test_rename_map_equivalent(self):
        orig = "def loadUsers(userList):\n    return userList\n"
        new = "def load_users(user_list):\n    return user_list\n"
        rename = {"loadUsers": "load_users", "userList": "user_list"}
        assert Verifier.verify_python(orig, new, rename) is True

    def test_logic_change_detected(self):
        orig = "x = 1 + 2\n"
        new = "x = 1 - 2\n"
        assert Verifier.verify_python(orig, new, {}) is False

    def test_constant_change_detected(self):
        assert Verifier.verify_python("x = 41\n", "x = 42\n", {}) is False

    def test_call_change_detected(self):
        orig = "print(x)\n"
        new = "len(x)\n"
        assert Verifier.verify_python(orig, new, {}) is False

    def test_rename_map_missing_entry_detected(self):
        # 声明了新名字但映射未覆盖 → 不等价
        orig = "y = 1\n"
        new = "z = 1\n"
        assert Verifier.verify_python(orig, new, {}) is False

    def test_syntax_error_either_side_fails(self):
        assert Verifier.verify_python("x = (\n", "x = 1\n", {}) is False
        assert Verifier.verify_python("x = 1\n", "x = (\n", {}) is False

    def test_attribute_not_renamed(self):
        # 属性访问不在重命名范围内：映射不应作用于 obj.attr
        orig = "obj.userName = 1\n"
        new = "obj.user_name = 1\n"
        assert Verifier.verify_python(orig, new, {"userName": "user_name"}) is False


class TestVerifyTokens:
    def test_whitespace_only_change_cpp(self):
        orig = "int main(){return 0;}\n"
        new = "int main()\n{\n    return 0;\n}\n"
        assert Verifier.verify_tokens(orig, new, Language.cpp, {}) is True

    def test_comment_changes_equivalent(self):
        orig = "int x; // old\n"
        new = "int x; // new\n"
        assert Verifier.verify_tokens(orig, new, Language.cpp, {}) is True

    def test_rename_map_valid(self):
        orig = "int userCount = 0; userCount++;\n"
        new = "int user_count = 0; user_count++;\n"
        assert Verifier.verify_tokens(
            orig, new, Language.cpp, {"userCount": "user_count"}
        ) is True

    def test_token_change_detected(self):
        orig = "int x = 1 + 2;\n"
        new = "int x = 1 - 2;\n"
        assert Verifier.verify_tokens(orig, new, Language.cpp, {}) is False

    def test_rename_to_keyword_rejected(self):
        assert (
            Verifier.verify_tokens(
                "int foo = 1;", "int class = 1;", Language.cpp, {"foo": "class"}
            )
            is False
        )

    def test_rename_to_invalid_identifier_rejected(self):
        assert (
            Verifier.verify_tokens(
                "int foo = 1;", "int x = 1;", Language.cpp, {"foo": "1abc"}
            )
            is False
        )

    def test_const_east_west_normalized(self):
        # const west 与 east 视为等价（归一化后比对）
        orig = "const int x = 1;\n"
        new = "int const x = 1;\n"
        assert Verifier.verify_tokens(orig, new, Language.cpp, {}) is True

    def test_java_equivalence(self):
        orig = "class A{void f(){int x=1;}}\n"
        new = "class A {\n  void f() {\n    int x = 1;\n  }\n}\n"
        assert Verifier.verify_tokens(orig, new, Language.java, {}) is True

    def test_java_token_change_detected(self):
        orig = "int x = 1;\n"
        new = "int x = 2;\n"
        assert Verifier.verify_tokens(orig, new, Language.java, {}) is False
