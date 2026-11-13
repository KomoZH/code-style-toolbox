"""命名风格判定与转换单元测试（core/naming.py）。"""

import pytest

from app.core.naming import Naming


class TestDetectStyle:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("user_name", "snake_case"),
            ("userName", "camelCase"),
            ("UserName", "PascalCase"),
            ("MAX_RETRY", "UPPER_SNAKE"),
            ("MAX", "UPPER_SNAKE"),  # 全大写无下划线的退化形态
            ("x", "snake_case"),  # 单字符小写
            ("_private_var", "snake_case"),  # 前导下划线不影响判定
            ("__dunder__", "snake_case"),
            ("m_memberVar", "camelCase"),  # m_ 成员前缀剥离后判定
            ("s_instance", "snake_case"),
        ],
    )
    def test_common_styles(self, name, expected):
        assert Naming.detect_style(name) == expected

    @pytest.mark.parametrize("name", ["Mixed_Case", "___", ""])
    def test_undetectable(self, name):
        assert Naming.detect_style(name) is None


class TestSplitAffixes:
    @pytest.mark.parametrize(
        "name,prefix,stem",
        [
            ("user_name", "", "user_name"),
            ("_private", "_", "private"),
            ("__dunder__", "__", "dunder__"),
            ("m_count", "m_", "count"),
            ("s_state", "s_", "state"),
        ],
    )
    def test_split(self, name, prefix, stem):
        assert Naming.split_affixes(name) == (prefix, stem)


class TestConvert:
    @pytest.mark.parametrize(
        "name,target,expected",
        [
            ("userName", "snake_case", "user_name"),
            ("user_name", "camelCase", "userName"),
            ("user_name", "PascalCase", "UserName"),
            ("max_retry", "UPPER_SNAKE", "MAX_RETRY"),
            ("MAX_RETRY", "snake_case", "max_retry"),
            ("HTTPServer", "snake_case", "http_server"),
            ("_privateVar", "snake_case", "_private_var"),  # 私有前缀保留
            ("m_memberVar", "snake_case", "m_member_var"),  # 成员前缀保留
            # 已知行为：词干尾部下划线在分词时丢弃（重写器不会对 dunder 调用 convert）
            ("__init__", "camelCase", "__init"),
            ("user_name", "snake_case", "user_name"),  # 已是目标风格
            ("user_name", "not_a_style", "user_name"),  # 非法目标原样返回
            ("___", "snake_case", "___"),  # 空词干原样返回
        ],
    )
    def test_convert(self, name, target, expected):
        assert Naming.convert(name, target) == expected
