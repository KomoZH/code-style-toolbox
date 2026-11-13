"""C++/Java 令牌化扫描器单元测试（core/tokenizer.py）。"""

from app.core.tokenizer import Tokenizer, TokenKind
from app.models.profile import Language


class TestTokenizeCpp:
    def test_basic_tokens(self):
        code = '#include <iostream>\nint main() { return 0; } // done\n'
        tokens = Tokenizer.tokenize(code, Language.cpp)
        kinds = [t.kind for t in tokens]
        values = [t.value for t in tokens]
        assert TokenKind.PREPROC in kinds
        assert "#include <iostream>" in values
        assert "int" in values
        assert "main" in values
        assert "// done" in values

    def test_multichar_operators_preferred(self):
        tokens = Tokenizer.tokenize("a <<= b; x->y; p == q;", Language.cpp)
        ops = [t.value for t in tokens if t.kind == TokenKind.OP]
        assert "<<=" in ops
        assert "->" in ops
        assert "==" in ops
        # 不应被拆成单字符
        assert "<" not in [t.value for t in tokens if t.kind == TokenKind.OP and t.value == "<"]

    def test_string_with_escapes_and_char_literal(self):
        code = 'const char* s = "a\\"b"; char c = \'x\';'
        tokens = Tokenizer.tokenize(code, Language.cpp)
        strings = [t.value for t in tokens if t.kind == TokenKind.STRING]
        chars = [t.value for t in tokens if t.kind == TokenKind.CHAR]
        assert strings == ['"a\\"b"']
        assert chars == ["'x'"]

    def test_raw_string(self):
        code = r'auto s = R"(a\not\\escaped)";'
        tokens = Tokenizer.tokenize(code, Language.cpp)
        strings = [t.value for t in tokens if t.kind == TokenKind.STRING]
        assert strings == [r'R"(a\not\\escaped)"']

    def test_preproc_with_line_continuation(self):
        code = "#define LONG \\\n    1 + 2\nint x;\n"
        tokens = Tokenizer.tokenize(code, Language.cpp)
        preproc = [t for t in tokens if t.kind == TokenKind.PREPROC]
        assert len(preproc) == 1
        assert "1 + 2" in preproc[0].value

    def test_block_comment_multiline(self):
        code = "/* line1\nline2 */ int x;"
        tokens = Tokenizer.tokenize(code, Language.cpp)
        blocks = [t for t in tokens if t.kind == TokenKind.COMMENT_BLOCK]
        assert len(blocks) == 1
        assert "line2" in blocks[0].value
        # 注释后的令牌行号应正确偏移
        x_tok = next(t for t in tokens if t.value == "x")
        assert x_tok.line == 2

    def test_numbers(self):
        tokens = Tokenizer.tokenize("0xFF 0b101 3.14 1e5 42u", Language.cpp)
        numbers = [t.value for t in tokens if t.kind == TokenKind.NUMBER]
        assert numbers == ["0xFF", "0b101", "3.14", "1e5", "42u"]


class TestTokenizeJava:
    def test_annotation_is_single_token(self):
        tokens = Tokenizer.tokenize("@Override void f() {}", Language.java)
        assert any(t.value == "@Override" for t in tokens)

    def test_text_block(self):
        code = 'String s = """\nhello\n""";\nint x = 1;'
        tokens = Tokenizer.tokenize(code, Language.java)
        strings = [t.value for t in tokens if t.kind == TokenKind.STRING]
        assert any("hello" in s for s in strings)

    def test_hash_is_not_preproc_in_java(self):
        # Java 无预处理器，# 应作为普通标点
        tokens = Tokenizer.tokenize("int # x;", Language.java)
        assert not any(t.kind == TokenKind.PREPROC for t in tokens)


class TestStripTrivia:
    def test_comments_removed_preproc_kept(self):
        code = "#define X 1\n// c\n/* b */\nint x;\n"
        tokens = Tokenizer.tokenize(code, Language.cpp)
        stripped = Tokenizer.strip_trivia(tokens)
        kinds = {t.kind for t in stripped}
        assert TokenKind.COMMENT_LINE not in kinds
        assert TokenKind.COMMENT_BLOCK not in kinds
        assert TokenKind.PREPROC in kinds


class TestBracketBalance:
    def test_balanced(self):
        tokens = Tokenizer.tokenize("int f() { return (1 + 2) * [3][0]; }", Language.cpp)
        assert Tokenizer.check_bracket_balance(tokens) is None

    def test_unbalanced_close(self):
        tokens = Tokenizer.tokenize("int f() { return 1; }}", Language.cpp)
        reason = Tokenizer.check_bracket_balance(tokens)
        assert reason is not None
        assert "}" in reason

    def test_unclosed_open(self):
        tokens = Tokenizer.tokenize("int f() { if (x) { return 1; }", Language.cpp)
        reason = Tokenizer.check_bracket_balance(tokens)
        assert reason is not None
        assert "未闭合" in reason

    def test_mismatched_pair(self):
        tokens = Tokenizer.tokenize("int a = (1 + 2];", Language.cpp)
        reason = Tokenizer.check_bracket_balance(tokens)
        assert reason is not None

    def test_brackets_in_strings_ignored(self):
        # 字符串内的括号不参与配平
        tokens = Tokenizer.tokenize('const char* s = "}{("; ', Language.cpp)
        assert Tokenizer.check_bracket_balance(tokens) is None
