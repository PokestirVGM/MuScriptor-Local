# Windows preview

The Windows interface is being developed separately from the published macOS 1.0 Beta. It shares the official MuScriptor transcription engine and the model/output controls. This is an x64 Windows 10/11 preview; Windows ARM and AMD/Intel GPU acceleration are not included.

## Processor display

The app reports the actual backend and processor name. NVIDIA CUDA devices include their dedicated GPU memory; CPU mode reports system memory. Automatic chooses the available NVIDIA GPU with the most memory, or CPU when CUDA is unavailable. The Processor selector also allows a specific available GPU or CPU. Memory figures are total capacity, not an estimate of free space or whether a model will fit.

The engine validates where the loaded model actually resides. If a recognized GPU operation fails, the complete song retries on CPU and the display changes to CPU with a warning. If a previously saved GPU is no longer available, startup returns to Automatic. AMD/Intel graphics use CPU in this preview; the app does not claim to accelerate on an unsupported GPU.

On macOS, the shared worker reports the Apple chip, Apple MPS, and shared unified memory. The released macOS beta has its original compact backend label; the development branch adds the hardware detail.

## Build and run

On an x64 Windows machine with Python 3.12 and Git installed:

1. Check out the `codex/windows-preview` branch.
2. Install [Inno Setup 6](https://jrsoftware.org/isdl.php) for installer packaging, then run `powershell -NoProfile -ExecutionPolicy Bypass -File tools/build-windows.ps1` from the project. This installs build dependencies into the current Python environment; use a dedicated virtual environment for development.
3. Run `dist/windows/MuScriptor-Local-Windows-x64-Setup-Preview.exe`. It installs for the current user without administrator access and creates a Start Menu shortcut and uninstaller. A portable zip is also built; keep its entire extracted folder together.
4. First launch installs a private Python runtime and engine under `%LOCALAPPDATA%\MuScriptor Local\Engine`. A visible setup status remains in the window. Logs are under `%LOCALAPPDATA%\MuScriptor Local\Logs` (App → Show Logs).
5. Choose a model, accept that size’s Hugging Face terms, and connect your own read token. The actual model cache path appears in the window.
6. Drop audio in, review or change the MIDI output folder, and click Transcribe.

The app downloads the official uv Python installer and official Python packages. It checks for NVIDIA driver tooling when choosing CPU versus CUDA packages, then the worker checks whether PyTorch can actually use CUDA. A recent NVIDIA driver supporting the selected CUDA build is required for GPU acceleration. No driver or system Python changes are made. The bootstrap uses matching PyTorch/torchaudio 2.7.1 packages and records the resolved dependencies in `Engine/runtime/installed-packages.txt`.

To explicitly set up CPU mode from source, run `tools/bootstrap-windows.ps1 -Root <checkout> -Resources <checkout> -Compute cpu`. For CUDA use `-Compute cuda`. The app's Repair Dependencies command repeats automatic detection. A model-cache download, or new Python dependencies, requires Internet access; audio remains local.

The Python launcher can also be run from a development environment containing `PySide6-Essentials` as `python src/WindowsApp.py`, after setting up the root's `.venv` with the bootstrap.

## Validation and packaging

The `Windows preview` GitHub Actions workflow builds the executable and setup installer on Windows, runs headless UI tests, smoke-tests the packaged executable, installs the CPU worker in a fresh directory, and runs the wrapper tests. Successful runs attach the installer and portable archive to the workflow run. The installer removes only the app and shortcuts when uninstalled; model caches, credentials, and MIDI remain untouched. These checks do not download gated model weights or validate a real NVIDIA GPU.

Before publishing a Windows release, test on the actual PC: first launch, NVIDIA driver detection, actual CUDA model loading and transcription, all three model sizes permitted by the account, drag/drop, output folders with spaces/non-ASCII names, offline startup after download, safe collisions, restart/repair, and quitting during download/transcription. The current Mac cannot establish Windows GPU compatibility.

The executable is not Authenticode-signed. No account credentials, model weights, or recordings are included. Official model licenses and account/terms requirements are the same as for the macOS app.

Implementation references: [PyTorch Windows setup](https://pytorch.org/get-started/locally/) and [Qt process handling](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QProcess.html).

## Continue on the Windows PC

Clone this repository and check out `codex/windows-preview`. Give Codex this prompt:

> Finish the Windows 1.0 beta for MuScriptor Local. Read WINDOWS.md, WINDOWS_HANDOFF.md, and the latest Windows preview workflow results. Test the setup installer, identify this PC's CPU/GPU and available memory, verify the displayed processor against the model's actual device, and run a complete local transcription using an authorized model. Check custom output folders, restart/offline behavior, and installer/uninstaller behavior. Fix any Windows-specific problems, then publish a Windows 1.0 beta release with the installer, portable zip, checksums, and accurate validation notes. Keep the existing macOS release available and do not publish credentials, recordings, local paths, or raw personal logs.
