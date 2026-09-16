# 广告净化 · 轻量

主覆写：项目根目录的 **`stash_plugins.stoverride`**。

## 从旧版恢复

先停用或删除旧的「广告净化合集」，再导入新的主覆写。不要把新旧两版叠加启用。

主覆写目前约 **18 KB**，包含 **458 条分流规则**（含两条全局 QUIC 屏蔽）及 Loon 主配置的 **5 条 MITM 排除项**。不加载 JavaScript、不改写正文、不启用额外的 HTTPS 解密主机，也不强制所有 HTTP 流量进入重写引擎。无需启用任何增强文件，即可先使用基础拦截。

此前的全量文件约 2 MB，包含 90 份内嵌脚本、大量正文处理与近千个 MITM 条目，用户反馈内存占用过高。因此已停止生成这种全量覆写。文件体积不等于运行内存；当前版本尚未在 iPhone 上测量实际内存。

## fmz200 已移除

Stash 的下载和构建流程均排除 fmz200 综合插件 `blockAds.plugin`，即使它仍在 `loon_config.conf` 中启用，也不会重新加入 Stash。其分流规则、HTTP 重写、脚本、MITM 主机名以及独有的下载资源均已移除。

其余 20 个 Loon 插件继续作为来源。主覆写只取去重后的网络分流规则；需要 HTTP 引擎的 URL / User-Agent 匹配、重写与脚本归入可选增强。

保留先匹配规则及直连例外；重复或已被前面的规则完全覆盖的分流条目会删除。原始来源、去重明细和当前数量见 `report.json`。

## 可选增强

`addons/` 内按应用或功能拆分，共 20 个可选覆写。例如：

- `YouTube_remove_ads.stoverride`
- `RedPaper_remove_ads.stoverride`（小红书）
- `Weibo_remove_ads.stoverride`
- `AppleWeatherEnhancer.stoverride`
- `Amap_remove_ads.stoverride`

这些文件**不会被主覆写自动加载**。先只使用主覆写，恢复稳定后，再逐个导入确实需要的增强文件并观察内存。每个增强文件依赖主覆写中的网络规则；需要处理 HTTPS 时，还需启用 MITM 并安装、信任自己的 Stash 证书。

增强文件不再内嵌脚本，而是引用本仓库 `runtime/` 中经过兼容处理的脚本。目前共 9 份运行脚本，按内容哈希命名；启用对应增强才需要下载。**必须把生成的 `runtime/` 和 `addons/` 一起推送 GitHub，增强文件中的脚本地址才能访问。** 旧版本运行脚本保留，以兼容尚未刷新覆写的客户端。

需要读取正文的脚本上限为 **1 MiB**，超出上限不会执行该脚本；执行超时上限为 10 秒。这是降低开销的取舍，较大的响应可能不再净化。仅把脚本改为外置并不能消除运行开销，因此仍需按需启用。

天气增强沿用源插件的 ColorfulClouds 默认值，令牌为空。需要时编辑该增强文件的两条 WeatherKit 脚本 `argument`；也可将 `Weather.Provider` 和 `NextHour.Provider` 都改为 `WeatherKit`。私有令牌请只保留在本地。

## 每日自动更新

工作流：`.github/workflows/update-stash-plugins.yml`，名称 **Update Stash plugins**。

- 每天北京时间 **08:23** 运行，支持 Actions 页面手动 **Run workflow**。
- 使用 Loon UA 重新抓取允许的插件及其脚本、jq、mock 数据；始终跳过 fmz200 综合插件。
- 生成轻量主覆写、独立增强文件和外置运行脚本，校验通过后才提交。有变化才提交；失败保留仓库中上次成功的版本。
- 校验会阻止主覆写重新出现脚本、正文重写、正向 MITM 主机或 HTTP 强制捕获；也检查增强文件的脚本正文大小限制。
- 下载产物包含主覆写、增强文件、运行脚本和报告，保留 14 天。

将本次修改、生成文件和目录一并推送默认分支后，远程版本才会更新。工作流需要 `contents: write` 权限，并允许提交默认分支。

主覆写远程地址：

```text
https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.stoverride
```

增强文件远程地址示例（按需导入）：

```text
https://raw.githubusercontent.com/liristy/ssrules/main/stash-plugins/addons/YouTube_remove_ads.stoverride
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

`sources/` 和 `scripts/` 保存当前使用的来源，`runtime/` 保存增强文件引用的适配脚本。`validation-input.json` 仅用于构建时校验，已被 Git 忽略，不是供 Stash 导入的文件。`report.json` 区分主覆写数量与全部来源的数量，并列出可选增强。

已做 YAML、正则、JavaScript、jq、引用和去重校验，并测试下载失败保留旧资源、排除 fmz200，以及真实的 12306 拦截/放行行为。尚未在手机端实测实际内存和全部 App 功能。

参考：[Stash 内嵌脚本说明](https://stash.wiki/script/manage-script)、[正文处理与 max-size](https://stash.wiki/script/rewrite-requests)、[高效配置建议](https://stash.wiki/faq/effective-stash)。
