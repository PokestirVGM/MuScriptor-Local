# MuScriptor Local for Windows

**Current source: 1.0 Release Candidate 1.** Published Beta 4 remains separate. Session save/open/recovery, cancellation, strict-quantization disclosure, export readiness, and staged upgrades are shared with macOS. See [the release candidate checklist](WINDOWS_HANDOFF.md).

An easy local desktop app for the official MuScriptor engine. The installer and app handle a private Python environment, engine dependencies, model downloads, and Small/Medium/Large selection. Audio and transcription stay on your PC. Windows 10/11 x64 is supported; Windows ARM is not included. AMD acceleration through DirectML remains experimental. The owner reported successful RX 6800 XT testing after the Beta 4 fix; this release candidate still needs Windows hardware validation. Existing users must choose **Cog menu → Repair Dependencies** after upgrading. This is an independent community launcher for MuScriptor by Kyutai and Mirelo.

For normal use, you do not install Python or Node or run terminal commands. The app manages setup in your user folder and caches the models you download. The installer bundles the app and engine source; first launch downloads the private runtime and selected models, so Internet access and your own Hugging Face model access are needed initially. Optional MuseScore/FluidSynth features have additional requirements.

## Current development interface

This release candidate includes the compact desktop interface and local web GUI. The Windows Qt interface closely follows the current macOS layout: a compact 560-pixel default width, a small Small/Medium/Large segmented control, matching charcoal colors and spacing, a dashed audio drop area, neutral instrument rows, rounded checkboxes and panels, and a completion view with Save MIDI Copy and Reveal in Explorer actions. The gear menu provides sessions, processor and app information, model folder, logs, repair, and export requirements. Colors follow the light or dark palette at launch. Windows retains its native title bar, Segoe UI font, file dialogs, and Explorer actions. The window can be resized, and the page scrolls for longer content and larger display scaling.

Search **Instruments** to add supported upstream groups; click a selected item’s × to remove it. Empty means unrestricted detection. **Quantize** and **Create A/B audio render** both start unchecked and use the same worker APIs as the Mac. Tempo Auto follows detected beats; Manual sets a known BPM without changing playback speed or the original start. Time signature and Quantize are separate controls. Quantize optionally snaps individual notes; leave it off to preserve their times. Advanced contains beat anchors, pickup position, and meter changes. The desktop and bundled web GUI share the same timing implementation; see the README for compound-meter interpretation and detection limitations.

A/B audio has original audio on the left and performance-timing MIDI synthesis on the right, even when the separately exported MIDI is quantized. Install FluidSynth for Windows, add the directory containing `fluidsynth.exe` to your user `PATH`, and reopen the app. Use **Choose SoundFont…** to select a local `.sf2` file. Rendering does not download a SoundFont. Missing dependencies or rendering failures preserve the completed MIDI and show a warning. Successful A/B audio gets its own saved-path display and Explorer button. Saving a MIDI copy does not move the A/B audio.

Gear → **Processor and App Information** contains the Automatic/GPU/CPU selector, active backend, version, and model folder. Model selection, local processing, download progress, safe output naming, repair, and process cleanup retain the existing Windows behavior.

Qt tests cover the controls, state transitions, and long paths at the minimum window size. Windows builds use Qt's Windows platform plugin so previews include real system fonts, run these tests at 100%, 150%, and 200% scaling, and provide a **Windows-UI-Previews** artifact showing light and dark ready, options, completion, setup, and download states. Earlier Beta 2 GPU/options checks are historical; see [Beta 2 validation](validation/WINDOWS_BETA_2.md). The current candidate still needs its own physical Windows run. Follow [the Windows handoff](WINDOWS_HANDOFF.md): build the installer, let the user try it, and obtain their explicit approval before publishing a new beta.

## Install

### Official web GUI in current builds

