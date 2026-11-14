"""命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .parsers import FORMATS, parse
from .report import aggregate, render_table, to_json
from .runner import run_many


def _split_command(argv: list[str]) -> list[str]:
    """支持 `flakyfinder run -- pytest -q`，也支持直接跟命令。"""
    if "--" in argv:
        return argv[argv.index("--") + 1 :]
    return argv


def cmd_run(args: argparse.Namespace) -> int:
    command = _split_command(args.rest)
    if not command:
        print("没有给要跑的命令。例：flakyfinder run --runs 5 -- pytest -q", file=sys.stderr)
        return 2

    display = command if isinstance(command, str) else " ".join(command)
    print(f"跑 {args.runs} 次：{display}", file=sys.stderr)
    print("", file=sys.stderr)

    runs = run_many(
        command if len(command) > 1 else command[0],
        args.runs,
        cwd=args.cwd,
        timeout=args.timeout,
        fmt=args.format,
    )

    print("", file=sys.stderr)
    stats = aggregate(runs)

    if args.json:
        print(json.dumps(to_json(stats, len(runs)), ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(render_table(stats, len(runs)))

    flaky = [s for s in stats if s.is_flaky]
    if args.fail_on_flaky and flaky:
        return 1
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    """调试用：把一段保存下来的输出喂给解析器，看识别出什么。"""
    text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8", errors="replace").read()
    res = parse(text, args.format)
    print(f"格式：{res.fmt}")
    print(f"失败 {len(res.failed)} / 通过 {len(res.passed)} / 跳过 {len(res.skipped)}")
    for label, items in (("失败", res.failed), ("通过", res.passed), ("跳过", res.skipped)):
        if items:
            print(f"\n{label}：")
            for item in sorted(items):
                print(f"  {item}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="flakyfinder",
        description="反复跑测试，找出哪个用例在捣鬼。",
    )
    p.add_argument("--version", action="version", version=f"flakyfinder {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="反复跑测试命令并统计")
    r.add_argument("rest", nargs=argparse.REMAINDER, help="-- 之后的测试命令")
    r.add_argument("--runs", type=int, default=5, help="跑几次，默认 5")
    r.add_argument("--timeout", type=float, default=None, help="单次超时秒数")
    r.add_argument("--cwd", default=None, help="在哪个目录跑")
    r.add_argument("--format", default="auto", choices=FORMATS, help="测试输出格式")
    r.add_argument("--json", action="store_true", help="输出 JSON")
    r.add_argument(
        "--fail-on-flaky",
        action="store_true",
        help="发现 flaky 就以退出码 1 结束（给 CI 用）",
    )
    r.set_defaults(func=cmd_run)

    q = sub.add_parser("parse", help="调试：解析一段已保存的输出")
    q.add_argument("file", help="文件路径，- 表示从 stdin 读")
    q.add_argument("--format", default="auto", choices=FORMATS)
    q.set_defaults(func=cmd_parse)

    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
