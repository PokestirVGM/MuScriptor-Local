# Experimental DirectML implementation — 2026-09-21

Target: Windows 10/11 x64, AMD Radeon RX 6800 XT. Windows Beta 3 includes this experimental implementation. Windows Beta 2 and all macOS releases remain unchanged.

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
