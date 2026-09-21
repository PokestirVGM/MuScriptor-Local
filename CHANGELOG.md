# Changelog

## 1.0 Release Candidate 1 — unreleased

- Restore desktop session state after web handoff or engine restart, retain unapplied timing, ignore obsolete worker messages, and keep saved-session editing available without the selected model. Reject invalid/empty audio before inference on all frontends. Make the Mac release instructions part of the source handoff and refresh Windows documentation.

- Improve Auto swing/compound/odd-meter interpretation using guarded percussion accents and subdivisions. Suggest changing meters only with repeated evidence, preserve grouped clicks and session metadata, and retain manual overrides. Eight development cases and six additional actual-model cases pass; dense real-recording limitations remain.

- Preserve overlapping notes, controller timing/order, and long-recording timing through MIDI tempo serialization. Include release times in Auto subdivision, prevent one-tick Strict artifacts, disclose merged attacks, and update click units across meter changes. Add deterministic rhythm edge tests and a held-out audio stress report that retains complex-rhythm detection failures.

- Fix browser WAV export for sessions without source audio; synth-only WAV follows the selected MIDI while A/B keeps original performance timing. Ignore obsolete WAV/sheet render results after timing or session changes, and keep the local server responsive during audio rendering.
- Recover the newest disk/browser session using shared save timestamps, retire obsolete browser fallbacks after successful disk saves, and correct the sheet-music warning when quantization is intentionally off.

- Harden session recovery and failed saves across Mac, Windows, and web: preserve MIDI-only sessions, keep the current session if an import cannot save its MIDI, use Results when an export folder becomes unavailable, and offer recovery only when a saved file exists.
- Prevent stale browser audio/session loads, explicitly cancel the matching server run, report interrupted streams, and keep MIDI-only playback audible without misleading comparison controls. Restore numeric timing settings correctly and keep Windows Cancel available if shutdown takes longer than expected.
- Keep Mac build/packaging copies in `.noindex` folders to avoid adding duplicate Spotlight launch results. Extend Windows CI with Finish here, browser-state, and 200% scaling checks.

- Add Finish here during transcription on Mac, Windows, and web: export completed 5-second sections as partial MIDI, close held notes at the cutoff, preserve playback timing, and retain matching audio in saved sessions. Cancel remains separate.

- Refresh Mac, Windows, and web branding with the official MuScriptor logo and Pokestir credit; remove the web LOCAL badge and glow. Move session, processor, version, model-folder, and maintenance controls into the gear menu; add an arrow to Open Web GUI. Align timing controls, add a stable draggable instrument-list height, and enable Mac window resizing and native menu-bar commands.

- Refine Auto with guarded audio-pulse recovery, tighter fitting for supported tempo changes, preserved session metadata, and matching Mac/Windows/web disclosures. Eleven authored rhythm controls pass; complex real-recording accuracy remains unresolved.

- Normalize supported constant Auto estimates near a whole BPM only within 0.05 BPM and 20 ms of whole-recording grid drift; keep note playback timing, manual BPM, explicit anchors, and variable maps unchanged.
- Replace beat-by-beat Auto tempo spikes with a sparse, smoothed tempo map; retain supported tempo changes, approximate unreliable passages with disclosure, and preserve note playback timing.
- Add shared portable sessions with embedded audio, local recovery, and reopen/re-export without model inference.
- Add native cancellation, preserve selection/settings, and warn about unapplied timing changes.
- Label quantization Strict and disclose full snapping; preserve the original performance for reversal.
- Show export prerequisites, detect standard Windows MuseScore installations, and check desktop A/B dependencies before transcription.
- Stage engine upgrades with rollback for failed or interrupted replacements on both platforms.
- Identify the web GUI as Pokestir’s independent MuScriptor Local adaptation, explain added features and local processing, retain original-project credits, and direct feedback to the local project.
- Share Auto/Manual tempo, time signatures, and separate optional quantization across macOS, Windows, and the local web GUI.
- Preserve original playback speed and audio start when changing BPM or meter; remove performance stretching.
- Export changing tempo maps, compound-meter beat units, manual anchors, and meter changes; disclose uncertain detection and fallback tempo.
- Simplify timing controls, move detailed corrections under Advanced, and reuse transcription results for timing edits and click previews.
- Filter isolated extra beat detections conservatively without flattening sustained tempo changes.
- Package the shared engine extension and refresh installed engine sources with the bundled UI.

## 1.0 Beta 4 for macOS — 2026-09-21

- Add the upstream MuScriptor waveform-and-note app icon to the Mac bundle.
- Include the latest shared worker while keeping DirectML-specific changes confined to Windows GPU execution; macOS continues to use Apple MPS or CPU.
- Retain native transcription, instrument options, and the bundled local web GUI from Beta 3.
- Publish as a separate Apple Silicon macOS prerelease; existing Windows releases are unchanged.

## 1.0 Beta 4 for Windows — 2026-09-21

- **New feature: experimental AMD GPU support through DirectML**, introduced in Windows Beta 3 and corrected in Beta 4 for desktop and local web transcription. Select your Radeon GPU in the processor picker. The owner reports successful testing after the RX 6800 XT failure; CPU remains available.
- **Upgrading:** choose **App → Repair Dependencies** after installing the update to install the required GPU dependencies.
- Fix the reported DirectML `Cannot set version_counter for inference tensor` failure by replacing upstream's inference-mode generator decorator with no-gradient execution on DirectML model instances only. Desktop and web transcription share this correction.
- Recognize that DirectML error for desktop CPU recovery if it occurs elsewhere.
- Keep waveform padding/collation on CPU and rebuild the DirectML attention cache without nested slice writes, preventing corrupted conditioning and empty MIDI output.
- Draw readable circle-plus instrument buttons independently of Windows font glyphs.
- Use the official upstream MuScriptor mark for Windows executable/setup/window icons and the next macOS app bundle. Existing macOS releases remain unchanged.
- Set the Windows taskbar application identity and matching installer shortcuts so the running app uses the MuScriptor icon instead of Python's default icon.
- AMD support remains experimental. Full Large-model checks passed on integrated AMD graphics and NVIDIA through DirectML; the owner's RX 6800 XT follow-up was positive. Performance and compatibility vary by hardware and model.

## 1.0 Beta 3 for Windows — 2026-09-21

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
