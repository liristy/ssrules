// Original source: https://raw.githubusercontent.com/fmz200/wool_scripts/main/Scripts/template/req_replace_body.js
(async function () {
/**
 * author:fmz200
 * date:2023-10-09 22:55:00
 * function:部分APP收集用户信息，将上传的内容换成无效内容
 */
// oops, nothing here and fuck you.
// 4cb5ca2f450cad350d0a03fbc9231e6f
let body = {content: "oops, nothing here and fuck you. Collecting user privacy is suspected of being illegal."};
$done({body:JSON.stringify(body)});
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
