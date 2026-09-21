# Audio-pulse refinement validation

Later update: [build 11 percussion/meter evidence](METER_EVIDENCE.md) improves the eight difficult groove cases and adds limited automatic changing-meter suggestions. Results below describe the earlier build.

2026-09-21 · follow-up to [the initial VGM audit](VGM_STRESS_RESULTS.md)

The shared engine now checks a bass/percussion attack train when the neural beat grid drifts. A replacement requires a continuous, locally regular train, coverage of the detected passage, and at least eight consecutive one-for-one matches to the neural pulse somewhere in the recording. An unreliable introduction or a stray final neural guess does not veto that agreement. Subdivision-only matches, irregular attacks, sparse passages, and gaps are rejected. FFT processing uses bounded batches and existing NumPy; there is no extra model download or dependency.

Accepted audio attacks use a tighter 12 ms map-approximation budget and retain acceleration/tempo-change corners. This budget concerns the musical grid only. Source MIDI note times still pass through the inverse tempo map and are never stretched. Old downbeat guesses are discarded when replacing their grid; the app asks for manual meter confirmation. A pulse may still represent a subdivision rather than the intended written beat: this is a conservative recovery path, not proof of musical interpretation.

## Known-reference tests

**All 11 authored audio/reference-MIDI controls pass the existing Auto tempo/grid targets:** median quarter-BPM error ≤1%, p95 ≤3%, grid p95 ≤50 ms, maximum ≤100 ms. Eight are the original corpus; three additional patterns cover deceleration, double-time steps, and other step tempos in 5/4. The additional patterns also informed the introduction/tail guard refinement. They use the same simple synthesizer, not dense real-band arrangements.

| Control | Grid displacement p95 (before → after where previously failing) | Quarter-BPM error p95 | Tempo sections |
|---|---:|---:|---:|
| steady-170 | 2.9 ms | 0.00% | 1 |
| steps-120-150-100 | 261.6 ms → 5.0 ms | 0.00% | 3 |
| ramp-110-170 | 220.4 ms → 15.1 ms | 2.13% | 12 |
| triple-3-4 | 9.2 ms | 0.10% | 1 |
| compound-6-8 | 24.8 ms | 0.10% | 1 |
| odd-7-8 | 9.6 ms | 0.05% | 1 |
| odd-5-4 | 10.0 ms | 0.00% | 1 |
| mixed-meters-and-tempos | 268.4 ms → 9.2 ms | 0.10% | 4 |
| deceleration-180-100 | 9.3 ms | 2.38% | 14 |
| steps-96-192-96 | 5.0 ms | 0.00% | 3 |
| steps-132-168-108 | 9.4 ms | 0.04% | 3 |

Explicit reference anchors and meter changes still pass all 11 cases; already-on-grid Strict notes remain aligned. On the three previously failing original Auto cases, maximum Strict note displacement is now 5.0 ms, 17.1 ms, 10.0 ms respectively (steps, acceleration, mixed meters). Strict still intentionally moves notes and remains off by default. It is not a new AI or gentle quantizer.

## Real-recording regression and remaining limits

Fresh audio analysis covered seven transcribed recordings/excerpts plus four beat-only recordings: Littleroot, Champion Battle, Wedgehurst, South Province, Wild Pokémon Battle, the two public DEZOLVE previews, Star Wolf, Zoness, Meteo, and the Obsidian reference. **All 11 retain exactly the previous grids.** The guard declined replacement on these more complex attack patterns. This establishes non-regression, not improved accuracy on that material.

The seven cached real transcriptions still retain every one of their **17,048 notes / 34,096 note starts and ends**, with maximum timing deviation **0.120 ms** after MIDI serialization. Wild Pokémon still exports a single 170 BPM section. The three cached actual-model control transcriptions were also re-exported and retained every note event. No note-model rerun was needed to validate rhythm export.

**Unresolved:** DEZOLVE and some Star Fox/reference passages still have inaccurate or ambiguous automatic grids, and the engine still does not infer a changing-meter map. Enter time-signature changes explicitly. Source transcription accuracy is separate from preserving its timing. This refinement does not establish general 1.0 Auto accuracy or justify automatic Strict quantization.

## Cross-platform verification

- 108 regression tests: successful, two skipped (106 executed). Includes pulse recovery, genuine tempo changes, subdivision/irregular-pattern rejection, optional-check failure, session metadata validation/legacy compatibility, export timing, Windows UI behavior, worker/server and release checks.
- TypeScript checking and production web build passed; the existing bundle-size advisory remains.
- Native Apple Silicon build passed. Shared Python implementation and matching disclosure text are included in Mac, Windows source, and bundled web GUI. No new runtime dependencies.
- Saved sessions retain their cached beat detections. New audio analysis runs the pulse check; opening an old session alone does not re-detect beats. Newly recovered pulse metadata survives session save/open on all frontends.
- Windows hardware/installer and actual DAW import checks remain for the PC. Offscreen Qt tests on Mac do not certify Windows hardware.

## Reproduce

Use the installed engine Python with the model cached:

```sh
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_rhythm_stress.py
HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_rhythm_stress.py --additional
```

The `--additional` flag selects the three additional patterns. Generated reference audio/MIDI and measurements remain in ignored `build/vgm-final-validation/controls` and `build/vgm-final-validation/refinement/additional`. Real-recording recheck outputs are in `build/vgm-final-validation/refinement/real-results.json`. No downloaded audio is included in the source handoff.
