# 参与贡献

请先查阅 README、[更新记录](CHANGELOG.md)和[后续验收计划](docs/ROADMAP.md)。

1. 先创建 Issue 描述问题、运行环境与复现步骤，较大改动先讨论兼容性。
2. Fork 后建立分支，保持修改范围清晰，补充与行为变化有关的测试。
3. 提交 PR 时说明用户可见变化、验证方式和未验证环境。
4. 不提交个人配置、凭据、原始抓包、备份或身份信息；敏感报告见 [SECURITY.md](SECURITY.md)。

## 本地检查

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
ruby tests/test_xiaojing.rb
```

## 版本发布

在干净工作树中更新 CHANGELOG、版本说明及对应 README 链接；发布者确认测试和验收边界后，在已合并的提交上创建 `vX.Y.Z` 标签并推送。Release 工作流会重新运行检查、仅从标签提交打包、生成 SHA-256 并上传附件。0.x 标签自动标为预发布；正式稳定版需先完成验收计划。

本地检查打包方式：`python3 tools/build_release.py v0.1.1`。默认输出到 `dist/`，只包含 HEAD 中已提交文件。调整版本时同步更新 `docs/releases/vX.Y.Z.md` 与受影响包 Makefile 的 PKG_VERSION。自动生成的附件不应手工改写。
