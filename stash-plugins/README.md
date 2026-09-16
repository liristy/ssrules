# Loon 插件合集 → Stash

直接导入项目根目录的 **`stash_plugins.stoverride`**。这是 Stash 原生覆写文件，和原来的 Sub-Store 配置转换脚本 `stash_override.js` 用途不同。

## 使用

1. 在 Stash 的覆写管理中导入 `stash_plugins.stoverride`，为当前配置启用它。
2. 使用较新的 Stash，内嵌脚本 `payload` 要求 iOS/tvOS 3.2.5 或更高版本。文件约 2 MB，首次解析可能稍慢。
3. 在 Stash 中启用 MITM，安装并在系统中完全信任自己的 Stash CA 证书。合集已经包含 MITM 主机名，但不包含 Loon 配置里的 CA 私钥和密码。
4. 基础配置需要有 `AUTO` 策略组。你的现有配置中已有这个组；它对应原 Loon `blockAds.plugin, policy=AUTO` 的代理策略。
5. 同功能的旧去广告覆写建议关闭，避免重复处理响应。此文件可以搭配现有的 Stash 基础配置使用。

本文件按照 Stash 默认合并方式将规则和 HTTP 列表插入基础配置列表之前，不替换 DNS、节点或策略组，也不添加兜底分流规则。保留先匹配规则及插件顺序：各列表删除完全相同的重复项，分流规则进一步删除匹配条件相同或已被前面的域名、全局 QUIC 规则完全覆盖的条目。复杂正则和不同脚本之间的功能重叠不视为重复。

已在合集规则最前面加入全局 QUIC 屏蔽，并保留 `no-track`：

```yaml
rules:
  - PROTOCOL,QUIC,REJECT,no-track
  - AND,((NETWORK,UDP),(DST-PORT,443)),REJECT,no-track
```

第二条同时拦截所有发往 UDP 443 端口的连接。

## 包含内容

抓取日期：2026-09-16。来源为 `loon_config.conf` 的全部 **21 个启用插件**：

- HTTPDNS 拦截、广告联盟拦截、12306、Apple 天气增强、Google 重定向、YouTube。
- 百度网盘、菜鸟、滴滴、叮咚买菜、丰巢、高德、虎扑。
- 可莉去广告合集、淘宝、微博、闲鱼、小红书、萤石云、知乎。
- fmz200 广告拦截与净化合集。

下表为 2026-09-16 的构建结果；每日更新后的实际数量见 `report.json`。

| 类型 | 合并去重后的数量 |
| --- | ---: |
| 分流规则（含 2 条全局 QUIC 屏蔽） | 2,610 |
| URL 重写 | 1,488 |
| 正文重写 | 149 |
| 响应头重写 | 1 |
| Mock 响应 | 11 |
| HTTP 脚本触发项 | 276 |
| 内嵌脚本 | 90 |
| MITM 条目，含排除项 | 986 |

全部脚本、2 份远程 jq、2 份远程 mock 数据已经内嵌，不需要 Stash 再去下载 kelee.one 插件或脚本。脚本自身的天气查询、网络 API 调用仍然需要联网。每份生成文件是当次构建的快照，仓库通过下面的工作流每天更新；在 Stash 中使用远程覆写地址即可获取后续版本。

在原有完全重复项去重基础上，本次再删除 574 条不会被匹配到的分流规则：570 条被前面的域名规则覆盖、2 条局部 QUIC 屏蔽、2 条匹配条件相同的规则。每条删除项及对应保留项记在 `report.json` 的 `shadowed_rules_removed` 中；`no-resolve` 匹配差异和位于宽泛规则前面的直连例外保留。

## 参数和转换细节

- Loon 插件的参数采用源插件声明的默认值；本地 Loon App 中另行修改过的参数不在配置文件里，无法从本次输入中取得。
- YouTube 参数转为 JSON 字符串，保留简体中文字幕默认值；天气与贴吧采用脚本所需的 `key=value` 格式。
- **Apple 天气增强**沿用原插件的 `ColorfulClouds` 默认数据源，API 令牌为空。使用自己的天气 API 时，在两条 WeatherKit 脚本的 `argument` 中填入令牌；不使用外部天气源时，可将 `Weather.Provider` 和 `NextHour.Provider` 都改为 `WeatherKit`。建议只修改本地文件，避免把令牌提交到仓库。
- 保留 `requires-body` → `require-body` 和 `binary-body-mode` → `binary-mode`，没有把二进制脚本当成普通 JSON 脚本。
- 转换 Loon 的正文、响应头、重定向和模拟响应语法。79 条 jq 表达式已编译校验。
- 给 3 份依赖 `$utils.ungzip` 的脚本内嵌 fflate 0.8.2 兼容实现及 MIT 许可证；将 Surge 的 abort 结果转为 Stash 的中断调用。
- 脚本用 async 函数包裹，兼容源脚本顶层 `return`，并在异常时记录日志、放行原始内容。
- 修复源插件中的重复动作、错误段落、朴朴 URL 正则混入标签、肯德基无效正则转义、MITM 域名粘连等问题。具体来源和行号见 `report.json`。
- 原 Loon 的 5 个 MITM 排除域名及合集里的爱奇艺排除项保留在列表前方。
- `force-http-engine: ['*:80']` 使进入 Tunnel 的普通 HTTP 请求也能应用重写。

