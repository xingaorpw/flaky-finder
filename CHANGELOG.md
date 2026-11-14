# Changelog

## [Unreleased]

## [0.1.0] - 2026-11-14

首个可用版本。

### Added

- **反复跑测试**：`flakyfinder run --runs N -- <命令>`，每次打印进度，最后出统计表。
- **五种输出格式**：pytest、unittest、go test、TAP、jest/vitest，`--format auto` 自动识别。
- **区分 flaky 与一直失败**：跑 N 次失败 k 次，`0 < k < N` 才是 flaky，`k == N` 判为「真的坏了」。
- **只打印失败的框架也能算通过率**：用「没失败的次数」补出通过次数。
- **超时不算中断**：单次超时记为一次失败，继续跑完剩余次数。
- **`parse` 子命令**：把保存下来的输出喂给解析器，用于排查格式识别问题。
- **`--fail-on-flaky`**：给 CI 用，发现 flaky 退出码 1。
- **`--json`**：机器可读输出。
- 35 个测试，CI 覆盖 Ubuntu + Windows、Python 3.9 + 3.12，外加真 flaky 套件的冒烟任务。

### Notes

- 零依赖，只用标准库。
- 子进程会注入 `NO_COLOR=1`、`TERM=dumb`，避免 ANSI 颜色破坏正则匹配。

[0.1.0]: https://github.com/xingaorpw/flaky-finder/releases/tag/v0.1.0
