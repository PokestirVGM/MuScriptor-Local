import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

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

    def test_model_caches_are_separate_and_respect_cache_override(self):
        with patch("huggingface_hub.constants.HF_HUB_CACHE", str(self.folder / "custom-cache")):
            for size in worker.MODELS:
                repo = f"MuScriptor/muscriptor-{size}"
                self.assertEqual(worker.model_directory(size), self.folder.resolve() / "custom-cache" / f"models--MuScriptor--muscriptor-{size}")
                with patch("huggingface_hub.hf_hub_download", side_effect=["/snapshot/config.json", "/snapshot/model.safetensors"]) as download:
                    self.assertEqual(worker.cached_weights(size), Path("/snapshot/model.safetensors"))
                    self.assertEqual([call.args[0] for call in download.call_args_list], [repo, repo])
                    self.assertTrue(all(call.kwargs["local_files_only"] for call in download.call_args_list))

    def test_mismatched_snapshots_are_not_ready(self):
        with patch("huggingface_hub.hf_hub_download", side_effect=["/revision-a/config.json", "/revision-b/model.safetensors"]):
            self.assertIsNone(worker.cached_weights("medium"))

    def test_download_uses_selected_model_and_pins_revision(self):
        for size in worker.MODELS:
            with self.subTest(size=size), patch.object(worker, "cached_weights", return_value=None), patch.object(worker, "require_space") as space, patch.object(worker, "emit"), patch("huggingface_hub.hf_hub_download", side_effect=["/cache/revision-a/config.json", "/cache/revision-a/model.safetensors"]) as download:
                worker.get_weights(size)
                self.assertEqual(space.call_args.args[1], worker.MODEL_SPACE[size])
                self.assertEqual(download.call_args.args[:2], (worker.model_repo(size), "model.safetensors"))
                self.assertEqual(download.call_args.kwargs["revision"], "revision-a")
                progress = download.call_args.kwargs["tqdm_class"]
                with patch.object(worker, "emit") as emitted:
                    with progress(total=100) as bar:
                        bar.update(100)
                    reports = [call.kwargs for call in emitted.call_args_list if call.args == ("download",)]
                    self.assertTrue(reports)
                    self.assertEqual(reports[-1]["model"], size)
                    self.assertEqual(reports[-1]["directory"], str(worker.model_directory(size)))

    def test_switch_releases_loaded_model_and_does_not_download(self):
        engine = worker.Engine.__new__(worker.Engine)
        engine.model = object()
        engine.model_size = "large"
        engine.device = "cpu"
        engine.ready = Mock()
        with patch("torch.backends.mps.is_available", return_value=True), patch("torch.mps.empty_cache") as clear, patch.object(worker, "get_weights") as download, patch.object(worker, "emit"):
            engine.select("small")
            self.assertIsNone(engine.model)
            self.assertEqual(engine.model_size, "small")
            self.assertEqual(engine.device, "mps")
            clear.assert_called_once()
            download.assert_not_called()
            engine.ready.assert_called_once()
        with self.assertRaises(worker.UserError):
            engine.select("invalid")
        self.assertEqual(engine.model_size, "small")

    def test_load_uses_selected_weights(self):
        engine = worker.Engine.__new__(worker.Engine)
        engine.model = None
        engine.model_size = "medium"
        engine.device = "cpu"
        model = Mock()
        parameter = Mock()
        parameter.device.type = "cpu"
        model._model.parameters.return_value = iter([parameter])
        with patch.object(worker, "get_weights", return_value=Path("/medium/model.safetensors")) as weights, patch("muscriptor.TranscriptionModel.load_model", return_value=model) as load, patch.object(worker, "emit"):
            engine.load()
            weights.assert_called_once_with("medium")
            load.assert_called_once_with(Path("/medium/model.safetensors"), device="cpu")

    def test_plan_and_save_to_chosen_folder_without_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = worker.planned_output(self.wav, Path(folder))
            self.assertEqual(destination, Path(folder) / "source_transcription.mid")
            self.assertFalse(destination.exists(), "Planning should not create a file")
            output, fallback = worker.save_result(self.wav, b"midi", destination)
            self.assertEqual(output, destination)
            self.assertFalse(fallback)
            self.assertEqual(output.read_bytes(), b"midi")
            second = worker.planned_output(self.wav, Path(folder))
            self.assertEqual(second.name, "source_transcription (2).mid")
            second.write_bytes(b"arrived after preview")
            actual, _ = worker.save_result(self.wav, b"new midi", second)
            self.assertNotEqual(actual, second)
            self.assertEqual(second.read_bytes(), b"arrived after preview")

    def test_plan_rejects_directory_and_missing_audio(self):
        for source in (self.folder, self.folder / "missing.wav"):
            with self.assertRaisesRegex(worker.UserError, "no longer available"):
                worker.planned_output(source)

    def test_plan_previews_fallback_for_unwritable_source_folder(self):
        with patch.object(worker.os, "access", return_value=False), patch.object(worker, "emit") as emitted:
            planned = worker.planned_output(self.wav)
            self.assertEqual(planned.parent, worker.SUPPORT / "Results")
            self.assertEqual(emitted.call_args.args, ("warning",))


if __name__ == "__main__":
    unittest.main()
