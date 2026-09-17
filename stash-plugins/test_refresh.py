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

    def test_fmz200_is_excluded_even_when_enabled_in_loon(self):
        selected = fetcher.enabled_plugins(
            '[Plugin]\nhttps://test.invalid/demo.lpx, enabled=true\n'
            'https://raw.githubusercontent.com/fmz200/wool_scripts/main/Loon/plugin/blockAds.plugin, enabled=true\n')
        self.assertEqual(selected, [('https://test.invalid/demo.lpx', 'demo.lpx')])

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

    def test_extra_excerpt_downloads_only_selected_script_dependencies(self):
        extra = {'file': 'Extra.lpx', 'name': 'Selected app', 'url': 'https://test.invalid/aggregate.plugin',
                 'select': {'script': [r'^https://selected\.test/'], 'rule': ['DOMAIN,ads.selected.test,REJECT']}, 'mitm': ['selected.test']}
        (self.root / 'extra-plugins.json').write_text(json.dumps([extra]), encoding='utf-8')
        self.resources[extra['url']] = (
            '[Script]\nhttp-response ^https://selected\\.test/ script-path=https://test.invalid/selected.js, requires-body=true\n'
            'http-response ^https://unrelated.test/ script-path=https://test.invalid/unrelated.js\n'
            '[Rule]\nDOMAIN, ads.selected.test, REJECT\nDOMAIN, other.test, REJECT\n').encode()
        self.resources['https://test.invalid/selected.js'] = b'$done({});\n'
        self.run_refresh()
        snapshot = (self.root / 'sources/Extra.lpx').read_text()
        self.assertIn('selected.js', snapshot)
        self.assertNotIn('unrelated', snapshot)
        self.assertIn('DOMAIN, ads.selected.test, REJECT', snapshot)
        self.assertNotIn('other.test', snapshot)
        manifest = json.loads((self.root / 'dependencies.json').read_text())
        self.assertIn('https://test.invalid/selected.js', manifest)
        self.assertNotIn('https://test.invalid/unrelated.js', manifest)
        self.assertFalse((self.root / 'sources/aggregate.plugin').exists())


if __name__ == '__main__':
    unittest.main()
