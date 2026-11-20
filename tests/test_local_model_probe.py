"""Contrato do aceite de IA usando dublês explícitos, sem inferência no CI."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from radar_quantum_bench.ollama import AdvisorError
from tools.verify_local_model import main, probe, source_binding


class ProbeAdvisor:
    mode = 'valid'

    def __init__(self, model, timeout):
        self.model = model if ':' in model else model + ':latest'
        self.timeout = timeout
        self.identity = {'name': self.model, 'digest': 'a' * 64, 'server_version': '1.0.0'}

    def propose(self, source):
        if self.mode == 'timeout':
            raise AdvisorError('tempo_esgotado')
        candidate = source['proposta_base']
        if self.mode == 'invalid':
            candidate['observacoes'][0]['texto'] = 'CONTEUDO-LIVRE-FICTICIO'
        else:
            candidate['observacoes'].reverse()
        return candidate


class LocalModelProbeTests(unittest.TestCase):
    def test_three_validated_selections_reopen_and_match_downloads(self):
        with patch('radar_quantum_bench.ollama.OllamaAdvisor', ProbeAdvisor):
            document = probe('test-model')
        self.assertEqual(document['status'], 'passed')
        self.assertTrue(document['reopened_without_model'])
        self.assertEqual([case['circuit'] for case in document['cases']], ['bell', 'ghz', 'bv'])
        for case in document['cases']:
            self.assertEqual(case['origin'], 'modelo_local')
            self.assertIsNone(case['fallback_reason'])
            self.assertTrue(case['facts_preserved'])
            self.assertTrue(case['limits_preserved'])
            self.assertTrue(case['exports_match'])
            self.assertGreaterEqual(case['elapsed_ms'], 0)
        encoded = json.dumps(document)
        for forbidden in ('job_id', 'run_id', 'messages', 'thinking', 'prompt'):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(document['new_scientific_executions'], 0)
        self.assertTrue(document['preparatory'])
        self.assertIsNone(document['source'])

    def test_model_timeout_is_a_failed_acceptance_even_with_safe_downloads(self):
        with patch.object(ProbeAdvisor, 'mode', 'timeout'), patch('radar_quantum_bench.ollama.OllamaAdvisor', ProbeAdvisor):
            document = probe('test-model')
        self.assertEqual(document['status'], 'failed')
        self.assertFalse(document['real_model_selected'])
        self.assertEqual({case['fallback_reason'] for case in document['cases']}, {'tempo_esgotado'})
        self.assertTrue(all(case['exports_match'] for case in document['cases']))
        self.assertTrue(document['reopened_without_model'])

    def test_free_text_cannot_become_an_approved_model_acceptance(self):
        with patch.object(ProbeAdvisor, 'mode', 'invalid'), patch('radar_quantum_bench.ollama.OllamaAdvisor', ProbeAdvisor):
            document = probe('test-model')
        self.assertEqual(document['status'], 'failed')
        self.assertEqual({case['fallback_reason'] for case in document['cases']}, {'proposta_invalida'})
        self.assertNotIn('CONTEUDO-LIVRE-FICTICIO', json.dumps(document))

    def test_binding_checks_extracted_files_before_any_model_call(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            data = b'fonte-ficticia'
            file = root / 'component.py'
            file.write_bytes(data)
            manifest = {'source_revision': 'b' * 40,
                        'files': {'component.py': {'sha256': sha256(data).hexdigest(), 'bytes': len(data)}}}
            (root / 'RELEASE-MANIFEST.json').write_text(json.dumps(manifest))
            with patch('tools.verify_local_model.ROOT', root), patch('radar_quantum_bench.release.verify_release', return_value=manifest) as verify:
                bound = source_binding(root / 'candidate.zip', 'c' * 64)
                self.assertEqual(bound['candidate_sha256'], 'c' * 64)
                self.assertEqual(bound['source_revision'], 'b' * 40)
                self.assertTrue(bound['content_matches_manifest'])
                verify.assert_called_once_with(root / 'candidate.zip', expected_sha256='c' * 64)
                file.write_bytes(b'fonte-adulterada')
                with patch('radar_quantum_bench.ollama.OllamaAdvisor') as model, self.assertRaises(ValueError):
                    probe('test', candidate=root / 'candidate.zip', expected_sha256='c' * 64)
                model.assert_not_called()

    def test_binding_requires_the_external_digest_even_for_python_callers(self):
        with self.assertRaises(ValueError):
            source_binding(Path('candidate.zip'), None)
        with self.assertRaises(ValueError):
            source_binding(None, 'c' * 64)

    def test_cli_keeps_evidence_out_of_public_source_directories(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'docs').mkdir()
            (root / 'local-data').mkdir()
            with patch('tools.verify_local_model.ROOT', root), patch('tools.verify_local_model.probe') as model, redirect_stderr(StringIO()):
                self.assertEqual(main(['--model', 'test', '--output', str(root / 'docs/model.json')]), 1)
                model.assert_not_called()
            self.assertFalse((root / 'docs/model.json').exists())
            with patch('tools.verify_local_model.ROOT', root), patch('tools.verify_local_model.probe', return_value={'schema': 'rqb-local-model-verification/1', 'status': 'failed'}), redirect_stdout(StringIO()):
                self.assertEqual(main(['--model', 'test', '--output', str(root / 'local-data/model.json')]), 1)
            self.assertTrue((root / 'local-data/model.json').exists())

    def test_cli_preserves_existing_evidence_before_any_model_call(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'model.json'
            path.write_text('evidencia-anterior')
            with patch('tools.verify_local_model.probe') as generation, redirect_stderr(StringIO()):
                self.assertEqual(main(['--model', 'test', '--output', str(path)]), 1)
                generation.assert_not_called()
            self.assertEqual(path.read_text(), 'evidencia-anterior')

    def test_cli_writes_failed_result_without_claiming_acceptance(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'failed.json'
            with patch('tools.verify_local_model.probe', return_value={'schema': 'rqb-local-model-verification/1', 'status': 'failed'}), redirect_stdout(StringIO()):
                self.assertEqual(main(['--model', 'test', '--output', str(path)]), 1)
            self.assertEqual(json.loads(path.read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
