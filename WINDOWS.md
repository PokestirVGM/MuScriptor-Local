# MuScriptor Local 1.0 Beta for Windows

An independent desktop wrapper for the official MuScriptor engine. Audio and transcription stay on your PC. Windows 10/11 x64 is supported; Windows ARM and AMD/Intel GPU acceleration are not included.

## Install

1. Download **MuScriptor-Local-1.0-Beta-Windows-x64-Setup.exe** from the [Windows release](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-beta.windows.1).
2. Run the installer. It installs for your account and creates a Start Menu shortcut and uninstaller; administrator access is not required.
3. Open MuScriptor Local and allow first-run engine setup to finish. Internet access is required for the private Python runtime and CPU or CUDA dependencies.
4. Choose a model. Accept that size's Hugging Face terms yourself, then connect your own read token in the app. Each size requires separate acceptance and download.
5. Choose audio, review the MIDI destination, and click **Transcribe**. **Change Output Folder** selects another destination; existing MIDI files get a numbered filename instead of being overwritten.

The **Portable.zip** alternative contains the same app. Extract the whole archive and keep the executable, **_internal**, and **Legal** folders together. The engine, cache, and settings still live in your Windows account.

CUDA setup downloads roughly 3 GiB of PyTorch packages plus other dependencies. Large downloads about 5.47 GB of weights. Allow at least 20 GB of free disk space for CUDA setup and Large, including extraction and cache overhead. Additional models require more space.

## Processor selection

**Automatic** chooses the available NVIDIA GPU with the most memory, otherwise CPU. A specific NVIDIA GPU or CPU can also be selected. The window reports processor names and total memory capacity, not free memory or a guarantee that every model and recording will fit.

The worker checks the loaded model's actual device. Recognized GPU failures retry the complete transcription on CPU with a warning. An unavailable saved GPU returns to Automatic. AMD/Intel graphics use CPU.

The private engine uses Python 3.12.14 and matching PyTorch/torchaudio 2.7.1 CUDA 12.8 or CPU packages. No system Python or driver is changed. A compatible NVIDIA driver is required. See [validation results](https://github.com/PokestirVGM/MuScriptor-Local/blob/v1.0.0-beta.windows.1/validation/WINDOWS_RESULTS.md) for tested hardware and limitations.

## Storage and offline operation

| Item | Default location |
| --- | --- |
| Installed app | %LOCALAPPDATA%/Programs/MuScriptor Local |
| Private engine | %LOCALAPPDATA%/MuScriptor Local/Engine |
| Recovered MIDI | %LOCALAPPDATA%/MuScriptor Local/Results |
| Local diagnostics | %LOCALAPPDATA%/MuScriptor Local/Logs |
| Model cache and Hugging Face credentials | %USERPROFILE%/.cache/huggingface |
| MIDI | Beside the source audio or in your chosen folder |

Cache environment overrides are respected and the app shows the effective model folder. Cached transcription works offline after engine setup and model download. Setup, repair, and new model downloads require Internet access. Credentials are handled by the Hugging Face client and never included in release assets.

MIDI is not quantized. Optional upstream tempo detection is used only when its beat_this-final0.ckpt is already in the standard Torch checkpoint cache. Without it, MIDI uses the upstream default tempo metadata while preserving note timing. Transcription does not download that optional checkpoint.

## Recovery and updates

**Try Again** repairs incomplete engine setup. **App → Repair Dependencies** repeats automatic engine setup. **App → Show Logs** opens local diagnostics; redact personal paths before sharing any log excerpts.

Close the app before upgrading through the installer. Closing during work cancels the active operation; completed MIDI remains intact and model downloads can resume. Uninstall removes the app and shortcuts while retaining engine files, shared model caches, credentials, settings, and MIDI. Remove retained data separately only if you no longer need it.

## Beta scope

- The installer and executable are unsigned.
- Large-model CUDA and offline CPU transcription were tested on Windows 11 with an AMD Ryzen 9 9950X and NVIDIA GeForce RTX 5070 Ti (16 GB), driver 610.88.
- Small and Medium transcription, other GPUs, Windows 10, and the full upgrade/uninstall preservation cycle were not independently validated on this PC.
- Offline CUDA transcription was not separately completed in this validation session.
- Transcription is approximate and may require musical editing. CPU mode is slower.
- Downloads contain no model weights, credentials, recordings, MIDI results, or private logs. Component notices are in **Legal**.

The [macOS v1.0.0-beta.2 release](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-beta.2) remains available.

## Development

Use a dedicated Python 3.12 environment, Git, and Inno Setup 6, then run tools/build-windows.ps1. The Windows preview workflow builds both packages, checks the UI and worker, smoke-tests installation, and tests first-run setup in Windows PowerShell with an engine path containing spaces. Resolved engine dependencies are recorded locally in Engine/runtime/installed-packages.txt.
