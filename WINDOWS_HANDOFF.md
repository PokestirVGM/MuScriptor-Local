# Windows 1.0 beta handoff

## Release update — 2026-09-20

The Windows beta is now prepared as `v1.0.0-beta.windows.1`. See [WINDOWS.md](WINDOWS.md) for installation and [validation/WINDOWS_RESULTS.md](validation/WINDOWS_RESULTS.md) for completed physical-PC checks and explicit limits. The owner confirmed the app works and requested publication with those limits. The original handoff below records the pre-validation state and checklist; it is not a claim that every item was completed. The macOS tag `v1.0.0-beta.2` is preserved.

## Current state

- The newest public macOS release is `v1.0.0-beta.2`, titled **MuScriptor Local 1.0 Beta — macOS**. Keep it available when adding a Windows release.
- Windows development is on `codex/windows-preview`. Start from this branch, not the macOS-only release tag.
- `src/WindowsApp.py` provides model selection, local download paths, output preview/folder selection, readable hardware details, GPU/CPU selection, and a separate worker process.
- `src/worker.py` supports Windows app-data locations, CUDA device selection, actual model-device checks, CPU fallback reporting, and Windows-safe output publication.
- `tools/build-windows.ps1` builds a portable directory archive and a per-user Inno Setup installer. The setup installer is `MuScriptor-Local-Windows-x64-Setup-Preview.exe`; it creates shortcuts and an uninstaller. First launch installs the private Python engine automatically.
- `.github/workflows/windows-preview.yml` builds on a Windows runner, tests interface states, launches the packaged app, installs the setup package, and checks the CPU worker. The newest run is authoritative; inspect its result before relying on its artifacts.
- Local development validation passed 21 worker tests and 7 headless interface tests. A complete offline Large transcription also passed on Apple MPS after the shared worker changes. These are not NVIDIA hardware-validation results.

## Finish on the Windows PC

1. Read the latest build results and repair any remaining CI failures. Retrieve the installer/zip from a successful run, or build locally using Python 3.12, Git, and Inno Setup 6. See WINDOWS.md.
2. Install through the setup program with a normal user account. Verify shortcuts, first launch, private environment setup, and readable errors. Verify an upgrade preserves settings/cache/results and that uninstall removes only the app/shortcuts.
3. Identify the PC's processor, GPU(s), driver, and memory. Confirm that Automatic, a specific supported NVIDIA GPU, and CPU report the actual device used. AMD/Intel GPU acceleration is outside this preview; use CPU and describe that limitation accurately.
4. Use the owner's Hugging Face account and authorized cached/downloaded models. Do not read tokens into chat or command arguments. Accepting any new model terms remains the owner's action. Test one complete original/permitted recording, then model switching and any other sizes the account can access.
5. Check the actual MIDI output, custom destinations (spaces/non-ASCII names), collisions, offline startup after caching, retry/repair, and quitting during downloads/transcription. Use the generated sample melody where possible.
6. Confirm CUDA driver compatibility with the pinned PyTorch/torchaudio 2.7.1 CUDA 12.8 build. If changing the build, update installer constraints and retest on the PC. Do not claim CUDA support solely from the presence of a GPU.
7. Inspect the installer, archive, bundled legal notices, and source for credentials, personal paths, local logs, recordings, or model weights. The app is unsigned; decide whether to distribute this beta unsigned or arrange signing before publication. No signing certificate has been configured.
8. Update WINDOWS.md and validation notes to state exactly what passed. Merge the reviewed Windows work when ready, then publish a clearly labeled Windows 1.0 beta with setup installer, portable zip, checksums, installation steps, and known limitations. Use a distinct tag (for example `v1.0.0-beta.windows.1`) so the macOS source tag is unchanged.

The repository's current public docs are installation-neutral and include wrapper/upstream licenses. Earlier Git history still contains old development paths; this cleanup did not rewrite history. Do not reintroduce those paths or commit raw local logs.
