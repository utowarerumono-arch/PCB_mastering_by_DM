"""Portable integrity tests. These do not test an LLM or qualify a PCB."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check_evidence.py'


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {'board': b'final board', 'schema': b'final schema',
                      'report': b'{"errors": [], "parity_executed": true}',
                      'source': b'original immutable'}
        artifacts = {}
        for key, value in self.files.items():
            (self.root / key).write_bytes(value)
            artifacts[key] = {'path': key, 'sha256': hashlib.sha256(value).hexdigest()}
        self.manifest = {
            'schema_version': 1,
            'artifacts': artifacts,
            'protected_sources': {'source': artifacts['source']['sha256']},
            'required_checks': ['parity'],
            'checks': [{'id': 'parity', 'executed': True, 'outcome': 'pass',
                        'evidence': 'report', 'inputs': {
                            key: artifacts[key]['sha256'] for key in ('board', 'schema')}}]
        }

    def run_check(self):
        self.assertTrue(SCRIPT.is_file(), 'Missing evidence validator')
        path = self.root / 'manifest.json'
        path.write_text(json.dumps(self.manifest))
        proc = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                              text=True, capture_output=True)
        self.assertIn(proc.returncode, (0, 1), proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(proc.returncode == 0, result['status'] == 'PASS')
        self.assertEqual(result['scope'], 'integrity_and_execution_only')
        return result

    def reject(self, code):
        result = self.run_check()
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn(code, [e['code'] for e in result['errors']])

    def test_valid_manifest(self):
        self.assertEqual(self.run_check()['status'], 'PASS')

    def test_board_modified_after_check(self):
        (self.root / 'board').write_bytes(b'later board')
        self.reject('HASH_MISMATCH')

    def test_old_check_after_manifest_updated(self):
        (self.root / 'board').write_bytes(b'later board')
        self.manifest['artifacts']['board']['sha256'] = hashlib.sha256(b'later board').hexdigest()
        self.reject('STALE_INPUT')

    def test_empty_parity_not_execution(self):
        self.manifest['checks'][0]['executed'] = False
        self.reject('NOT_EXECUTED')

    def test_missing_required_check(self):
        self.manifest['checks'] = []
        self.reject('MISSING_CHECK')

    def test_failed_check(self):
        self.manifest['checks'][0]['outcome'] = 'fail'
        self.reject('CHECK_NOT_PASS')

    def test_missing_report(self):
        (self.root / 'report').unlink()
        self.reject('MISSING_FILE')

    def test_report_modified(self):
        (self.root / 'report').write_text('all good')
        self.reject('HASH_MISMATCH')

    def test_unknown_evidence(self):
        self.manifest['checks'][0]['evidence'] = 'missing'
        self.reject('UNKNOWN_EVIDENCE')

    def test_check_without_inputs(self):
        self.manifest['checks'][0]['inputs'] = {}
        self.reject('NO_INPUTS')

    def test_unknown_input(self):
        self.manifest['checks'][0]['inputs']['other'] = '0' * 64
        self.reject('UNKNOWN_INPUT')

    def test_source_modified_even_when_artifact_hash_updated(self):
        (self.root / 'source').write_bytes(b'changed source')
        self.manifest['artifacts']['source']['sha256'] = hashlib.sha256(b'changed source').hexdigest()
        self.reject('SOURCE_CHANGED')

    def test_duplicate_check_id(self):
        self.manifest['checks'].append(copy.deepcopy(self.manifest['checks'][0]))
        self.reject('DUPLICATE_CHECK')

    def test_path_outside_package(self):
        self.manifest['artifacts']['board']['path'] = '../elsewhere'
        self.reject('UNSAFE_PATH')

    def test_no_required_checks_is_not_success(self):
        self.manifest['required_checks'] = []
        self.reject('NO_REQUIRED_CHECKS')

    def test_invalid_document(self):
        self.manifest = {'schema_version': 99}
        self.reject('SCHEMA')


if __name__ == '__main__':
    unittest.main(verbosity=2)
