# VGM, tempo, and meter stress-test results

Later update: [build 11 percussion/meter evidence](METER_EVIDENCE.md) improves the eight difficult groove cases and adds limited automatic changing-meter suggestions. Results below describe the earlier build.

**Historical baseline:** subsequent [audio-pulse refinement](RHYTHM_REFINEMENT.md) fixes the three authored tempo/grid failures below and passes three additional patterns. Complex real-recording limitations remain. The measurements below describe the original audit before that refinement.

2026-09-21 · cached MuScriptor Large on Apple MPS · unpublished local candidate

**Result: MIDI timing preservation passes; automatic tempo/grid/meter accuracy is not ready for unconditional 1.0 sign-off.**

No production algorithm was changed during this audit. Difficult cases are retained as failures. The earlier two-recording checks were too narrow to establish general Auto accuracy.

## Scope and what was measured

- Seven transcribed real recordings/excerpts: five newly tested plus the existing full South Province and Wild Pokémon sessions. **17,048 notes / 34,096 note starts and ends**; maximum export deviation below **0.12 ms** from the model’s unquantized MIDI. This verifies the exporter, not that every model note matches the audio.
- New full recordings: Littleroot Town (88.44 s), Battle! (Champion) (91.39 s), and Wedgehurst (46.30 s). DEZOLVE tests use the complete publicly available ~29.93-second previews of Orbital Revolution and Circus, not the full songs.
- Eight self-authored audio/reference-MIDI controls with known tempo maps and meters. All eight pass explicit-anchor/meter export and grid checks. Five pass the Auto tempo/grid targets; three fail. Auto leaves meter uncertain on all eight and does not generate a changing time-signature map.
- Three controls additionally run through the actual transcription model, with onset/pitch comparison against the authored notes.
- Additional full-audio beat-only screening: Star Wolf, Zoness, Meteo, and a local Obsidian Crown reference. These are not additional completed note-transcription tests.
- Fresh regression run: **102 tests, two skipped**. Those passing code tests do not override the failing audio-accuracy benchmark. No actual Windows hardware or DAW-host test was performed here.

## Controlled Auto accuracy

Acceptance targets for this corpus: median relative quarter-BPM error ≤1%, 95th percentile ≤3%; 95th-percentile beat-grid displacement ≤50 ms and maximum ≤100 ms. These are explicit engineering targets, not universal perceptual thresholds. Grid error compares the predicted pulse against known quarter-beat times; half/double interpretations count as failures to recover that reference. Meter spelling can remain ambiguous from audio alone.

| Control | Expected tempo / meter | Auto BPM error p95 | Grid error p95 | Auto result |
|---|---|---:|---:|---|
| steady-170 | 170 BPM; 4/4 | 0.00% | 2.9 ms | PASS tempo/grid; meter unconfirmed |
| steps-120-150-100 | 120 → 150 → 100 BPM; 4/4 | 24.88% | 261.6 ms | FAIL |
| ramp-110-170 | 110 → 170 BPM; 4/4 | 39.33% | 220.4 ms | FAIL |
| triple-3-4 | 126 BPM; 3/4 | 0.10% | 9.2 ms | PASS tempo/grid; meter unconfirmed |
| compound-6-8 | 135 BPM; 6/8 | 0.10% | 24.8 ms | PASS tempo/grid; meter unconfirmed |
| odd-7-8 | 140 BPM; 7/8 | 0.05% | 9.6 ms | PASS tempo/grid; meter unconfirmed |
| odd-5-4 | 120 BPM; 5/4 | 0.00% | 10.0 ms | PASS tempo/grid; meter unconfirmed |
| mixed-meters-and-tempos | 120 → 144 → 96 → 160 BPM; 4/4 → 3/4 → 6/8 → 7/8 → 5/4 | 39.84% | 268.4 ms | FAIL |

With explicit reference anchors and meters, all eight controls have zero measured grid displacement in floating-point calculations, correctly timed MIDI meter events, and less than 0.05 ms of note-time rounding error. Already-on-grid notes remain on the intended grid with explicit Strict quantization. This validates support for 3/4, 6/8, 7/8, 5/4, changing signatures and tempo ramps when supplied; it does not prove automatic discovery of those maps.

**Strict-quantization finding:** with the incorrect Auto grids, maximum displacement of already-correct note events was 66.2 ms on the step-change test, 107.4 ms on the ramp, and 77.9 ms on the mixed-meter test. All events were retained, but their timing became less accurate. Keep Strict off until a grid has been confirmed or corrected.

## Real recordings and excerpts

These BPMs are model estimates. No independent composer tempo map was available for these commercial recordings. Detector-versus-grid agreement is a consistency measure, not a correctness certificate.

