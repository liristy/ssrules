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

// The published 12306 handler must answer only the splash placement and fail open.
const railSplash = Object.values(providers).find(x => x.payload.includes('Original source: https://raw.githubusercontent.com/kokoryh/Script/master/js/12306.js'));
assert.ok(railSplash);
for (const body of ['{"placementNo":"0007"}', '{"placementNo":"G0054"}', '{"placementNo":"unknown"}', '{}', 'null', 'not-json', undefined]) {
  let calls = 0, output;
  await vm.runInNewContext(railSplash.payload, {
    $request: {url: 'https://ad.12306.cn/ad/ser/getAdList?version=1', body},
    $done: value => {calls++; output = value;}, console,
  }, {timeout: 1000});
  assert.equal(calls, 1);
  if (body === '{"placementNo":"0007"}') {
    assert.equal(output.response.status, 200);
    assert.equal(output.response.headers['Content-Type'], 'application/json');
    const result = JSON.parse(output.response.body);
    assert.equal(result.advertParam.skipTime, 1);
    assert.deepEqual(result.materialsList, [{billMaterialsId: '255', filePath: 'h', creativeType: 1}]);
  } else {
    assert.equal(JSON.stringify(output), '{}', 'non-splash or malformed requests must pass through');
  }
}
console.log('12306 splash response and non-splash/malformed request passthrough OK.');

// Exercise the actual reduced upstream splash handlers, including Weibo's
// non-JSON "OK" trailer and RedPaper's unrelated theme/store fields.
async function splash(app, url, input, trailer = '') {
  const payload = Object.values(providers).find(provider => provider.payload.split('\n', 1)[0].endsWith(app === 'Hema' ? '/freshippo.js' : `/${app}_remove_ads.js`))?.payload;
  assert.ok(payload, app);
  let calls = 0, output;
  await vm.runInNewContext(payload, {
    $request: {url}, $response: {body: JSON.stringify(input) + trailer},
    $done: value => { calls++; output = value; }, console,
  }, {timeout: 1000});
  assert.equal(calls, 1, app);
  assert.equal(typeof output?.body, 'string', app);
  if (trailer) assert.ok(output.body.endsWith(trailer));
  return JSON.parse(trailer ? output.body.slice(0, -trailer.length) : output.body);
}
let result = await splash('Weibo', 'https://sdkapp.uve.weibo.com/interface/sdk/sdkad.php',
  {show_push_splash_ad: true, ads: [{displaytime: 5}], keep: 'unchanged'}, 'OK');
assert.equal(result.show_push_splash_ad, false);
assert.equal(result.ads[0].displaytime, 0);
assert.equal(result.keep, 'unchanged');
result = await splash('Weibo', 'https://bootpreload.uve.weibo.com/v2/ad/preload', {ads: [{display_duration: 5}]});
assert.equal(result.ads[0].display_duration, 0);
result = await splash('Weibo', 'https://wbapp.uve.weibo.com/preload/get_ad', {cached_ad: {ads: [{duration: 5}]}});
assert.equal(result.cached_ad.ads[0].duration, 0);
result = await splash('Amap', 'https://m5.amap.com/ws/valueadded/alimama/splash_screen',
  {data: {ad: [{set: {setting: {display_time: 5}}, creative: [{}]}]}, keep: true});
assert.equal(result.data.ad[0].set.setting.display_time, 0);
assert.equal(result.keep, true);
result = await splash('RedPaper', 'https://edith.xiaohongshu.com/api/sns/v1/system_service/config',
  {data: {app_theme: 'keep', store: 'keep', splash: {}, loading_img: 'ad'}});
assert.deepEqual(result, {data: {app_theme: 'keep', store: 'keep'}});
result = await splash('RedPaper', 'https://edith.xiaohongshu.com/api/sns/v2/system_service/splash_config',
  {data: {ads_groups: [{ads: [{}]}]}});
assert.equal(result.data.ads_groups[0].start_time, 3818332800);
assert.equal(result.data.ads_groups[0].ads[0].start_time, 3818332800);
result = await splash('Taobao', 'https://guide-acs.m.taobao.com/gw/mtop.taobao.cloudvideo.video.query',
  {data: {duration: '5', resources: ['ad'], caches: ['ad']}});
assert.equal(result.data.duration, '0');
assert.deepEqual(result.data.resources, []);
console.log('Reduced splash JS fixtures OK: Weibo SDK/preload/cache, Amap, RedPaper config/splash, Taobao.');
result = await splash('Hema', 'https://acs-m.freshippo.com/gw/mtop.wdk.render.queryindexpage',
  {data: {scenes: [{sceneTemplateId: '509'}, {sceneTemplateId: 'unknown'}], secondFloor: {ad: 1}}, keep: true});
assert.deepEqual(result.data.scenes, [{sceneTemplateId: '509'}]);
assert.deepEqual(result.data.secondFloor, {});
assert.equal(result.keep, true);
result = await splash('Hema', 'https://acs-m.freshippo.com/gw/mtop.wdk.render.querymypage',
  {data: {scenes: [{sceneTemplateId: '906'}, {sceneTemplateId: 'unknown'}]}});
assert.deepEqual(result.data.scenes, [{sceneTemplateId: '906'}]);
result = await splash('Hema', 'https://acs.m.taobao.com/gw/mtop.wdk.render.querytabfeedstream',
  {data: {scenes: [{sceneType: '100004'}, {sceneType: 'keep'}]}});
assert.deepEqual(result.data.scenes, [{sceneType: 'keep'}]);
console.log('Hema homepage, account page and recommendation fixtures OK.');
