// Original source: https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/xiaotucc.js
(async function () {
if (-1 != $request.url.indexOf("main_page/index/getActivity")) {
  let obj = JSON.parse($response.body);
  delete obj.data.p3;
  $done({body: JSON.stringify(obj)});
} else if (-1 != $request.url.indexOf("mall/main")) {
  let obj = JSON.parse($response.body);
  delete obj.data;
  $done({body: JSON.stringify(obj)});
} else $done($response);
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
