"""Invalid audio is rejected before inference, on desktop and both HTTP APIs."""
import io
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import Mock
from unittest.mock import patch
import wave
import numpy as np
import soundfile as sf
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'upstream')]
from fastapi.testclient import TestClient
from muscriptor.server import create_app
from muscriptor.utils.audio import load_audio, read_audio


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

    def test_compressed_uploads_decode_by_content_including_m4a_and_aac(self):
        import imageio_ffmpeg
        from muscriptor.events import ProgressEvent
        from muscriptor.utils import rhythm
        from test_finish_transcription import midi_model
        model=midi_model()
        model.transcribe=lambda *args,**kw: iter([ProgressEvent(0,1),ProgressEvent(1,1)])
        with tempfile.TemporaryDirectory() as directory, TestClient(create_app(model)) as client:
            source=Path(directory)/'source.wav'
            source.write_bytes(pcm((np.sin(np.arange(16000)*.04)*8192).astype('<i2').tobytes()))
            for suffix,codec in [('m4a','aac'),('aac','aac'),('mp3','libmp3lame'),('flac','flac')]:
                path=Path(directory)/('encoded.'+suffix)
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(source),'-c:a',codec,str(path)],check=True)
                data=path.read_bytes()
                with self.subTest(suffix=suffix):
                    wav,sr=read_audio(io.BytesIO(data))
                    self.assertEqual(sr,16000);self.assertGreaterEqual(wav.shape[-1],16000)
                    with patch.object(rhythm,'detect',return_value=rhythm.Detection([],[])):
                        response=client.post('/transcribe',files={'file':('misnamed.wav',data)},data={'timing':'{"mode":"manual","bpm":120}'})
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertIn('transcription_complete',response.text)
