# Stash 替代 LocalDevVPN 测试

本分支从 `dev` 的 `1aed594` 创建。目标是在同一条 Stash VPN 中同时保留原有代理分流，并为 SideStore 提供本机回环连接。当前完成配置和离线验证，**尚未在 iPhone 上验证安装、续签或后台稳定性**。

## 方案与适用范围

使用 SideStore 自带的 EMProxy WireGuard 服务：

`发往 10.7.0.1 的设备服务连接 → Stash 的 SideStore-Local 节点 → 本机 127.0.0.1:51820 的 EMProxy → 设备服务`

Stash 文档支持 `type: wireguard` 节点；SideStore 当前源码提供 EMProxy 开关、导出配置和本机 UDP 绑定参数。这里将它们组合成实验方案，不宣称 Stash 原生实现了 LocalDevVPN 的全部数据包反射能力。

这条规则只匹配 `10.7.0.1/32`，TCP 和 UDP 均交给同一个本机节点。普通分流继续处理下载、Apple 登录、GitHub 等网络请求。仅把此地址设为 `DIRECT` 不能创建回环功能；也没有添加未经 Stash 文档确认的 Mihomo `loopback-address` 字段。

**前提：所用 SideStore 版本必须能够启用 EMProxy。** 这不是适用于所有依赖 LocalDevVPN 的 App 的通用替代；尤其不能据此保证 StikDebug、StikJIT 或其他开发者服务可用。若当前安装版本没有此开关，先停止本方案，保留原有可用连接方式。

## 使用方法

先记录当前可用的 LocalDevVPN 和 SideStore 设置，测试时保持 Wi-Fi 连接并授予 SideStore 本地网络权限。

1. SideStore → Settings → User Customizations：开启 **EMProxy (WireGuard) Server**，按提示重启 SideStore。
2. SideStore → Connection Config：打开 **Use Local VPN**；User Configuration 中 **Device IP = `10.7.0.1`**；WireGuard Server Parameters 中 **Bind Host / IP = `127.0.0.1`**，**Bind Port = `51820`**；点 Confirm。不要把 `10.7.0.10` 填到 Device IP，它是节点内部的 WireGuard 客户端地址。RemotePair Port 保留原来的自动发现，只有明确发现端口不符时才按实际广播调整。
3. 下面两种导入方法选一种。
4. 关闭 LocalDevVPN，仅启动 Stash，保持**规则模式**。重新打开 SideStore 查看用户指定 Device IP 的 Active 是否为 Yes，然后尝试刷新一个 App。

### 方法一：使用本分支一体化脚本

Sub-Store 文件处理中，将原来的 `dev/stash_override.js` 换成：

```text
https://raw.githubusercontent.com/liristy/ssrules/localdevvpn_test/stash_override.js
```

重新生成完整配置，在 Stash 更新并重连。脚本会在现有主配置转换与插件合并完成后加入本机节点，将精确设备规则置顶；保留所有其他节点，不把本机节点加入机场策略组。有同名且参数不同的节点时停止生成，不覆盖现有配置。

广告覆写数据源**有意继续使用现有 `dev/stash_plugins.stoverride`**，其他规则源沿用输入配置。这让测试只引入本机连接变化，不重新刷新广告资源。本分支不自动刷新上游广告；CI 仅运行离线检查。因此本分支脚本并不表示所有依赖均固定在本分支，`dev` 后续更新广告仍会反映到重新生成的配置中。

### 方法二：直接导入独立覆写

保留原来的主配置，在 Stash 覆写中导入并启用：

```text
https://raw.githubusercontent.com/liristy/ssrules/localdevvpn_test/stash_localdevvpn.stoverride
```

重连后核对最终配置，确认设备规则在广告、Lan、IP 分流和 MATCH 之前。覆写含一个名为 `SideStore-Local` 的节点和一条规则，不含 DNS、MITM 或策略组设置。导入前避免已有同名节点。**不要同时使用方法一和方法二。**

仓库现有 `PROXY` / `AUTO` 的节点筛选不会匹配 `SideStore-Local`，离线检查对此有验证。如使用其他主配置，需检查 `include-all: true` 的组是否没有筛选条件；本机节点不能被当作普通上网出口选中。

## 参数依据

