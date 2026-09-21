#!/usr/bin/env python3
"""Render the vocabulary for reading: vocab-proof.pdf.

Reads chapter1.txt, chapter2.txt, ... from the project root. One page per
chapter, each entry given as its transliteration and its `aramaic` field set
in the Onqelos font.

The Aramaic is set by shaping it with HarfBuzz rather than by drawing text
with PIL, which cannot position the marks.

Usage:  python3 scripts/proof_sheet.py [output.pdf]
"""

import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# The script lives in scripts/; the vocab and font live one level up.
ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "Onqelos-Regular.ttf"
LABEL_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

PAGE_W = 1400
MARGIN = 46
HEADER_H = 96
ROW_H = 132
COLS = 2
LABEL_W = 250
SIZE = 72            # px per em when shaping the Aramaic


def nfc(s):
    return unicodedata.normalize("NFC", s)


def label_font(size, bold=False):
    for path in LABEL_FONTS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


CHAPTER_RE = re.compile(r"^chapter(\d+)\.txt$")


def chapters():
    """-> [(number, vocab path)], in chapter order."""
    found = []
    for path in ROOT.glob("chapter*.txt"):
        match = CHAPTER_RE.match(path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found)


def chapter_entries(path):
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = nfc(raw.strip())
        if not line or line.startswith("#"):
            continue
        aramaic, translit = (p.strip() for p in line.split("|")[:2])
        yield translit, aramaic


def shape(text, tmp):
    """Set `text` in the font and return it as a trimmed image."""
    txt, png = tmp / "t.txt", tmp / "t.png"
    txt.write_text(text, encoding="utf-8")
    subprocess.run(
        ["hb-view", f"--font-file={FONT}", f"--font-size={SIZE}",
         "--margin=8", f"--text-file={txt}", f"--output-file={png}"],
        check=True,
    )
    return Image.open(png).convert("RGB")


def fit(img, box_w, box_h):
    s = min(box_w / img.size[0], box_h / img.size[1], 1.0)
    return img.resize((max(1, int(img.size[0] * s)),
                       max(1, int(img.size[1] * s))), Image.LANCZOS)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "vocab-proof.pdf"
    if not FONT.exists():
        raise SystemExit(f"{FONT} is missing; run python3 scripts/build_font.py")

    title_f, small, big = label_font(44), label_font(20), label_font(27)
    col_w = (PAGE_W - MARGIN * 2) // COLS
    cell_w = col_w - LABEL_W - 20
    pages, total = [], 0

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for number, path in chapters():
            rows = list(chapter_entries(path))
            total += len(rows)
            per_col = (len(rows) + COLS - 1) // COLS
            page = Image.new(
                "RGB", (PAGE_W, HEADER_H + ROW_H * per_col + MARGIN), "white")
            draw = ImageDraw.Draw(page)
            draw.text((MARGIN, MARGIN), f"Chapter {number}",
                      fill="#111", font=title_f)
            draw.text((PAGE_W - MARGIN - 110, MARGIN + 18),
                      f"{len(rows)} entries", fill="#aaa", font=small)
            draw.line([(MARGIN, HEADER_H - 12), (PAGE_W - MARGIN, HEADER_H - 12)],
                      fill="#ccc")

            for i, (translit, aramaic) in enumerate(rows):
                col, slot = divmod(i, per_col)
                x = MARGIN + col * col_w
                y = HEADER_H + slot * ROW_H
                if slot:
                    draw.line([(x, y), (x + col_w - 20, y)], fill="#eee")
                draw.text((x, y + 34), f"{i + 1}.", fill="#ccc", font=small)
                draw.text((x + 40, y + 30), translit, fill="#111", font=big)
                im = fit(shape(aramaic, tmp), cell_w, ROW_H - 18)
                page.paste(im, (x + col_w - 20 - im.size[0],
                                y + (ROW_H - im.size[1]) // 2))
            pages.append(page)

    pages[0].save(out, save_all=True, append_images=pages[1:], resolution=150)
    print(f"wrote {out}  ({total} entries, {len(pages)} pages)")


if __name__ == "__main__":
    main()
