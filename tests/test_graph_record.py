import copy
import json
import re
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_graph_record import validate_record, normalize_path


def fixture(name):
    return json.loads((ROOT / 'eval/fixtures/graph-record' / (name + '.json')).read_text())


class GraphTests(unittest.TestCase):
    def test_four_positive_shapes(self):
        for name in ('l0', 'independent', 'verification', 'reassignment'):
            with self.subTest(name=name):
                self.assertEqual(validate_record(fixture(name)), [])
        self.assertEqual(validate_record(fixture('reassignment'), fixture('l0')), [])

    def test_portable_skill_example_matches_schema(self):
        for alias in ('adaptive-agent-orchestrator', 'astra-orchestrator'):
            doc = (ROOT / 'skills' / alias / 'assets/graph-record.md').read_text(encoding='utf-8')
            examples = re.findall(r'```json\n(.*?)\n```', doc, re.DOTALL)
            self.assertTrue(examples)
            for example in examples:
                self.assertEqual(validate_record(json.loads(example)), [])

    def test_stop_request_is_not_confirmation(self):
        self.assertTrue(any('confirmed disposition' in e for e in validate_record(fixture('invalid-stop-request'))))

    def test_collision_normalizes_case_separators_and_dot(self):
        record = fixture('independent')
        record['nodes'][0]['write_paths'] = ['src/Feature.mjs']
        record['nodes'][1]['write_paths'] = ['./SRC\\feature.mjs']
        self.assertTrue(any('collision' in e for e in validate_record(record)))

    def test_read_scope_can_overlap(self):
        record = fixture('independent')
        self.assertEqual(validate_record(record), [])

    def test_dependency_cycle_but_not_verification_edges(self):
        record = fixture('verification')
        record['edges'] = [{'from': 'impl', 'to': 'review', 'kind': 'dependency'},
                           {'from': 'review', 'to': 'impl', 'kind': 'dependency'}]
        self.assertIn('dependency cycle', validate_record(record))
        record['edges'][1]['kind'] = 'verification'
        self.assertEqual(validate_record(record), [])

    def test_unknown_edges_requirements_and_duplicate_ids(self):
        for mutation in ('edge', 'requirement', 'duplicate'):
            record = fixture('l0')
            if mutation == 'edge':
                record['edges'] = [{'from': 'missing', 'to': 'main', 'kind': 'dependency'}]
            elif mutation == 'requirement':
                record['nodes'][0]['requirement_ids'] = ['missing']
            else:
                record['nodes'].append(copy.deepcopy(record['nodes'][0]))
            self.assertTrue(validate_record(record))

    def test_terminal_and_pass_need_evidence(self):
        record = fixture('l0')
        record['nodes'][0]['status'] = 'completed'
        record['criteria'][0]['status'] = 'pass'
        errors = validate_record(record)
        self.assertTrue(any('terminal' in e for e in errors))
        self.assertTrue(any('pass needs' in e for e in errors))

    def test_actor_is_not_a_command(self):
        record = fixture('l0')
        record['criteria'][0]['verification_owner'] = 'node --test'
        self.assertTrue(any('recorded actor' in e for e in validate_record(record)))

    def test_independence_needs_different_actor(self):
        record = fixture('l0')
        record['criteria'][0]['independent'] = True
        self.assertTrue(any('same actor' in e for e in validate_record(record)))

    def test_previous_requires_handoff_for_changed_writer(self):
        record = fixture('reassignment')
        record['change']['handoffs'] = []
        self.assertTrue(any('missing evidenced' in e for e in validate_record(record, fixture('l0'))))

    def test_revision_and_task_must_match_previous(self):
        record = fixture('reassignment')
        record['task_id'] = 'wrong'
        self.assertTrue(any('mismatch' in e for e in validate_record(record, fixture('l0'))))

    def test_completed_new_writer_does_not_bypass_handoff(self):
        record = fixture('reassignment')
        record['nodes'][0].update(status='completed', evidence=['trace:new-finished'])
        record['change']['handoffs'] = []
        self.assertTrue(any('missing evidenced' in e for e in validate_record(record, fixture('l0'))))

    def test_clearing_old_scope_requires_confirmed_release(self):
        record = fixture('l0')
        record['revision'] = 2
        record['nodes'][0]['write_paths'] = []
        record['change'] = {'from_revision': 1, 'to_revision': 2, 'trigger': 'scope change',
                            'obsolete_work_disposition': 'stop requested', 'handoffs': []}
        self.assertTrue(any('release' in e for e in validate_record(record, fixture('l0'))))
        record['change']['handoffs'] = [{'path': 'label.txt', 'from_actor': 'root',
                                        'to_actor': 'unassigned', 'confirmation': 'handoff_confirmed',
                                        'evidence': ['trace:release-ack']}]
        self.assertEqual(validate_record(record, fixture('l0')), [])

    def test_confirmed_terminal_old_writer_can_release(self):
        record = fixture('l0')
        record['revision'] = 2
        record['nodes'][0].update(status='completed', evidence=['trace:completed'])
        record['change'] = {'from_revision': 1, 'to_revision': 2, 'trigger': 'done',
                            'obsolete_work_disposition': 'completed', 'handoffs': []}
        self.assertEqual(validate_record(record, fixture('l0')), [])

    def test_historical_completion_cannot_release_current_reservation(self):
        previous = fixture('l0')
        historical = copy.deepcopy(previous['nodes'][0])
        historical.update(id='historical', status='completed', evidence=['trace:past'])
        previous['nodes'].append(historical)
        record = copy.deepcopy(previous)
        record['revision'] = 2
        record['nodes'][0]['write_paths'] = []
        record['change'] = {'from_revision': 1, 'to_revision': 2, 'trigger': 'release',
                            'obsolete_work_disposition': 'stop requested', 'handoffs': []}
        self.assertTrue(any('missing evidenced' in e for e in validate_record(record, previous)))

    def test_preserved_obsolete_node_does_not_trigger_repeated_transfer(self):
        previous = fixture('reassignment')
        obsolete = copy.deepcopy(fixture('l0')['nodes'][0])
        obsolete.update(id='old', status='completed', evidence=['trace:old-completed'])
        previous['nodes'].append(obsolete)
        self.assertEqual(validate_record(previous, fixture('l0')), [])
        record = copy.deepcopy(previous)
        record['revision'] = 3
        record['change'] = {'from_revision': 2, 'to_revision': 3, 'trigger': 'checkpoint',
                            'obsolete_work_disposition': 'old completion preserved', 'handoffs': []}
        self.assertEqual(validate_record(record, previous), [])

    def test_unsafe_and_unsupported_paths(self):
        for path in ('../other', '/root', 'D:\\file', '*.mjs', '.', 'dir/', 'label.txt.', 'dir /file', 'NUL.txt'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                normalize_path(path)

    def test_case_sensitive_convention_is_explicit(self):
        record = fixture('independent')
        record['path_case_sensitive'] = True
        record['nodes'][0]['write_paths'] = ['A.mjs']
        record['nodes'][1]['write_paths'] = ['a.mjs']
        self.assertEqual(validate_record(record), [])

    def test_malformed_shapes_return_errors(self):
        for value in (None, [], {}, {'schema_version': 1, 'nodes': []}):
            self.assertTrue(validate_record(value))
        for section, key in (('criteria', 'workstream_id'), ('edges', 'from'), ('nodes', 'agent_id')):
            record = fixture('verification')
            record[section][0][key] = []
            self.assertTrue(validate_record(record))

    def test_criterion_links_back_to_implementation_node(self):
        record = fixture('independent')
        record['nodes'][0]['requirement_ids'] = ['R2']
        self.assertTrue(any('linked' in e for e in validate_record(record)))


if __name__ == '__main__':
    unittest.main()