Current `main` builds also bundle the official web frontend from the same pinned MuScriptor revision as the engine. Click **Open Web GUI** after downloading a model: it opens in your browser and reuses the app's installation, selected model, and processor. No separate web setup or second transcription-model download is needed. Keep the desktop app open; **Return to Desktop** stops the web server and any active web transcription, then restores the latest saved session. Save/apply browser changes first; unsaved edits are not retained. Browser exports use browser download settings. Optional playback can fetch a SoundFont, and sheet-music export requires MuseScore 4+.

The candidate includes the latest shared UI and timing updates. It has not been approved for publication; see [the handoff instructions](WINDOWS_HANDOFF.md).

### Installing the published beta

1. Download **MuScriptor-Local-1.0-Beta-Windows-x64-Setup.exe** from the [Windows release](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-beta.windows.4).
2. Run the installer. It installs for your account and creates a Start Menu shortcut and uninstaller; administrator access is not required.
3. Open MuScriptor Local and allow first-run engine setup to finish. Internet access is required for the private Python runtime and CPU or CUDA dependencies.
4. Choose a model. Accept that size's Hugging Face terms yourself, then connect your own read token in the app. Each size requires separate acceptance and download.
5. Choose audio, review the MIDI destination, and click **Transcribe**. **Change Output Folder** selects another destination; existing MIDI files get a numbered filename instead of being overwritten.

The **Portable.zip** alternative contains the same app. Extract the whole archive and keep the executable, **_internal**, and **Legal** folders together. The engine, cache, and settings still live in your Windows account.

CUDA setup downloads roughly 3 GiB of PyTorch packages plus other dependencies. Large downloads about 5.47 GB of weights. Allow at least 20 GB of free disk space for CUDA setup and Large, including extraction and cache overhead. Additional models require more space.

## Processor selection

**Automatic** chooses the available NVIDIA GPU with the most memory, then an available DirectML GPU, otherwise CPU. With DirectML, recognizable discrete Radeon RX/Pro adapters are preferred over integrated graphics, then DirectML's default adapter. A specific detected GPU or CPU can also be selected. The window reports processor names; CUDA reports total memory capacity, not free memory or a guarantee that every model and recording will fit. DirectML does not report memory capacity.

The worker checks the loaded decoder's actual device. Recognized GPU failures in desktop transcription retry the complete transcription on CPU with a warning. An unavailable saved GPU returns to Automatic. The local web GUI uses the same loaded model and adapter; if inference fails there, return to the desktop and choose CPU to retry.

The private engine uses Python 3.12.14 and matching PyTorch/torchaudio 2.7.1 CUDA 12.8 or CPU packages. DirectML instead pins PyTorch/torchaudio 2.4.1, torchvision 0.19.1, and torch-directml 0.2.5.dev240914 to match Microsoft's published package dependencies. No system Python or driver is changed. A compatible graphics driver is required. See [validation results](https://github.com/PokestirVGM/MuScriptor-Local/blob/v1.0.0-beta.windows.2/validation/WINDOWS_BETA_2.md) for previously tested hardware and limitations.

## AMD GPUs: DirectML (experimental)

This feature was included in Windows Beta 3 and corrected in Beta 4. It targets DirectX 12 AMD GPUs such as the Radeon RX 6800 XT on Windows 10/11 x64. It uses Microsoft's [PyTorch DirectML backend](https://learn.microsoft.com/en-us/windows/ai/directml/pytorch-windows). The RX 6800 XT is not listed in AMD's [native Windows ROCm 7.2.1 support matrix](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2.1/docs/compatibility/compatibilityrad/windows/windows_compatibility.html), so installing ROCm is not the setup path for this card.

1. Update the Radeon graphics driver and install a Windows build made from the updated source.
2. For an existing installation, choose **Cog menu → Repair Dependencies**. First-time setup selects DirectML automatically when AMD graphics are detected and NVIDIA's setup tool is absent. Cached models are retained.
3. Start with **Small** and a short recording. Expand processor settings and confirm **DirectML (experimental) — AMD Radeon RX 6800 XT**, or select that adapter explicitly if the machine also has integrated graphics.
4. Transcribe and check that the footer still says DirectML when it finishes. A warning and CPU footer mean the desktop retried on CPU, not that the GPU run succeeded.

