"""Independent arrangements for percussion evidence, overrides, and MIDI export."""
import base64
import copy
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import mido
import numpy as np
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'upstream'),str(Path(__file__).parent)]
from muscriptor.utils.rhythm_evidence import percussion_meter
from muscriptor.utils.rhythm import Detection, Timeline, retime, detect, RhythmError
from muscriptor.utils import session
from test_rhythm_edges import performance, events_in_seconds


def arrangement(sections, sr=22050, swing=False, accents=True, seed=828):
    """sections=(numerator, denominator, grouping, bars, quarter BPM)."""
    rng=np.random.default_rng(seed);events=[];truth=[];segments=[];start=.4
    for n,d,groups,bars,bpm in sections:
        segments.append((start,n,d));quarter=60/bpm;bar=n*4/d*quarter
        for b in range(bars):
            offset=0.
            for j,g in enumerate(groups):
                t=start+b*bar+offset;truth.append(t)
                events.append((t,'low',(.66 if j==0 and accents else .38)*rng.uniform(.96,1.04)))
                offset+=g*4/d*quarter
            if swing:
                for q in range(n):
                    events.extend([(start+b*bar+(q+o)*quarter,'high',.09) for o in (0,.63)])
            else:
                for q in np.arange(0,n*4/d,.5):
                    events.append((start+b*bar+q*quarter,'high',.09))
        start+=bars*bar
    audio=np.zeros(round((start+.3)*sr))
    for at,band,gain in events:
        t=np.arange(round(.075*sr))/sr
        wave=(np.sin(2*np.pi*(95*t-130*t*t))*np.exp(-55*t) if band=='low' else rng.normal(size=len(t))*np.exp(-130*t))
        i=round(at*sr);audio[i:i+len(t)]+=gain*wave
    # A separate accompaniment timbre, not the development fixture's 330 Hz tone.
    for at in np.arange(.4,start,.31):
        t=np.arange(round(.06*sr))/sr;i=round(at*sr)
        audio[i:i+len(t)]+=.008*np.sin(2*np.pi*587*t)*np.exp(-55*t)
    return audio,np.array(truth),segments


