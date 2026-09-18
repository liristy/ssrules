# ssrules

> 本仓库仅供个人使用，不用于商业用途。第三方资源的版权及许可归各自原作者所有。

个人维护的 Loon、Mihomo 和 Stash 网络配置、分流修正规则与广告净化适配仓库。主要工作是整理上游资源、筛选所需功能、适配客户端语法和维护生成流程；第三方规则、脚本、图标和数据的原始成果归各自作者所有。

包含客户端配置、分流规则、应用去广告和天气增强功能。

## 仓库结构

| 文件或目录 | 用途 |
| --- | --- |
| [loon_config.conf](loon_config.conf) | Loon 主配置：DNS、策略组、远程分流与插件引用；也是广告构建读取的插件启用入口 |
| [mihomo_config.yaml](mihomo_config.yaml) | Mihomo 基础配置：DNS、TUN、策略组及规则集合 |
| [stash_override.js](stash_override.js) | Sub-Store 文件脚本：将基础配置转换为 Stash 配置 |
| [stash_plugins.js](stash_plugins.js) | Sub-Store 文件脚本：将广告净化配置合并到主配置 |
| [stash_plugins.stoverride](stash_plugins.stoverride) | 自动生成的 Stash 广告覆写；可以直接导入 Stash，也可作为上述合并脚本的数据源 |
| [Rule/list/](Rule/list/) | Loon 使用的列表规则，包括直连、代理、拦截修正及其他分类 |
| [Rule/yaml/](Rule/yaml/) | YAML 规则集合，供基础配置引用；与 `.list` 有对应分类，也有客户端专用分类 |
| [stash-plugins/](stash-plugins/) | 广告来源快照、依赖、功能筛选、转换构建、运行脚本和校验工具 |
| [.github/workflows/update-stash-plugins.yml](.github/workflows/update-stash-plugins.yml) | 定时刷新上游、构建、校验和提交生成产物 |
| [AGENTS.md](AGENTS.md) | 自动化维护规范：资源来源、文件职责和修改流程 |

`DirectRevise`、`ProxyRevise`、`BlockRevise` 分别用于直连、代理和拦截修正；`Emby`、`OpenAI` 等服务分类交给对应策略处理。`Hijacking_DNS` 是基础分流中的特定地址集合，与广告插件中的 HTTPDNS 拦截不是同一个概念。

## 使用方式

### Loon 与 Mihomo

按所用客户端选择对应主配置，并补齐自己的节点或订阅。策略组中的节点名称、筛选条件及网络参数是个人配置，使用前需按自己的环境调整。Loon 插件不等同于 Stash 广告产物：后者会经过功能筛选和语法转换。

Mihomo 的 Google、TikTok 分流使用 blackmatrix7 规则集，均可独立选择策略，默认使用 AUTO；策略组与匹配规则中，Google 位于 Apple 前，TikTok 位于 Emby 前。

### Stash 与 Sub-Store

完整配置的处理顺序是：

```text
节点或订阅 + mihomo_config.yaml
                ↓
        stash_override.js
                ↓
    stash_plugins.js（需要合并广告净化时）
                ↓
       生成完整配置并由 Stash 更新
```

两个 JS 都放在 Sub-Store 的**文件处理**中，不要放进节点操作。`stash_override.js` 处理 Stash 的主配置兼容、DNS、策略名及相关规则转换；`stash_plugins.js` 只负责广告资源的合并。

也可以使用转换后的主配置，在 Stash 中单独导入 [广告覆写](https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.stoverride)。广告已通过 `stash_plugins.js` 合入主配置时，不再重复叠加同一覆写。HTTPS 重写需要在设备上配置并信任自己的 MITM 证书；不要使用仓库或他人提供的证书私钥和口令。

更新脚本或构建文件后，需要重新生成配置并在客户端更新。未推送的本地改动不会出现在远程订阅中；Sub-Store 下载缓存也可能影响更新时间。

## 去广告资源

提供应用开屏去广告、YouTube 去广告、通用广告拦截和苹果天气增强等功能。详细配置见 [广告净化说明](stash-plugins/README.md)。

去广告规则主要来自以下两个来源，具体脚本的作者与依赖以源文件署名为准：

