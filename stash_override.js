const STASH_QUIC_RULES = [
  'PROTOCOL,QUIC,REJECT,no-track',
  'AND,((NETWORK,UDP),(DST-PORT,443)),REJECT,no-track',
];
const STASH_PREVIOUS_QUIC_RULES = [
  ...STASH_QUIC_RULES,
  'AND,((PROTOCOL,QUIC),(NOT,((GEOIP,CN)))),REJECT,no-track',
  'AND,((NETWORK,UDP),(DST-PORT,443),(NOT,((GEOIP,CN)))),REJECT,no-track',
];

async function main(config) {
  if (!config || !Array.isArray(config.rules) || !Array.isArray(config['proxy-groups'])) {
    throw new Error('请先合并 mihomo_config.yaml，再执行 Stash 覆写。');
  }

  // 1. Stash 保留 GLOBAL；只修改策略名称和引用，不改域名、URL 或规则集名称。
  const groups = config['proxy-groups'];
  if (groups.some(g => g.name === 'GLOBAL') && groups.some(g => g.name === 'Global')) {
    throw new Error('GLOBAL 与 Global 策略组同时存在，请先解决重名。');
  }
  const rename = value => value === 'GLOBAL' ? 'Global' : value;
  for (const group of groups) {
    group.name = rename(group.name);
    if (Array.isArray(group.proxies)) group.proxies = group.proxies.map(rename);
    if (group['ssid-policy']) {
      for (const key of Object.keys(group['ssid-policy'])) {
        group['ssid-policy'][key] = rename(group['ssid-policy'][key]);
      }
    }
  }
  const renameRule = rule => {
    const parts = rule.split(',');
    let index = parts.length - 1;
    while (index > 0 && ['no-resolve', 'no-track'].includes(parts[index].trim())) index--;
    if (index > 0 && parts[index].trim() === 'GLOBAL') parts[index] = 'Global';
    return parts.join(',');
  };

  // 2. 沿用手机已验证的 DNS：国内 DoH 直连，继承普通 Fake-IP 排除项。
  const dns = config.dns || {};
  config.dns = {
    ipv6: dns.ipv6 ?? false,
    'follow-rule': false,
    'fake-ip-filter': (dns['fake-ip-filter'] || []).filter(
      entry => !/^(rule-set|geosite):/.test(String(entry))
    ),
    'default-nameserver': ['223.5.5.5', '119.29.29.29'],
    nameserver: ['https://dns.alidns.com/dns-query', 'https://doh.pub/dns-query'],
  };

  const providers = config['rule-providers'] || {};
  // 3. iOS 不使用这组 Windows 进程规则。
  delete providers.Application_CN;

  // 4. 仅在原配置仍使用已知源时拆分 Privacy，保留源更新间隔和其他参数。
  const privacy = providers.Privacy;
  const splitPrivacy = /\/Privacy_Classical\.yaml(?:[?#]|$)/.test(privacy?.url || '');
  if (splitPrivacy) {
    if (providers.Privacy_Domain) {
      throw new Error('Privacy_Domain 已存在，无法安全添加兼容域名集合。');
    }
    providers.Privacy_Domain = {
      ...privacy,
      behavior: 'domain',
      url: privacy.url.replace('Privacy_Classical.yaml', 'Privacy_Domain.yaml'),
      path: './ruleset/stash/Privacy_Domain.yaml',
    };
    privacy.url = privacy.url.replace('Privacy_Classical.yaml', 'Privacy.yaml');
    privacy.path = './ruleset/stash/Privacy_Other.yaml';
  }

  // 5. 已知 ChinaMax_IP 源混入 ASN；采用与手机验证版相同的替代源。
  const china = providers.ChinaIP;
  const replaceChina = /\/ChinaMax\/ChinaMax_IP\.yaml(?:[?#]|$)/.test(china?.url || '');
  if (replaceChina) {
    china.url = china.url.replace('/ChinaMax/ChinaMax_IP.yaml', '/ChinaIPs/ChinaIPs_IP.yaml');
    china.path = './ruleset/stash/ChinaIPs.yaml';
  }

  // 6. 从当前源读取 Hijacking_DNS，动态展开；不在脚本内复制网段列表。
  const hijacking = providers.Hijacking_DNS;
  const hasHijackingRule = config.rules.some(rule =>
    /^RULE-SET\s*,\s*Hijacking_DNS\s*,/.test(rule.trim())
  );
  let cidrRules = [];
  if (hijacking && hasHijackingRule) {
    let payload = hijacking.payload;
    if (!Array.isArray(payload)) {
      if (!hijacking.url) throw new Error('Hijacking_DNS 缺少可读取的 URL 或 payload。');
      const raw = await ProxyUtils.download(hijacking.url);
      payload = hijacking.format === 'text'
        ? raw.split(/\r?\n/).map(s => s.trim()).filter(s => s && !s.startsWith('#'))
        : ProxyUtils.yaml.safeLoad(raw)?.payload;
    }
    if (!Array.isArray(payload) || payload.length === 0) {
      throw new Error('Hijacking_DNS 未返回有效规则；停止生成，避免丢失规则。');
    }
    cidrRules = payload.map(entry => {
      const cidr = String(entry).trim().replace(/^IP-CIDR6?\s*,\s*/, '');
      const match = /^([0-9a-f:.]+)\/(\d+)$/i.exec(cidr);
      const v6 = cidr.includes(':');
      if (!match || Number(match[2]) > (v6 ? 128 : 32)) {
        throw new Error('Hijacking_DNS 存在非 CIDR 条目：' + entry);
      }
      return (v6 ? 'IP-CIDR6,' : 'IP-CIDR,') + cidr;
    });
  }
  if (hasHijackingRule && !hijacking) throw new Error('缺少 Hijacking_DNS 规则源。');
  delete providers.Hijacking_DNS;

  // 原地替换对应规则，继承其目标策略及 no-resolve 等参数，其他规则保持原顺序。
  config.rules = config.rules.flatMap(rule => {
    const renamed = renameRule(rule);
    const parts = renamed.split(',').map(s => s.trim());
    if (parts[0] !== 'RULE-SET') return [renamed];
    const tail = parts.slice(2).join(',');
    if (parts[1] === 'Application_CN') return [];
    if (parts[1] === 'Hijacking_DNS') return cidrRules.map(cidr => `${cidr},${tail}`);
    if (parts[1] === 'Privacy' && splitPrivacy) {
      return [`RULE-SET,Privacy_Domain,${tail}`, renamed];
    }
    if (parts[1] === 'ChinaIP' && replaceChina) {
      return [renamed, `IP-ASN,132203,${tail}`];
    }
    return [renamed];
  });
  // 7. QUIC 由主配置统一管理：现有分流优先，最后在兜底前拦截。
  // 清除本项目旧版前置/带 CN 条件的规则，避免重复或抢先拦截国内直连。
  const quicKey = rule => rule.replace(/\s+/g, '').replace(/,no-track$/, '');
  const previousQuic = new Set(STASH_PREVIOUS_QUIC_RULES.map(quicKey));
  config.rules = config.rules.filter(rule => !previousQuic.has(quicKey(rule)));
  const fallback = config.rules.findIndex(rule => /^(MATCH|FINAL)\s*,/.test(rule.trim()));
  config.rules.splice(fallback < 0 ? config.rules.length : fallback, 0, ...STASH_QUIC_RULES);
  return config;
}

// Sub-Store 标准文件脚本入口；兼容普通文件和 mihomo 配置文件的脚本操作。
async function operator(input) {
  if (!input || typeof input.$content !== 'string') {
    throw new Error('请在 Sub-Store 的文件处理中使用本脚本，不要放到订阅的节点操作中。');
  }
  const config = await main(ProxyUtils.yaml.safeLoad(input.$content));
  input.$content = ProxyUtils.yaml.safeDump(config);
  return input;
}
