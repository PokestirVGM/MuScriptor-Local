"""Private JSON-lines bridge to unmodified official MuScriptor. No network server."""
from __future__ import annotations

import contextlib
import errno
import gc
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import warnings

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
# Use Hugging Face's resumable HTTP transport. Xet failed on this Mac's CDN
# connection; HTTP also exposes exact byte progress without an extra chunk cache.
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
MODEL = "large"
REPO = "MuScriptor/muscriptor-large"
MODELS = ("small", "medium", "large")
# Conservative space allowances, including download overhead.
MODEL_SPACE = {"small": 1024**3, "medium": 2 * 1024**3, "large": 7 * 1024**3}
SUPPORT = Path.home() / "Library/Application Support/MuScriptor Local"
LOG_DIR = Path.home() / "Library/Logs/MuScriptor Local"
protocol = sys.stdout


def emit(kind, **fields):
    protocol.write(json.dumps({"type": kind, **fields}) + "\n")
    protocol.flush()


class UserError(Exception):
    def __init__(self, message, code="error"):
        super().__init__(message)
        self.code = code


def model_repo(model):
    if model not in MODELS:
        raise UserError("Choose Small, Medium, or Large.", "model")
    return f"MuScriptor/muscriptor-{model}"


def model_directory(model):
    from huggingface_hub.constants import HF_HUB_CACHE
    return Path(HF_HUB_CACHE).expanduser().resolve() / ("models--" + model_repo(model).replace("/", "--"))


def cached_weights(model=MODEL):
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import LocalEntryNotFoundError
    try:
        repo = model_repo(model)
        config = hf_hub_download(repo, "config.json", local_files_only=True)
        weights = hf_hub_download(repo, "model.safetensors", local_files_only=True)
        # Both files must share a snapshot: upstream reads config beside weights.
        if Path(config).parent == Path(weights).parent:
            return Path(weights)
    except LocalEntryNotFoundError:
        pass
    return None


def require_space(path, amount):
    path = Path(path)
    while not path.exists():
        path = path.parent
    if shutil.disk_usage(path).free < amount:
        raise UserError("There isn’t enough free disk space. Free up some space and try again.", "disk")


def get_weights(model=MODEL):
    cached = cached_weights(model)
    if cached:
        return cached
    from huggingface_hub import hf_hub_download
    from huggingface_hub.constants import HF_HUB_CACHE
    from tqdm.auto import tqdm
    class DownloadProgress(tqdm):
        def __init__(self, *args, **kwargs):
            self.last_report = 0.0
            kwargs["disable"] = False
            super().__init__(*args, **kwargs)

        def display(self, *args, **kwargs):
            now = time.monotonic()
            if self.total and (now - self.last_report >= 0.25 or self.n >= self.total):
                self.last_report = now
                emit("download", model=model, directory=str(model_directory(model)), completed=self.n, total=self.total)
    require_space(HF_HUB_CACHE, MODEL_SPACE[model])
    emit("status", message=f"Downloading MuScriptor {model.title()}… This only happens once.")
    config = Path(hf_hub_download(model_repo(model), "config.json"))
    # Keep config and weights on the exact same upstream revision.
    return Path(hf_hub_download(model_repo(model), "model.safetensors", revision=config.parent.name, tqdm_class=DownloadProgress))


@contextlib.contextmanager
def decoded_audio(source):
    """Preserve rate/channels; upstream performs its own mono/16 kHz conversion."""
    import soundfile as sf
    if not source.is_file():
        raise UserError("That audio file is no longer available. Choose it again.", "audio")
    try:
        info = sf.info(str(source))
        if info.frames <= 0:
            raise UserError("This audio file is empty.", "audio")
    except (sf.LibsndfileError, RuntimeError):
        import imageio_ffmpeg
        emit("status", message="Preparing audio…")
        require_space(tempfile.gettempdir(), 256 * 1024**2)
        with tempfile.TemporaryDirectory(prefix="muscriptor-local-") as folder:
            wav = Path(folder) / "decoded.wav"
            decoder = subprocess.Popen(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-v", "error", "-xerror",
                 "-i", str(source), "-map", "0:a:0", "-vn", "-c:a", "pcm_s24le", "-y", str(wav)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            try:
                _, stderr = decoder.communicate()
            except BaseException:
                decoder.terminate()
                try:
                    decoder.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    decoder.kill()
                    decoder.wait()
                raise
            if decoder.returncode:
                detail = stderr.decode(errors="replace")
                logging.error("Audio decoder: %s", detail)
                if "No space left" in detail:
                    raise UserError("There isn’t enough space to decode this audio. Free some disk space and retry.", "disk")
                raise UserError("This file couldn’t be decoded. It may be damaged, protected, or not a supported audio file.", "audio")
            if sf.info(str(wav)).frames <= 0:
                raise UserError("This file contains no audio.", "audio")
            yield wav
    else:
        yield source


def write_unique(directory, name, data):
    """Publish complete MIDI atomically without ever overwriting an existing file."""
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".muscriptor-", delete=False) as f:
        temporary = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            for index in range(10000):
                suffix = "" if index == 0 else f" ({index + 1})"
                target = directory / f"{name}{suffix}.mid"
                try:
                    os.link(temporary, target)
                    return target
                except FileExistsError:
                    continue
            raise UserError("Too many files have this name. Save to another folder.", "save")
        finally:
            temporary.unlink(missing_ok=True)


