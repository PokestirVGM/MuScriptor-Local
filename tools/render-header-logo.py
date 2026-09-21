"""Render the official SVG for native headers: pip install resvg-py==0.5.0.

Build-time utility only. resvg preserves nested SVG uses and luminance masks,
which AppKit's SVG import loses (including the pink noteheads).
"""
from pathlib import Path
import argparse
import resvg_py

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
source = args.source.read_text()
# Remove excess transparent vertical padding without changing the artwork.
source = source.replace('viewBox="0 0 676 512" width="676" height="512"',
                        'viewBox="0 105 676 310" width="676" height="310"')
args.output.mkdir(parents=True, exist_ok=True)
for variant in ('dark', 'light'):
    svg = source.replace('#ffffff', '#25262a') if variant == 'light' else source
    png = resvg_py.svg_to_bytes(svg_string=svg, width=304, skip_system_fonts=True)
    (args.output / f'muscriptor-header-{variant}.png').write_bytes(png)
