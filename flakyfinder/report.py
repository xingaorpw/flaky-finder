"""把多次运行的结果聚合成「每个用例的稳定性」，并渲染成人能看的表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .runner import RunResult

__all__ = [
    "TestStats",
    "aggregate",
    "render_table",
    "to_json",
    "VERDICT_FLAKY",
    "VERDICT_ALWAYS_FAIL",
    "VERDICT_STABLE",
]

VERDICT_FLAKY = "flaky"
VERDICT_ALWAYS_FAIL = "always-fail"
VERDICT_STABLE = "stable"


@dataclass
class TestStats:
    test_id: str
    runs_seen: int = 0
    failures: int = 0
    passes: int = 0
    skips: int = 0

    @property
    def pass_rate(self) -> float:
        decided = self.passes + self.failures
        return self.passes / decided if decided else 1.0

    @property
    def verdict(self) -> str:
        if self.failures == 0:
            return VERDICT_STABLE
        if self.passes == 0:
            # 从来没通过过 —— 这是坏的，不是 flaky
            return VERDICT_ALWAYS_FAIL
        return VERDICT_FLAKY

    @property
    def is_flaky(self) -> bool:
        return self.verdict == VERDICT_FLAKY


def aggregate(runs: Sequence[RunResult]) -> list[TestStats]:
    """按用例聚合。返回顺序：flaky 优先，其次一直失败，最后稳定。

    只看失败行也能判断 flaky：
    跑了 N 次，某用例失败了 k 次，0 < k < N 就是 flaky。
    不需要它出现在「通过」列表里。
    """
    total_runs = len(runs)
    stats: dict[str, TestStats] = {}

    def get(test_id: str) -> TestStats:
        if test_id not in stats:
            stats[test_id] = TestStats(test_id)
        return stats[test_id]

    for res in runs:
        for test_id in res.failed:
            s = get(test_id)
            s.failures += 1
            s.runs_seen += 1
        for test_id in res.passed:
            s = get(test_id)
            s.passes += 1
            s.runs_seen += 1
        for test_id in res.parsed.skipped:
            s = get(test_id)
            s.skips += 1

    for s in stats.values():
        # 没有通过行的格式下，用它没失败的那些轮次补上「通过」次数
        if s.passes == 0 and s.failures < total_runs:
            s.passes = total_runs - s.failures

    def sort_key(s: TestStats):
        order = {VERDICT_FLAKY: 0, VERDICT_ALWAYS_FAIL: 1, VERDICT_STABLE: 2}
        return (order[s.verdict], -s.failures, s.test_id)

    return sorted(stats.values(), key=sort_key)


def _bar(rate: float, width: int = 12) -> str:
    filled = round(rate * width)
    return "█" * filled + "░" * (width - filled)


def render_table(stats: Iterable[TestStats], total_runs: int, *, color: bool = False) -> str:
    """渲染成文本表。不用制表符对齐库，纯字符串。"""
    rows = list(stats)
    if not rows:
        return "没有识别到任何用例。可能格式不对，用 --format 指定。"

    flaky = [s for s in rows if s.verdict == VERDICT_FLAKY]
    broken = [s for s in rows if s.verdict == VERDICT_ALWAYS_FAIL]

    lines: list[str] = []

    if flaky:
        lines.append(f"不稳定的用例（{len(flaky)} 个）")
        lines.append("")
        width = max(len(s.test_id) for s in flaky)
        for s in flaky:
            rate = s.pass_rate
            lines.append(
                f"  {s.test_id.ljust(width)}  "
                f"{_bar(rate)}  {rate:5.0%}  "
                f"失败 {s.failures}/{total_runs} 次"
            )
        lines.append("")

    if broken:
        lines.append(f"一直失败（{len(broken)} 个）—— 这不是 flaky，是真的坏了")
        lines.append("")
        width = max(len(s.test_id) for s in broken)
        for s in broken:
            lines.append(f"  {s.test_id.ljust(width)}  失败 {s.failures}/{total_runs} 次")
        lines.append("")

    stable = [s for s in rows if s.verdict == VERDICT_STABLE]
    if stable and not flaky:
        lines.append(f"{len(stable)} 个用例全部稳定通过，跑 {total_runs} 次没有一次失败。")

    return "\n".join(lines).rstrip() + "\n"


def to_json(stats: Iterable[TestStats], total_runs: int) -> dict:
    rows = []
    for s in stats:
        rows.append(
            {
                "test": s.test_id,
                "verdict": s.verdict,
                "pass_rate": round(s.pass_rate, 4),
                "failures": s.failures,
                "passes": s.passes,
                "skips": s.skips,
            }
        )
    return {
        "total_runs": total_runs,
        "flaky": sum(1 for s in stats if s.verdict == VERDICT_FLAKY),
        "always_failing": sum(1 for s in stats if s.verdict == VERDICT_ALWAYS_FAIL),
        "tests": rows,
    }
