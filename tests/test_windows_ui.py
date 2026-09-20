"""Headless interface tests: no downloads, real credentials, or GPU are needed."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from WindowsApp import MainWindow


class WindowsUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.settings = QSettings(str(self.folder / 'settings.ini'), QSettings.IniFormat)
        self.window = MainWindow(root=self.folder, autostart=False, settings=self.settings)
        self.window.receive(dict(type='ready', cached=True, authenticated=True, directory='C:/Models/large'))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.temporary.cleanup()

    def test_audio_is_staged_without_transcribing(self):
        source = self.folder / 'song.wav'
        source.write_bytes(b'test fixture')
        with patch.object(self.window, 'send') as send:
            self.window.stage(source)
            self.assertEqual(send.call_args.args[0], dict(action='plan', path=str(source)))
            self.assertIsNone(self.window.destination)
            destination = self.folder / 'chosen folder/song_transcription.mid'
            self.window.receive(dict(type='planned', path=str(destination)))
            self.assertEqual(self.window.output_path.text(), str(destination))
            self.window.transcribe()
            self.assertEqual(send.call_args.args[0]['destination'], str(destination))
            self.assertEqual(send.call_args.args[0]['action'], 'transcribe')

    def test_model_switch_is_remembered_and_does_not_download(self):
        with patch.object(self.window, 'send') as send:
            self.window.model.setCurrentIndex(0)
            self.assertEqual(self.settings.value('model'), 'small')
            self.assertEqual(send.call_args.args[0], dict(action='select_model', model='small'))
        self.window.receive(dict(type='ready', cached=False, authenticated=True, directory='C:/Models/small'))
        self.assertTrue(self.window.setup)
        self.assertEqual(self.window.model_path.text(), 'C:/Models/small')
        self.assertTrue(self.window.model.isEnabled())
        self.assertFalse(self.window.transcribe_button.isEnabled())

    def test_gpu_name_memory_selection_and_cpu_fallback(self):
        self.window.receive(dict(type='backend', device='NVIDIA CUDA', device_id='cuda:1', requested_device='auto', detail='NVIDIA RTX Test · 24 GB dedicated GPU memory', devices=[dict(id='cuda:1', backend='NVIDIA CUDA', name='NVIDIA RTX Test'), dict(id='cpu', backend='CPU', name='Test Processor')]))
        self.assertIn('24 GB', self.window.hardware.text())
        self.assertEqual(self.window.device.count(), 3)
        with patch.object(self.window, 'send') as send:
            self.window.device.setCurrentIndex(self.window.device.findData('cpu'))
            self.assertEqual(send.call_args.args[0], dict(action='select_device', device='cpu'))
        self.window.receive(dict(type='backend', device='CPU', device_id='cpu', requested_device='auto', detail='Test Processor', devices=[dict(id='cpu', backend='CPU', name='Test Processor')]))
        self.assertIn('Using CPU', self.window.hardware.text())
        self.assertNotIn('Using NVIDIA', self.window.hardware.text())

    def test_busy_locks_model_device_and_destination(self):
        self.window.busy = True
        self.window.refresh()
        for widget in (self.window.model, self.window.device, self.window.folder_button, self.window.audio_button):
            self.assertFalse(widget.isEnabled())

    def test_auth_error_allows_token_retry_and_model_switch(self):
        self.window.receive(dict(type='error', code='auth', message='Accept model terms'))
        self.assertFalse(self.window.authenticated)
        self.assertTrue(self.window.setup)
        self.assertFalse(self.window.busy)
        self.assertTrue(self.window.model.isEnabled())

    def test_completion_shows_actual_collision_adjusted_path(self):
        self.window.receive(dict(type='complete', path='C:/MIDI/song (2).mid', needs_save=False))
        self.assertEqual(self.window.output_path.text(), str(Path('C:/MIDI/song (2).mid')))
        self.assertEqual(self.window.status.text(), 'Transcription complete.')

    def test_save_cancel_keeps_original_result(self):
        original = self.folder / 'song.mid'
        original.write_bytes(b'midi')
        self.window.result = original
        with patch('WindowsApp.QFileDialog.getSaveFileName', return_value=('', '')):
            self.window.save_copy()
        self.assertEqual(self.window.result, original)
        self.assertEqual(original.read_bytes(), b'midi')

    def test_dependency_error_retry_repairs_incomplete_environment(self):
        self.window.receive(dict(type='error', code='dependencies', message='Incomplete engine'))
        self.assertEqual(self.window.status.text(), 'Action needed')
        with patch.object(self.window, 'repair') as repair, patch.object(self.window, 'start') as start:
            self.window.retry()
        repair.assert_called_once()
        start.assert_not_called()

    def test_setup_failure_does_not_leave_installing_status(self):
        self.window.support = self.folder
        self.window.status.setText('Installing private Python…')
        self.window.setup_finished(1)
        self.assertEqual(self.window.status.text(), 'Action needed')
        self.assertIn('Try Again', self.window.error.text())
        self.assertFalse(self.window.busy)


if __name__ == '__main__':
    unittest.main()
