# Windows finishing checklist — 1.0 Release Candidate 1

The current source contains the matching Mac, Windows, and local web changes. This is a release candidate; it has not been published as stable 1.0. Existing Beta 4 releases must remain intact.

The latest [usability audit](validation/USABILITY_AUDIT.md) adds session/save safeguards, cancellation fixes, stale browser playback/export protection, correct MIDI-only playback and WAV export, and selection of the newest recovery save. The Mac-hosted regression run covers 160 Python tests (two skips) plus 18 browser state tests; the Windows interface also passes 200% offscreen scaling checks. These do not replace the PC checks below.

The [rhythm edge-case pass](validation/RHYTHM_EDGE_CASES.md) fixes overlapping notes, controller timing/order, serialization drift, short-note quantization, and compound-meter click changes in the shared engine. Test sustain, overlapping notes, triplets, and 4/4 → 6/8 in your Windows DAW as well. The later meter-evidence refinement addresses those eight authored failures; dense real-recording limitations remain documented.

**Before release:** read [the VGM/mixed-meter stress-test results](validation/VGM_STRESS_RESULTS.md). MIDI time preservation passes, and the [pulse refinement](validation/RHYTHM_REFINEMENT.md) now passes all 11 authored controls, but complex real-recording Auto accuracy remains unresolved and changing-meter suggestions require repeated percussion evidence and remain limited. Windows installer testing cannot resolve those shared-engine limitations. Do not describe this candidate as having verified automatic alignment for complex music.

The [latest Auto meter refinement](validation/METER_EVIDENCE.md) improves swing, compound, odd, and changing-meter cases with clear repeated percussion. Test fresh analysis and session reopening on Windows, including 4/4 → 6/8 → 7/8 and a grouped odd-meter click. Old sessions retain cached detections; analyze source audio again for new suggestions.

Latest [final readiness pass](validation/FINAL_READINESS.md): build 12 restores session state after web return/restart, preserves pending desktop timing, keeps timing controls available with an undownloaded model, ignores stale worker messages, and rejects malformed audio before inference. Verify these flows on Windows, including returning after saving changed timing in the browser.

## Get the correct source

Use the latest `main` from `https://github.com/PokestirVGM/MuScriptor-Local.git`, preserving any local edits before pulling, or extract the matching source handoff ZIP into a fresh folder. Confirm the checkout includes `VERSION` set to `1.0.0-rc.1` and this build-12 readiness report. The source contains no models, credentials, user recordings, or generated sessions.

## Fastest route to a Windows candidate

First check the **Windows build** GitHub Actions run for your exact commit. If it succeeds, its `MuScriptor-Local-Windows-x64-Preview` artifact contains the RC1 installer and portable ZIP; use those for PC acceptance instead of rebuilding identical binaries. Otherwise run the build command below and fix any build/test failures. Keep the RC1 version and the existing Beta 4 releases unchanged.

Prioritize installed startup/upgrade, one real transcription on the available GPU, Finish here, cancellation/retry, session recovery and desktop/web round-trip, manual BPM/meter timing preservation, and a DAW import with the MIDI tempo map. Then complete the remaining applicable checks below. Record exact tested hardware, artifact hashes, results, and anything blocked; provide the installer/portable ZIP without publishing a release or claiming stable 1.0. Signing requires the owner's identity if available; do not let unavailable signing prevent producing an explicitly unsigned local candidate.

## Build

Install Git, Python 3.12, Node.js 22+, pnpm 10.20.0, and Inno Setup 6. From the source directory, run:

```powershell
./tools/build-windows.ps1
```

The script fetches the pinned upstream engine, applies the tracked local extension, builds the frontend, and packages the launcher. Outputs are `dist/windows/MuScriptor-Local-1.0-RC1-Windows-x64-Setup.exe` and the matching portable ZIP. Test these exact files before release.

## Check on the PC

