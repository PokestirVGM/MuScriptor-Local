# 1.0 usability and failure-path audit

2026-09-21, Apple Silicon host. Local, unpublished RC1, Mac bundle build 12.

Latest release pass: [final readiness](FINAL_READINESS.md), including session restart/return fixes, invalid-audio rejection, and corrected source packaging.

Latest Auto work: [percussion and meter evidence](METER_EVIDENCE.md), with 152 Python tests (two skips), 18 browser tests, and guarded changing-meter suggestions.

## Rhythm follow-up (build 10)

See [rhythm edge cases](RHYTHM_EDGE_CASES.md): seven reproduced export/quantization/click defects fixed, 13 new regression cases, all 140 Python checks successful with two skips, and 18 browser tests passed. Real-recording note preservation improved to a maximum 0.036 ms deviation. Held-out audio tests expose unresolved Auto rhythm interpretation; no broad accuracy sign-off is claimed.

## Follow-up bug pass (build 9)

- Reproduced and fixed a no-op WAV synthesis action when reopening a session without source audio. Synth-only export uses the selected MIDI, including explicit quantization; A/B continues to use original performance timing. Audio-less export filenames retain the session name.
- Reproduced and fixed old sheet results appearing after timing/session changes. WAV and sheet exports are scoped to the current result, abort their request on replacement/unmount, suppress obsolete errors/downloads, and prevent duplicate concurrent exports.
- Reproduced a server responsiveness failure during WAV rendering. Rendering now runs off the request loop, and the rendering thread owns and cleans its temporary files on success or failure. A controlled long render no longer blocks a concurrent health request.
- Reproduced recovery selecting an older disk copy over a newer browser fallback. Desktop and browser recovery now carry save timestamps; reads choose the newer copy. Successful disk saves clear obsolete browser copies without deleting a newer fallback from another tab.
- Corrected the sheet warning: unquantized notes do not imply that beat detection failed.
- Follow-up verification: 127 Python tests, successful with two optional skips (125 executed), and 18 browser state tests passed. Logs: `build/followup-regression.log` and `build/followup-browser-state.log`. TypeScript/Vite and native Swift builds passed. Tests use controlled renderers/network boundaries; no new real FluidSynth, MuseScore, or physical Windows GPU run is claimed.

## Initial pass fixes

- MIDI-only sessions remain MIDI-only when saved and recovered; an empty WAV can no longer make them fail on reopening.
- Desktop session imports keep the current session if the new MIDI cannot be saved. Re-exports fall back to Results when the selected folder disappears or is unwritable. Existing files are never overwritten.
- Recovery actions are offered only when a saved recovery file is available. Failed recovery saves leave the MIDI usable and give a specific warning.
- Browser audio decode and session import results cannot replace newer selections. Cancelling or leaving during an import prevents it from repopulating the screen.
- Browser Cancel explicitly signals its client/run pair; another tab or a delayed request cannot cancel another run. Engine work stops at the next event boundary, not in the middle of a GPU operation.
- A stream that closes without a final MIDI reports an error instead of displaying completion. Partial exports rebuild the instrument list from retained notes.
- MIDI-only browser sessions play at full centered MIDI volume even after Original-only or stereo playback. They show that no original audio is present instead of offering an unusable comparison mixer.
- Mac restores the normal tempo interpretation from numeric session values; Windows restores numeric subdivision values. Windows keeps Cancel accessible and blocks new work if its worker has not finished stopping.
- Windows Finish here retains existing warnings. Session-save messages no longer claim embedded audio when the project has none.
- Mac build and packaging copies use `.noindex` folders so future builds do not clutter Spotlight with launchable duplicates.

## Initial pass verification (build 8)

- Full Python suite: 125 tests, successful with two optional skips (123 executed). Covers shared engine, MIDI timing, session interoperability and recovery, failed/atomic saves, partial export, scoped server cancellation, worker shutdown, upgrades, and offscreen Windows UI behavior. Log: `build/audit-regression.log`.
- Eight browser state regression tests execute the TypeScript methods against controlled decode/network boundaries. Log: `build/audit-browser-state.log`.
- Windows UI suite at 200% scaling: 28 tests, all passed; light/dark screenshots generated. Reviewed the options layout and app-information panel. This is Qt offscreen rendering on macOS, not a physical Windows display. Log: `build/audit-ui-windows-200.log`.
- Actual browser smoke test against an isolated local server: gear and information dialog; 560×730 layout; import a MIDI-only 170 BPM / 7/8 fixture; reload and recover it; change to 120 BPM / 6/8; Apply restores download availability and shows dotted-quarter BPM with Original timing. Original/MIDI comparison controls are absent without audio. No browser console errors. This uses controlled MIDI, not live model inference.
- TypeScript checks, production frontend build, and native Swift compilation passed. Vite retains its existing bundle-size advisory.
- Windows CI now includes partial-export/cancellation and browser-state tests, plus 200% scaling. The workflow has not been run remotely as part of this local pass.

## Release limits

During the original audit, the installed Mac session was not closed or restarted. The later build-12 restart and its current startup status are recorded in `FINAL_READINESS.md`. Native compilation and shared tests do not replace a complete workflow walkthrough. The browser preview used a separate recovery folder and did not overwrite the user's recovery session.

Before stable 1.0: complete the physical Windows installer/upgrade and CPU/GPU checks in `WINDOWS_HANDOFF.md`, verify exports in the intended DAW, and perform owner signing/notarization. Existing complex-recording Auto tempo accuracy limitations remain; changing-meter suggestions are now limited to repeated percussion evidence; see `METER_EVIDENCE.md`. This pass does not claim perfect rhythm inference or introduce a new quantization model.
