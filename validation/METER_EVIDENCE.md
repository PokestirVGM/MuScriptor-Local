# Auto percussion/meter evidence — build 11

2026-09-21 · Apple Silicon host · unpublished RC1

## What changed

Auto now cross-checks ambiguous beat interpretations against independent low-frequency percussion attacks, high-frequency subdivisions, and repeated accent patterns. It can suggest simple, compound, or unequal-group meters and a changing-meter map when the recording supplies enough consistent evidence. The original Beat This! model is retained; no additional model, runtime dependency, or download was added. Its [official implementation](https://github.com/CPJKU/beat_this) remains the primary beat detector.

The correction requires at least six evidenced bars overall, at least four consecutive matching bars per section, separated accent strengths, subdivisions aligned with primary attacks, recording coverage, and a plausible rhythmic relationship to the neural pulse. Gaps, inconsistent fills, ambiguous accents, very short sections, and unrelated tempos are rejected. A regular backbeat cannot halve a consistent neural bar interpretation when the quarter pulse already agrees. Optional-analysis failure retains the original neural result.

Equal ternary subdivisions distinguish the tested compound rhythms from swing's unequal pairs. Unequal groups such as 2+2+3 or 3+2+2 describe 7/8; they no longer become alternating tempo values. Quarter-note coordinates remain independent of the displayed BPM unit. Click playback uses the detected groups; MIDI uses standard tempo and time-signature events. MIDI hosts may use their own click grouping for odd meters.

Meter changes and grouping metadata survive session save/reopen across Mac, Windows, and web. Explicit meter/anchor settings override suggestions. Original note timing is still preserved; this is not a new quantizer. Strict remains optional, off by default, and intentionally moves notes.

## Measured improvement

The eight difficult arrangements from build 10 became development cases for this work. Their acceptance thresholds were not relaxed. Previously 2/8 passed the two-way pulse target and 0/8 provided the fixture's meter. **Now 8/8 pass and 8/8 suggest the expected meter**, with pulse p95 error approximately 5 ms. Includes swing, syncopation, 6/8, 9/8, 12/8, grouped 7/8, and two tempo-step patterns.

Six additional actual-model cases use a separate sound generator, additional seeds, unfamiliar tempos, and 16–44.1 kHz sample rates:

| Case | Pulse p95 error | Meter events |
|---|---:|---|
| Swing, 132 quarter BPM | 15.0 ms | 4/4 correct |
| 6/8, 112 dotted-quarter BPM | 15.9 ms | Correct |
| 9/8, 72 dotted-quarter BPM | 15.9 ms | Correct |
| 12/8, 128 dotted-quarter BPM | 10.0 ms | Correct |
| 7/8 grouped 3+2+2, 144 quarter BPM | 15.9 ms | Correct |
| 4/4 → 6/8 → 7/8, 108 → 144 quarter BPM | 17.2 ms | All changes within 30 ms |

All six pass both directions of the 50 ms p95 pulse target and actual MIDI meter-event checks. All note events survive, maximum serialization error below 0.03 ms. Matching fixture notation does not prove that the same audio admits only one written time signature.

- Original 11 authored tempo controls remain passing, including ramps, deceleration, and abrupt changes.
- Fresh full audio analysis of seven real recordings (Pokémon recordings and two DEZOLVE previews) retains their previous beat grids. No new meter evidence is asserted there. All 34,096 note starts/releases remain, maximum timing deviation **0.036 ms**.
- Full regression: **152 Python tests, successful with two optional skips (150 executed)**; **18 browser state tests passed**. Twelve added evidence tests cover independent arrangements, session validation, manual overrides, missing percussion, ambiguity, and optional failure.
- Production frontend and native Mac builds pass. Shared engine and tests are included in the Windows source handoff; physical Windows/DAW validation remains outstanding.

Logs/results: `build/meter-evidence-*.log`, `build/meter-evidence-real-results.json`, and `build/vgm-final-validation/{grooves,meter-evidence}/results.json`. Generated audio stays outside distributed archives.

## Remaining limits

This is a conservative improvement for repeated percussion-led patterns, not a universal meter model. Dense DEZOLVE passages, frequent short meter changes, weak/missing percussion, and ambiguous notation remain unresolved. Existing real grids were protected, not proven more accurate. Stable 1.0 Auto-accuracy sign-off is still withheld.

The new evidence check runs during **fresh audio analysis**. Existing saved sessions retain their cached detections. Reopening/re-exporting an old session alone does not invoke the improved detector; analyze the source recording again to obtain new suggestions. Sessions created with this version preserve the new suggestions when reopened.

## Reproduce

```sh
PYTHONPATH=upstream:src .venv/bin/python -m unittest discover -s tests -p 'test_rhythm*.py' -v
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_groove_stress.py
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_meter_evidence.py
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_rhythm_stress.py
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_rhythm_stress.py --additional
```