- Install in a clean Windows user profile. Complete setup, authentication, and a model download. Run one whole recording. Confirm the displayed processor is the processor actually used.
- Upgrade a Beta 4 installation using the candidate. Verify engine startup, saved MIDI, model caches, and credentials remain usable. Interrupted engine replacement should recover the previous engine; dependency repair is still available.
- During transcription, wait for a completed section and choose Finish here & save MIDI. Verify the `_partial.mid` ends at the displayed completed section, sustained notes close cleanly, the partial session reopens with matching audio, and starting the same file again transcribes the whole file. Check the equivalent browser download action.
- Cancel a model download and a running transcription. Verify the worker and its child processes stop, controls recover, and the selected file/settings remain. Retry. No partial transcription/resume is promised.
- Save a `.muscriptor` session in the desktop app. Restart and use Recover Last Session. Open the saved file in the web GUI; change BPM/meter and export without model inference. Save from the browser and reopen on desktop. Test a session created on Mac as well.
- Change timing without saving/applying and attempt to close or replace the session. Confirm the warning can keep you in the current session. Save separate session files for work you want to retain; recovery retains only the latest completed/applied project.
- Leave Strict quantization off for original timing. Test manual BPM 80/140/200 and 6/8. Enable Strict, compare, then disable it and apply: original performance timing must return. This candidate has no new AI quantizer/Gentle mode.
- Confirm Auto exports a sparse tempo map instead of beat-by-beat spikes. Reopen a saved session to regenerate its map from cached beats. The new audio-pulse check runs during new audio analysis; reopening alone does not re-detect beats. Check the click against the audio, especially in passages flagged as unreliable; tempo estimates remain fallible.
- Install MuseScore 4+ and verify the browser readiness check enables sheet exports. Without it, the menu should explain the requirement. Test FluidSynth with a local SF2 for desktop A/B; test the browser SoundFont first-use download and subsequent offline export. A missing desktop A/B dependency should be reported before transcription begins.
- Import exported MIDI into the DAW(s) you use. Import its tempo map where required by that DAW. Check audio/MIDI start alignment, tempo changes, pickups, 6/8 beat units, note lengths, and meter changes. Record DAW versions and exact import options. MIDI-host handling of fractional pickups is not proven by byte-level tests.
- Check the MuScriptor logo and Pokestir credit, Open Web GUI ↗, and gear menu. Open/Recover Session, Processor and App Information, version, model download folder, dependency repair, logs, and export checks should be reachable there. Drag the instrument-list grip up/down and use its arrow keys; confirm smooth movement and scrollability.
- Inspect the native UI at 100%, 150%, and 200% scaling and both themes. Check browser controls at narrow and wide widths, keyboard navigation, long filenames, non-ASCII folders, disk-full handling, and read-only destinations.
- Test Small/Medium/Large as supported by memory, CPU, and your available GPU. AMD DirectML remains experimental. Previous Beta 4 results are historical and do not replace candidate testing.
- Close the web GUI through Return to Desktop and quit the app. Verify its local server and model process exit.

## Automated checks

Use the installed engine Python for worker/session tests and the build Python with PySide6 for UI tests:

```powershell
python -m unittest discover -s tests -p test_windows_ui.py -v
& "$env:LOCALAPPDATA/MuScriptor Local/Engine/.venv/Scripts/python.exe" -m unittest discover -s tests -p test_release_ready.py -v
& "$env:LOCALAPPDATA/MuScriptor Local/Engine/.venv/Scripts/python.exe" -m unittest discover -s tests -p "test_rhythm*.py" -v
```

The GitHub Windows workflow also checks setup, packaged startup, UI scaling, worker logic, sessions, timing, and DirectML adapter behavior. Passing simulated/CPU checks is not a GPU benchmark.

## Remaining release steps

Record outcomes and resolve failures before calling this stable 1.0. Mac Developer ID signing/notarization and Windows publisher signing require the owner's signing identities; current build scripts still produce locally/ad-hoc signed Mac and unsigned Windows artifacts. Check the actual downloaded installer experience. Inspect archives for private data and retain third-party notices. Publish only after the owner approves the tested candidate; create a new release rather than replacing Beta 4.
