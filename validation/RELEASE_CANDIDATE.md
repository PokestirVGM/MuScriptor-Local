# 1.0 Release Candidate 1 validation

Validated on Apple Silicon, 2026-09-21. This is a local, unpublished candidate.

Latest pass: [final readiness, build 12](FINAL_READINESS.md). 160 Python tests successful (two optional skips), 18 browser tests, 33 UI tests at 200% scaling, browser recovery/export smoke check, compatible dependencies, and successful native/web/share builds. Build 12 has been installed and restarted; its native information panel confirms the version. Startup completed after the macOS Documents request was resolved; Large is cached and Apple MPS is selected. Complete native workflows, Windows/DAW, optional renderer, and signing acceptance remain open.

Latest rhythm pass: [percussion and meter evidence](METER_EVIDENCE.md), 152 Python tests (two optional skips), 18 browser tests, and six additional actual-model cases. Build 11 supports guarded changing-meter suggestions; dense real-recording accuracy remains unresolved.

Previous rhythm pass: [edge cases and held-out detection tests](RHYTHM_EDGE_CASES.md), 140 Python tests (two optional skips), 18 browser tests; shared engine fixes included in build 10. New complex-rhythm failures remain unresolved.

Previous pass: [usability and failure-path audit](USABILITY_AUDIT.md), with 127 Python tests (two optional skips), 18 browser state tests, compact-window browser checks, and Windows UI checks at 200% scaling.

Partial export: [Finish here validation](PARTIAL_EXPORT.md) covers the new completed-section MIDI export and its tests.

Latest interface update: [UI polish validation](UI_POLISH.md) covers the refreshed branding, gear settings, resizing, Mac menu bar, and 110-test run.

**Accuracy sign-off withheld:** [audio-pulse refinement](RHYTHM_REFINEMENT.md) now passes all 11 authored tempo/grid controls, including the three failures in the initial audit. Complex real recordings, including the DEZOLVE previews, remain unresolved; automatic changing-meter suggestions now work only with sufficiently repeated percussion evidence. Passing export and regression checks do not establish general Auto accuracy.

- Full Python suite after the Auto tempo-map correction and near-integer normalization: **108 tests, successful with two skips** (106 executed). Includes offscreen Qt checks of Windows UI behavior, worker behavior, local HTTP routes, tempo/meter handling, and release lifecycle tests. See [the corrected tempo-map validation](STABLE_TEMPO.md) for both recording comparisons.
- New lifecycle checks cover portable session import/export without model inference, session ownership, recovery across server instances, corrupt session rejection, atomic-save failure, original timing restored after disabling Strict quantization, actual worker cancellation, and failed/interrupted engine-upgrade rollback.
- TypeScript checking and production frontend build passed. Vite retains a bundle-size advisory; it is not a build failure.
- Native Mac release candidate compiled successfully. The isolated candidate opened with session/recovery controls and the revised timing controls. Full native visual walkthrough was not completed because the app state changed during inspection.
- In the actual browser interface, opened the full 186.43-second recording's saved session, inspected the recovered notes/instruments and timing summary, downloaded a portable session, refreshed, and recovered it. This reused the existing transcription. Export readiness correctly reported the installed FluidSynth and missing MuseScore.
- See [rhythm validation](RHYTHM.md) for the full-recording MIDI timing comparison. Tempo/meter changes preserve source playback time; Strict quantization is explicit and intentionally moves individual notes. This candidate does not add a new AI quantizer or Gentle mode.

The source handoff includes the tracked engine/frontend patch and all new release files; it excludes model weights, credentials, recordings, and generated sessions. A clean pinned-engine patch check and archive inventory check accompany packaging.

Still required before stable release: Windows installer/upgrade and physical GPU runs, native display scaling, actual DAW import checks, owner signing/notarization, and verification of the distributed downloads. Follow [the Windows handoff](../WINDOWS_HANDOFF.md). Automated checks and macOS-hosted Qt checks do not establish Windows hardware compatibility.
