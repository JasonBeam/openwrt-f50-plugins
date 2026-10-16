# 安装、配置和卸载

## 兼容性与准备

这是实验性源码 feed。先用测试设备验收，保留 USB/串口等恢复通道，并自行备份现有配置。
尚未提供经过 SDK 构建和全新安装验收的二进制包。使用与固件匹配的 SDK 生成 APK/IPK 后，再通过该固件的软件包管理器安装；不要用 `--force` 掩盖依赖冲突。

- 公共依赖由各包 Makefile 声明。
- RA 另需可信、匹配 CPU 架构的 `rdisc6`，例如 [ndisc6 项目](https://www.remlab.net/ndisc6/)提供的工具。必须核对其来源、构建与许可；本仓库没有捆绑二进制，也不自动下载执行脚本。
- RA 会依次检查 `/usr/bin/rdisc6`、`/usr/sbin/rdisc6`、`/usr/libexec/f50-rdisc6`。
- 小鲸必须在设备上已有兼容的 `unisoc.traffic` 服务；安装本插件不会创建计费流量池。
- 后台包可以单独使用，LuCI 包则依赖对应后台。两个功能没有互相依赖。
- 同名私人脚本不是包管理器可可靠处理的迁移源；安装前检查 `/etc/init.d/f50-*` 与 `/etc/f50-xiaojing`，不要覆盖正在使用的私人部署。

新安装后如状态接口尚未注册，可运行 `/etc/init.d/rpcd reload` 再重新登录 LuCI。
这只重新加载管理接口，不重启网络或设备。

## RA

默认不开启。先只读查看：

```sh
/usr/sbin/f50-ra-refresh --status
ubus call network.interface.wan status
```

确认逻辑 WAN、真实网卡前缀和 `rdisc6` 都正确后，再配置。例如展锐蜂窝 `sipa_eth*`：

```sh
uci set f50_ra.main.network='wan'
uci set f50_ra.main.device_prefix='sipa_eth'
uci set f50_ra.main.interval='3600'
uci set f50_ra.main.threshold='7200'
uci set f50_ra.main.enabled='1'
uci commit f50_ra
/etc/init.d/f50-ra-refresh enable
/etc/init.d/f50-ra-refresh restart
```

### v0.1.1 自适应模式

`f50_ra.main.adaptive` 默认为 `1`，包括旧配置尚无此项的情况；服务总开关 `enabled` 仍默认关闭，不会因更新自动启用。
上面的 `interval=3600` 只用于固定模式；`threshold=7200` 在自适应模式中作为上限。

- 自动观察通常间隔 60 秒，剩余寿命不足 240 秒时为 10 秒，寿命未知时为 30 秒。
- 自适应阈值为已知寿命的 1/4，至少 30 秒、最多 7200 秒，同时不超过已配置阈值。
- 没有真实通告寿命时，剩余值只作为观察下界。自然续期至少需两个样本才显示间隔，主动请求不计入；本脚本请求后 30 秒内的跳升也不作为自然样本。其他程序发 RS、漏掉采样仍可能影响结果，这不是抓包证明的运营商周期。
- 状态位于 `/var/run/f50-ra-refresh.state`，重启、启动 ID、接口索引或默认网关变化后重新学习；不保存到闪存。
- `--status` 保留原有 JSON 字段，增加 `adaptive`、`lifetime`、`lifetime_source`、`natural_interval`、`observed_renewals`、`last_event`；未知寿命或间隔为 JSON `null`，状态查询不触发请求或写入学习文件。
- 主动请求仍使用标准组播 RS；回读路由确实续期或确认当前网关回包且已接近通告寿命后才记成功。工具退出成功但倒计时未更新会返回失败。

恢复旧固定策略时设置 `uci set f50_ra.main.adaptive='0'`，提交配置并只重启此服务。更新源码时 RA 后台与对应 LuCI 都为 0.1.1，小鲸仍为 0.1.0。

按阈值检查一次：`f50-ra-refresh --once`。健康路由不会额外发送 RS。
`--force` 会绕过寿命阈值，但仍要求启用、WAN 匹配并有可信工具；不要在不清楚用途时执行。
如果剩余寿命未知但有 RA 路由，默认不会强行改动。

通过 LuCI 修改设置需「保存并应用」，服务只重新加载自身，不重启网络。

## 小鲸

在「服务 → 小鲸 IoT 校正」填写自己的卡号、必要时的查询验证码、目标 SIM 和同步间隔。
凭据输入框只用于写入，不显示已保存的凭据；同一张卡留空保留，更换卡号时验证码留空表示不使用旧验证码。
新安装需启动/启用对应服务：

```sh
/etc/init.d/f50-xiaojing enable
/etc/init.d/f50-xiaojing start
```

勾选自动校正并保存后，后台会在下一次配置检查时启用（最多约 30 秒）。
未勾选时不查询运营商、不更改流量池；状态页和手动同步入口仍可使用，但手动同步也要求明确启用。

### 重要的 HTTP 风险

默认 HTTPS。若平台不提供可用 HTTPS，查询会失败；插件**不会偷偷降级到 HTTP**。
只有你明确接受风险并勾选「允许明文 HTTP 查询」时，才会用 HTTP。
这样卡号、验证码及流量数据可能被网络链路上的第三方看到；不能靠安装此插件消除这一风险。
也不应把 HTTP 接口经代理转发给不可信节点。

只读状态：

```sh
/usr/libexec/f50-xiaojing --status
```

`--preview` 会查询平台但不写流量池或成功状态，仍会发送你的凭据给已配置的小鲸平台；不是离线测试。
`--sync` 才会执行真实校正。新手建议使用网页的确认按钮，不要为测试清空流量池。
查询成功不代表流量卡服务商的账单是实时的，剩余量以服务商最终计费为准。

## 停用与卸载

先停用，避免卸载过程中还有任务运行：

```sh
/etc/init.d/f50-ra-refresh stop
/etc/init.d/f50-ra-refresh disable
/etc/init.d/f50-xiaojing stop
/etc/init.d/f50-xiaojing disable
```

只安装其中一项时，只执行对应服务命令。用固件软件包管理器先卸载对应 LuCI 包，再卸载后台包。
插件不会自动删除 `/etc/f50-xiaojing` 中的私有凭据、状态或 RA 的已修改配置；是否保留 conffile 也受包管理器行为影响，卸载前请自行保存需要的数据。
卸载后如不再需要凭据，应在确认精确文件后自行安全清理。**不要把这些目录打包提交到 GitHub。**
插件不删除流量池，不清空历史，不撤销运营商账单，也不删除现有 IPv6 路由。

## 后续修改

Fork 仓库后，每个功能位于独立目录，修改后跑测试，使用对应 SDK 构建再在测试设备上验收。
新版本包的源码审核、SDK 构建、开机、停用、卸载、失败恢复和真实请求验证是不同步骤，不能互相代替。
