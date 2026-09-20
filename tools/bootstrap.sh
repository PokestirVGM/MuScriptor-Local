#!/bin/zsh
# Bundled in the portable app. Only installs into the supplied private folder.
set -euo pipefail
ROOT="$1"
RESOURCES="${0:A:h}"
mkdir -p "$ROOT/tools" "$ROOT/runtime" "$ROOT/src"
if [[ ! -x "$ROOT/tools/uv" ]]; then
  ARCHIVE=$(mktemp -t muscriptor-uv)
  trap 'rm -f "$ARCHIVE"' EXIT
  /usr/bin/curl --fail --location --retry 3 'https://github.com/astral-sh/uv/releases/download/0.12.17/uv-aarch64-apple-darwin.tar.gz' -o "$ARCHIVE"
  /usr/bin/tar -xzf "$ARCHIVE" --strip-components=1 -C "$ROOT/tools" uv-aarch64-apple-darwin/uv
fi
cp "$RESOURCES/engine/worker.py" "$ROOT/src/worker.py"
cp "$RESOURCES/engine/requirements.lock" "$ROOT/requirements.lock"
cp "$RESOURCES/engine/upstream-revision.txt" "$ROOT/upstream-revision.txt"
/usr/bin/ditto "$RESOURCES/engine/upstream" "$ROOT/upstream"
export UV_PYTHON_INSTALL_DIR="$ROOT/runtime/python"
export UV_CACHE_DIR="$ROOT/runtime/uv-cache"
cd "$ROOT"
tools/uv python install --no-bin 3.12
if [[ ! -x .venv/bin/python ]]; then tools/uv venv --python 3.12 .venv; fi
tools/uv pip sync --python .venv/bin/python requirements.lock
tools/uv pip check --python .venv/bin/python
# MuScriptor's standard MIDI tempo helper. Transcription also has upstream's
# supported no-grid fallback if this optional download is unavailable.
.venv/bin/python -c 'from beat_this.inference import load_model; load_model("final0")' || true
tools/uv cache clean
echo 'Local environment is ready.'
