"""Check the actual repository configuration through Sub-Store, without an iPhone."""
import json
from pathlib import Path
import re
import subprocess
import unittest

import yaml


ROOT = Path(__file__).resolve().parent.parent


def run_pipeline(config):
    fixture = {
        'base': config,
        'ads': yaml.safe_load((ROOT / 'stash_plugins.stoverride').read_text()),
        'hijacking': (ROOT / 'Rule/yaml/Hijacking_DNS.yaml').read_text(),
    }
    script = r"""
const fs = require('node:fs'), vm = require('node:vm');
const fixture = JSON.parse(fs.readFileSync(0, 'utf8'));
const base = fixture.base;
// Supply the actual Hijacking payload offline; the ad download is also a local fixture.
base['rule-providers'].Hijacking_DNS.payload = fixture.hijacking;
const c = vm.createContext({ProxyUtils: {
  yaml: {safeLoad: JSON.parse, safeDump: JSON.stringify},
  download: async url => {
    if (url !== 'https://raw.githubusercontent.com/liristy/ssrules/dev/stash_plugins.stoverride')
      throw new Error('Unexpected network request');
    return JSON.stringify(fixture.ads);
  },
}});
vm.runInContext(fs.readFileSync('stash_override.js', 'utf8'), c);
c.operator({$content: JSON.stringify(base)}).then(result => {
  process.stdout.write(result.$content);
}).catch(() => process.exit(1));
"""
    # Send an already parsed payload; Node's YAML interface is simulated with JSON.
    fixture['hijacking'] = yaml.safe_load(fixture['hijacking'])['payload']
    result = subprocess.run(['node', '-e', script], cwd=ROOT,
                            input=json.dumps(fixture), text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


class LocalDevVPNTests(unittest.TestCase):
    def test_actual_mihomo_input_and_advertising_patch(self):
        base = yaml.safe_load((ROOT / 'mihomo_config.yaml').read_text())
        result = run_pipeline(base)
        rule = 'IP-CIDR,10.7.0.1/32,SideStore-Local,no-resolve'
        self.assertEqual(result['rules'][0], rule)
        self.assertEqual(result['rules'].count(rule), 1)
        self.assertEqual(result['rules'][-1], base['rules'][-1])
        self.assertLess(result['rules'].index(rule), next(
            i for i, row in enumerate(result['rules']) if row.startswith('RULE-SET,Lan,')))
        self.assertEqual(result['proxies'][:-1], base.get('proxies', []))
        self.assertEqual(len(result['proxy-groups']), len(base['proxy-groups']))
        for group in result['proxy-groups']:
            if group.get('include-all'):
                self.assertTrue(group.get('filter'), 'include-all group needs a node filter')
                self.assertIsNone(re.search(group['filter'], 'SideStore-Local'))
        ads = yaml.safe_load((ROOT / 'stash_plugins.stoverride').read_text())
        self.assertEqual(result['http']['script'], ads['http']['script'])
        self.assertEqual(result['script-providers'], ads['script-providers'])

    def test_standalone_override_matches_the_script_output(self):
        base = yaml.safe_load((ROOT / 'mihomo_config.yaml').read_text())
        result = run_pipeline(base)
        patch = yaml.safe_load((ROOT / 'stash_localdevvpn.stoverride').read_text())
        self.assertEqual(patch['proxies'], result['proxies'][-1:])
        self.assertEqual(patch['rules'], result['rules'][:1])
        self.assertNotIn('dns', patch)
        self.assertNotIn('proxy-groups', patch)
        self.assertNotIn('http', patch)


if __name__ == '__main__':
    unittest.main()
