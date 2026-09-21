#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
.venv/bin/python tools/build-web.py
APP="$PWD/build/Current Build.noindex/MuScriptor Local.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" build/module-cache
cp assets/muscriptor.icns "$APP/Contents/Resources/MuScriptor.icns"
cp assets/muscriptor-header-dark.png assets/muscriptor-header-light.png "$APP/Contents/Resources/"
/usr/bin/swiftc -O -target arm64-apple-macosx14.0 -module-cache-path "$PWD/build/module-cache" src/App.swift -o "$APP/Contents/MacOS/MuScriptor Local" -framework AppKit -framework SwiftUI
mkdir -p "$APP/Contents/Resources/engine/upstream"
cp src/engine_install.py "$APP/Contents/Resources/engine_install.py"
cp tools/bootstrap.sh "$APP/Contents/Resources/bootstrap.sh"
cp src/worker.py requirements.lock upstream-revision.txt "$APP/Contents/Resources/engine/"
ditto upstream/muscriptor "$APP/Contents/Resources/engine/upstream/muscriptor"
cp upstream/pyproject.toml upstream/README.md upstream/LICENSE "$APP/Contents/Resources/engine/upstream/"
mkdir -p "$APP/Contents/Resources/Legal/licenses"
cp LICENSE THIRD_PARTY_NOTICES.md PRIVACY.md "$APP/Contents/Resources/Legal/"
cp licenses/MuScriptor-MIT.txt "$APP/Contents/Resources/Legal/licenses/"
.venv/bin/python - "$APP" "$PWD" <<'PY'
import plistlib, shutil, sys
from pathlib import Path
app, root = sys.argv[1:]
info = dict(CFBundleExecutable='MuScriptor Local', CFBundleIdentifier='local.muscriptor.desktop', CFBundleName='MuScriptor Local', CFBundleDisplayName='MuScriptor Local', CFBundlePackageType='APPL', CFBundleShortVersionString='1.0', CFBundleVersion='12', CFBundleGetInfoString='1.0 Release Candidate 1', LSMinimumSystemVersion='14.0', NSHighResolutionCapable=True, MuScriptorRoot=root, NSHumanReadableCopyright='MuScriptor Local contributors. Engine: Kyutai x Mirelo. Code: MIT. Model weights: separate license.')
info['CFBundleIconFile'] = 'MuScriptor.icns'
for cache in Path(app, 'Contents/Resources/engine').rglob('__pycache__'):
    shutil.rmtree(cache)
for bytecode in Path(app, 'Contents/Resources/engine').rglob('*.pyc'):
    bytecode.unlink()
Path(app, 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
PY
/usr/bin/codesign --force --sign - "$APP"
echo "Built $APP"
