# Validation on this Mac

Machine: Apple Silicon MacBook Pro, macOS 26.6.2, 64 GB memory (user supplied).
Engine: official MuScriptor 0.3.0, source revision `7f213afecf23bd6a1b8672aa223690ee9807cefb`.
Python 3.12.14, PyTorch 2.14.0, native ARM64 FFmpeg 7.1.

Completed checks:

- Inspected upstream README, Python model API, MIDI writer, audio loader, HTTP server and installed CLI help before implementation.
- Native application compiled, ad-hoc signed, installed in the user's Applications folder and launched through macOS.
- The running app reports **MuScriptor Large • Apple MPS • Local**. Independent PyTorch tensor arithmetic completed on `mps:0` outside the command sandbox.
- All eight wrapper tests pass. These decode actual stereo 44.1 kHz WAV, MP3, FLAC, M4A and AAC, confirm upstream's mono 16 kHz output, check corrupt-file errors, cleanup after success/failure, disk-space errors, collision-safe saving, permission fallback and device-error classification.
- Hugging Face login/license access succeeded through the native secure field. Credentials were stored with owner-only permissions; the token was not sent through chat or command arguments.
- The initial Xet download failed at Hugging Face's CDN. Replaced it with the official Hub client's HTTP transport and verified live byte-based progress in the app. Partial Xet data was automatically removed by Hub; the failed-session log was cleaned up.
- The portable app's bootstrap was run in a fresh temporary directory and installed all 55 compatible dependencies. The official MuScriptor API and bundled FFmpeg were then imported/run successfully from that fresh environment. That disposable installation has been removed.
- The share archive has no embedded local installation path and contains no credentials, model checkpoint, Python environment, or personal audio. Hardware compatibility beyond this Mac has not been tested.

The initial full Large download and actual transcription tests are still running. This file will be updated with their results before delivery.

Supporting records: `wrapper-tests.txt`, `portable-install.txt`; original test melody source: `make_audio.py`.
