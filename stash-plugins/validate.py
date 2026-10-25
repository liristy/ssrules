"""Static checks and fixture tests; does not claim to run the Stash app."""
import base64
import json
from pathlib import Path
import re
import subprocess
import yaml
import jq
from build import (Builder, LEGACY_QUIC_RULES, requires_quic, sections, RUNTIME_URL,
                   MAX_BODY_BYTES, NATIVE_HTTP_SECTIONS, STASH_JSON_DEL_MAX_PATHS,
                   STASH_NATIVE_JSON_PATH)
from fetch_dependencies import selected_plugins, extra_plugins
from focus import keep_entry, ZHIHU_SPLASH

ROOT = Path(__file__).resolve().parent
core_path = ROOT.parent / 'stash_plugins.stoverride'
core = yaml.safe_load(core_path.read_text(encoding='utf-8'))
data = json.loads((ROOT / 'validation-input.json').read_text(encoding='utf-8'))
report = json.loads((ROOT / 'report.json').read_text(encoding='utf-8'))
locations = json.loads((ROOT / 'locations.json').read_text(encoding='utf-8'))
config_text = (ROOT.parent / 'loon_config.conf').read_text(encoding='utf-8-sig')
assert report['counts']['plugins'] == len(selected_plugins(config_text))
assert report['counts']['rules'] == len(core['rules'])
assert report['source_counts']['rules'] == len(data['rules'])
assert report['profile'] == 'all-enabled'
approved_excerpts = {entry['file'] for entry in extra_plugins()}
assert not any(item['file'] == 'blockAds.plugin' or ('/fmz200/' in item['url'] and item['file'] not in approved_excerpts) for item in report['sources'])
assert any(item['file'] == 'Bilibili_remove_ads.lpx' for item in report['sources'])
assert not any(item['file'] == 'Bilibili_splash.lpx' for item in report['sources'])
assert not any('/fmz200/' in url for url in json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8')))
assert set(core['http']) <= {'mitm', 'script', *NATIVE_HTTP_SECTIONS}
def selected(section):
    rows = data['rules'] if section == 'rules' else data['http'][section]
    return [row for row, loc in zip(rows, locations.get(section, []))
            if keep_entry(section, row, loc.rsplit(':', 1)[0])]

assert core['rules'] == selected('rules')
for key in NATIVE_HTTP_SECTIONS:
    assert core['http'].get(key, []) == selected(key), key
    assert report['counts'].get(key, 0) == len(core['http'].get(key, []))
# Full dev build must include every successfully converted rule and HTTP entry.
assert len(core['rules']) == report['source_counts']['rules']
assert len(core['http'].get('url-rewrite', [])) == report['source_counts']['url-rewrite']
assert len(core['http'].get('body-rewrite', [])) == report['source_counts']['body-rewrite']
assert len(core['http'].get('script', [])) == report['source_counts']['script']
assert len(core['http']['script']) > 30, 'Full script entries were accidentally filtered'
assert len(core['http']['url-rewrite']) > 100, 'Full URL rewrites were accidentally filtered'
assert len(core['http']['body-rewrite']) > 20, 'Full body rewrites were accidentally filtered'
assert 'weatherkit.apple.com' in core['http']['mitm']
assert 'DOMAIN-KEYWORD,apimg.qunliao.info,REJECT' in core['rules']
assert 'app.bilibili.com' in core['http']['mitm']
assert not set(LEGACY_QUIC_RULES) & set(core['rules'])
# Application-specific QUIC matching may exist; only the legacy unscoped QUIC rules are excluded.
assert not set(LEGACY_QUIC_RULES) & set(core['rules'])
assert core_path.stat().st_size < 3_000_000

exclusions = []
for _, line in sections(config_text).get('mitm', []):
    if line.lower().startswith('hostname'):
        exclusions.extend(x.strip() for x in line.split('=', 1)[1].split(',') if x.strip().startswith('-'))
exclusions = list(dict.fromkeys(exclusions))
assert data['http']['mitm'][:len(exclusions)] == exclusions
assert core['http']['mitm'][:len(exclusions)] == exclusions
assert 'ca' not in data['http'] and 'ca-passphrase' not in data['http']
assert 'proxy-groups' not in data and 'dns' not in data
assert not any(rule.startswith(('MATCH,', 'FINAL,')) for rule in data['rules'])
assert not set(LEGACY_QUIC_RULES) & set(data['rules'])
assert not set(LEGACY_QUIC_RULES) & set(data['rules'])
# A DIRECT exception must survive before a broader blocking rule. Conversely,
# a later exception already hidden by that blocking rule must not change routing.
fixture = [
    'DOMAIN,keep.example.com,DIRECT',
    'DOMAIN-SUFFIX,example.com,REJECT',
    'DOMAIN,late.example.com,DIRECT',
    'DOMAIN-SUFFIX,ads.example.com,REJECT',
    'DOMAIN-SUFFIX,otherexample.com,DIRECT',
    'DOMAIN-KEYWORD,tracker,REJECT',
    'DOMAIN-SUFFIX,tracker.test,DIRECT',
    'DOMAIN,independent.test,DIRECT',
]
builder = Builder()
builder.data['rules'] = fixture[:]
builder.locations['rules'] = [f'fixture:{i}' for i in range(len(fixture))]
builder.deduplicate_rules()

def route(rules, domain):
    for rule in rules:
        kind, value, policy = rule.split(',')
        if ((kind == 'DOMAIN' and domain == value)
                or (kind == 'DOMAIN-SUFFIX' and (domain == value or domain.endswith('.' + value)))
                or (kind == 'DOMAIN-KEYWORD' and value in domain)):
            return policy
    return None

for domain in ['keep.example.com', 'late.example.com', 'example.com', 'a.ads.example.com',
               'otherexample.com', 'a.otherexample.com', 'tracker.test', 'independent.test', 'unmatched.test']:
    assert route(fixture, domain) == route(builder.data['rules'], domain), domain
assert 'DOMAIN,keep.example.com,DIRECT' in builder.data['rules']
assert len(builder.data['rules']) == 5
assert requires_quic('AND,((DOMAIN-SUFFIX,example.com),(PROTOCOL,QUIC))')
assert not requires_quic('OR,((DOMAIN-SUFFIX,example.com),(PROTOCOL,QUIC))')
assert not requires_quic('NOT,((PROTOCOL,QUIC))')
builder.data['rules'] = ['IP-CIDR,1.2.3.4/32,REJECT,no-resolve', 'IP-CIDR,1.2.3.4/32,REJECT']
builder.locations['rules'] = ['fixture:1', 'fixture:2']
builder.deduplicate_rules()
assert len(builder.data['rules']) == 2
for section in ['url-rewrite', 'header-rewrite', 'body-rewrite', 'mock', 'script']:
    for row in data['http'][section]:
        pattern = row['match'] if isinstance(row, dict) else row.split()[0]
        re.compile(pattern)
for host in data['http']['mitm']:
    assert re.fullmatch(r'-?[a-zA-Z0-9.*?:_-]+', host), host
for mock in data['http']['mock']:
    if 'base64' in mock:
        base64.b64decode(mock['base64'], validate=True)
    elif mock.get('headers', {}).get('Content-Type') == 'application/json':
        json.loads(mock['text'])
expressions = []
for rule in data['http']['body-rewrite']:
    _, action, expression = rule.split(maxsplit=2)
    if action.endswith('-jq'):
        expressions.append(expression)
        jq.compile(expression)
# Exercise a real BaiduNetDisk rewrite rather than only compiling jq syntax.
baidu = next(x for x in expressions if x.startswith('.data.data |= map'))
before = {'data': {'data': [{'type': 'novel'}, {'type': 'file'}, {'type': 'shortplay'}]}}
assert jq.compile(baidu).input(before).first() == {'data': {'data': [{'type': 'file'}]}}
# Regression for Stash iOS failing to parse the Amap response-json-del
# expression containing a digit-prefixed JSON key and 39 concatenated paths.
# The published YAML must use short, valid native paths and jq for that key.
for row in core['http'].get('body-rewrite', []):
    if ' response-json-del ' in row or ' request-json-del ' in row:
        matched = re.search(r' (?:request|response)-json-del (.*)    if isinstance(rows, list):
        assert len(rows) == len({json.dumps(row, sort_keys=True) for row in rows}), section
assert any('response-jq .data.data |= map' in row for row in data['http']['body-rewrite'])
youtube = next(row for row in data['http']['script'] if 'YouTube_remove_ads_response' in row['name'])
assert json.loads(youtube['argument'])['captionLang'] == 'off'
assert youtube['binary-mode'] is True
weather = next(row for row in data['http']['script'] if 'weatherkit' in row['match'])
assert 'Weather.Provider=ColorfulClouds' in weather['argument']
assert '-weather-data.apple.com' in data['http']['mitm']
assert 'weatherkit.apple.com' in data['http']['mitm']
assert 'api.xiachufang.com' in data['http']['mitm']
assert report['addons'] == []
providers = core['script-providers']
scripts = core['http']['script']
assert report['counts']['script'] == len(scripts)
assert report['counts']['providers'] == len(providers)
assert 0 < len(scripts) <= 1024
assert set(providers) == {entry['name'] for entry in scripts}
# Full mode keeps internal page handlers and expanded script bindings.
assert len(core['http'].get('body-rewrite', [])) == report['source_counts']['body-rewrite']
assert any('虎扑' in name for name in providers)
assert sum('weatherkit' in row['match'] for row in scripts) == 2
assert all(not name.startswith(('loon-', 'ssrules-')) for name in providers)
for entry in scripts:
    assert entry['timeout'] <= 10
    if entry.get('require-body'):
        assert 0 < entry['max-size'] <= MAX_BODY_BYTES
for name, provider in providers.items():
    assert 'payload' not in provider
    assert provider['url'].startswith(RUNTIME_URL)
    filename = provider['url'][len(RUNTIME_URL):]
    assert '/' not in filename and '\\' not in filename
    assert not filename.startswith(('loon-', 'ssrules-')), filename
    runtime = ROOT / 'runtime' / filename
    original_name = filename.rsplit('-', 1)[0]
    assert runtime.read_text(encoding='utf-8') == data['script-providers'][original_name]['payload']
def script_identity(entry):
    return json.dumps({key: value for key, value in entry.items() if key not in ('name', 'timeout', 'max-size')}, sort_keys=True)
assert [script_identity(row) for row in scripts] == [script_identity(row) for row in selected('script')]
for published, original in zip(scripts, selected('script')):
    assert providers[published['name']]['url'].rsplit('/', 1)[1].rsplit('-', 1)[0] == original['name']
assert len(scripts) == len({script_identity(row) for row in scripts})
(ROOT / 'validation-input.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
subprocess.run(['node', str(ROOT / 'validate.mjs')], check=True)
subprocess.run(['node', str(ROOT / 'test_substore.mjs')], input=json.dumps(core, ensure_ascii=False), encoding='utf-8', check=True)
print('YAML, regex, references, mock responses, arguments, exclusions and deduplication OK.')
print(f'jq syntax OK: {len(expressions)} expressions; BaiduNetDisk filtering fixture OK.')
print('Deduplication preserves first-match routing, DIRECT exceptions, OR/NOT conditions and no-resolve behavior.')
print('Full dev override: all selected-source rewrites, body modifications, scripts and relevant MITM hosts retained; size limits and remote providers verified.')
, row)
        assert matched, row
        paths = matched.group(1).split()
        assert 1 <= len(paths) <= STASH_JSON_DEL_MAX_PATHS, row
        assert all(STASH_NATIVE_JSON_PATH.fullmatch(path) for path in paths), row
        assert not any(path.startswith('$.') for path in paths), row
assert any(' response-jq del(.data["920bestwishes"])' in row
           for row in core['http']['body-rewrite']), 'Amap numeric JSON key must be escaped as jq'
assert any(' response-json-del data.shadingWords' in row
           for row in core['http']['body-rewrite']), 'Loon JSONPath root must be removed'
assert not any('data.920bestwishes' in row for row in core['http']['body-rewrite'])
for section, rows in data['http'].items():
    if isinstance(rows, list):
        assert len(rows) == len({json.dumps(row, sort_keys=True) for row in rows}), section
assert any('response-jq .data.data |= map' in row for row in data['http']['body-rewrite'])
youtube = next(row for row in data['http']['script'] if 'YouTube_remove_ads_response' in row['name'])
assert json.loads(youtube['argument'])['captionLang'] == 'off'
assert youtube['binary-mode'] is True
weather = next(row for row in data['http']['script'] if 'weatherkit' in row['match'])
assert 'Weather.Provider=ColorfulClouds' in weather['argument']
assert '-weather-data.apple.com' in data['http']['mitm']
assert 'weatherkit.apple.com' in data['http']['mitm']
assert 'api.xiachufang.com' in data['http']['mitm']
assert report['addons'] == []
providers = core['script-providers']
scripts = core['http']['script']
assert report['counts']['script'] == len(scripts)
assert report['counts']['providers'] == len(providers)
assert 0 < len(scripts) <= 1024
assert set(providers) == {entry['name'] for entry in scripts}
# Full mode keeps internal page handlers and expanded script bindings.
assert len(core['http'].get('body-rewrite', [])) == report['source_counts']['body-rewrite']
assert any('虎扑' in name for name in providers)
assert sum('weatherkit' in row['match'] for row in scripts) == 2
assert all(not name.startswith(('loon-', 'ssrules-')) for name in providers)
for entry in scripts:
    assert entry['timeout'] <= 10
    if entry.get('require-body'):
        assert 0 < entry['max-size'] <= MAX_BODY_BYTES
for name, provider in providers.items():
    assert 'payload' not in provider
    assert provider['url'].startswith(RUNTIME_URL)
    filename = provider['url'][len(RUNTIME_URL):]
    assert '/' not in filename and '\\' not in filename
    assert not filename.startswith(('loon-', 'ssrules-')), filename
    runtime = ROOT / 'runtime' / filename
    original_name = filename.rsplit('-', 1)[0]
    assert runtime.read_text(encoding='utf-8') == data['script-providers'][original_name]['payload']
def script_identity(entry):
    return json.dumps({key: value for key, value in entry.items() if key not in ('name', 'timeout', 'max-size')}, sort_keys=True)
assert [script_identity(row) for row in scripts] == [script_identity(row) for row in selected('script')]
for published, original in zip(scripts, selected('script')):
    assert providers[published['name']]['url'].rsplit('/', 1)[1].rsplit('-', 1)[0] == original['name']
assert len(scripts) == len({script_identity(row) for row in scripts})
(ROOT / 'validation-input.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
subprocess.run(['node', str(ROOT / 'validate.mjs')], check=True)
subprocess.run(['node', str(ROOT / 'test_substore.mjs')], input=json.dumps(core, ensure_ascii=False), encoding='utf-8', check=True)
print('YAML, regex, references, mock responses, arguments, exclusions and deduplication OK.')
print(f'jq syntax OK: {len(expressions)} expressions; BaiduNetDisk filtering fixture OK.')
print('Deduplication preserves first-match routing, DIRECT exceptions, OR/NOT conditions and no-resolve behavior.')
print('Full dev override: all selected-source rewrites, body modifications, scripts and relevant MITM hosts retained; size limits and remote providers verified.')
