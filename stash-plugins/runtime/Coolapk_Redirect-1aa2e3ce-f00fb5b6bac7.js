// Original source: https://raw.githubusercontent.com/VenenoSix24/Ivy-Script/refs/heads/main/Loon/script/Coolapk_Redirect.js
(async function () {
let url = $request.url;

if (url.indexOf("coolapk.com/link") !== -1) {
  let match = url.match(/url=([^&]+)/);
  if (match) {
    let realUrl = decodeURIComponent(match[1]);

    $done({
      response: {
        status: 302,
        headers: {
          "Location": realUrl,
          "Cache-Control": "no-cache"
        }
      }
    });
    return;
  }
}

$done({});
}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });
