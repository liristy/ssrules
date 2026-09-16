import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import zlib from 'node:zlib';

const config = JSON.parse(fs.readFileSync(new URL('validation-input.json', import.meta.url), 'utf8'));
const providers = config['script-providers'];
for (const [name, provider] of Object.entries(providers)) {
  new vm.Script(provider.payload, { filename: name });
}
for (const script of config.http.script) {
  assert.ok(providers[script.name], `Missing provider ${script.name}`);
  // URL matching uses Stash's native regex engine, not JavaScript RegExp;
  // native atomic groups (?>...) are checked by validate.py instead.
  if (script['binary-mode']) assert.equal(script['require-body'], true);
}

// Exercise the actual adapted gzip prelude with compressed binary data.
let gzipAdapters = 0;
for (const [name, provider] of Object.entries(providers)) {
  if (!provider.payload.includes('var $utils = { ungzip:')) continue;
  const end = provider.payload.indexOf('\n', provider.payload.indexOf('var $utils = { ungzip:'));
  const context = vm.createContext({});
  vm.runInContext(provider.payload.slice(0, end), context);
  context.input = [...zlib.gzipSync('Stash gzip compatibility 测试')];
  const result = vm.runInContext('$utils.ungzip(input)', context);
  assert.equal(Buffer.from(result).toString(), 'Stash gzip compatibility 测试', name);
  gzipAdapters++;
}

// Execute the real 12306 request script against blocked and allowed operations.
const provider = Object.values(providers).find(x => x.payload.includes('Original source: https://kelee.one/Resource/JavaScript/12306/'));
assert.ok(provider);
for (const [operation, blocked] of [['com.cars.otsmobile.newHomePage.initData', true], ['com.cars.otsmobile.checkLoginStatus', false]]) {
  let called = false;
  let result;
  vm.runInNewContext(provider.payload, {
    $request: { url: 'https://mobile.12306.cn/otsmobile/app/mgs/mgw.htm', headers: {'operation-type': operation} },
    $done: value => { called = true; result = value; }, console,
  }, { timeout: 1000 });
  assert.ok(called);
  assert.equal(result === undefined, blocked);
}
console.log(`JavaScript syntax OK: ${Object.keys(providers).length} providers; ${config.http.script.length} script bindings; gzip adapters tested: ${gzipAdapters}; 12306 behavior OK.`);
