# Continuing development on Windows

## Shared source of truth

Use **`main`** for both Windows and macOS. The old `codex/windows-preview` work is merged, including its physical-PC setup fixes. Current source also includes the newer compact interface, instrument picker, notation quantization, and A/B audio options. Published release installers remain snapshots of their release tags and may show the earlier interface until a new release is built.

For a new chat on another computer:

> Clone https://github.com/PokestirVGM/MuScriptor-Local if needed, fetch origin, and start from the latest main. Inspect and preserve any local uncommitted work before switching or pulling. Read README.md, WINDOWS.md, and the latest Windows build workflow. Keep the current compact UI and transcription options; do not restore the older two-column Windows interface. Test the new controls on this PC, retain the Windows setup/runtime fixes, and publish a new Windows beta only after validation. Keep existing macOS releases available and do not commit credentials, recordings, personal paths, or raw local logs.

## What is already integrated

- The Windows 1.0 beta's fixes for private Python on Windows RedirectionGuard, paths containing spaces, PowerShell quoting, and dependency-repair retries.
- Local CUDA/CPU selection, actual processor reporting, collision-safe output, and first-run private engine installation.
- The latest Mac and Windows UI: instrument filtering, optional notation MIDI, optional A/B render, and matching compact layout.
- Default transcription does not fetch an uncached optional tempo helper. Enabling notation quantization explicitly may fetch it; failure preserves performance timing with a warning.
- The Inno Setup installer, portable package, third-party notices, and Windows build checks now run from main and pull requests targeting main.

## Validate before the next Windows release

Use WINDOWS.md for build/setup instructions and validation/WINDOWS_RESULTS.md for the scope of the earlier physical-PC checks. Those older results do not prove the newly added options have been tested on Windows hardware.

Check installation/upgrade, actual CUDA device use, the current UI at Windows display scaling, instrument filtering, quantization, FluidSynth/SoundFont A/B rendering, custom output paths, collisions, and offline startup. Confirm failed optional rendering preserves the MIDI. Review the release archive for credentials and local paths. If publishing, update validation notes and use a new Windows tag so existing release tags remain intact.

Before changing computers, commit and push the current work. On the other computer, fetch and update main; preserve uncommitted edits before doing so. Do not reset or force-push shared branches to an older local checkout.
