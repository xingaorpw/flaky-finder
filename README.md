# flaky-finder

[![CI](https://github.com/xingaorpw/flaky-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/xingaorpw/flaky-finder/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-35%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![deps](https://img.shields.io/badge/dependencies-0-success)
![license](https://img.shields.io/badge/license-MIT-green)

反复跑测试，找出哪个用例在捣鬼。

> CI 又红了，重跑一次又绿了。到底是哪个用例？这个工具跑 N 次，给你一张表。

---

## 装

```bash
pip install -e .
```

零依赖，只用标准库。

---

## 用

```bash
flakyfinder run --runs 10 -- pytest -q
```

它会跑 10 次，每次打印进度，最后给结论：

```
不稳定的用例（1 个）

  test_concurrent_write  ██████████░░    80%  失败 1/5 次
```

跑一次完整的（真实输出）：

```
跑 5 次：python suite.py
  第 1/5 次  ✓  rc=0  0 失败 / 3 通过  0.2s
  第 2/5 次  ✗  rc=1  1 失败 / 2 通过  0.2s
  第 3/5 次  ✓  rc=0  0 失败 / 3 通过  0.2s
  第 4/5 次  ✓  rc=0  0 失败 / 3 通过  0.2s
  第 5/5 次  ✓  rc=0  0 失败 / 3 通过  0.2s

不稳定的用例（1 个）

  test_concurrent_write  ██████████░░    80%  失败 1/5 次
```

给 CI 用，发现 flaky 就挂：

```bash
flakyfinder run --runs 10 --fail-on-flaky -- pytest -q
```

输出 JSON：

```bash
flakyfinder run --runs 10 --json -- pytest -q
```

---

## 它真正解决的问题：区分「抖」和「坏」

大部分工具会把所有失败混在一起。这两个东西完全不同：

| | 表现 | 该怎么做 |
|---|---|---|
| **flaky** | 有时过有时不过 | 查竞态、时间依赖、共享状态 |
| **一直失败** | 每次都不对 | 就是代码坏了，直接修 |

所以输出分成两段：

```
不稳定的用例（2 个）
  test_concurrent_write  ██████████░░    80%  失败 1/5 次
  test_timezone_boundary ████░░░░░░░░    40%  失败 3/5 次

一直失败（1 个）—— 这不是 flaky，是真的坏了
  test_new_feature       失败 5/5 次
```

**判定规则**：跑了 N 次，某用例失败了 k 次。`0 < k < N` 才是 flaky；`k == N` 是坏了。

这条规则有个好处：**只打印失败的框架也能判断**。pytest 默认不输出 PASSED 行，但它不失败的次数就是通过次数，一样能算出通过率。

---

## 支持的测试输出格式

| 格式 | 命令示例 | 说明 |
|---|---|---|
| `pytest` | `pytest -v` / `pytest -q` | 有 `PASSED` 行最好；只有 `FAILED` 行也行 |
| `unittest` | `python -m unittest -v` | `test_x (mod.Cls.test_x) ... ok` |
| `go` | `go test -v ./...` | 支持子测试 `TestX/case` |
| `tap` | `node --test` / `bats` / `prove` | `ok 1 - name` / `not ok 2 - name` |
| `jest` | `jest --verbose` / `vitest` | `✓` / `✕` / `○`，按文件分组 |

默认 `--format auto`：把五个解析器都跑一遍，取识别出用例最多的那个。

不确定时先看一眼它认出了什么：

```bash
pytest -q > out.txt 2>&1
flakyfinder parse out.txt
```

---

## 全部参数

```bash
flakyfinder run [--runs N] [--timeout S] [--cwd DIR] [--format F]
                [--json] [--fail-on-flaky] -- <测试命令>
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--runs` | 5 | 跑几次。10 次能抓到 10% 概率的抖 |
| `--timeout` | 无 | 单次超时秒数，超时记为一次失败而不是中断整个任务 |
| `--cwd` | 当前目录 | 在哪个目录跑 |
| `--format` | auto | 见上表 |
| `--json` | 关 | 输出机器可读结果 |
| `--fail-on-flaky` | 关 | 有 flaky 就退出码 1 |

退出码：`0` 没有 flaky，`1` 有 flaky（仅 `--fail-on-flaky`），`2` 用法错误。

---

## 已知限制

这些是当前版本就做不到，不是待优化项：

- **只认行式输出。** 输出里没有任何逐用例信息的框架（比如只打印一个 `.` 的 `pytest -q --no-header` 极端情况）抓不到用例名，只能看到"这次失败了"。
- **不做二分定位。** 它告诉你哪个用例抖，不告诉你是哪一行代码抖。定位要自己上 `pytest --lf` 或 `--bisect`。
- **不控制并发。** 串行跑 N 次。想复现并发相关的抖，得靠 `-p xdist` 这类参数自己加进命令里。
- **颜色会干扰解析。** 子进程会注入 `NO_COLOR=1`、`TERM=dumb`，但如果你的测试框架无视这些变量，可能解析不到。
- **不缓存结果。** 每次都是真跑。

---

## 跑测试

```bash
python -m unittest discover -s tests -t . -v
```

35 个用例：

| 文件 | 覆盖 |
|---|---|
| `test_parsers.py` | 五个框架的真实输出片段、参数化用例名、子测试、垃圾输入不崩 |
| `test_report.py` | flaky / 一直失败 / 稳定 的判定、只打印失败时的通过率推算、排序、渲染 |
| `test_runner.py` | **真起子进程**：超时不抛异常、退出码、列表形式 vs shell 形式、端到端检测 flaky |

端到端测试用的「假 flaky」是确定性失败的（靠计数器文件，不用随机数），所以测试本身不会抖。

CI 在 Ubuntu 和 Windows 上跑 Python 3.9 和 3.12，外加一个用真 flaky 套件验证 `--fail-on-flaky` 的冒烟任务。

---

## 为什么不用 pytest-rerunfailures

那个插件是**让测试变绿**（失败自动重跑）。这个工具是**让问题暴露**（跑 N 次统计通过率）。

方向相反。两个可以一起用：先用这个找出谁在抖，再用 rerun 兜住它。

---

## License

[MIT](LICENSE) © 2026 xingaorpw
