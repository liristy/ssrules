# 仓库维护约定

本文件适用于整个仓库，记录用户确认的偏好和维护方式。开始修改前阅读本文件及 [README.md](README.md)；广告相关工作再阅读 [stash-plugins/README.md](stash-plugins/README.md)。用户后续明确指示优先于这里的既有约定。

## 去广告资源：固定从这两个地方查找

以后用户说“给某个应用去广告”“加入某应用开屏去广告”或要求修复广告规则时，主动查找以下两个来源，不要反复询问来源：

1. **可莉插件中心**：<https://hub.kelee.one/>。按应用名称查找对应插件，核对插件实际下载地址、作者、更新说明及引用的脚本。仓库已有插件通常使用 `https://kelee.one/Tool/Loon/Lpx/` 下的地址；不要凭文件命名习惯猜测一个未核实的地址。
2. **fmz200（奶思）的广告拦截与净化合集**：
   - 浏览：<https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/blockAds.plugin>
   - 原始文件：<https://raw.githubusercontent.com/fmz200/wool_scripts/main/Loon/plugin/blockAds.plugin>

查找并比较两个来源中的相关条目，追溯引用脚本的实际作者和源文件。本地快照用于定位，上游最新内容需另行核实；来源无法访问时如实说明。

只选择当前请求涉及的应用、接口和依赖，不直接导入整个 fmz200 合集，也不默认把两份相同功能叠加。优先使用兼容 Stash 的原生规则或重写；需要 JS 时才引入对应脚本。用户要求开屏去广告时，只处理开屏，不顺带启用信息流、评论、去水印、导航或购物推荐净化。用户只说应用去广告时，先沿用本仓库的开屏优先范围，再依据具体请求扩展。

## 文件职责

| 内容 | 修改入口 |
| --- | --- |
| Mihomo 基础配置、策略组和基础分流 | `mihomo_config.yaml` |
| Loon 配置、插件启用列表 | `loon_config.conf` |
| Stash 的主配置兼容转换、DNS、策略名称和 QUIC 顺序 | **`stash_override.js`** |
| 把广告资源合并进完整 Stash 配置 | `stash_plugins.js` |
| Stash 广告覆写产物 | `stash_plugins.stoverride`，由构建生成 |
| 去广告范围与额外合集条目 | `stash-plugins/focus-policy.json`、`stash-plugins/extra-plugins.json` |
| 下载、转换、裁剪和生成逻辑 | `stash-plugins/fetch_dependencies.py`、`build.py`、`focus.py` |
| 本仓库分流修正规则 | `Rule/list/` 与 `Rule/yaml/` |

`stash_override.js` 先执行，`stash_plugins.js` 后执行。它们是 Sub-Store **文件处理脚本**，处理 `$content`，不是节点操作脚本。

Mihomo 分流优先使用上游提供的 `behavior: domain` 规则集，减少 `classical` 规模；需要补充关键词、IP、进程等规则时，使用上游配套的补充集合，避免再叠加包含同一批域名的完整 `classical` 集合。先核实实际文件与覆盖范围；上游没有 domain 版本时保留必要的 classical 规则，不直接修改 behavior 导致格式不兼容或遗漏规则。

QUIC / UDP 443 由 **`stash_override.js`** 管理，位置是现有业务分流、国内直连之后，首条 `MATCH` / `FINAL` 之前。不要在广告覆写里重新前置全局 QUIC 拦截。当前这两条规则只处理兜底前尚未匹配的流量；不能描述为“所有代理连接都会屏蔽 QUIC”。用户已实测全局前置拦截会造成小红书打开和刷新缓慢。

## 广告维护流程

1. 检查当前产物是否已经包含目标功能，避免重复添加。
2. 按上述两个来源查找条目，核对实际请求路径、返回处理、MITM 域名、依赖脚本和作者声明；保留溯源信息。
3. 修改实际构建入口：已启用插件的 HTTP 功能由 `focus-policy.json` 筛选；从 fmz200 合集新增条目时，同时维护 `extra-plugins.json` 及适用的筛选项。必要时更新下载、转换或裁剪代码。
4. 重新生成 `stash_plugins.stoverride` 和关联产物。不要只手改生成文件，否则每日构建会覆盖。不要为了一条规则刷新或扩展无关功能。
5. 运行与改动相关的校验；广告构建变更执行 `python stash-plugins/build.py`、`python stash-plugins/validate.py`，涉及维护逻辑时再运行现有 `unittest`。验证 Sub-Store 合并后的顺序，而非只看单个文件。
6. 同步功能说明及原作者致谢。区分静态检查、样例测试与手机实测；没有手机验证就不能声称应用效果已实测。
7. 说明本地修改、提交、推送和客户端更新各自是否完成。仅修改本地文件不会更新 GitHub 远程订阅。

## 来源、声明和保留事项

README 面向首次阅读仓库的人，介绍用途、结构、来源、使用方法和声明；AGENTS.md 记录稳定的维护规则。两者均不记录口误纠正、对话原话或沟通过程。

仓库总览保持简洁，具体接口、MITM 和脚本实现放在对应模块文档。

仓库声明为“仅供个人使用，不用于商业用途”。后续维护文档时保持这一用途说明，不将其表述为面向公众提供的商业服务，也不将个人使用声明视为第三方资源的授权。

保留上游作者、来源 URL、许可证及必要的版权声明，不把汇总、转换或裁剪说成原始规则创作。不统一替第三方资源授予许可证，致谢和免责声明不能代替授权；尤其注意可莉站点关于抓取、二次修改及公开分发的声明，具体使用方式以对应上游的有效许可或授权为准。

不要在说明、日志或示例里复制真实证书私钥、口令、控制器密钥或订阅凭据。不要覆盖用户的其他未提交修改。当前功能细节以构建代码、清单和实际产物为准，发生变化时同步更新文档。
