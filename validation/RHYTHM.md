# Tempo and rhythm validation

Validated locally on Apple Silicon with the cached Large model, 2026-09-21.

The initial Auto map described below was subsequently corrected after user review. See [Auto tempo-map correction](STABLE_TEMPO.md) for the latest behavior and full-recording comparison; the older dense map is no longer the intended output.

- Full desktop/worker/web suite: 84 tests, successful with two platform-specific skips. After the final manual-warning adjustment, all 13 focused rhythm tests passed.
- TypeScript checking and production frontend build passed. Swift typechecking, the Mac application build, and bundle signature verification passed.
- Inspected the compact browser controls, including a narrow viewport, manual BPM disclosure, and removal of performance stretching. The development browser server was then switched from mock inference to the real cached Large model.
- Transcribed an entire user-supplied 186.43-second recording on Apple MPS: 4,104 notes. The recording and generated files remain in ignored local build storage.
- Compared every MIDI note-on and note-off with the unquantized upstream export. Auto's maximum timing difference was 0.046 ms; manual 140 BPM / 4/4 was 0.202 ms; manual 80 BPM / 6/8 was zero; manual 200 BPM / 4/4 was 0.011 ms. These are MIDI tick/tempo rounding differences, measured relative to the model's transcription, not an assessment of transcription accuracy against the audio.
- The test recording's detected grid has a faster opening and a main pulse near 140 BPM. Some transitions produce extra or uncertain detections. Conservative cleanup removed 11 isolated extra beats; uncertain changes remain disclosed. Automatic meter remained uncertain instead of guessing a signature.

Automated MIDI round trips cover sustained tempo changes, manual anchors, compound beat units, pickup timing without added silence, separate optional quantization, fallback disclosure, meter changes, and cached web re-export. Detector cleanup tests ensure that isolated extras are removed without moving retained timestamps or filling missed beats, and that genuine sustained tempo changes survive.

Windows UI logic was exercised through Qt locally; no new Windows installer or Windows hardware run was performed. The Windows build workflow now includes the rhythm tests. A MIDI host may handle fractional pickup bars differently; note playback retains the original time origin regardless. Auto beat and meter detection remain fallible, and optional quantization intentionally changes individual note timing.
