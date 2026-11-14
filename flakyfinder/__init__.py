"""flaky-finder —— 反复跑测试，找出哪个用例在捣鬼。"""

__version__ = "0.1.0"

from .parsers import FORMATS, PARSERS, ParseResult, parse
from .report import (
    VERDICT_ALWAYS_FAIL,
    VERDICT_FLAKY,
    VERDICT_STABLE,
    TestStats,
    aggregate,
    render_table,
    to_json,
)
from .runner import RunResult, run_many, run_once

__all__ = [
    "__version__",
    "ParseResult",
    "parse",
    "PARSERS",
    "FORMATS",
    "RunResult",
    "run_once",
    "run_many",
    "TestStats",
    "aggregate",
    "render_table",
    "to_json",
    "VERDICT_FLAKY",
    "VERDICT_ALWAYS_FAIL",
    "VERDICT_STABLE",
]
