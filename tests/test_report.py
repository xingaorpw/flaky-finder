"""聚合与渲染测试：核心是「怎么判定 flaky」。"""

import unittest

from flakyfinder.parsers import ParseResult
from flakyfinder.report import (
    VERDICT_ALWAYS_FAIL,
    VERDICT_FLAKY,
    VERDICT_STABLE,
    aggregate,
    render_table,
    to_json,
)
from flakyfinder.runner import RunResult


def make_run(index: int, failed=(), passed=()):
    return RunResult(
        index=index,
        returncode=1 if failed else 0,
        duration_s=0.1,
        parsed=ParseResult("pytest", failed=set(failed), passed=set(passed)),
    )


class TestVerdict(unittest.TestCase):
    def test_never_failed_is_stable(self):
        runs = [make_run(i, passed={"t1"}) for i in range(3)]
        (s,) = aggregate(runs)
        self.assertEqual(s.verdict, VERDICT_STABLE)
        self.assertFalse(s.is_flaky)

    def test_sometimes_failed_is_flaky(self):
        runs = [
            make_run(0, failed={"t1"}),
            make_run(1, passed={"t1"}),
            make_run(2, passed={"t1"}),
        ]
        (s,) = aggregate(runs)
        self.assertEqual(s.verdict, VERDICT_FLAKY)
        self.assertTrue(s.is_flaky)
        self.assertAlmostEqual(s.pass_rate, 2 / 3)

    def test_always_failed_is_not_flaky(self):
        """一直失败是「坏了」，不是 flaky —— 这个区分很重要。"""
        runs = [make_run(i, failed={"t1"}) for i in range(3)]
        (s,) = aggregate(runs)
        self.assertEqual(s.verdict, VERDICT_ALWAYS_FAIL)
        self.assertFalse(s.is_flaky)
        self.assertEqual(s.pass_rate, 0.0)


class TestFailureOnlyFormats(unittest.TestCase):
    def test_infers_passes_from_absent_failures(self):
        """只打印失败的格式（pytest 默认）也能判断 flaky。

        跑了 4 次，失败 1 次 → 剩下 3 次必然是通过的。
        """
        runs = [
            make_run(0),
            make_run(1, failed={"t1"}),
            make_run(2),
            make_run(3),
        ]
        (s,) = aggregate(runs)
        self.assertEqual(s.failures, 1)
        self.assertEqual(s.passes, 3)
        self.assertEqual(s.verdict, VERDICT_FLAKY)
        self.assertAlmostEqual(s.pass_rate, 0.75)

    def test_single_run_cannot_detect_flaky(self):
        runs = [make_run(0, failed={"t1"})]
        (s,) = aggregate(runs)
        self.assertEqual(s.verdict, VERDICT_ALWAYS_FAIL)
        self.assertFalse(s.is_flaky)


class TestOrdering(unittest.TestCase):
    def test_flaky_sorts_before_broken_before_stable(self):
        runs = [
            make_run(0, failed={"flaky", "broken"}, passed={"stable"}),
            make_run(1, failed={"broken"}, passed={"flaky", "stable"}),
        ]
        verdicts = [s.verdict for s in aggregate(runs)]
        self.assertEqual(
            verdicts,
            [VERDICT_FLAKY, VERDICT_ALWAYS_FAIL, VERDICT_STABLE],
        )


class TestRender(unittest.TestCase):
    def test_reports_flaky_with_rate(self):
        runs = [
            make_run(0, failed={"t_flaky"}),
            make_run(1, passed={"t_flaky"}),
        ]
        out = render_table(aggregate(runs), 2)
        self.assertIn("不稳定的用例", out)
        self.assertIn("t_flaky", out)
        self.assertIn("50%", out)

    def test_separates_always_failing_section(self):
        runs = [make_run(i, failed={"t_broken"}) for i in range(2)]
        out = render_table(aggregate(runs), 2)
        self.assertIn("一直失败", out)
        self.assertIn("不是 flaky", out)

    def test_empty_says_so(self):
        out = render_table([], 3)
        self.assertIn("没有识别到任何用例", out)

    def test_all_stable_says_so(self):
        runs = [make_run(i, passed={"t1", "t2"}) for i in range(3)]
        out = render_table(aggregate(runs), 3)
        self.assertIn("全部稳定通过", out)
        self.assertIn("3 次", out)


class TestJson(unittest.TestCase):
    def test_shape(self):
        runs = [
            make_run(0, failed={"a"}),
            make_run(1, passed={"a"}),
        ]
        data = to_json(aggregate(runs), 2)
        self.assertEqual(data["total_runs"], 2)
        self.assertEqual(data["flaky"], 1)
        self.assertEqual(data["tests"][0]["test"], "a")
        self.assertEqual(data["tests"][0]["verdict"], VERDICT_FLAKY)


if __name__ == "__main__":
    unittest.main()
