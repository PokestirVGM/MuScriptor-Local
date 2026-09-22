"""Partial export checks use controlled note streams, without model downloads."""
import base64
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import worker
import numpy as np
import soundfile as sf
import torch
import mido
from muscriptor.events import NoteStartEvent, NoteEndEvent, ProgressEvent
from muscriptor.transcription_model import TranscriptionModel
from muscriptor.utils.partial import FinishableTranscription
from muscriptor.utils import rhythm, session


def midi_model():
    model = TranscriptionModel.__new__(TranscriptionModel)
    model._program_for_instrument = lambda _: 0
    return model


def sounding_times(data):
    time = 0; notes = []
    for event in mido.MidiFile(file=io.BytesIO(data)):
        time += event.time
        if event.type in ('note_on', 'note_off'):
            notes.append((event.type, event.note, time))
    return notes


class FinishTests(unittest.TestCase):
    def test_cutoff_discards_inflight_notes_closes_held_notes_and_closes_generator(self):
        finish = threading.Event(); closed = []
        held = NoteStartEvent(60, .125, 0, 'acoustic_piano')
        extra = NoteStartEvent(64, 5.25, 1, 'acoustic_piano')
        def stream():
            try:
                yield ProgressEvent(0, 3)
                yield held
                yield ProgressEvent(1, 3)
                yield extra
                finish.set()
                yield NoteEndEvent(6, held)
                self.fail('Generation continued after Finish')
            finally:
                closed.append(True)
        run = FinishableTranscription(stream(), 12.3, finish)
        list(run)
        self.assertTrue(run.partial); self.assertEqual(run.duration, 5)
        self.assertTrue(closed); self.assertFalse(run.can_finish)
        events = sounding_times(midi_model().events_to_midi_bytes(iter(run.events)))
        self.assertEqual([e[:2] for e in events], [('note_on',60),('note_off',60)])
        self.assertAlmostEqual(events[0][2], .125, places=3)
        self.assertAlmostEqual(events[1][2], 5, places=3)

    def test_full_completion_preserves_final_note_off_and_fractional_last_section(self):
        finish = threading.Event()
        note = NoteStartEvent(60, 5.1, 0, 'acoustic_piano')
        def stream():
            yield ProgressEvent(0, 2); yield ProgressEvent(1, 2)
            yield note; yield ProgressEvent(2, 2)
            finish.set()  # a late click must not discard the decoder's final note-offs
            yield NoteEndEvent(7.2, note)
        run = FinishableTranscription(stream(), 7.3, finish);list(run)
        self.assertFalse(run.partial);self.assertEqual(run.duration,7.3)
        self.assertIsInstance(run.events[-1], NoteEndEvent)

    def test_finish_at_boundary_does_not_generate_another_section(self):
        finish=threading.Event()
        def stream():
            yield ProgressEvent(0,3);yield ProgressEvent(1,3)
            self.fail('Next section was unnecessarily generated')
        run=FinishableTranscription(stream(),15,finish)
        iterator=iter(run);next(iterator);next(iterator);finish.set()
        self.assertEqual(list(iterator),[]);self.assertTrue(run.partial)

    def test_command_reader_handles_finish_while_inference_thread_is_busy(self):
        lines=queue.Queue()
        inbox=worker.CommandInbox(iter(lines.get,None))
        with inbox.transcription('current') as finish:
            lines.put(json.dumps({'action':'finish_transcription','run_id':'old'})+'\n')
            lines.put(json.dumps({'action':'plan'})+'\n')
            self.assertEqual(json.loads(next(iter(inbox)))['action'],'plan')
            self.assertFalse(finish.is_set())
            lines.put(json.dumps({'action':'finish_transcription','run_id':'current'})+'\n')
            self.assertTrue(finish.wait(2))
        with inbox.transcription('next') as finish:
            lines.put(json.dumps({'action':'finish_transcription','run_id':'current'})+'\n')
            lines.put('{}\n');next(iter(inbox));self.assertFalse(finish.is_set())
        lines.put(None)

    def test_command_reader_does_not_hold_stdin_during_worker_shutdown(self):
        script = "from worker import CommandInbox; import sys; inbox=CommandInbox(sys.stdin); next(iter(inbox)); print('done',flush=True)"
        # sys.path changes in this test process are not inherited by a child.
        # Resolve worker from its source directory on a clean Windows runner too.
        process=subprocess.Popen([sys.executable,'-c',script],cwd=Path(worker.__file__).parent,
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            process.stdin.write('{"action":"quit"}\n');process.stdin.flush()
            code = process.wait(timeout=5)
            errors = process.stderr.read()
            self.assertEqual(code,0,errors)
            self.assertEqual(process.stdout.read().strip(),'done')
            self.assertNotIn('Fatal Python error',errors)
        finally:
            if process.poll() is None:process.kill();process.wait()
            process.stdin.close();process.stdout.close();process.stderr.close()

    def test_worker_partial_session_audio_and_reexport_preserve_timing(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'loop.wav';sf.write(source,np.zeros(16000*12),16000)
            finish=threading.Event();model=midi_model()
            held=NoteStartEvent(60,.125,0,'acoustic_piano')
            def stream(*args,**kwargs):
                yield ProgressEvent(0,3);yield held;yield ProgressEvent(1,3)
                finish.set();yield NoteEndEvent(6,held)
            model.transcribe=stream
            engine=worker.Engine.__new__(worker.Engine);engine.model=model;engine.model_size='small';engine.device='cpu';engine.load=lambda:None
            events=[]
            detection=rhythm.Detection([],[])
            with patch.object(worker,'emit',lambda kind,**kw:events.append({'type':kind,**kw})),patch.object(worker,'SUPPORT',Path(folder)),patch.object(rhythm,'detect',return_value=detection) as detect:
                engine.transcribe(source,Path(folder)/'result.mid',timing={'mode':'manual','bpm':170},finish=finish)
                complete=next(e for e in events if e['type']=='complete')
                self.assertTrue(complete['partial']);self.assertTrue(complete['path'].endswith('_partial.mid'))
                self.assertEqual(detect.call_args.args[0].shape[-1],5*16000)
                project=session.read(Path(folder)/'last-session.muscriptor')
                raw,_,duration,_,audio,_,_=session.validate(project)
                self.assertEqual(duration,5);self.assertEqual(sf.info(io.BytesIO(audio)).duration,5)
                self.assertIsNone(engine.rhythm_cache['key'])
                changed=engine.render_cache(engine.rhythm_cache,{'mode':'manual','bpm':120})
                for data in [Path(complete['path']).read_bytes(),base64.b64decode(changed['data']),raw]:
                    times=sounding_times(data)
                    self.assertAlmostEqual(times[0][2],.125,places=3);self.assertAlmostEqual(times[-1][2],5,places=3)

    def test_web_finish_is_run_and_client_scoped_and_preserves_partial_session(self):
        from fastapi.testclient import TestClient
        from muscriptor.server import create_app
        checkpoint=threading.Event();resume=threading.Event();closed=threading.Event()
        held=NoteStartEvent(60,.125,0,'acoustic_piano');model=midi_model()
        def stream(*args,**kwargs):
            try:
                yield ProgressEvent(0,3);yield held;yield ProgressEvent(1,3)
                checkpoint.set()
                if not resume.wait(5):raise RuntimeError('Test timed out')
                yield NoteStartEvent(64,5.5,1,'acoustic_piano')
                yield NoteEndEvent(6,held)
            finally:closed.set()
        model.transcribe=stream
        wav=io.BytesIO();sf.write(wav,np.zeros(16000*12),16000,format='WAV')
        detection=rhythm.Detection([],[])
        with patch.object(rhythm,'detect',return_value=detection),TestClient(create_app(model)) as client,ThreadPoolExecutor() as pool:
            future=pool.submit(client.post,'/transcribe',files={'file':('loop.wav',wav.getvalue(),'audio/wav')},data={'run_id':'run1','timing':json.dumps({'mode':'manual','bpm':170})},headers={'X-Client-Id':'a'})
            try:
                self.assertTrue(checkpoint.wait(5))
                self.assertEqual(client.post('/transcribe/finish',json={'run_id':'run1'},headers={'X-Client-Id':'b'}).status_code,404)
                self.assertEqual(client.post('/transcribe/finish',json={'run_id':'stale'},headers={'X-Client-Id':'a'}).status_code,404)
                reply=client.post('/transcribe/finish',json={'run_id':'run1'},headers={'X-Client-Id':'a'})
                self.assertEqual(reply.status_code,200,reply.text);self.assertEqual(reply.json()['completed_seconds'],5)
            finally:resume.set()
            response=future.result(timeout=10);self.assertEqual(response.status_code,200,response.text)
            events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
            result=next(e for e in events if e['type']=='transcription_complete')
            self.assertTrue(result['partial']);self.assertEqual(result['duration'],5);self.assertTrue(closed.is_set())
            self.assertEqual(len(result['notes']),1)
            times=sounding_times(base64.b64decode(result['data']))
            self.assertAlmostEqual(times[0][2],.125,places=3);self.assertAlmostEqual(times[-1][2],5,places=3)
            saved=client.post('/session/export',json={'session':result['session']},headers={'X-Client-Id':'a'})
            self.assertEqual(saved.status_code,200);self.assertEqual(saved.json()['duration'],5)
            self.assertEqual(client.post('/transcribe/finish',json={'run_id':'run1'},headers={'X-Client-Id':'a'}).status_code,404)

    def test_web_cancel_is_scoped_and_releases_engine_without_exporting(self):
        from fastapi.testclient import TestClient
        from muscriptor.server import create_app
        checkpoint=threading.Event(); resume=threading.Event(); closed=threading.Event()
        model=midi_model()
        def stream(*args, **kwargs):
            try:
                yield ProgressEvent(0,3)
                checkpoint.set()
                if not resume.wait(5): raise RuntimeError('Test timed out')
                yield ProgressEvent(1,3)
                self.fail('Cancelled transcription continued')
            finally: closed.set()
        model.transcribe=stream
        wav=io.BytesIO(); sf.write(wav,np.zeros(16000*12),16000,format='WAV')
        with TestClient(create_app(model)) as client, ThreadPoolExecutor() as pool:
            future=pool.submit(client.post,'/transcribe',files={'file':('song.wav',wav.getvalue(),'audio/wav')},data={'run_id':'active'},headers={'X-Client-Id':'a'})
            try:
                self.assertTrue(checkpoint.wait(5))
                for run_id, owner in [('active','b'), ('old','a'), ('active','')]:
                    self.assertEqual(client.post('/transcribe/cancel',json={'run_id':run_id},headers={'X-Client-Id':owner}).status_code,404)
                self.assertEqual(client.post('/transcribe/cancel',json={'run_id':'active'},headers={'X-Client-Id':'a'}).status_code,200)
            finally: resume.set()
            result=future.result(timeout=10)
            self.assertNotIn('transcription_complete',result.text)
            self.assertTrue(closed.is_set())
            self.assertEqual(client.post('/transcribe/cancel',json={'run_id':'active'},headers={'X-Client-Id':'a'}).status_code,404)
            model.transcribe=lambda *a,**kw: iter([ProgressEvent(0,1),ProgressEvent(1,1)])
            with patch.object(rhythm,'detect',return_value=rhythm.Detection([],[])):
                next_run=client.post('/transcribe',files={'file':('next.wav',wav.getvalue(),'audio/wav')},data={'run_id':'next','timing':'{"mode":"manual","bpm":120}'},headers={'X-Client-Id':'b'})
            self.assertEqual(next_run.status_code,200)
            self.assertIn('transcription_complete',next_run.text)
