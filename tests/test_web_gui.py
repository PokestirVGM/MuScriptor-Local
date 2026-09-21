"""Real upstream HTTP routes with a fake model; no downloads or inference."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import worker
from fastapi.testclient import TestClient


class WebGUITests(unittest.TestCase):
    def test_bundled_upstream_page_api_and_local_origin(self):
        directory = Path(worker.__file__).resolve().parents[1] / 'upstream/muscriptor/web_dist'
        self.assertTrue((directory / 'index.html').is_file(), 'Build the bundled web GUI first')
        self.assertTrue((directory / 'THIRD_PARTY_LICENSES.txt').is_file())
        origin = 'http://127.0.0.1:8123'
        app = worker.local_web_app(Mock(), directory, origin)
        with TestClient(app, base_url=origin) as client:
            page = client.get('/')
            self.assertEqual(page.status_code, 200)
            self.assertIn('id="root"', page.text)
            self.assertNotIn('fonts.googleapis.com', page.text)
            self.assertEqual(client.get('/health').json(), {'status': 'ok'})
            self.assertIn('acoustic_piano', client.get('/instruments').json()['instruments'])
            self.assertEqual(client.get('/health', headers={'Origin': origin}).status_code, 200)
            self.assertEqual(client.post('/transcribe', headers={'Origin': 'https://unrelated.example'}).status_code, 403)
            self.assertEqual(client.get('/health', headers={'Host': 'unrelated.example'}).status_code, 400)
            asset = next((directory / 'assets').glob('*.js')).name
            self.assertEqual(client.get('/assets/' + asset).status_code, 200)

    def test_missing_model_does_not_download_or_start_server(self):
        engine = Mock(model_size='small')
        with patch.object(worker, 'cached_weights', return_value=None):
            with self.assertRaisesRegex(worker.UserError, 'Download the selected model'):
                worker.open_web_gui(engine)
        engine.load.assert_not_called()

    def test_real_server_readiness_and_process_cleanup(self):
        # Exercise the actual server/socket lifecycle without loading a checkpoint.
        source = """
import sys
from unittest.mock import Mock
sys.path.insert(0, 'src')
import worker
worker.cached_weights = lambda _: True
worker.open_web_gui(Mock(model_size='small', device='cpu'))
"""
        with tempfile.TemporaryFile(mode='w+b') as errors:
            process = subprocess.Popen([sys.executable, '-u', '-c', source], cwd=Path(worker.__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=errors, text=True)
            events = []
            ready = threading.Event()
            def read_events():
                for line in process.stdout:
                    event = json.loads(line)
                    if event.get('type') == 'web_ready':
                        events.append(event)
                        ready.set()
            reader = threading.Thread(target=read_events, daemon=True)
            reader.start()
            try:
                self.assertTrue(ready.wait(45), 'Local server did not announce readiness')
                url = events[0]['url']
                self.assertTrue(url.startswith('http://127.0.0.1:'))
                with urlopen(url + '/health', timeout=5) as response:
                    self.assertEqual(json.load(response), {'status': 'ok'})
                port = int(url.rsplit(':', 1)[1])
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                reader.join(timeout=3)
                process.stdout.close()
            with socket.socket() as probe:
                self.assertNotEqual(probe.connect_ex(('127.0.0.1', port)), 0)


if __name__ == '__main__':
    unittest.main()