## 验证与重建

已验证 YAML 解析和回读、所有 HTTP 匹配正则、脚本引用、90 份 JavaScript 语法、79 条 jq 语法、mock 内容、参数、去重和 MITM 排除项。另用真实脚本/表达式测试了 gzip 解压、12306 广告请求拦截与登录请求放行、百度网盘推广项目过滤。

**未在 iPhone 的 Stash 中实际导入或逐个 App 实测。** App 升级、证书固定、重叠规则和脚本运行环境差异仍可能影响具体功能；静态校验不等于全部 App 行为已验证。

使用 Python 3.11+ 和 Node.js 22，可根据已保存的来源快照离线重建：

```powershell
python -m pip install -r stash-plugins/requirements.txt
python stash-plugins/build.py
python stash-plugins/validate.py
```

`sources/` 保存原始插件、jq 与 mock，`scripts/` 保存原始脚本及 gzip 依赖；生成器不修改这些来源快照。`dependencies.json` 记录脚本 URL 对应的本地文件，`report.json` 记录插件来源、哈希、数量和修复明细。`refresh.json` 保存全部资源的内容指纹及最近变化日期。

## 每日自动更新

工作流：`.github/workflows/update-stash-plugins.yml`，名称 **Update Stash plugins**。

- 每天北京时间 **08:23**（UTC 00:23）运行，支持 Actions 页面手动 **Run workflow**。
- 从 `loon_config.conf` 读取已启用插件，用 Loon UA 强制重新抓取插件和全部脚本、远程 jq、mock 数据；gzip 依赖保持指定的 fflate 0.8.2 版本。
- 所有资源下载成功后才替换来源快照；之后重新合并、去重，并运行完整校验。QUIC 全局屏蔽和主配置中的 MITM 排除项继续保留。
- 校验通过后提交有变化的生成文件、资源快照和清单到默认分支，同时提供名为 `stash-plugins` 的 Actions 下载产物，保留 14 天。
- 下载或校验失败时工作流失败，不提交更新，仓库中上次成功生成的覆写仍可使用。源文件出现未知语法时也会停止，避免生成缺失规则的合集。
- 内容不变时保留原变化日期，不产生仅更新时间的提交；同时运行的工作流会排队，不强制推送。

把工作流、`stash-plugins/` 目录和生成文件一起提交并推送到仓库默认分支后，定时任务才会生效。仓库需要启用 Actions，并允许工作流使用 `contents: write` 向默认分支提交。GitHub 定时运行可能延迟，公开仓库连续 60 天没有活动时可能暂停定时任务，详见 [GitHub schedule 文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

推送后可在 Stash 中导入以下远程覆写地址：

```text
https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.stoverride
```

本地手动刷新及重建：

```powershell
python -m unittest discover -s stash-plugins -p 'test_*.py'
python stash-plugins/fetch_dependencies.py --refresh
python stash-plugins/build.py
python stash-plugins/validate.py
```

省略 `--refresh` 时优先使用已有资源快照，只补齐缺失文件。工作流始终使用 `--refresh`，不会因文件已存在而跳过更新。

本次成功使用的资源下载 UA：`Loon/985 CFNetwork/3860.500.111.2.2 Darwin/25.4.0`。

## 格式参考

- [Stash 覆写合并规则](https://stash.wiki/configuration/override)
- [Stash HTTP 重写、正文重写与 Mock](https://stash.wiki/http-engine/rewrite)
- [Stash 脚本参数与二进制模式](https://stash.wiki/script/rewrite-requests)
- [Stash 内嵌脚本 payload](https://stash.wiki/script/manage-script)
- [Stash MITM 配置与证书](https://stash.wiki/http-engine/mitm)
- [Stash 配置样例中的 MITM 排除语法](https://stash.wiki/configuration/example-config)
- [fflate gzip 解压接口](https://github.com/101arrowz/fflate/blob/master/docs/functions/gunzipSync.md)

插件和脚本的原作者信息保留在来源文件及内嵌脚本中。
