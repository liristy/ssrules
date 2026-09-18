// Sub-Store interface simulation using the actual generated override as input.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const patch = JSON.parse(fs.readFileSync(0, 'utf8'));
const code = fs.readFileSync(new URL('../stash_plugins.js', import.meta.url), 'utf8');
let downloaded = JSON.stringify(patch), failDownload = false;
const context = vm.createContext({ProxyUtils: {
  yaml: {safeLoad: JSON.parse, safeDump: JSON.stringify},
  download: async url => {
    assert.equal(url, 'https://raw.githubusercontent.com/liristy/ssrules/main/stash_plugins.stoverride');
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
vm.runInContext(fs.readFileSync(new URL('../stash_override.js', import.meta.url), 'utf8'), overrideContext);
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
