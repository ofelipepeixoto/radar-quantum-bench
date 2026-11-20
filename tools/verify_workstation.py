"""Conferir uma candidata no Linux/WSL e registrar o ensaio no computador usado."""

import argparse
from hashlib import sha256
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCHEMA = 'rqb-workstation-verification/1'


def target():
    return {'os': platform.system(), 'architecture': platform.machine(),
            'python': platform.python_version(),
            'is_wsl': 'microsoft' in platform.release().lower() or 'wsl' in platform.release().lower()}


def inspect_candidate(candidate, expected_sha256):
    from radar_quantum_bench.release import verify_release

    manifest = verify_release(candidate, expected_sha256=expected_sha256)
    source = {'candidate_sha256': expected_sha256,
              'source_revision': manifest['source_revision'], 'content_matches_manifest': True}
    with ZipFile(candidate) as archive:
        path = 'tools/verify_workstation.py'
        # A newer or modified driver cannot attest for an older candidate.
        if sha256(Path(__file__).read_bytes()).hexdigest() != manifest['files'][path]['sha256']:
            raise ValueError('Use o verificador da mesma candidata.')
        if archive.read(path) != Path(__file__).read_bytes():
            raise ValueError('Verificador incompatível com a candidata.')
    return source


def verify(candidate, expected_sha256):
    system = target()
    source = inspect_candidate(candidate, expected_sha256)
    if (system['os'] != 'Linux' or system['architecture'] != 'x86_64'
            or sys.version_info[:2] != (3, 12)):
        raise ValueError('O ambiente travado exige Linux x86_64 e Python 3.12.')
    with TemporaryDirectory(prefix='rqb-workstation-') as folder:
        extracted = Path(folder) / 'candidate'
        with ZipFile(candidate) as archive:
            # verify_release bounded every member before this extraction.
            archive.extractall(extracted)
        dependencies = []
        for filename in ('requirements.txt', 'requirements-api.txt'):
            for name, expected in re.findall(r'^([A-Za-z0-9_.-]+)==([0-9][A-Za-z0-9.+_-]*)',
                                             (extracted / filename).read_text(), re.M):
                actual = metadata.version(name)
                dependencies.append({'name': name, 'version': actual, 'matches': actual == expected})
        if not all(item['matches'] for item in dependencies):
            raise ValueError('As dependências diferem da candidata.')
        evidence = Path(folder) / 'probe.json'
        result = subprocess.run(
            [sys.executable, str(extracted / 'tools/verify_candidate.py'), '--output', str(evidence)],
            cwd=extracted, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240,
        )
        if result.returncode != 0 or not evidence.is_file():
            raise ValueError('O percurso da candidata não foi aprovado.')
        probe = json.loads(evidence.read_bytes())
        if (probe.get('status') != 'passed'
                or probe.get('schema') != 'radar-quantum-bench/candidate-verification-v1'
                or not probe.get('source', {}).get('content_matches_manifest')
                or probe['source'].get('source_revision') != source['source_revision']):
            raise ValueError('A evidência não corresponde à candidata.')
    return {'schema': SCHEMA, 'status': 'passed', 'source': source,
            'target': system, 'prerequisites': {'dependencies': dependencies,
                'virtualenv_active': sys.prefix != sys.base_prefix},
            'probe': probe, 'scope': 'environment-automation-not-human-review'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--sha256', required=True, help='digest esperado do registro da candidata')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    destination = args.output.resolve()
    if destination.is_relative_to(ROOT) and not destination.is_relative_to(ROOT / 'local-data'):
        parser.error('Dentro do projeto, guarde a evidência somente em local-data.')
    try:
        args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            try:
                report = verify(args.candidate, args.sha256)
            except (ValueError, OSError, KeyError, TypeError, metadata.PackageNotFoundError,
                    subprocess.TimeoutExpired, BadZipFile):
                report = {'schema': SCHEMA, 'status': 'failed', 'target': target(),
                          'failure_code': 'conferencia_local_incompleta',
                          'scope': 'environment-automation-not-human-review'}
            json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
    except OSError:
        print('Escolha um arquivo de saída novo e um diretório gravável.', file=sys.stderr)
        return 1
    print('Ensaio do computador aprovado.' if report['status'] == 'passed'
          else 'Ensaio incompleto. Consulte o registro e o guia de instalação.')
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
