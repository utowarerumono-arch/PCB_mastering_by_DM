#!/usr/bin/env python3
"""Check declared evidence integrity, not report semantics or engineering quality.

Usage: python3 scripts/check_evidence.py /path/to/manifest.json
All artifact paths are relative to the manifest directory and must stay inside it.
Uses only the Python standard library; never modifies the package.
"""
import hashlib
import json
from pathlib import Path
import re
import sys


def validate(document, root):
    errors = []

    def fail(code, detail):
        errors.append({'code': code, 'detail': detail})

    def result():
        return {'status': 'FAIL' if errors else 'PASS',
                'scope': 'integrity_and_execution_only', 'errors': errors}

    if (not isinstance(document, dict) or document.get('schema_version') != 1
            or not isinstance(document.get('artifacts'), dict)
            or not isinstance(document.get('checks'), list)
            or not isinstance(document.get('required_checks'), list)
            or not isinstance(document.get('protected_sources', {}), dict)):
        fail('SCHEMA', 'Expected schema_version=1, artifacts, checks, required_checks.')
        return result()
    root = Path(root).resolve()
    artifacts = document['artifacts']
    actual = {}
    for key, item in artifacts.items():
        if (not isinstance(item, dict) or not isinstance(item.get('path'), str)
                or not isinstance(item.get('sha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            fail('SCHEMA', 'Invalid artifact: ' + str(key))
            continue
        path = (root / item['path']).resolve()
        if Path(item['path']).is_absolute() or root not in path.parents:
            fail('UNSAFE_PATH', str(key))
            continue
        if not path.is_file():
            fail('MISSING_FILE', str(key))
            continue
        try:
            actual[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            fail('READ_ERROR', str(exc))
            continue
        if actual[key] != item['sha256']:
            fail('HASH_MISMATCH', str(key))
    for key, before in document.get('protected_sources', {}).items():
        if key not in actual or actual[key] != before:
            fail('SOURCE_CHANGED', str(key))
    required = document['required_checks']
    if not required:
        fail('NO_REQUIRED_CHECKS', 'Declare checks required for this scope.')
    if any(not isinstance(key, str) or not key for key in required):
        fail('SCHEMA', 'required_checks must contain non-empty string IDs.')
        return result()
    seen = set()
    for check in document['checks']:
        if not isinstance(check, dict) or not isinstance(check.get('id'), str):
            fail('SCHEMA', 'Invalid check record')
            continue
        key = check['id']
        if key in seen:
            fail('DUPLICATE_CHECK', key)
        seen.add(key)
        if check.get('executed') is not True:
            fail('NOT_EXECUTED', key)
        if check.get('outcome') != 'pass':
            fail('CHECK_NOT_PASS', key)
        evidence = check.get('evidence')
        if not isinstance(evidence, str) or evidence not in artifacts:
            fail('UNKNOWN_EVIDENCE', key)
        inputs = check.get('inputs')
        if not isinstance(inputs, dict) or not inputs:
            fail('NO_INPUTS', key)
            continue
        for source, digest in inputs.items():
            if source not in artifacts:
                fail('UNKNOWN_INPUT', key + ': ' + source)
            elif source not in actual or digest != actual[source]:
                fail('STALE_INPUT', key + ': ' + source)
    for key in required:
        if key not in seen:
            fail('MISSING_CHECK', key)
    return result()


def main():
    if len(sys.argv) != 2:
        print('Usage: check_evidence.py manifest.json', file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        result = validate(json.loads(path.read_text(encoding='utf-8')), path.parent)
    except (OSError, ValueError) as exc:
        result = {'status': 'FAIL', 'scope': 'integrity_and_execution_only',
                  'errors': [{'code': 'READ_OR_JSON', 'detail': str(exc)}]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
