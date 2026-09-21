#!/usr/bin/env python3
"""Build an Anki deck of Targumic Aramaic vocabulary.

Reads chapter1.txt, chapter2.txt, ... from the project root, one entry a line:

    "aramaic | vocalization | definition. pos. notes"

The aramaic field is pointed Hebrew in Tiberian codepoints, which the Onqelos
font renders as Babylonian supralinear pointing. The card front is that word;
the back adds the gloss, part of speech and notes.

Usage:  python3 scripts/build_deck.py [output.apkg]
"""

import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

import genanki

# The script lives in scripts/; the vocab and font live one level up.
ROOT = Path(__file__).resolve().parent.parent

# Shipped inside the deck, so cards render on a device without it installed.
# The leading underscore stops Anki's "check media" offering to delete it as
# unused, since only the @font-face rule names it. TTF over the smaller woff2
# because every Anki client handles TTF and 14KB is not worth the risk.
FONT_SRC = ROOT / "Onqelos-Regular.ttf"
FONT_MEDIA = "_Onqelos-Regular.ttf"

# Stable ids so re-importing an updated deck updates existing cards
# instead of creating duplicates.
MODEL_ID = 1748392011
DECK_BASE_ID = 1748392100

POS_WORDS = [
    "verb",
    "noun",
    "adjective",
    "adj",
    "preposition",
    "prep",
    "adverb",
    "adv",
    "pronoun",
    "pron",
    "conjunction",
    "conj",
    "particle",
    "interjection",
    "numeral",
]
POS_RE = re.compile(
    r"(?:^|[.,;]\s*)(" + "|".join(POS_WORDS) + r")\s*[.,;]?\s*", re.IGNORECASE
)
POS_EXPANSIONS = {
    "adj": "adjective",
    "prep": "preposition",
    "adv": "adverb",
    "pron": "pronoun",
    "conj": "conjunction",
}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def parse_line(line):
    """-> (aramaics, vocalizations, gloss, pos, notes), or None for blanks.

    A line is "aramaic | vocalization | definition. pos. notes", and either of
    the first two fields may carry several variants separated by "/".
    """
    line = nfc(line.strip())
    if not line or line.startswith("#"):
        return None
    if line.count("|") < 2:
        raise ValueError(
            f"expected 'aramaic | vocalization | definition': {line!r}"
        )

    aramaic, vocab, rest = (part.strip() for part in line.split("|", 2))
    rest = re.sub(r"\s+", " ", rest).strip()

    # Split the definition into gloss / part-of-speech / trailing notes.
    match = POS_RE.search(rest)
    if match:
        gloss = rest[: match.start()].strip()
        pos = match.group(1).lower()
        pos = POS_EXPANSIONS.get(pos, pos)
        notes = rest[match.end() :].strip()
    else:
        gloss, pos, notes = rest, "", ""

    gloss = gloss.strip(" .,;")
    notes = notes.strip()
    # "(sometimes ʔabad)" -> "sometimes ʔabad"
    if notes.startswith("(") and notes.endswith(")") and notes.count("(") == 1:
        notes = notes[1:-1].strip()

    aramaics = [a.strip() for a in aramaic.split("/") if a.strip()]
    vocalizations = [v.strip() for v in vocab.split("/") if v.strip()]
    return aramaics, vocalizations, gloss, pos, notes


CSS = """
@font-face {
  font-family: "Onqelos";
  src: url("_Onqelos-Regular.ttf");
}

/* The word set in the embedded font: Tiberian codepoints in, Babylonian
   supralinear pointing out. Marks sit above the letters, so the line needs
   headroom a Latin line-height does not give it. The size scales with the
   viewport because the longest entries ("gubrā/gabrā") would otherwise run
   off a phone screen; it inherits the card color, so night mode needs no
   special handling the way an image did. */
.aramaic {
  font-family: "Onqelos", serif;
  direction: rtl;
  unicode-bidi: isolate;
  font-size: 64px;
  font-size: clamp(38px, 12vw, 76px);
  line-height: 1.5;
  margin: 30px auto 0;
}

.card {
  font-family: -apple-system, "Helvetica Neue", "Segoe UI", Arial, sans-serif;
  font-size: 20px;
  text-align: center;
  color: #1a1a1a;
  background: #fbfaf7;
  padding: 8px 4px;
}
.night_mode .card, .nightMode .card { color: #e8e6e3; background: #2b2b2b; }

/* Vocalization, tucked in the corner for reference. */
.vocalization {
  position: absolute;
  top: 10px;
  right: 14px;
  font-size: 15px;
  letter-spacing: .02em;
  color: #8a8579;
  font-family: "Charis SIL", "Doulos SIL", "Gentium Plus", "Times New Roman", serif;
}
.night_mode .vocalization, .nightMode .vocalization { color: #8f8b84; }

hr#answer {
  height: 1px;
  border: 0;
  background: #dedad0;
  margin: 22px 18% 20px;
}
.night_mode hr#answer, .nightMode hr#answer { background: #4a4a4a; }

.gloss { font-size: 26px; line-height: 1.35; }
.pos {
  margin-top: 8px;
  font-size: 15px;
  font-style: italic;
  letter-spacing: .06em;
  text-transform: lowercase;
  color: #8a8579;
}
.notes {
  margin: 16px auto 4px;
  max-width: 32em;
  font-size: 16px;
  line-height: 1.45;
  color: #5c5a54;
}
.night_mode .notes, .nightMode .notes { color: #b8b4ae; }
"""

