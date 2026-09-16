"""Ensure narrowing preserves supported URL hosts and abstains on unknown syntax."""
import unittest
from build import literal_url_hosts, narrow_mitm


class MitmNarrowingTests(unittest.TestCase):
    def test_literal_and_alternative_hosts(self):
        self.assertEqual(literal_url_hosts(r'^https:\/\/(?:info|m5)\.amap\.com\/ws/'),
                         ['info.amap.com', 'm5.amap.com'])
        self.assertEqual(literal_url_hosts(r'^https?://api\.weibo\.cn/2/'), ['api.weibo.cn'])

    def test_unknown_authority_is_preserved(self):
        for pattern in [r'^https://[\w-]+\.googlevideo\.com/', r'^https://api.weibo.cn/',
                        r'https://api\.weibo\.cn/', r'^https://api\.weibo\.cn(:443)?/',
                        r'^https://api\.weibo\.cn/feed|^https://other\.weibo\.cn/']:
            with self.subTest(pattern=pattern):
                self.assertIsNone(literal_url_hosts(pattern))
                entries = {'mitm': ['*.weibo.cn'], 'script': [{'match': pattern}]}
                self.assertEqual(narrow_mitm(entries), entries['mitm'])

    def test_all_processing_sections_and_exclusions(self):
        entries = {'mitm': ['-private.example.com', '*.example.com'],
                   'script': [{'match': r'^https://api\.example\.com/feed'}],
                   'url-rewrite': [r'^https://ads\.example\.com/ - reject'],
                   'body-rewrite': [r'^https://body\.example\.com/ response-jq .'],
                   'header-rewrite': [r'^https://headers\.example\.com/ request-del Test'],
                   'mock': [{'match': r'^https://mock\.example\.com/'}]}
        self.assertEqual(narrow_mitm(entries), ['-private.example.com', 'ads.example.com',
                         'api.example.com', 'body.example.com', 'headers.example.com', 'mock.example.com'])
        entries['rules'] = ['URL-REGEX,^https://other.example.com/,REJECT']
        self.assertEqual(narrow_mitm(entries), entries['mitm'])


if __name__ == '__main__':
    unittest.main()
