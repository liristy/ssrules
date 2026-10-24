// Original source: https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/youdao/dict-youdao-ad.js
(async function () {
/*************************************

 项目名称：网易有道词典-首页净化，学习Tab界面净化，首页听读训练净化
 使用声明：⚠️仅供参考，🈲转载与售卖！

 **************************************

 [rewrite_local]
^https:\/\/dict\.youdao\.com\/(homepage\/promotion|course\/tab\/home|homepage\/tile) url script-response-body https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/youdao/dict-youdao-ad.js

 [mitm]
 hostname = dict.youdao.com
 ************************************/

let obj = JSON.parse($response.body);
const url = $request.url;

if (url.includes('/homepage/promotion')) {
  obj.data.dataList = obj.data.dataList.filter(i => i.type === 'WOW');
} else if (url.includes('/course/tab/home')) {
  obj.data.tab.tabList = obj.data.tab.tabList.filter(i => i.title === '学库' || i.title === '四六级');
  obj.data.icon.iconList = obj.data.icon.iconList.filter(i => i.title === '实用英语');
  obj.data.fragmentList = obj.data.fragmentList.filter(i => i.type === 'GREAT_COURSE');
} else if (url.includes('/homepage/tile')) {
  obj.data.children = obj.data.children.filter(i => i.type === '');
}

$done({body: JSON.stringify(obj)});
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
