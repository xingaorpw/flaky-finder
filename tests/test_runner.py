"""端到端：真起子进程，真跑一个会抖的测试脚本。"""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

from flakyfinder.report import aggregate, render_table
from flakyfinder.runner import run_many, run_once

# 一个确定性的「flaky」测试：第 1 次跑失败，之后都成功。
# 用计数器文件，不依赖随机数，所以测试不会自己抖。
FLAKY_SCRIPT = r'''
import pathlib, sys
counter = pathlib.Path(__file__).with_suffix(".count")
n = int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(n + 1))
if n == 0:
    print("not ok 1 - sometimes_fails")
    print("ok 2 - always_ok")
    sys.exit(1)
print("ok 1 - sometimes_fails")
print("ok 2 - always_ok")
'''

# 每次都很稳
STABLE_SCRIPT = r'''
print("ok 1 - always_ok")
print("ok 2 - also_ok")
'''

# 每次都失败
BROKEN_SCRIPT = r'''
import sys
print("not ok 1 - never_works")
print("ok 2 - always_ok")
sys.exit(1)
'''


class TestRunOnce(unittest.TestCase):
    def test_captures_exit_code_and_parses(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "t.py"
            script.write_text(STABLE_SCRIPT, encoding="utf-8")
            res = run_once(f'"{sys.executable}" "{script}"', fmt="tap")

        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.failed, set())
        self.assertIn("always_ok", res.passed)
        self.assertGreaterEqual(res.duration_s, 0.0)

    def test_timeout_is_recorded_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "slow.py"
            script.write_text("import time; time.sleep(5)\n", encoding="utf-8")
            res = run_once(f'"{sys.executable}" "{script}"', timeout=0.3, fmt="tap")

        self.assertTrue(res.timed_out)
        self.assertIsNone(res.returncode)

    def test_nonexistent_command_via_list_raises(self):
        """列表形式直接 exec，命令不存在会抛 FileNotFoundError，我们转成 SystemExit。"""
        with self.assertRaises(SystemExit):
            run_once(["definitely-not-a-real-command-xyz"], fmt="tap")

    def test_nonexistent_command_via_shell_returns_nonzero(self):
        """字符串形式走 shell，Windows 下是 rc=1 而不是抛异常。"""
        res = run_once("definitely-not-a-real-command-xyz", fmt="tap")
        self.assertNotEqual(res.returncode, 0)
        self.assertEqual(res.parsed.total, 0)


class TestEndToEnd(unittest.TestCase):
    def test_detects_flaky(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "flaky.py"
            script.write_text(FLAKY_SCRIPT, encoding="utf-8")
            runs = run_many(
                f'"{sys.executable}" "{script}"',
                4,
                fmt="tap",
                progress=False,
            )
            stats = aggregate(runs)
            out = render_table(stats, len(runs))

        by_id = {s.test_id: s for s in stats}
        self.assertEqual(by_id["sometimes_fails"].verdict, "flaky")
        self.assertEqual(by_id["always_ok"].verdict, "stable")
        self.assertIn("不稳定的用例", out)

    def test_stable_suite_reports_no_flaky(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "stable.py"
            script.write_text(STABLE_SCRIPT, encoding="utf-8")
            runs = run_many(f'"{sys.executable}" "{script}"', 3, fmt="tap", progress=False)
            stats = aggregate(runs)

        self.assertTrue(all(s.verdict == "stable" for s in stats))
        self.assertEqual(len(stats), 2)

    def test_broken_suite_is_not_flaky(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "broken.py"
            script.write_text(BROKEN_SCRIPT, encoding="utf-8")
            runs = run_many(f'"{sys.executable}" "{script}"', 3, fmt="tap", progress=False)
            stats = aggregate(runs)

        by_id = {s.test_id: s for s in stats}
        self.assertEqual(by_id["never_works"].verdict, "always-fail")
        self.assertFalse(by_id["never_works"].is_flaky)

    def test_progress_output_goes_to_stream(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "stable.py"
            script.write_text(STABLE_SCRIPT, encoding="utf-8")
            buf = io.StringIO()
            run_many(
                f'"{sys.executable}" "{script}"',
                2,
                fmt="tap",
                progress=True,
                stream=buf,
            )

        text = buf.getvalue()
        self.assertIn("第 1/2 次", text)
        self.assertIn("第 2/2 次", text)


class TestCommandForms(unittest.TestCase):
    def test_list_form_avoids_shell(self):
        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "stable.py"
            script.write_text(STABLE_SCRIPT, encoding="utf-8")
            res = run_once([sys.executable, str(script)], fmt="tap")

        self.assertEqual(res.returncode, 0)
        self.assertEqual(len(res.passed), 2)


if __name__ == "__main__":
    unittest.main()