FRONT = """<div class="aramaic">{{Aramaic}}</div>"""

BACK = """<div class="vocalization">{{Vocalization}}</div>
<div class="aramaic">{{Aramaic}}</div>

<hr id="answer">

<div class="gloss">{{Gloss}}</div>
{{#POS}}<div class="pos">{{POS}}</div>{{/POS}}
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
"""

MODEL = genanki.Model(
    MODEL_ID,
    "Targumic Aramaic (Babylonian pointing)",
    fields=[
        {"name": "Aramaic"},
        {"name": "Vocalization"},
        {"name": "Gloss"},
        {"name": "POS"},
        {"name": "Notes"},
    ],
    templates=[
        {"name": "Aramaic -> Gloss", "qfmt": FRONT, "afmt": BACK},
    ],
    css=CSS,
    sort_field_index=1,  # sort the browser by vocalization
)


CHAPTER_RE = re.compile(r"^chapter(\d+)\.txt$")


def chapters():
    """-> [(number, vocab path)], in chapter order."""
    found = []
    for path in ROOT.glob("chapter*.txt"):
        match = CHAPTER_RE.match(path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found)


def scan_dir(number):
    """The directory of textbook scans for a chapter, if it is still there.

    Only used to warn about a scan with no entry; the deck itself no longer
    reads them.
    """
    path = ROOT / f"chapter {number}"
    return path if path.is_dir() else None


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "targumic-aramaic.apkg"
    if not FONT_SRC.exists():
        raise SystemExit(
            f"{FONT_SRC} is missing; run python3 scripts/build_font.py")

    decks, problems = [], []

    for idx, (number, vocab) in enumerate(chapters()):
        deck = genanki.Deck(DECK_BASE_ID + idx,
                            f"Targumic Aramaic::Chapter {number}")
        # Feeds the note guid, so changing it orphans the review history.
        slug = f"chapter-{number}"

        lines = vocab.read_text(encoding="utf-8").splitlines()
        covered, count = set(), 0

        for lineno, raw in enumerate(lines, 1):
            entry = parse_line(raw)
            if entry is None:
                continue
            try:
                aramaics, vocalizations, gloss, pos, notes = entry
            except ValueError as exc:
                raise ValueError(f"{vocab.name}:{lineno}: {exc}") from exc
            covered.update(nfc(v) for v in vocalizations)

            deck.add_note(
                genanki.Note(
                    model=MODEL,
                    fields=["/".join(aramaics), " / ".join(vocalizations),
                            gloss, pos, notes],
                    guid=genanki.guid_for(slug, vocalizations[0]),
                )
            )
            count += 1

        # A scan with no entry means a word that never got transcribed.
        scans = scan_dir(number)
        if scans:
            for orphan in sorted(nfc(p.name[:-4]) for p in scans.glob("*.png")):
                if orphan not in covered:
                    problems.append(
                        f"{scans.name}/{orphan}.png has no {vocab.name} entry")

        print(f"{deck.name}: {count} cards")
        decks.append(deck)

    # genanki names media by basename, so the file has to exist under the name
    # @font-face asks for. Staged in a temp dir to leave nothing behind.
    with tempfile.TemporaryDirectory() as staging:
        staged = Path(staging) / FONT_MEDIA
        shutil.copyfile(FONT_SRC, staged)
        package = genanki.Package(decks)
        package.media_files = [str(staged)]
        package.write_to_file(out_path)

    print(f"\nwrote {out_path}")
    for p in problems:
        print(f"  warning: {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
