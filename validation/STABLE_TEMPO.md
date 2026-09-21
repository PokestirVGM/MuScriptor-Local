# Auto tempo-map correction

Validated 2026-09-21 on the existing South Province transcription. The prior map exported individual detector intervals whenever a global straight-line fit exceeded 15 ms of error. This converted timestamp jitter and false beats into hundreds of tempo events.

Auto now identifies supported beat runs, filters local timestamp jitter, repairs isolated missing/extra beats where supported, and simplifies the estimated grid into linear sections. The grid approximation tolerance is 60 ms relative to the locally filtered beat estimates. This is not a limit on note playback accuracy. Ambiguous passages are bridged and explicitly disclosed; the system does not establish a ground-truth tempo there. Manual BPM and explicit anchors bypass this automatic fitting.

The shared implementation covers Mac, Windows, and local web exports, including reopened sessions. Existing MIDI files require re-export from the updated app.

## Recording check

- Before: **369 tempo events**. After: **4 tempo events**.
- New map: approximately 161.78 BPM from the beginning, 153.03 at 8.85 seconds, 139.79 at 18.26 seconds, and 140.05 at 62.04 seconds.
- The opening/transition is uncertain; those values are estimates, not independently verified musical tempo changes.
- All **8,208 note-on/note-off events** retained. Maximum deviation from original unquantized transcription: **0.1162 ms**, caused by MIDI tick/tempo rounding. This does not measure the transcription model's accuracy against the audio.
- No new inference or audio stretching was used. User audio, sessions, and MIDI outputs remain in ignored local build storage.

Regression checks cover jitter around constant 140 BPM, supported 120 → 240 → 100 BPM changes, a gradual tempo ramp, isolated missed/extra beats, an unreliable transition, original note-time preservation, and existing manual/compound-meter behavior. See the release-candidate validation for platform limitations.

## Near-integer normalization and second recording

Supported constant Auto maps now normalize to whole BPM only when the estimate differs by at most 0.05 BPM and the maximum projected grid displacement from the first downbeat to either recording endpoint is at most 20 ms. The time-to-musical-position map is rebuilt; original note seconds are preserved. Uncertain estimates, manual settings, explicit anchors, and variable maps bypass this step.

The full 212.90-second Wild Pokémon battle recording produced 7,031 notes, a suggested 4/4 meter, and a single estimated 169.99247 BPM tempo. Normalization selects 170 BPM, with approximately 9.4 ms of projected grid displacement. All 14,062 note starts/ends were retained within 0.1198 ms of the unquantized transcription. The MIDI stores the nearest integer-microsecond tempo, 352941 µs per quarter, which decodes to approximately 170.000085 BPM; this is file-format precision, not a second tempo estimate. No new model inference was needed for the re-export.

Tests additionally reject rounding when the BPM difference exceeds 0.05 or the full-duration drift exceeds 20 ms, and retain manual/anchor values and uncertain short estimates.
