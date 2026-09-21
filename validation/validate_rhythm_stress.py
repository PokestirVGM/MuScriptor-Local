"""Self-authored audio/MIDI ground-truth corpus; no copyrighted fixtures/downloads.

Run with PYTHONPATH=upstream:src and the installed engine Python. Generated media
and detailed JSON stay under ignored build/vgm-final-validation/controls.
Auto detection is compared against authored ground truth and checked against
explicit accuracy targets. Explicit tempo/meter export invariants are asserted. No transcription-model inference is needed here.
"""
from pathlib import Path
import base64
import io
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'upstream')]
import mido
import numpy as np
import soundfile as sf
import torch
from muscriptor.utils import rhythm

OUT = ROOT/'build/vgm-final-validation/controls'
RATE = 16000


def midi_events(data):
    sec, notes, signatures = 0., {}, []
    for msg in mido.MidiFile(file=io.BytesIO(data)):
        sec += msg.time
        if msg.type == 'time_signature':
            signatures.append((sec, f'{msg.numerator}/{msg.denominator}'))
        if msg.type in ('note_on', 'note_off'):
            key = (msg.channel, msg.note, 'on' if msg.type == 'note_on' and msg.velocity else 'off')
            notes.setdefault(key, []).append(sec)
    return notes, signatures


