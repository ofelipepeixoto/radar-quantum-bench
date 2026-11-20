"""Evidências fictícias do piloto, sem participantes ou declarações reais."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from io import StringIO
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from radar_quantum_bench import acceptance as a


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.records = self.directory / 'private'
        self.candidate = self.directory / 'candidate.zip'
        self.candidate.write_bytes(b'fictional candidate fixture, not an actual release')
        self.readiness = {'status': 'blocked', 'reasons': ['licenca_propria_pendente'],
                          'scope': 'revisao_tecnica_sem_autorizacao_de_redistribuicao'}
        # The release suite verifies real ZIPs. Here the fixture isolates pilot records.
        with patch.object(a, 'verify_release', return_value={'source_revision': 'a' * 40, 'readiness': self.readiness}):
            self.state = a.initialize(self.candidate, self.records, expected_sha256=sha256(self.candidate.read_bytes()).hexdigest(), model_enabled=True)
        self.attachment = self.directory / 'evidence.txt'
        self.attachment.write_bytes(b'SYNTHETIC ATTACHMENT ONLY; NOT A HUMAN SESSION')
        self.binding = {key: self.state[key] for key in ('source_revision', 'candidate_sha256')}
        self.common = {**self.binding, 'evidence_sha256': sha256(self.attachment.read_bytes()).hexdigest(),
                       'observer_code': 'R01', 'observed_on': '2026-11-20'}

    def check(self, name='wsl_pc', result='passed'):
        return {**self.common, 'schema': 'rqb-pilot-check/1', 'check': name, 'result': result,
                'basis': 'recorded_human_attestation'}

    def session(self, index=0):
        return {**self.common, 'schema': 'rqb-pilot-session/1', 'participant': f'P{index + 1:02}',
                'lab': 'A' if index < 3 else 'B', 'circuit': 'bell',
                'order': 'notebook_first' if index < 3 else 'platform_first',
                'notebook': {'seed_list': 'A' if index % 2 == 0 else 'B', 'duration_seconds': 900,
                             'help_count': 0, 'export_completed': True},
                'platform': {'seed_list': 'B' if index % 2 == 0 else 'A', 'duration_seconds': 500 + index * 10,
                             'help_count': 0, 'export_completed': True},
                'interpretation': {'observed': True, 'theory': True, 'limitation': index != 4},
                'peer_recalculation': True}

    def test_empty_registry_has_no_human_results_or_automatic_release_approval(self):
        result = a.summarize(self.records)
        self.assertEqual(result['sessions_recorded'], 0)
        self.assertTrue(all(value == 'pending' for value in result['checks'].values()))
        self.assertTrue(all(value == 'pending' for value in result['technical_receipts'].values()))
        self.assertIsNone(result['median_platform_minus_notebook_seconds'])
        self.assertEqual(result['decision'], 'blocked_by_candidate_policy')
        self.assertFalse(result['human_attestations_independently_verified'])
        self.assertFalse(result['technical_receipts_authenticated'])
        with self.assertRaisesRegex(ValueError, 'já existe'):
            with patch.object(a, 'verify_release', return_value={'source_revision': 'a' * 40, 'readiness': self.readiness}):
                a.initialize(self.candidate, self.records, expected_sha256=sha256(self.candidate.read_bytes()).hexdigest())
        with self.assertRaises(Exception):
            a.initialize(self.candidate, self.directory / 'invalid-archive', expected_sha256=sha256(self.candidate.read_bytes()).hexdigest())

    def test_recorded_human_history_is_distinct_from_authentication(self):
        a.add_check(self.records, self.check(result='failed'), self.attachment)
        a.add_check(self.records, self.check(result='passed'), self.attachment)
        self.assertEqual(a.summarize(self.records)['checks']['wsl_pc'], 'passed')
        raw = json.loads((self.records / 'acceptance.json').read_bytes())
        self.assertEqual(len(raw['checks']['wsl_pc']), 2)
        self.assertTrue(all(item['basis'] == 'recorded_human_attestation' for item in raw['checks']['wsl_pc']))
        fake_automatic = self.check()
        fake_automatic['basis'] = 'automated_receipt'
        with self.assertRaises(ValueError):
            a.add_check(self.records, fake_automatic, self.attachment)
        with self.assertRaises(ValueError):
            a.add_check(self.records, self.check('local_model'), self.attachment)

    def test_foreign_candidate_unknown_fields_and_missing_attachment_are_rejected(self):
        cases = []
        foreign = self.check()
        foreign['candidate_sha256'] = 'f' * 64
        cases.append(foreign)
        private = self.check()
        private['email'] = 'fictional-person@example.invalid'
        cases.append(private)
        invalid_date = self.check()
        invalid_date['observed_on'] = '20261120'
        cases.append(invalid_date)
        for record in cases:
            with self.subTest(record=record), self.assertRaises(ValueError):
                a.add_check(self.records, record, self.attachment)
        wrong_digest = self.check()
        wrong_digest['evidence_sha256'] = 'b' * 64
        with self.assertRaises(ValueError):
            a.add_check(self.records, wrong_digest, self.attachment)
        self.assertTrue(all(value == 'pending' for value in a.summarize(self.records)['checks'].values()))

    def test_five_paired_sessions_compute_thresholds_without_unlocking_candidate(self):
        for index in range(5):
            a.add_session(self.records, self.session(index), self.attachment)
        round_record = {**self.common, 'schema': 'rqb-pilot-second-round/1', 'lab': 'B',
                        'responsible_code': 'R02', 'scheduled_on': '2026-12-01',
                        'commercial_interest': 'accepted_discussion'}
        a.add_second_round(self.records, round_record, self.attachment)
        result = a.summarize(self.records)
        self.assertEqual(result['sessions_recorded'], 5)
        self.assertEqual(result['exports_without_help_within_600s'], 5)
        self.assertEqual(result['correct_interpretations'], 4)
        self.assertEqual(result['peer_recalculations'], 5)
        self.assertEqual(result['median_platform_minus_notebook_seconds'], -380)
        self.assertEqual(result['completed_pairs_count'], 5)
        self.assertTrue(all(result['criteria'].values()))
        self.assertEqual(result['decision'], 'blocked_by_candidate_policy')
        rendered = json.dumps(result)
        for private in ('R01', 'R02', '2026-12-01', 'evidence.txt', 'SYNTHETIC ATTACHMENT', 'P01'):
            self.assertNotIn(private, rendered)
        with self.assertRaisesRegex(ValueError, 'já possui'):
            a.add_session(self.records, self.session(0), self.attachment)

    def test_failed_tasks_and_missing_participants_do_not_meet_criteria(self):
        for index in range(4):
            row = self.session(index)
            row['platform']['help_count'] = 1
            row['platform']['duration_seconds'] = 601
            row['peer_recalculation'] = False
            row['interpretation']['theory'] = False
            a.add_session(self.records, row, self.attachment)
        result = a.summarize(self.records)
        self.assertEqual(result['exports_without_help_within_600s'], 0)
        self.assertEqual(result['correct_interpretations'], 0)
        self.assertEqual(result['peer_recalculations'], 0)
        self.assertTrue(all(not value for value in result['criteria'].values()))
        for key, bad in (('duration_seconds', True), ('duration_seconds', float('nan')),
                         ('help_count', -1), ('export_completed', 'yes')):
            row = self.session(4)
            row['platform'][key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                a.add_session(self.records, row, self.attachment)

    def test_concurrent_check_records_preserve_history_and_attachment_tampering_is_visible(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(lambda _: a.add_check(self.records, self.check(), self.attachment), range(5)))
        raw = json.loads((self.records / 'acceptance.json').read_text())
        self.assertEqual(len(raw['checks']['wsl_pc']), 5)
        attachment = self.records / 'attachments' / self.common['evidence_sha256']
        attachment.write_bytes(b'ALTERED SYNTHETIC EVIDENCE')
        with self.assertRaisesRegex(ValueError, 'difere'):
            a.summarize(self.records)

    def receipt(self, kind='local_model'):
        source = {**self.binding, 'content_matches_manifest': True}
        if kind == 'workstation':
            return {'schema': 'rqb-workstation-verification/1', 'status': 'passed', 'source': source,
                    'target': {'os': 'Linux', 'architecture': 'x86_64', 'python': '3.12.14', 'is_wsl': True},
                    'prerequisites': {}, 'probe': {'status': 'passed'},
                    'scope': 'environment-automation-not-human-review'}
        cases = [{'circuit': circuit, 'status': 'passed', 'origin': 'modelo_local', 'fallback_reason': None,
                  'elapsed_ms': 123.4, 'model_identity': {'name': 'fixture:latest', 'digest': 'b' * 64, 'server_version': '1.0.0'},
                  'source_result_sha256': 'c' * 64, 'selected_phrase_ids': ['ideal.taxa'],
                  'facts_preserved': True, 'limits_preserved': True, 'exports_match': True}
                 for circuit in ('bell', 'ghz', 'bv')]
        return {'schema': 'rqb-local-model-verification/1', 'status': 'passed', 'source': source,
                'model': 'fixture:latest', 'timeout_seconds': 20, 'warmup': False,
                'environment': {}, 'reopened_without_model': True, 'cases': cases,
                'real_model_selected': True, 'scope': 'selecao_de_frases_do_catalogo_sem_avaliacao_de_texto_livre',
                'new_scientific_executions': 0, 'preparatory': False}

    def test_technical_receipts_do_not_mark_human_workstation_review_complete(self):
        for kind in ('local_model', 'workstation'):
            receipt_path = self.directory / f'{kind}.json'
            receipt_path.write_text(json.dumps(self.receipt(kind)))
            a.import_technical(self.records, receipt_path)
            a.import_technical(self.records, receipt_path)  # same receipt is idempotent
        result = a.summarize(self.records)
        self.assertEqual(result['checks']['local_model'], 'technical_receipt_recorded')
        self.assertEqual(result['checks']['wsl_pc'], 'pending')
        self.assertEqual(result['checks']['second_computer'], 'pending')
        self.assertEqual(result['technical_receipts']['workstation'], 'technical_receipt_recorded')
        self.assertFalse(result['human_attestations_independently_verified'])

    def test_incomplete_pairs_are_not_reported_as_faster_successful_exports(self):
        interrupted = self.session(0)
        interrupted['platform'].update(export_completed=False, duration_seconds=0.1)
        interrupted['peer_recalculation'] = False
        a.add_session(self.records, interrupted, self.attachment)
        result = a.summarize(self.records)
        self.assertIsNone(result['median_platform_minus_notebook_seconds'])
        self.assertEqual(result['completed_pairs_count'], 0)
        a.add_session(self.records, self.session(1), self.attachment)
        result = a.summarize(self.records)
        self.assertEqual(result['median_platform_minus_notebook_seconds'], -390)
        self.assertEqual(result['completed_pairs_count'], 1)

    def test_failed_stub_foreign_or_incomplete_model_receipts_are_not_accepted(self):
        receipt = self.receipt()
        changed = []
        for key, value in (('status', 'failed'), ('real_model_selected', False), ('reopened_without_model', False),
                           ('preparatory', True)):
            item = deepcopy(receipt)
            item[key] = value
            changed.append(item)
        item = deepcopy(receipt)
        item['source']['candidate_sha256'] = 'd' * 64
        changed.append(item)
        item = deepcopy(receipt)
        item['cases'][0]['fallback_reason'] = 'modelo_indisponivel'
        changed.append(item)
        item = deepcopy(receipt)
        item['cases'][0]['model_identity']['name'] = 'another:latest'
        changed.append(item)
        item = deepcopy(receipt)
        item['unexpected'] = 'fictional private marker'
        changed.append(item)
        for index, value in enumerate(changed):
            path = self.directory / f'rejected-{index}.json'
            path.write_text(json.dumps(value))
            with self.subTest(index=index), self.assertRaises(ValueError):
                a.import_technical(self.records, path)
        self.assertEqual(a.summarize(self.records)['checks']['local_model'], 'pending')

    def test_cli_export_is_exclusive_and_rejects_in_repository_destinations(self):
        output = self.directory / 'summary.json'
        with redirect_stdout(StringIO()):
            self.assertEqual(a.main(['--directory', str(self.records), 'status', '--output', str(output)]), 0)
        self.assertEqual(json.loads(output.read_text())['sessions_recorded'], 0)
        with redirect_stdout(StringIO()):
            self.assertEqual(a.main(['--directory', str(self.records), 'status', '--output', str(output)]), 1)
        with self.assertRaises(ValueError):
            a._root(Path(__file__).resolve().parents[1] / 'pilot' / 'private-records')


if __name__ == '__main__':
    unittest.main()