| WireGuard 原始字段 | Stash 字段 | 本次值 |
| --- | --- | --- |
| Interface.Address | 节点 `ip`，去掉 CIDR | `10.7.0.10` |
| Interface.PrivateKey | `private-key` | 上游随应用公开分发的固定 EMProxy 测试参数 |
| Peer.PublicKey | `public-key` | 上游随应用公开分发的固定 EMProxy 测试参数 |
| Peer.Endpoint | `server` + `port` | `127.0.0.1` + `51820` |
| Peer.AllowedIPs | Stash 精确分流规则 | `10.7.0.1/32` |
| PersistentKeepalive | `keepalive` | `25` |

节点参数逐项取自 SideStore 的公开 `SideStore.conf`，不含用户的个人节点凭据；没有照搬普通 WireGuard 示例中随意的地址和密钥。如你安装的版本导出的配置与此不同，应在本地按导出内容调整对应字段，不能只改 Device IP。不要把个人导出配置或个人密钥提交到公开仓库。

## 验证与排查

| 检查 | 通过条件 | 当前状态 |
| --- | --- | --- |
| 脚本语法与完整配置转换 | 原节点、策略、全部插件脚本保留，规则置顶 | 已离线验证 |
| 重复处理与重名保护 | 不重复加入规则或节点；冲突时原输出不被替换 | 已离线验证 |
| 独立覆写与脚本一致 | 两者节点参数及规则一致 | 已离线验证 |
| 本机设备连接 | 仅 Stash 开启，SideStore Device IP Active 为 Yes | 待真机验证 |
| 刷新与安装 | 刷新一个 App 成功，再验证一个 IPA 安装 | 待真机验证 |
| 网络并存与后台 | 原有代理访问正常；切后台、锁屏后重复刷新 | 待真机验证 |

在 Stash 连接记录中搜索 `10.7.0.1`，目标应匹配 `SideStore-Local`，不能走 Lan DIRECT、机场节点或 REJECT。节点已禁用公网测速，它是本机服务入口，不能用常规测速超时判断其不可用。

- 看不到目标连接：先确认 SideStore 已手动指定 Device IP，Stash 已更新配置且处于规则模式；同时检查 Stash 的路由排除设置是否让 `10.7.0.1` 绕过隧道。普通 YAML 规则不能强行修正应用级路由排除。
- 连接命中节点仍超时：核对 EMProxy 开关、重启状态和绑定地址，先让 SideStore 保持前台；该版本可能无法通过此方式完成回环或设备服务握手。保留日志，不反复增加宽泛内网直连规则。
- Active 为 Yes 但安装失败：记录完整错误；这只证明端点检查通过，不代表配对、RemotePair 服务、签名会话、Anisette 或苹果服务全部正常。`Session Expired` 等错误不能仅凭表现归因于回环。
- 需要回退：方法一换回原 `dev/stash_override.js`，从原始主配置重新生成；方法二禁用此覆写；重新连接 LocalDevVPN。SideStore 的 Device IP 和 EMProxy 设置恢复到测试前记录。不要用已带测试节点的输出作为回退的输入。

离线检查：

```sh
node --check stash_override.js
node --check stash_plugins.js
python -c "import json,yaml; print(json.dumps(yaml.safe_load(open('stash_plugins.stoverride'))))" | node stash-plugins/test_substore.mjs
python -m unittest discover -s stash-plugins -p 'test_localdevvpn.py'
```

## 参考来源

- [Stash WireGuard 节点文档](https://stash.wiki/proxy-protocols/proxy-types#wireguard)
- [SideStore 官方旧版 WireGuard 说明及适用范围](https://docs.sidestore.io/docs/advanced/alternative#wireguard)
- [SideStore 随应用分发的公开配置，固定到核对的源码版本](https://github.com/SideStore/SideStore/blob/d97ec133719d79916675bdaf722b82a8d091d545/SideStore.conf)
- [SideStore EMProxy 本机绑定实现](https://github.com/SideStore/SideStore/blob/d97ec133719d79916675bdaf722b82a8d091d545/SideStore/Core/DeviceApi/EMProxyWrapper.swift)
- [SideStore EMProxy 开关和配置导出实现](https://github.com/SideStore/SideStore/blob/d97ec133719d79916675bdaf722b82a8d091d545/SideStore/Views/Settings/Advanced/UserCustomizations/UserCustomizationsView.swift)

上述公开配置和源码归 SideStore 原作者所有；本仓库仅做配置映射与实验验证，保持仅供个人使用、不用于商业用途的声明。
