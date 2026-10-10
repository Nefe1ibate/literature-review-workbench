"""Distribution checks with synthetic records, not scholarly evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / 'skills/literature-review-workbench/scripts/workbench.py'
IMPORTER = CLI.with_name('import_library.py')


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='literature-workbench-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'review with spaces 文献'

    def run_cli(self, script, *args, code=0):
        result = subprocess.run([sys.executable, '-B', str(script), *map(str, args)],
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def init(self):
        self.run_cli(CLI, 'init', '--root', self.root, '--topic', 'Synthetic fixture')

    def write_json(self, name, data):
        path = Path(self.temp.name) / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return path

    def test_install_and_refuse_overwrite(self):
        target = Path(self.temp.name) / 'skills'
        self.run_cli(REPO / 'install.py', '--skills-dir', target)
        installed = target / 'literature-review-workbench'
        self.assertTrue((installed / 'SKILL.md').is_file())
        self.assertTrue((installed / 'assets/library-config.example.json').is_file())
        self.run_cli(installed / 'scripts/workbench.py', '--help')
        sentinel = installed / 'local-edit.txt'
        sentinel.write_text('keep', encoding='utf-8')
        self.run_cli(REPO / 'install.py', '--skills-dir', target, code=2)
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep')

    def test_init_validate_checkpoint_on_unicode_path(self):
        self.init()
        report = self.root / 'checks/validation.json'
        self.run_cli(CLI, 'validate', '--root', self.root, '--report', report)
        self.assertIn(json.loads(report.read_text(encoding='utf-8'))['verdict'], ('pass', 'needs_review'))
        self.run_cli(CLI, 'checkpoint', '--root', self.root, '--label', 'initial')
        manifests = list((self.root / 'snapshots').glob('*.manifest.json'))
        self.assertTrue(manifests)
        manifest = json.loads(manifests[-1].read_text(encoding='utf-8'))
        snapshot = manifests[-1].parent / manifest['state_file']
        self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), manifest['sha256'])

    def test_stale_revision_does_not_change_state(self):
        self.init()
        before = (self.root / 'state.json').read_bytes()
        records = self.write_json('papers.json', [{'id': 'p1', 'title': 'Fixture', 'authors': [],
                                                 'status': 'candidate', 'read_status': 'unread'}])
        self.run_cli(CLI, 'put', '--root', self.root, '--collection', 'papers', '--input', records,
                     '--reason', 'Fixture import', '--expected-revision', 999999, code=3)
        self.assertEqual((self.root / 'state.json').read_bytes(), before)

    def test_missing_foreign_key_is_rejected(self):
        self.init()
        before = (self.root / 'state.json').read_bytes()
        records = self.write_json('sources.json', [{'id': 's1', 'paper_id': 'missing', 'kind': 'text',
                                                  'path': None, 'sha256': None, 'version_label': 'fixture'}])
        self.run_cli(CLI, 'put', '--root', self.root, '--collection', 'sources', '--input', records,
                     '--reason', 'Invalid fixture', code=1)
        self.assertEqual((self.root / 'state.json').read_bytes(), before)

    def test_unverified_claim_cannot_be_accepted(self):
        self.init()
        records = self.write_json('claims.json', [{'id': 'c1', 'text': 'Synthetic assertion',
                                                 'kind': 'source_result', 'status': 'draft', 'evidence_ids': []}])
        self.run_cli(CLI, 'put', '--root', self.root, '--collection', 'claims', '--input', records,
                     '--reason', 'Fixture claim')
        before = (self.root / 'state.json').read_bytes()
        self.run_cli(CLI, 'review', '--root', self.root, '--target', 'claim:c1', '--action', 'ACCEPT',
                     '--reason', 'Unsupported fixture', code=1)
        self.assertEqual((self.root / 'state.json').read_bytes(), before)

    def test_library_import_is_read_only(self):
        library = Path(self.temp.name) / 'library'
        library.mkdir()
        ledger = library / 'catalog.json'
        ledger.write_text(json.dumps({'papers': [{'key': 'p1', 'title': 'Fixture', 'authors': []}]}), encoding='utf-8')
        config = self.write_json('library-config.json', {
            'schema_version': 'literature-library-config/1', 'adapter': 'mapped-ledger',
            'library_root': 'library', 'collections': {'papers': {
                'path': 'library/catalog.json', 'format': 'json', 'records_key': 'papers',
                'mapping': {'id': 'key', 'title': 'title', 'authors': 'authors',
                            'status': {'constant': 'candidate'}, 'read_status': {'constant': 'unread'}}}}})
        before = ledger.read_bytes()
        output = Path(self.temp.name) / 'exports/bundle.json'
        self.run_cli(IMPORTER, '--config', config, '--output', output)
        bundle = json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(len(bundle['papers']), 1)
        self.assertEqual(ledger.read_bytes(), before)
        forbidden = library / 'bundle.json'
        self.run_cli(IMPORTER, '--config', config, '--output', forbidden, code=2)
        self.assertFalse(forbidden.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
