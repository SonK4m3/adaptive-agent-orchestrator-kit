import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
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
        (self.package / "adaptive-agent-orchestrator").mkdir()
        (self.package / "astra-orchestrator").mkdir()
        (self.package / "roles").mkdir()
        for name in manage.SKILLS:
            (self.package / name / "SKILL.md").write_text(f"skill={name}\n")
        for n in range(8):
            (self.package / "roles" / f"ao_test{n}.toml").write_text(f"role={n}\n")
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
        (self.package / "astra-orchestrator" / "SKILL.md").write_text("tampered\n")
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


if __name__ == "__main__":
    unittest.main()
