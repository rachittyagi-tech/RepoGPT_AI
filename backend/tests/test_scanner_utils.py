"""
tests/test_scanner_utils.py

Pure unit tests for app/utils/language_detector.py and app/utils/file_utils.py.
No cloned repository or network access required.
"""

from pathlib import Path

from app.utils.file_utils import count_lines, should_ignore_directory
from app.utils.language_detector import detect_language, is_supported_file


def test_detect_language_by_extension() -> None:
    assert detect_language(Path("main.py")) == "Python"
    assert detect_language(Path("App.tsx")) == "TSX"
    assert detect_language(Path("styles.scss")) == "CSS"
    assert detect_language(Path("README.md")) == "Markdown"


def test_detect_language_special_filenames() -> None:
    assert detect_language(Path("Dockerfile")) == "Dockerfile"
    assert detect_language(Path("Makefile")) == "Text"


def test_detect_language_unsupported_returns_none() -> None:
    assert detect_language(Path("image.png")) is None
    assert detect_language(Path("archive.zip")) is None


def test_is_supported_file() -> None:
    assert is_supported_file(Path("main.go")) is True
    assert is_supported_file(Path("binary.exe")) is False


def test_should_ignore_directory() -> None:
    assert should_ignore_directory("node_modules") is True
    assert should_ignore_directory(".git") is True
    assert should_ignore_directory("src") is False


def test_count_lines() -> None:
    assert count_lines("") == 0
    assert count_lines("one line") == 1
    assert count_lines("line1\nline2\n") == 2
    assert count_lines("line1\nline2") == 2
