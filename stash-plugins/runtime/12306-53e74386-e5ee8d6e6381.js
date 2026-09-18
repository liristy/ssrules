// Original source: https://raw.githubusercontent.com/kokoryh/Script/master/js/12306.js
(async function () {
// Splash response from kokoryh/Script, selected via fmz200/wool_scripts.
let request;
try { request = JSON.parse($request.body); } catch (_) { $done({}); return; }
if (request && request.placementNo === "0007") {
  $done({response: {status: 200, headers: {"Content-Type": "application/json"}, body: "{\"materialsList\":[{\"billMaterialsId\":\"255\",\"filePath\":\"h\",\"creativeType\":1}],\"advertParam\":{\"skipTime\":1}}"}});
} else { $done({}); }
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
