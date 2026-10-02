import copy
import unittest
from compare_usage import compare


def run(enabled):
    binding = {'model': 'model-a', 'effort': 'medium'}
    return {'run_id': 'advisory' if enabled else 'baseline', 'status': 'completed',
            'intake': {'comparison_contract': {'spec_sha256': 'a' * 64,
                'prompt_sha256': 'b' * 64, 'fixture_sha256': 'c' * 64,
                'coding_models': {'root': binding}, 'acceptance_ids': ['R1'], 'jev_enabled': enabled}},
            'report': {'outcome': {'criteria': [{'id': 'R1', 'result': 'met', 'evidence': ['test-log']} ]},
                       'usage': {'measured_channels': {
                           'coding_agents': {'threads': [{'role': 'root', 'category': 'coding',
                                                          'model_bindings': [binding]}]},
                           'jev_advisory': [{'status': 'pass'}] if enabled else []}}}}


class ComparisonTests(unittest.TestCase):
    def test_same_setup_is_only_eligible_not_proven_savings(self):
        result = compare(run(False), run(True))
        self.assertEqual(result['status'], 'eligible_for_review')
        self.assertIsNone(result['savings'])

    def test_changed_hash_models_acceptance_blocked(self):
        for key, value in [('spec_sha256', 'd' * 64), ('fixture_sha256', 'd' * 64),
                           ('prompt_sha256', 'd' * 64), ('acceptance_ids', ['R2']),
                           ('coding_models', {'root': {'model': 'different', 'effort': 'high'}})]:
            advisory = run(True)
            advisory['intake']['comparison_contract'][key] = value
            self.assertEqual(compare(run(False), advisory)['status'], 'blocked')

    def test_partial_failed_missing_acceptance_blocked(self):
        for result in ('unverified', 'unmet', 'blocked'):
            advisory = run(True)
            advisory['report']['outcome']['criteria'][0]['result'] = result
            self.assertEqual(compare(run(False), advisory)['status'], 'blocked')

    def test_actual_model_changed_even_same_declared_contract(self):
        advisory = run(True)
        advisory['report']['usage']['measured_channels']['coding_agents']['threads'][0]['model_bindings'] = []
        self.assertEqual(compare(run(False), advisory)['status'], 'blocked')

    def test_wrong_arm_same_run_missing_jev(self):
        advisory = run(True)
        advisory['run_id'] = 'baseline'
        advisory['report']['usage']['measured_channels']['jev_advisory'] = []
        self.assertEqual(compare(run(False), advisory)['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
