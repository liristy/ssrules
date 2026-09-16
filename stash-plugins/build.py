"""Build one Stash override with native rewrites and external script providers.

Requires PyYAML. Unknown syntax fails the build instead of silently losing rules.
"""
from collections import Counter
from fnmatch import fnmatchcase
from hashlib import sha256
import json
from pathlib import Path
import re
import urllib.parse
import yaml
from fetch_dependencies import enabled_plugins, excluded_plugin

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
OUTPUT = PROJECT / 'stash_plugins.stoverride'
QUIC_RULES = [
    'PROTOCOL,QUIC,REJECT,no-track',
    'AND,((NETWORK,UDP),(DST-PORT,443)),REJECT,no-track',
]
RUNTIME_URL = 'https://raw.githubusercontent.com/liristy/ssrules/main/stash-plugins/runtime/'
MAX_BODY_BYTES = 256 * 1024
NATIVE_HTTP_SECTIONS = ('url-rewrite', 'header-rewrite', 'body-rewrite', 'mock')


def needs_http(rule):
    return bool(re.search(r'(?:^|\()(?:URL-REGEX|USER-AGENT),', rule))


def literal_url_hosts(pattern):
    """Prove a finite host list for simple anchored URL patterns; otherwise abstain."""
    depth, in_class, escaped = 0, False, False
    for char in pattern:
        if escaped:
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == '[':
            in_class = True
        elif char == ']' and in_class:
            in_class = False
        elif not in_class:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == '|' and depth == 0:
                return None
    pattern = pattern.replace(r'\/', '/')
    prefix = re.match(r'^\^https?\??://', pattern)
    if not prefix:
        return None
    authority, slash, _ = pattern[prefix.end():].partition('/')
    if not slash:
        return None
    pending, hosts = [authority], []
    while pending:
        value = pending.pop()
        group = re.search(r'\(\?:([a-zA-Z0-9|-]+)\)', value)
        if group:
            pending.extend(value[:group.start()] + part + value[group.end():] for part in group[1].split('|'))
            if len(pending) + len(hosts) > 64:
                return None
            continue
        # An unescaped dot, optional port, character class, or other regex means
        # we cannot safely enumerate every host, so retain the source wildcard.
        if not re.fullmatch(r'[a-zA-Z0-9-]+(?:\\\.[a-zA-Z0-9-]+)+', value):
            return None
        hosts.append(value.replace(r'\.', '.').lower())
    return sorted(set(hosts))


def narrow_mitm(entries):
    hosts = entries.get('mitm', [])
    if any(needs_http(rule) for rule in entries.get('rules', [])):
        return hosts
    patterns = [row['match'] if isinstance(row, dict) else row.split()[0]
                for key in (*NATIVE_HTTP_SECTIONS, 'script') for row in entries.get(key, [])]
    if not patterns:
        return hosts
    required = set()
    for pattern in patterns:
        resolved = literal_url_hosts(pattern)
        if resolved is None:
            return hosts
        required.update(resolved)
    result = []
    for host in hosts:
        if not host.startswith('-') and '*' in host:
            matched = sorted(value for value in required if fnmatchcase(value, host.lower()))
            # Keep unmatched host entries rather than guessing they are obsolete.
            result.extend(matched or [host])
        else:
            result.append(host)
    return list(dict.fromkeys(result))


def sections(text):
    result = {}
    section = ''
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith(('#', ';', '//')):
            continue
        if re.fullmatch(r'\[[\w ]+\]', line):
            section = line[1:-1].lower()
            continue
        result.setdefault(section, []).append((number, line))
    return result


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def scalar(value):
    value = unquote(value.strip())
    if value in ('true', 'false'):
        return value == 'true'
    return value


def rule_parts(rule):
    """Separate the policy/options from the right; regexes may contain commas."""
    condition, tail = rule.rsplit(',', 1)
    options = []
    while tail in ('no-track', 'no-resolve'):
        options.append(tail)
        condition, tail = condition.rsplit(',', 1)
    return condition, tail, options


