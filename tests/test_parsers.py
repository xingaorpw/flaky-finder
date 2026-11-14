"""解析器测试：用各框架的真实输出片段。"""

import unittest

from flakyfinder.parsers import (
    FORMATS,
    parse,
    parse_go,
    parse_jest,
    parse_pytest,
    parse_tap,
    parse_unittest,
)


PYTEST_VERBOSE = """\
tests/test_a.py::test_ok PASSED                                      [ 33%]
tests/test_a.py::test_bad FAILED                                     [ 66%]
tests/test_a.py::test_param[1-2] PASSED                              [100%]

=================================== FAILURES ===================================
_________________________________ test_bad _____________________________________
"""

PYTEST_SHORT = """\
tests/test_a.py ..F                                                  [100%]
=================================== FAILURES ===================================
FAILED tests/test_a.py::test_bad - AssertionError: assert 1 == 2
ERROR tests/test_b.py::test_boom
"""

UNITTEST_VERBOSE = """\
test_ok (tests.test_a.TestA.test_ok) ... ok
test_bad (tests.test_a.TestA.test_bad) ... FAIL
test_skip (tests.test_a.TestA.test_skip) ... skipped 'not on windows'
test_err (tests.test_a.TestA.test_err) ... ERROR
test_xf (tests.test_a.TestA.test_xf) ... expected failure
"""

GO_VERBOSE = """\
=== RUN   TestAdd
--- PASS: TestAdd (0.00s)
=== RUN   TestSub
--- FAIL: TestSub (0.00s)
    --- FAIL: TestSub/negative (0.00s)
"""

TAP_OUT = """\
TAP version 13
ok 1 - adds two numbers
not ok 2 - subtracts
ok 3 - skips when needed # SKIP not supported
1..3
"""

JEST_OUT = """\
PASS src/math.test.js
  ✓ adds (3 ms)
  ✕ subtracts (1 ms)
  ○ todo later
FAIL src/other.test.js
  ✕ renders
"""


class TestPytest(unittest.TestCase):
    def test_verbose_statuses(self):
        res = parse_pytest(PYTEST_VERBOSE)
        self.assertIn("tests/test_a.py::test_ok", res.passed)
        self.assertIn("tests/test_a.py::test_bad", res.failed)
        self.assertIn("tests/test_a.py::test_param[1-2]", res.passed)

    def test_short_output_only_failures(self):
        res = parse_pytest(PYTEST_SHORT)
        self.assertEqual(res.failed, {"tests/test_a.py::test_bad", "tests/test_b.py::test_boom"})
        self.assertEqual(res.passed, set())

    def test_no_duplicate_when_both_sections(self):
        res = parse_pytest(PYTEST_VERBOSE + PYTEST_SHORT)
        self.assertEqual(len(res.failed), 2)


class TestUnittest(unittest.TestCase):
    def test_statuses(self):
        res = parse_unittest(UNITTEST_VERBOSE)
        self.assertIn("tests.test_a.TestA.test_ok", res.passed)
        self.assertIn("tests.test_a.TestA.test_bad", res.failed)
        self.assertIn("tests.test_a.TestA.test_err", res.failed)
        self.assertIn("tests.test_a.TestA.test_skip", res.skipped)

    def test_expected_failure_is_not_a_failure(self):
        """unittest 的 expected failure 不会让 CI 变红，所以不能算失败。"""
        res = parse_unittest(UNITTEST_VERBOSE)
        self.assertIn("tests.test_a.TestA.test_xf", res.skipped)
        self.assertNotIn("tests.test_a.TestA.test_xf", res.failed)


class TestGo(unittest.TestCase):
    def test_statuses_and_subtests(self):
        res = parse_go(GO_VERBOSE)
        self.assertIn("TestAdd", res.passed)
        self.assertIn("TestSub", res.failed)
        self.assertIn("TestSub/negative", res.failed)


class TestTap(unittest.TestCase):
    def test_statuses(self):
        res = parse_tap(TAP_OUT)
        self.assertIn("adds two numbers", res.passed)
        self.assertIn("subtracts", res.failed)
        self.assertIn("skips when needed", res.skipped)

    def test_ignores_trailing_plan(self):
        res = parse_tap("1..0\n")
        self.assertEqual(res.total, 0)


class TestJest(unittest.TestCase):
    def test_groups_by_file(self):
        res = parse_jest(JEST_OUT)
        self.assertIn("src/math.test.js::adds", res.passed)
        self.assertIn("src/math.test.js::subtracts", res.failed)
        self.assertIn("src/math.test.js::todo later", res.skipped)
        self.assertIn("src/other.test.js::renders", res.failed)


class TestAutoDetect(unittest.TestCase):
    def test_picks_matching_format(self):
        self.assertEqual(parse(PYTEST_VERBOSE).fmt, "pytest")
        self.assertEqual(parse(UNITTEST_VERBOSE).fmt, "unittest")
        self.assertEqual(parse(GO_VERBOSE).fmt, "go")
        self.assertEqual(parse(JEST_OUT).fmt, "jest")

    def test_empty_output_returns_empty(self):
        res = parse("")
        self.assertEqual(res.total, 0)

    def test_garbage_does_not_crash(self):
        res = parse("完全不是测试输出\n随便什么\n")
        self.assertEqual(res.total, 0)

    def test_explicit_format_bypasses_detection(self):
        res = parse(PYTEST_SHORT, "pytest")
        self.assertEqual(res.fmt, "pytest")
        self.assertEqual(len(res.failed), 2)

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            parse("x", "nope")

    def test_all_formats_registered(self):
        for name in ("pytest", "unittest", "go", "tap", "jest"):
            self.assertIn(name, FORMATS)


if __name__ == "__main__":
    unittest.main()
