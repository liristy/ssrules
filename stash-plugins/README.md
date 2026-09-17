# 广告净化

只需导入项目根目录的 `stash_plugins.stoverride`。主文件保留开屏去广告、YouTube 去广告、苹果天气增强，以及通用广告平台网络拦截和 QUIC 屏蔽。

## 当前范围

主文件约 27 KB，包含 456 条分流规则、22 条 URL 拦截、1 条原生正文重写、1 条静态响应，以及 7 份 JavaScript 的 13 条触发规则。MITM 共 35 项，原有 5 条排除项优先。

| 应用 | JS 触发规则 | 保留功能 |
|---|---:|---|
| 微博 | 3 | 开屏预加载、SDK 开屏、缓存开屏广告 |
| YouTube | 3 | 去广告及配套请求处理，使用两份脚本 |
| 苹果天气 | 2 | 天气可用性与天气数据增强 |
| 小红书 | 2 | 开屏配置及开屏广告 |
| 淘宝 | 2 | 开屏视频、图片及开屏活动 |
| 高德地图 | 1 | 开屏广告 |

微博信息流、评论区、搜索和个人主页净化，高德路线/首页推广处理，小红书去水印及信息流处理，虎扑与 12306 应用内脚本，以及闲鱼、知乎、滴滴等页面/正文净化已移除。12306 的原生广告列表处理仍保留。

普通广告平台域名拦截继续保留，可能同时拦截开屏和应用内广告；不会为了保留应用内广告而放行共用广告平台。HTTP 处理只保留经过挑选的开屏接口及 YouTube、天气功能。

YouTube 的可选字幕翻译设为 `off`，隐藏按钮选项保持关闭。复杂的 YouTube 去广告请求/响应逻辑沿用上游，未自行拆解二进制协议处理。

天气增强完整保留，沿用 ColorfulClouds 默认值，令牌为空。需要时在主文件的两条 WeatherKit 脚本参数中填写自己的令牌，或将 `Weather.Provider` 与 `NextHour.Provider` 都设为 `WeatherKit`。私有令牌只保留在本地。

## 内存调整

相较之前完整合并版，JS 触发规则从 58 条减少到 13 条，原生正文重写从 73 条减少到 1 条，MITM 从 132 项减少到 35 项。

微博、高德、小红书的发布脚本只提取上游开屏处理分支，不再包含信息流、评论、导航净化和去水印逻辑。小红书整体配置只删除开屏相关字段，保留主题和商城字段。淘宝原脚本已是开屏处理，因此保留。

需要正文的脚本上限为 256 KiB，超过上限跳过脚本，执行超时上限 10 秒。上限不是进程总内存限制，也不作用于原生正文重写。较大的 YouTube 或天气响应也可能跳过处理；这些功能仍有运行开销。尚未在手机上验证新版实际内存及全部应用效果。

脚本通过本仓库 `runtime/` 的远程地址加载。旧哈希脚本保留以兼容未更新客户端，但新版主文件只引用当前 7 份脚本，不会加载未引用的旧文件。

请停用旧主覆写、独立增强和诊断覆写后替换。仓库中的临时诊断文件已删除，不再生成。HTTPS 重写需要启用 MITM 并信任自己的 Stash 证书，原生正文重写需要 Stash 2.8+。

## 更新与筛选

每日工作流 `.github/workflows/update-stash-plugins.yml` 在北京时间 08:23 运行，也支持手动运行。使用 Loon UA 下载源插件，继续排除 fmz200 综合插件 `blockAds.plugin`。

`focus-policy.json` 保存经过审核的开屏、YouTube 和天气 HTTP 接口清单。每日构建更新这些接口的上游处理内容，新出现的其他应用内优化不会自动加入。接口或脚本结构发生不兼容变化时，构建失败并保留上次成功版本，等待调整清单或提取器。

`focus.py` 负责接口筛选和开屏 JS 分支提取。未发布的完整源数据仅用于转换校验，仍保存在 `sources/`、`scripts/`；`validation-input.json` 被 Git 忽略，不是导入文件。`report.json` 的 `source_counts` 是全部源数据数量，`counts` 才是实际主文件数量。

构建会检查筛选范围、引用、去重、QUIC、MITM 排除项、脚本大小限制与天气保留，并执行微博 SDK 的特殊 OK 尾缀、微博预加载/缓存、高德、小红书和淘宝开屏处理样例。

将主覆写、构建代码、接口清单及新增运行脚本一并推送 GitHub 后，远程订阅才会更新。工作流使用 `contents: write` 提交有变化的产物，失败不提交。

主覆写地址：

```text
https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.stoverride
```

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
