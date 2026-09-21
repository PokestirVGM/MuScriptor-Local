"""Adapter/routing regression tests. These do not claim real DirectML validation."""
import contextlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import torch
from muscriptor.transcription_model import _build_model, _ModelConfig
from muscriptor.modules.conditioners import WavCondition

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import worker


class DirectMLTests(unittest.TestCase):
    def setUp(self):
        # These are CPU/meta tests. Upstream's timing helper otherwise tries to
        # synchronize the host Mac's unrelated MPS device, even for CPU tensors.
        timing = patch("muscriptor.accelerator.synchronize")
        timing.start()
        self.addCleanup(timing.stop)

    def tiny_model(self):
        decoder = _build_model(torch.device("cpu"), _ModelConfig(dim=16, num_heads=2, num_layers=1, card=32))
        decoder.eval()
        return SimpleNamespace(_model=decoder, _device=torch.device("cpu"))

    def inputs(self):
        wav = torch.linspace(-0.1, 0.1, 3200).reshape(1, 1, -1)
        return {"self_wav": WavCondition(wav, torch.tensor([3200]), [16000], [None], [0.0]),
                "instrument_group": torch.tensor([[1]]), "dataset_name": torch.tensor([[1]])}

    def test_cpu_conditioning_and_decoder_outputs_are_unchanged(self):
        model = self.tiny_model()
        inputs = self.inputs()
        with torch.no_grad(), contextlib.redirect_stdout(io.StringIO()):
            original = model._model.condition_provider(inputs)
            sequence = torch.tensor([[1, 2]])
            expected = model._model(sequence, original, first_step=True)
            worker.move_transcription_to_directml(model, torch.device("cpu"))
            transferred = model._model.condition_provider(inputs)
            actual = model._model(sequence, transferred, first_step=True)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        self.assertFalse(model._model.autocast.enabled)

    def test_only_decoder_and_finished_conditions_move_to_target(self):
        model = self.tiny_model()
        # Meta gives us a distinct device without needing an AMD GPU on CI.
        worker.move_transcription_to_directml(model, torch.device("meta"))
        provider = model._model.condition_provider
        self.assertEqual(model._device.type, "meta")
        self.assertTrue(all(p.device.type == "cpu" for p in provider.parameters()))
        self.assertTrue(all(b.device.type == "cpu" for b in provider.buffers()))
        for name, module in model._model.named_children():
            if name != "condition_provider":
                self.assertTrue(all(p.device.type == "meta" for p in module.parameters()))
        with torch.no_grad(), contextlib.redirect_stdout(io.StringIO()):
            result = provider(self.inputs())
        self.assertEqual(set(result), {"self_wav", "instrument_group", "dataset_name"})
        self.assertTrue(all(t.device.type == "meta" for pair in result.values() for t in pair))

    def test_automatic_prefers_discrete_radeon_over_integrated_adapter(self):
        devices = [dict(id="privateuseone:0", default=True, discrete=False),
                   dict(id="privateuseone:1", default=False, discrete=True), dict(id="cpu")]
        self.assertEqual(worker.choose_device(devices), "privateuseone:1")
        self.assertEqual(worker.choose_device(devices, "privateuseone:0"), "privateuseone:0")
        self.assertEqual(worker.choose_device(devices, "cpu"), "cpu")
        devices.append(dict(id="cuda:0", memory_bytes=8 * 1024**3))
        self.assertEqual(worker.choose_device(devices), "cuda:0")

    def test_optional_directml_is_not_imported_on_mac(self):
        with patch.object(worker.platform, "system", return_value="Darwin"), patch.dict(sys.modules, {"torch_directml": None}):
            self.assertEqual(worker.directml_devices(), [])

    def test_missing_directml_keeps_cpu_available(self):
        with patch.object(worker.platform, "system", return_value="Windows"), patch.dict(sys.modules, {"torch_directml": None}), patch("torch.cuda.is_available", return_value=False), patch("torch.backends.mps.is_available", return_value=False):
            self.assertEqual(worker.choose_device(worker.device_inventory()), "cpu")

    def test_inventory_probes_adapters_and_skips_broken_one(self):
        dml = SimpleNamespace(device_count=lambda: 2, device=lambda i: f"privateuseone:{i}",
                              device_name=lambda i: "AMD Radeon RX 6800 XT", default_device=lambda: 1)
        probe = torch.ones((2, 2))
        with patch.object(worker.platform, "system", return_value="Windows"), patch.dict(sys.modules, {"torch_directml": dml}), patch("torch.ones", side_effect=[RuntimeError("DirectML driver error"), probe]), patch.object(worker, "emit"), self.assertLogs(level="ERROR"):
            devices = worker.directml_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["id"], "privateuseone:1")
        self.assertEqual(devices[0]["name"], "AMD Radeon RX 6800 XT")
        self.assertTrue(devices[0]["discrete"])
        self.assertIsNone(devices[0]["memory_bytes"])

    def test_directml_errors_are_distinct_from_bad_audio(self):
        for message in ("DirectML device lost", "Could not run aten::x on PrivateUse1", "privateuseone allocation failed", "out of memory", "Not enough GPU video memory", "Invalid argument (80070057)", "Allocation failed (8007000e)"):
            with self.subTest(message=message):
                self.assertTrue(worker.device_error(RuntimeError(message), "privateuseone:0"))
        for error in (RuntimeError("invalid audio"), OSError("DirectML file missing"), ValueError("out of memory")):
            self.assertFalse(worker.device_error(error, "privateuseone:0"))
        self.assertFalse(worker.device_error(RuntimeError("DirectML error"), "cpu"))

    def test_failed_gpu_model_transfer_reloads_on_cpu_and_reports_it(self):
        engine = worker.Engine.__new__(worker.Engine)
        engine.model = None
        engine.model_size = "small"
        engine.device = "privateuseone:0"
        engine.requested_device = "auto"
        engine.devices = [dict(id=engine.device, backend="DirectML (experimental)", name="RX 6800 XT"),
                          dict(id="cpu", backend="CPU", name="Ryzen")]
        engine.ready = Mock()
        gpu_model, cpu_model = Mock(), Mock()
        cpu_model._model.parameters.return_value = iter([SimpleNamespace(device=torch.device("cpu"))])
        with patch.object(worker, "get_weights", return_value=Path("model.safetensors")), patch("muscriptor.TranscriptionModel.load_model", side_effect=[gpu_model, cpu_model]) as load, patch.object(worker, "move_transcription_to_directml", side_effect=RuntimeError("DirectML out of memory")), patch.object(worker, "emit") as emit:
            engine.prepare()
        self.assertEqual(engine.device, "cpu")
        self.assertIs(engine.model, cpu_model)
        self.assertEqual(load.call_count, 2)
        self.assertTrue(all(call.kwargs["device"] == "cpu" for call in load.call_args_list))
        messages = [call.kwargs["message"] for call in emit.call_args_list if call.args == ("warning",)]
        self.assertIn("DirectML", messages[0])
        self.assertNotIn("NVIDIA", messages[0])


if __name__ == "__main__":
    unittest.main()
