# Experimental DirectML implementation — 2026-09-21

Target: Windows 10/11 x64, AMD Radeon RX 6800 XT. This is source work for a future build; published Windows Beta 2 is unchanged.

## Checks completed on the development Mac

- Complete local unittest suite: 67 tests run, 66 passed, one optional visual-artifact test skipped.
- New adapter tests cover CPU conditioning with real upstream spectrogram/decoder computation, unchanged CPU outputs, decoder/output transfer to a distinct meta device, discrete GPU preference, missing/unusable adapters, DirectML error classification, and CPU recovery after failed GPU model transfer.
- Windows UI test confirms that the Radeon/DirectML option is selectable and does not display the CPU-only hint.
- Windows x64 Python 3.12 dependency resolution succeeded for the upstream requirements and torch 2.4.1, torchaudio 2.4.1, torchvision 0.19.1, torch-directml 0.2.5.dev240914 (57 resolved packages).
- Whitespace/diff checks passed.

The first sandboxed runs could not access the host's Qt processor detection; the full suite passed outside that sandbox. CPU/meta adapter tests stub upstream's GPU timing synchronization so CPU tests do not initialize the Mac's unrelated MPS device.

## Still required on Windows

- Run the updated Windows workflow: it now installs DirectML after the existing CPU checks and runs adapter/worker tests against those exact dependencies. That workflow was added, not executed from the development Mac.
- Build the updated Windows executable/installer and verify upgrade plus Repair Dependencies on the friend's machine.
- Verify AMD detection, driver initialization, and successful complete MIDI transcription on the physical RX 6800 XT, first with Small and then the desired model.
- Compare CPU and DirectML elapsed time on the same recording/model/settings. Check warnings for individual CPU operator fallbacks; do not count a complete CPU retry as GPU success.
- Exercise the local web GUI with the same mixed CPU/GPU model if that interface is used.

Use `validation/validate_directml.py` with a cached model and a local recording as described in `WINDOWS.md`. It rejects a complete CPU fallback. No physical AMD compatibility, speedup, or Large-model memory capacity is claimed by the local tests.
