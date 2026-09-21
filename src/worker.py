"""Private bridge to official MuScriptor, with an optional loopback-only web UI."""
from __future__ import annotations

import contextlib
import errno
import gc
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import re
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import warnings

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
# Use Hugging Face's resumable HTTP transport for byte progress without
# an additional chunk cache.
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
MODEL = "large"
REPO = "MuScriptor/muscriptor-large"
MODELS = ("small", "medium", "large")
# Conservative space allowances, including download overhead.
MODEL_SPACE = {"small": 1024**3, "medium": 2 * 1024**3, "large": 7 * 1024**3}
def application_directories(system=None):
    system = system or platform.system()
    if system == "Windows":
        support = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MuScriptor Local"
        return support, support / "Logs"
    if system == "Darwin":
        return Path.home() / "Library/Application Support/MuScriptor Local", Path.home() / "Library/Logs/MuScriptor Local"
    support = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "muscriptor-local"
    return support, support / "Logs"


SUPPORT, LOG_DIR = application_directories()
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
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
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


def write_unique(directory, name, data, extension=".mid"):
    """Publish a complete output atomically without ever overwriting an existing file."""
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".muscriptor-", delete=False) as f:
            temporary = Path(f.name)
            if isinstance(data, Path):
                with data.open("rb") as source:
                    shutil.copyfileobj(source, f)
            else:
                f.write(data)
            f.flush()
            os.fsync(f.fileno())
        # Close before linking/removing: Windows cannot unlink an open file.
        for index in range(10000):
            suffix = "" if index == 0 else f" ({index + 1})"
            target = directory / f"{name}{suffix}{extension}"
            try:
                os.link(temporary, target)
                return target
            except FileExistsError:
                continue
        raise UserError("Too many files have this name. Save to another folder.", "save")
    finally:
        if temporary is not None:
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


def supported_instruments():
    from muscriptor.tokenizer.mt3 import MT3_FULL_PLUS_GROUP_NAMES
    return list(MT3_FULL_PLUS_GROUP_NAMES)


def validate_options(instruments, quantize, create_ab):
    if instruments is not None and (not isinstance(instruments, list) or
            any(not isinstance(name, str) or name not in supported_instruments() for name in instruments)):
        raise UserError("Choose instruments from the supported instrument picker.", "options")
    if type(quantize) is not bool or type(create_ab) is not bool:
        raise UserError("Transcription options must be enabled or disabled.", "options")
    return list(dict.fromkeys(instruments)) if instruments else None


def fluidsynth_help():
    if platform.system() == "Windows":
        return "On Windows, install FluidSynth, add the folder containing fluidsynth.exe to your user PATH, then reopen the app."
    return "On macOS, install it with Homebrew: brew install fluidsynth. Then reopen the app."


def render_comparison(midi_data, audio, output, soundfont):
    """Use upstream rendering with an explicit local SF2; never fetch assets here."""
    from muscriptor.utils.auralization import auralize
    if not shutil.which("fluidsynth"):
        raise UserError("A/B audio needs FluidSynth. " + fluidsynth_help(), "render")
    if not soundfont or not Path(soundfont).expanduser().is_file():
        raise UserError("A/B audio needs a local .sf2 SoundFont. Choose SoundFont… in the app and select a downloaded file such as MuseScore_General.sf2.", "render")
    with tempfile.TemporaryDirectory(prefix="muscriptor-ab-") as folder:
        midi = Path(folder) / "performance.mid"
        wav = Path(folder) / "comparison.wav"
        midi.write_bytes(midi_data)
        auralize(midi_path=midi, original_audio_path=audio, output_path=wav,
                 soundfont_path=Path(soundfont).expanduser())
        try:
            return write_unique(output.parent, output.stem + "_AB", wav, ".wav")
        except OSError:
            return write_unique(SUPPORT / "Results", output.stem + "_AB", wav, ".wav")


