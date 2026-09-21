# Windows Beta 2 validation

Validated on 2026-09-20 (local time). The owner explicitly approved this candidate for Windows beta publication after installer handoff. Approval is recorded separately from test evidence; it does not imply that every remaining manual check was independently verified. macOS Beta 3 and its three asset digests are unchanged.

## Build and interface

- Installer version: `1.0.0-beta.windows.2`, with the existing installer AppId for upgrades.
- Candidate packages were built from commit `3c93e39`. [Windows build 35552378063](https://github.com/PokestirVGM/MuScriptor-Local/actions/runs/35552378063) passed the build, normal and 150% UI checks, packaged startup, installer smoke test, fresh CPU setup, and worker/option/web tests. Subsequent validation-document updates do not change the packaged app sources or bundled README.
- The desktop heading is **MuScriptor Local**. The compact interface, instrument picker, notation option, A/B option, and bundled official web GUI are included.
- Local checks: 24 worker tests, 12 transcription-option tests, 3 web tests, and 19 Windows interface tests. All 19 interface tests also passed at 150% scaling with generated light/dark previews.
- Fixed worker cleanup when a restricted Windows account denies `taskkill`: the app also uses its own process handle. A real-child regression test covers Return to Desktop and Quit.

## Physical Windows PC

- Windows 11 x64, AMD Ryzen 9 9950X, NVIDIA GeForce RTX 5070 Ti (16 GB).
- Fresh automatic CUDA setup from the packaged resources completed in Windows PowerShell, using a path with spaces. Python 3.12.14 and PyTorch/torchaudio 2.7.1+cu128 imported successfully; CUDA was available and all 55 installed packages passed dependency checks.
- The sandbox cannot use Windows Schannel for the initial downloader fetch, so this local setup test was seeded with the existing `uv.exe`. CI tests the full first-run downloader/runtime/CPU dependency installation without that seed.
- A sandboxed silent installer attempt stopped before installation because Windows shell-folder resolution was unavailable to the sandbox account. CI installer tests and the owner's normal interactive install are separate checks; the sandbox failure is not represented as a successful physical install.

## Real local processing

- Downloaded the full Large checkpoint (5,465,642,136 bytes) into a separate initially empty cache through the app's download code. It emitted 524 progress updates and recognized the complete weights alongside the pinned config. The download was interrupted and retried; the current Hub client restarted the file, as documented.
- The downloaded weights' SHA-256 matched the Hub blob hash.
- Loaded that freshly downloaded cache using the freshly installed CUDA engine and repeated offline transcription successfully: all three chunks, 20 notes, 11.23 seconds of MIDI, and zero socket/DNS attempts.

- Large on CUDA with a Python audit hook rejecting socket connection and DNS calls: all three chunks of the generated 12-second melody completed; 20 note-on events and 11.23 seconds of MIDI; zero network attempts. Actual model parameters were on `cuda:0`.
- Custom output folder with spaces and Unicode passed. Existing MIDI was preserved and a distinct collision-safe filename was written.
- The fresh CUDA engine passed acoustic-piano conditioning: the output MIDI contained program 0 only.
- Enabling notation fetched the 77.3 MB tempo helper. The generated melody yielded no usable beat subdivision; the app correctly warned and retained performance timing.
- A second generated 32-second steady-beat sample successfully produced quantized MIDI on CUDA: all seven chunks completed, `quantized=true`, and no warnings.
- Requesting A/B without FluidSynth preserved the completed MIDI and reported the missing optional dependency.
- A separate successful render used temporary FluidSynth 2.6.1 and a checksum-verified MuseScore General SF2. It produced 44.1 kHz stereo audio with two non-silent, distinct channels (original left, synthesis right). Neither dependency was bundled or added to the system PATH.

## Official local web GUI

- A real Large model ran behind the desktop's loopback server. The official page loaded in a browser and the generated melody completed through the browser interface.
- An additional real HTTP transcription with acoustic-piano conditioning completed all three chunks and returned valid MIDI bytes.
- Desktop integration verified the emitted local browser URL, reuse of the selected cached model, locked desktop controls during web use, return to a ready desktop, and closed server ports after Return to Desktop and Quit. The integration harness intercepts the OS browser-launch call; the owner's default-browser handoff remains part of interactive acceptance.
- The browser displayed its export menu. The in-app browser did not report a download event after clicking MIDI; the actual browser-saved file and its destination still require owner confirmation. The HTTP MIDI payload itself was validated.

## Approval and remaining beta limits

- Package audit checks every entry for credentials, private home paths, local logs, weights, and personal audio/MIDI. The only audio allowlist is the official web GUI's two public example MP3s, each required to match the pinned upstream file byte for byte. The candidate app's packaged startup test passed locally.

- Install/upgrade and launch the candidate normally, check Windows scaling and Explorer actions, transcribe a chosen file, open the web GUI, save a browser MIDI export, and return to the desktop.
- Both notation and A/B success/fallback paths were exercised with generated test audio. Accuracy on the owner's recordings and other material remains part of musical evaluation.
- Small/Medium require the user's separate model terms and were not downloaded or transcribed in this session. Other GPUs, Windows 10, and a complete uninstall/preservation cycle remain unvalidated.
- The executable and installer are unsigned. First setup and new model downloads require Internet access. Current Hugging Face downloads may restart an interrupted file.
- The owner explicitly approved release of this candidate. Release tag: `v1.0.0-beta.windows.2`. The exact tested installer and portable package are used; existing releases, including macOS Beta 3, are preserved.
