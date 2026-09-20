#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
export UV_PYTHON_INSTALL_DIR="$PWD/runtime/python"
export UV_CACHE_DIR="$PWD/runtime/uv-cache"
tools/uv python install --no-bin 3.12
if [[ ! -x .venv/bin/python ]]; then tools/uv venv --python 3.12 .venv; fi
tools/uv pip sync --python .venv/bin/python requirements.lock
tools/uv pip check --python .venv/bin/python
