# Final 1.0 readiness pass — build 12

2026-09-21 · Apple Silicon host · unpublished 1.0 RC1

**Verdict:** suitable for final acceptance testing, not yet signed off for public stable 1.0. Local regression, browser behavior, and packaging checks pass. Physical Windows/DAW acceptance, a complete native build-12 workflow walkthrough, and distribution signing remain open. Auto remains an estimate with the documented complex-music limitations.

## Issues fixed in this pass

- Returning from the web GUI could leave desktop controls attached to a session no longer present in the restarted engine. Mac and Windows now restore the latest saved recovery session reported by the new worker. Stale desktop timing does not overwrite newer web edits. Unsaved timing is checked before handing desktop work to the browser.
- Engine restart, cancellation, and dependency repair now restore the saved session when available and retain pending desktop timing separately. A failed restore does not falsely leave session editing enabled. Old Windows worker messages cannot be consumed by its replacement.
- Selecting an undownloaded model no longer hides timing/export controls for an already loaded session. Opening a session does not falsely mark that model as downloaded.
- Empty, non-finite, corrupt, and truncated audio is rejected before inference on desktop and both transcription HTTP routes. Valid PCM stereo and floating-point WAV remain supported. Bad HTTP uploads return a client error and do not occupy model work.
- The Mac share script depended on an ignored generated Read Me absent from the source archive. It now ships tracked `MACOS.md`, uses the RC1 archive name, and successfully packages through the normal share command. Generated `.noindex` app staging is now excluded from source handoffs. Windows instructions now describe the current gear menu and distinguish historical Beta hardware checks from current acceptance.

## Evidence

| Check | Result |
|---|---|
| Complete Python regression suite | 160 tests successful; two optional skips, 158 executed |
| Browser state regression suite | 18 passed |
| Windows Qt UI at 200% scaling | 33 passed, light/dark preview images generated |
| Installed engine dependency consistency | 57 packages checked; compatible |
| TypeScript and production frontend | Passed; existing bundle-size advisory remains |
| Native Swift build | Passed, build 12 |
| Mac release/share command | Passed with source-controlled instructions |
| Clean pinned-upstream patch application | Passed during packaging |
| Archive integrity, source inventory, manifest hashes | Verified during packaging |

Actual browser checks used a separate local server and synthetic MIDI-only session, never the user's recovery file. Verified gear recovery, 170 BPM/7/8 → 120 dotted-quarter BPM/6/8, disabled download while timing is dirty, Apply restoring export, original-timing disclosure, MIDI-only export options, correct disabling of original-audio mix and unavailable sheet export, and recovery after browser reload. No browser console warnings/errors were observed. The test server and tab were closed afterward.

The previously running build 8 was quit with the owner's approval. Build 12 was installed, its signature and bundled engine hashes verified, then launched from `~/Applications/MuScriptor Local.app`. The native information panel confirms build 12. The development engine initially waited for macOS Documents-folder permission. After that system request was resolved, startup completed: Large is Downloaded, Automatic selects Apple MPS on Apple M5 Pro with 64 GB unified memory, the instrument list is populated, and session/processor/export menus are enabled. The app was left ready at its start screen. This verifies startup and settings, not a new full transcription workflow.

At the owner's request, 20 older MuScriptor app bundles (builds 3–11, including old UI previews) were unregistered and moved to a dated folder in Trash, with a restore-location manifest. The installed build 12 and current `.noindex` packaging artifacts remain. Model caches, recordings, results, and the user's recovery session were preserved. LaunchServices was refreshed. A host-level Spotlight query for the exact bundle ID returns only `~/Applications/MuScriptor Local.app`, with the expected MuScriptor Local display name.

Logs are under `build/final-readiness-*.log`; offscreen images are in `build/final-readiness-previews`. Tests exercise controlled inference/render boundaries unless stated otherwise. No fresh model transcription, real FluidSynth/MuseScore render, Windows hardware run, or DAW import is claimed in this pass.

## Rhythm accuracy carried forward

The [build 11 evidence report](METER_EVIDENCE.md) remains the current accuracy record: 8/8 development groove cases, 6/6 additional actual-model cases, and all 11 original authored controls pass. Seven real recordings preserve all 34,096 note starts/releases within 0.036 ms. Dense DEZOLVE-style grids remain unresolved. That record demonstrates specific tested improvements and timing preservation, not universal automatic meter accuracy. This pass changed audio validation and session lifecycle, not the rhythm algorithm.

## Owner acceptance before publication

1. With build 12 startup verified, exercise a normal transcription, Finish here, recovery after restart, session save/open, and desktop ↔ web return with the new build. Save/apply web changes before returning.
2. Complete [WINDOWS_HANDOFF.md](../WINDOWS_HANDOFF.md) on the intended PC: installation/upgrade, CPU/GPU, failure/retry, model switching, session interoperability, scaling, and DAW import with the MIDI tempo map. The source handoff contains matching shared-engine and desktop fixes; no Windows binary was produced or certified on this Mac.
3. Verify real optional exports with the target MuseScore/FluidSynth/SoundFont versions, and inspect audio/MIDI alignment in the intended DAW. Missing tools are correctly disclosed but that does not establish renderer or host compatibility.
4. Apply owner-controlled signing/notarization and test the actual downloaded package on a clean machine. Approve the documented Auto limitations and published feature claims, then explicitly authorize publication. Existing Beta releases remain untouched.

The candidate stays `1.0.0-rc.1`; no release was published, tag created, or stable-1.0 claim added.
