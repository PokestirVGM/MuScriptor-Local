"""Offline model/session smoke check with cached checkpoints and authored audio."""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import time

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
import worker
import mido
from muscriptor.utils import session

parser = argparse.ArgumentParser()
parser.add_argument('--models', nargs='+', choices=worker.MODELS, default=['small'])
parser.add_argument('--device', default='auto')
args = parser.parse_args()
worker.SUPPORT = root / 'build/validation/audit-model'
worker.SUPPORT.mkdir(parents=True, exist_ok=True)
network_attempts = []
def deny_network(event, arguments):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        network_attempts.append(event)
        raise AssertionError('Unexpected network request during offline validation')
sys.addaudithook(deny_network)

def note_times(path):
    seconds = 0
    notes = []
    for message in mido.MidiFile(path):
        seconds += message.time
        if message.type in ('note_on', 'note_off'):
            notes.append((message.type, message.channel, message.note, message.velocity, seconds))
    return notes

results = []
for size in args.models:
    assert worker.cached_weights(size), f'{size} is not cached; this check never downloads models.'
    reports = []
    worker.emit = lambda kind, **fields: reports.append({'type': kind, **fields})
    started = time.monotonic()
    engine = worker.Engine(size, args.device)
    engine.transcribe(root / 'validation/Local Test Melody.flac', worker.SUPPORT / f'{size}.mid',
                      timing={'mode': 'manual', 'bpm': 109, 'meter': '4/4'})
    complete = next(e for e in reports if e['type'] == 'complete')
    before = note_times(complete['path'])
    count = sum(n[0] == 'note_on' and n[3] > 0 for n in before)
    assert count > 0 and complete['session'] and complete['recovery_path']
    session.read(complete['recovery_path'])
    portable = worker.SUPPORT / f'{size}.muscriptor'
    engine.save_session(portable, {'mode': 'manual', 'bpm': 109, 'meter': '4/4'})
    engine.model = None
    engine.load_session(portable)
    engine.reexport_session({'mode': 'manual', 'bpm': 140, 'meter': '6/8'}, worker.SUPPORT / f'{size}-changed-grid.mid')
    after = note_times([e for e in reports if e['type'] == 'complete'][-1]['path'])
    assert len(before) == len(after)
    assert all(a[:4] == b[:4] and abs(a[4] - b[4]) < .002 for a, b in zip(before, after))
    results.append(dict(model=size, backend=engine.device, notes=count,
                        seconds=round(time.monotonic() - started, 2),
                        warnings=[e['message'] for e in reports if e['type'] == 'warning'],
                        session_roundtrip=True, note_times_preserved=True))
    del engine
    import gc
    gc.collect()
    print(json.dumps(results[-1]), flush=True)
assert not network_attempts, network_attempts
(worker.SUPPORT / 'results.json').write_text(json.dumps(results, indent=2))
