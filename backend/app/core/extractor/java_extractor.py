"""Java 风格提取器：复用令牌层统计逻辑，覆盖 Java 关键字与 import 规则。"""

from __future__ import annotations

from typing import List, Sequence

from app.core.extractor.base import VoteBag
from app.core.extractor.cpp_extractor import TokenBasedExtractor
from app.core.tokenizer import Token
from app.models.profile import Language


class JavaExtractor(TokenBasedExtractor):
    """Java 规则归纳器。"""

    language = Language.java
    class_keywords = ("class", "interface", "enum", "record")
    paren_keywords = ("if", "for", "while", "switch", "catch", "synchronized")
    call_keywords = frozenset(
        {"if", "for", "while", "switch", "catch", "return", "new", "else",
         "do", "case", "super", "this", "synchronized", "throw", "assert"}
    )

    def _after_imports_stats(
        self, lines: List[str], tokens: Sequence[Token], bag: VoteBag
    ) -> None:
        block_end = 0
        for i, tok in enumerate(tokens):
            if tok.value == "import":
                block_end = max(block_end, tok.line)
            elif tok.value == "package":
                continue
            elif block_end and tok.line > block_end + 1:
                break
        if block_end and block_end < len(lines):
            blanks = 0
            row = block_end
            while row < len(lines) and lines[row].strip() == "":
                blanks += 1
                row += 1
            bag.add("blank_lines.after_imports", min(blanks, 4))
