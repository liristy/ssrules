// Sub-Store 文件处理脚本：放在 stash_override.js 之后。
// 生成订阅时读取最新去广告配置；Stash 中不要再叠加同一份广告覆写。
const STASH_ADS_URL = 'https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.stoverride';
const STASH_ADS_HTTP_FIELDS = ['mitm', 'url-rewrite', 'header-rewrite', 'body-rewrite', 'mock', 'script'];

function stashAdsObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function stashAdsScriptName(name) {
  // 兼容远程缓存中的旧版名称，改名与脚本下载地址无关。
  if (!/^(?:ssrules-|loon-)/.test(name)) return name;
  const stem = name.replace(/^(?:(?:ssrules|loon)-)+/, '').replace(/-[a-f0-9]{8,64}$/i, '');
  const labels = {
    'response.bundle': 'Apple天气增强',
    YouTube_remove_ads_response: 'YouTube去广告',
    YouTube_remove_ads_request: 'YouTube请求处理',
    Amap_remove_ads: '高德地图开屏广告',
    Taobao_remove_ads: '淘宝开屏广告',
    Weibo_remove_ads: '微博开屏广告',
    RedPaper_remove_ads: '小红书开屏广告',
    freshippo: '盒马净化',
  };
  return Object.prototype.hasOwnProperty.call(labels, stem) ? labels[stem] : (stem || '广告净化脚本');
}

function stashAdsKey(value) {
  if (Array.isArray(value)) return '[' + value.map(stashAdsKey).join(',') + ']';
  if (stashAdsObject(value)) {
    return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + stashAdsKey(value[key])).join(',') + '}';
  }
  return JSON.stringify(typeof value === 'string' ? value.trim() : value);
}

function stashAdsMergeRows(first = [], second = [], key = stashAdsKey) {
  if (!Array.isArray(first) || !Array.isArray(second)) throw new Error('去广告合并失败：规则字段必须是数组。');
  const seen = new Set();
  return [...first, ...second].filter(row => {
    const id = key(row);
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

async function main(config) {
  if (!stashAdsObject(config) || !Array.isArray(config.rules) || !Array.isArray(config['proxy-groups'])) {
    throw new Error('请先生成完整的 Stash 配置，再执行去广告文件脚本。');
  }
  if (config.http !== undefined && !stashAdsObject(config.http)) throw new Error('原配置的 http 字段格式不正确。');
  if (config['script-providers'] !== undefined && !stashAdsObject(config['script-providers'])) {
    throw new Error('原配置的 script-providers 字段格式不正确。');
  }

  let patch;
  try {
    patch = ProxyUtils.yaml.safeLoad(await ProxyUtils.download(STASH_ADS_URL));
  } catch (error) {
    throw new Error('无法读取去广告覆写，请确认仓库文件已发布且 Sub-Store 可以访问 GitHub。');
  }
  if (!stashAdsObject(patch) || !Array.isArray(patch.rules) || patch.rules.length === 0 || !stashAdsObject(patch.http)) {
    throw new Error('下载内容不是有效的去广告覆写，已停止生成。');
  }
  for (const [field, rows] of Object.entries(patch.http)) {
    if (!STASH_ADS_HTTP_FIELDS.includes(field) || !Array.isArray(rows)) {
      throw new Error('去广告覆写包含不支持的 HTTP 字段：' + field);
    }
    const objectRows = field === 'script' || field === 'mock';
    if (rows.some(row => objectRows ? !stashAdsObject(row) : typeof row !== 'string')) {
      throw new Error('去广告覆写的 HTTP 规则格式不正确：' + field);
    }
  }
  if (patch.rules.some(rule => typeof rule !== 'string' || /^(MATCH|FINAL)\s*,/.test(rule.trim()))) {
    throw new Error('去广告覆写包含无效分流规则或兜底规则，已停止生成。');
  }
  if (patch['script-providers'] !== undefined && !stashAdsObject(patch['script-providers'])) {
    throw new Error('去广告覆写的脚本提供者格式不正确。');
  }

  // 在合并端转换旧名称；仅在同名冲突时添加后缀，保护用户原有脚本。
  const existingProviders = config['script-providers'] || {};
  const incomingProviders = Object.create(null);
  const providerNames = new Map();
  const reservedNames = new Set(Object.keys(patch['script-providers'] || {}).map(stashAdsScriptName));
  for (const [name, provider] of Object.entries(patch['script-providers'] || {})) {
    if (!stashAdsObject(provider) || typeof provider.url !== 'string' || !provider.url.startsWith('https://')) {
      throw new Error('去广告脚本缺少有效的远程地址：' + name);
    }
    const label = stashAdsScriptName(name);
    let resolved = label, suffix = 1;
    while ((Object.hasOwn(existingProviders, resolved) && stashAdsKey(existingProviders[resolved]) !== stashAdsKey(provider))
      || Object.hasOwn(incomingProviders, resolved) || (resolved !== label && reservedNames.has(resolved))) {
      resolved = label + (suffix === 1 ? '（广告净化）' : '（广告净化 ' + suffix + '）');
      suffix++;
    }
    incomingProviders[resolved] = provider;
    providerNames.set(name, resolved);
  }
  const incomingScripts = (patch.http.script || []).map(entry => {
    if (typeof entry.name !== 'string' || typeof entry.match !== 'string' || !['request', 'response'].includes(entry.type)) {
      throw new Error('去广告脚本触发规则格式不正确。');
    }
    const name = providerNames.get(entry.name);
    if (!name) throw new Error('去广告脚本引用缺失：' + entry.name);
    return {...entry, name};
  });

  // 与 Stash 覆写一致：广告规则优先，原配置的规则和兜底规则排在后面。
  const result = {...config, rules: stashAdsMergeRows(patch.rules, config.rules)};
  const http = {...(config.http || {})};
  for (const field of STASH_ADS_HTTP_FIELDS) {
    if (patch.http[field] === undefined) continue;
    const incoming = field === 'script' ? incomingScripts : patch.http[field];
    const identity = field === 'script'
      ? row => stashAdsKey([row.name, row.type, row.match])
      : stashAdsKey;
    http[field] = stashAdsMergeRows(incoming, http[field] || [], identity);
    if (field === 'mitm') {
      if (http.mitm.some(host => typeof host !== 'string')) throw new Error('MITM 主机名必须是字符串。');
      // 两边的排除项都必须排在正向解密主机之前。
      http.mitm = [...http.mitm.filter(host => host.startsWith('-')), ...http.mitm.filter(host => !host.startsWith('-'))];
    }
  }
  result.http = http;
  result['script-providers'] = {...(config['script-providers'] || {}), ...incomingProviders};
  // name、desc、date 等覆写元数据不写入主配置；证书和其他设置沿用原配置。
  return result;
}

async function operator(input) {
  if (!input || typeof input.$content !== 'string') {
    throw new Error('请在 Sub-Store 的文件处理中使用本脚本，不要放到订阅的节点操作中。');
  }
  const config = await main(ProxyUtils.yaml.safeLoad(input.$content));
  input.$content = ProxyUtils.yaml.safeDump(config);
  return input;
}
