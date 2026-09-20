#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
zsh tools/build.sh
mkdir -p dist
APP="$PWD/dist/MuScriptor Local.app"
ditto 'build/MuScriptor Local.app' "$APP"
/usr/libexec/PlistBuddy -c 'Delete :MuScriptorRoot' "$APP/Contents/Info.plist"
/usr/bin/codesign --force --sign - "$APP"
/usr/bin/ditto -c -k --keepParent "$APP" "$PWD/dist/MuScriptor Local - Apple Silicon.zip"
echo 'Share dist/MuScriptor Local - Apple Silicon.zip. It contains no credentials, audio, or model weights.'
