// Original source: https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/soda.js
(async function () {
let obj = JSON.parse($response.body);
obj.data.objects.forEach(item => {
  item.imageUrl = "https://raw.githubusercontent.com/fmz200/wool_scripts/main/pic/rewrite/warm_water.png";
});
$done({body: JSON.stringify(obj)});
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
