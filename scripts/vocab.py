#!/usr/bin/env python3
"""Read vocabulary.yaml, the vocabulary for the whole deck.

The file is a list of chapters, each with its entries:

    - chapter: 1                # or a label, e.g. "Appendix - Genesis 12-16"
      entries:
        - aramaic: [אְבַד]
          vocalization: [ʔǝbad]
          gloss: to perish, die
          pos: verb
          notes: (sometimes ʔabad).
          hebrew: ʔbd

aramaic and vocalization are parallel lists of variants, so the nth spelling
goes with the nth transliteration. A word spelled more than one way but
pronounced one way, like min, gives a single vocalization for all of its
spellings. gloss, pos, notes and hebrew are plain text, and all but gloss may
be left out. hebrew is the Hebrew equivalent the textbook glossary gives, kept
apart from the notes so it can be read on its own.

A gloss has to be unique within its chapter, since one of the two cards each
entry makes is answered from the gloss alone; see README.md for how to
separate two words that would otherwise share one.

A chapter is a lesson number, or a label for material that is not a numbered
lesson; labelled chapters come last. Chapter order and the first vocalization
of each entry feed the Anki note and deck ids, so reordering either orphans
review history.
"""
import os
import re
import unicodedata

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "vocabulary.yaml")
LISTS = ("aramaic", "vocalization")
TEXT = ("gloss", "pos", "notes", "hebrew")
FIELDS = LISTS + TEXT


def nfc(s):
    return unicodedata.normalize("NFC", s)


# a plain YAML scalar would be misread if it carried one of these
UNSAFE_START = "-?:,[]{}#&*!|>'\"%@`"
RESERVED = {"", "true", "false", "null", "yes", "no", "on", "off", "~"}


def scalar(s):
    """s as a YAML scalar, quoted only when it has to be."""
    if (s.lower() in RESERVED or s[:1] in UNSAFE_START or s != s.strip()
            or ": " in s or s.endswith(":") or " #" in s
            or re.fullmatch(r"[-+]?[\d._eE+]+", s)):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _entry(raw, where):
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected a mapping")
    unknown = set(raw) - set(FIELDS)
    if unknown:
        raise ValueError(f"{where}: unknown field(s) {sorted(unknown)}")

    entry = {}
    for key in LISTS:
        value = raw.get(key)
        if isinstance(value, str):           # a lone variant need not be a list
            value = [value]
        if not value or not all(isinstance(v, str) and v.strip()
                                for v in value):
            raise ValueError(f"{where}: {key} must be a non-empty list")
        entry[key] = [nfc(v.strip()) for v in value]
    # one vocalization may serve several spellings of the one pronunciation
    if len(entry["vocalization"]) not in (1, len(entry["aramaic"])):
        raise ValueError(
            f"{where}: {len(entry['aramaic'])} aramaic variants but "
            f"{len(entry['vocalization'])} vocalizations")
    for key in TEXT:
        value = raw.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"{where}: {key} must be text")
        entry[key] = nfc(value.strip())
    if not entry["gloss"]:
        raise ValueError(f"{where}: gloss is required")
    return entry


def deck_name(chapter):
    """The Anki subdeck for a chapter: "Chapter 7", or the label itself."""
    return f"Chapter {chapter}" if isinstance(chapter, int) else str(chapter)


def load(path=PATH):
    """-> [(chapter, [entry])], in file order.

    Raises on anything malformed, so every reader can trust what it gets.
    """
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    if not isinstance(doc, list):
        raise ValueError(f"{name}: expected a list of chapters")

    out, seen = [], set()
    for i, chapter in enumerate(doc, 1):
        if not isinstance(chapter, dict):
            raise ValueError(f"{name}: chapter {i} is not a mapping")
        extra = set(chapter) - {"chapter", "entries"}
        if extra:
            raise ValueError(f"{name}: chapter {i} has unknown key(s) "
                             f"{sorted(extra)}")
        number = chapter.get("chapter")
        # numbered lessons, or a label like "Appendix - Genesis 12-16"
        if not isinstance(number, (int, str)) or isinstance(number, bool) \
                or (isinstance(number, str) and not number.strip()):
            raise ValueError(f"{name}: chapter {i} needs a number or a label "
                             f"in 'chapter'")
        if isinstance(number, str):
            number = number.strip()
        if number in seen:
            raise ValueError(f"{name}: chapter {number!r} appears twice")
        seen.add(number)
        entries = [_entry(raw, f"chapter {number} entry {k}")
                   for k, raw in enumerate(chapter.get("entries") or [], 1)]
        out.append((number, entries))

    # Numbered lessons stay in order, and labelled ones follow them, so that a
    # chapter's position -- which fixes its deck id -- never shifts.
    numbered = [n for n, _ in out if isinstance(n, int)]
    if numbered != sorted(numbered):
        raise ValueError(f"{name}: numbered chapters are out of order")
    labelled = [i for i, (n, _) in enumerate(out) if not isinstance(n, int)]
    if labelled and min(labelled) < len(numbered):
        raise ValueError(f"{name}: labelled chapters must come after the "
                         f"numbered ones")
    return out


def notes_text(entry):
    """The notes and the Hebrew equivalent as one run of prose."""
    parts = [entry["notes"]]
    if entry["hebrew"]:
        parts.append(f"Heb. {entry['hebrew']}.")
    return " ".join(p for p in parts if p)
