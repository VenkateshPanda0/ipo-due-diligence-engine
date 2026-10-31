"""Read a filing as poppler text while labelling (a different path from the extractor's parser).

    python tools/pg.py DOC page N [WIDTH]        print page N
    python tools/pg.py DOC grep REGEX [LO [HI]]  print EVERY matching line with its page number

Text is cached in data/labeltext/DOC.txt (git-ignored). grep never truncates: a truncated search
once hid the sentence that settled a label, so output is all hits or nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pages(doc: str) -> list[str]:
    cache = ROOT / "data" / "labeltext" / f"{doc}.txt"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        pdf = ROOT / "data" / "raw" / f"{doc}.pdf"
        subprocess.run(["pdftotext", "-layout", str(pdf), str(cache)], check=True)
    return cache.read_text(encoding="utf-8", errors="ignore").split("\f")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    doc, mode = argv[0], argv[1]
    text = pages(doc)
    if mode == "page":
        width = int(argv[3]) if len(argv) > 3 else 170
        for line in text[int(argv[2]) - 1].splitlines():
            if line.strip():
                print(line[:width])
    elif mode == "grep":
        pat = re.compile(argv[2], re.IGNORECASE)
        lo = int(argv[3]) if len(argv) > 3 else 1
        hi = int(argv[4]) if len(argv) > 4 else len(text)
        for n in range(lo, min(hi, len(text)) + 1):
            for line in text[n - 1].splitlines():
                if pat.search(line):
                    print(f"p{n}: {line.strip()[:200]}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
