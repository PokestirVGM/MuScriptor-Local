# Third-party notices

## Wrapper

MuScriptor Local's own source code is licensed under the MIT License in `LICENSE`. This license applies to the wrapper, not to third-party software or model weights. This community application is not an official Kyutai or Mirelo product.

## Official MuScriptor engine

- Source: https://github.com/muscriptor/muscriptor
- Copyright: 2026 Kyutai x Mirelo
- License: MIT; full text in `licenses/MuScriptor-MIT.txt`.
- The bundled source revision is recorded in `upstream-revision.txt`.

The release includes the upstream license beside its source. It uses the official transcription and MIDI-generation APIs.

## Model weights

Model weights are not included in the app or source archive. They are downloaded from the model owner's Hugging Face repositories after the user obtains access:

- https://huggingface.co/MuScriptor/muscriptor-small
- https://huggingface.co/MuScriptor/muscriptor-medium
- https://huggingface.co/MuScriptor/muscriptor-large

The model pages specify CC BY-NC 4.0 and additional conditions of use. Those conditions are independent of the wrapper's MIT license and include requirements concerning rights in input audio and permitted use. Consult the model owner's current terms directly; this file does not replace them or grant additional permissions.

## Runtime dependencies

Python, PyTorch, Hugging Face Hub, FFmpeg/imageio-ffmpeg, SoundFile/libsndfile, beat-this, and other engine dependencies retain their own licenses. The macOS release downloads these into a private environment during setup rather than bundling the installed runtime or its packages. Package metadata and license files remain in that environment. The recorded dependency list is `requirements.lock`.

Windows preview builds additionally use PySide6/Qt and PyInstaller. Their license notices must accompany the packaged executable. The preview uses a directory bundle with separate Qt libraries; consult the included third-party license files and the upstream Qt licensing information at https://www.qt.io/licensing/. The Windows source and build instructions are available on `main`.
