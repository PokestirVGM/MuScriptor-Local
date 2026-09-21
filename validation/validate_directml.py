"""Opt-in, offline, real-GPU transcription check; requires a cached model."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", choices=worker.MODELS, default="small")
    parser.add_argument("--device", help="Adapter ID shown by the worker, e.g. privateuseone:1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-notes", action="store_true", help="Fail on empty MIDI when testing known musical audio")
    args = parser.parse_args()
    devices = worker.directml_devices()
    if not devices:
        raise SystemExit("No usable DirectML GPU. Install DirectML dependencies and update the graphics driver.")
    selected = worker.choose_device(devices, args.device or "auto")
    if worker.cached_weights(args.model) is None:
        raise SystemExit("Download this model in the app first. This check stays offline.")
    args.output.mkdir(parents=True, exist_ok=True)
    engine = worker.Engine(args.model, selected)
    events = []
    def record(kind, **fields):
        events.append(dict(type=kind, **fields))
        print(json.dumps(events[-1]), flush=True)
    worker.emit = record
    start = time.perf_counter()
    engine.transcribe(args.audio.resolve(), args.output.resolve() / (args.audio.stem + "_directml.mid"))
    if engine.device != selected:
        raise SystemExit("FAILED: transcription fell back to CPU. Check warnings above; this is not a successful GPU run.")
    completed = [event for event in events if event["type"] == "complete"]
    if not completed:
        raise SystemExit("FAILED: no completed MIDI was reported.")
    import mido
    midi = mido.MidiFile(completed[-1]["path"])
    notes = sum(message.type == "note_on" and message.velocity > 0 for track in midi.tracks for message in track)
    if args.require_notes and not notes:
        raise SystemExit("FAILED: DirectML returned an empty MIDI for the musical test input.")
    print(json.dumps(dict(result="completed on DirectML", model=args.model, device=selected,
                          gpu=next(d["name"] for d in devices if d["id"] == selected),
                          note_count=notes, midi_seconds=round(midi.length, 2),
                          elapsed_seconds=round(time.perf_counter() - start, 2),
                          midi=completed[-1]["path"])))


if __name__ == "__main__":
    main()