def requires_quic(condition):
    """Prove that a logical condition requires QUIC; unknown leaves stay opaque."""
    if condition == 'PROTOCOL,QUIC':
        return True
    kind, _, body = condition.partition(',')
    if kind not in ('AND', 'OR') or not body.startswith('((') or not body.endswith('))'):
        return False
    children, depth, start = [], 0, 0
    inner = body[1:-1]
    for index, char in enumerate(inner):
        if char == '(':
            if depth == 0:
                start = index + 1
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                children.append(inner[start:index])
        elif depth == 0 and char != ',':
            return False
        if depth < 0:
            return False
    if depth or not children:
        return False
    proofs = [requires_quic(child) for child in children]
    return any(proofs) if kind == 'AND' else all(proofs)


class Literal(str):
    pass


class Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


Dumper.add_representer(Literal, lambda d, s: d.represent_scalar('tag:yaml.org,2002:str', s, style='|'))


class Builder:
    def __init__(self):
        self.dependencies = json.loads((ROOT / 'dependencies.json').read_text(encoding='utf-8'))
        self.data = {
            'name': '广告净化',
            'desc': '应用去广告、隐私拦截、QUIC 屏蔽与天气增强。',
            'date': '2026-09-16',
            'rules': [],
            'http': {'force-http-engine': ['*:80'], 'mitm': [], 'url-rewrite': [], 'header-rewrite': [], 'body-rewrite': [], 'mock': [], 'script': []},
            'script-providers': {},
        }
        self.seen = {}
        self.duplicates = Counter()
        self.notes = []
        self.sources = []
        self.locations = {}
        self.defaults = {}
        self.source = ''
        self.line = 0
        self.shadowed_rules = []
        self.plugin_entries = {}
        self.plugin_names = {}

    def note(self, message):
        self.notes.append({'source': self.source, 'line': self.line, 'message': message})

    def deduplicate_rules(self):
        """Keep first-match behavior; only remove provably unreachable entries."""
        retained, locations, conditions = [], [], {}
        domains, suffixes, keywords = {}, {}, {}
        quic = None
        for rule, location in zip(self.data['rules'], self.locations['rules']):
            condition, _, options = rule_parts(rule)
            kind, _, value = condition.partition(',')
            if kind in ('DOMAIN', 'DOMAIN-SUFFIX'):
                value = value.lower()
                condition = kind + ',' + value
            # no-track changes logging, not matching; no-resolve can change matching.
            key = (condition, 'no-resolve' in options)
            covering = conditions.get(key)
            reason = '相同匹配条件，保留先匹配规则'
            if covering is None and quic is not None and requires_quic(condition):
                covering, reason = quic, '已被前面的全局 QUIC 屏蔽覆盖'
            if covering is None and kind in ('DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD'):
                # A previous keyword matching part of a later keyword/domain
                # necessarily matches every connection that the later rule does.
                covering = next((r for keyword, r in keywords.items() if keyword in value), None)
                if covering is None and kind in ('DOMAIN', 'DOMAIN-SUFFIX'):
                    covering = next((r for suffix, r in suffixes.items() if value == suffix or value.endswith('.' + suffix)), None)
                if covering is None and kind == 'DOMAIN':
                    covering = domains.get(value)
                reason = '匹配范围已被前面的域名规则完全覆盖'
            if covering is not None:
                self.shadowed_rules.append({'source': location, 'removed': rule, 'retained': covering, 'reason': reason})
                continue
            retained.append(rule)
            locations.append(location)
            conditions[key] = rule
            if condition == 'PROTOCOL,QUIC':
                quic = rule
            if kind == 'DOMAIN':
                domains[value] = rule
            elif kind == 'DOMAIN-SUFFIX':
                suffixes[value] = rule
            elif kind == 'DOMAIN-KEYWORD':
                keywords[value] = rule
        self.data['rules'] = retained
        self.locations['rules'] = locations

    def add(self, section, entry):
        # Capture independently: a later optional addon must not lose entries
        # just because another addon contains the same rule.
        entries = self.plugin_entries.setdefault(self.source, {}).setdefault(section, [])
        if entry not in entries:
            entries.append(entry)
        key = json.dumps(entry, sort_keys=True, ensure_ascii=False)
        seen = self.seen.setdefault(section, set())
        if key in seen:
            self.duplicates[section] += 1
            return
        seen.add(key)
        target = self.data['rules'] if section == 'rules' else self.data['http'][section]
        target.append(entry)
        self.locations.setdefault(section, []).append(f'{self.source}:{self.line}')

    def export_combined(self):
        """Merge all enabled features while keeping script code externally hosted."""
        full = self.data
        # Build-time validation only. This file is ignored by Git and never imported.
        (ROOT / 'validation-input.json').write_text(json.dumps(full, ensure_ascii=False), encoding='utf-8')
        hosts = [host for host in full['http']['mitm'] if host.startswith('-')]
        for filename, entries in self.plugin_entries.items():
            narrowed = narrow_mitm(entries)
            hosts.extend(narrowed)
            if narrowed != entries.get('mitm', []):
                self.notes.append({'source': filename, 'message': '将可完整枚举的 MITM 通配域名收窄为实际规则接口。', 'before': entries['mitm'], 'after': narrowed})
        core = {
            'name': '广告净化',
            'desc': '应用去广告、隐私拦截、QUIC 屏蔽与天气增强。',
            'date': full['date'],
            'rules': list(full['rules']),
            'http': {
                'mitm': list(dict.fromkeys(hosts)),
                **{key: list(full['http'][key]) for key in NATIVE_HTTP_SECTIONS if full['http'][key]},
                'script': [dict(entry) for entry in full['http']['script']],
            },
            'script-providers': {},
        }
        runtime_files = {}
        addon_dir = ROOT / 'addons'
        for entry in core['http']['script']:
            entry['timeout'] = min(entry.get('timeout', 10), 10)
            if entry.get('require-body'):
                entry['max-size'] = min(entry.get('max-size', MAX_BODY_BYTES) or MAX_BODY_BYTES, MAX_BODY_BYTES)
            name = entry['name']
            payload = str(full['script-providers'][name]['payload'])
            digest = sha256(payload.encode()).hexdigest()[:12]
            runtime_name = name + '-' + digest + '.js'
            runtime_files[runtime_name] = payload
            core['script-providers'][name] = {'url': RUNTIME_URL + runtime_name, 'interval': 86400}
        assert len(core['http']['script']) <= 80, 'Script bindings exceeded the size budget'
        runtime_dir = ROOT / 'runtime'
        runtime_dir.mkdir(exist_ok=True)
        for name, payload in runtime_files.items():
            (runtime_dir / name).write_text(payload, encoding='utf-8', newline='\n')
        # Remove only files identified as generated by the previous build report.
        previous_report = ROOT / 'report.json'
        previous = json.loads(previous_report.read_text(encoding='utf-8')) if previous_report.exists() else {}
        for item in previous.get('addons', []):
            old = (ROOT / item['file']).resolve()
            if old.parent != addon_dir.resolve():
                raise ValueError('Invalid generated addon path')
            old.unlink(missing_ok=True)
        # Versioned runtime scripts are retained for clients using older overrides.
        self.data = core

    def provider(self, url):
        entry = self.dependencies[url]
        if 'error' in entry:
            raise ValueError(f'Dependency download failed: {url}: {entry}')
        name = 'loon-' + Path(urllib.parse.urlparse(url).path).stem + '-' + sha256(url.encode()).hexdigest()[:8]
        providers = self.data['script-providers']
        if name not in providers:
            script = (ROOT / entry['file']).read_text(encoding='utf-8-sig')
            # Surge's abort result is not a Stash response field.
            script = script.replace('$done({abort:!0})', '$done()')
            prefix = '// Original source: ' + url + '\n'
            if '$utils.ungzip' in script:
                license_text = (ROOT / 'scripts/fflate-LICENSE.txt').read_text(encoding='utf-8')
                fflate = (ROOT / 'scripts/fflate-0.8.2.js').read_text(encoding='utf-8')
                prefix += '/* fflate 0.8.2 — gzip adapter for Stash\n' + license_text + '\n*/\n'
                prefix += fflate + '\n'
                prefix += 'var $utils = { ungzip: function (bytes) { return globalThis.fflate.gunzipSync(new Uint8Array(bytes)); } };\n'
            # Some source scripts use top-level return. An async wrapper also
            # permits await while keeping failures from breaking app traffic.
            wrapped = '(async function () {\n' + script.rstrip() + '\n}).call(globalThis).catch(function (error) { console.log(String(error)); $done({}); });\n'
            providers[name] = {'payload': Literal(prefix + wrapped)}
        return name

    def script(self, line):
        broken = 'a朴朴超市, enable={pupuicui_enable}_resource'
        if broken in line:
            line = line.replace(broken, 'app_resource')
            self.note('修复朴朴脚本 URL 正则中混入的标签和开关文本，恢复 app_resource 路径。')
        match = re.fullmatch(r'http-(request|response)\s+(\S+)\s+(.+)', line)
        if not match:
            raise ValueError('Unrecognized script: ' + line)
        kind, pattern, rest = match.groups()
        keys = list(re.finditer(r'(?:^|,\s*)([\w-]+)\s*=\s*', rest))
        options = {m[1]: rest[m.end():keys[i+1].start() if i+1 < len(keys) else len(rest)].strip() for i,m in enumerate(keys)}
        unknown = set(options) - {'script-path', 'requires-body', 'binary-body-mode', 'timeout', 'tag', 'enable', 'argument', 'max-size'}
        if unknown:
            raise ValueError('Unrecognized script options: ' + str(unknown))
        enabled = options.get('enable', 'true')
        if enabled.startswith('{'):
            key = enabled.strip('{}')
            if key not in self.defaults:
                # Upstream blockAds references an undeclared optimizeRequest switch.
                self.note('未声明的脚本开关 ' + key + ' 按启用处理；参数交给脚本内置默认值。')
            enabled = self.defaults.get(key, True)
        if enabled in (False, 'false'):
            self.note('保留源插件默认关闭状态：' + options.get('tag', pattern))
            return
        entry = {'name': self.provider(options['script-path']), 'match': pattern, 'type': kind}
        for old, new in [('requires-body','require-body'), ('binary-body-mode','binary-mode')]:
            if old in options:
                entry[new] = options[old] == 'true'
        for key in ('timeout', 'max-size'):
            if key in options:
                entry[key] = int(options[key])
        if 'argument' in options:
            raw = options['argument']
            names = re.findall(r'\{([^}]+)\}', raw)
            args = {name: self.defaults[name] for name in names if name in self.defaults}
            missing = [name for name in names if name not in self.defaults]
            if missing:
                self.note('源插件未声明参数，使用脚本自身默认值：' + ', '.join(missing))
            # WeatherKit and Tieba parse key=value; other argument consumers parse JSON.
            if 'WeatherKit/' in options['script-path'] or options['script-path'].endswith('/tieba-proto.js'):
                entry['argument'] = '&'.join(f'{k}={str(v).lower() if isinstance(v,bool) else v}' for k,v in args.items())
            else:
                entry['argument'] = json.dumps(args, ensure_ascii=False, separators=(',', ':')) if names else unquote(raw)
        self.add('script', entry)

    def rule(self, line):
        line = re.split(r'\s+//', line, maxsplit=1)[0]
        line = re.sub(r'\s*,\s*', ',', line).replace('"', '')
        # Plugin PROXY is assigned to AUTO by the user's Loon configuration.
        if line.endswith(',PROXY'):
            line = line[:-5] + 'AUTO'
            self.note('PROXY 按原 [Plugin] policy=AUTO 映射；需要基础配置含 AUTO 策略组。')
        if line.endswith(',REJECT-DICT'):
            kind, pattern, _ = line.split(',', 2)
            assert kind == 'URL-REGEX'
            self.add('url-rewrite', pattern + ' - reject-dict')
        else:
            self.add('rules', line)

    def rewrite(self, line):
        if r'res\.kfc\.com.\cn' in line:
            line = line.replace(r'res\.kfc\.com.\cn', r'res\.kfc\.com\.cn')
            self.note('修复肯德基域名正则中的无效 \\c 转义。')
        if line.startswith(('http-request ', 'http-response ')):
            self.note('将源文件错放在 Rewrite 段的脚本移回 script。')
            if 'requires-body' not in line and line.startswith('http-response '):
                line += ', requires-body=true'
            return self.script(line)
        pattern, action, *tail = line.split(maxsplit=2)
        rest = tail[0] if tail else ''
        if action == '-':
            action, rest = rest, ''
        if action.startswith('reject'):
            if rest:
                assert rest == action, line
                self.note('移除重复的 ' + action + ' 动作。')
            assert action in ('reject','reject-200','reject-dict','reject-array','reject-img'), line
            self.add('url-rewrite', pattern + ' - ' + action)
        elif action in ('302','307','header'):
            # Loon header redirects the request internally, equivalent to transparent.
            self.add('url-rewrite', f'{pattern} {rest} {"transparent" if action == "header" else action}')
        elif rest in ('302','307','header'):
            self.add('url-rewrite', f'{pattern} {action} {"transparent" if rest == "header" else rest}')
        elif action.startswith(('response-body-', 'request-body-')):
            converted = action.replace('-body-', '-').replace('-json-jq', '-jq')
            if converted.endswith('-jq'):
                rest = unquote(rest)
                external = re.fullmatch(r'jq-path="([^"]+)"', rest)
                if external:
                    resource = Path(urllib.parse.urlparse(external[1]).path).name
                    jq_text = (ROOT / 'sources' / resource).read_text(encoding='utf-8-sig')
                    rest = ' '.join(line.strip() for line in jq_text.splitlines() if line.strip() and not line.lstrip().startswith('#'))
                    self.note('内嵌远程 jq：' + resource)
            if '"imgUrl" response-body "fmz200"' == rest:
                rest = '"imgUrl" "fmz200"'
                self.note('修复正则替换中多余的 response-body 标记。')
            self.add('body-rewrite', f'{pattern} {converted} {rest}')
        elif action.startswith(('response-header-', 'request-header-')):
            self.add('header-rewrite', f'{pattern} {action.replace("-header-", "-")} {rest}')
        elif action == 'mock-response-body':
            status = re.search(r'status-code=(\d+)', rest)
            entry = {'match': pattern, 'status-code': int(status[1]) if status else 200}
            remote = re.search(r'data-path="([^"]+)"', rest)
            if remote:
                body = (ROOT / 'sources' / Path(urllib.parse.urlparse(remote[1]).path).name).read_text(encoding='utf-8-sig')
            else:
                bodymatch = re.search(r'data="(.*)"(?:\s+\w[\w-]*=.*)?$', rest)
                assert bodymatch, line
                body = bodymatch[1]
            if 'mock-data-is-base64=true' in rest:
                entry['base64'] = body
                entry['headers'] = {'Content-Type': 'application/grpc', 'grpc-status': '0'}
            else:
                entry['text'] = body
                entry['headers'] = {'Content-Type': 'application/json' if 'data-type=json' in rest else 'text/plain; charset=utf-8'}
            self.add('mock', entry)
        else:
            raise ValueError('Unrecognized rewrite: ' + line)

    def build(self):
        self.source = 'user:QUIC'
        for self.line, rule in enumerate(QUIC_RULES, 1):
            self.add('rules', rule)
        config_text = (PROJECT / 'loon_config.conf').read_text(encoding='utf-8-sig')
        config = sections(config_text)
        plugins = enabled_plugins(config_text)
        refresh_path = ROOT / 'refresh.json'
        if refresh_path.exists():
            self.data['date'] = json.loads(refresh_path.read_text(encoding='utf-8'))['date']
        for url, filename in plugins:
            self.source = filename
            text = (ROOT / 'sources' / self.source).read_text(encoding='utf-8-sig')
            title = re.search(r'^#!name\s*=\s*(.+)$', text, re.M)
            self.plugin_names[filename] = title[1].strip() if title else Path(filename).stem
            self.sources.append({'file': self.source, 'url': url, 'sha256': sha256(text.encode()).hexdigest()})
            parts = sections(text)
            self.defaults = {}
            for self.line, line in parts.get('argument', []):
                key, choices = line.split('=', 1)
                self.defaults[key.strip()] = scalar(choices.split(',')[1])
            for section, rows in parts.items():
                for self.line, line in rows:
                    if section == 'argument':
                        continue
                    elif section == 'rule':
                        self.rule(line)
                    elif section == 'rewrite':
                        self.rewrite(line)
                    elif section == 'script':
                        # One plain reject rewrite is misplaced under [Script] upstream.
                        if not line.startswith('http-'):
                            self.note('将源文件错放在 Script 段的重写移回 url-rewrite。')
                            self.rewrite(line)
                        else:
                            self.script(line)
                    elif section == 'mitm':
                        assert line.lower().startswith('hostname'), line
                        if line.lower().count('hostname') > 1:
                            self.note('修复 MITM 列表中粘连的 hostname =，拆分为两个域名。')
                        hosts = re.sub(r'hostname\s*=', ',', line, flags=re.I)
                        for host in hosts.split(','):
                            if host.strip():
                                self.add('mitm', host.strip())
                    else:
                        raise ValueError('Unrecognized section: ' + section)
        self.deduplicate_rules()
        # Keep the user's existing Loon MITM exclusions before positive hosts.
        exclusions = []
        for _, line in config.get('mitm', []):
            if line.lower().startswith('hostname'):
                exclusions.extend(x.strip() for x in line.split('=',1)[1].split(',') if x.strip().startswith('-'))
        hosts = self.data['http']['mitm']
        self.data['http']['mitm'] = list(dict.fromkeys(exclusions + [x for x in hosts if x.startswith('-')] + [x for x in hosts if not x.startswith('-')]))
        source_counts = {'plugins': len(self.sources), 'rules': len(self.data['rules']), 'providers': len(self.data['script-providers']), **{k:len(v) for k,v in self.data['http'].items()}}
        self.export_combined()
        counts = {'plugins': len(self.sources), 'rules': len(self.data['rules']), 'providers': len(self.data['script-providers']), **{key: len(value) for key, value in self.data['http'].items()}}
        excluded = [line.split(',', 1)[0].strip() for _, line in config.get('plugin', []) if excluded_plugin(line.split(',', 1)[0].strip())]
        report = {'date': self.data['date'], 'profile': 'combined', 'counts': counts, 'source_counts': source_counts, 'addons': [], 'excluded_plugins': excluded, 'duplicates_removed': dict(self.duplicates), 'shadowed_rules_removed': self.shadowed_rules, 'sources': self.sources, 'adjustments': self.notes}
        (ROOT / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        (ROOT / 'locations.json').write_text(json.dumps(self.locations, ensure_ascii=False), encoding='utf-8')
        header = '# 自动生成：python stash-plugins/build.py\n# 拦截、重写和脚本已合并；只需导入此覆写，脚本代码通过远程地址加载。\n# HTTPS 重写需要启用 MITM 并信任自己的证书；请停用旧版及独立增强覆写后替换。\n'
        output = header + yaml.dump(self.data, Dumper=Dumper, allow_unicode=True, sort_keys=False, width=120)
        assert yaml.safe_load(output) == self.data
        assert len(output.encode()) < 150_000, 'Core override exceeded its size budget'
        assert not re.search(r'\{(?:\w+_enable|Weather\.Provider)\}', output)
        OUTPUT.write_text(output, encoding='utf-8')
        print(json.dumps(counts, ensure_ascii=False))
        print('Bytes:', OUTPUT.stat().st_size)


if __name__ == '__main__':
    Builder().build()
