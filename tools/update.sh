#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
export UV_CACHE_DIR="$PWD/runtime/uv-cache"
if /usr/bin/pgrep -f 'MuScriptor Local.app/Contents/MacOS/MuScriptor Local' >/dev/null; then
  echo 'Quit MuScriptor Local before updating.'
  exit 1
fi
.venv/bin/python tools/apply-engine-patches.py --reverse
# Reapply the extension on failures, preserving the pinned wrapper behavior.
trap '.venv/bin/python tools/apply-engine-patches.py' EXIT
git -C upstream fetch origin main
git -C upstream merge --ff-only origin/main
.venv/bin/python tools/apply-engine-patches.py
trap - EXIT
tools/uv pip install --python .venv/bin/python --upgrade ./upstream imageio-ffmpeg
tools/uv pip check --python .venv/bin/python
.venv/bin/python -c 'from muscriptor import TranscriptionModel; assert hasattr(TranscriptionModel, "events_to_midi_bytes"); assert hasattr(TranscriptionModel, "transcribe"); import imageio_ffmpeg; print("MuScriptor API available")'
tools/uv pip freeze --python .venv/bin/python > requirements.lock
.venv/bin/python - <<'PY'
from pathlib import Path
p = Path('requirements.lock')
p.write_text('\n'.join('./upstream' if line.startswith('muscriptor @') else line for line in p.read_text().splitlines()) + '\n')
PY
git -C upstream rev-parse HEAD > upstream-revision.txt
echo 'MuScriptor updated. Model weights remain cached. Open MuScriptor Local normally.'
