"""Unselected upstream syntax must not block publication of reviewed rules."""
import unittest
from unittest.mock import patch

from build import Builder
from focus import keep_entry


class RewriteScopeTests(unittest.TestCase):
    pattern = r'^https?:\/\/appconf\.mail\.163\.com\/mailmaster\/api\/http\/urlConfig\.do$'

    def builder(self):
        builder = Builder()
        builder.source = 'Remove_ads_by_keli.lpx'
        builder.line = 42
        return builder

    def conditional(self):
        return 'request if ${url} ~= /' + self.pattern + '/i then reject_dict(200)'

    def test_actual_mail_conditional_is_excluded(self):
        builder = self.builder()
        builder.rewrite(self.conditional())
        row = builder.data['http']['url-rewrite'][0]
        self.assertEqual(row, '(?i)' + self.pattern + ' - reject-dict')
        self.assertFalse(keep_entry('url-rewrite', row, builder.source))

    def test_selected_conditional_still_fails(self):
        builder = self.builder()
        with patch.dict('build.POLICY', {builder.source: {'rewrite': [self.pattern]}}):
            with self.assertRaisesRegex(ValueError, 'Remove_ads_by_keli.lpx:42'):
                builder.rewrite(self.conditional().replace('reject_dict(200)', 'future_action()'))

    def test_redirect_preserves_status_target_and_case_insensitivity(self):
        builder = self.builder()
        builder.rewrite(self.conditional().replace('reject_dict(200)', 'redirect(307, "https://www.google.com")'))
        row = builder.data['http']['url-rewrite'][0]
        self.assertEqual(row, '(?i)' + self.pattern + ' https://www.google.com 307')
        import re
        self.assertIsNotNone(re.search(row.split()[0], 'HTTPS://APPCONF.MAIL.163.COM/mailmaster/api/http/urlConfig.do'))

    def test_http_200_rejection_keeps_status(self):
        builder = self.builder()
        builder.rewrite(self.conditional().replace('reject_dict(200)', 'reject(200)'))
        self.assertTrue(builder.data['http']['url-rewrite'][0].endswith(' - reject-200'))

    def test_unsupported_unselected_conditional_is_recorded(self):
        builder = self.builder()
        builder.rewrite(self.conditional().replace('reject_dict(200)', 'future_action()'))
        self.assertEqual(builder.data['http']['url-rewrite'], [])
        self.assertEqual(builder.notes[0]['source'], builder.source)

    def test_ambiguous_conditional_still_fails(self):
        with self.assertRaises(ValueError):
            self.builder().rewrite('request if ${method} == GET then reject_dict(200)')

    def test_unknown_action_only_skipped_outside_scope(self):
        builder = self.builder()
        builder.rewrite(self.pattern + ' future-action')
        with patch.dict('build.POLICY', {builder.source: {'rewrite': [self.pattern]}}):
            with self.assertRaisesRegex(ValueError, 'Unrecognized selected rewrite'):
                builder.rewrite(self.pattern + ' future-action')

    def test_supported_rewrite_remains_in_validation_data(self):
        builder = self.builder()
        builder.rewrite(self.pattern + ' reject-dict')
        self.assertEqual(builder.data['http']['url-rewrite'], [self.pattern + ' - reject-dict'])

    def test_script_preserves_arguments_and_binary_response_options(self):
        builder = self.builder()
        builder.defaults = {'captionLang': 'off', 'blockUpload': False}
        with patch.object(builder, 'provider', return_value='youtube'):
            builder.rewrite('response if ${url} ~= /' + self.pattern + '/i then '
                            'script("https://test.invalid/youtube.js", {${captionLang}, ${blockUpload}}) '
                            'with tag="YouTube", requires_body=true, binary_body_mode=true')
        entry = builder.data['http']['script'][0]
        self.assertEqual(entry['type'], 'response')
        self.assertTrue(entry['binary-mode'])
        self.assertTrue(entry['require-body'])
        import json
        self.assertEqual(json.loads(entry['argument']), {'captionLang': 'off', 'blockUpload': False})

    def test_json_mock_and_jq_unescape_quoted_values(self):
        import json
        builder = self.builder()
        prefix = 'response if ${url} ~= /' + self.pattern + '/i then '
        builder.rewrite(prefix + r'response.body.mock("json", "{\"ads\":[]}")')
        self.assertEqual(json.loads(builder.data['http']['mock'][0]['text']), {'ads': []})
        builder.rewrite(prefix + r'response.json.jq("del(.ads) | .name = \"keep\"")')
        self.assertTrue(builder.data['http']['body-rewrite'][0].endswith('del(.ads) | .name = "keep"'))


if __name__ == '__main__':
    unittest.main()
