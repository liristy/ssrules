# 广告净化

主覆写：项目根目录的 **`stash_plugins.stoverride`**。

## 从旧版恢复

先停用或删除旧的主覆写及独立增强覆写，再导入新的主覆写。所有功能已合并，只需导入这一个文件，避免与旧的独立增强重复执行。

主覆写目前约 **71 KB**，包含 **477 条分流规则**（含两条全局 QUIC 屏蔽）、**213 条 URL 拦截/重定向**、**73 条原生正文重写**（包括 jq、JSON 操作）、**1 条静态响应**及 **9 份 JavaScript 的 58 条触发规则**。不强制所有 HTTP 流量进入重写引擎。

MITM 列表共 **123 项**，包括 Loon 主配置的 **5 条排除项**，排除项优先。普通拦截、原生重写和脚本对应的解密列表均已合并去重。

HTTPS 重写需要在 Stash 中启用 MITM 并安装、信任自己的证书。原生正文重写需要 **Stash 2.8+**。原生重写仍有正文处理和 HTTPS 解密开销，不代表零内存开销。

此前的全量文件约 2 MB，包含 90 份内嵌脚本、大量正文处理与近千个 MITM 条目，用户反馈内存占用过高。因此已停止生成这种全量覆写。文件体积不等于运行内存；当前版本尚未在 iPhone 上测量实际内存。

## fmz200 已移除

Stash 的下载和构建流程均排除 fmz200 综合插件 `blockAds.plugin`，即使它仍在 `loon_config.conf` 中启用，也不会重新加入 Stash。其分流规则、HTTP 重写、脚本、MITM 主机名以及独有的下载资源均已移除。

其余 20 个 Loon 插件继续作为来源。主覆写保留去重后的全部分流规则（含 URL / User-Agent 匹配）、URL 重写、原生请求头/正文重写、静态响应和 JavaScript 配置。目前来源中没有独立的原生请求头重写。

保留先匹配规则及直连例外；重复或已被前面的规则完全覆盖的分流条目会删除。原始来源、去重明细和当前数量见 `report.json`。

## 脚本已合并

此前拆出的 12306、高德、天气、虎扑、小红书、淘宝、微博和 YouTube 脚本配置全部加入主覆写，不再生成 `addons/` 独立覆写。

主文件通过 `script-providers` 引用本仓库 `runtime/` 中经过兼容处理的脚本，共 9 份，按内容哈希命名。无需手动导入脚本文件。**必须把主覆写和生成的 `runtime/` 一起推送 GitHub，主覆写中的脚本地址才能访问。** 旧版本运行脚本保留，以兼容尚未刷新覆写的客户端。

需要读取正文的脚本上限为 **1 MiB**，超出上限不会执行该脚本；执行超时上限为 10 秒。较大的响应可能不再净化。脚本外置只减少配置体积，不消除运行开销；此次合并会恢复所有脚本功能的运行开销，手机端实际内存尚未测量。

天气增强沿用源插件的 ColorfulClouds 默认值，令牌为空。需要时编辑主覆写的两条 WeatherKit 脚本 `argument`；也可将 `Weather.Provider` 和 `NextHour.Provider` 都改为 `WeatherKit`。私有令牌请只保留在本地。

## 每日自动更新

工作流：`.github/workflows/update-stash-plugins.yml`，名称 **Update Stash plugins**。

- 每天北京时间 **08:23** 运行，支持 Actions 页面手动 **Run workflow**。
- 使用 Loon UA 重新抓取允许的插件及其脚本、jq、mock 数据；始终跳过 fmz200 综合插件。
- 生成合并后的主覆写和外置运行脚本，校验通过后才提交。有变化才提交；失败保留仓库中上次成功的版本。
- 校验确保全部分流、原生重写、脚本及 MITM 配置没有遗漏，检查去重、脚本引用、正文大小和超时限制，并阻止 HTTP 强制捕获及 fmz200 综合插件重新加入。
- 下载产物包含主覆写、运行脚本和报告，保留 14 天。

将本次修改、生成文件和目录一并推送默认分支后，远程版本才会更新。工作流需要 `contents: write` 权限，并允许提交默认分支。

主覆写远程地址：

```text
https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.stoverride
```

## 本地构建与验证

需要 Python 3.11+ 和 Node.js 22：

```powershell
python -m pip install -r stash-plugins/requirements.txt
python -m unittest discover -s stash-plugins -p 'test_*.py'
python stash-plugins/fetch_dependencies.py --refresh
python stash-plugins/build.py
python stash-plugins/validate.py
```

省略 `--refresh` 时优先使用本地快照。全部资源下载成功后才更新快照，同时删除依赖清单中已不再引用的原始脚本。

`sources/` 和 `scripts/` 保存当前使用的来源，`runtime/` 保存主覆写引用的适配脚本。`validation-input.json` 仅用于构建时校验，已被 Git 忽略，不是供 Stash 导入的文件。`report.json` 记录主覆写数量、来源和去重明细。

已做 YAML、正则、JavaScript、jq、引用和去重校验，并测试下载失败保留旧资源、排除 fmz200，以及真实的 12306 拦截/放行行为。尚未在手机端实测实际内存和全部 App 功能。

参考：[Stash 原生 HTTP 重写及版本要求](https://stash.wiki/http-engine/rewrite)、[MITM 配置](https://stash.wiki/http-engine/mitm)、[正文处理与 max-size](https://stash.wiki/script/rewrite-requests)、[高效配置建议](https://stash.wiki/faq/effective-stash)。
