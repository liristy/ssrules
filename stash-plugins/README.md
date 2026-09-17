# 广告净化

只需导入项目根目录的 `stash_plugins.stoverride`。主文件保留开屏去广告、YouTube 去广告、苹果天气增强，以及盒马净化、通用广告平台网络拦截和 QUIC 屏蔽。

## 当前范围

主文件约 28 KB，包含 457 条分流规则、26 条 URL 拦截/跳转、2 条原生正文重写、1 条静态响应，以及 8 份 JavaScript 的 14 条触发规则。MITM 共 40 项，原有 5 条排除项优先。

| 应用 | JS 触发规则 | 保留功能 |
|---|---:|---|
| 微博 | 3 | 开屏预加载、SDK 开屏、缓存开屏广告 |
| YouTube | 3 | 去广告及配套请求处理，使用两份脚本 |
| 苹果天气 | 2 | 天气可用性与天气数据增强 |
| 小红书 | 2 | 开屏配置及开屏广告 |
| 淘宝 | 2 | 开屏视频、图片及开屏活动 |
| 高德地图 | 1 | 开屏广告 |
| 盒马 | 1 | 首页、“我的”页和推荐流净化 |

懂球帝增加 `ap.dongdianqiu.com/plat/v4` 的原生请求拦截及 `apimg.qunliao.info` 广告图片域名拦截，不增加 JS 或正文解析。

B 站开屏通过 1 条原生 jq 重写处理 `splash/list`、`splash/show` 和 `splash/event/list2`，不加载 B 站 JS。盒马是用户明确保留的应用内净化例外，不作为独立开屏去广告功能宣称。

微博信息流、评论区、搜索和个人主页净化，高德路线/首页推广处理，小红书去水印及信息流处理，虎扑与 12306 应用内脚本，以及闲鱼、知乎、滴滴等页面/正文净化已移除。12306 的原生广告列表处理仍保留。知乎保留 `commercial_api/launch_v2` 和 `commercial_api/real_time_launch_v2` 的原生开屏拦截及 `api.zhihu.com` 解密，不恢复信息流/回答页净化，也不添加 JS。

普通广告平台域名拦截继续保留，可能同时拦截开屏和应用内广告；不会为了保留应用内广告而放行共用广告平台。HTTP 处理保留经过挑选的开屏接口及 YouTube、天气功能，另按用户要求保留盒马净化。

Google 搜索与地图的中国域名跳转规则已恢复，沿用源插件的两条原生 307 跳转规则及 `www.google.cn` 解密项，不使用 JS。它们作为明确保留项参与每日构建。

YouTube 的可选字幕翻译设为 `off`，隐藏按钮选项保持关闭。复杂的 YouTube 去广告请求/响应逻辑沿用上游，未自行拆解二进制协议处理。

天气增强完整保留，沿用 ColorfulClouds 默认值，令牌为空。需要时在主文件的两条 WeatherKit 脚本参数中填写自己的令牌，或将 `Weather.Provider` 与 `NextHour.Provider` 都设为 `WeatherKit`。私有令牌只保留在本地。

## 内存调整

相较之前完整合并版，当前在开屏精简的基础上加入了 B 站和盒马：14 条 JS 触发规则、2 条原生正文重写、40 项 MITM。

微博、高德、小红书的发布脚本只提取上游开屏处理分支，不再包含信息流、评论、导航净化和去水印逻辑。小红书整体配置只删除开屏相关字段，保留主题和商城字段。淘宝原脚本已是开屏处理，因此保留。

需要正文的脚本上限为 256 KiB，超过上限跳过脚本，执行超时上限 10 秒。上限不是进程总内存限制，也不作用于原生正文重写。较大的 YouTube 或天气响应也可能跳过处理；这些功能仍有运行开销。尚未在手机上验证新版实际内存及全部应用效果。

脚本通过本仓库 `runtime/` 的远程地址加载。旧哈希脚本保留以兼容未更新客户端，但新版主文件只引用当前 8 份脚本，不会加载未引用的旧文件。

请停用旧主覆写、独立增强和诊断覆写后替换。仓库中的临时诊断文件已删除，不再生成。HTTPS 重写需要启用 MITM 并信任自己的 Stash 证书，原生正文重写需要 Stash 2.8+。

