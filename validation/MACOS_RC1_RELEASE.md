# macOS RC1 publication validation

2026-09-21 · Apple Silicon · native build 12 · `1.0.0-rc.1`

Release: [macOS 1.0 RC1](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-rc.mac.1). The owner explicitly requested publication and current README/download links. This is a prerelease, not stable 1.0 sign-off. Existing Windows RC1 and Beta assets are unchanged.

## Source and package

- Updated `main` through Windows commit `7b72759` before building. Those changes affect Windows UI/build behavior and a cross-platform subprocess test; the shared rhythm engine and Mac native code remain the tested build-12 implementation.
- Built with the normal `tools/share.sh` workflow. The portable app removes the development checkout path and installs/updates its private engine in Application Support.
- Package: `MuScriptor-Local-1.0-RC1-macOS-Apple-Silicon.zip`; Apple Silicon, macOS 14+.
- SHA-256: `8776ace813a59310e6cff087592a06cc5ddfd2246e2c35a36bceb1eee435d245`.
- The release also includes `SHA256SUMS.txt`.

## Checks completed for publication

- Python regression: 160 tests successful, two optional skips (158 executed).
- Browser state regression: 18 passed.
- Native optimized Swift build completed; bundled frontend source stamp is current.
- ZIP CRC/inventory checks passed; 88 entries. Required license notices and installation instructions are present. No private checkout paths, credentials, model weights, generated sessions/MIDI, Python caches, or user recordings were included. Upstream's bundled public example clips remain available.
- Extracted app passes `codesign --verify --deep --strict`; executable is arm64, bundle version is 12, minimum macOS is 14.0, and `MuScriptorRoot` is absent.
- Bundled worker, rhythm, meter-evidence, session, audio validation, and server sources exactly match the source checkout.
- The first regression attempt could not initialize Qt's processor detection inside the restricted execution environment. The successful full rerun had host processor access; no code change was needed.

Logs: `build/mac-rc1-publish-build.log`, `build/mac-rc1-publish-tests.log`, `build/mac-rc1-publish-browser.log`, and `build/mac-rc1-publish-archive.log` (local generated files).

## Carried-forward checks and remaining limits

[Final readiness](FINAL_READINESS.md) records the earlier actual build-12 restart: cached Large, Apple MPS on Apple M5 Pro, populated instrument list, and enabled settings/session controls. That was a native startup/settings check, not a fresh full transcription acceptance run. This publication pass does not claim a new model inference run, clean-machine installation, real optional renderer export, or DAW listening/import test.

The package is ad-hoc signed, not Developer ID signed or Apple-notarized. Gatekeeper/download acceptance and clean installation remain limited. MIDI timing preservation does not guarantee correct automatic tempo/meter interpretation; dense and ambiguous recordings still need manual corrections. Strict quantization is optional and intentionally moves notes. See [meter evidence](METER_EVIDENCE.md) and the separate [Windows PC results](WINDOWS_RC1_PC.md).
