# MuScriptor Local reliability audit

Audited on October 2, 2026. This review covers the Windows Qt interface, macOS interface, shared worker, engine updates, browser interface, audio loading, sessions, cancellation, MIDI publication, and current model choices. Concrete defects were fixed in source and covered by regression checks. The existing published RC1 installers have not been replaced.

## Fixes made

| Area | Finding and resulting behavior |
| --- | --- |
| Windows file drops | Scroll viewports and editable controls could consume a file before the main window received it. Scoped event filters now route file drops across those controls. Text drags retain their normal behavior. |
| Drop feedback | Accepted drags explicitly use the copy action and repaint feedback; rejected or completed drops clear the highlight. The source file stays in place. |
| Invalid file selection | Directories, missing files, remote URLs, and multiple native file drops are rejected. Selecting an invalid file preserves the current session before any discard prompt. macOS also rechecks its state after asynchronous file delivery. |
| Dropped projects | A `.muscriptor` file opens as a session on Windows, macOS, and web, instead of being submitted as audio. Browser drops reject empty files and multiple files before replacing a transcription. |
| Browser drag state | Nested drags, empty transfer types on leaving the page, cancelled drags, and listener cleanup are handled without intercepting text or link drags. |
| Windows export storage | Publication uses Windows rename, which fails on existing destinations, instead of hard links. FAT/exFAT and other filesystems without hard links can use the selected output folder. Numbered duplicates remain protected. |
| Export filenames | Long UTF-8 stems are bounded without splitting characters. Windows reserved names, invalid characters, and trailing spaces are handled, including names imported from another platform. |
| Browser audio formats | Content-based FFmpeg fallback decodes M4A/AAC and other unsupported libsndfile formats for both transcription endpoints and shared audio loading. Temporary inputs and output are cleaned up; decoder time is bounded. |
| Local server responsiveness | Decoding runs outside the HTTP event loop, so health, cancellation, and other requests remain responsive while decoding proceeds. |
| Inference ownership | Model initialization failures release the transcription lock. Stream cleanup releases it even if closing the generator raises. Lock acquisition uses nonblocking polling, preventing an abandoned background acquisition after HTTP cancellation. |
| Portable session validation | Invalid audio field types, unsupported embedded audio filenames, and non-object timing settings are rejected. Model note tails extending past the audio are preserved; real-model checks demonstrated why this is necessary. |
| Invalid session requests | Invalid session identifiers return a client error instead of an unhandled server error. A null re-export timing value uses default settings. |
| Failed model loads | A model becomes reusable only after decoder placement succeeds. Retrying a placement failure actually reloads it. |
| Desktop retry | Failed timing export, preview, session save, and session open retry the corresponding operation. Saved-session editing still works when the selected model is not downloaded. |
| Windows dependency repair | Repair stops the worker and its process tree and waits for completion before installation. A timeout leaves the current session available. |
| Installer lifecycle | A failed installer start clears its process reference, and an obsolete installer completion cannot restart or replace the current engine. |
| Concurrent engine updates | An operating-system file lock protects the refresh transaction. A second startup cannot delete or recover another process's in-progress update. Existing rollback behavior remains tested. |
| Browser streaming | The event parser handles CRLF split across chunks, optional spacing after `data:`, and multiple data fields. Closing the iterator cancels its reader and releases the stream. |
| Browser retry cleanup | Completed busy-retry waits remove their abort listeners. Example-track download failures show a useful message instead of an unhandled rejection. |
| Local server privacy | Cross-site fetch metadata is rejected even when an Origin header is absent, protecting recovery reads as well as work submission. Host and Origin restrictions remain in place. |
| Worker requests and errors | Non-object requests cannot crash the worker's cleanup. HTTP errors without a response cannot crash error reporting. Windows workers use UTF-8 mode. |
| Frontend build | The explicit offline build option runs the installed TypeScript/Vite tools directly, avoiding package-manager version or dependency downloads during a build. |
| Model choice guidance | Desktop captions now explain CPU suitability, speed/accuracy tradeoffs, and Large's preference for a GPU. Existing saved choices and the Large default remain. |

Engine and browser edits are included in `patches/upstream-rhythm.patch`. Its reverse application check passes, so the ignored engine checkout is not the only copy of these changes.

## Verification performed

