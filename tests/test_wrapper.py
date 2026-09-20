import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import worker
import numpy as np
import soundfile as sf
import subprocess
import imageio_ffmpeg
from muscriptor.utils.audio import load_audio


class WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        cls.wav = cls.folder / "source.wav"
        t = np.arange(44100 * 2) / 44100
        mono = 0.2 * np.sin(2 * np.pi * 440 * t)
        sf.write(cls.wav, np.column_stack([mono, mono]), 44100, subtype="PCM_24")
        for suffix, codec in [("mp3", "libmp3lame"), ("flac", "flac"), ("m4a", "aac"), ("aac", "aac")]:
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(cls.wav), "-c:a", codec, str(cls.folder / f"source.{suffix}")], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_real_audio_formats_and_upstream_sample_handling(self):
        for suffix in ("wav", "mp3", "flac", "m4a", "aac"):
            with self.subTest(suffix=suffix), worker.decoded_audio(self.folder / f"source.{suffix}") as decoded:
                info = sf.info(str(decoded))
                self.assertEqual(info.samplerate, 44100)
                self.assertEqual(info.channels, 2)
                samples = load_audio(decoded)
                self.assertEqual(samples.shape[0], 1)
                self.assertTrue(31900 <= samples.shape[-1] <= 34000)
            if suffix in ("m4a", "aac"):
                self.assertFalse(decoded.exists(), "Temporary decoded WAV leaked")

    def test_corrupt_file_is_readable_error(self):
        corrupt = self.folder / "corrupt.mp3"
        corrupt.write_bytes(b"not audio at all")
        with self.assertRaisesRegex(worker.UserError, "couldn’t be decoded"):
            with worker.decoded_audio(corrupt):
                self.fail("Corrupt audio should never reach the model")

    def test_cleanup_when_transcription_raises(self):
        decoded = None
        with self.assertRaises(RuntimeError):
            with worker.decoded_audio(self.folder / "source.m4a") as decoded:
                raise RuntimeError("simulated model failure")
        self.assertFalse(decoded.exists())

    def test_save_never_overwrites_and_leaves_no_partial(self):
        folder = self.folder / "results"
        first = worker.write_unique(folder, "song_transcription", b"first")
        second = worker.write_unique(folder, "song_transcription", b"second")
        self.assertEqual(first.read_bytes(), b"first")
        self.assertEqual(second.name, "song_transcription (2).mid")
        self.assertEqual(second.read_bytes(), b"second")
        self.assertEqual(len(list(folder.iterdir())), 2)

    def test_save_permission_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(worker, "SUPPORT", Path(folder)), patch.object(worker, "write_unique", side_effect=[PermissionError("read only"), Path(folder) / "Results/song.mid"]) as writer:
                result, fallback = worker.save_result(Path("/protected/song.wav"), b"midi")
                self.assertTrue(fallback)
                self.assertEqual(writer.call_args.args[0], Path(folder) / "Results")

    def test_only_device_errors_trigger_cpu_retry(self):
        self.assertTrue(worker.mps_error(RuntimeError("MPS backend out of memory")))
        self.assertTrue(worker.mps_error(NotImplementedError("operation unavailable for MPS")))
        self.assertFalse(worker.mps_error(RuntimeError("invalid audio")))
        self.assertFalse(worker.mps_error(OSError("MPS file missing")))

    def test_insufficient_disk_space(self):
        with patch.object(worker.shutil, "disk_usage", return_value=type("Usage", (), {"free": 10})()):
            with self.assertRaisesRegex(worker.UserError, "disk space"):
                worker.require_space(self.folder, 1024)

    def test_default_is_large(self):
        self.assertEqual(worker.MODEL, "large")
        self.assertEqual(worker.REPO, "MuScriptor/muscriptor-large")


if __name__ == "__main__":
    unittest.main()