class PercussionEvidenceTests(unittest.TestCase):
    def evidence(self,sections,**kwargs):
        signal,truth,segments=arrangement(sections,**kwargs)
        sr=kwargs.get('sr',22050)
        guessed=np.arange(.4,len(signal)/sr-.4,60/sections[0][-1])
        found=percussion_meter(signal,sr,guessed)
        self.assertIsNotNone(found)
        return Detection(**found,pulse_verified=True),signal,truth,segments

    def test_compound_meters_at_unseen_tempos_and_sample_rates(self):
        for n,bpm,sr in [(6,156,22050),(9,96,44100),(12,180,16000)]:
            with self.subTest(meter=n,bpm=bpm,sr=sr):
                d,a,truth,_=self.evidence([(n,8,[3]*(n//3),8,bpm)],sr=sr)
                timeline=Timeline({},d,len(a)/sr);grid=timeline.display_grid()
                self.assertEqual(grid['meter'],f'{n}/8')
                self.assertAlmostEqual(timeline.bpm,bpm/1.5,delta=.3)
                beats=np.array(grid['beats'])
                self.assertLess(np.max(np.min(abs(truth[:,None]-beats),axis=1)),.02)

    def test_swing_uses_primary_beats_not_triplet_meter(self):
        d,a,truth,_=self.evidence([(4,4,[1]*4,8,144)],swing=True)
        t=Timeline({},d,len(a)/22050)
        self.assertEqual(t.meter,(4,4))
        self.assertAlmostEqual(t.bpm,144,delta=.3)

    def test_unequal_groups_do_not_create_tempo_spikes(self):
        d,a,truth,_=self.evidence([(7,8,[3,2,2],8,156)])
        t=Timeline({},d,len(a)/22050)
        self.assertEqual(t.meter,(7,8))
        self.assertLess(np.ptp(t.periods),.005)
        beats=np.array(t.display_grid()['beats'])
        self.assertLess(np.max(np.min(abs(truth[:,None]-beats),axis=1)),.02)

    def test_meter_and_tempo_changes_survive_session_and_midi(self):
        d,a,truth,segments=self.evidence([(4,4,[1]*4,6,120),(6,8,[3,3],6,150),(7,8,[2,3,2],6,150)])
        self.assertEqual([tuple(s[1:3]) for s in d.meter_segments],[(4,4),(6,8),(7,8)])
        raw=performance([(1.123,mido.Message('note_on',note=60)),(20.527,mido.Message('note_off',note=60))])
        project=session.make(raw,d,len(a)/22050,{},'changing.wav')
        loaded=session.validate(project)[1]
        self.assertEqual(loaded.meter_segments,d.meter_segments)
        timeline=Timeline({},loaded,len(a)/22050);rendered=retime(raw,timeline)
        before,after=events_in_seconds(raw),events_in_seconds(base64.b64decode(rendered['data']))
        np.testing.assert_allclose([a[0] for a in before],[a[0] for a in after],atol=.0001,rtol=0)
        seconds=0;signatures=[]
        for m in mido.MidiFile(file=io.BytesIO(base64.b64decode(rendered['data']))):
            seconds+=m.time
            if m.type=='time_signature':signatures.append((seconds,m.numerator,m.denominator))
        for at,n,den in segments:
            self.assertTrue(any(abs(t-at)<.03 and (n,den)==(nn,dd) for t,nn,dd in signatures),signatures)
        beats=np.array(timeline.display_grid()['beats'])
        self.assertLess(np.max(np.min(abs(truth[:,None]-beats),axis=1)),.03)

    def test_no_meter_invented_for_missing_accents_or_silence(self):
        signal,_,_=arrangement([(4,4,[1]*4,8,120)],accents=False)
        guessed=np.arange(.4,16,.5)
        self.assertIsNone(percussion_meter(signal,22050,guessed))
        self.assertIsNone(percussion_meter(np.zeros(22050*10),22050,guessed))

    def test_short_or_inconsistent_sections_are_rejected(self):
        for sections in [[(6,8,[3,3],3,120)],[(4,4,[1]*4,6,120),(3,4,[1]*3,2,120),(4,4,[1]*4,6,120)]]:
            signal,_,_=arrangement(sections)
            self.assertIsNone(percussion_meter(signal,22050,np.arange(.4,len(signal)/22050,.5)))

    def test_manual_meter_and_changes_override_suggestions(self):
        d,a,_,_=self.evidence([(6,8,[3,3],8,120)])
        t=Timeline({'meter':'3/4','meter_changes':'3, 5/4'},d,len(a)/22050)
        self.assertEqual(t.meter,(3,4));self.assertFalse(t.meter_inferred)
        self.assertEqual(t.groupings,[])
        self.assertEqual(t.meters[-1][1],(5,4))
        self.assertAlmostEqual(t.bpm,120,delta=.2)

    def test_invalid_saved_meter_evidence_is_rejected(self):
        d,a,_,_=self.evidence([(6,8,[3,3],8,120)])
        project=session.make(performance([]),d,len(a)/22050,{},'test.wav')
        for invalid in [[[-.5,6,8,[3,3]]],[[.4,6,8,[2,2]]],[[float('nan'),6,8,[3,3]]],[[.4,True,8,[1]]],[[.4,6,8,[3,3]],[.3,6,8,[3,3]]],[[999,6,8,[3,3]]]]:
            copy_=copy.deepcopy(project);copy_['detection']['meter_segments']=invalid
            with self.assertRaises(RhythmError):session.validate(copy_)
        del project['detection']['meter_segments']
        self.assertEqual(session.validate(project)[1].meter_segments,[])

    def test_optional_evidence_failure_preserves_neural_result(self):
        import torch
        beats=np.arange(.4,16,.5)
        with patch('beat_this.inference.Audio2Beats') as model, patch('muscriptor.utils.rhythm.audio_pulse_candidate',return_value=None), patch('muscriptor.utils.rhythm_evidence.percussion_meter',side_effect=RuntimeError('test failure')):
            model.return_value.return_value=(beats,beats[::4])
            d=detect(torch.zeros(1,22050*17),22050)
        np.testing.assert_array_equal(d.beats,beats)
        self.assertEqual(d.meter_segments,[])

    def test_missing_percussion_passage_is_not_bridged_by_meter_evidence(self):
        signal,_,_=arrangement([(4,4,[1]*4,10,120)])
        signal[4*22050:5*22050]=0
        self.assertIsNone(percussion_meter(signal,22050,np.arange(.4,len(signal)/22050,.5)))

    def test_new_meter_evidence_cannot_reinterpret_unrelated_model_tempo(self):
        signal,_,_=arrangement([(4,4,[1]*4,10,120)])
        self.assertIsNone(percussion_meter(signal,22050,np.arange(.4,len(signal)/22050,2.0)))

    def test_regular_backbeat_does_not_halve_consistent_neural_bars(self):
        # Same accents could be written as 2/4 or be the backbeat in 4/4.
        signal,_,_=arrangement([(2,4,[1,1],16,120)])
        beats=np.arange(.4,len(signal)/22050-.3,.5)
        self.assertIsNone(percussion_meter(signal,22050,beats,beats[::4]))
