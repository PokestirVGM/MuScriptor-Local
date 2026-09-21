# Finish here — 2026-09-21

Mac, Windows, and the local web GUI can finish a transcription at its last fully completed 5-second model section. The control appears after one section completes and before all sections finish. Cancel remains separate. The partial file has `_partial` in its name; the browser requests the download automatically, while desktop writes it to the chosen output folder.

The shared stream wrapper keeps a checkpoint at completed-section boundaries, discards the unfinished section, and emits note-offs at the cutoff for sustained notes. Closing the model generator releases its inference state. No note onsets are shifted and no playback speed is changed. Strict quantization retains its existing explicit behavior. The request is handled at the next model event boundary; a slow decoder step can delay acknowledgment.

Native Finish commands are read concurrently with inference and scoped to a unique run ID. Browser requests require both the originating client ID and run ID, so stale requests and other tabs cannot finish a different run. Partial results are not reused as complete-file transcription caches. Session audio and optional A/B source audio are trimmed to the exported prefix.

Validation:

- Seven focused tests passed: cutoff/discard behavior, held-note closure, generator cleanup, normal final-section completion, no unnecessary next section, concurrent native command handling, clean stdin-reader shutdown, original-time MIDI re-export, matching session audio, and browser ownership/stale-request handling. Several tests cover multiple behaviors.
- Full regression suite before the added shutdown check: 117 tests, successful with two optional skips. The additional shutdown test passed in the focused run.
- Windows control test verifies hidden/disabled states before completed audio, one scoped finish command, duplicate-click suppression, and partial completion status.
- TypeScript production build and native Swift compilation passed. Physical Windows GPU execution and a live-model GUI Finish run were not performed for this change.
- Existing tempo accuracy limitations are unchanged; partial export does not detect loops or provide pause/resume.

An already-running app keeps its old code until restart. Finish here applies to transcriptions started after launching this update.
