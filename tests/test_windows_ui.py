"""Interface tests: no downloads, real credentials, or GPU are needed."""
import os
import sys
os.environ.setdefault('QT_QPA_PLATFORM', 'windows' if sys.platform == 'win32' else 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PySide6.QtCore import QProcess, QSettings, QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QPalette, QPixmap, QMouseEvent, QKeyEvent
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
        self.window.receive(dict(type='ready', cached=True, authenticated=True, directory='C:/Models/large', instruments=['acoustic_piano', 'drums', 'electric_bass']))

    def tearDown(self):
        with patch.object(self.window, 'confirm_discard_timing', return_value=True):
            self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.temporary.cleanup()

    def test_late_messages_from_old_worker_are_ignored(self):
        old=Mock();self.window.worker=Mock()
        self.window.read_events(old)
        old.readAllStandardOutput.assert_not_called()
        self.window.worker.readAllStandardOutput.assert_not_called()
        self.window.worker=None

    def test_model_download_requirement_keeps_loaded_session_editable(self):
        self.window.has_session = True
        self.window.result = self.folder / 'saved.mid'
        self.window.receive(dict(type='ready', cached=False))
        self.assertFalse(self.window.options_widget.isHidden())
        self.assertTrue(self.window.reexport_button.isEnabled())
        self.window.receive(dict(type='session_loaded', timing={}))
        self.assertTrue(self.window.setup)  # Opening a session does not download a model.

    def test_return_from_web_restores_latest_session_without_stale_timing(self):
        self.window.has_session = True
        self.window.recovery_path = 'old.muscriptor'
        self.window.web_url = 'http://127.0.0.1:8767'
        self.window.tempo_bpm.setText('170')
        with patch.object(self.window, 'start'):
            self.window.return_to_desktop()
        self.assertFalse(self.window.has_session)
        with patch.object(self.window, 'send') as send:
            self.window.receive(dict(type='ready', cached=True, recovery_path='new.muscriptor'))
            self.assertEqual(send.call_args.args[0], dict(action='load_session',path='new.muscriptor'))
        self.assertIsNone(self.window.pending_timing)

    def test_engine_crash_restores_session_and_unapplied_timing_on_retry(self):
        self.window.has_session = True
        self.window.recovery_path = 'saved.muscriptor'
        self.window.tempo_bpm.setText('173')
        process=Mock();self.window.worker=process
        self.window.engine_stopped(process)
        self.assertFalse(self.window.has_session)
        with patch.object(self.window, 'send') as send:
            self.window.receive(dict(type='ready',cached=True,recovery_path='saved.muscriptor'))
            self.assertEqual(send.call_args.args[0]['action'],'load_session')
        self.window.receive(dict(type='session_loaded',timing={'bpm':120}))
        self.window.receive(dict(type='complete',path=str(self.folder/'restored.mid'),session=True))
        self.assertEqual(self.window.tempo_bpm.text(),'173')
        self.assertIsNone(self.window.pending_timing)

    def test_web_handoff_checks_unsaved_timing_before_replacing_context(self):
        with patch.object(self.window,'confirm_discard_timing',return_value=False), patch.object(self.window,'send') as send:
            self.window.open_web_gui()
        send.assert_not_called()

    def test_finish_control_waits_for_completed_section_and_sends_scoped_request(self):
        self.window.busy = True
        self.window.transcription_id = "active-run"
        self.window.receive(dict(type="progress", completed=0, total=4, completed_seconds=0, can_finish=False))
        self.assertTrue(self.window.finish_button.isHidden())
        self.window.receive(dict(type="progress", completed=1, total=4, completed_seconds=5, can_finish=True))
        self.assertFalse(self.window.finish_button.isHidden())
        with patch.object(self.window, "send") as send:
            self.window.finish_transcription(); self.window.finish_transcription()
            send.assert_called_once()
            self.assertEqual(send.call_args.args[0], {"action":"finish_transcription", "run_id":"active-run"})
        self.assertFalse(self.window.finish_button.isEnabled())
        self.window.receive(dict(type="complete", path=str(self.folder/'partial.mid'), partial=True, completed_seconds=5))
        self.assertTrue(self.window.finish_button.isHidden())
        self.assertIn("Partial MIDI saved", self.window.status.text())

    def test_session_menu_dispatch_and_processor_settings_busy_state(self):
        with patch.object(self.window, 'open_session') as opened:
            self.window.open_session_action.trigger()
            opened.assert_called_once_with()
            self.window.recovery_path = 'saved.muscriptor'
            self.window.refresh()
            self.window.recover_action.trigger()
            self.assertEqual(opened.call_args.args, ('saved.muscriptor',))
        self.window.show_app_info()
        self.app.processEvents()
        self.assertTrue(self.window.info_dialog.isVisible())
        self.assertTrue(self.window.device.isEnabled())
        self.window.busy = True
        self.window.refresh()
        self.assertFalse(self.window.device.isEnabled())
        self.assertFalse(self.window.open_session_action.isEnabled())
        self.window.info_dialog.close()

    def test_instrument_list_drag_keyboard_and_bounds(self):
        grip = self.window.instrument_resize_handle
        choices = self.window.instrument_choices
        def mouse(kind, y, button, buttons):
            event = QMouseEvent(kind, QPointF(5, 5), QPointF(100, y), button, buttons, Qt.NoModifier)
            self.app.sendEvent(grip, event)
        mouse(QEvent.MouseButtonPress, 100, Qt.LeftButton, Qt.LeftButton)
        mouse(QEvent.MouseMove, 165, Qt.NoButton, Qt.LeftButton)
        self.assertEqual(choices.height(), 165)
        mouse(QEvent.MouseButtonRelease, 165, Qt.LeftButton, Qt.NoButton)
        mouse(QEvent.MouseMove, 200, Qt.NoButton, Qt.NoButton)
        self.assertEqual(choices.height(), 165)
        self.app.sendEvent(grip, QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.NoModifier))
        self.assertEqual(choices.height(), 185)
        grip.resize_list(1000); self.assertEqual(choices.height(), 320)
        grip.resize_list(-100); self.assertEqual(choices.height(), 80)

    def test_windows_return_and_quit_stop_worker_when_taskkill_is_denied(self):
        # A real child verifies the QProcess-handle fallback, rather than
        # only asserting that a mocked termination method was called.
        for action in ('return_to_desktop', 'close'):
            with self.subTest(action=action):
                process = QProcess(self.window)
                process.start(sys.executable, ['-c', 'import time; time.sleep(60)'])
                self.assertTrue(process.waitForStarted(5000))
                self.window.worker = process
                self.window.web_url = 'http://127.0.0.1:8123'
                try:
                    with patch('WindowsApp.sys.platform', 'win32'), patch('WindowsApp.QProcess.execute', return_value=1), patch.object(self.window, 'start'):
                        getattr(self.window, action)()
                    self.assertEqual(process.state(), QProcess.NotRunning)
                finally:
                    process.kill()
                    process.waitForFinished(3000)
                    self.window.worker = None

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

    def test_cancel_stops_child_and_keeps_file_and_timing(self):
        process = QProcess(self.window)
        process.start(sys.executable, ['-c', 'import time; time.sleep(60)'])
        self.assertTrue(process.waitForStarted(5000))
        self.window.worker = process
        self.window.busy = True
        self.window.source = self.folder / 'recording.wav'
        self.window.tempo_bpm.setText('141')
        try:
            with patch.object(self.window, 'start') as restart:
                self.window.cancel_operation()
                restart.assert_called_once()
            self.assertEqual(process.state(), QProcess.NotRunning)
            self.assertEqual(self.window.source.name, 'recording.wav')
            self.assertEqual(self.window.tempo_bpm.text(), '141')
        finally:
            process.kill(); process.waitForFinished(3000)
            self.window.worker = None

    def test_cancel_timeout_keeps_retry_cancel_available_and_blocks_new_work(self):
        process = Mock(); process.waitForFinished.return_value = False
        self.window.worker = process; self.window.busy = True
        with patch('WindowsApp.QProcess.execute'), patch.object(self.window, 'start') as restart:
            self.window.cancel_operation()
            self.assertTrue(self.window.busy)
            self.assertFalse(self.window.cancel_button.isHidden())
            self.assertFalse(self.window.transcribe_button.isEnabled())
            restart.assert_not_called()
            process.waitForFinished.return_value = True
            self.window.cancel_operation()
            restart.assert_called_once()
        self.window.worker = None; self.window.busy = False

    def test_session_restores_numeric_subdivision_and_tempo_factor(self):
        self.window.restore_timing({'subdivision':4, 'factor':1.0, 'meter':'7/8'})
        self.assertEqual(self.window.tempo_subdivision.currentData(), '4')
        self.assertEqual(self.window.tempo_factor.currentData(), 1.0)
        self.assertEqual(self.window.tempo_meter.currentText(), '7/8')

    def test_loaded_session_can_export_without_original_path_or_model(self):
        self.window.receive(dict(type='session_loaded', name='Saved song', timing={'mode':'manual','bpm':93,'meter':'6/8'}))
        self.window.receive(dict(type='complete', path=str(self.folder/'restored.mid'), session=True))
        self.assertIsNone(self.window.source)
        self.assertEqual(self.window.tempo_bpm.text(), '93')
        self.assertEqual(self.window.tempo_meter.currentText(), '6/8')
        with patch.object(self.window, 'send') as send:
            self.window.apply_session()
            self.assertEqual(send.call_args.args[0]['action'], 'reexport_session')
        self.window.has_session = False  # No unsaved-change dialog during test cleanup.

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
        with patch('WindowsApp.sys.platform', 'win32'):
            self.window.receive(dict(type='backend', device='CPU', device_id='cpu', requested_device='auto', detail='Test Processor', devices=[dict(id='cpu', backend='CPU', name='Test Processor')]))
        self.assertIn('CPU', self.window.footer.text())
        self.assertNotIn('NVIDIA', self.window.footer.text())
        self.assertEqual(self.window.hardware.text().splitlines()[0], 'Test Processor')
        self.assertIn('No supported GPU is available', self.window.hardware.text())

    def test_directml_gpu_is_selectable_and_not_reported_as_cpu_only(self):
        with patch('WindowsApp.sys.platform', 'win32'):
            self.window.receive(dict(type='backend', device='DirectML (experimental)', device_id='privateuseone:0', requested_device='auto', detail='AMD Radeon RX 6800 XT', devices=[dict(id='privateuseone:0', backend='DirectML (experimental)', name='AMD Radeon RX 6800 XT'), dict(id='cpu', backend='CPU', name='Ryzen')]))
        self.assertIn('DirectML', self.window.footer.text())
        self.assertEqual(self.window.hardware.text(), 'AMD Radeon RX 6800 XT')
        with patch.object(self.window, 'send') as send:
            self.window.device.setCurrentIndex(self.window.device.findData('privateuseone:0'))
            self.assertEqual(send.call_args.args[0], dict(action='select_device', device='privateuseone:0'))

    def test_busy_locks_model_device_and_destination(self):
        self.window.busy = True
        self.window.refresh()
        for widget in (self.window.model, self.window.device, self.window.folder_button, self.window.audio_button):
            self.assertFalse(widget.isEnabled())

    def test_web_gui_reuses_worker_locks_desktop_and_reopens_same_url(self):
        with patch.object(self.window, 'send') as send:
            self.window.open_web_gui()
        self.assertEqual(send.call_args.args[0], {'action': 'web_gui'})
        with patch('WindowsApp.QDesktopServices.openUrl') as open_url:
            self.window.receive(dict(type='web_ready', url='http://127.0.0.1:8123'))
            self.window.open_web_gui()
            self.assertEqual(open_url.call_count, 2)
            self.assertEqual(open_url.call_args.args[0].toString(), 'http://127.0.0.1:8123')
        self.assertFalse(self.window.web_widget.isHidden())
        self.assertFalse(self.window.model_segments.isEnabled())
        self.assertFalse(self.window.device.isEnabled())
        self.assertTrue(self.window.audio_button.isHidden())
        self.assertTrue(self.window.web_button.isEnabled())
        with patch.object(self.window, 'start') as start:
            self.window.return_to_desktop()
            start.assert_called_once()
        self.assertIsNone(self.window.web_url)

    def test_web_gui_rejects_remote_address(self):
        with patch('WindowsApp.QDesktopServices.openUrl') as open_url:
            self.window.receive(dict(type='web_ready', url='https://example.com'))
        open_url.assert_not_called()
        self.assertIsNone(self.window.web_url)

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

    def test_segments_select_model_and_follow_busy_state(self):
        with patch.object(self.window, 'send'):
            self.window.model_buttons.button(1).click()
        self.window.refresh()
        self.assertEqual(self.window.model.currentData(), 'medium')
        self.assertTrue(self.window.model_buttons.button(1).isChecked())
        self.window.busy = True
        self.window.refresh()
        self.assertFalse(self.window.model_segments.isEnabled())
        self.assertFalse(self.window.options_widget.isEnabled())

    def test_search_add_remove_and_option_command(self):
        self.assertFalse(self.window.quantize.isChecked())
        self.assertFalse(self.window.create_ab.isChecked())
        self.window.instrument_search.setText('piano')
        self.assertEqual(self.window.instrument_layout.itemAt(0).widget().text(), 'Acoustic Piano')
        self.window.instrument_layout.itemAt(0).widget().click()
        self.window.add_instrument('drums')
        self.window.add_instrument('drums')
        self.assertEqual(self.window.selected_instruments, ['acoustic_piano', 'drums'])
        self.window.selected_layout.itemAt(0).widget().click()
        self.assertEqual(self.window.selected_instruments, ['drums'])
        self.window.quantize.setChecked(True)
        self.window.create_ab.setChecked(True)
        self.window.soundfont = self.folder / 'local.sf2'
        self.window.source = self.folder / 'audio.wav'
        self.window.destination = self.folder / 'audio.mid'
        with patch.object(self.window, 'send') as send:
            self.window.transcribe()
        command = send.call_args.args[0]
        self.assertEqual(command['instruments'], ['drums'])
        self.assertTrue(command['quantize'])
        self.assertTrue(command['create_ab'])
        self.assertEqual(command['soundfont'], str(self.window.soundfont))

    def test_tempo_is_independent_and_manual_options_are_disclosed(self):
        self.assertTrue(self.window.manual_timing_widget.isHidden())
        self.assertTrue(self.window.advanced_timing.isHidden())
        self.assertEqual(self.window.timing_options()['mode'], 'auto')
        self.assertFalse(self.window.timing_options()['quantize'])
        self.window.tempo_mode.setCurrentIndex(1)
        self.assertFalse(self.window.manual_timing_widget.isHidden())
        self.window.tempo_bpm.setText('80')
        self.window.tempo_meter.setCurrentText('6/8')
        self.window.tempo_anchors.setPlainText('0.5, 1\n2.5, 5')
        self.window.source = self.folder / 'audio.wav'
        self.window.destination = self.folder / 'audio.mid'
        with patch.object(self.window, 'send') as send:
            self.window.transcribe()
        timing = send.call_args.args[0]['timing']
        self.assertEqual((timing['bpm'], timing['meter']), ('80', '6/8'))
        self.assertNotIn('stretch', timing)
        self.assertFalse(timing['quantize'])
        self.window.receive(dict(type='complete', path='song.mid', timing_summary='80 BPM · dotted-quarter · 6/8'))
        self.assertIn('dotted-quarter', self.window.timing_summary.text())

    def test_completion_and_convert_another_reset_result_panels(self):
        self.window.receive(dict(type='complete', path='C:/MIDI/song.mid', ab_path='C:/MIDI/song_AB.wav'))
        self.assertFalse(self.window.complete_widget.isHidden())
        self.assertFalse(self.window.ab_widget.isHidden())
        self.assertFalse(self.window.options_widget.isHidden())
        self.assertFalse(self.window.reexport_button.isHidden())
        self.assertTrue(self.window.advanced_timing.isHidden())
        self.assertEqual(self.window.ab_path.text(), str(Path('C:/MIDI/song_AB.wav')))
        self.window.another()
        self.assertIsNone(self.window.ab_result)
        self.assertTrue(self.window.complete_widget.isHidden())
        self.assertTrue(self.window.ab_widget.isHidden())
        self.assertFalse(self.window.audio_button.isHidden())
        self.assertFalse(self.window.options_widget.isHidden())

    def test_warnings_accumulate_and_processor_settings_keep_selection(self):
        self.window.receive(dict(type='warning', message='Quantization unavailable'))
        self.window.receive(dict(type='warning', message='A/B unavailable'))
        self.assertIn('Quantization unavailable', self.window.warning.text())
        self.assertIn('A/B unavailable', self.window.warning.text())
        self.assertTrue(self.window.info_dialog.isHidden())
        self.window.show_app_info()
        self.assertTrue(self.window.device.isVisible())
        self.window.info_dialog.close()
        self.assertTrue(self.window.info_dialog.isHidden())
        self.assertEqual(self.window.device.currentData(), 'auto')

    def test_windows_reveal_selects_file_without_shell(self):
        path = self.folder / 'song with spaces.mid'
        with patch('WindowsApp.sys.platform', 'win32'), patch('WindowsApp.QProcess.startDetached') as reveal:
            self.window.reveal(path)
        reveal.assert_called_once_with('explorer.exe', ['/select,', str(path.resolve())])

    def test_offscreen_layout_preview(self):
        # Exercise real Qt layout at the Mac-sized default window, no engine.
        self.window.show()
        self.app.processEvents()
        self.assertGreaterEqual(self.window.centralWidget().viewport().width(), 500)
        self.assertLessEqual(self.window.model_segments.width(), self.window.centralWidget().viewport().width())
        # Long Windows paths must wrap inside the page, including at minimum size.
        self.window.model_path.setText('C:/Users/Example/AppData/Local/' + 'a-long-cache-directory-' * 8)
        self.window.resize(self.window.minimumWidth(), self.window.minimumHeight())
        self.app.processEvents()
        self.assertLessEqual(self.window.centralWidget().widget().width(), self.window.centralWidget().viewport().width())
        self.assertGreaterEqual(self.window.instrument_search.height(), self.window.instrument_search.fontMetrics().height() + 6)
        self.assertTrue(self.window.instrument_search.fontMetrics().inFont('A'), 'Preview fonts must render real text')
        content = self.window.centralWidget().widget()
        self.assertLessEqual(content.height(), max(self.window.centralWidget().viewport().height(), content.heightForWidth(content.width())) + 2)

    @unittest.skipUnless(os.environ.get('MUSCRIPTOR_UI_PREVIEW_DIR'), 'Optional visual review artifacts')
    def test_visual_review_states(self):
        original = self.app.palette()
        try:
            output = Path(os.environ['MUSCRIPTOR_UI_PREVIEW_DIR'])
            output.mkdir(parents=True, exist_ok=True)
            self.window.resources = Path(__file__).resolve().parents[1]
            for theme in ('dark', 'light'):
                palette = QPalette(original)
                palette.setColor(QPalette.Window, QColor('#1e2528' if theme == 'dark' else '#fafafa'))
                self.app.setPalette(palette)
                self.window.setPalette(palette)
                self.window.apply_theme()
                self.window.another()
                self.window.selected_instruments = []
                self.window.create_ab.setChecked(False)
                self.window.info_dialog.hide()
                self.window.receive(dict(type='backend', device='NVIDIA CUDA', detail='NVIDIA GeForce RTX Example · 16 GB dedicated GPU memory', devices=[dict(id='cuda:0', backend='NVIDIA CUDA', name='NVIDIA GeForce RTX Example')]))
                self.window.receive(dict(type='ready', cached=True, authenticated=True, directory='C:/Users/Example/.cache/huggingface/hub/models--MuScriptor--muscriptor-large', instruments=['acoustic_piano', 'electric_piano', 'chromatic_percussion', 'organ', 'guitar', 'bass', 'drums']))
                self.window.show()
                for state in ('ready', 'options', 'complete', 'setup', 'download'):
                    if state == 'options':
                        self.window.add_instrument('acoustic_piano')
                        self.window.add_instrument('drums')
                        self.window.create_ab.setChecked(True)
                        self.window.show_app_info()
                        self.window.source = Path('C:/Music/Example recording.wav')
                        self.window.destination = Path('C:/Music/Example recording_transcription.mid')
                        self.window.refresh()
                    elif state == 'complete':
                        self.window.receive(dict(type='complete', path='C:/Music/Example recording_transcription.mid', ab_path='C:/Music/Example recording_transcription_AB.wav'))
                    elif state == 'setup':
                        self.window.another()
                        self.window.receive(dict(type='ready', cached=False, authenticated=False, directory='C:/Users/Example/.cache/huggingface/hub/models--MuScriptor--muscriptor-large'))
                    elif state == 'download':
                        self.window.busy = True
                        self.window.receive(dict(type='download', completed=1200000000, total=2000000000, directory='C:/Users/Example/.cache/huggingface/hub/models--MuScriptor--muscriptor-large'))
                    self.app.processEvents()
                    self.app.processEvents()
                    for index in range(self.window.selected_layout.count()):
                        row = self.window.selected_layout.itemAt(index).widget()
                        self.assertGreaterEqual(row.height(), row.layout().sizeHint().height())
                    content = self.window.centralWidget().widget()
                    preview = QPixmap(content.size())
                    content.render(preview)
                    self.assertTrue(preview.save(str(output / f'{theme}-{state}.png')))
                    if state == 'options':
                        self.assertTrue(self.window.info_dialog.grab().save(str(output / f'{theme}-settings.png')))
                        self.window.info_dialog.hide()
        finally:
            self.app.setPalette(original)

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
