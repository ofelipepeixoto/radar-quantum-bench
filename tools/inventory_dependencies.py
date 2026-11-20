"""Inventário das versões travadas, sem incluir pacotes ou dados do laboratório."""
import argparse
from hashlib import sha256
import importlib.metadata as metadata
import json
from pathlib import Path
import re


def generate(root):
    python = []
    for filename in ('requirements.txt', 'requirements-api.txt'):
        for name, version in re.findall(r'^([A-Za-z0-9_.-]+)==([^\\\s]+)', (root / filename).read_text(), re.M):
            distribution = metadata.distribution(name)
            if distribution.version != version:
                raise ValueError(f'Versão instalada diferente da travada para {name}.')
            label = distribution.metadata.get('License', '')
            license_files = []
            for entry in distribution.files or []:
                if '.dist-info/' in str(entry) and re.search(r'(license|licence|notice|copying)', str(entry), re.I):
                    path = distribution.locate_file(entry)
                    if path.is_file():
                        license_files.append({'path': str(entry), 'sha256': sha256(path.read_bytes()).hexdigest()})
            python.append({'name': name, 'version': version, 'requirements': filename,
                           'license_expression': distribution.metadata.get('License-Expression'),
                           'license_label': label if len(label) < 200 and '\n' not in label else None,
                           'license_text_sha256': sha256(label.encode()).hexdigest() if label else None,
                           'license_classifiers': sorted(c for c in distribution.metadata.get_all('Classifier', []) if c.startswith('License ::')),
                           'license_files': sorted(license_files, key=lambda item: item['path'])})
    lock = json.loads((root / 'web/package-lock.json').read_text())
    node = []
    for path, item in sorted(lock['packages'].items()):
        if not path:
            continue
        if not item.get('license') or not item.get('integrity'):
            raise ValueError(f'Metadados de licença ou integridade ausentes para {path}.')
        node.append({'path': path, 'version': item['version'], 'license': item['license'],
                     'integrity': item['integrity'], 'dev': bool(item.get('dev')),
                     'optional': bool(item.get('optional'))})
    return {'schema_version': 'rqb-dependencies/1',
            'target': {'os': 'linux', 'arch': 'x86_64', 'python': '3.12'},
            'scope': 'Python instalado das versões travadas e referências do lockfile npm, incluindo opcionais de outras plataformas. O pacote não inclui wheels ou node_modules.',
            'requirements_sha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in ('requirements.txt', 'requirements-api.txt', 'web/package-lock.json')},
            'own_code_license': 'pending-owner-decision',
            'python': sorted(python, key=lambda item: item['name']), 'npm_lock': node}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    destination = root / 'releases/dependencies.json'
    encoded = json.dumps(generate(root), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if args.check:
        if destination.read_text() != encoded:
            raise SystemExit('O inventário difere do ambiente e das versões travadas.')
        print('Inventário conferido.')
    else:
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(encoded)
        print('Inventário atualizado a partir das versões instaladas e do lockfile.')


if __name__ == '__main__':
    main()
