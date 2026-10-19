"""Static policy contract checks; runtime instruction following needs a fresh session."""
from pathlib import Path
import json
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
ALIASES = ('adaptive-agent-orchestrator', 'astra-orchestrator')


def policy_text(alias=ALIASES[0]):
    return (ROOT / 'skills' / alias / 'references/deepseek-first.md').read_text(encoding='utf-8')


def routing_contract():
    return json.loads(re.search(r'```json\n(.*?)\n```', policy_text(), re.DOTALL).group(1))


class RoutingPolicyTests(unittest.TestCase):
    def test_both_skill_entrypoints_share_policy(self):
        self.assertEqual(policy_text(ALIASES[0]), policy_text(ALIASES[1]))
        adaptive_entry = (ROOT / 'skills' / ALIASES[0] / 'SKILL.md').read_text(encoding='utf-8')
        astra_entry = (ROOT / 'skills' / ALIASES[1] / 'SKILL.md').read_text(encoding='utf-8')
        self.assertEqual(
            adaptive_entry.replace('name: adaptive-agent-orchestrator', 'name: astra-orchestrator', 1),
            astra_entry,
        )
        for alias in ALIASES:
            entry = (ROOT / 'skills' / alias / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('(references/deepseek-first.md)', entry)
            self.assertIn('Model routing and delegation', entry)
            self.assertNotIn('For small or tightly coupled work, complete it at root', entry)

    def test_root_ownership_is_model_neutral(self):
        for alias in ALIASES:
            entry = (ROOT / 'skills' / alias / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('Root owns requirements, scope, planning, integration, diff review, and final acceptance regardless of its configured model.', entry)
            self.assertNotIn('Astra owns scope and acceptance', entry)
            self.assertNotIn('straightforward fallback uses Astra', entry)
            self.assertNotIn('complex fallback uses Luna', entry)

    def test_routing_checks_constraints_clarity_risk_and_benefit_in_order(self):
        policy = routing_contract()
        self.assertEqual(policy['default_implementation_worker'], 'deepseek')
        self.assertEqual(policy['routing_order'], [
            'constraints_and_execution_capability', 'task_clarity', 'risk', 'delegation_benefit'])
        self.assertEqual(set(policy['root_direct_when']), {
            'tiny_or_tightly_coupled', 'external_sharing_unsuitable', 'delegation_has_no_net_benefit'})
        text = policy_text()
        self.assertIn('DeepSeek Harness is the default worker', text)
        self.assertIn('For suitable implementation delegation', text)

    def test_direct_deepseek_and_adaptive_topology_have_no_minimum_subagents(self):
        policy = routing_contract()
        self.assertEqual(policy['minimum_codex_subagents'], 0)
        text = policy_text()
        self.assertIn('Root may invoke it directly', text)
        self.assertIn('no Luna supervisor', text)
        for level in ('**L0:**', '**L1:**', '**L2:**', '**L3:**'):
            self.assertIn(level, text)
        self.assertIn('Topology level describes coordinated workstreams', text)

    def test_specialists_are_demand_driven(self):
        policy = routing_contract()
        self.assertEqual(policy['specialists'], {
            'exploration_or_current_research': 'luna_on_demand',
            'architecture_or_independent_review': 'astra_on_demand'})
        text = policy_text()
        self.assertIn('resolving it can change the implementation', text)
        self.assertIn('independent review when risk warrants it', text)
        self.assertIn('do not repeat exploration already completed', text)

    def test_retry_is_bounded_and_known_incompatible_path_is_not_retried(self):
        policy = routing_contract()
        self.assertEqual(policy['provider_availability_retries'], 1)
        self.assertEqual(policy['retry_timeout_seconds'], 60)
        self.assertFalse(policy['retry_known_incompatible_workspace'])
        text = policy_text()
        self.assertIn('one bounded retry', text)
        self.assertIn('Do not retry the same known-incompatible workspace', text)
        self.assertIn('If the same DSH session can safely accept one focused correction', text)

    def test_windows_acl_failure_routes_without_disabling_sandbox(self):
        policy = routing_contract()
        self.assertFalse(policy['retry_known_incompatible_workspace'])
        text = policy_text()
        self.assertIn('grantWrite(...D:\\Web\\adaptive-agent-orchestrator-kit)', text)
        self.assertIn('Never disable sandbox restrictions', text)
        self.assertIn('a user-profile worktree is a candidate', text)

    def test_handoff_requires_stopped_workers_and_diff_review(self):
        self.assertEqual(set(routing_contract()['handoff_requires']),
                         {'owned_processes_stopped', 'cleanup_errors_empty', 'diff_reviewed'})
        self.assertIn('Before any retry or writer handoff', policy_text())
        self.assertIn('do not start another writer', policy_text())

    def test_verification_is_owned_by_codex(self):
        self.assertEqual(routing_contract()['verification_owner'], 'codex')
        self.assertIn('runs the requested acceptance checks independently', policy_text())
        self.assertIn('A completed wrapper status or worker claim does not establish correctness', policy_text())

    def test_wrapper_cwd_and_permission_limits_are_documented(self):
        text = policy_text()
        self.assertIn('wrapper cwd', text)
        self.assertIn('no `--cwd` or session-resume option', text)
        self.assertIn('Read the selected `scripts/deepseek_worker.py --help` and implementation', text)
        self.assertIn('Resolve the wrapper from the active checkout first', text)
        self.assertIn('Send the task as UTF-8 on stdin', text)
        self.assertIn('dsh --profile headless --json -', text)
        self.assertIn("separately from the child's `exit_code`", text)
        self.assertIn('requested permission separate from `effective_permission_mode=null`', text)
        self.assertIn('effective_permission_mode: null', text)
        self.assertIn('Record model pins separately from runtime-confirmed model identity', text)

    def test_fallback_uses_existing_model_pins_without_editing_them(self):
        text = policy_text()
        self.assertIn('select an available writable Codex role by its actual configured model/effort', text)
        for role in ('ao_worker_critical', 'ao_worker'):
            role_data = tomllib.loads((ROOT / f'profiles/adaptive/codex/agents/{role}.toml').read_text())
            self.assertTrue(role_data['model'].startswith('gpt-'))
            self.assertEqual(role_data['sandbox_mode'], 'workspace-write')


if __name__ == '__main__':
    unittest.main()
