# Historical beta validation

Current candidate records: [macOS RC1](MACOS_RC1_RELEASE.md) and [Windows RC1](WINDOWS_RC1_PC.md).

## macOS 1.0 beta

Validated on Apple Silicon with macOS 14+ as the app's deployment target. Other Mac configurations have not been independently validated.

- The native application compiled, was locally signed, and opened successfully.
- All 16 wrapper checks passed for the macOS beta. Coverage includes real audio decoding/cleanup, separate model caches, selected-model loading, download metadata, output previews/custom folders, disk errors, collision-safe saving, and CPU fallback classification.
- The official Large checkpoint's 5,465,642,136 bytes matched the Hub blob SHA-256: `ac4eb6ea87dfc26b6ca6b954c6b967ab87ad4c7d08e078b25214f13ed051f397`.
- A real worker-protocol test switched Small → Medium → Large, planned a custom destination, and transcribed a complete original 12-second melody with Large on Apple MPS. It produced 20 MIDI note-on events over three chunks, with zero network attempts and no warnings. The saved path matched the preview; the MIDI duration was 11.2298895 seconds.
- Small/Medium routing was tested, but actual transcription with those checkpoints has not been validated.
- A fresh portable environment installed successfully and imported the official engine and bundled FFmpeg.
- The portable archive has no checkout-specific installation path, authentication files, recordings, or model weights.

Local raw logs are not distributed because they may contain machine-specific paths. `make_audio.py` generates the original test melody. `validate_controls.py` reruns the offline integration check after its model and audio prerequisites are available. Generated JSON reports from this check and `validate_offline.py` are saved under ignored `build/validation/`.

## Windows

Both platform implementations now live on `main`. See [Windows RC1 PC validation](WINDOWS_RC1_PC.md) for actual hardware coverage and remaining limits; the early Mac beta results above do not establish Windows compatibility.
