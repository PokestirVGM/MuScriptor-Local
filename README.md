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

## Transcribe audio

1. Choose a model. The app remembers your choice and keeps downloaded models cached when you switch.
2. Drop one audio file into the window, or click to choose it.
3. Review the full **MIDI destination**. Use **Change Folder…** to select a different output folder.
4. Click **Transcribe**. When it finishes, use **Save MIDI Copy…**, **Reveal in Finder**, or **Convert Another**.

The default output is `<song>_transcription.mid` beside the audio. Existing files are preserved; duplicates get a numbered name. If a folder becomes unavailable, the app attempts to keep the MIDI in its Results folder and opens a save dialog. Canceling that dialog keeps the recovered result.

Model download progress shows bytes received and the actual cache folder as selectable text. Transcription progress follows the engine’s five-second chunks. Loading and final MIDI writing have an indeterminate indicator. Model switching is disabled while work is in progress. Closing the app stops its worker and cancels the current operation.

WAV, MP3, FLAC, M4A/AAC, and other formats supported by the loader or FFmpeg are accepted. The official engine performs resampling and MIDI generation; the wrapper does not invent or edit notes. MIDI is produced without quantization. Transcription is approximate and may require editing, particularly for dense recordings.

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
- `.venv/bin/python -m unittest discover -s tests -v` runs the wrapper checks.
- `validation/validate_controls.py` exercises real model switching and offline Large transcription after the model is cached and the sample audio has been generated.

Generated app bundles and archives belong in GitHub Releases, not source control. See [CONTRIBUTING.md](CONTRIBUTING.md) and [validation/RESULTS.md](validation/RESULTS.md) for validation scope and known limitations.

## Licenses and attribution

The wrapper code is available under the [MIT License](LICENSE). The included official MuScriptor source is separately MIT licensed by **Kyutai x Mirelo**; its notice is retained in [licenses/MuScriptor-MIT.txt](licenses/MuScriptor-MIT.txt).

**The code license does not license the model weights.** Weights are downloaded separately and use **CC BY-NC 4.0 plus the additional conditions on each model page**. Review and accept the applicable terms: [Small](https://huggingface.co/MuScriptor/muscriptor-small), [Medium](https://huggingface.co/MuScriptor/muscriptor-medium), [Large](https://huggingface.co/MuScriptor/muscriptor-large). Use audio for which you have the necessary rights.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for component attribution. The application name does not imply endorsement by the upstream authors.