def mps_error(exc):
    return isinstance(exc, (RuntimeError, NotImplementedError)) and any(
        word in str(exc).lower() for word in ("mps", "metal", "placeholder storage"))


def device_error(exc, device):
    if device == "mps":
        return mps_error(exc)
    if device.startswith("privateuseone:"):
        return isinstance(exc, (RuntimeError, NotImplementedError)) and any(
            word in str(exc).lower() for word in (
                "directml", "privateuseone", "privateuse1", "dml", "out of memory",
                "not enough memory", "gpu video memory", "unsupported data type",
                "80070057", "8007000e", "device removed",
                "cannot set version_counter for inference tensor"))
    return device.startswith("cuda") and isinstance(exc, (RuntimeError, NotImplementedError)) and any(
        word in str(exc).lower() for word in ("cuda", "cublas", "cudnn", "no kernel image", "out of memory"))


def directml_devices():
    """DirectML is optional and Windows-only; a broken driver must not block CPU."""
    if platform.system() != "Windows":
        return []
    try:
        import torch_directml
    except ImportError:
        return []
    except (OSError, RuntimeError):
        logging.exception("DirectML could not initialize")
        emit("warning", message="DirectML could not start. Update your AMD graphics driver and use Repair Dependencies. CPU is still available.")
        return []
    import torch
    devices = []
    try:
        for index in range(torch_directml.device_count()):
            try:
                device = torch_directml.device(index)
                # Force a small operation and readback, not just adapter enumeration.
                probe = torch.ones((2, 2), device=device)
                if not torch.equal((probe @ probe).cpu(), torch.full((2, 2), 2.0)):
                    raise RuntimeError("DirectML calculation check failed")
                name = torch_directml.device_name(index)
                devices.append(dict(id=str(device), name=name, backend="DirectML (experimental)",
                                    memory_bytes=None, memory_kind="GPU memory",
                                    discrete=bool(re.search(r"\b(RX|Arc|GeForce|Quadro)\b|Radeon Pro", name, re.I)),
                                    default=index == torch_directml.default_device()))
            except (RuntimeError, OSError):
                logging.exception("DirectML adapter %d is unavailable", index)
        if not devices:
            emit("warning", message="No working DirectML GPU was found. Update your graphics driver. CPU is still available.")
    except (RuntimeError, OSError):
        logging.exception("DirectML GPU discovery failed")
    return devices


def move_transcription_to_directml(model, device):
    """Keep official CPU conditioning (complex STFT) and accelerate the decoder.

    Safetensors is loaded on CPU first. Upstream's conditioners retain their CPU
    device attributes; only their small completed outputs cross to DirectML.
    No global torch patches or changes to the vendored engine are needed.
    """
    import torch
    from types import MethodType

    # The pinned upstream generator uses inference_mode. DirectML 0.2.5
    # cannot update version counters for its inference tensors during linear
    # projection. Replace that decorator on this instance only, preserving
    # no-gradient execution and context restoration at every generator yield.
    generate = type(model._model).generate.__wrapped__
    generate = torch.inference_mode(False)(torch.no_grad()(generate))
    model._model.generate = MethodType(generate, model._model)

    for name, module in model._model.named_children():
        if name != "condition_provider":
            module.to(device)

    def transfer_conditions(module, args, output):
        return {key: (condition.to(device), mask.to(device))
                for key, (condition, mask) in output.items()}

    model._model.condition_provider.register_forward_hook(transfer_conditions)
    model._device = device
    return model


def system_memory():
    try:
        if platform.system() == "Windows":
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong) for name in ("total", "available", "page", "page_available", "virtual", "virtual_available", "extended")]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            return status.total if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        return None


