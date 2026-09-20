"""Mac options bridge: real upstream MIDI/post-processing, mocked inference."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import worker
import mido
import numpy as np
import soundfile as sf
from muscriptor import TranscriptionModel
from muscriptor.events import NoteStartEvent, NoteEndEvent, ProgressEvent
from muscriptor.tokenizer.mt3 import MT3_FULL_PLUS_GROUP_NAMES
from muscriptor.utils.beats import BeatGrid, read_bar_offset


class MacOptionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        checkpoint = self.folder / "checkpoints/beat_this-final0.ckpt"
        checkpoint.parent.mkdir()
        checkpoint.touch()
        cache = patch("torch.hub.get_dir", return_value=str(self.folder))
        cache.start()
        self.addCleanup(cache.stop)
        self.audio = self.folder / "song.wav"
        sf.write(self.audio, np.zeros(32000), 16000)
        self.events = []
        for i in range(48):
            start = NoteStartEvent(60, 0.52 + i * 0.5, i, "acoustic_piano")
            self.events += [start, NoteEndEvent(start.start_time + 0.18, start)]
        self.engine = worker.Engine.__new__(worker.Engine)
        self.engine.device = "cpu"
        self.engine.load = Mock()
        self.engine.model = TranscriptionModel.__new__(TranscriptionModel)
        self.engine.model._inst_to_program = {"acoustic_piano": 0}
        self.engine.model.transcribe = Mock(return_value=[ProgressEvent(1, 1), *self.events])
        self.grid = BeatGrid(120, 4, 0, beats=np.arange(60) * 0.5)
        self.engine.model.detect_beat_grid_for = Mock(return_value=self.grid)
        self.reports = []
        emitter = patch.object(worker, "emit", side_effect=lambda kind, **kw: self.reports.append(dict(type=kind, **kw)))
        emitter.start()
        self.addCleanup(emitter.stop)

    def run_transcription(self, **options):
        self.engine.transcribe(self.audio, self.folder / "out.mid", **options)
        return next(e for e in reversed(self.reports) if e["type"] == "complete")

    def test_default_raw_and_opt_in_quantization_both_correct_onset_delay(self):
        for quantize in (False, True):
            with self.subTest(quantize=quantize):
                result = self.run_transcription(quantize=quantize)
                measured = self.grid.with_onset_delay([ev.start_time for ev in self.events if isinstance(ev, NoteStartEvent)])
                self.assertAlmostEqual(measured.onset_delay, 0.02, places=3)
                expected = self.engine.model.events_to_midi_bytes(iter(self.events), beat_grid=measured, quantize=quantize)
                self.assertEqual(Path(result["path"]).read_bytes(), expected)
                messages = list(mido.MidiFile(result["path"]))
                first_note = next(m for m in messages if m.type == "note_on")
                self.assertAlmostEqual(first_note.time - read_bar_offset(mido.MidiFile(result["path"])), 0.5, places=2)
                self.assertEqual(result["quantized"], quantize)
                self.assertIsNone(result["ab_path"])
        self.engine.model.transcribe.assert_called_with(unittest.mock.ANY, instruments=None)

    def test_catalog_and_multiple_instruments_passed_to_official_api(self):
        self.assertEqual(worker.supported_instruments(), list(MT3_FULL_PLUS_GROUP_NAMES))
        self.run_transcription(instruments=["acoustic_piano", "drums", "acoustic_piano"])
        self.assertEqual(self.engine.model.transcribe.call_args.kwargs, {"instruments": ["acoustic_piano", "drums"]})
        self.run_transcription(instruments=[])
        self.assertIsNone(self.engine.model.transcribe.call_args.kwargs["instruments"])

    def test_invalid_options_rejected_before_inference(self):
        for options in ({"instruments": ["piano"]}, {"instruments": "drums"}, {"instruments": [42]}, {"quantize": "false"}, {"create_ab": 1}):
            with self.subTest(options=options), self.assertRaises(worker.UserError):
                self.run_transcription(**options)
        self.engine.load.assert_not_called()

    def test_no_grid_or_subdivision_reports_quantization_fallback(self):
        for grid in (None, BeatGrid(120, 4, 0)):
            self.engine.model.detect_beat_grid_for.return_value = grid
            result = self.run_transcription(quantize=True)
            self.assertFalse(result["quantized"])
            self.assertTrue(Path(result["path"]).exists())
            self.assertTrue(any("Performance-timing MIDI" in e.get("message", "") for e in self.reports))

    def test_offline_tempo_failure_keeps_raw_midi(self):
        self.engine.model.detect_beat_grid_for.side_effect = RuntimeError("offline")
        result = self.run_transcription()
        self.assertTrue(Path(result["path"]).exists())
        self.assertFalse(result["quantized"])

    def test_cpu_retry_preserves_options(self):
        self.engine.device = "mps"
        self.engine.model.transcribe.side_effect = [RuntimeError("MPS unavailable"), self.events]
        self.engine.fallback = Mock(side_effect=lambda: setattr(self.engine, "device", "cpu"))
        self.run_transcription(instruments=["acoustic_piano"], quantize=True)
        self.engine.fallback.assert_called_once()
        self.assertEqual([c.kwargs for c in self.engine.model.transcribe.call_args_list], [{"instruments": ["acoustic_piano"]}] * 2)

    def test_ab_uses_performance_midi_and_keeps_decoded_audio_alive(self):
        def render(data, audio, output, soundfont):
            self.assertTrue(audio.is_file())
            self.assertTrue(output.is_file())
            grid = self.grid.with_onset_delay([ev.start_time for ev in self.events if isinstance(ev, NoteStartEvent)])
            self.assertEqual(data, self.engine.model.events_to_midi_bytes(iter(self.events), beat_grid=grid, quantize=False))
            self.assertNotEqual(data, output.read_bytes())
            return self.folder / "comparison.wav"
        with patch.object(worker, "render_comparison", side_effect=render) as render:
            result = self.run_transcription(quantize=True, create_ab=True, soundfont="local.sf2")
            self.assertEqual(result["ab_path"], str(self.folder / "comparison.wav"))
            render.assert_called_once()

    def test_ab_disabled_does_not_touch_renderer(self):
        with patch.object(worker, "render_comparison") as render:
            self.run_transcription()
            render.assert_not_called()

    def test_missing_dependencies_keep_completed_midi_with_mac_help(self):
        for available, soundfont, expected in ((None, None, "brew install fluidsynth"), ("/opt/homebrew/bin/fluidsynth", None, "Choose SoundFont")):
            with patch.object(worker.shutil, "which", return_value=available):
                result = self.run_transcription(create_ab=True, soundfont=soundfont)
                self.assertTrue(Path(result["path"]).is_file())
                self.assertIsNone(result["ab_path"])
                self.assertTrue(any(expected in e.get("message", "") for e in self.reports))

    def test_upstream_render_stereo_unique_publication_and_cleanup(self):
        font = self.folder / "font.sf2"
        font.touch()
        output = self.folder / "out.mid"
        existing = self.folder / "out_AB.wav"
        existing.write_bytes(b"keep")
        original = 0.2 * np.sin(2 * np.pi * 440 * np.arange(88200) / 44100)
        sf.write(self.audio, original, 44100)
        temporary_paths = []
        def synth(midi, font_path):
            temporary_paths.append(midi)
            self.assertEqual(font_path, font)
            return np.ones(44100, dtype=np.float32) * 0.1
        data = self.engine.model.events_to_midi_bytes(iter(self.events), beat_grid=self.grid)
        with patch.object(worker.shutil, "which", return_value="/opt/homebrew/bin/fluidsynth"), patch("muscriptor.utils.auralization._synthesize_midi", side_effect=synth):
            result = worker.render_comparison(data, self.audio, output, str(font))
        self.assertEqual(existing.read_bytes(), b"keep")
        self.assertEqual(result.name, "out_AB (2).wav")
        self.assertEqual(sf.info(result).channels, 2)
        stereo, rate = sf.read(result)
        self.assertEqual(rate, 44100)
        np.testing.assert_allclose(stereo[:, 0], sf.read(self.audio)[0], atol=1e-4)
        self.assertFalse(np.allclose(stereo[:, 0], stereo[:, 1]))
        self.assertTrue(all(not p.exists() for p in temporary_paths))
        self.assertFalse(list(self.folder.glob(".muscriptor-*")))

    def test_ab_save_falls_back_to_results_without_overwrite(self):
        font = self.folder / "font.sf2"
        font.touch()
        def render(**kw):
            kw["output_path"].write_bytes(b"complete audio")
        destination = self.folder / "recovered.wav"
        with patch.object(worker.shutil, "which", return_value="fluidsynth"), patch("muscriptor.utils.auralization.auralize", side_effect=render), patch.object(worker, "SUPPORT", self.folder / "Support"), patch.object(worker, "write_unique", side_effect=[PermissionError(), destination]) as save:
            result = worker.render_comparison(b"midi", self.audio, self.folder / "song.mid", str(font))
        self.assertEqual(result, destination)
        self.assertEqual(save.call_args.args[0], self.folder / "Support/Results")
        self.assertEqual(save.call_args.args[3], ".wav")

    def test_failed_renderer_removes_partial_and_keeps_midi(self):
        font = self.folder / "font.sf2"
        font.touch()
        temps = []
        def fail(**kw):
            temps.append(kw["output_path"])
            kw["output_path"].write_bytes(b"partial")
            raise RuntimeError("bad soundfont")
        with patch.object(worker.shutil, "which", return_value="fluidsynth"), patch("muscriptor.utils.auralization.auralize", side_effect=fail):
            result = self.run_transcription(create_ab=True, soundfont=str(font))
        self.assertTrue(Path(result["path"]).is_file())
        self.assertIsNone(result["ab_path"])
        self.assertTrue(all(not p.exists() for p in temps))
        self.assertFalse(list(self.folder.glob("*_AB*.wav")))


if __name__ == "__main__":
    unittest.main()
