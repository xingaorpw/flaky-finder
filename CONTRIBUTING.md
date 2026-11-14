# 参与贡献

## 先跑起来

```bash
git clone https://github.com/xingaorpw/flaky-finder.git
cd flaky-finder
pip install -e .
python -m unittest discover -s tests -t . -v
```

## 几个硬约定

**不要引入第三方依赖。** 卖点就是「pip 装完就能用，不拖任何东西」。

**新增格式要加真实输出样本。** 不要自己编一段「看起来像」的输出 —— 去跑一次真的框架，把结果贴进 `tests/test_parsers.py`。

**不要把 flaky 和失败混为一谈。** 这是整个工具存在的理由。任何让两者混淆的改动都会被拒。

**测试不许自己抖。** 端到端测试里的假 flaky 必须确定性失败（计数器、固定种子），不能用随机数。

**不要为了过测试改断言。** 测试挂了先确认是实现错了还是测试写错了。

## 加一个新格式

1. 在 `parsers.py` 写 `parse_xxx(output) -> ParseResult`
2. 注册进 `PARSERS` 和 `_PRIORITY`
3. 在 `tests/test_parsers.py` 贴真实输出并断言三个集合
4. 更新 README 的格式表

## License

提交的代码默认按 [MIT](LICENSE) 授权。
