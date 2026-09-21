"""Round-trip timing checks using actual MIDI bytes, with no model downloads."""
import base64
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'upstream'), str(Path(__file__).resolve().parents[1]/'src')]
import mido
import numpy as np
from muscriptor.utils.rhythm import Detection, Timeline, RhythmError, retime, options, clean_isolated_beats, stable_tempo_map, audio_pulse_candidate, detect
from muscriptor.utils.beats import read_bar_offset


def raw_midi(times):
    midi = mido.MidiFile(ticks_per_beat=9600)
    track = mido.MidiTrack([mido.MetaMessage('set_tempo', tempo=500000), mido.MetaMessage('track_name', name='acoustic piano')])
    midi.tracks.append(track)
    events=[]
    for i, sec in enumerate(times):
        events += [(sec, mido.Message('note_on', note=60+i%12, velocity=100)), (sec+.1, mido.Message('note_off', note=60+i%12))]
    last = 0
    for sec, msg in sorted(events, key=lambda x:x[0]):
        tick=round(sec*19200)
        track.append(msg.copy(time=tick-last));last=tick
    f=io.BytesIO();midi.save(file=f);return f.getvalue()


def decoded(result):
    midi=mido.MidiFile(file=io.BytesIO(base64.b64decode(result['data'])))
    sec=0; notes=[]
    for msg in midi:
        sec+=msg.time
        if msg.type=='note_on' and msg.velocity: notes.append(sec-read_bar_offset(midi))
    return midi, notes


