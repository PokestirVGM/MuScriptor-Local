# Validation on this Mac

Machine: Apple Silicon MacBook Pro, macOS 26.6.2, 64 GB memory (user supplied).
Engine: official MuScriptor 0.3.0, source revision `7f213afecf23bd6a1b8672aa223690ee9807cefb`.
Python 3.12.14, PyTorch 2.14.0, native ARM64 FFmpeg 7.1.

Completed checks:

- Inspected upstream README, Python model API, MIDI writer, audio loader, HTTP server and installed CLI help before implementation.
- Native application compiled, ad-hoc signed, installed in the user's Applications folder and launched through macOS.
- The running app reports **MuScriptor Large • Apple MPS • Local**. Independent PyTorch tensor arithmetic completed on `mps:0` outside the command sandbox.
- All sixteen wrapper tests pass (rerun for 1.0 Beta). These decode actual stereo 44.1 kHz WAV, MP3, FLAC, M4A and AAC, confirm upstream's mono 16 kHz output, check corrupt-file errors, cleanup after success/failure, disk-space errors, collision-safe saving, permission fallback and device-error classification.
- Hugging Face login/license access succeeded through the native secure field. Credentials were stored with owner-only permissions; the token was not sent through chat or command arguments.
- The initial Xet download failed at Hugging Face's CDN. Replaced it with the official Hub client's HTTP transport and verified live byte-based progress in the app. Partial Xet data was automatically removed by Hub; the failed-session log was cleaned up.
- The portable app's bootstrap was run in a fresh temporary directory and installed all 55 compatible dependencies. The official MuScriptor API and bundled FFmpeg were then imported/run successfully from that fresh environment. That disposable installation has been removed.
- The share archive has no embedded local installation path and contains no credentials, model checkpoint, Python environment, or personal audio. Hardware compatibility beyond this Mac has not been tested.

## 1.0 Beta model and output controls

- Rebuilt the native app and checked its model selector and readable cache path in the running macOS window.
- All sixteen wrapper tests pass, including separate caches for Small/Medium/Large, environment-specific cache paths, same-revision config/weights, selected-model loading, download progress metadata, releasing the previous model on a switch, output previews, custom output folders, collision handling, and inaccessible-folder fallback.
- `validate_controls.py` exercised the real worker protocol: Small → Medium → Large, destination planning, then a complete offline Large transcription into a custom folder. Network calls were prohibited with a Python audit hook.
- The original 12-second test melody completed all three chunks on Apple MPS, producing 20 note-on events and 11.2298895 seconds of MIDI. The actual output matched the preview, with zero network attempts and no warnings. Temporary validation files were removed after checking.
- Large's 5,465,642,136-byte checkpoint matched the official Hub blob SHA-256 (see `model-integrity.txt`).
- Small and Medium repository routing and switching were tested; their actual checkpoints have not been downloaded or transcribed on this Mac. They require separate model-term acceptance.

Supporting records for this release: `model-controls-results.json`, `model-controls-run.txt`, and `wrapper-tests.txt`.

Supporting records: `wrapper-tests.txt`, `portable-install.txt`; original test melody source: `make_audio.py`.
