# Release validation

## macOS 1.0 beta

Validated on Apple Silicon with macOS 14+ as the app's deployment target. Other Mac configurations have not been independently validated.

- The native application compiled, was locally signed, and opened successfully.
- All 16 wrapper checks passed for the macOS beta. Coverage includes real audio decoding/cleanup, separate model caches, selected-model loading, download metadata, output previews/custom folders, disk errors, collision-safe saving, and CPU fallback classification.
- The official Large checkpoint's bytes matched the Hub blob hash; see `model-integrity.txt`.
- A real worker-protocol test switched Small → Medium → Large, planned a custom destination, and transcribed a complete original 12-second melody with Large on Apple MPS. It produced 20 MIDI note-on events over three chunks, with zero network attempts and no warnings. The saved path matched the preview. See `model-controls-results.json`.
- Small/Medium routing was tested, but actual transcription with those checkpoints has not been validated.
- A fresh portable environment installed successfully and imported the official engine and bundled FFmpeg.
- The portable archive has no checkout-specific installation path, authentication files, recordings, or model weights.

Local raw logs are not distributed because they may contain machine-specific paths. `make_audio.py` generates the original test melody. `validate_controls.py` reruns the offline integration check after its model and audio prerequisites are available.

## Windows

The Windows implementation lives on the development branch. Its build and unit checks do not substitute for validation on a Windows PC with the intended GPU. See that branch's Windows documentation for the current test scope.