class RhythmTests(unittest.TestCase):
    @staticmethod
    def pulse_audio(times, sr=16000):
        # A different sound/arrangement from the melodic stress-test fixtures.
        samples = np.zeros(round((times[-1]+.3)*sr), dtype=np.float32)
        phase = np.arange(round(.12*sr))/sr
        hit = np.sin(2*np.pi*83*phase)*np.exp(-32*phase)
        for at in times:
            start = round(at*sr)
            samples[start:start+len(hit)] += hit
        return samples

    def test_audio_pulse_recovers_supported_change_without_moving_notes(self):
        import torch
        truth = .3 + np.r_[np.arange(16)*.5, 8+np.arange(20)/3]
        guessed = np.arange(.3, truth[-1]+.001, .5)
        signal = self.pulse_audio(truth)
        with patch('beat_this.inference.Audio2Beats') as model:
            model.return_value.return_value = (guessed, guessed[::4])
            result = detect(torch.tensor(signal[None, :]), 16000)
        self.assertTrue(result.pulse_verified)
        self.assertEqual(result.downbeats, [])  # Do not carry the wrong bars across.
        np.testing.assert_allclose(result.beats, truth, atol=.015)
        timeline = Timeline({}, result, len(signal)/16000)
        np.testing.assert_allclose(60*np.diff(timeline.q)/np.diff(timeline.x), [120, 180], atol=.1)
        _, notes = decoded(retime(raw_midi([.1, 3, 8.31, 12.43]), timeline))
        np.testing.assert_allclose(notes, [.1, 3, 8.31, 12.43], atol=.0002)

    def test_audio_pulse_accepts_later_agreement_and_ignores_one_tail_guess(self):
        attacks = .3 + np.arange(40)*.5
        signal = self.pulse_audio(attacks)
        guessed = np.r_[np.arange(.3, 6, .7), attacks[12:], attacks[-1]+.5]
        recovered = audio_pulse_candidate(signal, 16000, guessed)
        self.assertIsNotNone(recovered)
        np.testing.assert_allclose(recovered, attacks, atol=.015)

    def test_audio_pulse_does_not_reinterpret_subdivisions(self):
        attacks = .3 + np.arange(80)*.25
        self.assertIsNone(audio_pulse_candidate(self.pulse_audio(attacks), 16000, attacks[::2]))

    def test_audio_pulse_rejects_irregular_or_missing_attacks(self):
        for intervals in (np.tile([.3, .7], 20), np.r_[np.full(20, .5), 2., np.full(20, .5)]):
            attacks = .3 + np.r_[0, np.cumsum(intervals)]
            self.assertIsNone(audio_pulse_candidate(self.pulse_audio(attacks), 16000, attacks))

    def test_optional_pulse_failure_keeps_model_detection(self):
        import torch
        beats = .3 + np.arange(24)*.5
        with patch('beat_this.inference.Audio2Beats') as model, patch('muscriptor.utils.rhythm.audio_pulse_candidate', side_effect=RuntimeError('verification unavailable')):
            model.return_value.return_value = (beats, beats[::4])
            result = detect(torch.tensor(self.pulse_audio(beats)[None, :]), 16000)
        np.testing.assert_array_equal(result.beats, beats)
        self.assertFalse(result.pulse_verified)

    def test_verified_pulse_session_roundtrip_and_legacy_default(self):
        from muscriptor.utils import session
        beats = (.3+np.arange(30)*.5).tolist()
        d = Detection(beats, [], 'Audio pulse recovered', True)
        project = session.make(raw_midi([.4, 3, 10]), d, 16, {}, 'test.wav')
        _, reopened, duration, settings, *_ = session.validate(project)
        self.assertTrue(reopened.pulse_verified)
        np.testing.assert_array_equal(Timeline(settings, reopened, duration).x, Timeline({}, d, 16).x)
        del project['detection']['pulse_verified']
        self.assertFalse(session.validate(project)[1].pulse_verified)
        project['detection']['pulse_verified'] = 'yes'
        with self.assertRaises(RhythmError):
            session.validate(project)

    def test_remove_isolated_extra_beat_without_moving_neighbors(self):
        original = np.arange(40)*.5
        noisy = np.sort(np.r_[original, 4.15, 12.8])
        beats, downs = clean_isolated_beats(noisy, np.r_[original[::4], 4.15])
        np.testing.assert_array_equal(beats, original)
        np.testing.assert_array_equal(downs, original[::4])

    def test_cleanup_keeps_real_tempo_changes_and_missing_beats(self):
        beats = np.r_[np.arange(20)*.5, 10+np.arange(20)*.25, 15+np.arange(20)*.6]
        beats = np.delete(beats, 8)
        cleaned, downs = clean_isolated_beats(beats, beats[::4])
        np.testing.assert_array_equal(cleaned, beats)
        np.testing.assert_array_equal(downs, beats[::4])

    def test_variable_tempo_preserves_seconds_and_aligns_beats(self):
        beats=np.cumsum(np.r_[0, np.linspace(.42,.8,39)])
        detection=Detection(beats.tolist(), beats[::4].tolist())
        times=[float(t+.032) for t in beats[:-1]]
        timeline=Timeline({'meter':'4/4'}, detection, float(beats[-1]))
        result=retime(raw_midi(times), timeline)
        midi, notes=decoded(result)
        np.testing.assert_allclose(notes,times,atol=.0002)
        count = sum(m.type=='set_tempo' for m in midi.tracks[0])
        self.assertGreater(count, 1)
        self.assertLess(count, 15)
        # Auto approximates a musical grid; note playback still stays exact.
        x, pulse, _ = stable_tempo_map(beats)
        np.testing.assert_allclose(np.interp(np.arange(len(beats)), pulse, x), beats, atol=.065)
        self.assertIn('variable tempo',result['summary'])

    def test_auto_jitter_does_not_become_hundreds_of_tempo_events(self):
        ideal = .3 + np.arange(400)*60/140
        beats = ideal + np.random.default_rng(7).normal(0, .01, len(ideal))
        timeline = Timeline({}, Detection(beats.tolist(), []), 175)
        result = retime(raw_midi([.1, 3, 40, 100, 170]), timeline)
        midi, notes = decoded(result)
        tempos = [m.tempo for m in midi.tracks[0] if m.type == 'set_tempo']
        self.assertEqual(len(tempos), 1)
        self.assertAlmostEqual(60_000_000/tempos[0], 140, delta=.1)
        np.testing.assert_allclose(notes, [.1, 3, 40, 100, 170], atol=.0003)

    def test_auto_keeps_supported_abrupt_changes(self):
        beats = np.r_[np.arange(20)*.5, 10+np.arange(20)*.25, 15+np.arange(20)*.6]
        result = retime(raw_midi([.1, 10.1, 15.1, 24]), Timeline({}, Detection(beats.tolist(), []), 27))
        midi, notes = decoded(result)
        tempos = [60_000_000/m.tempo for m in midi.tracks[0] if m.type == 'set_tempo']
        np.testing.assert_allclose(tempos, [120, 240, 100], atol=.001)
        np.testing.assert_allclose(notes, [.1, 10.1, 15.1, 24], atol=.0002)

    def test_auto_normalizes_near_integer_bpm_without_moving_notes(self):
        beats = .3 + np.arange(603)*60/169.99247
        for meter in ('4/4', '6/8'):
            timeline = Timeline({'meter': meter}, Detection(beats.tolist(), beats[::4].tolist()), 213)
            self.assertAlmostEqual(timeline.bpm, 170, places=9)
            self.assertAlmostEqual(float(timeline.seconds_at_q(0)), .3, places=9)
            result = retime(raw_midi([.1, 1, 80, 212]), timeline)
            midi, notes = decoded(result)
            tempo = next(m.tempo for m in midi.tracks[0] if m.type == 'set_tempo')
            self.assertEqual(tempo, round(60_000_000/(170*timeline.unit)))
            np.testing.assert_allclose(notes, [.1, 1, 80, 212], atol=.0004)

    def test_auto_keeps_fractional_bpm_when_difference_or_drift_is_too_large(self):
        for bpm, duration in ((169.94, 10), (169.96, 600)):
            beats = .3 + np.arange(int(duration*bpm/60))*60/bpm
            timeline = Timeline({}, Detection(beats.tolist(), []), duration)
            self.assertAlmostEqual(timeline.bpm, bpm, places=8)

    def test_normalization_leaves_manual_bpm_and_anchors_exact(self):
        beats = .3 + np.arange(400)*60/169.99
        detection = Detection(beats.tolist(), [])
        for settings in ({'mode': 'manual', 'bpm': 169.99},
                         {'anchors': [[0, 1], [60/169.99*100, 101]]}):
            timeline = Timeline(settings, detection, 150)
            self.assertAlmostEqual(timeline.bpm, 169.99, places=8)

    def test_normalization_does_not_round_an_uncertain_short_estimate(self):
        beats = .3 + np.arange(5)*60/169.99
        timeline = Timeline({}, Detection(beats.tolist(), []), 2)
        self.assertAlmostEqual(timeline.bpm, 169.99, places=8)
        self.assertTrue(timeline.warnings)

    def test_auto_handles_isolated_missing_and_extra_beats(self):
        ideal = .3 + np.arange(120)*.5
        beats = np.sort(np.r_[np.delete(ideal, 40), 20.45, 38.95])
        x, pulse, uncertain = stable_tempo_map(beats)
        self.assertLessEqual(len(x), 3)
        np.testing.assert_allclose(60*np.diff(pulse)/np.diff(x), 120, atol=.1)

    def test_auto_bridges_unreliable_passage_without_spikes(self):
        beats = np.r_[np.arange(30)*.4, 12+np.cumsum([.12,.14,.58,.16,.21,.13,.73,.18,.2,.55,.17,.6]), 17+np.arange(100)*.5]
        timeline = Timeline({}, Detection(beats.tolist(), []), 68)
        self.assertTrue(any('unreliable' in warning for warning in timeline.warnings))
        tempos = 60*np.diff(timeline.q)/np.diff(timeline.x)
        self.assertLess(len(tempos), 10)
        self.assertTrue(np.all((tempos >= 100) & (tempos <= 170)), tempos)

    def test_compound_meter_and_beat_unit(self):
        beats=np.arange(20)*.75
        result=retime(raw_midi([0,.75,1.5]),Timeline({'meter':'6/8'},Detection(beats.tolist(),beats[::2].tolist()),14.25))
        midi, notes=decoded(result)
        sig=next(m for m in midi.tracks[0] if m.type=='time_signature')
        tempo=next(m for m in midi.tracks[0] if m.type=='set_tempo')
        self.assertEqual((sig.numerator,sig.denominator,sig.clocks_per_click),(6,8,36))
        self.assertEqual(tempo.tempo,500000)
        self.assertAlmostEqual(result['beat_grid']['bpm'],80)
        self.assertEqual(result['beat_grid']['unit'],'dotted-quarter')
        np.testing.assert_allclose(notes,[0,.75,1.5],atol=.0001)

    def test_manual_grid_preserves_playback_and_pickup(self):
        result=retime(raw_midi([.1,.5,1.2,5]),Timeline({'mode':'manual','bpm':95,'meter':'3/4','first_downbeat':.5},Detection([],[]),6))
        midi, notes=decoded(result)
        np.testing.assert_allclose(notes,[.1,.5,1.2,5],atol=.0001)
        self.assertEqual(read_bar_offset(midi),0)
        self.assertFalse(result['quantized'])

    def test_manual_bpm_never_changes_speed_or_start(self):
        beats=np.arange(20)*.75
        for bpm in (40, 80, 120, 200):
            for meter in ('4/4', '6/8'):
                result=retime(raw_midi([.1,.75,1.5,10]),Timeline({'mode':'manual','bpm':bpm,'meter':meter,'first_downbeat':.3},Detection(beats.tolist(),beats[::4].tolist()),14))
                midi, notes=decoded(result)
                np.testing.assert_allclose(notes,[.1,.75,1.5,10],atol=.0002)
                self.assertEqual(read_bar_offset(midi),0)
                self.assertNotIn('stretched',result)
                np.testing.assert_allclose([n['start'] for n in result['notes']],notes,atol=.0002)

    def test_failed_detector_manual_anchors_preserve_timing(self):
        result=retime(raw_midi([1,2,3]),Timeline({'mode':'manual','bpm':120,'meter':'4/4','anchors':'1, 1\n3, 3'},Detection([],[]),4))
        midi, notes=decoded(result)
        np.testing.assert_allclose(notes,[1,2,3],atol=.0001)
        self.assertEqual(read_bar_offset(midi),0)
        with self.assertRaises(RhythmError):
            Timeline({'mode':'manual','stretch':True},Detection([],[]),4)

    def test_manual_grid_does_not_repeat_unused_detector_warning(self):
        d = Detection([0,.5,1,1.2,1.5,2], [], 'Abrupt beat-spacing changes detected.')
        for settings in ({'mode':'manual','bpm':120}, {'anchors':'0, 1\n2, 5'}):
            self.assertEqual(Timeline(settings,d,3).warnings, [])

    def test_quantize_separate_from_tempo(self):
        d=Detection(list(np.arange(20)*.5),list(np.arange(5)*2.))
        a=retime(raw_midi([.032,.53]),Timeline({'meter':'4/4'},d,9.5))
        b=retime(raw_midi([.032,.53]),Timeline({'meter':'4/4','quantize':True,'subdivision':'4'},d,9.5))
        np.testing.assert_allclose(decoded(a)[1],[.032,.53],atol=.0001)
        np.testing.assert_allclose(decoded(b)[1],[0,.5],atol=.0001)

    def test_fallback_is_disclosed_and_never_quantized(self):
        result=retime(raw_midi([.12,.9]),Timeline({'quantize':True},Detection([],[],'Tempo could not be detected'),2))
        self.assertIn('placeholder 120',result['summary'])
        self.assertFalse(result['quantized'])
        np.testing.assert_allclose(decoded(result)[1],[.12,.9],atol=.0001)

    def test_meter_changes_have_correct_ticks(self):
        result=retime(raw_midi([0,10]),Timeline({'mode':'manual','meter':'4/4','meter_changes':'3, 6/8\n5, 3/4'},Detection([],[]),12))
        midi,_=decoded(result); tick=0; changes=[]
        for msg in midi.tracks[0]:
            tick+=msg.time
            if msg.type=='time_signature':changes.append((tick/midi.ticks_per_beat,msg.numerator,msg.denominator))
        self.assertEqual(changes,[(0,4,4),(8,6,8),(14,3,4)])

    def test_invalid_inputs(self):
        for settings in ({'bpm':'nan'},{'bpm':True},{'mode':'other'},{'meter':'6/3'},{'anchors':'1, 1'}, {'anchors':'2, 1\n1, 2'}, {'meter_changes':'9, 3/4\n8, 4/4'}, {'stretch':True}):
            with self.subTest(settings=settings), self.assertRaises(RhythmError): options(settings)

    def test_web_cached_export_matches_shared_export(self):
        from fastapi.testclient import TestClient
        from muscriptor.server import create_app
        from muscriptor.events import NoteStartEvent, NoteEndEvent
        import soundfile as sf
        model=Mock();start=NoteStartEvent(60,.5,0,'acoustic_piano')
        model.transcribe.return_value=[start,NoteEndEvent(.7,start)]
        raw=raw_midi([.5]);model.events_to_midi_bytes.return_value=raw
        audio=io.BytesIO();sf.write(audio,np.zeros(32000),16000,format='WAV')
        d=Detection([],[],'Tempo could not be detected')
        with patch('muscriptor.utils.rhythm.detect',return_value=d), TestClient(create_app(model)) as client:
            response=client.post('/transcribe',files={'file':('test.wav',audio.getvalue(),'audio/wav')},data={'timing':'{}'},headers={'X-Client-Id':'a'})
            import json
            payload=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data:')][-1]
            settings={'mode':'manual','bpm':90,'meter':'6/8'}
            response=client.post('/rhythm/reexport',json={'session':payload['session'],'timing':settings},headers={'X-Client-Id':'a'})
            self.assertEqual(response.status_code,200,response.text)
            expected=retime(raw,Timeline(settings,d,2))
            self.assertEqual(response.json()['data'],expected['data'])
            self.assertEqual(model.transcribe.call_count,1)
            self.assertEqual(client.post('/rhythm/reexport',json={'session':payload['session']},headers={'X-Client-Id':'b'}).status_code,404)

if __name__=='__main__': unittest.main()