| 来源 | 查找入口 |
| --- | --- |
| 可莉插件中心 | [hub.kelee.one](https://hub.kelee.one/)；具体插件的实际下载地址以其页面为准 |
| fmz200 / 奶思 | [广告拦截与净化合集 blockAds.plugin](https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/blockAds.plugin) · [原始文件](https://raw.githubusercontent.com/fmz200/wool_scripts/main/Loon/plugin/blockAds.plugin) |

## 生成与维护

| 构建文件 | 职责 |
| --- | --- |
| [focus-policy.json](stash-plugins/focus-policy.json) | 允许进入发布产物的 HTTP 接口清单 |
| [extra-plugins.json](stash-plugins/extra-plugins.json) | 从 fmz200 合集中选择的额外条目及其 MITM、参数 |
| [fetch_dependencies.py](stash-plugins/fetch_dependencies.py) | 下载插件、依赖脚本及选定合集片段，保存来源信息 |
| [focus.py](stash-plugins/focus.py) | 功能筛选和指定脚本的开屏处理分支提取 |
| [build.py](stash-plugins/build.py) | 语法转换、去重、MITM 范围收敛及产物生成 |
| [validate.py](stash-plugins/validate.py)、[validate.mjs](stash-plugins/validate.mjs) | 配置、引用、表达式和脚本样例校验 |
| `sources/`、`scripts/` | 上游插件与依赖快照，用于构建和溯源，不代表其中所有功能都会启用 |
| `runtime/` | 发布产物实际引用的脚本；保留部分旧哈希文件用于兼容旧客户端 |
| `dependencies.json`、`refresh.json`、`locations.json`、`report.json` | 记录依赖、刷新信息、条目位置和构建统计 |

不要只手动修改 `stash_plugins.stoverride`，应修改筛选清单或生成逻辑后重新构建，否则下次更新会覆盖。基础分流变更需要检查相关客户端的规则表示；专属规则无需机械地复制到所有格式。

本地构建依赖 Python 3.11+、Node.js 22 及 Python 依赖：

```powershell
python -m pip install -r stash-plugins/requirements.txt
python -m unittest discover -s stash-plugins -p 'test_*.py'
python stash-plugins/build.py
python stash-plugins/validate.py
```

需要刷新上游快照时，在构建前执行 `python stash-plugins/fetch_dependencies.py --refresh`。使用和分发前应核对相应上游的许可及限制。

当前 GitHub Actions 设置为北京时间每天 08:23 触发，也支持手动运行；实际开始时间可能受平台调度影响。工作流校验成功后才提交变化的生成产物。静态校验与样例测试不等同于手机上所有应用均验证通过，实际效果还取决于应用版本、网络及客户端设置。

## 感谢原作者与贡献者

感谢所有提供规则、脚本、数据、图标、客户端和工具的原作者，以及持续整理、反馈和维护这些资源的社区成员。本仓库的整理与适配建立在这些工作之上，不应被误认为原始资源的独立创作。

以下根据当前配置引用、上游插件署名和脚本来源整理，排名不分先后，也不是完整作者名单：

- **资源整理与合集**：[可莉 / iKelee / luestr](https://github.com/luestr/ProxyResource)、[fmz200 / 奶思](https://github.com/fmz200/wool_scripts)。
- **插件和脚本作者**：[RuCu6](https://github.com/RuCu6)、[zirawell](https://github.com/zirawell/R-Store)、[Maasea](https://github.com/Maasea)、[VirgilClyne](https://github.com/VirgilClyne)、[WordlessEcho](https://github.com/WordlessEcho)、[001ProMax](https://github.com/001ProMax)、[Choler](https://github.com/Choler)、[DivineEngine](https://github.com/DivineEngine)、[app2smile](https://github.com/app2smile)、[kelv1n1n](https://github.com/kelv1n1n)、[zmqcherish](https://github.com/zmqcherish)、[ZenmoFeiShi](https://github.com/ZenmoFeiShi)，以及上游署名的 **wish、小白脸** 等作者。
- **天气增强项目**：[NSRingo / WeatherKit](https://github.com/NSRingo/WeatherKit) 及其作者、贡献者和依赖项目。
- **分流、广告规则与数据**：[blackmatrix7 / ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)、[Cats-Team / AdRules](https://github.com/Cats-Team/AdRules)、[Loyalsoldier / geoip](https://github.com/Loyalsoldier/geoip)、[MetaCubeX / meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) 及其引用的数据提供者。
- **工具与图标**：[Sub-Store](https://github.com/sub-store-org/Sub-Store)、[Orz-3 / mini](https://github.com/Orz-3/mini)、[luestr / IconResource](https://github.com/luestr/IconResource)、[101arrowz / fflate](https://github.com/101arrowz/fflate)，以及 Loon、Stash、Mihomo、Python、Node.js、PyYAML、jq 等项目的维护者。

更细的作者和依赖信息请沿 `sources/` 中的 `#!author`、原始脚本注释、`dependencies.json` 和上游仓库继续追溯。若有遗漏或错误，可通过 [本仓库 Issues](https://github.com/liristy/ssrules/issues) 提供原始出处以便补正。

## 使用与来源声明

本仓库仅供个人使用，用于个人配置整理、网络行为研究和客户端兼容适配，不用于商业用途，与所涉及应用、服务及其运营方没有隶属或背书关系。使用者应理解规则的作用，在自己的设备和有权管理的网络中使用，并遵守适用规则及服务约定。

第三方资源的版权、署名及许可归相应权利人；本仓库的致谢、引用或技术转换不意味着已获得额外授权，也不改变原有许可。转用代码时应保留相应版权和许可文本；没有明确许可的资源，不应仅因公开可访问就视为允许任意再分发。

截至本次文档核对，[可莉插件中心](https://hub.kelee.one/) 展示了禁止抓取站点内容、二次修改及公开分发的声明。仓库中已有的下载或转换能力不构成该站点的授权；相关资源的后续处理与公开分发应以权利人的有效许可或明确授权为准。其他来源及合集所引用脚本也应分别核对其声明。

规则可能因应用更新而失效，也可能影响连接速度、页面内容或功能。仓库不承诺永久有效、零误拦截或适配所有环境；修改前保留可恢复的配置，出现异常时可停用对应规则定位原因。请勿将真实订阅凭据、令牌、控制器密钥、证书私钥或密码用于公开分享。

这些说明用于明确用途、来源和边界，不是免责保证，也不能替代应承担的责任。若权利人对相关内容的引用、署名或分发有异议，请通过仓库 Issues 指明条目和依据，维护者将核实并更正或移除。
