"""Guard the upstream-dependent 12306 splash branch extraction."""
import json
from pathlib import Path
import unittest

from focus import trim_script


class RailSplashTests(unittest.TestCase):
    url = 'https://raw.githubusercontent.com/kokoryh/Script/master/js/12306.js'

    def upstream(self):
        root = Path(__file__).parent
        manifest = json.loads((root / 'dependencies.json').read_text(encoding='utf-8'))
        return (root / manifest[self.url]['file']).read_text(encoding='utf-8')

    def test_extract_only_splash(self):
        result = trim_script(self.url, self.upstream())
        self.assertIn('"0007"', result)
        self.assertNotIn('G0054', result)
        self.assertIn('kokoryh/Script', result)

    def test_changed_or_ambiguous_branch_fails_build(self):
        source = self.upstream()
        for changed in [source.replace('0007', '0008'), source + source,
                        source.replace('skipTime', 'newTime')]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                trim_script(self.url, changed)


if __name__ == '__main__':
    unittest.main()
