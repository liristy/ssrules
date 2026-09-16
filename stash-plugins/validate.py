"""Static checks and fixture tests; does not claim to run the Stash app."""
import base64
import json
from pathlib import Path
import re
import subprocess
import yaml
import jq
from build import Builder, QUIC_RULES, requires_quic, sections, needs_http, RUNTIME_URL, MAX_BODY_BYTES
from fetch_dependencies import enabled_plugins

ROOT = Path(__file__).resolve().parent
core_path = ROOT.parent / 'stash_plugins.stoverride'
core = yaml.safe_load(core_path.read_text(encoding='utf-8'))
data = json.loads((ROOT / 'validation-input.json').read_text(encoding='utf-8'))
report = json.loads((ROOT / 'report.json').read_text(encoding='utf-8'))
config_text = (ROOT.parent / 'loon_config.conf').read_text(encoding='utf-8-sig')
assert report['counts']['plugins'] == len(enabled_plugins(config_text))
assert report['counts']['rules'] == len(core['rules'])
assert report['source_counts']['rules'] == len(data['rules'])
assert report['profile'] == 'lightweight-core'
assert not any(item['file'] == 'blockAds.plugin' or '/fmz200/' in item['url'] for item in report['sources'])
assert not any('/fmz200/' in url for url in json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8')))
assert 'script-providers' not in core
assert set(core['http']) == {'mitm'}
assert all(host.startswith('-') for host in core['http']['mitm'])
assert not any(needs_http(rule) for rule in core['rules'])
assert core['rules'] == [rule for rule in data['rules'] if not needs_http(rule)]
assert core_path.stat().st_size < 150_000
assert core['rules'][:2] == QUIC_RULES
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
assert data['rules'][:2] == QUIC_RULES
assert not any(requires_quic(rule.rsplit(',', 1)[0]) for rule in data['rules'][2:])
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
for section, rows in data['http'].items():
    if isinstance(rows, list):
        assert len(rows) == len({json.dumps(row, sort_keys=True) for row in rows}), section
assert any('response-jq .data.data |= map' in row for row in data['http']['body-rewrite'])
youtube = next(row for row in data['http']['script'] if 'YouTube_remove_ads_response' in row['name'])
assert json.loads(youtube['argument'])['captionLang'] == 'zh-Hans'
assert youtube['binary-mode'] is True
weather = next(row for row in data['http']['script'] if 'weatherkit' in row['match'])
assert 'Weather.Provider=ColorfulClouds' in weather['argument']
assert '-weather-data.apple.com' in data['http']['mitm']
assert 'weatherkit.apple.com' in data['http']['mitm']
assert 'api.xiachufang.com' in data['http']['mitm']
for item in report['addons']:
    addon_path = ROOT / item['file']
    addon = yaml.safe_load(addon_path.read_text(encoding='utf-8'))
    assert 'blockAds' not in item['file']
    assert addon_path.stat().st_size < 100_000
    assert 'force-http-engine' not in addon['http']
    assert addon['http']['mitm'][:len(exclusions)] == exclusions
    providers = addon.get('script-providers', {})
    scripts = addon['http'].get('script', [])
    assert len(scripts) <= 80
    assert set(providers) == {entry['name'] for entry in scripts}
    for entry in scripts:
        assert entry['timeout'] <= 10
        if entry.get('require-body'):
            assert 0 < entry['max-size'] <= MAX_BODY_BYTES
    for name, provider in providers.items():
        assert 'payload' not in provider
        assert provider['url'].startswith(RUNTIME_URL)
        filename = provider['url'][len(RUNTIME_URL):]
        assert '/' not in filename and '\\' not in filename
        runtime = ROOT / 'runtime' / filename
        assert runtime.read_text(encoding='utf-8') == data['script-providers'][name]['payload']
(ROOT / 'validation-input.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
subprocess.run(['node', str(ROOT / 'validate.mjs')], check=True)
print('YAML, regex, references, mock responses, arguments, exclusions and deduplication OK.')
print(f'jq syntax OK: {len(expressions)} expressions; BaiduNetDisk filtering fixture OK.')
print('Deduplication preserves first-match routing, DIRECT exceptions, OR/NOT conditions and no-resolve behavior.')
print('Lightweight core: no JavaScript, HTTP matching, body rewrites or positive MITM hosts; fmz200 aggregate excluded. Optional addons have external scripts and bounded bodies.')
