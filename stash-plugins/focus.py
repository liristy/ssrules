"""Full-import policy for the Stash development branch.

Only previously selected standalone plugins are imported whole; the full
fmz200 aggregate is excluded, and older targeted snippets remain scoped.
No application/function allowlist and no splash-only script trimming.
"""

PROFILE = 'all-enabled'
POLICY = {}  # Historical focus-policy.json is not used by this branch.
ZHIHU_COMMERCIAL = r'^https:\/\/api\.zhihu\.com\/commercial_api\/'
ZHIHU_SPLASH = ZHIHU_COMMERCIAL + r'(?:launch_v2|real_time_launch_v2)(?:\?|/|$)'


def keep_entry(section, entry, source):
    return True


def trim_script(url, script):
    return script


def splash_pattern(source, pattern):
    return pattern
