# Continuing development on Windows

## Shared source of truth

Use **`main`** for both Windows and macOS. The old `codex/windows-preview` work is merged, including its physical-PC setup fixes. Current source also includes the newer compact interface, instrument picker, notation quantization, and A/B audio options. Published release installers remain snapshots of their release tags and may show the earlier interface until a new release is built.

For a new chat on another computer:

> Clone or update https://github.com/PokestirVGM/MuScriptor-Local to the latest main, preserving local changes. Read WINDOWS_HANDOFF.md. Build and test the final Windows installer with the current UI, automatic local setup, model downloads, and one-click official web GUI. Let me install and try it, then ask for my explicit approval before publishing a new Windows 1.0 beta. Preserve macOS Beta 3 and push all source changes.

## What is already integrated

- The Windows 1.0 beta's fixes for private Python on Windows RedirectionGuard, paths containing spaces, PowerShell quoting, and dependency-repair retries.
- Local CUDA/CPU selection, actual processor reporting, collision-safe output, and first-run private engine installation.
- The latest Mac and Windows UI: instrument filtering, optional notation MIDI, optional A/B render, and matching compact layout.
- **Open Web GUI** launches the bundled official interface with the same cached model and processor. Verify browser launch, model/device reuse, Return to Desktop, and server cleanup when quitting. Browser exports use browser download settings.
- Default transcription does not fetch an uncached optional tempo helper. Enabling notation quantization explicitly may fetch it; failure preserves performance timing with a warning.
- The Inno Setup installer, portable package, third-party notices, and Windows build checks now run from main and pull requests targeting main.

## Validate before the next Windows release

Use WINDOWS.md for build/setup instructions and validation/WINDOWS_RESULTS.md for the scope of the earlier physical-PC checks. Those older results do not prove the newly added options have been tested on Windows hardware.

Check installation/upgrade, actual CUDA device use, the current UI at Windows display scaling, instrument filtering, quantization, FluidSynth/SoundFont A/B rendering, custom output paths, collisions, and offline startup. Confirm failed optional rendering preserves the MIDI. Review the release archive for credentials and local paths. Give the user the built installer to run, then wait for their feedback and ask for explicit approval to publish. Passing automated tests does not authorize publication. After approval, update validation notes and use a new Windows tag so existing release tags remain intact.

Before changing computers, commit and push the current work. On the other computer, fetch and update main; preserve uncommitted edits before doing so. Do not reset or force-push shared branches to an older local checkout.
