"""Apply the reviewed local rhythm extension to the pinned engine checkout.

Idempotent; refuses divergent upstream files instead of overwriting local edits.
The patch is tracked here because upstream/ is a separately managed checkout.
"""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
patch = root / 'patches/upstream-rhythm.patch'
reverse = '--reverse' in sys.argv
args = ['--reverse'] if reverse else []
other = [] if reverse else ['--reverse']
def run(flags, check=False):
    return subprocess.run(['git', 'apply', *flags, '--check' if check else '--whitespace=nowarn', str(patch)], cwd=root/'upstream', capture_output=True, text=True)
if run(args, True).returncode == 0:
    result = run(args)
    if result.returncode:
        raise SystemExit(result.stderr)
elif run(other, True).returncode != 0:
    raise SystemExit('The local rhythm extension does not match this engine checkout. Preserve local edits and review patches/upstream-rhythm.patch against the pinned revision before rebuilding.')
