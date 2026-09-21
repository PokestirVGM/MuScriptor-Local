"""Invalid audio is rejected before inference, on desktop and both HTTP APIs."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import wave
import numpy as np
import soundfile as sf
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'upstream')]
from fastapi.testclient import TestClient
from muscriptor.server import create_app
from muscriptor.utils.audio import load_audio


def pcm(samples=b'', channels=1):
    out=io.BytesIO()
    with wave.open(out,'wb') as wav:
        wav.setnchannels(channels);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(samples)
    return out.getvalue()


def float_wav(samples):
    out=io.BytesIO();sf.write(out,np.asarray(samples,dtype=np.float32),16000,format='WAV',subtype='FLOAT');return out.getvalue()


class AudioValidationTests(unittest.TestCase):
    def invalid_files(self):
        return {'empty.wav':pcm(),'nan.wav':float_wav([0,float('nan'),0]),
                'infinite.wav':float_wav([0,float('inf'),0]),
                'truncated.wav':pcm(b'\x01\x02\x03\x04',2)[:-1],
                'corrupt.wav':b'not audio'}

    def test_invalid_web_uploads_are_client_errors_without_inference(self):
        model=Mock()
        with TestClient(create_app(model),raise_server_exceptions=False) as client:
            for route in ('/transcribe','/transcribe/midi'):
                for name,data in self.invalid_files().items():
                    with self.subTest(route=route,name=name):
                        response=client.post(route,files={'file':(name,data,'audio/wav')})
                        self.assertEqual(response.status_code,400,response.text)
                        self.assertIn('audio',response.json()['detail'].lower())
            self.assertEqual(client.get('/health').status_code,200)
        model.transcribe.assert_not_called()

    def test_invalid_desktop_audio_is_rejected_before_resampling(self):
        with tempfile.TemporaryDirectory() as directory:
            for name,data in self.invalid_files().items():
                path=Path(directory)/name;path.write_bytes(data)
                with self.subTest(name=name),self.assertRaises((ValueError,RuntimeError,wave.Error)):
                    load_audio(path)

    def test_valid_pcm_stereo_and_float_formats_still_load(self):
        with tempfile.TemporaryDirectory() as directory:
            for name,data in [('stereo.wav',pcm(np.array([[16384,-8192],[0,16384]],dtype='<i2').tobytes(),2)),
                              ('float.wav',float_wav([.125,.25]))]:
                path=Path(directory)/name;path.write_bytes(data)
                decoded=load_audio(path)
                self.assertEqual(tuple(decoded.shape),(1,2))
                np.testing.assert_allclose(decoded.numpy(),[[.125,.25]],atol=1e-7)
