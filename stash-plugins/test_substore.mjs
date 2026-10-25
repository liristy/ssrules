// Sub-Store interface simulation using the actual generated override as input.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const patch = JSON.parse(fs.readFileSync(0, 'utf8'));
const code = fs.readFileSync(new URL('../stash_plugins.js', import.meta.url), 'utf8');
const unifiedCode = fs.readFileSync(new URL('../stash_override.js', import.meta.url), 'utf8');
const syncStart = '// BEGIN synced full-plugin merger (from stash_plugins.js)\n';
const syncEnd = '// END synced full-plugin merger\n';
const normalizeMerger = code.split('async function operator(input) {')[0]
  .replace(/^\/\/ Sub-Store 文件处理脚本：[^\n]*\n\/\/ 生成订阅时读取[^\n]*\n/, '')
  .trimEnd()
  .replace('async function main(config) {', 'async function stashMergeAllPlugins(config) {');
assert.ok(unifiedCode.includes(syncStart) && unifiedCode.includes(syncEnd), 'unified script merger markers missing');
assert.equal(unifiedCode.split(syncStart)[1].split(syncEnd)[0].trimEnd(), normalizeMerger,
  'stash_override.js inline merger must stay in sync with stash_plugins.js');
let downloaded = JSON.stringify(patch), failDownload = false;
const context = vm.createContext({ProxyUtils: {
  yaml: {safeLoad: JSON.parse, safeDump: JSON.stringify},
  download: async url => {
    assert.equal(url, 'https://raw.githubusercontent.com/liristy/ssrules/dev/stash_plugins.stoverride');
    if (failDownload) throw new Error('offline');
    return downloaded;
  },
}});
vm.runInContext(code, context);
const providerName = Object.keys(patch['script-providers'])[0];
const customProvider = {url: 'https://custom.example/script.js', interval: 600};
const customScript = {name: providerName, type: 'request', match: '^https://custom.example/'};
const base = {
  name: 'my-config', 'log-level': 'warning',
  proxies: [{name: 'node', type: 'ss', server: 'example.com', port: 443, cipher: 'aes-128-gcm', password: 'fixture'}],
  'proxy-groups': [{name: 'Proxy', type: 'select', proxies: ['node']}],
  'rule-providers': {custom: {type: 'http', behavior: 'domain', url: 'https://custom.example/rules'}},
  dns: {nameserver: ['223.5.5.5']},
  rules: [patch.rules[0], 'DOMAIN,private.example,DIRECT', 'MATCH,Proxy'],
  http: {ca: 'fixture-certificate', 'ca-passphrase': 'fixture-password',
    mitm: ['custom.example', '-private.example', patch.http.mitm[0]],
    'url-rewrite': [patch.http['url-rewrite'][0], '^https://custom.example/ad - reject'],
    script: [customScript]},
  'script-providers': {[providerName]: customProvider},
};
const input = {$content: JSON.stringify(base), $files: ['unchanged']};
const output = await context.operator(input);
assert.equal(output, input);
assert.deepEqual(output.$files, ['unchanged']);
const merged = JSON.parse(output.$content);
for (const field of ['name', 'log-level', 'proxies', 'proxy-groups', 'rule-providers', 'dns']) {
  assert.deepEqual(merged[field], base[field], field);
}
assert.equal(merged.http.ca, base.http.ca);
assert.equal(merged.http['ca-passphrase'], base.http['ca-passphrase']);
assert.deepEqual(merged.rules.slice(0, patch.rules.length), patch.rules);
assert.equal(merged.rules.at(-1), 'MATCH,Proxy');
assert.equal(merged.rules.length, patch.rules.length + 2);
assert.equal(merged.http['url-rewrite'].length, patch.http['url-rewrite'].length + 1);
assert.ok(merged.http.mitm.includes('-private.example'));
const firstPositive = merged.http.mitm.findIndex(host => !host.startsWith('-'));
assert.ok(merged.http.mitm.slice(firstPositive).every(host => !host.startsWith('-')));
assert.deepEqual(merged['script-providers'][providerName], customProvider);
assert.deepEqual(merged.http.script.at(-1), customScript);
for (const script of merged.http.script.slice(0, -1)) {
  const original = patch.http.script.find(row => row.type === script.type && row.match === script.match);
  assert.equal(script.name, original.name === providerName ? providerName + '（广告净化）' : original.name);
  assert.ok(merged['script-providers'][script.name]);
}
assert.equal(merged.desc, undefined);
assert.equal(merged.date, undefined);
const once = input.$content;
await context.operator(input);
assert.equal(input.$content, once, 'same override must not duplicate entries');
const clean = {...base, http: {}, 'script-providers': {}};
const cleanMerged = await context.main(clean);
assert.deepEqual(JSON.parse(JSON.stringify(cleanMerged.http.script)), patch.http.script, 'readable names must survive merging');
const sameProvider = {...clean, 'script-providers': patch['script-providers']};
const sameMerged = await context.main(sameProvider);
assert.deepEqual(JSON.parse(JSON.stringify(sameMerged['script-providers'])), patch['script-providers'], 'identical providers must reuse names');
const occupied = {...base, 'script-providers': {
  ...base['script-providers'], [providerName + '（广告净化）']: customProvider,
}};
const occupiedMerged = await context.main(occupied);
assert.ok(occupiedMerged.http.script.some(row => row.name === providerName + '（广告净化 2）'));
assert.deepEqual(JSON.parse(JSON.stringify(await context.main(occupiedMerged))), JSON.parse(JSON.stringify(occupiedMerged)), 'collision suffix must remain stable');
// A cached old override must get readable names just by updating stash_plugins.js.
for (const prefix of ['loon-', 'ssrules-loon-']) {
  const legacyName = prefix + 'Weibo_remove_ads-dc0eef05';
  const legacyProvider = {url: 'https://raw.githubusercontent.com/liristy/ssrules/main/stash-plugins/runtime/loon-Weibo_remove_ads-dc0eef05-4cda91c9eed0.js', interval: 86400};
  const legacyPatch = {
    rules: patch.rules,
    http: {script: [{name: legacyName, type: 'response', match: '^https://sdkapp.example/'}]},
    'script-providers': {[legacyName]: legacyProvider},
  };
  downloaded = JSON.stringify(legacyPatch);
  const legacyMerged = JSON.parse(JSON.stringify(await context.main(clean)));
  assert.equal(legacyMerged.http.script[0].name, '微博开屏广告');
  assert.deepEqual(legacyMerged['script-providers']['微博开屏广告'], legacyProvider, 'renaming must preserve the working URL');
  assert.deepEqual(JSON.parse(JSON.stringify(await context.main(legacyMerged))), legacyMerged);
  const collisionBase = {...clean, 'script-providers': {'微博开屏广告': customProvider}};
  const collisionMerged = await context.main(collisionBase);
  assert.equal(collisionMerged.http.script[0].name, '微博开屏广告（广告净化）');
  assert.deepEqual(JSON.parse(JSON.stringify(collisionMerged['script-providers']['微博开屏广告'])), customProvider);
}
assert.equal(context.stashAdsScriptName('loon-UnknownApp-1234abcd'), 'UnknownApp');
assert.equal(context.stashAdsScriptName('自定义脚本'), '自定义脚本');
// Exercise the actual two-script pipeline: main routing owns QUIC, and even a
// cached advertising override must not prepend its historical QUIC rules.
const legacyQuic = ['PROTOCOL,QUIC,REJECT,no-track', 'AND,((NETWORK,UDP),(DST-PORT,443)),REJECT,no-track'];
const previousScopedQuic = [
  'AND,((PROTOCOL,QUIC),(NOT,((GEOIP,CN)))),REJECT,no-track',
  'AND,((NETWORK,UDP),(DST-PORT,443),(NOT,((GEOIP,CN)))),REJECT,no-track',
];
const overrideContext = vm.createContext({ProxyUtils: context.ProxyUtils});
vm.runInContext(unifiedCode, overrideContext);
// Preserve the upstream GLOBAL group, nested references and rule targets without renaming them.
const originalGlobalGroups = [
  {name: 'GLOBAL', type: 'select', proxies: ['node']},
  {name: 'Custom', type: 'select', proxies: ['GLOBAL'], 'ssid-policy': {home: 'GLOBAL'}},
];
const originalGlobalRules = ['DOMAIN,global.example,GLOBAL', 'RULE-SET,custom,GLOBAL,no-resolve', 'MATCH,GLOBAL'];
const preservedGlobal = JSON.parse(JSON.stringify(await overrideContext.main(structuredClone({
  ...clean, 'proxy-groups': originalGlobalGroups, rules: originalGlobalRules,
}))));
assert.deepEqual(preservedGlobal['proxy-groups'], originalGlobalGroups, 'GLOBAL group and references must remain unchanged');
assert.deepEqual(preservedGlobal.rules, [
  ...originalGlobalRules.slice(0, -1), ...legacyQuic, originalGlobalRules.at(-1),
], 'GLOBAL policy targets must remain unchanged');
const routes = ['DOMAIN,private.example,DIRECT', 'DOMAIN,proxy.example,Proxy', 'GEOIP,CN,DIRECT', 'MATCH,Proxy'];
for (const previous of [[], legacyQuic, previousScopedQuic, legacyQuic.map(rule => rule.replace(',no-track', ''))]) {
  const source = {...clean, rules: [...previous, ...routes]};
  const transformed = JSON.parse(JSON.stringify(await overrideContext.main(structuredClone(source))));
  assert.deepEqual(transformed.rules, [...routes.slice(0, -1), ...legacyQuic, routes.at(-1)]);
  assert.deepEqual(JSON.parse(JSON.stringify(await overrideContext.main(structuredClone(transformed)))), transformed);
}
for (const fallback of ['FINAL,Proxy', null]) {
  const source = {...clean, rules: [...routes.slice(0, -1), ...(fallback ? [fallback] : [])]};
  const transformed = JSON.parse(JSON.stringify(await overrideContext.main(structuredClone(source))));
  assert.deepEqual(transformed.rules, [...routes.slice(0, -1), ...legacyQuic, ...(fallback ? [fallback] : [])]);
}
for (const cached of [patch, ...[legacyQuic, previousScopedQuic].map(rules => ({...patch, rules: [...rules, ...patch.rules]}))]) {
  downloaded = JSON.stringify(cached);
  const transformed = await overrideContext.main(structuredClone({...clean, rules: [...legacyQuic, ...routes]}));
  const migrated = JSON.parse(JSON.stringify(await context.main(transformed)));
  assert.deepEqual(migrated.rules.slice(0, patch.rules.length), patch.rules);
  assert.deepEqual(migrated.rules.slice(patch.rules.length), [...routes.slice(0, -1), ...legacyQuic, routes.at(-1)]);
  assert.ok(legacyQuic.every(rule => migrated.rules.filter(row => row === rule).length === 1));
  assert.ok(previousScopedQuic.every(rule => !migrated.rules.includes(rule)));
  assert.deepEqual(JSON.parse(JSON.stringify(await context.main(migrated))), migrated);
}