def make_case(name, bars, tempo_knots):
    """bars=(signature, number_of_bars); tempo_knots=(quarter, quarter_BPM)."""
    folder = OUT/name
    folder.mkdir(parents=True, exist_ok=True)
    bar_starts, meters, q_end, bar_number = [], [], 0., 1
    for sig, count in bars:
        n, d = map(int, sig.split('/'))
        meters.append((bar_number, q_end, sig))
        for _ in range(count):
            bar_starts.append(q_end)
            q_end += n*4/d
        bar_number += count
    kq = np.array([q for q, _ in tempo_knots] + [q_end])
    bpms = np.array([bpm for _, bpm in tempo_knots])
    kt = .25 + np.r_[0, np.cumsum(np.diff(kq)*60/bpms)]
    at = lambda q: float(np.interp(q, kq, kt))
    duration = kt[-1]+.5
    samples = np.zeros(round(duration*RATE))
    rng = np.random.default_rng(47)
    events = []

    def tone(q, length, pitch, velocity, channel):
        start, end = at(q), at(min(q+length, q_end))
        events.extend([(start, mido.Message('note_on', note=pitch, velocity=velocity, channel=channel)),
                       (end, mido.Message('note_off', note=pitch, channel=channel))])
        t = np.arange(max(1, round((end-start)*RATE)))/RATE
        f = 440*2**((pitch-69)/12)
        envelope = np.minimum(t/.003, 1)*np.exp(-3*t)*np.minimum((end-start-t)/.015, 1).clip(0, 1)
        wave = sum(np.sin(2*np.pi*f*h*t)/h**2 for h in range(1, 7))
        i = round(start*RATE)
        samples[i:i+len(t)] += wave*envelope*.15*velocity/100

    for j, q in enumerate(np.arange(0, q_end, .5)):
        tone(q, .25, [72, 76, 79, 83, 81, 79, 76, 74][j % 8], 75, 0)
    for j, q in enumerate(np.arange(0, q_end, 1.)):
        tone(q, .5, [48, 48, 55, 48][j % 4], 95, 1)
        start = round(at(q)*RATE)
        t = np.arange(round(.12*RATE))/RATE
        # Drums emphasize quarter pulses; bar accents provide meter cues.
        accent = 1. if q in bar_starts else .65
        drum = np.sin(2*np.pi*(65*t-20*t*t))*np.exp(-35*t)
        drum += .25*rng.normal(size=len(t))*np.exp(-60*t)
        samples[start:start+len(t)] += accent*.4*drum
    for q in bar_starts:
        start = round(at(q)*RATE)
        t = np.arange(round(.05*RATE))/RATE
        samples[start:start+len(t)] += .15*rng.normal(size=len(t))*np.exp(-65*t)
    samples /= max(1., float(np.max(abs(samples))))
    sf.write(folder/'reference.wav', samples, RATE, subtype='PCM_16')
    raw = mido.MidiFile(ticks_per_beat=9600)
    tr = mido.MidiTrack([mido.MetaMessage('set_tempo', tempo=500000)])
    raw.tracks.append(tr)
    last = 0
    for seconds, msg in sorted(events, key=lambda pair: pair[0]):
        tick = round(seconds*19200)
        tr.append(msg.copy(time=tick-last)); last = tick
    buf = io.BytesIO(); raw.save(file=buf); raw_bytes = buf.getvalue()
    (folder/'reference-seconds.mid').write_bytes(raw_bytes)
    settings = {'meter': bars[0][0], 'unit': 'quarter',
                'anchors': [[float(t), float(q+1)] for q, t in zip(kq, kt)],
                'meter_changes': '\n'.join(f'{bar}, {sig}' for bar, _, sig in meters[1:])}
    detection = rhythm.detect(torch.tensor(samples[None, :], dtype=torch.float32), RATE)
    (folder/'detection.json').write_text(json.dumps(vars(detection)))
    auto = rhythm.Timeline({}, detection, duration)
    auto_result = rhythm.retime(raw_bytes, auto)
    (folder/'Auto.mid').write_bytes(base64.b64decode(auto_result['data']))
    exact = rhythm.Timeline(settings, detection, duration)
    exact_result = rhythm.retime(raw_bytes, exact)
    exact_bytes = base64.b64decode(exact_result['data'])
    (folder/'Reference-grid.mid').write_bytes(exact_bytes)
    original, _ = midi_events(raw_bytes)
    checks = {}
    for label, data in [('auto', base64.b64decode(auto_result['data'])), ('reference_grid', exact_bytes)]:
        notes, signatures = midi_events(data)
        assert original.keys() == notes.keys()
        assert all(len(v) == len(notes[k]) for k, v in original.items())
        error = max(float(np.max(abs(np.array(v)-notes[k]))) for k, v in original.items())
        assert error < .001, (name, label, error)
        checks[label+'_note_error_ms'] = error*1000
    _, signatures = midi_events(exact_bytes)
    for _, q, sig in meters:
        assert any(s == sig and abs(t-at(q)) < .001 for t, s in signatures), (name, q, sig, signatures)
    qbeats = np.arange(0, q_end)
    true_times = np.interp(qbeats, kq, kt)
    manual_grid_error = float(np.max(abs(exact.seconds_at_q(qbeats)-true_times)))
    assert manual_grid_error < .000001, (name, manual_grid_error)
    # These reference notes already lie on a sixteenth-note grid. Explicit
    # quantization must keep them there, including through meter/tempo changes.
    strict = rhythm.retime(raw_bytes, rhythm.Timeline({**settings, 'quantize': True, 'subdivision': '4'}, detection, duration))
    strict_notes, _ = midi_events(base64.b64decode(strict['data']))
    assert original.keys() == strict_notes.keys()
    strict_error = max(float(np.max(abs(np.array(v)-strict_notes[k]))) for k, v in original.items())
    assert strict_error < .001, (name, strict_error)
    grid = auto.display_grid()
    actual = np.asarray(grid['beats']) if grid else np.array([])
    errors = np.min(abs(true_times[:, None]-actual[None, :]), axis=1) if len(actual) else np.array([999.])
    sample_q = qbeats+.5
    sample_times = np.interp(sample_q, kq, kt)
    slopes = 60/(auto.seconds_at_q(auto.to_q(sample_times)+.01)-sample_times)*.01
    truth = bpms[np.minimum(np.searchsorted(kq, sample_q, side='right')-1, len(bpms)-1)]
    bpm_error = abs(slopes/truth-1)*100
    record = {'case': name, 'seconds': duration, 'reference_quarter_bpms': bpms.tolist(),
              'reference_meters': [s for _, _, s in meters], 'auto_summary': auto_result['summary'],
              'auto_warnings': auto.warnings, 'audio_pulse_recovered': detection.pulse_verified, 'auto_meter': grid['meter'] if grid else None,
              'auto_tempo_sections': len(auto.x)-1,
              'auto_bpm_relative_error_percent_p50_p95': np.percentile(bpm_error, [50, 95]).tolist(),
              'auto_grid_error_ms_p50_p95_max': (np.percentile(errors, [50, 95, 100])*1000).tolist(),
              'reference_meter_events_verified': True, **checks}
    record['reference_grid_error_ms_max'] = manual_grid_error*1000
    record['already_on_grid_strict_note_error_ms_max'] = strict_error*1000
    # Engineering acceptance targets for this corpus, not perceptual standards.
    record['auto_bpm_pass'] = bool(np.percentile(bpm_error, 50) <= 1 and np.percentile(bpm_error, 95) <= 3)
    record['auto_grid_pass'] = bool(np.percentile(errors, 95) <= .05 and np.max(errors) <= .1)
    auto_strict = rhythm.retime(raw_bytes, rhythm.Timeline({'quantize': True, 'subdivision': '4'}, detection, duration))
    snapped, _ = midi_events(base64.b64decode(auto_strict['data']))
    same_events = original.keys() == snapped.keys() and all(len(v) == len(snapped[k]) for k, v in original.items())
    record['auto_strict_kept_all_note_events'] = same_events
    record['auto_strict_note_error_ms_max'] = (max(float(np.max(abs(np.array(v)-snapped[k]))) for k, v in original.items())*1000 if same_events else None)
    (folder/'validation.json').write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)
    return record


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--additional', action='store_true', help='Run additional deceleration and abrupt-change patterns.')
    args = parser.parse_args()
    if args.additional:
        OUT = OUT.parent/'refinement'/'additional'
    OUT.mkdir(parents=True, exist_ok=True)
    cases = [
        ('steady-170', [('4/4', 16)], [(0, 170)]),
        ('steps-120-150-100', [('4/4', 12)], [(0, 120), (16, 150), (32, 100)]),
        ('ramp-110-170', [('4/4', 8)], [(i, float(v)) for i, v in enumerate(np.linspace(110, 170, 32))]),
        ('triple-3-4', [('3/4', 12)], [(0, 126)]),
        ('compound-6-8', [('6/8', 12)], [(0, 135)]),
        ('odd-7-8', [('7/8', 12)], [(0, 140)]),
        ('odd-5-4', [('5/4', 8)], [(0, 120)]),
        ('mixed-meters-and-tempos', [('4/4', 4), ('3/4', 4), ('6/8', 4), ('7/8', 4), ('5/4', 4)],
         [(0, 120), (28, 144), (40, 96), (54, 160)]),
    ]
    if args.additional:
        cases = [
            ('deceleration-180-100', [('4/4', 8)], [(i, float(v)) for i, v in enumerate(np.linspace(180, 100, 32))]),
            ('steps-96-192-96', [('4/4', 12)], [(0, 96), (16, 192), (32, 96)]),
            ('steps-132-168-108', [('5/4', 12)], [(0, 132), (20, 168), (40, 108)]),
        ]
    report = [make_case(*case) for case in cases]
    (OUT/'results.json').write_text(json.dumps(report, indent=2)+'\n')

    failed = [r['case'] for r in report if not (r['auto_bpm_pass'] and r['auto_grid_pass'])]
    if failed:
        raise SystemExit('Auto tempo/grid accuracy failed: ' + ', '.join(failed))