def device_inventory():
    import torch
    cpu = os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor() or platform.machine()
    if platform.system() == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except (ImportError, OSError):
            pass
    if platform.system() == "Darwin":
        try:
            cpu = subprocess.check_output(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        except (OSError, subprocess.SubprocessError):
            pass
    memory = system_memory()
    devices = []
    if torch.cuda.is_available():
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            devices.append(dict(id=f"cuda:{index}", name=properties.name, backend="NVIDIA CUDA",
                                memory_bytes=properties.total_memory, memory_kind="dedicated GPU memory"))
    if torch.backends.mps.is_available():
        devices.append(dict(id="mps", name=cpu, backend="Apple MPS", memory_bytes=memory, memory_kind="shared unified memory"))
    devices.extend(directml_devices())
    devices.append(dict(id="cpu", name=cpu, backend="CPU", memory_bytes=memory, memory_kind="system memory"))
    return devices


def choose_device(devices, requested="auto"):
    if requested == "auto":
        gpus = [device for device in devices if device["id"].startswith("cuda:")]
        if gpus:
            return max(gpus, key=lambda device: device["memory_bytes"] or 0)["id"]
        directml = [device for device in devices if device["id"].startswith("privateuseone:")]
        if directml:
            return max(directml, key=lambda device: (device.get("discrete", False), device.get("default", False)))["id"]
        return "mps" if any(device["id"] == "mps" for device in devices) else "cpu"
    if not any(device["id"] == requested for device in devices):
        raise UserError("That processor is not available. Choose Automatic or CPU.", "device")
    return requested


class Engine:
    def __init__(self, model=MODEL, device="auto"):
        import torch
        import imageio_ffmpeg
        import muscriptor
        import mido
        import soundfile
        if not Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file():
            raise UserError("The audio decoder is missing. Reinstall the app’s dependencies.", "dependencies")
        self.devices = device_inventory()
        self.requested_device = device
        try:
            self.device = choose_device(self.devices, device)
        except UserError:
            self.requested_device = "auto"
            self.device = choose_device(self.devices)
            emit("warning", message="The previously selected processor is unavailable. Automatic selection is being used.")
        self.model = None
        model_repo(model)
        self.model_size = model
        self.device_event()
        logging.info("Startup: torch=%s device=%s MuScriptor=%s", torch.__version__, self.device, model)

    def ready(self):
        from huggingface_hub import get_token
        cached = {size: cached_weights(size) is not None for size in MODELS}
        emit("ready", model=self.model_size, cached=cached[self.model_size],
             models=cached, directory=str(model_directory(self.model_size)),
             authenticated=bool(get_token()), instruments=supported_instruments())

    def select(self, model):
        model_repo(model)
        if model != self.model_size:
            import torch
            self.model = None
            gc.collect()
            self.clear_device_cache()
            self.model_size = model
            self.device = choose_device(self.devices, self.requested_device)
            self.device_event()
        self.ready()

    def device_event(self):
        device = next((item for item in self.devices if item["id"] == self.device), {"backend": "CPU", "name": "CPU"})
        memory = device.get("memory_bytes")
        detail = device["name"]
        if memory:
            detail += f" · {memory / 1024**3:.0f} GB {device['memory_kind']}"
        emit("backend", device=device["backend"], device_id=self.device, detail=detail,
             devices=self.devices, requested_device=self.requested_device)

    def clear_device_cache(self):
        import torch
        if self.device == "mps" and torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif self.device.startswith("cuda") and torch.cuda.is_available():
            with torch.cuda.device(self.device):
                torch.cuda.empty_cache()

    def select_device(self, requested):
        device = choose_device(self.devices, requested)
        self.model = None
        gc.collect()
        self.clear_device_cache()
        self.requested_device = requested
        self.device = device
        self.device_event()
        self.ready()

    def fallback(self):
        import torch
        self.model = None
        gc.collect()
        previous = self.device
        backend = next((item["backend"] for item in self.devices if item["id"] == previous), "GPU")
        try:
            self.clear_device_cache()
        except RuntimeError:
            logging.exception("GPU cache cleanup failed during CPU recovery")
        self.device = "cpu"
        self.device_event()
        emit("warning", message=f"{backend} could not complete this operation. Retrying locally on CPU; this will be slower. Try a smaller model to reduce GPU memory use.")

    def load(self):
        if self.model is not None:
            return
        from muscriptor import TranscriptionModel
        path = get_weights(self.model_size)
        emit("status", message=f"Loading MuScriptor {self.model_size.title()}…")
        if self.device.startswith("privateuseone:"):
            import torch
            self.model = TranscriptionModel.load_model(path, device="cpu")
            move_transcription_to_directml(self.model, torch.device(self.device))
            # Conditioning intentionally stays on CPU; verify decoder placement.
            actual = self.model._model.emb.weight.device
        else:
            self.model = TranscriptionModel.load_model(path, device=self.device)
            actual = next(self.model._model.parameters()).device
        logging.info("Loaded official %s: parameter device=%s", self.model_size, actual)
        if actual.type != self.device.split(":")[0] or (":" in self.device and actual.index != int(self.device.split(":")[1])):
            raise RuntimeError(f"Model did not load on the selected device ({self.device})")
        self.device_event()

    def prepare(self):
        try:
            self.load()
        except Exception as exc:
            if not device_error(exc, self.device):
                raise
            logging.exception("GPU model load failed")
            self.fallback()
            self.load()
        self.ready()

    def beat_grid(self, wav, *, allow_download=False):
        """Only explicit notation mode may fetch an uncached tempo helper."""
        import torch
        checkpoint = Path(torch.hub.get_dir()) / "checkpoints/beat_this-final0.ckpt"
        if not checkpoint.is_file() and not allow_download:
            logging.info("Optional tempo checkpoint is not cached; preserving note timing without a beat grid")
            return None
        try:
            return self.model.detect_beat_grid_for((wav, 16000), "best-effort")
        except Exception:
            logging.exception("Optional upstream tempo detection unavailable")
            return None

    def transcribe(self, source, destination=None, *, instruments=None, quantize=False, create_ab=False, soundfont=None):
        from muscriptor.events import ProgressEvent, NoteStartEvent
        from muscriptor.utils.audio import load_audio
        import mido
        import torch
        instruments = validate_options(instruments, quantize, create_ab)
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
                    for event in self.model.transcribe((wav, 16000), instruments=instruments):
                        if isinstance(event, ProgressEvent):
                            emit("progress", completed=event.completed, total=event.total)
                        else:
                            events.append(event)
                    break
                except Exception as exc:
                    if not device_error(exc, self.device):
                        raise
                    logging.exception("GPU transcription failed; restarting complete song on CPU")
                    events = []
                    self.fallback()
            emit("status", message="Writing MIDI…")
            # Match upstream transcribe_and_postprocess while retaining progress.
            # Tempo failure must not make a valid transcription unusable offline.
            grid = self.beat_grid(wav, allow_download=quantize)
            if grid is not None:
                grid = grid.with_onset_delay([ev.start_time for ev in events if isinstance(ev, NoteStartEvent)])
            quantized = quantize and grid is not None and grid.beat_subdivision is not None
            if quantize and not quantized:
                emit("warning", message="No usable beat subdivision was detected. Performance-timing MIDI was saved instead; try a recording with a steady beat. The tempo helper may need its initial download while online.")
            data = self.model.events_to_midi_bytes(iter(events), beat_grid=grid, quantize=quantize)
            midi = mido.MidiFile(file=io.BytesIO(data))
            output, needs_save = save_result(source, data, destination)
            logging.info("Complete: %s; tracks=%d duration=%.2f device=%s", output, len(midi.tracks), midi.length, self.device)
            ab_path = None
            if create_ab:
                emit("status", message="Creating A/B audio…")
                try:
                    # Upstream recommends performance timing for listening, even
                    # when the separately exported notation MIDI is quantized.
                    performance = self.model.events_to_midi_bytes(iter(events), beat_grid=grid, quantize=False) if quantize else data
                    ab_path = render_comparison(performance, audio, output, soundfont)
                except Exception as exc:
                    logging.exception("Optional A/B render failed; MIDI preserved")
                    detail = str(exc) if isinstance(exc, UserError) else "Check your local .sf2 SoundFont and free disk space. " + fluidsynth_help() + " Details are in the app’s logs."
                    emit("warning", message="Your MIDI was saved, but A/B audio could not be created. " + detail)
            emit("complete", path=str(output), needs_save=needs_save,
                 ab_path=str(ab_path) if ab_path else None, quantized=quantized)


def local_web_app(model, web_dir, origin):
    from muscriptor.server import create_app
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from starlette.responses import PlainTextResponse

    app = create_app(model, web_dir=web_dir)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])

    @app.middleware("http")
    async def same_origin(request, call_next):
        # Prevent unrelated websites from submitting work to the local engine.
        if request.headers.get("origin") not in (None, origin):
            return PlainTextResponse("Use the local web GUI opened by the app.", status_code=403)
        return await call_next(request)

    return app


