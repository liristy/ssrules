"""Exercise the workflow's Git staging and config guard in a disposable repo."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
import yaml


PROJECT = Path(__file__).resolve().parent.parent
WORKFLOW = yaml.safe_load((PROJECT / '.github/workflows/update-stash-plugins.yml').read_text(encoding='utf-8'))
STEPS = WORKFLOW['jobs']['update']['steps']


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        # The Windows system32 bash launcher targets WSL, not the Windows repo.
        candidate = Path('C:/Program Files/Git/bin/bash.exe')
        self.bash = str(candidate) if os.name == 'nt' and candidate.is_file() else shutil.which('bash')
        if not self.bash or not shutil.which('git'):
            self.skipTest('Git and Bash are required for workflow integration tests')
        self.temp = tempfile.TemporaryDirectory(prefix='ssrules-workflow-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.generated = ['stash_plugins.stoverride', 'stash-plugins/sources/demo.lpx',
                          'stash-plugins/scripts/old.js', 'stash-plugins/runtime/old.js',
                          *['stash-plugins/' + name + '.json' for name in
                            ['dependencies', 'refresh', 'report', 'locations']]]
        self.manual = ['README.md', 'stash_override.js', 'stash_plugins.js',
                       'stash-plugins/README.md', 'stash-plugins/focus-policy.json']
        for name in self.generated + self.manual:
            self.write(name, 'original\n')
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Workflow Test', '-c', 'user.email=test@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True,
                              capture_output=True, text=True).stdout

    def test_commit_only_stages_generated_files_including_additions_and_deletions(self):
        for name in self.generated + self.manual:
            self.write(name, 'updated\n')
        (self.root / 'stash-plugins/scripts/old.js').unlink()
        self.write('stash-plugins/runtime/new.js', 'new runtime\n')
        self.write('stash-plugins/validation-input.json', 'temporary\n')
        script = next(step['run'] for step in STEPS if step['name'] == 'Commit changed snapshots and generated files')
        staging = '\n'.join(line for line in script.splitlines() if line.strip().startswith('git add '))
        subprocess.run([self.bash, '-e', '-c', staging], cwd=self.root, check=True, capture_output=True)
        staged = set(self.git('diff', '--cached', '--name-only').splitlines())
        self.assertEqual(staged, set(self.generated) | {'stash-plugins/runtime/new.js'})
        self.assertEqual(self.git('diff', '--cached', '--diff-filter=D', '--name-only').strip(),
                         'stash-plugins/scripts/old.js')

    def test_guard_stops_publication_when_main_configuration_is_modified(self):
        script = next(step['run'] for step in STEPS if step['name'] == 'Verify hand-maintained configuration was not changed')
        def run_guard():
            return subprocess.run([self.bash, '-e', '-c', script], cwd=self.root, capture_output=True)
        self.write('stash_plugins.stoverride', 'generated update\n')
        self.assertEqual(run_guard().returncode, 0)
        for name in ['stash_override.js', 'stash_plugins.js', 'stash-plugins/focus-policy.json']:
            with self.subTest(path=name):
                self.write(name, 'unexpected change\n')
                self.assertNotEqual(run_guard().returncode, 0)
                self.write(name, 'original\n')


if __name__ == '__main__':
    unittest.main()