- The engine, session, rhythm, DirectML adapter, audio-validation, and local HTTP suite ran 136 tests: 135 passed and one platform-specific test was skipped.
- The Qt interface suite ran 41 tests: 40 passed and the optional screenshot test was skipped. The same screenshot test passed separately and rendered ready, options, completion, setup, download, and settings views in both light and dark themes; sampled previews were visually inspected. Real Qt drag events reached scroll viewports, the drop button, and timing fields. This is Qt testing on macOS, not Explorer or Windows hardware acceptance.
- Browser state and file-drop tests passed all 25 checks. They cover playback races, stale exports, recovery freshness, streaming, cancellation, nested drags, rejected drops, and cleanup.
- TypeScript checking and the production frontend build passed; the bundled GUI and third-party notices were rebuilt. Vite still reports a large application bundle, discussed below.
- The final Swift source compiled for Apple Silicon and macOS 14, and the local development app bundle was rebuilt and ad-hoc signed. Installed Python dependency compatibility passed.
- Real loopback-server startup, readiness, responsiveness, shutdown, and socket release passed outside the sandbox. The sandbox itself blocks loopback listening and Qt CPU-feature detection, so those checks required execution outside it.
- Both cached Small and Large checkpoints completed the authored 12-second melody entirely offline, saved recovery and portable sessions, reopened with the model released, and re-exported at a different tempo and meter. All MIDI note events and their times were preserved within 2 ms. No CPU fallback warnings or network attempts occurred.

| Real model check | Small | Large |
| --- | --- | --- |
| Processor | Apple MPS | Apple MPS |
| Note attacks produced | 49 | 20 |
| Authored note attacks | 20 | 20 |
| Pitch sequence matched the authored melody | No | Yes |
| Mean absolute onset error for the matched sequence | Not compared because note counts differ | 13.70 ms |
| Elapsed time including loading and session checks | 12.42 seconds | 24.63 seconds |
| Offline session round trip | Passed | Passed |

This simple melody is a functional smoke test, not a broad transcription benchmark. The runtime comparison includes model loading and does not establish general inference speed. Raw logs and generated artifacts are under `build/audit-*` and `build/validation/audit-model/`; the reusable real-model check is `validation/validate_audit.py`.

## Current model research

The [official model catalog](https://huggingface.co/MuScriptor/models) still lists Small, Medium, and Large, alongside the asset repository. No newer official replacement checkpoint was established by this review. The [official engine guidance](https://github.com/muscriptor/muscriptor#models) recommends Small for CPU use, Medium for a speed/accuracy balance, and Large for accuracy with a GPU. The [Large model card](https://huggingface.co/MuScriptor/muscriptor-large) describes the same shared architecture and instrument taxonomy.

Recommendation: retain the official models and Large as the quality default. Recommend Small when CPU speed or memory is the limiting factor, and Medium for a balance. The authored melody check supports keeping Large for quality, but does not settle dense, real-world performance.

The [community Medium ONNX conversion](https://huggingface.co/happyme531/muscriptor-medium-onnx) is a possible deployment experiment, not evidence of a newer or more accurate official model. It requires a different inference adapter and hardware/output comparisons before becoming an app option. [Spotify Basic Pitch](https://github.com/spotify/basic-pitch) is lightweight and includes pitch bends, but its maintainers say it works best on one instrument at a time. It would be a separate single-instrument workflow, not an automatic replacement for this app's multi-instrument engine.

## Checks still needed before a stable release

1. **Actual Windows acceptance:** build fresh installer and portable artifacts, then test Explorer drops over the whole window, filenames with spaces and Unicode, UNC paths, local OneDrive files, cloud placeholders, and normal versus elevated launch. Test MIDI/A-B export on actual NTFS and FAT/exFAT media, including full disks and disconnected drives. Current rename coverage simulates Windows semantics on this Mac.
2. **CUDA and DirectML hardware:** run current source on NVIDIA and AMD PCs with all model sizes, GPU memory pressure, CPU fallback, repeated cancellation, browser handoff, and repair. Adapter tests are controlled CPU/meta checks; AMD remains experimental.
3. **Windows display and accessibility:** run the existing 150% and 200% CI checks on Windows, inspect native dialogs and multiple-monitor changes, and try keyboard-only use plus a screen reader. The Mac Qt preview cannot certify Windows fonts or Explorer behavior.
4. **Dense music and rhythm accuracy:** existing VGM and mixed-meter stress records retain missed changes and half/double pulse errors. Validate with held-out recordings; use manual grids when detection is unreliable. Strict quantization can reduce timing accuracy with an incorrect grid. None of these launcher fixes makes transcription exact.
5. **First launch and update acceptance:** test clean user accounts, offline/failed downloads, disk exhaustion, interrupted installation, restrictive permissions, and multiple simultaneous launches. Windows repair/bootstrap operations and setup termination on macOS need real installed-app acceptance beyond transaction tests.
6. **Export tools:** complete actual MuseScore and FluidSynth checks on both platforms. Automated responsiveness and cleanup checks use controlled renderers. Browser-native audio decoding can differ from the engine's FFmpeg support, so some otherwise transcribable files may have MIDI-only preview.
7. **Distribution trust:** Windows signing and macOS notarization remain unfinished. They require publisher credentials and a release process; they were not replaced with claims of certification in this audit.
8. **Frontend startup size:** the production application script is about 724 kB before compression. Consider loading synthesis and optional export UI on demand, measuring launch time before changing playback initialization. This is a performance opportunity, not a demonstrated correctness failure.

No remote release was published, no system dependencies were installed, and no model weights or credentials were added to the repository.
