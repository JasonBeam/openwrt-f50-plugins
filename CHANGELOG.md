# Changelog

All notable changes are documented here using [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/); 0.x releases are experimental.

## [Unreleased]

### Added
- 2026-10-22：为已有 MU300 `f50.iot` 流量池集成版增加自定义小鲸 IoT 刷新间隔（5–1440 整数分钟，默认20分钟），包括页面、后端校验、私有配置原子保存及自动任务热读取。
- 新增离线兼容补丁工具、调度/数据保留隔离测试及集成说明；不会覆盖独立插件或自动安装到路由器。

### Changed
- 集成版过期判定跟随配置间隔；保存间隔不直接查询平台，不改额度、凭据及流量历史。
- 按实机反馈保留原流量池布局，将间隔输入缩到同步按钮旁；兼容浏览器 RPC 自动附带的会话元数据，不把它写入配置。
- Android/UFI 版 RA 刷新仍处于待设备检查阶段，本次未实现、未发布；本次更新不涉及 Wi-Fi 驱动或固件。

## [0.1.1] - 2026-10-16

### Added
- Added adaptive RA lifetime observation and sampled renewal intervals, with unknown values kept explicit.
- Added an adaptive-mode switch and LuCI status for learned lifetimes and renewal results; fixed-mode settings remain available.

### Fixed
- Verify actual route renewal after router solicitation instead of trusting the tool exit code alone.
- Discard learning across boot, interface or gateway changes and exclude this script's solicited responses from natural-cadence samples.

## [0.1.0] - 2026-10-16

### Added
- Added independent IPv6 RA refresh and Xiaojing IoT calibration source packages.
- Added optional LuCI interfaces, disabled defaults, installation guidance and isolated checks.
- Added versioned Release downloads, SHA-256 checksums, a release workflow and contributor guidance.

[0.1.0]: https://github.com/JasonBeam/openwrt-f50-plugins/releases/tag/v0.1.0

[0.1.1]: https://github.com/JasonBeam/openwrt-f50-plugins/compare/v0.1.0...v0.1.1
