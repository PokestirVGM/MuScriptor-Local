# MuScriptor Local

A desktop app for turning audio into MIDI with the official [MuScriptor](https://github.com/muscriptor/muscriptor) engine. Transcription runs locally on your computer. This is an independent community wrapper, not an official Kyutai or Mirelo application.

**[Download the macOS beta](https://github.com/PokestirVGM/MuScriptor-Local/releases)** · [Report an issue](https://github.com/PokestirVGM/MuScriptor-Local/issues) · [Changelog](CHANGELOG.md)

## Platform status

| Platform | Status |
| --- | --- |
| macOS 14+ on Apple Silicon | Public 1.0 beta |
| Windows 10/11 x64 | [Development preview](https://github.com/PokestirVGM/MuScriptor-Local/tree/codex/windows-preview); hardware validation pending |
| Intel Mac, Windows ARM, Linux desktop | No packaged release |

## Install on macOS

1. Download **MuScriptor Local - Apple Silicon.zip** from [Releases](https://github.com/PokestirVGM/MuScriptor-Local/releases).
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
5. Optionally enable **Quantize MIDI for notation** or **Create A/B audio render**. Both start unchecked.
6. Click **Transcribe**. When it finishes, use **Save MIDI Copy…**, **Reveal in Finder**, or **Convert Another**. If A/B audio was created, its full saved path and a separate Finder button appear.

The default output is `<song>_transcription.mid` beside the audio. Existing files are preserved; duplicates get a numbered name. If a folder becomes unavailable, the app attempts to keep the MIDI in its Results folder and opens a save dialog. Canceling that dialog keeps the recovered result.

Model download progress shows bytes received and the actual cache folder as selectable text. Transcription progress follows the engine’s five-second chunks. Loading and final MIDI writing have an indeterminate indicator. Model switching is disabled while work is in progress. Closing the app stops its worker and cancels the current operation.

WAV, MP3, FLAC, M4A/AAC, and other formats supported by the loader or FFmpeg are accepted. The official engine performs resampling and MIDI generation; the wrapper does not invent or edit notes. MIDI retains performance timing by default. Both timing modes use upstream onset-delay correction when the engine finds enough beat/onset evidence. Transcription is approximate and may require editing, particularly for dense recordings.

### Optional notation MIDI and A/B audio

**Quantize MIDI for notation** uses MuScriptor’s beat-grid quantization. It works best with a steady tempo. If the engine cannot find a usable beat subdivision, the app saves performance-timing MIDI and shows a warning. The upstream tempo helper may need an initial download; once cached it runs locally. The wrapper does not invent a replacement grid or correction when upstream cannot measure one.

**Create A/B audio render** uses upstream post-processing: original audio on the **left** and FluidSynth synthesis on the **right**, with upstream alignment and loudness matching. It uses onset-corrected performance timing for listening, including when the exported MIDI is quantized for notation. The Hugging Face transcription checkpoints do **not** include FluidSynth or a SoundFont.

For A/B rendering on macOS:

1. Install FluidSynth using Homebrew: `brew install fluidsynth`, then reopen the app. Finder launches also search `/opt/homebrew/bin` and `/usr/local/bin`.
2. Download a local `.sf2` SoundFont, for example [MuScriptor’s MuseScore General asset](https://huggingface.co/MuScriptor/assets/blob/main/MuseScore_General.sf2).
3. Enable **Create A/B audio render**, click **Choose SoundFont…**, and select that file. Rendering uses the selected local file; the app does not automatically download a SoundFont.

The comparison is saved as `<MIDI name>_AB.wav` beside the actual saved MIDI, or in the app’s Results folder if that folder becomes unavailable. Existing audio files are preserved with numbered names. If FluidSynth, the SoundFont, or rendering fails, the completed MIDI remains available and the app shows recovery guidance. **Save MIDI Copy…** copies only the MIDI; the A/B path continues to identify the saved audio.

### Upstream compatibility verified

These macOS controls were checked against the official engine and the released [Small](https://huggingface.co/MuScriptor/muscriptor-small), [Medium](https://huggingface.co/MuScriptor/muscriptor-medium), and [Large](https://huggingface.co/MuScriptor/muscriptor-large) model cards. All three checkpoints use the shared instrument taxonomy. The app obtains picker entries from `MT3_FULL_PLUS_GROUP_NAMES` and passes exact names to the current `TranscriptionModel.transcribe(instruments=...)` API; older model-card examples use an earlier conditioning-string API.

The pinned engine in `upstream-revision.txt` provides the supported APIs used here: [instrument groups](https://github.com/muscriptor/muscriptor/blob/7f213afecf23bd6a1b8672aa223690ee9807cefb/muscriptor/tokenizer/mt3.py), [beat detection, onset measurement, and MIDI export](https://github.com/muscriptor/muscriptor/blob/7f213afecf23bd6a1b8672aa223690ee9807cefb/muscriptor/transcription_model.py), and [A/B auralization](https://github.com/muscriptor/muscriptor/blob/7f213afecf23bd6a1b8672aa223690ee9807cefb/muscriptor/utils/auralization.py). Quantization and A/B rendering are engine post-processing of model events, not alternative inference implementations. The Windows preview now follows these controls and layout; see [Windows instructions](WINDOWS.md).

## Processing and privacy

The macOS app prefers **Apple MPS** and displays the selected backend. Recognized MPS failures restart the complete song on CPU with a visible notice. Unrelated audio errors do not silently switch processors.

Audio and inference stay on the computer. Setup and updates download software and models from their providers. Hugging Face credentials are stored by its client and sent to Hugging Face for authentication; the app does not include credentials in release downloads or command-line arguments. No hosted inference service, local web server, or app analytics is used. After setup and model download, cached models can transcribe offline. See [PRIVACY.md](PRIVACY.md).

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

The macOS interface is Swift/AppKit/SwiftUI; the worker is Python. The pinned upstream revision is recorded in `upstream-revision.txt`, and the macOS environment uses `requirements.lock`.

Clone this repository, fetch the official upstream source into `upstream/` at the recorded revision, and set up the dedicated `.venv`. `tools/bootstrap.sh` is the installer bundled with release builds; `tools/repair.sh` and `tools/update.sh` maintain an existing development environment.

- `zsh tools/build.sh` builds a local launcher that points at the checkout.
- `zsh tools/share.sh` creates a portable app and zip with no checkout-specific installation path.
- `.venv/bin/python -m unittest discover -s tests -p 'test_wrapper.py' -v` runs the shared worker checks.
- `.venv/bin/python -m unittest discover -s tests -p 'test_mac_options.py' -v` runs focused macOS option checks, including real upstream MIDI conversion and A/B processing with mocked inference/synthesis. Windows UI tests require a compatible Windows Qt environment.
- `validation/validate_controls.py` exercises real model switching and offline Large transcription after the model is cached and the sample audio has been generated.

Generated app bundles and archives belong in GitHub Releases, not source control. See [CONTRIBUTING.md](CONTRIBUTING.md) and [validation/RESULTS.md](validation/RESULTS.md) for validation scope and known limitations.

## Licenses and attribution

The wrapper code is available under the [MIT License](LICENSE). The included official MuScriptor source is separately MIT licensed by **Kyutai x Mirelo**; its notice is retained in [licenses/MuScriptor-MIT.txt](licenses/MuScriptor-MIT.txt).

**The code license does not license the model weights.** Weights are downloaded separately and use **CC BY-NC 4.0 plus the additional conditions on each model page**. Review and accept the applicable terms: [Small](https://huggingface.co/MuScriptor/muscriptor-small), [Medium](https://huggingface.co/MuScriptor/muscriptor-medium), [Large](https://huggingface.co/MuScriptor/muscriptor-large). Use audio for which you have the necessary rights.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for component attribution. The application name does not imply endorsement by the upstream authors.
