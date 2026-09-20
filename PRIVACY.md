# Privacy and local data

MuScriptor Local transcribes audio on your computer. The wrapper does not upload audio or generated MIDI, run a hosted inference service, or collect app analytics.

Network connections are used for dependency installation, updates, Hugging Face authentication, model downloads, and the upstream optional tempo model. These providers receive normal download-request information under their own policies. Model access may require sharing account information with the model owner through Hugging Face's terms-acceptance process.

Authentication is handled by the Hugging Face client. Tokens are passed to the worker through a private process pipe and stored in the client's user cache; they are not embedded in app packages or command-line arguments. Hugging Face credentials and caches may be shared with other tools on the computer. Existing cache environment settings are respected.

Audio decoding can create temporary local WAV files. Completed MIDI is saved to the selected destination or the app's recovery folder. Diagnostic logs can include file paths, hardware details, error messages, and download diagnostics. Inspect and redact logs before sharing them; never publish tokens or private recordings in an issue report.

Removing the app does not delete the user's audio or MIDI. Private runtime files, recovered results, logs, and model caches can be removed separately as described in the README. Revoke an unwanted or exposed token in Hugging Face account settings.
