# Contributing

Use GitHub issues for reproducible bugs and pull requests for focused changes. Include platform, app version, model size, displayed processor/backend, steps to reproduce, and the observed error. Share an original or freely redistributable short test recording only when needed. Redact local usernames, private paths, tokens, and identifying information from logs.

Keep audio processing in the official engine. Do not add cloud uploads, analytics, model weights, credentials, or personal recordings to the repository or release archives. Preserve upstream notices and separate the code license from the model license.

Use a dedicated Python environment. macOS builds require Apple Silicon, macOS 14+, and Xcode Command Line Tools. The Windows preview has its own build workflow and hardware-validation requirements on `main`. Record what was actually tested; do not describe mocked GPU checks as real hardware validation.

Before a release, run the relevant automated checks, compile the native application, inspect the packaged archive, confirm portable paths and license notices, and test a complete transcription with a permitted model. A release archive must contain no development-machine paths or authentication material. Generated binaries belong in release assets.
