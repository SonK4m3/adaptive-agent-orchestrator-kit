from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InteractiveSetupTests(unittest.TestCase):
    def test_setup_installs_selected_skill_and_optional_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "codex-home"
            original = b'# Consumer project rules\r\nKeep this exact content.'
            (Path(temp) / 'AGENTS.md').write_bytes(original)
            env = {**os.environ, "CODEX_HOME": str(target)}
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "setup.py")],
                input=f"1\n3\ny\nn\n{target}\n{temp}\n",
                text=True,
                capture_output=True,
                cwd=ROOT,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / "skills" / "adaptive-agent-orchestrator" / "SKILL.md").is_file())
            self.assertEqual(len(list((target / "agents").glob("ao_*.toml"))), 8)
            self.assertIn("Setup complete", result.stdout)
            instructions = (Path(temp) / 'AGENTS.md').read_text()
            self.assertIn('adaptive-agent-orchestrator', instructions)
            self.assertIn('root-only', instructions)
            self.assertTrue((Path(temp) / 'AGENTS.md').read_bytes().startswith(original))

    def test_invalid_project_stops_before_install(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'codex-home'
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/setup.py')],
                input=f'1\n3\nn\nn\n{target}\n{Path(temp) / "missing"}\n',
                text=True, capture_output=True, cwd=ROOT,
                env={**os.environ, 'CODEX_HOME': str(target)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target.exists())

    def test_registration_error_is_reported_without_erasing_project(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'codex-home'
            instructions = Path(temp) / 'AGENTS.md'
            original = b'# Keep\n<!-- adaptive-agent-orchestrator-kit: routing v1 -->'
            instructions.write_bytes(original)
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/setup.py')],
                input=f'1\n3\nn\nn\n{target}\n{temp}\n', text=True,
                capture_output=True, cwd=ROOT, env={**os.environ, 'CODEX_HOME': str(target)},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Skills installed, but project registration failed', result.stderr)
            self.assertTrue((target / 'skills/adaptive-agent-orchestrator/SKILL.md').is_file())
            self.assertEqual(instructions.read_bytes(), original)

    def test_optional_profile_prompt_installs_named_preset(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'codex-home'
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/setup.py')],
                input=f'2\n2\nn\ny\n{target}\n\n', text=True, capture_output=True, cwd=ROOT,
                env={**os.environ, 'CODEX_HOME': str(target)},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / 'adaptive-max-2-subagents.config.toml').is_file())
            self.assertTrue((target / 'skills/astra-orchestrator/SKILL.md').is_file())
            self.assertFalse((target / 'agents').exists())
            self.assertFalse((target / 'config.toml').exists())


if __name__ == "__main__":
    unittest.main()
