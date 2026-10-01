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
            env = {**os.environ, "CODEX_HOME": str(target)}
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "setup.py")],
                input=f"3\ny\n{target}\n",
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


if __name__ == "__main__":
    unittest.main()
