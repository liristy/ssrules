// Original source: https://kelee.one/Resource/JavaScript/Amap/Amap_remove_ads.js
(async function () {
const obj = JSON.parse($response.body);

  // 开屏广告
  if (obj?.data?.ad?.length > 0) {
    for (let item of obj.data.ad) {
      item.set.setting.display_time = 0;
      item.creative[0].start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
      item.creative[0].end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
    }
  }
$done({body: JSON.stringify(obj)});
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