## 更新与筛选

每日工作流 `.github/workflows/update-stash-plugins.yml` 在北京时间 08:23 运行，也支持手动运行。使用 Loon UA 下载源插件，继续排除 fmz200 综合插件的全量内容。`extra-plugins.json` 明确列出 B 站开屏、盒马和懂球帝三项例外；每日只从合集提取指定条目，保存为三份小型源快照，仅下载盒马所需的 JS，不导入其他 fmz200 规则或依赖。

`focus-policy.json` 保存经过审核的开屏、YouTube 和天气 HTTP 接口清单（含 B 站开屏、盒马与懂球帝例外）。每日构建更新这些接口的上游处理内容，新出现的其他应用内优化不会自动加入。接口或脚本结构发生不兼容变化时，构建失败并保留上次成功版本，等待调整清单或提取器。

`focus.py` 负责接口筛选和开屏 JS 分支提取。未发布的完整源数据仅用于转换校验，仍保存在 `sources/`、`scripts/`；`validation-input.json` 被 Git 忽略，不是导入文件。`report.json` 的 `source_counts` 是全部源数据数量，`counts` 才是实际主文件数量。

构建会检查筛选范围、引用、去重、QUIC、MITM 排除项、脚本大小限制与天气保留，并执行微博 SDK 的特殊 OK 尾缀、微博预加载/缓存、高德、小红书和淘宝开屏处理样例，以及 B 站开屏 jq、盒马页面处理和选定条目下载样例。

将主覆写、构建代码、接口清单、额外来源清单及新增运行脚本一并推送 GitHub 后，远程订阅才会更新。工作流使用 `contents: write` 提交有变化的产物，失败不提交。

主覆写地址：

```text
https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.stoverride
```

## 在 Sub-Store 中合并

项目根目录的 `stash_plugins.js` 可用于 Sub-Store 的文件处理，直接把广告净化合并进生成的 Stash 配置。

这里使用的是文件脚本读写 `$content` 的能力：JS 将 `.stoverride` 作为 YAML 数据解析，再合并 `rules`、`http` 和 `script-providers` 等字段，输出完整配置。不要将 `.stoverride` 地址直接填入节点订阅或 JS 脚本地址；Sub-Store 不负责执行其中的 Stash 重写规则。

1. 在生成 Stash 配置的文件中添加一个脚本操作，放在现有 `stash_override.js` 之后。
2. 粘贴 `stash_plugins.js` 的内容，或在推送到 GitHub 后使用下面的远程脚本地址。
3. 重新生成文件，在 Stash 中更新该配置，并停用重复的广告净化覆写。这个脚本应在配置已经转换为 Stash 格式后运行。

```text
https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.js
```

脚本每次执行都会通过 Sub-Store 的下载接口读取本仓库已发布的 `stash_plugins.stoverride`，因此去广告内容随每日工作流更新，无需把全部规则复制进 JS。下载缓存的刷新遵循 Sub-Store 设置；尚未推送的本地改动不会出现在远程结果中。

合并会保留原配置的节点、策略组、DNS 和证书，把广告分流规则放在原规则前面，对相同条目去重，并将两边的 MITM 排除项提前。导入的脚本名称统一加上 `ssrules-` 前缀，避免与原有同名脚本冲突。请以原始基础配置作为流水线输入；不要把之前生成的最终配置反复作为基础，否则已经移除的旧规则仍会保留。

这里的 JS 只在 Sub-Store 生成文件时运行；去广告所需的 HTTP 重写和运行脚本仍由 Stash 执行，合并方式本身不会消除这些内存开销。下载失败或格式不符合预期时会报错，不会输出缺少广告规则的半成品。每日构建也会验证合并、去重、脚本引用和失败处理。

## 本地构建

需要 Python 3.11+ 与 Node.js 22：

```powershell
python -m pip install -r stash-plugins/requirements.txt
python -m unittest discover -s stash-plugins -p 'test_*.py'
python stash-plugins/fetch_dependencies.py --refresh
python stash-plugins/build.py
python stash-plugins/validate.py
```

参考：[Stash HTTP 重写](https://stash.wiki/http-engine/rewrite)、[MITM](https://stash.wiki/http-engine/mitm)、[脚本正文限制](https://stash.wiki/script/rewrite-requests)。
