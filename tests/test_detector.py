"""语言识别单元测试（core/detector.py）。"""

import pytest

from app.core.detector import LanguageDetector
from conftest import read_example


class TestExtensionDetection:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("a.py", "python"),
            ("a.PY", "python"),
            ("a.cpp", "cpp"),
            ("a.cc", "cpp"),
            ("a.cxx", "cpp"),
            ("a.h", "cpp"),
            ("a.hpp", "cpp"),
            ("A.java", "java"),
        ],
    )
    def test_extension_mapping(self, filename, expected):
        # 扩展名命中时无论内容都高置信度返回
        result = LanguageDetector.detect(filename, "??? meaningless content")
        assert result.language == expected
        assert result.confidence >= 0.9
        assert result.manual_required is False


class TestContentDetection:
    @pytest.mark.parametrize("language", ["python", "cpp", "java"])
    def test_examples_detected_by_content(self, language):
        """三种语言示例在无文件名时应被内容特征正确识别。"""
        _, code = read_example(language)
        result = LanguageDetector.detect(None, code)
        assert result.language == language
        assert result.manual_required is False

    def test_pure_python_snippet(self):
        code = "def hello(name):\n    print('hi', name)\n    return None\n"
        result = LanguageDetector.detect(None, code)
        assert result.language == "python"
        assert result.manual_required is False

    def test_java_vs_cpp_disambiguation(self):
        code = (
            "package com.demo;\n"
            "public class App {\n"
            "    public static void main(String[] args) {\n"
            "        System.out.println(\"hi\");\n"
            "    }\n"
            "}\n"
        )
        result = LanguageDetector.detect(None, code)
        assert result.language == "java"

    @pytest.mark.parametrize("code", ["", "   \n\t ", "??? @@@ $$$", "123 456"])
    def test_unrecognizable_requires_manual(self, code):
        result = LanguageDetector.detect(None, code)
        assert result.language == "unknown"
        assert result.manual_required is True

    def test_unknown_extension_falls_back_to_content(self):
        _, code = read_example("python")
        result = LanguageDetector.detect("snippet.txt", code)
        assert result.language == "python"
