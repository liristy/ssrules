# 仓库维护约定

本文件适用于整个仓库，记录用户确认的偏好和维护方式。开始修改前阅读本文件及 [README.md](README.md)；广告相关工作再阅读 [stash-plugins/README.md](stash-plugins/README.md)。用户后续明确指示优先于这里的既有约定。

## 去广告资源：固定从这两个地方查找

以后用户说“给某个应用去广告”“加入某应用开屏去广告”或要求修复广告规则时，主动查找以下两个来源，不要反复询问来源：

1. **可莉插件中心**：<https://hub.kelee.one/>。按应用名称查找对应插件，核对插件实际下载地址、作者、更新说明及引用的脚本。仓库已有插件通常使用 `https://kelee.one/Tool/Loon/Lpx/` 下的地址；不要凭文件命名习惯猜测一个未核实的地址。
2. **fmz200（奶思）的广告拦截与净化合集**：
   - 浏览：<https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/blockAds.plugin>
   - 原始文件：<https://raw.githubusercontent.com/fmz200/wool_scripts/main/Loon/plugin/blockAds.plugin>

查找并比较两个来源中的相关条目，追溯引用脚本的实际作者和源文件。本地快照用于定位，上游最新内容需另行核实；来源无法访问时如实说明。

**dev 分支当前约定：只完整导入已选择的独立插件，不扩展 App 范围。** Loon `[Plugin]` 中的完整 fmz200/blockAds.plugin **必须排除**；只保留原来单独启用的应用插件、Bilibili 的完整插件，以及原有 `extra-plugins.json` 明确选取的少量 fmz200 应用片段。独立插件不再裁剪脚本分支或开屏/信息流等功能。这里的“插件全量”绝不表示启用 fmz200 中约 730 款 App。去重需保证首条匹配行为不变，无法转换时构建失败并保留上次发布文件。`main` 继续保持原样。

## 文件职责

| 内容 | 修改入口 |
| --- | --- |
| Mihomo 基础配置、策略组和基础分流 | `mihomo_config.yaml` |
| Loon 配置、插件启用列表 | `loon_config.conf` |
| Stash 的主配置转换、DNS、策略与 QUIC 顺序，以及 dev 全量插件自动合并 | **`stash_override.js`** |
| 独立广告合并兼容入口（dev 不必重复执行） | `stash_plugins.js` |
| Stash 广告覆写产物 | `stash_plugins.stoverride`，由构建生成 |
| 额外完整插件、限定来源片段与历史精简清单 | `stash-plugins/extra-plugins.json`、`stash-plugins/focus-policy.json`（dev 不用于过滤独立插件） |
| 全量下载、Stash 格式转换与生成逻辑 | `stash-plugins/fetch_dependencies.py`、`build.py`、`focus.py` |
| 本仓库分流修正规则 | `Rule/list/` 与 `Rule/yaml/` |

`dev` 只需执行 `stash_override.js` 一个 Sub-Store **文件处理脚本**：先转换 Mihomo 主配置，再下载 dev 全量 `stash_plugins.stoverride`，合并全部分流、MITM、重写、脚本和 provider，最后写回 `$content`。不能放到节点操作。原 `stash_plugins.js` 仍可用于旧两阶段流程，但不应默认叠加，避免重复下载。

Mihomo 分流优先使用上游提供的 `behavior: domain` 规则集，减少 `classical` 规模；需要补充关键词、IP、进程等规则时，使用上游配套的补充集合，避免再叠加包含同一批域名的完整 `classical` 集合。先核实实际文件与覆盖范围；上游没有 domain 版本时保留必要的 classical 规则，不直接修改 behavior 导致格式不兼容或遗漏规则。

QUIC / UDP 443 由 **`stash_override.js`** 管理，位置是现有业务分流、国内直连之后，首条 `MATCH` / `FINAL` 之前。不要在广告覆写里重新前置全局 QUIC 拦截。当前这两条规则只处理兜底前尚未匹配的流量；不能描述为“所有代理连接都会屏蔽 QUIC”。用户已实测全局前置拦截会造成小红书打开和刷新缓慢。

`dev` 的 `extra-plugins.json` 只允许原有指定应用：可为完整独立插件（如 Bilibili），也可为 fmz200 综合插件中曾明确选择的具体应用功能片段。不能把这些片段扩展为整个 fmz200 合集，也不能未经用户要求扩大 App 范围。`stash_override.js` 内嵌的全量插件合并逻辑必须与 `stash_plugins.js` 一致，任何一方改动都应同步更新，并由 `stash-plugins/test_substore.mjs` 的源代码一致性、单/双流程等价性和幂等校验把关。`focus-policy.json` 为历史清单，在 `dev` 不参与构建。旧全局 QUIC 拦截仍由主配置处理，插件自带的定向 QUIC 规则保留。下载、语法校验及 Sub-Store 合并必须覆盖整个实际发布内容；构建验证不等于设备真机验证。

## 广告维护流程

1. 检查当前产物是否已经包含目标功能，避免重复添加。
2. 按上述两个来源查找条目，核对实际请求路径、返回处理、MITM 域名、依赖脚本和作者声明；保留溯源信息。
3. 修改实际构建入口：`dev` 完整纳入已选的独立插件内容，`focus-policy.json` 不得过滤这些插件内部功能；同时必须排除 fmz200 整份综合插件，只允许事先指定的应用片段。更新上游源文件不得导致意外扩大 App 范围。
4. 重新生成 `stash_plugins.stoverride` 和关联产物。不要只手改生成文件，否则每日构建会覆盖。不要为了一条规则刷新或扩展无关功能。
5. 运行与改动相关的校验；广告构建变更执行 `python stash-plugins/build.py`、`python stash-plugins/validate.py`，涉及维护逻辑时再运行现有 `unittest`。验证 Sub-Store 合并后的顺序，而非只看单个文件。
6. 同步功能说明及原作者致谢。区分静态检查、样例测试与手机实测；没有手机验证就不能声称应用效果已实测。
7. 说明本地修改、提交、推送和客户端更新各自是否完成。仅修改本地文件不会更新 GitHub 远程订阅。

## 来源、声明和保留事项

README 面向首次阅读仓库的人，介绍用途、结构、来源、使用方法和声明；AGENTS.md 记录稳定的维护规则。两者均不记录口误纠正、对话原话或沟通过程。

仓库总览保持简洁，具体接口、MITM 和脚本实现放在对应模块文档。

仓库声明为“仅供个人使用，不用于商业用途”。后续维护文档时保持这一用途说明，不将其表述为面向公众提供的商业服务，也不将个人使用声明视为第三方资源的授权。

保留上游作者、来源 URL、许可证及必要的版权声明，不把汇总、转换或裁剪说成原始规则创作。不统一替第三方资源授予许可证，致谢和免责声明不能代替授权；尤其注意可莉站点关于抓取、二次修改及公开分发的声明，具体使用方式以对应上游的有效许可或授权为准。

不要在说明、日志或示例里复制真实证书私钥、口令、控制器密钥或订阅凭据。不要覆盖用户的其他未提交修改。`dev` 全量模式可能让客户端内存、MITM 和耗电负担显著增加；要在导入与客户端实测之间明确区分。当前功能细节以构建代码、清单和实际产物为准，发生变化时同步更新文档。
