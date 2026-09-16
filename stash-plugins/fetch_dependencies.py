"""Refresh enabled Loon plugins and their complete dependency graph.

--refresh downloads every resource; failed batches never replace snapshots.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import time
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parent
UA = 'Loon/985 CFNetwork/3860.500.111.2.2 Darwin/25.4.0'
FIXED = {
    'scripts/fflate-0.8.2.js': 'https://cdn.jsdelivr.net/npm/fflate@0.8.2/umd/index.js',
    'scripts/fflate-LICENSE.txt': 'https://raw.githubusercontent.com/101arrowz/fflate/v0.8.2/LICENSE',
}


def excluded_plugin(url):
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc.lower() in ('github.com', 'raw.githubusercontent.com') and parsed.path.lower().startswith('/fmz200/')


def enabled_plugins(config):
    section = ''
    plugins = []
    names = set()
    for raw in config.splitlines():
        line = raw.strip()
        if not line or line.startswith(('#', ';', '//')):
            continue
        if line.startswith('['):
            section = line.lower()
            continue
        if section != '[plugin]' or re.search(r'\benabled\s*=\s*false\b', line, re.I):
            continue
        url = line.split(',', 1)[0].strip()
        parsed = urllib.parse.urlparse(url)
        name = Path(parsed.path).name
        if excluded_plugin(url):
            continue
        if parsed.scheme != 'https' or not name.endswith(('.lpx', '.plugin')):
            raise ValueError('Unsupported plugin URL: ' + url)
        if name in names:
            raise ValueError('Duplicate plugin snapshot filename: ' + name)
        names.add(name)
        plugins.append((url, name))
    if not plugins:
        raise ValueError('No enabled plugins; refusing to produce an empty override.')
    return plugins


def download(url):
    error = None
    for attempt in range(3):
        request_url = url
        if attempt:
            separator = '&' if '?' in url else '?'
            request_url += separator + 'stash-refresh=' + str(time.time_ns())
            time.sleep(attempt)
        try:
            req = urllib.request.Request(request_url, headers={'User-Agent': UA, 'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(req, timeout=40) as res:
                data = res.read()
            text = data.decode('utf-8-sig').replace('\r\n', '\n')
            if not text.strip() or text.lstrip().lower().startswith(('<!doctype html', '<html')):
                raise ValueError('Empty or HTML response instead of the requested resource')
            return text.encode('utf-8')
        except Exception as exc:
            error = exc
    raise RuntimeError(f'Download failed: {url}: {error}')


def fetch_batch(jobs, *, root, refresh):
    def fetch(job):
        relative, url = job
        path = root / relative
        return relative, download(url) if refresh or not path.exists() else path.read_bytes()
    with ThreadPoolExecutor(max_workers=6) as pool:
        return dict(pool.map(fetch, sorted(jobs.items())))


def atomic_write(path, data):
    if path.exists() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)


def refresh_resources(*, root=ROOT, refresh=False):
    plugins = enabled_plugins((root.parent / 'loon_config.conf').read_text(encoding='utf-8-sig'))
    plugin_jobs = {'sources/' + name: url for url, name in plugins}
    snapshots = fetch_batch(plugin_jobs, root=root, refresh=refresh)
    jobs, script_paths = {}, {}
    for path, data in snapshots.items():
        text = data.decode('utf-8-sig')
        if not re.search(r'^\[(?:Rule|Rewrite|Script|Mitm)\]\s*$', text, re.M | re.I):
            raise ValueError('Not a recognized Loon plugin: ' + path)
        for line in text.splitlines():
            if not line.strip() or line.lstrip().startswith(('#', ';', '//')):
                continue
            for url in re.findall(r'script-path\s*=\s*(https?://[^,\s]+)', line):
                name = sha256(url.encode()).hexdigest()[:12] + '-' + Path(urllib.parse.urlparse(url).path).name
                relative = 'scripts/' + name
                jobs[relative] = url
                script_paths[url] = relative
            for url in re.findall(r'(?:jq-path|data-path)\s*=\s*["\']?(https?://[^"\'\s,]+)', line):
                relative = 'sources/' + Path(urllib.parse.urlparse(url).path).name
                if relative in plugin_jobs or (relative in jobs and jobs[relative] != url):
                    raise ValueError('Dependency snapshot filename collision: ' + relative)
                jobs[relative] = url
    jobs.update(FIXED)
    snapshots.update(fetch_batch(jobs, root=root, refresh=refresh))
    dependencies = {
        url: {'file': relative, 'bytes': len(snapshots[relative])}
        for url, relative in sorted(script_paths.items())
    }
    digest = sha256()
    for path, data in sorted(snapshots.items()):
        digest.update(path.encode() + b'\0' + data + b'\0')
    fingerprint = digest.hexdigest()
    metadata_path = root / 'refresh.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    if metadata.get('sha256') != fingerprint:
        metadata = {
            'date': datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
            'sha256': fingerprint,
            'plugins': len(plugins),
            'scripts': len(script_paths),
        }
    # No snapshots are written until both download batches have succeeded.
    old_manifest = root / 'dependencies.json'
    previous = json.loads(old_manifest.read_text(encoding='utf-8')) if old_manifest.exists() else {}
    obsolete = {item['file'] for item in previous.values() if 'file' in item} - set(snapshots)
    old_aggregate = root / 'sources/blockAds.plugin'
    if old_aggregate.exists():
        for url in re.findall(r'(?:jq-path|data-path)\s*=\s*["\']?(https?://[^"\'\s,]+)', old_aggregate.read_text(encoding='utf-8-sig')):
            relative = 'sources/' + Path(urllib.parse.urlparse(url).path).name
            if relative not in snapshots:
                obsolete.add(relative)
        obsolete.add('sources/blockAds.plugin')
    for path, data in sorted(snapshots.items()):
        atomic_write(root / path, data)
    atomic_write(root / 'dependencies.json', (json.dumps(dependencies, indent=2, ensure_ascii=False) + '\n').encode())
    atomic_write(metadata_path, (json.dumps(metadata, indent=2, ensure_ascii=False) + '\n').encode())
    for relative in sorted(obsolete):
        target = (root / relative).resolve()
        allowed = {(root / 'scripts').resolve(), (root / 'sources').resolve()}
        if target.parent not in allowed:
            raise ValueError('Refusing to delete a path outside resource directories: ' + relative)
        target.unlink(missing_ok=True)
    print(json.dumps({'plugins': len(plugins), 'scripts': len(script_paths), 'resources': len(snapshots), 'date': metadata['date'], 'sha256': fingerprint}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Re-download plugins, scripts, jq and mock resources even when cached.')
    args = parser.parse_args()
    refresh_resources(refresh=args.refresh)
