"""MIDI event, articulation, and meter stress cases independent of audio inference."""
import base64
import io
from pathlib import Path
import sys
import unittest
import numpy as np
import mido
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'upstream'))
from muscriptor.utils.rhythm import Detection, Timeline, retime


def performance(events):
    midi=mido.MidiFile(ticks_per_beat=9600)
    track=mido.MidiTrack([mido.MetaMessage('set_tempo',tempo=500000),mido.MetaMessage('track_name',name='acoustic piano')]);midi.tracks.append(track)
    last=0
    for seconds,message in sorted(events,key=lambda e:e[0]):
        tick=round(seconds*19200);track.append(message.copy(time=tick-last));last=tick
    out=io.BytesIO();midi.save(file=out);return out.getvalue()


def events_in_seconds(data):
    seconds=0;events=[]
    for message in mido.MidiFile(file=io.BytesIO(data)):
        seconds+=message.time
        if not message.is_meta: events.append((seconds,tuple(sorted({k:v for k,v in message.dict().items() if k!='time'}.items()))))
    return events


def render(raw, settings, duration=8):
    return retime(raw,Timeline(settings,Detection([],[]),duration))


class RhythmEdgeTests(unittest.TestCase):
    def test_unquantized_same_pitch_overlaps_keep_every_start_and_release(self):
        raw=performance([(t,mido.Message(kind,note=60,velocity=velocity)) for t,kind,velocity in [
            (.1,'note_on',100),(.2,'note_on',80),(.4,'note_off',0),(.6,'note_off',0)]])
        for settings in ({'mode':'manual','bpm':170}, {'anchors':[[0,1],[2,5],[6,17]],'meter':'7/8'}):
            result=render(raw,settings)
            before,after=events_in_seconds(raw),events_in_seconds(base64.b64decode(result['data']))
            self.assertEqual([e[1] for e in before],[e[1] for e in after])
            np.testing.assert_allclose([e[0] for e in before],[e[0] for e in after],atol=.001)
            self.assertEqual(len(result['notes']),2)

    def test_controllers_and_program_changes_keep_their_original_times(self):
        raw=performance([(0,mido.Message('program_change',program=5)),(.2,mido.Message('note_on',note=60)),
            (.3,mido.Message('control_change',control=64,value=127)),(.7,mido.Message('pitchwheel',pitch=2048)),
            (1,mido.Message('note_off',note=60)),(1.3,mido.Message('control_change',control=64,value=0)),
            (1.5,mido.Message('program_change',program=10))])
        result=render(raw,{'mode':'manual','bpm':95,'meter':'6/8'})
        before,after=events_in_seconds(raw),events_in_seconds(base64.b64decode(result['data']))
        self.assertEqual([e[1] for e in before],[e[1] for e in after])
        np.testing.assert_allclose([e[0] for e in before],[e[0] for e in after],atol=.001)

    def test_auto_quantization_respects_short_note_lengths(self):
        raw=performance([(t,mido.Message(kind,note=60+i)) for i in range(4)
            for t,kind in [(i*.5,'note_on'),(i*.5+.125,'note_off')]])
        result=render(raw,{'mode':'manual','bpm':120,'quantize':True})
        np.testing.assert_allclose([n['end']-n['start'] for n in result['notes']],.125,atol=.001)

    def test_explicit_quantization_never_creates_sub_tick_blips(self):
        raw=performance([(.01,mido.Message('note_on',note=60)),(.03,mido.Message('note_off',note=60))])
        result=render(raw,{'mode':'manual','bpm':120,'quantize':True,'subdivision':'4'})
        self.assertAlmostEqual(result['notes'][0]['end']-result['notes'][0]['start'],.125,places=3)

    def test_time_signature_changes_update_the_automatic_click_unit(self):
        timeline=Timeline({'mode':'manual','bpm':120,'meter':'4/4','meter_changes':'3, 6/8\n5, 3/4'},Detection([],[]),11)
        result=retime(performance([]),timeline)
        midi=mido.MidiFile(file=io.BytesIO(base64.b64decode(result['data'])))
        signatures=[(m.numerator,m.denominator,m.clocks_per_click) for m in midi.tracks[0] if m.type=='time_signature']
        self.assertEqual(signatures,[(4,4,24),(6,8,36),(3,4,24)])
        beats=np.array(result['beat_grid']['beats'])
        np.testing.assert_allclose(beats[(beats>=4)&(beats<7)],[4,4.75,5.5,6.25],atol=.0001)
        np.testing.assert_allclose(beats[(beats>=7)&(beats<8.5)],[7,7.5,8],atol=.0001)

    def test_long_recording_does_not_accumulate_tempo_rounding_drift(self):
        raw=performance([(3599,mido.Message('note_on',note=60)),(3600,mido.Message('note_off',note=60))])
        result=render(raw,{'mode':'manual','bpm':600,'unit':'dotted-quarter'},3601)
        expected=events_in_seconds(raw)
        actual=events_in_seconds(base64.b64decode(result['data']))
        np.testing.assert_allclose([e[0] for e in actual],[e[0] for e in expected],atol=.00001,rtol=0)
        self.assertAlmostEqual(result['notes'][0]['start'],actual[0][0],places=8)
        self.assertAlmostEqual(result['notes'][0]['end'],actual[1][0],places=8)

    def test_triplets_and_sixteenth_articulation_choose_distinct_grids(self):
        for step,expected in [(1/3,1/3),(.25,.25)]:
            boundaries=np.arange(0,4,step)*.5
            timeline=Timeline({'mode':'manual','bpm':120,'quantize':True},Detection([],[]),4)
            self.assertAlmostEqual(timeline.step(boundaries),expected)

    def test_colliding_quantized_attacks_are_disclosed_and_reversible(self):
        raw=performance([(t,mido.Message(kind,note=60)) for t,kind in [
            (.01,'note_on'),(.03,'note_off'),(.04,'note_on'),(.06,'note_off')]])
        strict=render(raw,{'mode':'manual','bpm':120,'quantize':True,'subdivision':'4'})
        self.assertEqual(len(strict['notes']),1)
        self.assertTrue(any('merged 1' in w for w in strict['warnings']))
        restored=render(raw,{'mode':'manual','bpm':120,'quantize':False})
        self.assertEqual(events_in_seconds(raw),events_in_seconds(base64.b64decode(restored['data'])))

    def test_randomized_unquantized_performances_preserve_all_channels_and_events(self):
        rng=np.random.default_rng(2841)
        events=[]
        for i in range(100):
            start=float(rng.uniform(0,100));end=start+float(rng.uniform(.01,2))
            channel=i%4;pitch=60+i%7
            events.extend([(start,mido.Message('note_on',channel=channel,note=pitch,velocity=40+i%80)),
                           (end,mido.Message('note_off',channel=channel,note=pitch))])
        raw=performance(events);expected=events_in_seconds(raw)
        for settings in [
            {'mode':'manual','bpm':73.29,'meter':'7/8','first_downbeat':.375},
            {'mode':'manual','bpm':191.37,'meter':'9/8'},
            {'anchors':[[.25,1],[32.717,81],[80.136,121]],'meter':'5/4','meter_changes':'5, 13/16\n12, 6/8'},
        ]:
            result=render(raw,settings,103)
            actual=events_in_seconds(base64.b64decode(result['data']))
            self.assertEqual([e[1] for e in expected],[e[1] for e in actual])
            np.testing.assert_allclose([e[0] for e in expected],[e[0] for e in actual],atol=.0001,rtol=0)

    def test_explicit_click_unit_survives_compound_meter_changes(self):
        timeline=Timeline({'mode':'manual','bpm':120,'unit':'eighth','meter':'4/4',
            'meter_changes':'2, 6/8\n3, 9/8'},Detection([],[]),20)
        grid=timeline.display_grid()
        np.testing.assert_allclose(np.diff(grid['beats']),1/2,atol=1e-8)
        result=retime(performance([]),timeline)
        signatures=[m for m in mido.MidiFile(file=io.BytesIO(base64.b64decode(result['data']))).tracks[0] if m.type=='time_signature']
        self.assertEqual([m.clocks_per_click for m in signatures],[12,12,12])

    def test_auto_meter_requires_consistent_bar_counts(self):
        beats=np.arange(0,24,.5)
        for count in (3,4,5,7):
            timeline=Timeline({},Detection(beats.tolist(),beats[::count].tolist()),24)
            self.assertEqual(timeline.meter,(count,4))
            self.assertTrue(timeline.meter_inferred)
        # Alternating 3/4 and 4/4 is not a confident single-meter suggestion.
        timeline=Timeline({},Detection(beats.tolist(),beats[[0,3,7,10,14,17,21]].tolist()),24)
        self.assertIsNone(timeline.meter)
        self.assertFalse(timeline.meter_inferred)

    def test_explicit_compound_meter_overrides_ambiguous_duple_pulse(self):
        beats=np.arange(.25,20,.75)
        detection=Detection(beats.tolist(),beats[::2].tolist())
        auto=Timeline({},detection,20)
        self.assertEqual(auto.meter,(2,4))
        self.assertTrue(auto.meter_inferred)  # Beat counts do not establish 2/4 vs 6/8.
        manual=Timeline({'meter':'6/8'},detection,20)
        self.assertEqual(manual.meter,(6,8))
        self.assertEqual(manual.unit,1.5)
        self.assertFalse(manual.meter_inferred)

    def test_unquantized_simultaneous_messages_keep_source_order(self):
        raw=performance([(0,mido.Message('note_on',note=60)),
            (.5,mido.Message('control_change',control=64,value=127)),
            (.5,mido.Message('note_off',note=60)),(.5,mido.Message('note_on',note=62)),
            (1,mido.Message('note_off',note=62))])
        result=render(raw,{'mode':'manual','bpm':120})
        self.assertEqual(events_in_seconds(raw),events_in_seconds(base64.b64decode(result['data'])))
