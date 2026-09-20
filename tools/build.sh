#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
APP="$PWD/build/MuScriptor Local.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" build/module-cache
/usr/bin/swiftc -O -target arm64-apple-macosx14.0 -module-cache-path "$PWD/build/module-cache" src/App.swift -o "$APP/Contents/MacOS/MuScriptor Local" -framework AppKit -framework SwiftUI
mkdir -p "$APP/Contents/Resources/engine/upstream"
cp tools/bootstrap.sh "$APP/Contents/Resources/bootstrap.sh"
cp src/worker.py requirements.lock upstream-revision.txt "$APP/Contents/Resources/engine/"
ditto upstream/muscriptor "$APP/Contents/Resources/engine/upstream/muscriptor"
cp upstream/pyproject.toml upstream/README.md upstream/LICENSE "$APP/Contents/Resources/engine/upstream/"
mkdir -p "$APP/Contents/Resources/Legal/licenses"
cp LICENSE THIRD_PARTY_NOTICES.md PRIVACY.md "$APP/Contents/Resources/Legal/"
cp licenses/MuScriptor-MIT.txt "$APP/Contents/Resources/Legal/licenses/"
.venv/bin/python - "$APP" "$PWD" <<'PY'
import plistlib, sys
from pathlib import Path
app, root = sys.argv[1:]
info = dict(CFBundleExecutable='MuScriptor Local', CFBundleIdentifier='local.muscriptor.desktop', CFBundleName='MuScriptor Local', CFBundleDisplayName='MuScriptor Local', CFBundlePackageType='APPL', CFBundleShortVersionString='1.0', CFBundleVersion='3', CFBundleGetInfoString='1.0 Beta', LSMinimumSystemVersion='14.0', NSHighResolutionCapable=True, MuScriptorRoot=root, NSHumanReadableCopyright='MuScriptor Local contributors. Engine: Kyutai x Mirelo. Code: MIT. Model weights: separate license.')
Path(app, 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
PY
/usr/bin/codesign --force --sign - "$APP"
echo "Built $APP"
