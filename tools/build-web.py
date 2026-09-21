"""Build upstream's pinned frontend into the app; Node is only a build dependency."""
import json
import hashlib
import sys
import os
from pathlib import Path
import re
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(root / "tools/apply-engine-patches.py")], check=True)
web = root / "upstream/web"
output = root / "upstream/muscriptor/web_dist"
revision = (root / "upstream-revision.txt").read_text().strip() + ":" + hashlib.sha256((root / "patches/upstream-rhythm.patch").read_bytes()).hexdigest()
app_version = (root / "VERSION").read_text().strip()
revision += ":" + app_version
stamp = output / "SOURCE_REVISION"
if (output / "index.html").is_file() and (output / "THIRD_PARTY_LICENSES.txt").is_file() and stamp.is_file() and stamp.read_text().strip() == revision:
    print("Bundled web GUI is current.")
else:
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise SystemExit("Building the app requires Node.js 22+ and pnpm 10.20.0. Users of the installer do not need either.")
    if "--skip-install" not in sys.argv:
        subprocess.run([pnpm, "install", "--frozen-lockfile"], cwd=web, check=True)
    environment = dict(os.environ, VITE_GA_MEASUREMENT_ID="", VITE_APP_VERSION=app_version)
    subprocess.run([pnpm, "run", "build"], cwd=web, env=environment, check=True)
    # Upstream already supplies offline font fallbacks. Avoid external font
    # requests in the local app without changing the upstream checkout.
    index = output / "index.html"
    index.write_text(re.sub(r'<link\b[^>]*https://fonts\.(?:googleapis|gstatic)\.com[^>]*>', '', index.read_text(encoding="utf-8")), encoding="utf-8")
    # Include the exact production packages' notices alongside the built UI.
    # Read the packages actually linked into this build. Unlike `pnpm licenses`,
    # this also works when an existing node_modules tree outlives its store index.
    report = {}
    seen = set()
    def collect(name, parent, optional=False):
        directory = next((base / "node_modules" / name for base in (parent, *parent.parents)
                          if (base / "node_modules" / name / "package.json").is_file()), None)
        if directory is None:
            if optional:
                return
            raise RuntimeError(f"Missing production package: {name}")
        directory = directory.resolve()
        if directory in seen:
            return
        seen.add(directory)
        metadata = json.loads((directory / "package.json").read_text())
        report.setdefault(str(metadata.get("license", "See package license")), []).append({"paths": [str(directory)]})
        for dependency in metadata.get("dependencies", {}):
            collect(dependency, directory)
        for dependency in {*metadata.get("optionalDependencies", {}), *metadata.get("peerDependencies", {})}:
            collect(dependency, directory, optional=True)
    for name in json.loads((web / "package.json").read_text()).get("dependencies", {}):
        collect(name, web)
    notices = ["MuScriptor official web UI — bundled third-party notices\n"]
    for license_name, packages in report.items():
        for package in packages:
            for location in package["paths"]:
                directory = Path(location)
                metadata = json.loads((directory / "package.json").read_text())
                name = metadata["name"] + "@" + metadata["version"]
                notices.append(f"\n{'=' * 60}\n{name}\nLicense: {license_name}\n")
                files = [path for path in directory.iterdir() if path.is_file() and path.name.lower().startswith(("license", "licence", "copying", "notice"))]
                if not files:
                    raise RuntimeError(f"Missing license text for {name}")
                for path in sorted(files):
                    notices.append(path.read_text(encoding="utf-8", errors="replace"))
    (output / "THIRD_PARTY_LICENSES.txt").write_text("\n".join(notices), encoding="utf-8")
    stamp.write_text(revision + "\n")
    print("Bundled official web GUI and license notices.")