| Recording | Tested duration | Notes | Auto estimate | Tempo events | Export error max | Detector/grid difference p95 |
|---|---:|---:|---|---:|---:|---:|
| Littleroot Town | 88.44 s | 865 | 107.5 BPM; 4/4 suggested; Original timing | 1 | 0.106 ms | 17.7 ms |
| Battle! (Champion) | 91.39 s | 2,028 | 93.5 BPM; meter uncertain; variable tempo; Original timing | 5 | 0.051 ms | 38.5 ms |
| Wedgehurst Theme | 46.30 s | 1,359 | 108.1 BPM; meter uncertain; Original timing | 1 | 0.029 ms | 35.5 ms |
| DEZOLVE — Orbital Revolution | 29.93 s | 814 | 130.4 BPM; meter uncertain; Original timing | 1 | 0.023 ms | 200.0 ms |
| DEZOLVE — Circus | 29.93 s | 847 | 134.0 BPM; meter uncertain; variable tempo; Original timing | 5 | 0.031 ms | 182.7 ms |

Littleroot and Wedgehurst yield stable maps with relatively close detector agreement. The Champion battle and both DEZOLVE excerpts are flagged as uncertain. Orbital Revolution’s simplified map still differs from its detector by roughly 200 ms at the 95th percentile; Circus by roughly 183 ms. These are not accepted as verified correct grids or BPMs. No claim is made that either preview contains a specific meter-change sequence.

The additional beat-only Star Fox screening exposed half/double-pulse switches and short spurious tempo sections. The paired Obsidian reference includes 120 → 144 BPM and an outro slowdown plus 7/8 and 5/4 measures, while Auto commonly tracked a 72 BPM pulse and did not recover those meter changes. This is further evidence that a sparse map alone is not proof of correctness.

## Actual model note-onset checks

Limited synthetic benchmark: pitched reference notes only; detected channel-10 percussion is excluded. Greedy same-pitch matching within 100 ms, ignoring instrument labels. Precision penalizes extra pitched detections. These figures must not be generalized to commercial music.

| Control | Matched / reference pitched notes | Pitched precision | Pitched recall | Matched onset error p95 | Export error max |
|---|---:|---:|---:|---:|---:|
| mixed-meters-and-tempos | 220 / 222 | 67.5% | 99.1% | 19.8 ms | 0.036 ms |
| steady-170 | 190 / 192 | 75.1% | 99.0% | 11.4 ms | 0.024 ms |
| steps-120-150-100 | 137 / 144 | 72.1% | 95.1% | 19.8 ms | 0.029 ms |

Matched note onsets are usually close in these controls, but the model also adds extra pitched notes. Unquantized output preserves those model estimates; it does not correct transcription errors. Turning quantization off is the only current way to guarantee that grid changes do not move the model’s performance timing.

## Release blockers and next work

1. Auto misses genuine changes and sometimes mistakes half/double pulse choices for tempo changes. Evaluate beat/tempo tracking against reference annotations before changing or replacing the tracker.
2. Auto currently suggests one meter or leaves it uncertain; it does not infer a full changing-meter map. The app needs explicit editing/confirmation for that map, or separately validated automatic support.
3. Strict snapping is not an accuracy improvement when the grid is wrong. Grid approval and confidence handling must precede any accuracy claim for quantization.
4. Establish annotated real-recording BPM/downbeat/meter references and test actual DAW imports on Windows and Mac. Do not relabel detector agreement as ground truth.

## Sources and reproducibility

- [Littleroot Town](https://downloads.khinsider.com/game-soundtracks/album/pokemon-ruby-sapphire-music-super-complete/1-05.%2520Littleroot%2520Town.mp3)
- [Battle! (Champion)](https://downloads.khinsider.com/game-soundtracks/album/pokemon-diamond-and-pearl-super-music-collection/2-67.%2520Battle%2521%2520%2528Champion%2529.mp3)
- Wedgehurst Theme: existing local recording.
- [DEZOLVE — Orbital Revolution](https://music.apple.com/us/album/orbital-revolution/1286580437?i=1286580446&uo=4)
- [DEZOLVE — Circus](https://music.apple.com/us/album/circus/1173376163?i=1173376170&uo=4)

Reproduce the self-authored controls with `HF_HUB_OFFLINE=1 PYTHONPATH=upstream:src .venv/bin/python validation/validate_rhythm_stress.py`. Generated audio, MIDI, detailed results, source provenance and audition files are under ignored `build/vgm-final-validation/`. The report HTML links to local audition files and sessions. No downloaded recordings are committed or publicly published.
