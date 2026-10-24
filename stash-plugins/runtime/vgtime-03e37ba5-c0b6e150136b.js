// Original source: https://raw.githubusercontent.com/app2smile/rules/master/js/vgtime.js
(async function () {
console.log('vgtime-开屏页');
let body = JSON.parse($response.body);
if (!body.data?.ad) {
    console.log('data/ad字段为空');
    console.log(`body:${$response.body}`);
} else {
    body.data.ad = null;
    console.log('成功');
}
body = JSON.stringify(body);

$done({
    body
});
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
