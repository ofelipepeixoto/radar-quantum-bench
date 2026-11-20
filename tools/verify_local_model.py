"""Conferir um modelo Ollama já instalado com os três resultados de referência.

Não instala modelos. Só considera o aceite aprovado quando as três seleções
reais passam pelo contrato do produto e sobrevivem à reabertura e exportação.
"""

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import platform
import re
import sys
from tempfile import TemporaryDirectory
from time import monotonic
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CIRCUITS = ('bell', 'ghz', 'bv')
SCHEMA = 'rqb-local-model-verification/1'


def source_binding(candidate, expected_sha256):
    if candidate is None:
        if expected_sha256 is not None:
            raise ValueError('candidata_ausente')
        return None
    if not isinstance(expected_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('digest_da_candidata_obrigatorio')
    from radar_quantum_bench.release import verify_release
    manifest = verify_release(candidate, expected_sha256=expected_sha256)
    raw = (ROOT / 'RELEASE-MANIFEST.json').read_bytes()
    if json.loads(raw) != manifest:
        raise ValueError('manifesto_da_fonte_divergente')
    for name, row in manifest['files'].items():
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError('caminho_da_fonte_incompativel')
        data = path.read_bytes()
        if len(data) != row['bytes'] or sha256(data).hexdigest() != row['sha256']:
            raise ValueError('fonte_diverge_da_candidata')
    return {'candidate_sha256': expected_sha256, 'source_revision': manifest['source_revision'],
            'content_matches_manifest': True}


def probe(model, timeout_seconds=20.0, warmup=False, candidate=None, expected_sha256=None):
    from fastapi.testclient import TestClient
    from radar_quantum_bench.api import create_app
    from radar_quantum_bench.experiment import load_result
    from radar_quantum_bench.ollama import AdvisorError, OllamaAdvisor
    from radar_quantum_bench.report import build_report, model_input

    provenance = source_binding(candidate, expected_sha256)
    advisor = OllamaAdvisor(model, timeout=timeout_seconds)
    rows = []
    warmup_result = None
    if warmup:
        raw = (ROOT / 'examples/catalogo/bell.json').read_bytes()
        base = build_report(load_result(ROOT / 'examples/catalogo/bell.json'),
                            job_id=str(uuid4()), result_sha256=sha256(raw).hexdigest())
        started = monotonic()
        try:
            candidate = advisor.propose(model_input(base))
            checked = build_report(load_result(ROOT / 'examples/catalogo/bell.json'),
                                   job_id=base['job_id'], result_sha256=base['result_sha256'],
                                   proposal=candidate, model_id=advisor.model)
            warmup_result = {'origin': checked['origem_texto'], 'fallback_reason': checked['fallback_reason']}
        except AdvisorError as exc:
            warmup_result = {'origin': 'deterministico', 'fallback_reason': exc.code}
        warmup_result['elapsed_ms'] = round((monotonic() - started) * 1000, 3)

    with TemporaryDirectory(prefix='rqb-local-model-') as folder:
        directory = Path(folder)
        app = create_app(directory, advisor=advisor)
        store = app.state.store
        original_reports = {}
        with TestClient(app, base_url='http://127.0.0.1:8000') as client:
            for circuit in CIRCUITS:
                source = ROOT / f'examples/catalogo/{circuit}.json'
                document, raw = load_result(source), source.read_bytes()
                job = store.submit(str(uuid4()), circuit, document['config']['base_seed'])
                claim = store.claim()
                if claim['id'] != job['id']:
                    raise ValueError('fila_de_teste_inconsistente')
                store.result_path(job['id']).write_bytes(raw)
                store.finish(job['id'], claim['attempt_id'], True,
                             result_sha256=sha256(raw).hexdigest())
                route = f"/api/v1/comparacoes/{job['id']}/relatorio"
                initial = client.get(route)
                if initial.status_code != 200:
                    raise ValueError('leitura_do_resumo_reprovada')
                baseline = initial.json()
                started = monotonic()
                response = client.post(route)
                elapsed = round((monotonic() - started) * 1000, 3)
                if response.status_code != 200:
                    raise ValueError('geracao_do_relatorio_reprovada')
                report = response.json()
                identifier = report.get('modelo_versao')
                accepted = (report['origem_texto'] == 'modelo_local' and report['fallback_reason'] is None
                            and identifier is not None and identifier['name'] == advisor.model
                            and report['fatos'] == baseline['fatos']
                            and report['limitacoes'] == baseline['limitacoes']
                            and report['resumo'] == baseline['resumo']
                            and report['proximo_teste'] == baseline['proximo_teste'])
                json_response, md_response = client.get(route + '.json'), client.get(route + '.md')
                exports_match = (json_response.status_code == 200 and md_response.status_code == 200
                                 and json_response.json() == report
                                 and report['result_sha256'] in md_response.text
                                 and all(node['texto'] in md_response.text for node in report['observacoes']))
                original_reports[job['id']] = report
                rows.append({'circuit': circuit, 'status': 'passed' if accepted and exports_match else 'failed',
                             'origin': report['origem_texto'], 'fallback_reason': report['fallback_reason'],
                             'elapsed_ms': elapsed, 'model_identity': identifier,
                             'source_result_sha256': sha256(raw).hexdigest(),
                             'selected_phrase_ids': [node['frase_id'] for node in report['observacoes']],
                             'facts_preserved': report['fatos'] == baseline['fatos'],
                             'limits_preserved': report['limitacoes'] == baseline['limitacoes'],
                             'exports_match': exports_match})
        with TestClient(create_app(directory), base_url='http://127.0.0.1:8000') as reopened:
            restored = all(reopened.get(f'/api/v1/comparacoes/{job_id}/relatorio').json() == report
                           for job_id, report in original_reports.items())
    accepted = len(rows) == 3 and all(row['status'] == 'passed' for row in rows) and restored
    return {'schema': SCHEMA, 'status': 'passed' if accepted else 'failed',
            'model': advisor.model, 'timeout_seconds': timeout_seconds, 'warmup': warmup_result,
            'source': provenance, 'preparatory': provenance is None,
            'environment': {'platform': platform.system(), 'architecture': platform.machine(),
                            'python': platform.python_version()},
            'reopened_without_model': restored, 'cases': rows,
            'real_model_selected': any(row['origin'] == 'modelo_local' for row in rows),
            'scope': 'selecao_de_frases_do_catalogo_sem_avaliacao_de_texto_livre',
            'new_scientific_executions': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=float, default=20.0)
    parser.add_argument('--candidate', type=Path, help='ZIP da candidata correspondente à fonte extraída')
    parser.add_argument('--sha256', help='digest esperado do ZIP, proveniente do registro da candidata')
    parser.add_argument('--warmup', action='store_true', help='fazer uma consulta prévia explícita e registrar seu resultado')
    args = parser.parse_args(argv)
    if (not isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 120):
        parser.error('O prazo deve ser positivo, finito e no máximo 120 segundos.')
    if (args.candidate is None) != (args.sha256 is None):
        parser.error('--candidate e --sha256 precisam ser fornecidos juntos.')
    target = args.output.resolve()
    if target.is_relative_to(ROOT) and not target.is_relative_to(ROOT / 'local-data'):
        print('Grave a evidência em local-data ou fora da pasta de fontes.', file=sys.stderr)
        return 1
    # Reserve exclusively before calling the model, preserving previous evidence.
    try:
        with args.output.open('x', encoding='utf-8') as stream:
            try:
                document = probe(args.model, args.timeout_seconds, args.warmup, args.candidate, args.sha256)
            except (ImportError, ValueError, OSError, KeyError, TypeError):
                document = {'schema': SCHEMA, 'status': 'failed', 'failure_code': 'ensaio_local_incompleto'}
            json.dump(document, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
    except OSError:
        print('Não foi possível criar a evidência. Use um destino novo.', file=sys.stderr)
        return 1
    print('Ensaio do modelo aprovado. Confira o vínculo à candidata.' if document['status'] == 'passed' else 'Aceite do modelo pendente. Confira a evidência reduzida.')
    return 0 if document['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
