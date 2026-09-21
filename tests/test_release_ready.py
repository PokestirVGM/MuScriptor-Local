"""Failure-path and interoperability checks for the release candidate."""
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'src'), str(Path(__file__).resolve().parents[1]/'upstream')]
import numpy as np
import torch
import soundfile as sf
from muscriptor.utils import session, rhythm
from test_rhythm import raw_midi, decoded
import worker
import engine_install


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.raw = raw_midi([.12,.51,1.24])
        self.detection = rhythm.Detection([0,.5,1,1.5,2], [0,2])
        audio = io.BytesIO(); sf.write(audio, np.zeros(32000),16000,format='WAV')
        self.project = session.make(self.raw,self.detection,2,{'mode':'manual','bpm':93,'meter':'6/8'},'Music.wav',audio.getvalue())
    def tearDown(self):
        self.temp.cleanup()

    def test_native_session_reopens_without_model_and_restores_raw_after_quantization(self):
        path = self.folder/'Saved.muscriptor'; session.write(path,self.project)
        engine = worker.Engine.__new__(worker.Engine); engine.model = Mock()
        with patch.object(worker,'SUPPORT',self.folder), patch.object(worker,'emit') as emit:
            engine.load_session(path)
            self.assertEqual(engine.model.mock_calls, [])
            on = engine.render_cache(engine.rhythm_cache,{'mode':'manual','quantize':True,'subdivision':'4'})
            off = engine.render_cache(engine.rhythm_cache,{'mode':'manual','quantize':False,'bpm':200})
            self.assertNotEqual(decoded(on)[1],decoded(off)[1])
            np.testing.assert_allclose(decoded(off)[1],[.12,.51,1.24],atol=.0002)
            loaded = next(c.kwargs for c in emit.call_args_list if c.args[0]=='session_loaded')
            self.assertEqual(loaded['timing']['meter'],'6/8')
            self.assertTrue((self.folder/'last-session.muscriptor').exists())
            self.assertGreater(session.read(self.folder/'last-session.muscriptor')['recovery_saved_at'],0)
            engine.save_session(self.folder/'Copy.muscriptor',self.project['timing'])
            self.assertEqual(session.read(self.folder/'Copy.muscriptor')['midi'],self.project['midi'])

    def test_session_validation_rejects_invalid_data_and_ignores_paths(self):
        for changes in ({'version':99},{'midi':'not base64'}, {'duration':float('nan')},
                        {'detection':{'beats':[1,0]}},{'timing':{'stretch':True}}):
            with self.subTest(changes=changes), self.assertRaises(rhythm.RhythmError):
                session.validate({**self.project,**changes})
        normalized = session.validate({**self.project,'name':'../../secret.wav','audio_name':'C:\\Users\\somebody\\recording.wav'})
        self.assertEqual(normalized[-2: ],('secret.wav','recording.wav'))

    def test_midi_only_session_can_be_saved_and_recovered_repeatedly(self):
        project = session.make(self.raw, self.detection, 8, {'mode':'manual','bpm':170}, 'No audio.mid', None)
        path = self.folder/'No audio.muscriptor'; session.write(path, project)
        engine = worker.Engine.__new__(worker.Engine)
        with patch.object(worker, 'SUPPORT', self.folder), patch.object(worker, 'emit'):
            engine.load_session(path)
            engine.save_session(path, project['timing'])
            self.assertIsNone(session.validate(session.read(path))[4])
            engine.load_session(path)
            engine.load_session(self.folder/'last-session.muscriptor')
            self.assertEqual(engine.rhythm_cache['duration'], 8)
            np.testing.assert_allclose(decoded(engine.render_cache(engine.rhythm_cache, project['timing']))[1], [.12,.51,1.24], atol=.0002)

    def test_reexport_falls_back_when_selected_folder_disappears(self):
        engine = worker.Engine.__new__(worker.Engine)
        engine.rhythm_cache = dict(raw=self.raw, detection=self.detection, duration=2, wav=torch.zeros((1,0)), name='Music.wav')
        blocked = self.folder/'removed drive'; blocked.write_text('Not a folder')
        with patch.object(worker, 'SUPPORT', self.folder), patch.object(worker, 'emit') as emit:
            engine.reexport_session(self.project['timing'], blocked/'Chosen.mid')
        result = next(c.kwargs for c in emit.call_args_list if c.args[0]=='complete')
        self.assertTrue(result['needs_save'])
        self.assertEqual(Path(result['path']).parent, self.folder/'Results')
        self.assertEqual(Path(result['path']).name, 'Chosen.mid')
        self.assertTrue(Path(result['path']).is_file())

    def test_failed_open_preserves_previous_session_and_does_not_announce_new_one(self):
        path = self.folder/'Saved.muscriptor'; session.write(path,self.project)
        engine = worker.Engine.__new__(worker.Engine)
        previous = {'name':'Previous session'}; engine.rhythm_cache = previous
        with patch.object(worker, 'SUPPORT', self.folder), patch.object(worker, 'emit') as emit, \
             patch.object(worker, 'write_unique', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): engine.load_session(path)
        self.assertIs(engine.rhythm_cache, previous)
        self.assertNotIn('session_loaded', [c.args[0] for c in emit.call_args_list])

    def test_recovery_failure_does_not_claim_a_missing_recovery_file(self):
        engine = worker.Engine.__new__(worker.Engine)
        with patch.object(worker,'SUPPORT',self.folder), patch.object(worker,'emit'), \
             patch.object(engine,'session_project',return_value=self.project), \
             patch.object(session,'write',side_effect=OSError('disk full')):
            self.assertIsNone(engine.autosave_session(self.project['timing']))
            # An existing older recovery remains available if saving the new one fails.
            (self.folder/'last-session.muscriptor').write_text('{}')
            self.assertEqual(engine.autosave_session(self.project['timing']),str(self.folder/'last-session.muscriptor'))

    def test_failed_save_keeps_previous_session(self):
        path=self.folder/'Saved.muscriptor';session.write(path,self.project)
        previous=path.read_bytes()
        with patch('muscriptor.utils.session.os.replace',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):session.write(path,self.project)
        self.assertEqual(path.read_bytes(),previous)

    def test_web_native_interchange_and_recovery_across_server_restart(self):
        from fastapi.testclient import TestClient
        from muscriptor.server import create_app
        model=Mock(); recovery=self.folder/'recovery.muscriptor'
        with TestClient(create_app(model,recovery_path=recovery)) as client:
            r=client.post('/session/import',json=self.project,headers={'X-Client-Id':'a'})
            self.assertEqual(r.status_code,200,r.text)
            result=r.json();np.testing.assert_allclose(decoded(result)[1],[.12,.51,1.24],atol=.0002)
            exported=client.post('/session/export',json={'session':result['session'],'timing':self.project['timing']},headers={'X-Client-Id':'a'})
            self.assertEqual(exported.json()['midi'],self.project['midi'])
            self.assertEqual(client.post('/session/export',json={'session':result['session']},headers={'X-Client-Id':'b'}).status_code,404)
            self.assertEqual(client.post('/session/recovery',json=self.project).status_code,200)
        with TestClient(create_app(model,recovery_path=recovery)) as client:
            self.assertTrue(client.get('/session/recovery/status').json()['available'])
            recovered = client.get('/session/recovery').json()
            self.assertGreater(recovered.pop('recovery_saved_at'),0)
            self.assertEqual(recovered,self.project)
            self.assertEqual(client.post('/session/import',json={'format':'unknown'}).status_code,422)
        self.assertEqual(model.mock_calls,[])

    def installation_fixture(self):
        root=self.folder/'engine'; bundle=self.folder/'bundle'; bundle.mkdir();root.mkdir()
        (bundle/'package').mkdir(); (bundle/'package/transcription_model.py').write_text('new engine')
        (bundle/'worker.py').write_text('new worker')
        (root/'src').mkdir();(root/'src/worker.py').write_text('old worker')
        (root/'upstream/muscriptor').mkdir(parents=True);(root/'upstream/muscriptor/transcription_model.py').write_text('old engine')
        return root,bundle

    def test_upgrade_rolls_back_both_files_when_second_swap_fails(self):
        root,bundle=self.installation_fixture(); replace=engine_install.os.replace
        def fail_second(source,destination):
            if Path(source).name=='new-1':raise OSError('blocked')
            return replace(source,destination)
        with patch.object(engine_install.os,'replace',side_effect=fail_second):
            with self.assertRaises(OSError):engine_install.install(root,bundle/'worker.py',bundle/'package')
        self.assertEqual((root/'src/worker.py').read_text(),'old worker')
        self.assertEqual((root/'upstream/muscriptor/transcription_model.py').read_text(),'old engine')
        engine_install.install(root,bundle/'worker.py',bundle/'package')
        self.assertEqual((root/'src/worker.py').read_text(),'new worker')
        self.assertEqual((root/'upstream/muscriptor/transcription_model.py').read_text(),'new engine')

    def test_upgrade_recovers_interrupted_swap(self):
        root,bundle=self.installation_fixture(); tx=root/'.engine-update';tx.mkdir()
        (tx/'journal.json').write_text('[true,true]')
        (root/'src/worker.py').rename(tx/'backup-0');(root/'src/worker.py').write_text('interrupted new')
        engine_install.recover(root)
        self.assertEqual((root/'src/worker.py').read_text(),'old worker')
        self.assertFalse(tx.exists())

    def test_readiness_does_not_download_assets(self):
        from muscriptor.utils.capabilities import capabilities
        with patch('muscriptor.utils.download.download_if_necessary',side_effect=AssertionError('download')), \
             patch('muscriptor.utils.sheets.find_musescore',side_effect=OSError()), \
             patch('muscriptor.utils.capabilities.shutil.which',return_value=None), \
             patch('muscriptor.utils.capabilities.cached_asset',return_value=False):
            c=capabilities();self.assertTrue(c['midi']);self.assertFalse(c['sheets']);self.assertFalse(c['fluidsynth'])

if __name__=='__main__':unittest.main()
