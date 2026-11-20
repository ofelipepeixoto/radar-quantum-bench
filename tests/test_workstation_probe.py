"""Guardas do comando local com processo de prova explicitamente simulado."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('workstation_probe', ROOT / 'tools/verify_workstation.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class WorkstationProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.candidate = self.directory / 'candidate.zip'
        self.output = self.directory / 'receipt.json'
        self.source = {'candidate_sha256': 'a' * 64, 'source_revision': 'b' * 40,
                       'content_matches_manifest': True}

    def test_existing_evidence_is_never_overwritten_or_executed_again(self):
        self.output.write_text('evidencia anterior')
        with patch.object(probe, 'verify') as verify:
            code = probe.main(['--candidate', str(self.candidate), '--sha256', 'a' * 64,
                               '--output', str(self.output)])
        self.assertEqual(code, 1)
        self.assertEqual(self.output.read_text(), 'evidencia anterior')
        verify.assert_not_called()

    def test_driver_from_another_candidate_is_rejected_before_execution(self):
        with ZipFile(self.candidate, 'w') as archive:
            archive.writestr('tools/verify_workstation.py', b'outro verificador')
        manifest = {'source_revision': 'b' * 40,
                    'files': {'tools/verify_workstation.py': {'sha256': sha256(b'outro verificador').hexdigest()}}}
        with patch('radar_quantum_bench.release.verify_release', return_value=manifest):
            with self.assertRaises(ValueError):
                probe.inspect_candidate(self.candidate, 'a' * 64)

    def test_receipt_cannot_be_written_to_a_public_source_folder(self):
        destination = self.directory / 'docs' / 'workstation.json'
        with patch.object(probe, 'ROOT', self.directory), patch.object(probe, 'verify') as verify:
            with self.assertRaises(SystemExit) as context:
                probe.main(['--candidate', str(self.candidate), '--sha256', 'a' * 64,
                            '--output', str(destination)])
        self.assertEqual(context.exception.code, 2)
        self.assertFalse(destination.exists())
        verify.assert_not_called()

    def test_failed_probe_cannot_become_an_accepted_workstation(self):
        with patch.object(probe, 'verify', side_effect=ValueError('DADO_PRIVADO_DE_TESTE')):
            code = probe.main(['--candidate', str(self.candidate), '--sha256', 'a' * 64,
                               '--output', str(self.output)])
        receipt = self.output.read_text()
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(receipt)['status'], 'failed')
        self.assertNotIn('DADO_PRIVADO_DE_TESTE', receipt)
        self.assertNotIn(str(self.directory), receipt)

    def test_successful_simulated_transport_retains_candidate_binding_and_wsl_identity(self):
        with ZipFile(self.candidate, 'w') as archive:
            archive.writestr('requirements.txt', 'qiskit==2.6.2 \\\n  --hash=sha256:fake\n')
            archive.writestr('requirements-api.txt', '-r requirements.txt\n')

        def simulate_run(arguments, **kwargs):
            evidence = Path(arguments[-1])
            evidence.write_text(json.dumps({'schema': 'radar-quantum-bench/candidate-verification-v1',
                'status': 'passed', 'source': {'content_matches_manifest': True,
                                             'source_revision': 'b' * 40}}))
            return type('Result', (), {'returncode': 0})()

        environment = {'os': 'Linux', 'architecture': 'x86_64', 'python': '3.12.14', 'is_wsl': True}
        with patch.object(probe, 'inspect_candidate', return_value=self.source), \
                patch.object(probe, 'target', return_value=environment), \
                patch.object(probe.subprocess, 'run', side_effect=simulate_run), \
                patch.object(probe.metadata, 'version', return_value='2.6.2'):
            result = probe.verify(self.candidate, 'a' * 64)
        self.assertEqual(result['source'], self.source)
        self.assertTrue(result['target']['is_wsl'])
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['scope'], 'environment-automation-not-human-review')


if __name__ == '__main__':
    unittest.main()
