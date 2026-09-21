"""Build upstream's pinned frontend into the app; Node is only a build dependency."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
web = root / "upstream/web"
output = root / "upstream/muscriptor/web_dist"
revision = (root / "upstream-revision.txt").read_text().strip()
stamp = output / "SOURCE_REVISION"
if (output / "index.html").is_file() and (output / "THIRD_PARTY_LICENSES.txt").is_file() and stamp.is_file() and stamp.read_text().strip() == revision:
    print("Bundled web GUI is current.")
else:
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise SystemExit("Building the app requires Node.js 22+ and pnpm 10.20.0. Users of the installer do not need either.")
    subprocess.run([pnpm, "install", "--frozen-lockfile"], cwd=web, check=True)
    environment = dict(os.environ, VITE_GA_MEASUREMENT_ID="")
    subprocess.run([pnpm, "run", "build"], cwd=web, env=environment, check=True)
    # Upstream already supplies offline font fallbacks. Avoid external font
    # requests in the local app without changing the upstream checkout.
    index = output / "index.html"
    index.write_text(re.sub(r'<link\b[^>]*https://fonts\.(?:googleapis|gstatic)\.com[^>]*>', '', index.read_text(encoding="utf-8")), encoding="utf-8")
    # Include the exact production packages' notices alongside the built UI.
    report = json.loads(subprocess.check_output([pnpm, "licenses", "list", "--prod", "--json"], cwd=web, text=True))
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
