# MuScriptor Local

An easy way to run official [MuScriptor](https://github.com/muscriptor/muscriptor) locally as a desktop app. MuScriptor Local handles the private Python environment, model downloads, and switching between Small, Medium, and Large. Transcribe through the native app or open the adapted local web GUI with one click, using the same local model and processor.

This is an independent community launcher for MuScriptor by Kyutai and Mirelo. Audio processing stays on your computer.

**[Download Windows 1.0 Beta 4](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-beta.windows.4)** · **[Download macOS 1.0 Beta 4](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-beta.mac.4)** · [Report an issue](https://github.com/PokestirVGM/MuScriptor-Local/issues) · [Changelog](CHANGELOG.md)

## Current source: 1.0 Release Candidate 1

Published Beta 4 downloads above are unchanged. The release candidate adds portable sessions, recovery, desktop cancellation, explicit strict quantization, export readiness, and staged engine upgrades. It is not a published stable 1.0 release. See [the Windows finishing checklist](WINDOWS_HANDOFF.md) before distributing a Windows build.

**Save Session** stores the original notes, detected beats, current timing settings, and audio in a `.muscriptor` file. Open it in the desktop app or local web GUI on either platform without transcribing again. Sessions include audio, so only share them when you intend to share the recording. The file limit is 256 MB. Desktop sessions embed a decoded mono WAV; browser sessions embed the selected original audio.

While transcription is running, **Finish here & save MIDI** (desktop) or **Finish here & download MIDI** (web) appears after the first 5-second section is complete. It saves the fully completed sections, omits the unfinished section and remaining audio, and closes sustained notes at the cutoff. The file is labeled `_partial`; original playback timing is preserved unless Strict quantization is enabled. Partial sessions keep only the matching audio prefix. **Cancel** still stops without saving a new MIDI. This is an early finish, not pause/resume or automatic loop detection.

The **gear menu** houses Open Session, Recover Last Session, app/version information, and local model details. On desktop, it also provides processor selection, Open Model Folder, export checks, dependency repair, and logs. **Open Web GUI ↗** opens the browser interface. Drag the grip below the desktop instrument list to give it more room; resize the app window from its edges or corners. On Mac, the menu bar also provides File, Edit, View, Window, Help, and Settings (⌘,).

**Recover Last Session** restores the latest completed/applied session from local app storage, including after a restart. Each new recovery replaces the previous one. Keep separate Save Session files for projects you want to retain. Browser-only fallback recovery is tied to its browser address; the desktop-launched GUI saves to app storage across address changes. A recovery save failure is disclosed while MIDI remains available.

**Cancel operation** stops a desktop transcription or model download without closing the app and restarts the engine. File selection and timing settings remain. Cancel does not promise resumable inference or partial MIDI; retry a cancelled recording from the beginning. Initial dependency installation uses its existing repair/retry flow. The web GUI also has Cancel transcription.

**Strict quantization** fully snaps note starts and ends and can alter feel and note lengths. It is off by default. Disable it and apply timing to recover the original note timing. No new AI quantizer or Gentle mode is included in this candidate.

Use **Check export requirements** on desktop or **Export requirements** in the browser. MIDI needs no extra software; sheet music needs MuseScore 4+, while WAV/A-B rendering needs FluidSynth and a SoundFont. Browser WAV export downloads its SoundFont on first use if absent; desktop A/B uses your selected local SF2. The native apps provide MIDI/A-B; sheet-music exports remain in the bundled web GUI.

## Platform status

| Platform | Status |
| --- | --- |
| macOS 14+ on Apple Silicon | Beta 4, including the app icon and local web GUI |
| Windows 10/11 x64 | [1.0 Beta 4 — installation and limitations](WINDOWS.md) |
| Intel Mac, Windows ARM, Linux desktop | No packaged release |

Windows Beta 4 includes **experimental AMD GPU acceleration through DirectML**, including a setup path for Radeon RX 6800 XT. After upgrading an existing Windows installation, use **App → Repair Dependencies**. See [AMD setup and validation limits](WINDOWS.md#amd-gpus-directml-experimental).

## One app handles setup

The app bundles its native interface, official engine source, prebuilt adapted web GUI, and license notices. It installs and manages its own Python environment and dependencies in your user folder. You do not need to install Python or Node, run terminal commands, or set up a web server to use the app.

The app provides a self-contained setup and launch workflow. First launch downloads the private runtime and dependencies; the app downloads each model when you choose it and keeps it cached for future use. You supply your own Hugging Face access and accept each model's terms. After setup, cached audio-to-MIDI transcription runs locally without Internet access.

Optional score engraving and audio synthesis have additional upstream requirements, described below. Basic MIDI transcription and opening the bundled web GUI need no separate web setup.

## Install on macOS

1. Download **MuScriptor-Local-1.0-Beta-4-macOS-Apple-Silicon.zip** from the [macOS Beta 4 release](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-beta.mac.4).
2. Unzip it, move **MuScriptor Local.app** into Applications, and open it.
3. Let the app install its private Python environment. First setup requires Internet access.
4. Choose **Small**, **Medium**, or **Large**. Open the selected model’s terms link and accept its conditions with your Hugging Face account.
5. Create a [Hugging Face read token](https://huggingface.co/settings/tokens), paste it into the app, and choose **Connect & Download**. If already connected, choose **Download**.

The app is locally signed, but **not Apple-notarized**. macOS may require approval in **System Settings → Privacy & Security**. Download the app from this repository’s release page.

Each model size needs its own terms acceptance and download. Large needs substantially more memory and disk space than Small. Allow roughly 10 GB for initial setup with Large; retaining multiple models needs additional space. Performance varies with hardware and recording length.

## Transcribe audio on macOS

1. Choose a model. The app remembers your choice and keeps downloaded models cached when you switch.
2. Drop one audio file into the window, or click to choose it.
3. Review the full **MIDI destination**. Use **Change Folder…** to select a different output folder.
4. Optionally search the **Instruments** picker and add one or more groups. Remove a selected item with its × button. Leave the selection empty for unrestricted detection.
5. Optionally enable **Quantize** or **Create A/B audio render**. Both start unchecked.
6. Click **Transcribe**. When it finishes, use **Save MIDI Copy…**, **Reveal in Finder**, or **Convert Another**. If A/B audio was created, its full saved path and a separate Finder button appear.

The default output is `<song>_transcription.mid` beside the audio. Existing files are preserved; duplicates get a numbered name. If a folder becomes unavailable, the app attempts to keep the MIDI in its Results folder and opens a save dialog. Canceling that dialog keeps the recovered result.

Model download progress shows bytes received and the actual cache folder as selectable text. Transcription progress follows the engine’s five-second chunks. Loading and final MIDI writing have an indeterminate indicator. Model switching is disabled while work is in progress. Closing the app stops its worker and cancels the current operation.

WAV, MP3, FLAC, M4A/AAC, and other formats supported by the loader or FFmpeg are accepted. The official engine transcribes the notes. A shared local timing extension writes the tempo map and optional quantization. With Quantize off, MIDI preserves the transcribed note times and the original audio start: tempo settings never stretch playback or prepend silence. Transcription is approximate and may require editing, particularly for dense recordings.

Auto filters detector jitter into a simpler tempo map, retaining sustained tempo changes and gradual movement. Unreliable sections are approximated and disclosed, rather than exported as individual tempo spikes. The grid remains an estimate: check the click preview or use a known manual BPM/beat anchors. Changing the grid does not move notes unless Strict quantization is enabled.

The subsequent [audio-pulse refinement](validation/RHYTHM_REFINEMENT.md) recovers supported tempo changes in all 11 authored reference tests; it does not fix the dense real-recording cases. New audio analysis uses this check, while saved sessions retain their cached beat detections.

Broader [VGM and mixed-meter stress tests](validation/VGM_STRESS_RESULTS.md) found missed tempo changes and half/double-pulse errors in difficult material. The [percussion-evidence refinement](validation/METER_EVIDENCE.md) can suggest changing meters when several repeated bars confirm each section. Dense or ambiguous material still needs explicit meter corrections. A simple-looking tempo map is not proof of a correct grid. Strict quantization can reduce timing accuracy when its grid is wrong.

Supported constant Auto estimates round to the nearest whole BPM only when they are within 0.05 BPM and the projected grid drift across the recording is at most 20 ms. Both limits must pass. These are conservative product defaults, not a claim about the true tempo or a universal audibility threshold. Manual BPM, explicit anchors, uncertain estimates, and changing tempo maps retain their values. Note positions are recalculated to preserve playback timing.

### Tempo, time signature, and optional quantization

**Tempo → Auto** follows detected beats, including changing tempo. **Manual** sets the grid to a known BPM while preserving playback speed and note times. Changing the time signature also preserves speed. In 6/8, 9/8, and 12/8, the default BPM unit is a dotted quarter; Advanced lets you choose another unit. Automatic meter is only a suggestion and does not reliably identify compound meters or meter changes.

**Quantize** is independent and off by default. It snaps individual note starts and ends to the chosen subdivision; this changes their timing but never stretches the recording. Leave it off to preserve the performance. Auto detection may download the Beat This helper once, independently of quantization. If detection fails, the app discloses the placeholder 120 BPM, preserves note timing, and skips quantization until you supply a usable manual grid.

**Advanced** contains beat-unit interpretation, the first downbeat, beat anchors (`seconds, beat number`), and time-signature changes (`bar number, signature`). Two or more anchors define a changing grid without moving unquantized notes. Bar 1 starts at the first downbeat. MIDI hosts vary in support for fractional pickup measures; the export preserves the audio start and marks the first downbeat instead of adding silence.

After transcription, check the click preview and apply timing changes without running the model again. Desktop keeps the latest transcription in memory; the browser server retains up to four sessions. Abrupt beat-tracking changes are flagged for review. Neither a detected grid nor a manual BPM guarantees that every beat was identified correctly.

**Create A/B audio render** puts original audio on the **left** and FluidSynth synthesis on the **right**, with loudness matching. It uses original performance timing even when the separately exported MIDI is quantized. The Hugging Face transcription checkpoints do **not** include FluidSynth or a SoundFont.

For A/B rendering on macOS:

1. Install FluidSynth using Homebrew: `brew install fluidsynth`, then reopen the app. Finder launches also search `/opt/homebrew/bin` and `/usr/local/bin`.
2. Download a local `.sf2` SoundFont, for example [MuScriptor’s MuseScore General asset](https://huggingface.co/MuScriptor/assets/blob/main/MuseScore_General.sf2).
3. Enable **Create A/B audio render**, click **Choose SoundFont…**, and select that file. Rendering uses the selected local file; the app does not automatically download a SoundFont.

The comparison is saved as `<MIDI name>_AB.wav` beside the actual saved MIDI, or in the app’s Results folder if that folder becomes unavailable. Existing audio files are preserved with numbered names. If FluidSynth, the SoundFont, or rendering fails, the completed MIDI remains available and the app shows recovery guidance. **Save MIDI Copy…** copies only the MIDI; the A/B path continues to identify the saved audio.

### Upstream compatibility verified

These macOS controls were checked against the official engine and the released [Small](https://huggingface.co/MuScriptor/muscriptor-small), [Medium](https://huggingface.co/MuScriptor/muscriptor-medium), and [Large](https://huggingface.co/MuScriptor/muscriptor-large) model cards. All three checkpoints use the shared instrument taxonomy. The app obtains picker entries from `MT3_FULL_PLUS_GROUP_NAMES` and passes exact names to the current `TranscriptionModel.transcribe(instruments=...)` API; older model-card examples use an earlier conditioning-string API.

The pinned engine in `upstream-revision.txt` provides the supported APIs used here: [instrument groups](https://github.com/muscriptor/muscriptor/blob/7f213afecf23bd6a1b8672aa223690ee9807cefb/muscriptor/tokenizer/mt3.py), [beat detection, onset measurement, and MIDI export](https://github.com/muscriptor/muscriptor/blob/7f213afecf23bd6a1b8672aa223690ee9807cefb/muscriptor/transcription_model.py), and [A/B auralization](https://github.com/muscriptor/muscriptor/blob/7f213afecf23bd6a1b8672aa223690ee9807cefb/muscriptor/utils/auralization.py). The tracked `patches/upstream-rhythm.patch` adds shared timing export, browser controls, and cached re-export on top of this pinned source. Model inference remains upstream; both interfaces use the same local timing extension. The Windows preview now follows these controls and layout; see [Windows instructions](WINDOWS.md).

## Processing and privacy

The macOS app prefers **Apple MPS** and displays the selected backend. Recognized MPS failures restart the complete song on CPU with a visible notice. Unrelated audio errors do not silently switch processors.

Audio and inference stay on the computer. Setup and updates download software and models from their providers. Hugging Face credentials are stored by its client and sent to Hugging Face for authentication; the app does not include credentials in release downloads or command-line arguments. No hosted inference service or app analytics is used. The optional web GUI runs a server accessible only on this computer. After setup and model download, cached models can transcribe offline. See [PRIVACY.md](PRIVACY.md).

### One-click local web GUI

The browser interface is based on the official MuScriptor frontend, with the local tempo and rhythm extension built from the same pinned source as the bundled engine. Its audio requests go to the app's local backend on this computer. The native app provides installation, model management, and a simpler desktop workflow around those same official tools.

After downloading a model, click **Open Web GUI** in the app. The bundled MuScriptor interface opens in your browser using the same private Python installation, cached model, and selected processor. No terminal commands, Node installation, separate token, or second model download are needed. The app waits until the local server is ready before opening the browser; clicking again reopens the same session.

Keep the desktop app open. **Return to Desktop** stops the web server and any active web transcription, then restores the desktop controls. Only one interface owns the model at a time. Choose transcription options in the interface you are using. Browser-generated files use your browser's download/save location, independently of the desktop MIDI destination.

The bundled web GUI has analytics and remote font loading disabled. Upstream's browser playback may download and cache its SoundFont on first use; tempo detection can download the optional tempo helper. Sheet-music export still requires MuseScore 4+, and server-side audio rendering requires FluidSynth. These optional upstream features are separate from opening the GUI and transcribing to MIDI.

## Files and storage

These are the default locations for the released macOS app:

| Item | Location |
| --- | --- |
| Private engine and Python environment | `~/Library/Application Support/MuScriptor Local/Engine/` |
| Recovered MIDI files | `~/Library/Application Support/MuScriptor Local/Results/` |
| Diagnostic logs | `~/Library/Logs/MuScriptor Local/` |
| Model cache | `~/.cache/huggingface/hub/models--MuScriptor--muscriptor-<size>/` |
| Hugging Face credentials | Hugging Face’s standard user cache |

The model cache stays outside the app bundle. Existing Hugging Face cache environment overrides are respected; the app displays the effective path. The optional upstream tempo helper uses its own Torch cache.

To update, quit the app, replace it with a newer release, and reopen it. The portable app refreshes its local worker automatically. Use **MuScriptor Local → Repair Dependencies…** if dependency setup fails or needs refreshing. **Show Logs** opens the diagnostic folder. Review and redact local paths before posting logs publicly.

To uninstall, quit and trash the app, then remove its private engine folder if no longer needed. Save any recovered MIDI files before deleting Results. Model caches and credentials are shared with other Hugging Face tools; remove only files you recognize and no longer need. MIDI saved elsewhere is unaffected.

## Development

**Use `main` on both Mac and Windows.** Both interfaces and the shared worker live in this branch. The previous `codex/windows-preview` work was merged; do not use it as the starting point for new changes. Release tags preserve published builds, which can have an older UI than current source. Pull `main` before starting on another computer and push a reviewed change before switching machines.


The macOS interface is Swift/AppKit/SwiftUI; the worker is Python. The pinned upstream revision is recorded in `upstream-revision.txt`, and the macOS environment uses `requirements.lock`.

Clone this repository, fetch the official upstream source into `upstream/` at the recorded revision, and set up the dedicated `.venv`. Building an app also requires Node.js 22+ and pnpm 10.20.0 to bundle the pinned official web frontend; installed-app users do not need these tools. `tools/bootstrap.sh` is the installer bundled with release builds; `tools/repair.sh` and `tools/update.sh` maintain an existing development environment.

- `zsh tools/build.sh` builds a local launcher that points at the checkout, in `build/Current Build.noindex/`. Build and packaging copies stay outside Spotlight indexing.
- `zsh tools/share.sh` creates a portable app and zip with no checkout-specific installation path.
- `.venv/bin/python -m unittest discover -s tests -p 'test_wrapper.py' -v` runs the shared worker checks.
- `.venv/bin/python -m unittest discover -s tests -p 'test_mac_options.py' -v` runs focused macOS option checks, including real upstream MIDI conversion and A/B processing with mocked inference/synthesis. Windows UI tests require a compatible Windows Qt environment.
- `.venv/bin/python -m unittest discover -s tests -p 'test_rhythm.py' -v` checks variable tempo, compound meter, independent quantization, cached web export, and MIDI timing preservation. Builds apply the tracked engine patch automatically; use `tools/apply-engine-patches.py` before running directly from a fresh source checkout.
- `validation/validate_controls.py` exercises real model switching and offline Large transcription after the model is cached and the sample audio has been generated.

Generated app bundles and archives belong in GitHub Releases, not source control. See [CONTRIBUTING.md](CONTRIBUTING.md) and [validation/RESULTS.md](validation/RESULTS.md) for validation scope and known limitations.

## Licenses and attribution

The wrapper code is available under the [MIT License](LICENSE). The included official MuScriptor source is separately MIT licensed by **Kyutai x Mirelo**; its notice is retained in [licenses/MuScriptor-MIT.txt](licenses/MuScriptor-MIT.txt).

**The code license does not license the model weights.** Weights are downloaded separately and use **CC BY-NC 4.0 plus the additional conditions on each model page**. Review and accept the applicable terms: [Small](https://huggingface.co/MuScriptor/muscriptor-small), [Medium](https://huggingface.co/MuScriptor/muscriptor-medium), [Large](https://huggingface.co/MuScriptor/muscriptor-large). Use audio for which you have the necessary rights.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for component attribution. The application name does not imply endorsement by the upstream authors.
