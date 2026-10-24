"""Full import keeps upstream scripts byte-for-byte (before Stash runtime wrapper)."""
import unittest
from focus import trim_script

class FullSourceTests(unittest.TestCase):
    url = 'https://raw.githubusercontent.com/kokoryh/Script/master/js/12306.js'

    def test_original_source_is_not_trimmed(self):
        upstream = '!function(){ if (placementNo === "0007") responseOne(); if (placementNo === "G0054") responseTwo(); }();'
        self.assertEqual(trim_script(self.url, upstream), upstream)

    def test_edited_source_is_not_silently_reverted_to_old_splash_filter(self):
        source = 'console.log("12306 upstream changed");'
        self.assertEqual(trim_script(self.url, source), source)

if __name__ == '__main__':
    unittest.main()
