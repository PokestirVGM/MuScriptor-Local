# Experimental DirectML implementation — 2026-09-21

Target: Windows 10/11 x64, AMD Radeon RX 6800 XT. Windows Beta 3 includes this experimental implementation. Windows Beta 2 and all macOS releases remain unchanged.

## Windows Beta 4 candidate — physical DirectML regression checks

The RX 6800 XT report showed successful dependency repair and model loading, followed by `Cannot set version_counter for inference tensor` in both desktop and web generation. The candidate removes inference mode on DirectML instances. Further physical tests exposed nested cache writes and waveform collation producing incorrect output; the adapter now rebuilds the used attention cache and keeps waveform preparation on CPU.

- Build source: `07e1e47`; [Windows workflow](https://github.com/PokestirVGM/MuScriptor-Local/actions/runs/35564941160).
- The workflow passed executable/installer startup, normal and 150% UI checks, fresh CPU setup/tests, and pinned DirectML setup/tests. Downloaded installer and portable packages passed the private-content audit and matched the source. Installer SHA-256: `eb7fa8294971ac9877278a688e41e465319565a02075a336dbfba41854de4072`; portable SHA-256: `74bdbe2d26a89b29683e065a161f69c907fdcafb2f02e7d7f28963faf6ef850b`. The owner requested the EXE for testing and explicitly instructed not to publish yet.
- Tested the actual pinned torch 2.4.1 / torch-directml 0.2.5.dev240914 environment in an isolated runtime, preserving the installed CUDA environment.
- All 12 adapter tests passed, including opt-in real-device comparison of eight generated tokens against CPU on both NVIDIA RTX 5070 Ti and integrated AMD Radeon graphics. Cache tests also exercise beam reordering.
- Large completed the generated 12-second melody using DirectML on NVIDIA: 20 notes, about 11.23 seconds of MIDI, 11.47 seconds including model loading. This is a functional check, not a general speed benchmark.
- Large completed the same melody on the integrated AMD Radeon GPU: 20 notes, 11.23 seconds of MIDI, 65.5 seconds including loading. The validation rejected complete CPU fallback. An individual `aten::amin.out` operation fell back to CPU, as reported by DirectML.
- Local official web GUI integration passed with the cached Large model and DirectML selected: three chunks, 20 notes, acoustic-piano filter, successful return to desktop, and server termination when quitting. Hugging Face offline mode was enabled; only the loopback HTTP server was used for the web check.
- 24 worker tests and 12 transcription-option tests passed on the pinned runtime; the earlier UI/web unit checks passed as well.
- Official upstream waveform-and-note assets are wired into Windows executable, setup and window icons, and the next macOS bundle. ICO and ICNS decode correctly; a native macOS build was not run on Windows. Existing macOS downloads are unchanged.

The automated physical checks above use integrated AMD graphics, **not** an RX 6800 XT. The owner's subsequent feedback is recorded below. Support remains experimental. Choose **App → Repair Dependencies** after upgrading. No private audio, credentials, personal paths, or raw local logs are included in this record.

### Owner follow-up

The owner subsequently reported that the candidate works during testing after the RX 6800 XT failure, then explicitly authorized publication as a new Windows release. The brief report did not separately specify desktop versus web results, so it does not expand the detailed hardware checks above. Follow-up build source `1f7f76c` adds the Windows taskbar identity, matching shortcut identity and application-wide icon; it does not change transcription. Native Windows identity/icon checks and the Windows UI suite passed locally (19 passed, one optional visual-artifact test skipped).

The final [Windows workflow, run 35565724775](https://github.com/PokestirVGM/MuScriptor-Local/actions/runs/35565724775), passed all build, UI, installer/executable startup, CPU and DirectML dependency/test steps. Both downloaded release packages passed the private-content audit; bundled engine sources match the checkout. Final installer SHA-256: `97e93413dd116752e0520980fdf53a4d1104ec554a42814d9c4adceaa987867d`. Final portable SHA-256: `1bec226643652c2cd8a49637dbc66148c194d366cbea04d63041103971153619`. These supersede the earlier candidate hashes above; final publication is authorized as `v1.0.0-beta.windows.4`.

## Windows Beta 3 validation — 2026-09-21

- Confirmed the DirectML implementation from commit `b096aee` and prepared Windows installer version `1.0.0-beta.windows.3`.
- Local Windows checks passed: 8 DirectML adapter tests, 24 worker tests, 12 transcription-option tests, 3 web tests, and 20 interface tests (one optional visual-artifact test skipped locally).
- A real Large-model offline CUDA regression passed on the RTX 5070 Ti: all three chunks of the generated 12-second melody, 20 note-on events, 11.23 seconds of MIDI, zero socket/DNS attempts, and preserved output collisions. This is NVIDIA regression evidence, not AMD hardware validation.
- The source Windows workflow passed full CPU setup and DirectML installation/adapter/worker checks against the pinned dependencies: [run 35562710017](https://github.com/PokestirVGM/MuScriptor-Local/actions/runs/35562710017).
- Beta 3 packages use the existing build scripts and release build commit `364d0fb`. Existing users must choose **App → Repair Dependencies** after upgrading.
- The final [Beta 3 Windows build, run 35562782925](https://github.com/PokestirVGM/MuScriptor-Local/actions/runs/35562782925), passed packaging, normal and 150% UI tests, executable and installer startup, fresh CPU setup/tests, and DirectML installation/adapter/worker tests. Later validation-document edits do not change the packaged application sources.
- RX 6800 XT hardware transcription, performance, memory capacity, and AMD web GUI execution remain unverified. The owner explicitly authorized publication with this experimental scope.

## Checks completed on the development Mac

- Complete local unittest suite: 67 tests run, 66 passed, one optional visual-artifact test skipped.
- New adapter tests cover CPU conditioning with real upstream spectrogram/decoder computation, unchanged CPU outputs, decoder/output transfer to a distinct meta device, discrete GPU preference, missing/unusable adapters, DirectML error classification, and CPU recovery after failed GPU model transfer.
- Windows UI test confirms that the Radeon/DirectML option is selectable and does not display the CPU-only hint.
- Windows x64 Python 3.12 dependency resolution succeeded for the upstream requirements and torch 2.4.1, torchaudio 2.4.1, torchvision 0.19.1, torch-directml 0.2.5.dev240914 (57 resolved packages).
- Whitespace/diff checks passed.

The first sandboxed runs could not access the host's Qt processor detection; the full suite passed outside that sandbox. CPU/meta adapter tests stub upstream's GPU timing synchronization so CPU tests do not initialize the Mac's unrelated MPS device.

## Hardware validation still required

- Verify upgrade plus Repair Dependencies on the AMD machine. Windows workflow installation checks do not replace this physical-PC test.
- Verify AMD detection, driver initialization, and successful complete MIDI transcription on the physical RX 6800 XT, first with Small and then the desired model.
- Compare CPU and DirectML elapsed time on the same recording/model/settings. Check warnings for individual CPU operator fallbacks; do not count a complete CPU retry as GPU success.
- Exercise the local web GUI with the same mixed CPU/GPU model if that interface is used.

Use `validation/validate_directml.py` with a cached model and a local recording as described in `WINDOWS.md`. It rejects a complete CPU fallback. No physical AMD compatibility, speedup, or Large-model memory capacity is claimed by the local tests.
