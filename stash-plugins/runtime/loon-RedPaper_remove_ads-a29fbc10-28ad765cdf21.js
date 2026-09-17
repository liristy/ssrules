// Original source: https://kelee.one/Resource/JavaScript/RedPaper/RedPaper_remove_ads.js
(async function () {
const url = $request.url; const obj = JSON.parse($response.body);
if (url.includes("/v1/system_service/config")) {
  // 整体配置
  const item = ["loading_img", "splash"];
  if (obj?.data) {
    for (let i of item) {
      delete obj.data[i];
    }
  }

} else if (url.includes("/v2/system_service/splash_config")) {
  // 开屏广告
  if (obj?.data?.ads_groups?.length > 0) {
    for (let i of obj.data.ads_groups) {
      i.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
      i.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
      if (i?.ads?.length > 0) {
        for (let ii of i.ads) {
          ii.start_time = 3818332800; // Unix 时间戳 2090-12-31 00:00:00
          ii.end_time = 3818419199; // Unix 时间戳 2090-12-31 23:59:59
        }
      }
    }
  }

}
$done({body: JSON.stringify(obj)});
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