def open_web_gui(engine):
    """Hand this worker/model to upstream's server until the desktop restarts it."""
    import uvicorn
    if os.name == "posix" and os.getpgrp() != os.getpid():
        os.setpgid(0, 0)
    web_dir = Path(__file__).resolve().parents[1] / "upstream/muscriptor/web_dist"
    if not (web_dir / "index.html").is_file():
        raise UserError("The bundled web GUI is missing. Install the latest app build.", "web_gui")
    if cached_weights(engine.model_size) is None:
        raise UserError("Download the selected model in the app first.", "web_gui")
    try:
        engine.load()
    except Exception as exc:
        if not device_error(exc, engine.device):
            raise
        engine.fallback()
        engine.load()
    # Bind before announcing the URL, so another service cannot claim the port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        app = local_web_app(engine.model, web_dir, origin)

        class DesktopServer(uvicorn.Server):
            def capture_signals(self):
                # Keep the worker's immediate SIGTERM cleanup on Mac. Returning
                # to desktop must release this model before another worker starts.
                return contextlib.nullcontext()

            async def startup(self, sockets=None):
                await super().startup(sockets=sockets)
                if self.started:
                    emit("web_ready", url=origin, model=engine.model_size)

        config = uvicorn.Config(app, host="127.0.0.1", log_config=None, access_log=False, timeout_graceful_shutdown=1)
        DesktopServer(config).run(sockets=[listener])
    # Do not resume native inference after an unexpected server shutdown.
    raise SystemExit(0)


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
            emit("warning", message="One GPU operation is running on CPU; transcription is continuing locally.")
    warnings.showwarning = warning
    try:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--model", choices=MODELS, default=MODEL)
        parser.add_argument("--device", default="auto")
        args = parser.parse_args()
        engine = Engine(args.model, args.device)
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
            elif action == "web_gui":
                open_web_gui(engine)
            elif action == "select_model":
                engine.select(command["model"])
            elif action == "select_device":
                engine.select_device(command["device"])
            elif action == "plan":
                source = Path(command["path"]).expanduser().resolve()
                directory = Path(command["directory"]).expanduser().resolve() if command.get("directory") else None
                emit("planned", path=str(planned_output(source, directory)))
            elif action == "transcribe":
                destination = Path(command["destination"]).expanduser().absolute() if command.get("destination") else None
                engine.transcribe(Path(command["path"]).expanduser().resolve(), destination,
                                  instruments=command.get("instruments"), quantize=command.get("quantize", False),
                                  create_ab=command.get("create_ab", False), soundfont=command.get("soundfont"))
            elif action == "quit":
                break
        except Exception as exc:
            report_error(exc)
        finally:
            command.clear()


if __name__ == "__main__":
    main()
