# 哪些适合做成 IPK / APK？

**四个独立包适合走标准 OpenWrt 打包；已有 MU300 集成补丁暂时保留为离线补丁工具。** 适合打包不等于已经生成可安装附件，也不等于完成设备验收。

## 推荐打包组合

| 组合 | 包名 | 建议 |
| --- | --- | --- |
| RA 后台 | `f50-ra-refresh` | 优先完成 SDK 构建与测试设备验收；同时解决可信 `rdisc6` 的提供方式 |
| RA 网页设置 | `luci-app-f50-ra-refresh` | 与 RA 后台配套发布；需要 LuCI，并验证 rpcd 权限与页面交互 |
| 小鲸后台 | `f50-xiaojing` | 适合打包，但只面向有兼容 `unisoc.traffic` 的固件 |
| 小鲸网页设置 | `luci-app-f50-xiaojing` | 与小鲸后台配套发布；验证凭据保存、换卡、失败保留和同步行为 |
| 已有流量池间隔补丁 | `integrations/mu300/` + `tools/apply_mu300_interval.py` | 依赖特定旧文件与代码锚点，暂不包装成可通用安装的第五个包 |

两个后台可以单独安装；需要网页操作时，再安装对应 LuCI 包。按两个功能组合分别发布，不必把四个包捆成一个不可拆的大包。

## IPK 还是 APK，取决于目标固件

这里的 APK 是 **OpenWrt 的软件包格式，不是 Android 应用**。不要根据设备叫 F50、CPU 架构或系统界面猜格式。

先在目标 OpenWrt 设备上做只读检查：

```sh
cat /etc/openwrt_release
ubus call system board
command -v opkg
command -v apk
```

输出供自己核对；公开反馈前删除序列号或其他设备身份信息。仅发现某个命令存在还不够，应同时确认该固件实际使用的包管理器、软件仓库、目标平台与对应 SDK。

- 使用 opkg 的目标，应由对应 SDK 生成 IPK。
- 使用 apk 的目标，应由对应 SDK 生成 OpenWrt APK。
- 找不到与固件匹配的 SDK / 源码树时，先向固件维护者核对；不要把其他固件的包直接装进去。

**不能通过重命名后缀转换格式。** 如果以后同时发布两种格式，应分开注明各自匹配的固件与 SDK，而不是声称一份附件适配所有 F50。

## 现有 Makefile 能说明什么

四个目录已提供 OpenWrt Makefile。后台使用 `PKGARCH:=all`，LuCI 使用 `LUCI_PKGARCH:=all`，主要安装 Shell / Ruby / JavaScript、配置与服务文件，不包含内核驱动编译。

`all` 只说明这些包本身没有按 CPU 编译的程序，不表示任意 OpenWrt 固件都兼容：

- RA 依赖 `ip-full`、`flock`、`jsonfilter`、`ubus`、`uci`；还要求另行提供可信、匹配设备架构的 `rdisc6`。当前 Makefile 没有自动解决这个外部工具的来源。
- 小鲸依赖 `ruby`、`ruby-json`、`curl`、`ca-bundle`、`ubus`；其目标固件还必须提供预期格式的 `unisoc.traffic` 服务。
- LuCI 包依赖对应后台与 `luci-base`；具体页面 API 和权限仍需在目标 LuCI 版本中检查。

## 在匹配的 SDK 中构建独立插件

以下命令在**开发电脑的 SDK / OpenWrt 源码树**中运行，不是在路由器上运行。需要先按 SDK 自身说明准备受支持的构建环境。

在 `feeds.conf.default` 中加入源。只添加一次，已有同名条目时核对它，不要反复追加：

```text
src-git f50 https://github.com/JasonBeam/openwrt-f50-plugins.git
```

以上默认跟踪 `main`。复现固定 Release 时可将来源固定到已验证的标签或提交；OpenWrt `src-git` 的固定提交写法示例：

```text
src-git f50 https://github.com/JasonBeam/openwrt-f50-plugins.git^37103754c55a
```

这里 `37103754c55a` 对应 v0.1.1。选择固定版本后，要核对 feed 实际检出的提交；不要把当前 main 的集成补丁混进旧版构建说明。

```sh
./scripts/feeds update f50
# 只需要 RA 时：
./scripts/feeds install -p f50 f50-ra-refresh luci-app-f50-ra-refresh
# 只需要小鲸时：
./scripts/feeds install -p f50 f50-xiaojing luci-app-f50-xiaojing
make menuconfig
```

在 `menuconfig` 选择需要的包后编译。例如 RA：

```sh
make package/f50-ra-refresh/compile V=s
make package/luci-app-f50-ra-refresh/compile V=s
```

小鲸对应目标：

```sh
make package/f50-xiaojing/compile V=s
make package/luci-app-f50-xiaojing/compile V=s
```

产物路径与格式以 SDK 输出为准。SDK 构建尚未在本项目完成验收，本节提供构建入口，不宣称这些命令已在你的固件对应 SDK 上跑通。

## 达到什么条件再上传可安装包

建议先完成 RA 组合，再验证兼容固件上的小鲸组合。每组至少要有：

1. 目标固件版本、SDK / 源码提交、架构、包管理器与依赖来源。
2. 一次干净 SDK 构建和依赖检查，RA 的 `rdisc6` 来源、许可及架构另行注明。
3. 测试设备上的首次安装、默认关闭、启用、开机、升级、停用与卸载结果。
4. LuCI / rpcd 验收，以及原配置、凭据和历史保留验证。
5. 真实请求的结果与失败回退记录；小鲸另需明确 HTTP / HTTPS 行为。

满足后再将真正的 `.ipk` / `.apk` 和 `SHA256SUMS.txt` 加入新的预发布 Release。源码 ZIP 可以继续提供，但应与安装包分栏说明；在完成以上验证前，继续标为实验性源码。

[返回首页](../README.md) · [安装与配置](INSTALL.md) · [版本怎么选](VERSIONS.md)
