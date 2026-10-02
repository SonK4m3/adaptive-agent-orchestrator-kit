"""Release checks/handoffs use fixture network responses, never paid model calls."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update
from package_layout import distribution_files


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.tag = (ROOT / 'VERSION').read_text().strip()
        self.info = {'source_version': '1.0.0', 'release_tag': self.tag, 'update_available': True,
                     'release_notes': f'https://github.com/{update.REPO}/releases/tag/{self.tag}',
                     'archive_url': f'https://codeload.github.com/{update.REPO}/zip/refs/tags/{self.tag}'}

    def source_zip(self, changes=None):
        files = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in distribution_files(ROOT)}
        manifest = {'schema': 1, 'version': self.tag,
                    'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
        files['release-manifest.json'] = (json.dumps(manifest) + '\n').encode()
        files.update(changes or {})
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as bundle:
            for name, data in files.items():
                if data is not None:
                    bundle.writestr('source-root/' + name, data)
        return out.getvalue()

    def write_archive(self, data):
        archive = self.base / 'source.zip'
        archive.write_bytes(data)
        return archive

    def test_numeric_stable_versions(self):
        self.assertGreater(update.version('v2.10.0'), update.version('2.9.99'))
        self.assertEqual(update.version('v2.2.0'), update.version('2.2.0'))
        for value in ('2.2', '2.2.0-beta', '02.2.0', '../2.2.0', '2.2.0\n', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                update.version(value)

    def test_check_compares_source_not_project_receipt(self):
        (self.base / 'VERSION').write_text('1.9.9')
        metadata = {'draft': False, 'prerelease': False, 'tag_name': 'v2.0.0',
                    'html_url': 'https://evil.invalid/', 'zipball_url': 'https://evil.invalid/'}
        with patch.object(update, 'fetch', return_value=json.dumps(metadata).encode()):
            result = update.check(self.base)
        self.assertTrue(result['update_available'])
        self.assertTrue(result['archive_url'].startswith('https://codeload.github.com/' + update.REPO))
        self.assertEqual(result['source_version'], '1.9.9')

    def test_equal_or_older_release_not_update(self):
        (self.base / 'VERSION').write_text('2.0.0')
        for tag in ('2.0.0', 'v1.99.99'):
            with patch.object(update, 'fetch', return_value=json.dumps({'draft': False, 'prerelease': False, 'tag_name': tag}).encode()):
                self.assertFalse(update.check(self.base)['update_available'])

    def test_missing_source_version_fails_before_network(self):
        with patch.object(update, 'fetch') as network, self.assertRaises(OSError):
            update.check(self.base)
        network.assert_not_called()

    def test_invalid_release_metadata(self):
        for data in ([], {}, {'draft': True, 'prerelease': False, 'tag_name': '2.0.0'},
                     {'draft': False, 'prerelease': True, 'tag_name': '2.0.0'},
                     {'draft': False, 'prerelease': False, 'tag_name': 'latest'}):
            (self.base / 'VERSION').write_text('1.0.0')
            with patch.object(update, 'fetch', return_value=json.dumps(data).encode()), self.assertRaises(ValueError):
                update.check(self.base)

    def test_automatic_check_failure_continues_local(self):
        with patch.object(update, 'check', side_effect=OSError('offline')), patch.object(update, 'handoff') as handoff:
            self.assertIsNone(update.automatic())
        handoff.assert_not_called()

    def test_automatic_decline_continues_local(self):
        with patch.object(update, 'check', return_value=self.info), patch('builtins.input', return_value=''), patch.object(update, 'handoff') as handoff:
            self.assertIsNone(update.automatic())
        handoff.assert_not_called()

    def test_automatic_handoff_failure_no_fallback(self):
        with patch.object(update, 'check', return_value=self.info), patch('builtins.input', return_value='y'), patch.object(update, 'handoff', side_effect=ValueError('bad archive')):
            self.assertEqual(update.automatic(), 1)

    def test_check_only_and_json_never_download(self):
        with patch.object(update, 'check', return_value=self.info), patch.object(update, 'handoff') as handoff:
            self.assertEqual(update.main(['--check', '--json']), 0)
        handoff.assert_not_called()

    def test_explicit_failure_nonzero(self):
        with patch.object(update, 'check', side_effect=OSError('offline')):
            self.assertEqual(update.main(['--check']), 1)

    def test_offline_does_not_check(self):
        with patch.object(update, 'check') as network:
            self.assertEqual(update.main(['--offline']), 0)
        network.assert_not_called()

    def test_download_confirmation_empty_or_eof_no_download(self):
        for answer in ('', EOFError()):
            kwargs = {'side_effect': answer} if isinstance(answer, Exception) else {'return_value': answer}
            with patch('builtins.input', **kwargs), patch.object(update, 'fetch') as network:
                self.assertEqual(update.handoff(self.info), 0)
            network.assert_not_called()

    def test_safe_archive_matches_version_and_manifest(self):
        source = update.extract(self.write_archive(self.source_zip()), self.base / 'extract', self.tag)
        self.assertTrue((source / 'scripts/setup.py').is_file())
        self.assertEqual(len(list((source / 'profiles/adaptive/codex/agents').glob('*.toml'))), 8)

    def test_bad_manifest_version_layout_or_hash_rejected(self):
        for changes in ({'VERSION': b'0.0.1'}, {'scripts/setup.py': None},
                        {'scripts/setup.py': b'changed'}, {'release-manifest.json': b'{}'},
                        {'profiles/adaptive/codex/agents/ao_worker.toml': None}):
            with self.subTest(changes=changes):
                destination = self.base / 'extract'
                with self.assertRaises((ValueError, OSError)):
                    update.extract(self.write_archive(self.source_zip(changes)), destination, self.tag)
                if destination.exists():
                    shutil.rmtree(destination)

    def test_dangerous_archive_paths_rejected_before_writes(self):
        names = ('../escape', '/absolute', 'root/../escape', 'root/a\\b', 'root/C:/x',
                 'root/NUL.txt', 'root/file.', 'root/file ', 'root/a//b', 'root/a\x00b')
        for name in names:
            # zipfile truncates NUL names on writing, so test the validator directly.
            with self.subTest(name=name), self.assertRaises(ValueError):
                update.safe_parts(name)
        for name in names[:-1]:
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as bundle:
                bundle.writestr(name, b'bad')
            with zipfile.ZipFile(io.BytesIO(out.getvalue())) as bundle:
                if bundle.infolist()[0].filename != name:
                    continue  # Python may canonicalize names when constructing fixtures.
            destination = self.base / 'extract'
            with self.assertRaises(ValueError):
                update.extract(self.write_archive(out.getvalue()), destination, self.tag)
            self.assertFalse(destination.exists())

    def test_links_and_special_types_rejected_before_writes(self):
        for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFSOCK):
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as bundle:
                entry = zipfile.ZipInfo('root/link')
                entry.create_system = 3
                entry.external_attr = (kind | 0o777) << 16
                bundle.writestr(entry, b'target')
            destination = self.base / 'extract'
            with self.assertRaises(ValueError):
                update.extract(self.write_archive(out.getvalue()), destination, self.tag)
            self.assertFalse(destination.exists())

    def test_windows_collisions_and_multiple_roots_rejected(self):
        for names in (('root/A', 'root/a'), ('root/A/x', 'root/a/y'),
                      ('root/a', 'root/a/x'), ('root/a', 'other/b')):
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as bundle:
                for name in names:
                    bundle.writestr(name, b'x')
            with self.assertRaises(ValueError):
                update.extract(self.write_archive(out.getvalue()), self.base / 'extract', self.tag)
            self.assertFalse((self.base / 'extract').exists())

    def test_size_limit_rejected(self):
        data = self.source_zip()
        with patch.object(update, 'MAX_EXPANDED', 1), self.assertRaises(ValueError):
            update.extract(self.write_archive(data), self.base / 'extract', self.tag)
        self.assertFalse((self.base / 'extract').exists())

    def test_execution_decline_cleans_scratch(self):
        captured = []
        real_extract = update.extract
        def capture(*args):
            result = real_extract(*args)
            captured.append(result)
            return result
        with patch('builtins.input', side_effect=['y', '']), patch.object(update, 'fetch', return_value=self.source_zip()), patch.object(update, 'extract', side_effect=capture), patch.object(update.subprocess, 'run') as run:
            self.assertEqual(update.handoff(self.info), 0)
        run.assert_not_called()
        self.assertFalse(captured[0].exists())

    def test_execution_handoff_guard_exit_and_cleanup(self):
        commands = []
        def execute(command, **kwargs):
            commands.append(command)
            self.assertTrue(Path(command[1]).is_file())
            return subprocess.CompletedProcess(command, 7)
        with patch('builtins.input', side_effect=['y', 'y']), patch.object(update, 'fetch', return_value=self.source_zip()), patch.object(update.subprocess, 'run', side_effect=execute):
            self.assertEqual(update.handoff(self.info), 7)
        self.assertEqual(commands[0][-1], '--skip-release-check')
        self.assertFalse(Path(commands[0][1]).exists())

    def test_stage_for_ai_never_executes_and_refuses_overwrite(self):
        staged = self.base / 'new source with spaces'
        with patch('builtins.input', return_value='y'), patch.object(update, 'fetch', return_value=self.source_zip()), patch.object(update.subprocess, 'run') as run:
            self.assertEqual(update.handoff(self.info, staged), 0)
            self.assertTrue((staged / 'VERSION').is_file())
            with self.assertRaises(ValueError):
                update.handoff(self.info, staged)
        run.assert_not_called()

    def test_invalid_download_never_executes(self):
        with patch('builtins.input', return_value='y'), patch.object(update, 'fetch', return_value=b'not zip'), patch.object(update.subprocess, 'run') as run:
            with self.assertRaises(zipfile.BadZipFile):
                update.handoff(self.info)
        run.assert_not_called()

    def test_recursion_guard_and_offline_skip_automatic(self):
        import setup
        # Stop at the first local prompt; the check must not run.
        for flag in ('--skip-release-check', '--offline'):
            with patch.object(update, 'automatic') as automatic, patch.object(setup, 'choose', side_effect=EOFError), self.assertRaises(EOFError):
                setup.main([flag])
            automatic.assert_not_called()

    def test_untrusted_url_and_redirect_refused(self):
        with self.assertRaises(ValueError):
            update.fetch('https://evil.invalid/archive', 100)
        with self.assertRaises(ValueError):
            update.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://evil.invalid')

    def test_network_response_limit_and_no_auth(self):
        class Response(io.BytesIO):
            status = 200
        class Opener:
            def open(inner, request, timeout):
                self.assertEqual(timeout, 10)
                self.assertFalse(request.has_header('Authorization'))
                return Response(b'x' * 11)
        with patch.object(update.urllib.request, 'build_opener', return_value=Opener()):
            with self.assertRaises(ValueError):
                update.fetch(update.API, 10)
            self.assertEqual(update.fetch(update.API, 11), b'x' * 11)

    def test_archive_failure_cleans_scratch(self):
        captured = []
        def failure(archive, destination, tag):
            captured.append(archive.parent)
            destination.mkdir()
            raise ValueError('incomplete')
        with patch('builtins.input', return_value='y'), patch.object(update, 'fetch', return_value=b'zip'), patch.object(update, 'extract', side_effect=failure), self.assertRaises(ValueError):
            update.handoff(self.info)
        self.assertFalse(captured[0].exists())

    def test_partial_stage_failure_removes_only_new_stage(self):
        destination = self.base / 'stage'
        keep = self.base / 'unrelated'
        keep.write_text('keep')
        with patch('builtins.input', return_value='y'), patch.object(update, 'fetch', return_value=self.source_zip()), patch.object(update.shutil, 'copytree', side_effect=OSError('copy failed')), self.assertRaises(OSError):
            update.handoff(self.info, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(keep.read_text(), 'keep')

    def test_fixture_handoff_runs_actual_child_installer_without_network_recursion(self):
        target = self.base / 'Codex home with spaces'
        target.mkdir()
        config = target / 'config.toml'
        config.write_text('model = "keep-root"\n')
        run_process = subprocess.run
        def actual_child(command, **kwargs):
            self.assertEqual(command[-1], '--skip-release-check')
            return run_process(command, input=f'2\n3\ny\nn\n{target}\n\n', text=True, capture_output=True, **kwargs)
        with patch('builtins.input', side_effect=['y', 'y']), patch.object(update, 'fetch', return_value=self.source_zip()), patch.object(update.subprocess, 'run', side_effect=actual_child):
            self.assertEqual(update.handoff(self.info), 0)
        self.assertEqual(config.read_text(), 'model = "keep-root"\n')
        self.assertEqual(len(list((target / 'agents').glob('ao_*.toml'))), 8)
        self.assertTrue((target / 'skills/adaptive-agent-orchestrator/SKILL.md').is_file())

    def test_powershell_wrapper_offline_and_syntax(self):
        pwsh = shutil.which('pwsh')
        if not pwsh:
            self.skipTest('PowerShell 7 unavailable')
        result = subprocess.run([pwsh, '-NoProfile', '-File', str(ROOT / 'update.ps1'), '-CheckOnly', '-Offline'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('skipped', result.stdout)
        # Invoke setup wrapper up to EOF: validates parsing/argument forwarding,
        # without continuing through install or changing a Codex home.
        result = subprocess.run([pwsh, '-NoProfile', '-File', str(ROOT / 'setup.ps1'), '-Offline'], input='', text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Setup cancelled', result.stderr)

    def test_windows_powershell_51_wrapper_offline(self):
        powershell = shutil.which('powershell')
        if not powershell:
            self.skipTest('Windows PowerShell unavailable')
        result = subprocess.run([powershell, '-NoProfile', '-File', str(ROOT / 'update.ps1'), '-CheckOnly', '-Offline'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('skipped', result.stdout)


if __name__ == '__main__':
    unittest.main()
