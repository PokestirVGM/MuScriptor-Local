# macOS Beta 4 validation — 2026-09-21

- Tag: `v1.0.0-beta.mac.4`; bundle build 5, display version 1.0 Beta 4.
- Built the native Apple Silicon app and portable ZIP with the checked-in MuScriptor ICNS icon. Local code-signature verification passed; the app is not Apple-notarized.
- Current-code regression suite: 71 tests run, 69 passed, 2 skipped (optional/platform-specific checks). The subsequent release changes only update version metadata and documentation.
- Complete offline Large-model transcription passed on Apple MPS using the original 12-second validation melody: 3 chunks, 20 notes, MIDI duration 11.2298895 seconds, zero socket/DNS attempts, no GPU fallback warnings.
- Checked ZIP integrity, bundled notices and icon, version metadata, and absence of checkout-specific paths, model weights, private MIDI, caches, and credentials. Removed the development-only MuScriptorRoot plist key from the portable bundle.
- This release adds the Mac icon and packages the current shared worker. DirectML-specific execution changes are Windows-only. No new model-quality or speed claims are made.
