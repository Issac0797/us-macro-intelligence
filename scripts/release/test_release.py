"""Adversarial validation tests against the real reviewed snapshot (no network)."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import contextlib
import io
sys.path.insert(0,str(Path(__file__).resolve().parent))
from validate_snapshot import ROOT,validate
from scan_public import scan

class ReleaseValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=validate()

    def reject(self,change):
        data=copy.deepcopy(self.data)
        change(data)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'test-only.json';p.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(Exception):
                validate(p)

    def test_unreviewed_series(self):
        self.reject(lambda d:d['series'][0].update(id='UNREVIEWED'))

    def test_changed_attribution(self):
        self.reject(lambda d:d['series'][0].update(notice='removed'))

    def test_fake_live_flag(self):
        self.reject(lambda d:d.update(is_live=True))

    def test_bad_observation_date(self):
        self.reject(lambda d:d['series'][0]['observations'][0].update(date='2026-02-31'))

    def test_duplicate_date(self):
        self.reject(lambda d:d['series'][0]['observations'].__setitem__(1,d['series'][0]['observations'][0]))

    def test_coverage_mismatch(self):
        self.reject(lambda d:d['series'][0]['coverage'].update(count=1))

    def test_credential_in_source(self):
        self.reject(lambda d:d['series'][0].update(download_url='https://example.invalid/private'))

    def test_policy_date_mismatch(self):
        self.reject(lambda d:d['fed_decisions'][0].update(date='2020-03-14'))

class SecurityScanning(unittest.TestCase):
    def blocked(self,name,content):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/name;p.write_text(content)
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(SystemExit):scan(Path(temp))

    def test_unknown_token(self):
        self.blocked('test-only.txt','ghp_'+'A'*36)

    def test_generic_key_assignment(self):
        self.blocked('test-only.txt','API_KEY='+'b'*32)

    def test_local_runtime_file(self):
        self.blocked('.env','TEST_ONLY=not-a-real-secret')

    def test_private_path(self):
        self.blocked('test-only.txt','C:'+ '/Users/'+'PRIVATE_TEST/file')

if __name__=='__main__':
    unittest.main()
