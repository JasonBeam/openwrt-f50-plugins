# OpenWrt F50 插件库

面向 ZTE F50 / MU300 OpenWrt 的独立小工具。两项功能可以分别安装、下载、Fork 和修改。

> **0.1.0 实验性源码版**：已做代码审查和隔离测试，但尚未完成 SDK 打包、全新设备安装/卸载、开机以及新 LuCI 页面的实机验收。不是可直接添加到路由器的软件包下载源；暂不提供未经验证的 APK/IPK。不要在唯一的上网设备上直接试装。

## 按需选择

| 需要什么 | 纯后台包 | 可选 LuCI 界面 |
| --- | --- | --- |
| IPv6 RA 寿命检查与刷新 | `f50-ra-refresh` | `luci-app-f50-ra-refresh` |
| 小鲸 IoT 流量池校正 | `f50-xiaojing` | `luci-app-f50-xiaojing` |

两个后台包互不依赖；安装界面才会自动选择对应后台。不覆盖固件原有的流量池页面。

### RA 刷新

- 按剩余寿命阈值请求真实 Router Advertisement；默认间隔 3600 秒、阈值 7200 秒。
- 默认只允许逻辑 `wan` 下的 `sipa_eth` 网卡；其他设备需先核对接口再配置。
- **不删除/替换路由、不改 DNS、不重启网络或设备**，不编造无限寿命路由。
- 需要可信来源、与设备架构匹配的 `rdisc6`。本库不附带个人设备上的二进制。
- 不保证运营商一定回应请求，也不修复所有 IPv6 或驱动问题。

### 小鲸 IoT 校正

- 查询小鲸平台，更新当前周期额度和已用量；每日、自然月历史不变。
- 两次同步之间仍使用原流量池的网卡统计；默认间隔 1200 秒。
- **只兼容提供 `unisoc.traffic get/set` 的 MU300 流量池**，不是任意 OpenWrt 通用计费服务。
- 只支持当前小鲸平台接口，不是所有 IoT 卡运营商的通用查询器。
- 查询失败不校正流量池，保留最近成功的平台快照并显示失败/过期状态。
- 卡号和查询验证码存放在后端私有目录，状态接口不读回凭据。
- 默认关闭、默认只尝试 HTTPS；**只有明确勾选风险许可后才使用 HTTP**。HTTP 会暴露查询凭据和结果给链路上的第三方；不会自动降级。
- 平台按 1024 MB/显示 GB 换算，本机原统计仍按原口径累计；运营商数据也可能延迟，不能保证实时账单精度。
- 每月重置日由原流量池管理，插件不会从平台推断结算日，请自行核对。

## 下载源码与修改

[下载全部源码 ZIP](https://github.com/JasonBeam/openwrt-f50-plugins/archive/refs/heads/main.zip)，也可 Fork 后修改。
要按功能取用，可以只复制该功能的后台目录及对应 `luci-app-*` 目录。
不要只取一个可执行文件就认为依赖、权限和服务已安装完整。

```sh
git clone https://github.com/JasonBeam/openwrt-f50-plugins.git
```

## 用对应版本的 OpenWrt SDK 构建

在**匹配目标固件**的 SDK/源码树中加入 feed；不要直接在路由器上运行这些构建命令。

```sh
printf '%s\n' 'src-git f50 https://github.com/JasonBeam/openwrt-f50-plugins.git' >> feeds.conf.default
./scripts/feeds update f50
# 只要 RA：
./scripts/feeds install -p f50 f50-ra-refresh luci-app-f50-ra-refresh
# 只要小鲸：
./scripts/feeds install -p f50 f50-xiaojing luci-app-f50-xiaojing
make menuconfig
```

在 menuconfig 选择需要的包，然后编译，例如：

```sh
make package/f50-ra-refresh/compile V=s
make package/luci-app-f50-ra-refresh/compile V=s
```

小鲸对应目标是 `package/f50-xiaojing/compile` 与 `package/luci-app-f50-xiaojing/compile`。
生成 APK 或 IPK 取决于你的 SDK，不要混用包格式、版本或随意安装其他内核的模块。
本库不提供 kmod，不安装/替换 Wi-Fi 或基带驱动。

## 安装前与使用

完整步骤见 [安装、配置和卸载](docs/INSTALL.md)。两项功能均默认关闭，需明确启用。
若已装有同名的私人脚本/服务，**先备份并在测试设备上处理冲突**；不要覆盖生产设备。

安装对应 LuCI 包后，入口在「服务 → IPv6 RA 刷新」和「服务 → 小鲸 IoT 校正」。
纯后台也可用 CLI；凭据不要放在命令行参数、Issue 或日志里。

## 审查与测试边界

见 [代码审查与验收记录](docs/REVIEW.md)。可在开发电脑上运行：

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
ruby tests/test_xiaojing.rb
```

测试使用虚拟卡号、模拟运营商及流量池，不会查询真实账号或修改路由。
GitHub Actions 运行相同的源码检查；CI 绿灯**不代表**真实设备的网络、WPA3 或稳定性已验证。

## 参与与许可

欢迎 Fork 或提交 PR。先说明影响范围、兼容性和测试证据，再审查合并；请勿附带卡号或设备备份。
[MIT License](LICENSE) 允许使用、修改和再分发。外部 `rdisc6`、OpenWrt 和 LuCI 依赖仍遵守各自许可。
