# Privacy and local data

MuScriptor Local transcribes audio on your computer. The wrapper does not upload audio or generated MIDI, run a hosted inference service, or collect app analytics.

Network connections are used for dependency installation, updates, Hugging Face authentication, model downloads, the upstream optional tempo model, and optional web playback/rendering SoundFonts. These providers receive normal download-request information under their own policies. Model access may require sharing account information with the model owner through Hugging Face's terms-acceptance process.

**Open Web GUI** starts the adapted local interface on an automatically selected `127.0.0.1` port. It is not exposed to the network; browser uploads go to the local engine on this computer. Unrelated website origins and hostnames are rejected. The GUI uses the desktop's selected model and processor, and stops when you return to desktop or quit the app. Its files use the browser's download location. The bundled frontend disables analytics and remote font requests. Opening external project links or fetching optional upstream assets can still make network requests.

Authentication is handled by the Hugging Face client. Tokens are passed to the worker through a private process pipe and stored in the client's user cache; they are not embedded in app packages or command-line arguments. Hugging Face credentials and caches may be shared with other tools on the computer. Existing cache environment settings are respected.

Audio decoding can create temporary local WAV files. Completed MIDI is saved to the selected destination or the app's recovery folder. Diagnostic logs can include file paths, hardware details, error messages, and download diagnostics. Inspect and redact logs before sharing them; never publish tokens or private recordings in an issue report.

Removing the app does not delete the user's audio or MIDI. Private runtime files, recovered results, logs, and model caches can be removed separately as described in the README. Revoke an unwanted or exposed token in Hugging Face account settings.

Saved `.muscriptor` sessions contain the recording, original performance MIDI, beat data, and timing settings. The app keeps one automatic recovery session in its application-data folder; it is replaced by the next completed/applied session. The desktop-launched web GUI uses the same recovery location. A standalone browser fallback uses IndexedDB for its current address. Neither storage method uploads recovery data to a remote service. Remove recovery files or browser site data when no longer wanted.