def planned_output(source, directory=None):
    if not source.is_file():
        raise UserError("That audio file is no longer available. Choose it again.", "audio")
    folder = directory if directory is not None else source.parent
    if not folder.is_dir() or not os.access(folder, os.W_OK):
        folder = SUPPORT / "Results"
        emit("warning", message="That folder isn’t writable. The MIDI will be kept in the app’s Results folder; you can choose another folder.")
    name = source.stem + "_transcription"
    for index in range(10000):
        suffix = "" if index == 0 else f" ({index + 1})"
        path = folder / f"{name}{suffix}.mid"
        if not os.path.lexists(path):
            return path
    raise UserError("Too many files have this name. Choose another folder.", "save")


def save_result(source, data, destination=None):
    destination = destination if destination is not None else source.with_name(source.stem + "_transcription.mid")
    name = destination.stem
    try:
        return write_unique(destination.parent, name, data), False
    except OSError as exc:
        logging.info("Saving to requested folder unavailable: %s", exc)
        output = write_unique(SUPPORT / "Results", name, data)
        emit("warning", message="The selected folder couldn’t be used. Your MIDI was kept in the app’s Results folder; choose where to save a copy.")
        return output, True


def mps_error(exc):
    return isinstance(exc, (RuntimeError, NotImplementedError)) and any(
        word in str(exc).lower() for word in ("mps", "metal", "placeholder storage"))


class Engine:
    def __init__(self, model=MODEL):
        import torch
        import imageio_ffmpeg
        import muscriptor
        import mido
        import soundfile
        if not Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file():
            raise UserError("The audio decoder is missing. Reinstall the app’s dependencies.", "dependencies")
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.model = None
        model_repo(model)
        self.model_size = model
        self.device_event()
        logging.info("Startup: torch=%s MPS=%s MuScriptor=%s", torch.__version__, self.device, model)

    def ready(self):
        from huggingface_hub import get_token
        cached = {size: cached_weights(size) is not None for size in MODELS}
        emit("ready", model=self.model_size, cached=cached[self.model_size],
             models=cached, directory=str(model_directory(self.model_size)),
             authenticated=bool(get_token()))

    def select(self, model):
        model_repo(model)
        if model != self.model_size:
            import torch
            self.model = None
            gc.collect()
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
            self.model_size = model
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
            self.device_event()
        self.ready()

    def device_event(self):
        emit("backend", device="Apple MPS" if self.device == "mps" else "CPU")

    def fallback(self):
        import torch
        self.model = None
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        self.device = "cpu"
        self.device_event()
        emit("warning", message="Apple MPS could not complete this operation. Retrying locally on CPU; this will be slower.")

    def load(self):
        if self.model is not None:
            return
        from muscriptor import TranscriptionModel
        path = get_weights(self.model_size)
        emit("status", message=f"Loading MuScriptor {self.model_size.title()}…")
        self.model = TranscriptionModel.load_model(path, device=self.device)
        actual = next(self.model._model.parameters()).device
        logging.info("Loaded official %s: parameter device=%s", self.model_size, actual)
        if actual.type != self.device:
            raise RuntimeError("Model did not load on the selected device")
        self.device_event()

    def prepare(self):
        try:
            self.load()
        except Exception as exc:
            if self.device != "mps" or not mps_error(exc):
                raise
            logging.exception("MPS load failed")
            self.fallback()
            self.load()
        self.ready()

    def transcribe(self, source, destination=None):
        from muscriptor.events import ProgressEvent
        from muscriptor.utils.audio import load_audio
        import mido
        import torch
        with decoded_audio(source) as audio:
            emit("status", message="Reading audio…")
            try:
                wav = load_audio(audio)  # upstream mono and 16 kHz, exactly once
            except (ValueError, RuntimeError, EOFError) as exc:
                raise UserError("This audio file could not be read. It may be damaged.", "audio") from exc
            if wav.numel() == 0 or not torch.isfinite(wav).all():
                raise UserError("This audio file is empty or contains invalid samples.", "audio")
            while True:
                try:
                    self.load()
                    emit("status", message="Transcribing…")
                    events = []
                    for event in self.model.transcribe((wav, 16000)):
                        if isinstance(event, ProgressEvent):
                            emit("progress", completed=event.completed, total=event.total)
                        else:
                            events.append(event)
                    break
                except Exception as exc:
                    if self.device != "mps" or not mps_error(exc):
                        raise
                    logging.exception("MPS transcription failed; restarting complete song on CPU")
                    events = []
                    self.fallback()
            emit("status", message="Writing MIDI…")
            # Standard upstream MIDI postprocessing; never quantize. Optional
            # tempo failure must not make a valid transcription unusable offline.
            try:
                grid = self.model.detect_beat_grid_for((wav, 16000), "best-effort")
            except Exception:
                logging.exception("Optional upstream tempo detection unavailable")
                grid = None
            data = self.model.events_to_midi_bytes(iter(events), beat_grid=grid, quantize=False)
            midi = mido.MidiFile(file=io.BytesIO(data))
            output, needs_save = save_result(source, data, destination)
            logging.info("Complete: %s; tracks=%d duration=%.2f device=%s", output, len(midi.tracks), midi.length, self.device)
            emit("complete", path=str(output), needs_save=needs_save)


