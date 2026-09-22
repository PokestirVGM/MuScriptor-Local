# MuScriptor Local — 1.0 Release Candidate 1

Independent adaptation by Pokestir, based on MuScriptor by Kyutai and Mirelo. This is a prerelease for Apple Silicon Macs running macOS 14 or later.

[Download macOS RC1](https://github.com/PokestirVGM/MuScriptor-Local/releases/tag/v1.0.0-rc.mac.1) · [Release validation](https://github.com/PokestirVGM/MuScriptor-Local/blob/main/validation/MACOS_RC1_RELEASE.md)

## Install and start

Move **MuScriptor Local.app** into Applications and open it. First setup needs Internet access to install a private Python environment and dependencies. Choose Small, Medium, or Large, accept that model’s terms through your own Hugging Face account, and connect with your own read token to download it. Each size needs separate model access and disk space. Cached transcription runs locally.

This candidate is ad-hoc signed, not Developer ID signed or Apple-notarized. Stable distribution still requires final signing and installation checks. The package includes no models, credentials, recordings, or saved user sessions.

After installing an update, quit and reopen the app: an already-running window continues using the old native build. Gear → App Information shows the running build and processor.

## Transcribe and keep your work

1. Choose a model, then drop an audio file into the window.
2. Review the MIDI destination. Optionally select instruments; leave the list empty to detect any supported instrument.
3. Choose Auto tempo or enter a known Manual BPM and time signature. Leave **Strict quantization** off to retain original note timing.
4. Start transcription. **Finish here** saves fully completed sections; **Cancel** discards the current run. Finish here may omit the unfinished section.
5. Save a MIDI copy or a portable **Session**. Gear provides Open Session and Recover Last Session. Save separate sessions for work you want to retain; recovery keeps only the latest saved/applied project.

Changing BPM or meter never stretches playback. Strict quantization deliberately moves individual notes to the grid and can reduce accuracy if the grid is wrong. Auto can suggest repeated swing, compound, odd, and changing-meter patterns with clear percussion; complex arrangements still need checking and manual correction. Beat anchors and meter corrections are under Advanced timing. Reanalyze source audio for new detector improvements; old sessions keep their cached analysis.

## Web GUI and optional exports

**Open Web GUI ↗** provides audio/MIDI preview, browser downloads, and sheet-music options. Keep the desktop app open. **Return to Desktop** stops the web server and restores the latest saved session; save/apply browser changes before returning. Unsaved browser edits and an active web transcription are not retained.

MIDI export needs no separate renderer. Sheet music needs MuseScore 4+. Native A/B audio requires FluidSynth and a local SF2 SoundFont. Browser synthesis may download its SoundFont on first use. Check Export Requirements in the gear menu for installed capabilities.

## Settings and help

Gear → App Information contains processor selection, version, and model folder. Gear and the Mac menu bar also provide session actions, logs, repair, and export checks. Resize the window from an edge or corner; drag the grip below Instruments to resize its list.

If the engine stops, Try Again restarts it and restores the saved session when available. Repair Dependencies can repair setup problems. Keep the original recording and exported MIDI/session files; transcription and automatic rhythm interpretation remain approximate.
