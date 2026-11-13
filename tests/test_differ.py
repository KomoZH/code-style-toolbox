"""结构化 diff 单元测试（core/differ.py）。"""

from app.core.differ import compute_diff


class TestComputeDiff:
    def test_identical(self):
        ops = compute_diff("a\nb\n", "a\nb\n")
        assert len(ops) == 1
        assert ops[0]["tag"] == "equal"
        assert ops[0]["old_lines"] == ["a", "b"]

    def test_insert(self):
        ops = compute_diff("a\n", "a\nb\n")
        tags = [op["tag"] for op in ops]
        assert "insert" in tags
        inserted = [op for op in ops if op["tag"] == "insert"][0]
        assert inserted["new_lines"] == ["b"]
        assert inserted["old_lines"] == []

    def test_delete(self):
        ops = compute_diff("a\nb\n", "a\n")
        deleted = [op for op in ops if op["tag"] == "delete"]
        assert deleted and deleted[0]["old_lines"] == ["b"]

    def test_replace(self):
        ops = compute_diff("a\nold\n", "a\nnew\n")
        replaced = [op for op in ops if op["tag"] == "replace"]
        assert replaced
        assert replaced[0]["old_lines"] == ["old"]
        assert replaced[0]["new_lines"] == ["new"]

    def test_empty_to_content(self):
        ops = compute_diff("", "x\n")
        assert any(op["tag"] == "insert" for op in ops)

    def test_op_schema_keys(self):
        ops = compute_diff("a\nb\nc\n", "a\nx\nc\n")
        for op in ops:
            assert set(op.keys()) == {"tag", "old_lines", "new_lines"}
            assert op["tag"] in ("equal", "delete", "insert", "replace")
