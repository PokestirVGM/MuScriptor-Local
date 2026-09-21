# Rhythm edge cases and held-out audio stress tests

Later update: [build 11 percussion/meter evidence](METER_EVIDENCE.md) improves the eight difficult groove cases and adds limited automatic changing-meter suggestions. Results below describe the earlier build.

2026-09-21 · local RC1 build 10 · Apple Silicon host

## Fixed and reproduced

Thirteen new deterministic regression tests exercise actual MIDI bytes, not just displayed BPM values. Before fixes they reproduced seven failures:

- Overlapping same-pitch notes lost attacks/releases even with Strict off. Unquantized export now retains every source event and pairs previews FIFO.
- Sustain, pitch bends, and program changes were moved to time zero. They now retain source timing.
- Simultaneous sustain/note messages were reordered, changing performance semantics. Unquantized events now retain source order within their track.
- Auto subdivision considered attacks alone, collapsing short articulation. Both attacks and releases now inform the grid choice.
- Strict snapping could collapse a short note to one MIDI tick. Minimum snapped length is now one selected grid step. Same-pitch attacks merged at a grid point are disclosed; disabling Strict re-exports the untouched original.
- Auto beat units did not change when the meter changed to compound time. Click preview and MIDI clocks-per-click now follow each section; an explicitly selected unit remains fixed.
- Integer MIDI tempo rounding accumulated playback drift. Notes/controllers now use the inverse of the serialized tempo map; preview timing reads the same map. The extreme one-hour, 600 dotted-quarter BPM case improved from 18 ms drift to 0.00186 ms. Optional Strict still snaps to musical positions and intentionally moves notes.

Additional tests cover randomized four-channel performances, pickups, tempo anchors, 13/16 and compound meter changes, triplets, explicit beat-unit overrides, quantization reversal, and consistent versus changing downbeat counts. Beat counts alone cannot distinguish 2/4 from 6/8; the test explicitly verifies that ambiguity and manual override.

## Verification

- Full Python suite: **140 tests, successful, two optional skips (138 executed)**. Log: `build/rhythm-deep-regression.log`.
- Browser state suite: **18 passed**. Log: `build/rhythm-deep-browser.log`.
- Fresh actual beat-model inference: original eight authored controls and three additional tempo patterns still pass their established Auto BPM/grid targets. Explicit tempo/meter maps and already-on-grid Strict checks pass. Maximum unquantized note-event error across these controls: **0.032 ms**.
- Seven cached real transcriptions (Littleroot, Champion Battle, Wedgehurst, South Province, Wild Pokémon Battle, two DEZOLVE previews) re-exported: **34,096/34,096 starts/releases retained; maximum deviation 0.036 ms**. This validates preservation of transcription timing, not correctness of the transcription or its estimated grid. Results: `build/rhythm-deep-real-results.json`.
- TypeScript/production web and native Swift builds passed. Engine changes are shared by Mac, Windows, and web. Windows CI now includes every `test_rhythm*.py` file. A physical Windows/DAW run remains required.

## New held-out audio arrangements: failures retained

`validation/validate_groove_stress.py` runs the real cached neural beat model on eight separately authored arrangements. These include a quarter/eighth accompaniment against dotted-quarter or unequal drum groups, deliberately creating competing pulse cues. They are short synthetic arrangements, not evidence about all music in those meters.

A pulse passes only when both reference-to-export and export-to-reference p95 timing distances are at most 50 ms. Testing both directions prevents a denser subdivision grid from receiving a false pass. Written time signature is scored separately. Timing-error columns below are p95 milliseconds.

| Arrangement | Reference → Auto | Auto → reference | Pulse target |
|---|---:|---:|---|
| Swing 4/4 | 500 | 0 | Fail: half-time |
| Syncopation 4/4 | 0 | 0 | Pass |
| 6/8 with competing quarter accompaniment | 240 | 260 | Fail |
| 9/8 with competing quarter accompaniment | 240 | 260 | Fail |
| 12/8 with competing quarter accompaniment | 240 | 260 | Fail |
| 7/8 grouped 2+2+3 | 240 | 260 | Fail |
| Syncopated 120 → 150 tempo step | 10 | 10 | Pass |
| Compound 80 → 100 pulse step | 252 | 288 | Fail |

**2/8 pass the pulse target; none supplies the correct written meter automatically.** These cases remain visible in the report and are not used to loosen acceptance thresholds. Auto changing-meter discovery remains unimplemented. No neural-model improvement is claimed by the export fixes above. Strict remains optional/off by default; it is full grid snapping, not a gentle or newly trained AI quantizer.

For complex music, preview the click and use known BPM/beat anchors plus explicit meter changes where Auto is wrong. Source note playback stays aligned when Strict is off even if the estimated musical grid is wrong. Current evidence does **not** justify a general Auto-accuracy sign-off for stable 1.0.

## Reproduce

```sh
PYTHONPATH=upstream:src .venv/bin/python -m unittest discover -s tests -p 'test_rhythm*.py' -v
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_rhythm_stress.py
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_rhythm_stress.py --additional
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_groove_stress.py
```

The groove script records both passes and failures without treating a known detector limitation as a harness failure. Inspect `pulse_pass` and `literal_meter_match` in its results. Generated audio and measurement files remain under ignored `build/vgm-final-validation/grooves`; none is included in the source handoff.
