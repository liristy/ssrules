"""Reviewed HTTP allowlist and extraction of upstream splash-only JS branches."""
import json
from pathlib import Path

POLICY = json.loads(Path(__file__).with_name('focus-policy.json').read_text(encoding='utf-8'))['plugins']


def keep_entry(section, entry, source):
    if section == 'rules':
        # Keep ordinary network blocking, including QUIC. HTTP matching and
        # explicit shopping-page blocks are outside the focused feature set.
        return not any(token in entry for token in ('URL-REGEX,', 'USER-AGENT,', 'mallapi2.qinlinkeji.com', 'mall-dsp2.qinlinkeji.com'))
    kind = 'script' if section == 'script' else 'rewrite'
    pattern = entry['match'] if isinstance(entry, dict) else entry.split()[0]
    return pattern in POLICY.get(source, {}).get(kind, [])


def between(text, start, end):
    if text.count(start) != 1:
        raise ValueError('Upstream splash branch changed; review required: ' + start)
    offset = text.index(start) + len(start)
    if end not in text[offset:]:
        raise ValueError('Upstream splash branch end changed; review required: ' + end)
    return text[offset:text.index(end, offset)]


def trim_script(url, script):
    """Extract fresh upstream branches each build; fail on structural changes."""
    if url.endswith('/Amap_remove_ads.js'):
        body = between(script, '} else if (url.includes("/valueadded/alimama/splash_screen")) {', '\n}\n\n$done')
        return 'const obj = JSON.parse($response.body);\n' + body + '\n$done({body: JSON.stringify(obj)});\n'
    if url.endswith('/RedPaper_remove_ads.js'):
        config = between(script, '} else if (url.includes("/v1/system_service/config")) {', '} else if (url.includes("/v2/note/widgets")) {')
        old = '["app_theme", "loading_img", "splash", "store"]'
        if old not in config:
            raise ValueError('RedPaper splash fields changed; review required')
        config = config.replace(old, '["loading_img", "splash"]')
        splash = between(script, '} else if (url.includes("/v2/system_service/splash_config")) {', '} else if (url.includes("/v2/user/followings/followfeed")) {')
        return ('const url = $request.url; const obj = JSON.parse($response.body);\n'
                'if (url.includes("/v1/system_service/config")) {' + config + '\n}'
                ' else if (url.includes("/v2/system_service/splash_config")) {' + splash + '\n}\n'
                '$done({body: JSON.stringify(obj)});\n')
    if url.endswith('/Weibo_remove_ads.js'):
        sdk = between(script, 'if (url.includes("/interface/sdk/sdkad.php")) {', '} else {\n  let obj = JSON.parse(body);')
        splash = between(script, '} else if (url.includes("/v1/ad/preload") || url.includes("/v2/ad/preload")) {', '\n  $done({ body: JSON.stringify(obj) });')
        return ('const url = $request.url; const body = $response.body;\n'
                'if (url.includes("/interface/sdk/sdkad.php")) {' + sdk + '\n} else {\n'
                'let obj = JSON.parse(body);\n'
                'if (url.includes("/v1/ad/preload") || url.includes("/v2/ad/preload")) {' + splash + '\n'
                '$done({body: JSON.stringify(obj)});\n}\n')
    return script
