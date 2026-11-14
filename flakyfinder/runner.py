"""跑测试命令 N 次，把每次的结果收起来。"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Sequence

from .parsers import ParseResult, parse

__all__ = ["RunResult", "run_once", "run_many"]


@dataclass
class RunResult:
    index: int
    returncode: int | None
    duration_s: float
    parsed: ParseResult
    timed_out: bool = False
    output_tail: str = ""

    @property
    def failed(self) -> set[str]:
        return self.parsed.failed

    @property
    def passed(self) -> set[str]:
        return self.parsed.passed


def _build_command(command: str | Sequence[str]) -> tuple[str | list[str], bool]:
    """字符串 → 交给 shell；序列 → 直接 exec。"""
    if isinstance(command, str):
        return command, True
    return list(command), False


def run_once(
    command: str | Sequence[str],
    *,
    index: int = 0,
    cwd: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    fmt: str = "auto",
    env: dict[str, str] | None = None,
    tail_lines: int = 40,
) -> RunResult:
    """跑一次，返回解析结果。超时不抛异常，记在 timed_out 里。"""
    cmd, use_shell = _build_command(command)
    merged_env = {**os.environ, **(env or {})}
    # 让子进程输出别带颜色，否则正则匹配不到
    merged_env.setdefault("NO_COLOR", "1")
    merged_env.setdefault("FORCE_COLOR", "0")
    merged_env.setdefault("PY_COLORS", "0")
    merged_env.setdefault("TERM", "dumb")

    started = time.monotonic()
    timed_out = False
    rc: int | None = None
    output = ""

    try:
        proc = subprocess.run(
            cmd,
            shell=use_shell,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            env=merged_env,
        )
        rc = proc.returncode
        output = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        out = exc.stdout or ""
        err = exc.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        output = out + err
    except FileNotFoundError as exc:
        raise SystemExit(f"命令找不到：{exc}") from exc

    duration = time.monotonic() - started
    parsed = parse(output, fmt)

    tail = "\n".join(output.splitlines()[-tail_lines:])
    return RunResult(
        index=index,
        returncode=rc,
        duration_s=duration,
        parsed=parsed,
        timed_out=timed_out,
        output_tail=tail,
    )


def run_many(
    command: str | Sequence[str],
    runs: int,
    *,
    cwd: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    fmt: str = "auto",
    env: dict[str, str] | None = None,
    progress: bool = True,
    stream=sys.stderr,
) -> list[RunResult]:
    """连续跑 runs 次。每次的结果单独保留，不做合并。"""
    if runs < 1:
        raise ValueError("runs 至少是 1")

    results: list[RunResult] = []
    for i in range(runs):
        res = run_once(
            command,
            index=i,
            cwd=cwd,
            timeout=timeout,
            fmt=fmt,
            env=env,
        )
        results.append(res)

        if progress:
            status = "超时" if res.timed_out else f"rc={res.returncode}"
            flag = "✗" if res.failed else "✓"
            print(
                f"  第 {i + 1}/{runs} 次  {flag}  {status}  "
                f"{len(res.failed)} 失败 / {len(res.passed)} 通过  "
                f"{res.duration_s:.1f}s",
                file=stream,
            )

    return results
