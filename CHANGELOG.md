# Changelog

## Unreleased — Windows AMD GPU support

- Add experimental DirectML setup for AMD graphics, including the RX 6800 XT; existing installations use Repair Dependencies in an updated app build.
- Run the decoder on the GPU while keeping complex audio conditioning on CPU, without modifying the official model or vendored source.
- List DirectML adapters in the processor picker, prefer recognizable discrete adapters, and report GPU failures before retrying desktop transcription on CPU.
- Add adapter and UI regression checks, Windows dependency-install checks, and an opt-in hardware validation script. Physical AMD GPU transcription and speed are not yet validated.

## 1.0 Beta 3 for macOS — 2026-09-20

- Add one-click access to the bundled official web GUI using the desktop's local installation, selected model, and processor; Return to Desktop stops the web session.
- Add instrument filtering, optional notation quantization, and optional A/B audio rendering to the macOS release.
- Bundle frontend license notices, disable web analytics and remote font loading, and restrict the web server to this computer.
- Refresh the installed worker and web assets when upgrading; exclude build caches and stale files from release packages.
- Keep Windows releases separate and preserve earlier macOS downloads.

## 1.0 Beta for Windows — 2026-09-20

- Add a per-user Windows x64 setup installer and portable ZIP, with a redesigned MuScriptor Local desktop interface.
- Display actual processor names and support Automatic, NVIDIA CUDA, and CPU selection.
- Fix first-run setup in folders containing spaces, private Python version links, and incomplete-setup retries.
- Keep optional tempo checkpoint downloads out of transcription so cached operation remains local and offline.
- Validate Large on a physical RTX 5070 Ti and offline CPU, including complete MIDI output, Unicode destinations, and collision protection. Document untested configurations explicitly.
- Preserve the existing macOS release at v1.0.0-beta.2.

## 1.0 Beta 2 — 2026-09-20

- Publish installation-neutral documentation, privacy information, contribution guidance, and explicit wrapper/upstream license notices.
- Include license notices in the macOS download and remove Finder metadata from release archives.
- Keep generated app bundles, archives, and local Finder metadata out of source control.
- Document the Windows development preview separately from the macOS release.

## 1.0 Beta 1 — 2026-09-20

- Add remembered Small, Medium, and Large model selection.
- Show the actual model download folder and byte-based progress.
- Preview the MIDI destination before transcription and allow a custom output folder.
- Preserve existing output files and recover results when a destination becomes unavailable.
- Improve engine retry behavior and portable worker updates.
