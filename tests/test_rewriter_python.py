"""Python 重写器单元测试（core/rewriter/python_rewriter.py）。

重点覆盖：正常转换、语法错误回退、空/单字符/纯注释输入、
重命名碰撞、属性/关键字参数保护、私有前缀与 dunder 保护。
"""

import ast

from app.core.rewriter.python_rewriter import PythonRewriter


class TestHappyPath:
    def test_messy_example_converted_with_pep8(self, python_example, make_profile):
        filename, code = python_example
        profile = make_profile("python")  # 默认即 PEP8 风格
        result = PythonRewriter().safe_convert(code, filename, profile)
        assert result.status == "converted"
        assert result.reason == ""
        # 类名 camelCase → PascalCase，顶层函数 → snake_case
        assert "class UserManager" in result.converted
        assert "def main_entry():" in result.converted
        # 缩进由 2 空格变为 4 空格
        assert "\n    def __init__" in result.converted
        # 经实例调用的方法（mgr.loadUsers）按架构 §5-4 保守策略不改写
        assert "def loadUsers(self):" in result.converted
        assert "mgr.loadUsers()" in result.converted
        # 局部变量/参数重命名一致
        assert "user_list" in result.converted
        # rename_map 记录
        assert result.rename_map.get("userManager") == "UserManager"
        assert result.rename_map.get("mainEntry") == "main_entry"
        assert result.rename_map.get("userList") == "user_list"
        # diff 非空且结构合法
        assert result.diff
        for op in result.diff:
            assert op.tag in ("equal", "delete", "insert", "replace")

    def test_ast_equivalence_of_output(self, python_example, make_profile):
        """safe_convert 通过即已 AST 等价；这里再独立复验一次。"""
        filename, code = python_example
        result = PythonRewriter().safe_convert(code, filename, make_profile("python"))
        assert result.status == "converted"
        tree = ast.parse(result.converted)
        funcs = sorted(
            n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
        )
        # 方法经实例调用（属性位置）按保守策略保留原名
        assert funcs == ["__init__", "findUser", "loadUsers", "main_entry"]

    def test_runtime_behavior_preserved(self, python_example, make_profile):
        """语义等价抽查：原始与转换后的代码运行输出一致。"""
        _, code = python_example
        result = PythonRewriter().safe_convert(code, "demo.py", make_profile("python"))
        assert result.status == "converted"

        def run(src: str) -> str:
            import io
            import contextlib

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exec(compile(src, "demo.py", "exec"), {"__name__": "__main__"})
            return buf.getvalue()

        assert run(result.converted) == run(result.original)
        assert run(result.original) != ""  # 确认确实执行了打印

    def test_api_calls_and_attribute_access_unchanged(self, make_profile):
        """属性访问、关键字参数名、导入名不得改写（P0-3）。"""
        code = (
            "import json\n"
            "def parseIt(rawData):\n"
            "    obj = json.loads(rawData)\n"
            "    return obj.get('keyName', default=None)\n"
        )
        result = PythonRewriter().safe_convert(code, "a.py", make_profile("python"))
        assert result.status == "converted"
        assert "json.loads" in result.converted
        # 关键字参数名与属性名保持不变（空白可能调整，但标识符不动）
        assert "obj.get('keyName'," in result.converted
        assert "default" in result.converted and "None" in result.converted
        assert "import json" in result.converted
        assert "def parse_it(raw_data):" in result.converted

    def test_private_prefix_preserved(self, make_profile):
        code = "def _helperFunc():\n    pass\n"
        result = PythonRewriter().safe_convert(code, "a.py", make_profile("python"))
        assert result.status == "converted"
        assert "_helper_func" in result.converted

    def test_dunder_not_renamed(self, make_profile):
        code = "class foo:\n    def __init__(self):\n        self.x = 1\n"
        result = PythonRewriter().safe_convert(code, "a.py", make_profile("python"))
        assert result.status == "converted"
        assert "def __init__(self):" in result.converted
        assert "class Foo" in result.converted

    def test_spacing_normalization(self, make_profile):
        code = "x=1+2\ny = x*3\n"
        result = PythonRewriter().safe_convert(code, "a.py", make_profile("python"))
        assert result.status == "converted"
        assert "x = 1 + 2" in result.converted
        assert "y = x * 3" in result.converted

    def test_spacing_disabled(self, make_profile):
        profile = make_profile(
            "python", spacing={"space_around_operators": False, "space_after_comma": False}
        )
        code = "x = 1 + 2\nf(a, b)\n"
        result = PythonRewriter().safe_convert(code, "a.py", profile)
        assert result.status == "converted"
        assert "x=1+2" in result.converted
        assert "f(a,b)" in result.converted

    def test_tab_indent(self, make_profile):
        profile = make_profile("python", indent={"style": "tab"})
        code = "def f():\n        return 1\n"
        result = PythonRewriter().safe_convert(code, "a.py", profile)
        assert result.status == "converted"
        assert "\n\treturn 1" in result.converted


