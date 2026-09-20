"""Create a self-authored 12-second harmonic melody for end-to-end validation."""
from pathlib import Path
import numpy as np
import soundfile as sf
import imageio_ffmpeg
import subprocess

folder = Path(__file__).parent
rate = 44100
audio = np.zeros(rate * 12, dtype=np.float32)
notes = [60, 64, 67, 72, 71, 67, 65, 64, 62, 65, 69, 74, 72, 69, 67, 64, 60, 67, 64, 60]
for i, note in enumerate(notes):
    start = int((0.25 + i * 0.55) * rate)
    t = np.arange(int(0.5 * rate)) / rate
    f = 440 * 2 ** ((note - 69) / 12)
    wave = sum(np.sin(2 * np.pi * f * h * t) / h**2 for h in range(1, 7))
    envelope = np.minimum(t / 0.012, 1) * np.exp(-5 * t) * np.minimum((0.5 - t) / 0.06, 1)
    audio[start:start + len(t)] += 0.35 * wave * envelope
wav = folder / "Local Test Melody.wav"
sf.write(wav, np.column_stack([audio, audio]), rate, subtype="PCM_24")
for ext, codec in [("mp3", "libmp3lame"), ("flac", "flac"), ("m4a", "aac"), ("aac", "aac")]:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-i", str(wav), "-c:a", codec, str(wav.with_suffix("." + ext))], check=True)
print("Created 12-second test melody in WAV, MP3, FLAC, M4A and AAC.")
