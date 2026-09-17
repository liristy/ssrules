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
  assert.ok(script.name.startsWith('ssrules-'));
  assert.ok(merged['script-providers'][script.name]);
}
assert.equal(merged.desc, undefined);
assert.equal(merged.date, undefined);
const once = input.$content;
await context.operator(input);
assert.equal(input.$content, once, 'same override must not duplicate entries');
for (const bad of ['<html>error</html>', '{}', JSON.stringify({...patch, rules: ['MATCH,DIRECT']})]) {
  downloaded = bad;
  await assert.rejects(context.operator(input));
  assert.equal(input.$content, once, 'failed import must leave input intact');
}
failDownload = true;
await assert.rejects(context.operator(input));
assert.equal(input.$content, once);
await assert.rejects(context.operator([]));
console.log('Sub-Store merge OK: real override, original settings/certificate preserved, rules ordered, references namespaced, duplicates removed, failed downloads leave input unchanged.');
