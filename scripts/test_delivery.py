import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json

def load(name):
    spec=importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

deploy=load('deploy_release')
metadata=load('release_metadata')

class DeliveryTests(unittest.TestCase):
    def test_single_schema_head(self):
        self.assertEqual(metadata.schema_head(Path(__file__).parents[1]/'backend/alembic/versions'), '20260916_recorder')

    def test_acceptance_changes_only_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'cluster/apps/pnballie-acceptance';folder.mkdir(parents=True)
            release={'revision':'a'*40,'schema':'20260916_recorder','backend':'sha256:'+'b'*64,
                     'frontend':'sha256:'+'c'*64,'source_run':'https://github.com/RomanNekrasov/PNBallie/actions/runs/123'}
            for filename,service in [('backend.yaml','backend'),('avatar-worker.yaml','backend'),('frontend.yaml','frontend')]:
                (folder/filename).write_text('image: ghcr.io/romannekrasov/pnballie-'+service+'@sha256:'+'d'*64+'\n')
            deploy.prepare(root,'acceptance',release)
            self.assertEqual(json.loads((folder/'release.json').read_text()),release)
            with self.assertRaises(ValueError):
                deploy.prepare(root,'production',dict(release,revision='e'*40))
            with patch.object(deploy,'live_matches',return_value=False), self.assertRaises(ValueError):
                deploy.prepare(root,'production',release)

    def test_complete_release_includes_worker(self):
        release={'revision':'a','schema':'b'}
        with patch.object(deploy,'public_version',side_effect=[{'revision':'a','schema':'b','worker_revision':'old'},{'revision':'a'}]):
            self.assertFalse(deploy.live_matches('acceptance',release))

if __name__=='__main__':
    unittest.main()
