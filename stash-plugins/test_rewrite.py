"""Validate full-scope rewrite conversion and fail-closed handling of unknown syntax."""
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

    def test_actual_mail_conditional_is_included(self):
        builder = self.builder()
        builder.rewrite(self.conditional())
        row = builder.data['http']['url-rewrite'][0]
        self.assertEqual(row, '(?i)' + self.pattern + ' - reject-dict')
        self.assertTrue(keep_entry('url-rewrite', row, builder.source))

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

    def test_unsupported_full_scope_conditional_fails_closed(self):
        builder = self.builder()
        with self.assertRaisesRegex(ValueError, 'Unsupported selected conditional rewrite'):
            builder.rewrite(self.conditional().replace('reject_dict(200)', 'future_action()'))

    def test_ambiguous_conditional_still_fails(self):
        with self.assertRaises(ValueError):
            self.builder().rewrite('request if ${method} == GET then reject_dict(200)')

    def test_unknown_action_fails_closed_in_full_mode(self):
        builder = self.builder()
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

    def test_amap_large_delete_list_and_digit_prefixed_key(self):
        """Stash must never receive invalid data.920bestwishes or an enormous expression."""
        import json
        import jq
        from build import STASH_JSON_DEL_MAX_PATHS, STASH_NATIVE_JSON_PATH

        paths = [f'data.adItem{i}' for i in range(26)]
        paths += ['data.920bestwishes', 'data.custom_consultdata.widget_guide',
                  'data.free_ride', 'data.wallet']
        builder = self.builder()
        builder.source = 'Amap_remove_ads.lpx'
        action = 'response.json.delete(' + json.dumps(paths, ensure_ascii=False) + ')'
        builder.rewrite('response if ${url} ~= /' + self.pattern + '/i then ' + action)
        entries = builder.data['http']['body-rewrite']
        native_paths = []
        for rule in entries:
            if ' response-json-del ' in rule:
                native = rule.split(' response-json-del ', 1)[1].split()
                self.assertLessEqual(len(native), STASH_JSON_DEL_MAX_PATHS)
                self.assertTrue(all(STASH_NATIVE_JSON_PATH.fullmatch(p) for p in native))
                native_paths += native
        self.assertEqual(native_paths, [p for p in paths if p != 'data.920bestwishes'])
        jq_rules = [rule.split(' response-jq ', 1)[1] for rule in entries if ' response-jq ' in rule]
        self.assertEqual(jq_rules, ['del(.data["920bestwishes"])'])
        obj = {'data': {'920bestwishes': {'ad': 1}, 'wallet': 1, 'untouched': 123}}
        self.assertEqual(jq.compile(jq_rules[0]).input(obj).first()['data'],
                         {'wallet': 1, 'untouched': 123})
        self.assertTrue(all('data.920bestwishes' not in rule for rule in entries))

    def test_loon_jsonpath_root_normalization(self):
        from build import normalize_json_path
        builder = self.builder()
        builder.rewrite(
            'response if ${url} ~= /' + self.pattern + '/i then '
            'response.json.delete("$.data.shadingWords")'
        )
        self.assertEqual(
            builder.data['http']['body-rewrite'][0],
            '(?i)' + self.pattern + ' response-json-del data.shadingWords')
        self.assertEqual(normalize_json_path('$.data.name'), 'data.name')

    def test_reject_unrepresentable_stash_json_path(self):
        builder = self.builder()
        with self.assertRaisesRegex(ValueError, 'Unsupported upstream JSON deletion path'):
            builder.rewrite(
                'response if ${url} ~= /' + self.pattern + '/i then '
                'response.json.delete("data.invalid-key")')

    def test_json_mock_and_jq_unescape_quoted_values(self):
        import json
        builder = self.builder()
        prefix = 'response if ${url} ~= /' + self.pattern + '/i then '
        builder.rewrite(prefix + r'response.body.mock("json", "{\"ads\":[]}")')
        self.assertEqual(json.loads(builder.data['http']['mock'][0]['text']), {'ads': []})
        builder.rewrite(prefix + r'response.json.jq("del(.ads) | .name = \"keep\"")')
        self.assertTrue(builder.data['http']['body-rewrite'][0].endswith('del(.ads) | .name = "keep"'))

    def test_binary_grpc_mock_preserves_base64_payload(self):
        import base64
        builder = self.builder()
        source = b'\0\0\0\0\x03\x08\x01'
        encoded = base64.b64encode(source).decode()
        line = ('response if ${url} ~= /' + self.pattern + '/i then '
                'response.body.mock("text", "' + encoded + '", 200, true)')
        builder.rewrite(line)
        value = builder.data['http']['mock'][0]
        self.assertEqual(base64.b64decode(value['base64']), source)
        self.assertEqual(value['status-code'], 200)
        self.assertEqual(value['headers']['Content-Type'], 'application/grpc')

    def test_text_mock_with_explicit_200_keeps_upstream_cache_reset(self):
        import json
        builder = self.builder()
        builder.source = 'Bilibili_splash.lpx'
        pattern = r'^https:\/\/app\.bilibili\.com\/x\/v2\/splash\/list\?'
        builder.rewrite('response if ${url} ~= /' + pattern + '/i then '
                        r'response.body.mock("text", "{\"code\":0,\"data\":{\"keep_ids\":[],\"list\":[{}],\"max_time\":0}}", 200)')
        mock = builder.data['http']['mock'][0]
        self.assertEqual(mock['status-code'], 200)
        self.assertEqual(json.loads(mock['text'])['data']['keep_ids'], [])
        self.assertTrue(keep_entry('mock', mock, builder.source))
        import re
        self.assertIsNotNone(re.search(mock['match'], 'https://app.bilibili.com/x/v2/splash/list?appkey=1'))
        self.assertIsNone(re.search(mock['match'], 'https://app.bilibili.com/x/v2/splash/brand/list?appkey=1'))
        self.assertIsNone(re.search(mock['match'], 'https://app.bilibili.com/x/v2/splash/list_extra'))


if __name__ == '__main__':
    unittest.main()
