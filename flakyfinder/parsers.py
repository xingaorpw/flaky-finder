"""把各种测试框架的输出解析成「哪些用例失败了」。

只回答三个集合：failed / passed / skipped。
不关心断言内容，不关心耗时 —— 那些交给别的工具。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["ParseResult", "parse", "PARSERS", "FORMATS"]


@dataclass
class ParseResult:
    fmt: str
    failed: set[str] = field(default_factory=set)
    passed: set[str] = field(default_factory=set)
    skipped: set[str] = field(default_factory=set)

    @property
    def total(self) -> int:
        return len(self.failed) + len(self.passed) + len(self.skipped)


# ---------------------------------------------------------------- pytest

_PYTEST_VERBOSE = re.compile(
    r"^(?P<id>\S+\.py::\S+?)\s+(?P<status>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b",
    re.M,
)

_PYTEST_SHORT = re.compile(
    r"^(?:FAILED|ERROR)\s+(?P<id>\S+\.py::\S+?)(?:\s+-\s+.*)?$",
    re.M,
)


def parse_pytest(output: str) -> ParseResult:
    """支持 pytest -v 和 pytest 默认（只打印失败）两种输出。"""
    res = ParseResult("pytest")

    for m in _PYTEST_VERBOSE.finditer(output):
        test_id, status = m.group("id"), m.group("status")
        if status in ("PASSED", "XPASS"):
            res.passed.add(test_id)
        elif status in ("FAILED", "ERROR"):
            res.failed.add(test_id)
        else:
            res.skipped.add(test_id)

    for m in _PYTEST_SHORT.finditer(output):
        test_id = m.group("id").rstrip(":")
        if test_id:
            res.failed.add(test_id)

    return res


# ---------------------------------------------------------------- unittest

_UNITTEST = re.compile(
    r"^(?P<name>\S+) \((?P<path>[^)\s]+)\)"
    r"(?:\s+\.\.\.\s+|\s*\.\.\.\s*)"
    r"(?P<status>ok|FAIL|ERROR|skipped|expected failure|unexpected success)",
    re.M,
)


def parse_unittest(output: str) -> ParseResult:
    """支持 python -m unittest -v。"""
    res = ParseResult("unittest")

    for m in _UNITTEST.finditer(output):
        name, path, status = m.group("name"), m.group("path"), m.group("status")
        # path 是 dotted 全名；只有类名时补上方法名
        test_id = path if "." in path else f"{path}.{name}"

        if status == "ok":
            res.passed.add(test_id)
        elif status in ("FAIL", "ERROR", "unexpected success"):
            res.failed.add(test_id)
        else:
            res.skipped.add(test_id)

    return res


# ---------------------------------------------------------------- go test

_GO = re.compile(
    r"^\s*---\s+(?P<status>PASS|FAIL|SKIP):\s+(?P<name>\S+?)(?:\s+\(|$)",
    re.M,
)


def parse_go(output: str) -> ParseResult:
    """支持 go test -v。子测试形如 TestSub/case。"""
    res = ParseResult("go")

    for m in _GO.finditer(output):
        status, name = m.group("status"), m.group("name")
        if status == "PASS":
            res.passed.add(name)
        elif status == "FAIL":
            res.failed.add(name)
        else:
            res.skipped.add(name)

    return res


# ---------------------------------------------------------------- TAP

_TAP = re.compile(
    r"^(?P<status>not ok|ok)\s+\d+\s*(?:-\s*)?(?P<name>.*?)"
    r"(?:\s+#\s*(?P<directive>SKIP|TODO)\b.*)?$",
    re.M,
)


def parse_tap(output: str) -> ParseResult:
    """支持 TAP（node:test、bats、prove 等）。"""
    res = ParseResult("tap")

    for m in _TAP.finditer(output):
        name = (m.group("name") or "").strip()
        if not name:
            continue
        if m.group("directive"):
            res.skipped.add(name)
        elif m.group("status") == "ok":
            res.passed.add(name)
        else:
            res.failed.add(name)

    return res


# ---------------------------------------------------------------- jest

_JEST_FILE = re.compile(r"^(?P<status>PASS|FAIL)\s+(?P<file>\S+)\s*$")
_JEST_CASE = re.compile(r"^\s+(?P<mark>✓|✕|○)\s+(?P<name>.+?)(?:\s+\(\d+\s*m?s\))?$")


def parse_jest(output: str) -> ParseResult:
    """支持 jest / vitest 的逐用例输出。需要按文件分组，所以逐行扫。"""
    res = ParseResult("jest")
    current = ""

    for line in output.splitlines():
        fm = _JEST_FILE.match(line)
        if fm:
            current = fm.group("file")
            continue

        cm = _JEST_CASE.match(line)
        if not cm:
            continue

        name = cm.group("name").strip()
        test_id = f"{current}::{name}" if current else name
        mark = cm.group("mark")

        if mark == "✓":
            res.passed.add(test_id)
        elif mark == "✕":
            res.failed.add(test_id)
        else:
            res.skipped.add(test_id)

    return res


# ---------------------------------------------------------------- 路由

PARSERS = {
    "pytest": parse_pytest,
    "unittest": parse_unittest,
    "go": parse_go,
    "tap": parse_tap,
    "jest": parse_jest,
}

FORMATS = ("auto", *PARSERS)

# auto 模式下总分相同时的优先级：越靠前越可信
_PRIORITY = ("pytest", "unittest", "go", "jest", "tap")


def parse(output: str, fmt: str = "auto") -> ParseResult:
    """解析测试输出。

    fmt="auto" 时把所有解析器都跑一遍，取识别出用例最多的那个。
    """
    if fmt not in FORMATS:
        raise ValueError(f"未知格式 {fmt!r}，可选：{', '.join(FORMATS)}")

    if fmt != "auto":
        return PARSERS[fmt](output)

    # _PRIORITY 有序，只在「严格更多」时替换，所以并列时保留更可信的那个
    best: ParseResult | None = None
    for name in _PRIORITY:
        res = PARSERS[name](output)
        if res.total and (best is None or res.total > best.total):
            best = res

    return best or ParseResult("auto")
