import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import manage


class PackageInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.package = base / "package"
        self.target = base / "codex-home"
        self.package.mkdir()
        (self.package / "skills" / "adaptive-agent-orchestrator").mkdir(parents=True)
        (self.package / "skills" / "astra-orchestrator").mkdir()
        role_root = self.package / "profiles" / "adaptive" / "codex" / "agents"
        role_root.mkdir(parents=True)
        (self.package / "distribution.json").write_text(json.dumps({"schema": 1, "include": ["skills", "profiles", "distribution.json"], "directory_extensions": {"skills": [".md"], "profiles": [".toml"]}}))
        for profile in manage.PROFILES:
            profile_root = self.package / "profiles" / profile
            profile_root.mkdir(exist_ok=True)
            (profile_root / "codex").mkdir(exist_ok=True)
            (profile_root / "profile.toml").write_text(f'schema = 1\nname = "{profile}"\nroles = "profiles/adaptive/codex/agents"\nconfig = "profiles/{profile}/codex/config.toml"\n')
            (profile_root / "codex" / "config.toml").write_text('[agents]\nmax_concurrent_threads_per_session = 2\n')
        for name in manage.SKILLS:
            (self.package / "skills" / name / "SKILL.md").write_text(f"skill={name}\n")
        for n in range(8):
            (role_root / f"ao_test{n}.toml").write_text(f"role={n}\n")
        self.manifest = self.package / "release-manifest.json"
        self._refresh_manifest()
        self.old_root, self.old_manifest = manage.ROOT, manage.MANIFEST
        manage.ROOT, manage.MANIFEST = self.package, self.manifest
        self.addCleanup(self._restore_globals)

    def _restore_globals(self):
        manage.ROOT, manage.MANIFEST = self.old_root, self.old_manifest

    def _refresh_manifest(self):
        entries = {}
        for path in self.package.rglob("*"):
            if path.is_file() and path.name != "release-manifest.json":
                entries[path.relative_to(self.package).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps({"schema": 1, "version": "test", "files": entries}))

    def _args(self, **kwargs):
        defaults = dict(target=str(self.target), skill="both", parts="all", replace=False, force=False)
        defaults.update(kwargs)
        return type("Args", (), defaults)()

    def test_install_doctor_and_uninstall_preserve_unrelated_data(self):
        self.target.mkdir()
        config = self.target / "config.toml"
        config.write_text("model = 'user-choice'\n")
        unrelated = self.target / "skills" / "my-own-skill" / "SKILL.md"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("keep me\n")
        manage.install(self._args())
        with contextlib.redirect_stdout(io.StringIO()):
            manage.doctor(self._args())
            manage.uninstall(self._args())
        self.assertEqual(config.read_text(), "model = 'user-choice'\n")
        self.assertEqual(unrelated.read_text(), "keep me\n")
        self.assertFalse((self.target / "skills" / manage.SKILLS[0]).exists())
        self.assertEqual(json.loads((self.target / manage.STATE_DIR / "install.json").read_text())["components"], {})

    def test_conflicts_stop_then_replace_is_backed_up(self):
        dest = self.target / "skills" / manage.SKILLS[0]
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("user version\n")
        with self.assertRaisesRegex(RuntimeError, "Different existing component"):
            manage.install(self._args(parts="skills", skill=manage.SKILLS[0]))
        self.assertEqual((dest / "SKILL.md").read_text(), "user version\n")
        manage.install(self._args(parts="skills", skill=manage.SKILLS[0], replace=True))
        self.assertEqual((dest / "SKILL.md").read_text(), f"skill={manage.SKILLS[0]}\n")
        backups = list((self.target / ".adaptive-agent-orchestrator-backups").glob("*/skills/*/SKILL.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "user version\n")
        install_backup = backups[0].parents[2]
        manage.restore(type("Args", (), {"target": str(self.target), "backup_id": install_backup.name})())
        self.assertEqual((dest / "SKILL.md").read_text(), "user version\n")
        self.assertNotIn(f"skills/{manage.SKILLS[0]}", manage.load_state(self.target)["components"])

    def test_modified_managed_content_requires_explicit_forced_uninstall(self):
        manage.install(self._args(parts="skills", skill=manage.SKILLS[0]))
        file = self.target / "skills" / manage.SKILLS[0] / "SKILL.md"
        file.write_text("local edit\n")
        with self.assertRaisesRegex(RuntimeError, "Modified installed components"):
            manage.uninstall(self._args())
        manage.uninstall(self._args(force=True))
        backups = list((self.target / ".adaptive-agent-orchestrator-backups").glob("uninstall-*/skills/*/SKILL.md"))
        self.assertEqual(backups[0].read_text(), "local edit\n")

    def test_tampered_package_is_rejected(self):
        (self.package / "skills" / "astra-orchestrator" / "SKILL.md").write_text("tampered\n")
        with self.assertRaisesRegex(RuntimeError, "integrity check failed"):
            manage.install(self._args())

    def test_restore_reinstates_uninstalled_component_and_doctor_tracks_it(self):
        manage.install(self._args(parts="skills", skill=manage.SKILLS[0]))
        manage.uninstall(self._args())
        backup = next((self.target / ".adaptive-agent-orchestrator-backups").glob("uninstall-*"))
        manage.restore(type("Args", (), {"target": str(self.target), "backup_id": backup.name})())
        with contextlib.redirect_stdout(io.StringIO()):
            manage.doctor(self._args())
        self.assertTrue((self.target / "skills" / manage.SKILLS[0] / "SKILL.md").is_file())

    def test_named_profile_lifecycle_preserves_base_config(self):
        self.target.mkdir()
        (self.target / 'config.toml').write_text('model = "user-choice"\n')
        manage.install(self._args(profile='adaptive-max-2-subagents', with_profile_config=True))
        preset = self.target / 'adaptive-max-2-subagents.config.toml'
        self.assertTrue(preset.is_file())
        manage.uninstall(self._args())
        self.assertFalse(preset.exists())
        backup = next((self.target / '.adaptive-agent-orchestrator-backups').glob('uninstall-*'))
        manage.restore(type('Args', (), {'target': str(self.target), 'backup_id': backup.name})())
        self.assertTrue(preset.is_file())
        manage.doctor(self._args())
        self.assertEqual((self.target / 'config.toml').read_text(), 'model = "user-choice"\n')

    def test_profile_config_is_opt_in(self):
        manage.install(self._args())
        self.assertFalse((self.target / 'adaptive.config.toml').exists())

    def test_tampered_receipt_cannot_escape_target(self):
        manage.install(self._args(parts='skills', skill=manage.SKILLS[0]))
        outside = self.target.parent / 'outside'
        outside.write_text('preserve')
        receipt = self.target / manage.STATE_DIR / 'install.json'
        receipt.write_text(json.dumps({'schema': 1, 'components': {'../outside': manage.digest(outside)}}))
        with self.assertRaisesRegex(RuntimeError, 'Unsafe managed'):
            manage.uninstall(self._args())
        self.assertEqual(outside.read_text(), 'preserve')
        with self.assertRaisesRegex(RuntimeError, 'traversal'):
            manage.ensure_safe_path(self.target, self.target / '..' / 'outside')

    def test_uninstall_rolls_back_if_receipt_commit_fails(self):
        manage.install(self._args())
        original_receipt = (self.target / manage.STATE_DIR / 'install.json').read_bytes()
        original_write = manage.write_json
        def fail_state(path, value):
            if path.name == 'install.json':
                raise OSError('injected receipt failure')
            return original_write(path, value)
        with patch.object(manage, 'write_json', side_effect=fail_state):
            with self.assertRaisesRegex(OSError, 'injected'):
                manage.uninstall(self._args())
        self.assertEqual((self.target / manage.STATE_DIR / 'install.json').read_bytes(), original_receipt)
        manage.doctor(self._args())

    def test_restore_rolls_back_second_component_rename_failure(self):
        manage.install(self._args())
        manage.uninstall(self._args())
        backup = next((self.target / '.adaptive-agent-orchestrator-backups').glob('uninstall-*'))
        manage.install(self._args())
        current = self.target / 'skills' / manage.SKILLS[0] / 'SKILL.md'
        current.write_text('newer current version')
        updated_state = manage.load_state(self.target)
        updated_state['components'][f'skills/{manage.SKILLS[0]}'] = manage.tree_hash(current.parent)
        manage.write_json(self.target / manage.STATE_DIR / 'install.json', updated_state)
        before = manage.load_state(self.target)
        original_replace = manage.os.replace
        replacements = 0
        def fail_second(source, dest):
            nonlocal replacements
            if '.ao-restore-' in str(source):
                replacements += 1
                if replacements == 2:
                    raise OSError('injected rename failure')
            return original_replace(source, dest)
        with patch.object(manage.os, 'replace', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'injected'):
                manage.restore(type('Args', (), {'target': str(self.target), 'backup_id': backup.name})())
        self.assertEqual(manage.load_state(self.target), before)
        self.assertEqual(current.read_text(), 'newer current version')
        manage.doctor(self._args())

    def test_install_replacement_rolls_back_failed_rename(self):
        dest = self.target / 'skills' / manage.SKILLS[0]
        dest.mkdir(parents=True)
        (dest / 'SKILL.md').write_text('previous content')
        original_replace = manage.os.replace
        def fail_stage(source, target):
            if '.ao-stage-' in str(source):
                raise OSError('injected install rename failure')
            return original_replace(source, target)
        with patch.object(manage.os, 'replace', side_effect=fail_stage):
            with self.assertRaisesRegex(OSError, 'injected'):
                manage.install(self._args(parts='skills', skill=manage.SKILLS[0], replace=True))
        self.assertEqual((dest / 'SKILL.md').read_text(), 'previous content')


if __name__ == "__main__":
    unittest.main()
