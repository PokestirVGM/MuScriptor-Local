"""Exercise the actual installed worker and Large model with networking forbidden."""
import io
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
sys.path.insert(0, str(root / 'src'))
import worker

attempts = []
def deny_network(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        attempts.append(event)
        raise RuntimeError('Networking is disabled for offline validation')
sys.addaudithook(deny_network)

source = root / 'validation/Local Test Melody.flac'
sys.stdin = io.StringIO(json.dumps({'action':'transcribe','path':str(source)}) + '\n' + json.dumps({'action':'quit'}) + '\n')
sink = io.StringIO()
worker.protocol = sink
worker.main()
events = [json.loads(line) for line in sink.getvalue().splitlines()]
(root / 'validation/offline-events.json').write_text(json.dumps(events, indent=2))
completions = [e for e in events if e['type']=='complete']
assert completions, events
assert not attempts, f'Unexpected network attempts: {attempts}'
assert any(e['type']=='backend' and e['device']=='Apple MPS' for e in events)
assert not any(e['type']=='warning' for e in events), 'Unexpected GPU fallback'
import mido
midi = mido.MidiFile(completions[-1]['path'])
notes = sum(msg.type=='note_on' and msg.velocity>0 for track in midi.tracks for msg in track)
assert notes > 0
assert midi.length > 10, f'Expected a complete 12-second source, MIDI lasts {midi.length}'
assert max(e.get('completed',0) for e in events if e['type']=='progress') == 3
print(json.dumps({'offline':True,'network_attempts':len(attempts),'backend':'Apple MPS','model':'Large','chunks':3,'notes':notes,'midi_seconds':midi.length,'output':completions[-1]['path']}), file=sys.__stdout__)
