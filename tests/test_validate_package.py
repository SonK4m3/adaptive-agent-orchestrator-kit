"""Regression tests for specific navigation drift and portable skill copies."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_package import validate_navigation


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.skill = Path(self.tmp.name) / 'installed-skill'
        shutil.copytree(ROOT / 'skills/adaptive-agent-orchestrator', self.skill)

    def test_installed_skill_has_no_package_dependency(self):
        validate_navigation(self.skill)

    def test_old_installer_reference_rejected(self):
        path = self.skill / 'references/roles.md'
        path.write_text(path.read_text().replace('python scripts/manage.py install --parts roles', 'install-roles.ps1'))
        with self.assertRaises(AssertionError):
            validate_navigation(self.skill)

    def test_old_catalog_location_rejected(self):
        path = self.skill / 'references/evaluation.md'
        path.write_text(path.read_text().replace('eval/scenarios/catalog.md', 'scenario catalog in the kit root'))
        with self.assertRaises(AssertionError):
            validate_navigation(self.skill)

    def test_external_local_link_rejected_even_if_exists(self):
        (self.skill.parent / 'package.md').write_text('outside')
        path = self.skill / 'SKILL.md'
        path.write_text(path.read_text() + '\n[package](../package.md)\n')
        with self.assertRaises(AssertionError):
            validate_navigation(self.skill)


if __name__ == '__main__':
    unittest.main()
