#!/usr/bin/env python3
"""Replace the Nth mermaid block in a markdown file with its rendered GIF,
keeping the mermaid source collapsed underneath for diff history.

    python3 embed.py <file.md> <block-index> <gif-slug> "<alt text>"

Idempotent: a block already wrapped in <details> is left alone.
"""
import os
import pathlib
import re
import sys

MARKER = "<summary>Mermaid source (kept for diff history)</summary>"
DETAILS = f"<details>\n{MARKER}\n\n"

# scripts/diagram-gif/embed.py -> repo root -> the rendered GIFs.
GIF_DIR = pathlib.Path(__file__).resolve().parents[2] / "docs" / "diagrams" / "gif"


def main(path, index, slug, alt):
    md = pathlib.Path(path).resolve()
    src = md.read_text()
    blocks = list(re.finditer(r'^```mermaid\n.*?^```\n', src, re.S | re.M))
    if index >= len(blocks):
        sys.exit(f"{path}: no mermaid block {index} (found {len(blocks)})")
    b = blocks[index]

    # Already converted? The wrapper opens immediately before the fence.
    if src[:b.start()].rstrip().endswith(MARKER):
        print(f"{path} #{index}: already embedded, skipped")
        return

    gif = GIF_DIR / f"{slug}.gif"
    if not gif.exists():
        sys.exit(f"{path}: gif not found at {gif}")

    # os.path.relpath, not Path.relative_to: the link walks up out of the doc's directory,
    # which relative_to only learned to do with walk_up in 3.12.
    rel = os.path.relpath(gif, md.parent)
    new = f"![{alt}]({rel})\n\n{DETAILS}{b.group(0)}\n</details>\n"
    md.write_text(src[:b.start()] + new + src[b.end():])
    print(f"{path} #{index}: embedded {slug}.gif")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4])
