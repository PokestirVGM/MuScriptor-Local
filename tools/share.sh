#!/bin/zsh
set -euo pipefail
export COPYFILE_DISABLE=1
cd "${0:A:h:h}"
zsh tools/build.sh
mkdir -p dist
APP="$PWD/dist/MuScriptor Local.app"
rm -rf "$APP"
ditto 'build/MuScriptor Local.app' "$APP"
/usr/libexec/PlistBuddy -c 'Delete :MuScriptorRoot' "$APP/Contents/Info.plist"
/usr/bin/codesign --force --sign - "$APP"
STAGING=$(mktemp -d "$PWD/build/release-macos.XXXXXX")
trap 'rm -rf "$STAGING"' EXIT
mkdir -p "$STAGING/Legal/licenses"
ditto --norsrc --noextattr --noqtn "$APP" "$STAGING/MuScriptor Local.app"
cp 'dist/Read Me First.txt' "$STAGING/Read Me First.txt"
cp LICENSE THIRD_PARTY_NOTICES.md PRIVACY.md "$STAGING/Legal/"
cp licenses/MuScriptor-MIT.txt "$STAGING/Legal/licenses/"
/usr/bin/ditto --norsrc --noextattr --noqtn -c -k "$STAGING" "$PWD/dist/MuScriptor Local - Apple Silicon.zip"
echo 'Share dist/MuScriptor Local - Apple Silicon.zip. It contains no credentials, personal recordings, or model weights.'