def report_error(exc):
    if isinstance(exc, UserError):
        emit("error", message=str(exc), code=exc.code)
        return
    from huggingface_hub.errors import GatedRepoError, HfHubHTTPError, LocalEntryNotFoundError
    logging.exception("Operation failed")
    if isinstance(exc, GatedRepoError) or (isinstance(exc, HfHubHTTPError) and exc.response.status_code in (401, 403)):
        emit("error", code="auth", message="Hugging Face authorization isn’t complete. Accept the selected model’s terms, then connect a read token from that same account.")
    elif isinstance(exc, LocalEntryNotFoundError) or any(x in str(exc).lower() for x in ("connection", "resolve host", "offline", "network", "download", "cas client", "request middleware")):
        emit("error", code="model", message="The model isn’t cached yet and couldn’t be downloaded. Connect to the Internet and try again.")
    elif isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        emit("error", code="disk", message="There isn’t enough free disk space. Free some space and try again.")
    elif isinstance(exc, (MemoryError,)) or "out of memory" in str(exc).lower():
        emit("error", code="memory", message="There isn’t enough available memory. Close other large apps and try again.")
    else:
        emit("error", code="engine", message="MuScriptor couldn’t finish. Try again or choose another audio file. Details are saved in the app’s logs.")


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    SUPPORT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(LOG_DIR / "engine.log", maxBytes=2_000_000, backupCount=3)], format="%(asctime)s %(levelname)s %(message)s")
    class PrivateFormatter(logging.Formatter):
        def format(self, record):
            return re.sub(r'(https?://[^\s?]+)\?[^\s]+', r'\1?[redacted]', super().format(record))
    for handler in logging.getLogger().handlers:
        handler.setFormatter(PrivateFormatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Upstream diagnostic prints belong in native-launcher stderr, not protocol.
    sys.stdout = sys.stderr
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    original_warning = warnings.showwarning
    def warning(message, *args, **kwargs):
        original_warning(message, *args, **kwargs)
        if "fall back" in str(message).lower() and "cpu" in str(message).lower():
            emit("warning", message="One Apple MPS operation is running on CPU; transcription is continuing locally.")
    warnings.showwarning = warning
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--model", choices=MODELS, default=MODEL)
        engine = Engine(parser.parse_args().model)
        from huggingface_hub import get_token, login
        engine.ready()
    except Exception:
        logging.exception("Startup failed")
        emit("error", code="dependencies", message="The Python environment could not start. Use Repair Dependencies in the app menu.")
        return
    for line in sys.stdin:
        command = {}
        try:
            command = json.loads(line)
            action = command.get("action")
            if action == "auth":
                emit("status", message="Connecting to Hugging Face…")
                token = command.pop("token", "").strip()
                # Never log credentials or pass them in command-line arguments.
                try:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        login(token=token, add_to_git_credential=False)
                except Exception:
                    raise UserError("This token could not be verified. Check your read token and Internet connection.", "auth") from None
                finally:
                    token = None
                from huggingface_hub.constants import HF_TOKEN_PATH, HF_STORED_TOKENS_PATH
                for path in (HF_TOKEN_PATH, HF_STORED_TOKENS_PATH):
                    if Path(path).exists():
                        Path(path).chmod(0o600)
                emit("authenticated")
                engine.prepare()
            elif action == "prepare":
                engine.prepare()
            elif action == "select_model":
                engine.select(command["model"])
            elif action == "plan":
                source = Path(command["path"]).expanduser().resolve()
                directory = Path(command["directory"]).expanduser().resolve() if command.get("directory") else None
                emit("planned", path=str(planned_output(source, directory)))
            elif action == "transcribe":
                destination = Path(command["destination"]).expanduser().absolute() if command.get("destination") else None
                engine.transcribe(Path(command["path"]).expanduser().resolve(), destination)
            elif action == "quit":
                break
        except Exception as exc:
            report_error(exc)
        finally:
            command.clear()


if __name__ == "__main__":
    main()
