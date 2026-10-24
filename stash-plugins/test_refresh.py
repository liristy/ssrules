"""Refresh integration tests using an isolated filesystem and fake upstreams."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fetch_dependencies as fetcher


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'stash-plugins'
        (self.root / 'sources').mkdir(parents=True)
        (self.root.parent / 'loon_config.conf').write_text(
            '[Plugin]\nhttps://test.invalid/demo.lpx, enabled = true\n'
            'https://test.invalid/off.lpx, enabled = false\n[Mitm]\nhostname=-example.com\n', encoding='utf-8')
        (self.root / 'sources/demo.lpx').write_text('[Rule]\nDOMAIN,old.test,REJECT\n', encoding='utf-8')
        self.plugin = (
            '[Script]\nhttp-response ^https://example.com/ script-path=https://test.invalid/app.js, requires-body=true\n'
            '[Rewrite]\n^https://example.com/ response-body-json-jq jq-path="https://test.invalid/filter.jq"\n'
            '^https://example.com/mock mock-response-body data-path="https://test.invalid/body.json"\n'
        ).encode()
        self.resources = {
            'https://test.invalid/demo.lpx': self.plugin,
            'https://test.invalid/app.js': b'$done({});\n',
            'https://test.invalid/filter.jq': b'del(.ads)\n',
            'https://test.invalid/body.json': b'{}\n',
        }

    def run_refresh(self):
        with patch.object(fetcher, 'FIXED', {}), patch.object(fetcher, 'download', side_effect=self.resources.__getitem__), redirect_stdout(StringIO()):
            fetcher.refresh_resources(root=self.root, refresh=True)

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_refresh_replaces_cached_plugin_and_follows_new_dependencies(self):
        self.run_refresh()
        self.assertEqual((self.root / 'sources/demo.lpx').read_bytes(), self.plugin)
        self.assertTrue((self.root / 'sources/filter.jq').exists())
        self.assertTrue((self.root / 'sources/body.json').exists())
        manifest = json.loads((self.root / 'dependencies.json').read_text())
        script = self.root / manifest['https://test.invalid/app.js']['file']
        self.resources['https://test.invalid/app.js'] = b'$done({body: "new"});\n'
        self.run_refresh()
        self.assertEqual(script.read_bytes(), self.resources['https://test.invalid/app.js'])

    def test_failed_dependency_download_keeps_all_previous_files(self):
        self.run_refresh()
        previous = self.snapshot()
        self.resources['https://test.invalid/demo.lpx'] += b'# updated upstream\n'
        del self.resources['https://test.invalid/app.js']
        with self.assertRaises(KeyError):
            self.run_refresh()
        self.assertEqual(self.snapshot(), previous)

    def test_conditional_script_dependency_is_downloaded(self):
        self.resources['https://test.invalid/demo.lpx'] = (
            '[Script]\nresponse if ${url} ~= /^https:\\/\\/example.com\\//i then '
            'script("https://test.invalid/app.js", {${enabled}}) with requires_body=true\n'
        ).encode()
        self.run_refresh()
        manifest = json.loads((self.root / 'dependencies.json').read_text())
        self.assertEqual((self.root / manifest['https://test.invalid/app.js']['file']).read_bytes(),
                         self.resources['https://test.invalid/app.js'])

    def test_conditional_jq_file_is_fetched_and_refreshed(self):
        from hashlib import sha256
        url = 'https://test.invalid/filter.jq'
        self.resources['https://test.invalid/demo.lpx'] = (
            '[Rewrite]\n'
            r'response if ${url} ~= /^https:\/\/example\.com\//i then response.json.jq_file("https://test.invalid/filter.jq")'
            '\n'
        ).encode()
        self.run_refresh()
        name = sha256(url.encode()).hexdigest()[:12] + '-filter.jq'
        path = self.root / 'sources' / name
        self.assertEqual(path.read_bytes(), self.resources[url])
        self.resources[url] = b'del(.new_ad_field)\n'
        self.run_refresh()
        self.assertEqual(path.read_bytes(), self.resources[url])

    def test_unchanged_refresh_preserves_date_and_files(self):
        self.run_refresh()
        path = self.root / 'refresh.json'
        metadata = json.loads(path.read_text())
        metadata['date'] = '2025-01-01'
        path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n', newline='\n')
        previous = self.snapshot()
        self.run_refresh()
        self.assertEqual(self.snapshot(), previous)

    def test_reject_empty_plugin_selection(self):
        with self.assertRaises(ValueError):
            fetcher.enabled_plugins('[Plugin]\nhttps://test.invalid/off.lpx, enabled=false\n')

    def test_fmz200_full_plugin_is_included_when_enabled_in_loon(self):
        selected = fetcher.enabled_plugins(
            '[Plugin]\nhttps://test.invalid/demo.lpx, enabled=true\n'
            'https://raw.githubusercontent.com/fmz200/wool_scripts/main/Loon/plugin/blockAds.plugin, enabled=true\n')
        self.assertEqual(selected, [('https://test.invalid/demo.lpx', 'demo.lpx'),
                                    ('https://raw.githubusercontent.com/fmz200/wool_scripts/main/Loon/plugin/blockAds.plugin', 'blockAds.plugin')])

    def test_enabled_full_aggregate_is_not_deleted_after_successful_refresh(self):
        aggregate = 'https://raw.githubusercontent.com/fmz200/wool_scripts/main/Loon/plugin/blockAds.plugin'
        config = ('[Plugin]\n'
                  'https://test.invalid/demo.lpx, enabled=true\n'
                  + aggregate + ', enabled=true\n')
        (self.root.parent / 'loon_config.conf').write_text(config, encoding='utf-8')
        self.resources[aggregate] = b'[Rule]\nDOMAIN,ad-one.test,REJECT\n'
        self.run_refresh()
        source = self.root / 'sources/blockAds.plugin'
        self.assertEqual(source.read_bytes(), self.resources[aggregate])
        self.resources[aggregate] = b'[Rule]\nDOMAIN,ad-two.test,REJECT\n'
        self.run_refresh()
        self.assertEqual(source.read_bytes(), self.resources[aggregate])
        self.assertIn('blockAds.plugin', [name for _, name in fetcher.selected_plugins(config, root=self.root)])

    def test_obsolete_script_snapshot_is_removed_after_success(self):
        self.run_refresh()
        manifest = json.loads((self.root / 'dependencies.json').read_text())
        old_script = self.root / manifest['https://test.invalid/app.js']['file']
        self.resources['https://test.invalid/demo.lpx'] = b'[Rule]\nDOMAIN,new.test,REJECT\n'
        self.run_refresh()
        self.assertFalse(old_script.exists())
        self.assertEqual(json.loads((self.root / 'dependencies.json').read_text()), {})

    def test_download_uses_loon_ua_and_rejects_html(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'<!DOCTYPE html><html>blocked</html>'
        with patch.object(fetcher.urllib.request, 'urlopen', return_value=Response()) as request, patch.object(fetcher.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                fetcher.download('https://test.invalid/app.js')
            self.assertEqual(request.call_count, 3)
            self.assertEqual(request.call_args.args[0].get_header('User-agent'), fetcher.UA)

    def test_extra_plugin_downloads_entire_content_and_all_dependencies(self):
        extra = {'file': 'Extra.lpx', 'name': 'Full app',
                 'url': 'https://test.invalid/aggregate.plugin'}
        (self.root / 'extra-plugins.json').write_text(json.dumps([extra]), encoding='utf-8')
        self.resources[extra['url']] = (
            '[Script]\n'
            'http-response ^https://selected.test/ script-path=https://test.invalid/selected.js, requires-body=true\n'
            'http-response ^https://unrelated.test/ script-path=https://test.invalid/unrelated.js\n'
            '[Rule]\nDOMAIN, ads.selected.test, REJECT\nDOMAIN, other.test, REJECT\n'
        ).encode()
        self.resources['https://test.invalid/selected.js'] = b'$done({});\n'
        self.resources['https://test.invalid/unrelated.js'] = b'$done({});\n'
        self.run_refresh()
        snapshot = (self.root / 'sources/Extra.lpx').read_bytes()
        self.assertEqual(snapshot, self.resources[extra['url']])
        self.assertIn(b'unrelated.js', snapshot)
        self.assertIn(b'DOMAIN, other.test, REJECT', snapshot)
        manifest = json.loads((self.root / 'dependencies.json').read_text())
        self.assertIn('https://test.invalid/selected.js', manifest)
        self.assertIn('https://test.invalid/unrelated.js', manifest)

    def test_curated_extra_entries_are_rejected(self):
        extra = {'file': 'Splash.lpx', 'name': 'Splash', 'url': 'https://test.invalid/full.lpx',
                 'select': {'rewrite': [r'^https:\/\/app\.test\/splash\?']}, 'mitm': ['app.test']}
        (self.root / 'extra-plugins.json').write_text(json.dumps([extra]), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'rejects curated extras'):
            fetcher.selected_plugins('[Plugin]\nhttps://test.invalid/demo.lpx, enabled=true\n', root=self.root)


if __name__ == '__main__':
    unittest.main()
