#!/usr/bin/env python3
"""Read nouns.yaml, verbs.yaml and suffixes.yaml, the paradigms.

The file is a list of paradigms, each with the cells of its table:

    - paradigm: Unchanging base
      reference: A.1
      pattern: qattil
      lemma: šappir ‘beautiful’
      notes: The base never changes; only the ending does.
      cells:
        - slot: masculine singular emphatic, feminine singular absolute
          shape: CaCCiC-ā
          example: šappirā

A shape writes C for each root consonant, spells the vowels out, and separates
the ending with a hyphen, so that what varies between cells is visible without
a root getting in the way. pattern names the base with the q-t-l dummy root,
the convention the grammars use, so a type can be looked up.

One shape often fills more than one slot; slot then names them all, because
that syncretism is itself the thing to learn. A shape and a slot each have to
be unique within a paradigm, since the cards are asked in both directions and
the paradigm is all the reader is given to go on.
"""
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("nouns.yaml", "verbs.yaml", "suffixes.yaml")
PATHS = [os.path.join(ROOT, f) for f in FILES]
HEAD = ("paradigm", "reference", "pattern", "lemma", "notes")
CELL = ("slot", "shape", "example")


def load(path):
    """-> [paradigm], each with its cells. Raises on anything malformed."""
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    if not isinstance(doc, list):
        raise ValueError(f"{name}: expected a list of paradigms")

    out, lemmas = [], set()
    for i, raw in enumerate(doc, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"{name}: paradigm {i} is not a mapping")
        unknown = set(raw) - set(HEAD) - {"cells"}
        if unknown:
            raise ValueError(f"{name}: paradigm {i} has unknown key(s) "
                             f"{sorted(unknown)}")
        group = {}
        for key in HEAD:
            value = raw.get(key, "")
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name}: paradigm {i} needs a {key}")
            group[key] = value.strip()
        # the lemma is what tells two sub-types of one paradigm apart
        if group["lemma"] in lemmas:
            raise ValueError(f"{name}: two paradigms share the lemma "
                             f"{group['lemma']!r}")
        lemmas.add(group["lemma"])

        cells, shapes, slots = [], set(), set()
        for k, rawcell in enumerate(raw.get("cells") or [], 1):
            where = f"{group['lemma']} cell {k}"
            if not isinstance(rawcell, dict):
                raise ValueError(f"{name}: {where} is not a mapping")
            extra = set(rawcell) - set(CELL)
            if extra:
                raise ValueError(f"{name}: {where} has unknown key(s) "
                                 f"{sorted(extra)}")
            cell = {}
            for key in CELL:
                value = rawcell.get(key, "")
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{name}: {where} needs a {key}")
                cell[key] = value.strip()
            # both directions are asked, so neither side may repeat
            for value, seen, side in ((cell["shape"], shapes, "shape"),
                                      (cell["slot"], slots, "slot")):
                if value in seen:
                    raise ValueError(f"{name}: {group['lemma']} uses the "
                                     f"{side} {value!r} twice")
                seen.add(value)
            cells.append(cell)
        if not cells:
            raise ValueError(f"{name}: {group['lemma']} has no cells")
        group["cells"] = cells
        out.append(group)
    return out


def load_all(paths=None):
    """Every paradigm from every file, with lemmas unique across the lot."""
    out, lemmas = [], {}
    for path in (paths or PATHS):
        for group in load(path):
            name = os.path.basename(path)
            if group["lemma"] in lemmas:
                raise ValueError(f"{name}: the lemma {group['lemma']!r} is "
                                 f"also in {lemmas[group['lemma']]}")
            lemmas[group["lemma"]] = name
            # which file a paradigm came from decides its subdeck
            group["file"] = name
            out.append(group)
    return out


MOODS = ("imperfect", "perfect", "imperative", "non-finite")


def mood(paradigm):
    """A verb paradigm's mood, or "" for a noun or suffix paradigm.

    A name can carry an extra part -- "G stative (Peal), mwt perfect, hollow
    verbs" -- so the word is looked for rather than counted to, and imperfect
    is tried before perfect because the one contains the other.
    """
    for name in MOODS:
        if re.search(rf"\b{name}\b", paradigm):
            return name
    return ""


def title(group):
    """The paradigm as a card names it: "A.1 unchanging base · šappir"."""
    return f"{group['reference']} {group['paradigm']} · {group['lemma']}"