class TestErrorPaths:
    def test_syntax_error_fails_and_preserves_original(self, make_profile):
        code = "def broken(:\n    pass\n"
        result = PythonRewriter().safe_convert(code, "bad.py", make_profile("python"))
        assert result.status == "failed"
        assert result.converted == code  # P0-6：保留原始代码
        assert "1002" in result.reason

    def test_unclosed_bracket_fails(self, make_profile):
        code = "x = (1 + 2\n"
        result = PythonRewriter().safe_convert(code, "bad.py", make_profile("python"))
        assert result.status == "failed"
        assert result.converted == code

    def test_bad_indentation_fails(self, make_profile):
        code = "def f():\npass\n"
        result = PythonRewriter().safe_convert(code, "bad.py", make_profile("python"))
        assert result.status == "failed"
        assert result.converted == code


class TestEdgeInputs:
    def test_empty_file(self, make_profile):
        result = PythonRewriter().safe_convert("", "empty.py", make_profile("python"))
        assert result.status == "converted"
        assert result.converted == ""

    def test_single_char_file(self, make_profile):
        result = PythonRewriter().safe_convert("x", "one.py", make_profile("python"))
        assert result.status == "converted"

    def test_comment_only_file(self, make_profile):
        code = "# just a comment\n# another\n"
        result = PythonRewriter().safe_convert(code, "c.py", make_profile("python"))
        assert result.status == "converted"
        assert "# just a comment" in result.converted

    def test_docstring_content_not_rewritten(self, make_profile):
        """多行字符串内容属于 protected 区，空白规则不得改写。"""
        code = 'def f():\n    """a=1,  b=2"""\n    return 1\n'
        result = PythonRewriter().safe_convert(code, "d.py", make_profile("python"))
        assert result.status == "converted"
        assert '"""a=1,  b=2"""' in result.converted

    def test_string_literals_not_rewritten(self, make_profile):
        code = 'MSG = "a=1,b=2"\n'
        result = PythonRewriter().safe_convert(code, "s.py", make_profile("python"))
        assert result.status == "converted"
        assert '"a=1,b=2"' in result.converted


class TestRenameCollision:
    def test_collision_blocks_rename(self, make_profile):
        """目标名已存在时放弃该条重命名，避免语义碰撞。"""
        code = "total_count = 1\ntotalCount = 2\nprint(total_count)\nprint(totalCount)\n"
        result = PythonRewriter().safe_convert(code, "c.py", make_profile("python"))
        assert result.status == "converted"
        assert "totalCount" not in result.rename_map
        # 两个变量都必须保留且语义不变
        assert "totalCount = 2" in result.converted

    def test_attribute_name_blocks_local_rename(self, make_profile):
        """同名属性出现过的标识符不改写（保守策略，防改 API 语义）。"""
        code = "myAttr = 1\nobj.myAttr = 2\nprint(myAttr)\n"
        result = PythonRewriter().safe_convert(code, "a.py", make_profile("python"))
        assert result.status == "converted"
        assert "myAttr" not in result.rename_map