// The dev stash_override.js must be a complete ONE-SCRIPT pipeline. It
// converts the Mihomo base config, then imports the entire (unfiltered) patch.
downloaded = JSON.stringify(patch);
const unifiedBase = {...clean, rules: [...legacyQuic, ...routes]};
const unifiedInput = {$content: JSON.stringify(unifiedBase), $files: ['untouched']};
const unifiedOutput = await overrideContext.operator(unifiedInput);
assert.equal(unifiedOutput, unifiedInput);
assert.deepEqual(unifiedOutput.$files, ['untouched']);
const convertedBase = await overrideContext.main(structuredClone(unifiedBase));
const expectedFull = await context.main(convertedBase);
const unifiedFull = JSON.parse(unifiedOutput.$content);
assert.deepEqual(unifiedFull, JSON.parse(JSON.stringify(expectedFull)),
  'one-shot Stash conversion must match the original two-script pipeline');
assert.ok(unifiedFull.rules.length >= patch.rules.length, 'unified script lost full rule coverage');
assert.equal(unifiedFull.http.script.length, patch.http.script.length,
  'unified script must include every upstream script binding');
assert.ok(Object.keys(unifiedFull['script-providers']).length >= Object.keys(patch['script-providers']).length);
const singlePass = unifiedInput.$content;
await overrideContext.operator(unifiedInput);
assert.equal(unifiedInput.$content, singlePass, 'unified processing must be idempotent');
await context.operator(unifiedInput);
assert.equal(unifiedInput.$content, singlePass,
  'retained stash_plugins.js must not double-apply the full override');
downloaded = '<html>bad response</html>';
await assert.rejects(overrideContext.operator(unifiedInput));
assert.equal(unifiedInput.$content, singlePass, 'failed full import must leave input intact');

downloaded = JSON.stringify(patch);
for (const bad of ['<html>error</html>', '{}', JSON.stringify({...patch, rules: ['MATCH,DIRECT']})]) {
  downloaded = bad;
  await assert.rejects(context.operator(input));
  assert.equal(input.$content, once, 'failed import must leave input intact');
}
failDownload = true;
await assert.rejects(context.operator(input));
assert.equal(input.$content, once);
await assert.rejects(context.operator([]));
console.log('Sub-Store merge OK: readable names retained, collisions resolved, original settings/certificate preserved, rules ordered, duplicates removed, failed downloads leave input unchanged.');
console.log('Unified stash_override.js verified: full plugin import, one-script/two-script parity, idempotence, URL sync and fail-safe behavior.');