The transformer decoder runs on the GPU in float32. Audio conditioning, including the complex-valued spectrogram, stays on CPU, and its completed outputs transfer to the GPU. This avoids unsupported complex DirectML operations and keeps the official model and weights unchanged. CPU activity during transcription is expected. Some other operations may fall back individually to CPU, limiting speed. The existing Large default is unchanged; use Small first to reduce memory pressure.

**Validation limit:** previous Beta 4 hardware checks and owner feedback do not validate the new release candidate. Keep DirectML experimental. Run the candidate checklist on your PC and record the exact adapter, model, and outcome; no universal speedup is promised.

For development or if automatic hardware detection fails, close the app and run this from the updated source checkout in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\bootstrap-windows.ps1 -Root "$env:LOCALAPPDATA/MuScriptor Local/Engine" -Resources "$PWD" -Compute directml
```

Reopen the updated app afterward. The processor picker can switch to CPU without reinstalling. Developers can use `-Compute cpu` or `-Compute cuda` to replace the engine packages; automatic repair redetects the hardware. On a machine with both NVIDIA and AMD adapters, automatic setup prefers CUDA, so explicitly request DirectML to try the Radeon.

After caching a model in the app, a hardware check from the source checkout can verify a complete GPU run and produce a MIDI in the chosen output folder:

```powershell
& "$env:LOCALAPPDATA/MuScriptor Local/Engine/.venv/Scripts/python.exe" .\validation\validate_directml.py "C:/Audio/short-test.wav" --model small --output "C:/Audio/GPU-check"
```

The check fails if no DirectML adapter is usable, the selected model is not cached, or desktop inference falls back to CPU. Record the GPU, driver, model, audio length, wall time, and warnings before comparing with CPU using the same settings.

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

By default, Strict quantization is off. Auto tempo may download the optional beat helper once, independently of quantization. If it is unavailable, the app preserves performance timing, discloses placeholder 120 BPM, and allows a manual grid. Timing edits reuse the current transcription.

## Recovery and updates

**Try Again** repairs incomplete engine setup. **Cog menu → Repair Dependencies** repeats automatic engine setup. **Cog menu → Show Logs** opens local diagnostics; redact personal paths before sharing any log excerpts.

Close the app before upgrading through the installer. Cancel operation stops transcription or model downloads and keeps selection/settings. Closing during work also cancels the active operation; completed MIDI remains intact. Retry interrupted model downloads in the app; the current Hugging Face client may restart an interrupted file, so allow time and disk space for another full download. Uninstall removes the app and shortcuts while retaining engine files, shared model caches, credentials, settings, and MIDI. Remove retained data separately only if you no longer need it.

## Beta scope

- The installer and executable are unsigned.
- Large-model CUDA and offline CPU transcription were tested on Windows 11 with an AMD Ryzen 9 9950X and NVIDIA GeForce RTX 5070 Ti (16 GB), driver 610.88.
- Small and Medium transcription, other GPUs, Windows 10, and the full upgrade/uninstall preservation cycle were not independently validated on this PC.
- Beta 2 passed offline CUDA transcription using a freshly downloaded Large model, with zero socket/DNS attempts. See the validation record for notation, A/B, and local web GUI results.
- Transcription is approximate and may require musical editing. CPU mode is slower.
- Downloads contain no model weights, credentials, personal recordings, MIDI results, or private logs. The official web GUI includes its two unchanged public example audio clips. Component notices are in **Legal**.

The [macOS Beta 3 release](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-beta.3) remains available. Windows Beta 2 is a separate release approved by the owner; macOS Beta 3 is unchanged.

## Development

Use a dedicated Python 3.12 environment, Git, Node.js 22+, pnpm 10.20.0, and Inno Setup 6, then run tools/build-windows.ps1. Node and pnpm bundle the official web frontend at build time; installed-app users need neither. The Windows workflow builds both packages, checks the UI, local web server, and worker, smoke-tests installation, and tests first-run setup in Windows PowerShell with an engine path containing spaces. Resolved engine dependencies are recorded locally in Engine/runtime/installed-packages.txt.
