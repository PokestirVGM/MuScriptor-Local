"""Validate model switching and a real Large transcription with no network access."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
os.environ['HF_HUB_OFFLINE'] = '1'
sys.path.insert(0, str(root / 'src'))
import worker

attempts = []
def deny_network(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        attempts.append(event)
        raise RuntimeError('Network disabled for validation')
sys.addaudithook(deny_network)
source = root / 'validation/Local Test Melody.flac'
with tempfile.TemporaryDirectory(prefix='muscriptor-validation-') as temporary:
    directory = Path(temporary)
    worker.LOG_DIR = directory / 'Logs'
    worker.SUPPORT = directory / 'Support'
    destination = directory / 'Local Test Melody_transcription.mid'
    commands = [{'action': 'select_model', 'model': size} for size in ('small', 'medium', 'large')]
    commands += [
        {'action': 'plan', 'path': str(source), 'directory': str(directory)},
        {'action': 'transcribe', 'path': str(source), 'destination': str(destination)},
        {'action': 'quit'},
    ]
    sys.stdin = io.StringIO(''.join(json.dumps(command) + '\n' for command in commands))
    sink = io.StringIO()
    worker.protocol = sink
    worker.main()
    events = [json.loads(line) for line in sink.getvalue().splitlines()]
    errors = [e for e in events if e['type'] == 'error']
    assert not errors, errors
    ready = [e for e in events if e['type'] == 'ready']
    assert [e['model'] for e in ready[-3:]] == ['small', 'medium', 'large']
    assert all(e['directory'].endswith('muscriptor-' + e['model']) for e in ready)
    assert not any(e['type'] == 'download' for e in events)
    planned = next(e for e in events if e['type'] == 'planned')
    completed = next(e for e in events if e['type'] == 'complete')
    assert Path(planned['path']).resolve() == destination.resolve()
    assert Path(completed['path']).resolve() == destination.resolve()
    assert not completed['needs_save']
    assert not attempts, attempts
    import mido
    midi = mido.MidiFile(completed['path'])
    notes = sum(msg.type == 'note_on' and msg.velocity > 0 for track in midi.tracks for msg in track)
    assert notes > 0 and midi.length > 10
    assert max(e.get('completed', 0) for e in events if e['type'] == 'progress') == 3
    assert any(e['type'] == 'backend' and e['device'] == 'Apple MPS' for e in events)
    result = dict(models_switched=['small', 'medium', 'large'], actual_transcription_model='large',
                  backend='Apple MPS', network_attempts=len(attempts), custom_destination_matches_preview=True,
                  chunks=3, notes=notes, midi_seconds=midi.length,
                  warnings=[e['message'] for e in events if e['type'] == 'warning'])
    (root / 'validation/model-controls-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), file=sys.__stdout__)
