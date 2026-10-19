"""Verify the extracted distribution, not only the developer checkout."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from package_layout import distribution_files


class ReleaseLifecycleTests(unittest.TestCase):
    def test_extracted_zip_lifecycle_and_explicit_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'source'
            source.mkdir()
            for path in distribution_files(ROOT):
                dest = source / path.relative_to(ROOT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
            (source / '.env').write_text('FAKE_PRIVATE_VALUE=excluded\n')
            (source / 'scripts/nested.env').write_text('FAKE_PRIVATE_VALUE=excluded\n')
            (source / 'profiles/adaptive/private.key').write_text('fake key excluded\n')
            self.run_cli(source / 'scripts/build_release.py')
            archive = source / 'dist/adaptive-agent-orchestrator-kit.zip'
            expected = archive.with_suffix('.zip.sha256').read_text().split()[0]
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), expected)
            extracted = base / 'extracted'
            with zipfile.ZipFile(archive) as bundle:
                self.assertFalse(any(name.endswith('/.env') for name in bundle.namelist()))
                self.assertFalse(any(name.endswith('nested.env') or name.endswith('private.key') for name in bundle.namelist()))
                bundle.extractall(extracted)
            package = extracted / 'adaptive-agent-orchestrator-kit'
            self.run_cli(package / 'scripts/validate_package.py')
            target = base / 'codex-home'
            target.mkdir()
            (target / 'config.toml').write_text('model = "keep-root"\n')
            unrelated = target / 'skills/my-skill/SKILL.md'
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text('keep\n')
            manager = package / 'scripts/manage.py'
            self.run_cli(manager, 'install', '--target', str(target), '--with-profile-config')
            self.run_cli(manager, 'doctor', '--target', str(target))
            project = base / 'consumer-project'
            project.mkdir()
            instructions = project / 'AGENTS.md'
            original = b'# Existing project rules\r\nDo not erase.\r\n'
            instructions.write_bytes(original)
            registration = package / 'scripts/register_project.py'
            self.run_cli(registration, '--project', str(project), '--target', str(target))
            appended = instructions.read_bytes()
            self.assertTrue(appended.startswith(original))
            self.run_cli(registration, '--project', str(project), '--target', str(target))
            self.assertEqual(instructions.read_bytes(), appended)
            self.assertTrue((package / 'skills/adaptive-orchestrator-setup/SKILL.md').is_file())
            local_project = base / 'project-local-consumer'
            local_project.mkdir()
            local_instructions = local_project / 'AGENTS.md'
            local_instructions.write_bytes(original)
            local_home = local_project / '.codex'
            self.run_cli(manager, 'install', '--target', str(local_home), '--parts', 'roles', '--profile', 'adaptive-max-2-subagents')
            self.run_cli(manager, 'doctor', '--target', str(local_home))
            local_skill = local_project / '.agents/skills/adaptive-agent-orchestrator'
            shutil.copytree(package / 'skills/adaptive-agent-orchestrator', local_skill)
            self.run_cli(registration, '--project', str(local_project), '--project-skills', '--skill', 'adaptive-agent-orchestrator')
            local_bytes = local_instructions.read_bytes()
            self.assertTrue(local_bytes.startswith(original))
            self.assertIn(b'](.agents/skills/adaptive-agent-orchestrator/SKILL.md)', local_bytes)
            self.run_cli(registration, '--project', str(local_project), '--project-skills', '--skill', 'adaptive-agent-orchestrator')
            self.assertEqual(local_instructions.read_bytes(), local_bytes)
            self.assertEqual(len(list((local_home / 'agents').glob('ao_*.toml'))), 9)
            self.assertTrue((local_home / 'scripts/deepseek_worker.py').is_file())
            self.assertTrue((local_home / 'scripts/process_guard.py').is_file())
            self.assertFalse((local_home / 'config.toml').exists())
            self.assertFalse((local_home / 'skills').exists())
            for name in ('adaptive-agent-orchestrator', 'astra-orchestrator'):
                self.assertTrue((target / 'skills' / name / 'references/patterns.md').is_file())
            self.run_cli(manager, 'uninstall', '--target', str(target))
            self.assertEqual(instructions.read_bytes(), appended)
            self.assertFalse((target / 'adaptive.config.toml').exists())
            backup = next((target / '.adaptive-agent-orchestrator-backups').glob('uninstall-*'))
            self.run_cli(manager, 'restore', backup.name, '--target', str(target))
            self.run_cli(manager, 'doctor', '--target', str(target))
            self.assertEqual((target / 'config.toml').read_text(), 'model = "keep-root"\n')
            self.assertEqual(unrelated.read_text(), 'keep\n')
            for name in ('adaptive-agent-orchestrator', 'astra-orchestrator'):
                skill_target = base / name
                self.run_cli(manager, 'install', '--target', str(skill_target), '--skill', name, '--parts', 'skills')
                self.run_cli(manager, 'doctor', '--target', str(skill_target))
                self.assertTrue((skill_target / 'skills' / name / 'references/patterns.md').is_file())
                self.assertEqual(len(list((skill_target / 'skills').iterdir())), 1)
                self.assertFalse((skill_target / 'agents').exists())

    def run_cli(self, script, *args):
        result = subprocess.run([sys.executable, str(script), *args], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
