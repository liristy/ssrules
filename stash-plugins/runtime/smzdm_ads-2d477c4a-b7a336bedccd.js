// Original source: https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/smzdm/smzdm_ads.js
(async function () {
/**
 * @author fmz200
 * @function 什么值得买去广告
 * @date 2025-06-04 09:11:00
 */

let requestUrl = $request.url;
let responseBody = $response.body;

let obj = JSON.parse(responseBody);

if (requestUrl.includes("/vip/creator_user_center")) {
  obj.data = {};
  console.log('去除个人中心广告💕');
}

if (requestUrl.includes("/util/update")) {
  obj.data.operation_float = [];
  console.log('去除弹窗图片广告💕');
}

if (requestUrl.includes("/detail_modul/user_related_modul")) {
  delete obj.data.super_coupon;
  console.log('去除详情页广告💕');
}

if (requestUrl.includes("/ranking_list/articles?")) {
  obj.data.rows = obj.data.rows.filter(item => item.model_type !== "ads");
  console.log('去除排行榜广告💕');
}

if (requestUrl.includes("/sou/list_v10")) {
  obj.data.rows = obj.data.rows.filter(item => item.model_type !== "ads");
  console.log('去除搜索结果广告💕');
}

if (requestUrl.includes("/sou/filter/tags/hot_tags?")) {
  obj.data.search_hot.home = obj.data.search_hot.home.filter(item => item.pos);
  delete obj.data.tonglan;
  delete obj.data.hongbao;
  console.log('去除搜索热榜广告💕');
}

$done({body: JSON.stringify(obj)});
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
