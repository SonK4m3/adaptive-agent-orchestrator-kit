"""Project steering registration preserves user bytes and never rewrites blocks."""
import codecs
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from register_project import START, END, register_project


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'project with spaces'
        self.project.mkdir()
        self.home = self.base / 'codex home'
        for name in ('adaptive-agent-orchestrator', 'astra-orchestrator'):
            source = self.home / 'skills' / name / 'SKILL.md'
            source.parent.mkdir(parents=True)
            source.write_text('installed skill')
        self.path = self.project / 'AGENTS.md'

    def test_append_preserves_existing_bytes_and_rerun_is_noop(self):
        original = '# Quy tắc riêng\r\n\r\nKhông đổi config.'.encode('utf-8')
        self.path.write_bytes(original)
        result = register_project(self.project, self.home)
        written = self.path.read_bytes()
        self.assertEqual(result['status'], 'appended')
        self.assertTrue(written.startswith(original))
        self.assertEqual(written.count(START.encode()), 1)
        self.assertTrue(written.endswith((END + '\r\n').encode()))
        self.assertIn('codex%20home', written.decode())
        self.assertNotIn('skills/astra-orchestrator/SKILL.md)', written.decode().split('codex%20home')[0])
        self.assertEqual(register_project(self.project, self.home)['status'], 'unchanged')
        self.assertEqual(self.path.read_bytes(), written)

    def test_missing_file_created_and_selected_skill_only(self):
        register_project(self.project, self.home, 'astra-orchestrator')
        content = self.path.read_text()
        self.assertIn('[astra-orchestrator]', content)
        self.assertNotIn('[adaptive-agent-orchestrator]', content)
        self.assertIn('root-only', content)

    def test_supported_bom_encodings_preserve_original_prefix(self):
        for bom, encoding in ((codecs.BOM_UTF8, 'utf-8'), (codecs.BOM_UTF16_LE, 'utf-16-le'), (codecs.BOM_UTF16_BE, 'utf-16-be')):
            with self.subTest(encoding=encoding):
                original = bom + '# Nội dung\r\n'.encode(encoding)
                self.path.write_bytes(original)
                register_project(self.project, self.home)
                written = self.path.read_bytes()
                self.assertTrue(written.startswith(original))
                self.assertEqual(register_project(self.project, self.home)['status'], 'unchanged')
                self.assertEqual(self.path.read_bytes(), written)

    def test_edited_block_refuses_overwrite_or_duplicate(self):
        register_project(self.project, self.home)
        self.path.write_bytes(self.path.read_bytes().replace(b'root-only', b'USER-EDIT'))
        original = self.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            register_project(self.project, self.home)
        self.assertEqual(self.path.read_bytes(), original)

    def test_malformed_marker_refuses_change(self):
        for content in (START, END, START + '\n' + END + '\n' + START):
            self.path.write_text(content)
            original = self.path.read_bytes()
            with self.assertRaises(RuntimeError):
                register_project(self.project, self.home)
            self.assertEqual(self.path.read_bytes(), original)

    def test_missing_installed_skill_does_not_touch_project(self):
        (self.home / 'skills/astra-orchestrator/SKILL.md').unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing'):
            register_project(self.project, self.home)
        self.assertFalse(self.path.exists())

    def test_invalid_encoding_is_not_rewritten(self):
        self.path.write_bytes(b'\xffPRIVATE')
        with self.assertRaises(UnicodeError):
            register_project(self.project, self.home)
        self.assertEqual(self.path.read_bytes(), b'\xffPRIVATE')

    def test_existing_lock_blocks_without_touching_user_file(self):
        self.path.write_text('keep')
        lock = self.project / '.AGENTS.md.orchestrator.lock'
        lock.write_text('another installer')
        with self.assertRaisesRegex(RuntimeError, 'lock'):
            register_project(self.project, self.home)
        self.assertEqual(self.path.read_text(), 'keep')
        self.assertTrue(lock.exists())

    def test_symlink_instructions_rejected(self):
        outside = self.base / 'outside.md'
        outside.write_text('keep')
        try:
            self.path.symlink_to(outside)
        except OSError:
            self.skipTest('Symlink creation unavailable on this Windows configuration')
        with self.assertRaises(RuntimeError):
            register_project(self.project, self.home)
        self.assertEqual(outside.read_text(), 'keep')

    def test_target_directory_must_exist(self):
        with self.assertRaisesRegex(RuntimeError, 'existing directory'):
            register_project(self.base / 'missing', self.home)


if __name__ == '__main__':
    unittest.main()
