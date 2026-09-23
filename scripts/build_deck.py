#!/usr/bin/env python3
"""Build an Anki deck of Targumic Aramaic vocabulary.

Reads vocabulary.yaml from the project root; see vocab.py for the format. The
aramaic field is pointed Hebrew in Tiberian codepoints, which the Onqelos font
renders as Babylonian supralinear pointing.

Each vocabulary entry makes two cards: the word asking for its meaning, and
the meaning asking for the word. nouns.yaml adds a Paradigms subdeck, whose
cards ask an abstract shape from a grammatical slot and back again.

Usage:  python3 scripts/build_deck.py [output.apkg]
"""

import re
import shutil
import sys
import tempfile
from pathlib import Path

import genanki

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paradigms
import vocab

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
# The paradigm cards are a different shape of note, so a notetype of their
# own; its ids sit clear of the vocabulary's block.
PARADIGM_MODEL_ID = 1748392012
# One subdeck per paradigm file, and the verbs split again by stem and then
# by mood. Anki studies a parent deck together with everything under it, so
# the three levels are three ways into the same cards: "Verbs" is the whole
# system, "Verbs::D (Pael)" one stem, "Verbs::D (Pael)::perfect" one table.
PARADIGM_DECK_BASE = 1748392200
STEM = re.compile(r"^(G stative|G|D|C|Gt|Dt|Ct) \(([^)]+)\)")
STEMS = ("G (Peal)", "G stative (Peal)", "D (Pael)", "C (Aphel)",
         "Gt (Ithpeel)", "Dt (Ithpaal)", "Ct (Ittaphal)")
# Held in a fixed order, and the stem-by-mood cross product written out whole
# whether or not a table fills it, so that a deck's id never shifts when the
# paradigms change. The empty ones are dropped before the package is built.
PARADIGM_DECKS = (("Nouns", "Verbs", "Suffixes")
                  + tuple(f"Verbs::{s}" for s in STEMS)
                  + tuple(f"Verbs::{s}::{m}"
                          for s in STEMS for m in paradigms.MOODS))
# the levels that exist to be studied rather than to hold cards
PARADIGM_PARENTS = ("Verbs",) + tuple(f"Verbs::{s}" for s in STEMS)


def subdeck(group):
    """Which paradigm subdeck a group belongs in."""
    if group["file"] == "nouns.yaml":
        return "Nouns"
    if group["file"] == "suffixes.yaml":
        return "Suffixes"
    found = STEM.match(group["paradigm"])
    if not found:
        raise ValueError(f"no stem in {group['paradigm']!r}")
    mood = paradigms.mood(group["paradigm"])
    if not mood:
        raise ValueError(f"no mood in {group['paradigm']!r}")
    return f"Verbs::{found[1]} ({found[2]})::{mood}"

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

/* The meaning asked as a question, on the recall card. Smaller than .gloss
   because it can run to a clause or two, and it is the prompt rather than the
   reward. */
.prompt {
  margin: 26px auto 0;
  max-width: 26em;
  font-size: 30px;
  font-size: clamp(22px, 6vw, 30px);
  line-height: 1.3;
}

/* Which chapter's vocabulary this is, opposite the corner the recognition
   card gives the transliteration. A meaning like "darkness" is answered by a
   different word in different chapters, so the recall card has to say which. */
.chapter {
  position: absolute;
  top: 10px;
  left: 14px;
  font-size: 13px;
  letter-spacing: .04em;
  color: #a9a49a;
}
.night_mode .chapter, .nightMode .chapter { color: #7c7871; }

/* On the recall card the transliteration is part of the answer, so it sits
   under the word instead of in the corner. */
.answer-vocalization {
  margin-top: 10px;
  font-size: 19px;
  letter-spacing: .02em;
  color: #6e6a60;
  font-family: "Charis SIL", "Doulos SIL", "Gentium Plus", "Times New Roman", serif;
}
.night_mode .answer-vocalization, .nightMode .answer-vocalization {
  color: #a8a49c;
}

/* An abstract shape: C for a root consonant, the vowels spelled out. Set
   monospaced so the consonant slots line up between one shape and the next,
   which is most of the point of writing them this way. */
.shape {
  margin: 26px auto 0;
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 40px;
  font-size: clamp(26px, 8vw, 40px);
  letter-spacing: .02em;
}

/* The grammatical slot a shape fills, or the slots it fills when it is
   syncretic. */
.slot {
  margin: 26px auto 0;
  max-width: 24em;
  font-size: 26px;
  font-size: clamp(20px, 5.5vw, 26px);
  line-height: 1.35;
}

/* Which table this is, in the corner the vocabulary card gives the chapter. */
.paradigm {
  position: absolute;
  top: 10px;
  left: 14px;
  right: 14px;
  font-size: 13px;
  letter-spacing: .04em;
  color: #a9a49a;
}
.night_mode .paradigm, .nightMode .paradigm { color: #7c7871; }

/* The real word the shape was taken from: the pointed Aramaic and then its
   reading, or for the noun tables the reading alone. */
.example {
  margin-top: 14px;
  font-size: 20px;
  color: #6e6a60;
  font-family: "Charis SIL", "Doulos SIL", "Gentium Plus", "Times New Roman", serif;
}
.night_mode .example, .nightMode .example { color: #a8a49c; }

/* The pointed half goes in the embedded font like anywhere else. It sits on
   its own line above the reading rather than beside it: the font has to be
   set large for the marks above the letters to be legible at all, and at that
   size it cannot share a line with a serif reading without the two looking
   mismatched. Stacked, the difference reads as the word and then its caption.
   Sized to sit level with the shape above it, which is smaller in points than
   it looks because Hebrew letterforms are shorter than Latin ones. */
.example .aramaic {
  display: block;
  font-size: 46px;
  font-size: clamp(30px, 11vw, 48px);
  line-height: 1.4;
  margin: 0;
}

.example .reading {
  display: block;
  margin-top: 2px;
  font-size: 18px;
  letter-spacing: .01em;
}
"""

FRONT = """<div class="aramaic">{{Aramaic}}</div>"""

BACK = """<div class="vocalization">{{Vocalization}}</div>
<div class="aramaic">{{Aramaic}}</div>

<hr id="answer">

<div class="gloss">{{Gloss}}</div>
{{#POS}}<div class="pos">{{POS}}</div>{{/POS}}
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
"""

# The other direction: recall the word from its meaning. The part of speech
# comes along to narrow it down, but the vocalization and the notes are held
# back — the vocalization is the answer, and the notes quote forms and idioms
# that would give it away.
REVERSE_FRONT = """<div class="chapter">{{Chapter}}</div>
<div class="prompt">{{Gloss}}</div>
{{#POS}}<div class="pos">{{POS}}</div>{{/POS}}"""

REVERSE_BACK = """<div class="chapter">{{Chapter}}</div>
<div class="prompt">{{Gloss}}</div>
{{#POS}}<div class="pos">{{POS}}</div>{{/POS}}

<hr id="answer">

<div class="aramaic">{{Aramaic}}</div>
<div class="answer-vocalization">{{Vocalization}}</div>
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
        {"name": "Chapter"},
    ],
    # Order matters: Anki keys a card to its template by position, so the
    # recognition card stays first and the recall card is appended.
    templates=[
        {"name": "Aramaic -> Gloss", "qfmt": FRONT, "afmt": BACK},
        {"name": "Gloss -> Aramaic", "qfmt": REVERSE_FRONT,
         "afmt": REVERSE_BACK},
    ],
    css=CSS,
    sort_field_index=1,  # sort the browser by vocalization
)


# Both directions, as with the vocabulary. The shape and the example sit on
# the same side, since they are two views of one form, and what is asked for
# is the name of that form. Nothing else stands in front of the form: naming
# the class there would say which table it came from without helping, so it
# waits on the back, where knowing whether a verb was sound or hollow is
# worth having. The other direction has to keep it in front, since a name
# like "G perfect 3ms" belongs to all seven tables at once.
PARADIGM_FRONT = """<div class="shape">{{Shape}}</div>
<div class="example">{{Example}}</div>"""

PARADIGM_BACK = """<div class="shape">{{Shape}}</div>
<div class="example">{{Example}}</div>

<hr id="answer">

<div class="slot">{{Slot}}</div>
<div class="paradigm">{{Paradigm}}</div>
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
"""

PARADIGM_REVERSE_FRONT = """<div class="paradigm">{{Paradigm}}</div>
<div class="slot">{{Slot}}</div>"""

PARADIGM_REVERSE_BACK = """<div class="paradigm">{{Paradigm}}</div>
<div class="slot">{{Slot}}</div>

<hr id="answer">

<div class="shape">{{Shape}}</div>
<div class="example">{{Example}}</div>
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
"""

PARADIGM_MODEL = genanki.Model(
    PARADIGM_MODEL_ID,
    "Targumic Aramaic (noun paradigms)",
    fields=[
        {"name": "Shape"},
        {"name": "Slot"},
        {"name": "Paradigm"},
        {"name": "Example"},
        {"name": "Notes"},
    ],
    templates=[
        {"name": "Shape -> Slot", "qfmt": PARADIGM_FRONT,
         "afmt": PARADIGM_BACK},
        {"name": "Slot -> Shape", "qfmt": PARADIGM_REVERSE_FRONT,
         "afmt": PARADIGM_REVERSE_BACK},
    ],
    css=CSS,
    sort_field_index=0,
)


def tags_for(group):
    """Tags mirroring where a paradigm sits, as two crossing dimensions.

    A card lives in one deck, so the deck tree has to pick an order to nest
    in -- stem, then mood. Tags do not, so stem and mood are tagged
    separately: "tag:mood::perfect" is every perfect across all seven stems,
    which no deck in the tree corresponds to. They also survive an import
    onto notes that already exist, which a deck does not, so they are what
    makes refiling an already-imported collection a search rather than a
    hunt.
    """
    out = [f"paradigm::{group['file'].removesuffix('.yaml')}"]
    if group["file"] == "verbs.yaml":
        found = STEM.match(group["paradigm"])
        stem = f"{found[1]} {found[2]}".lower().replace(" ", "-")
        out += [f"stem::{stem}", f"mood::{paradigms.mood(group['paradigm'])}"]
    return out


def verb_card(group, slot):
    """-> (context, name) for a cell of a verb paradigm.

    The stem and the mood move out of the context and into the name, so that
    "G perfect 3ms" is what the card asks for rather than something printed
    in front of it. What stays is the reference and the weak class, which the
    example belongs to without naming the form. The traditional stem name is
    dropped from the answer -- the subdeck carries it -- and so is the
    non-finite bucket, since the slot there already says participle or
    infinitive.
    """
    head, _, klass = group["paradigm"].rpartition(", ")
    head = re.sub(r" \([^)]+\)", "", head).replace(", ", " ")
    head = re.sub(r"\s*\bnon-finite\b\s*", " ", head).strip()
    return f"{group['reference']} {klass}", f"{head} {slot}".strip()


HEBREW = re.compile(r"[\u0590-\u05ff]")


def example_html(example):
    """The example with its pointed half set in the deck's own font.

    The yaml keeps the example as plain text, which is what `make check`
    reads; the markup is put on here so that only the built cards carry it.
    """
    word, _, reading = example.partition(" ")
    if not HEBREW.search(word):
        return example                      # a noun table, reading only
    out = f'<span class="aramaic">{word}</span>'
    if reading:
        out += f'<span class="reading">{reading}</span>'
    return out


def syncretic(groups):
    """-> {(shape, example): {every name that form answers to}}.

    Kept only where more than one name shares a form, since that is where a
    card showing the form alone would otherwise be unanswerable.
    """
    seen = {}
    for group in groups:
        for cell in group["cells"]:
            if group["file"] == "verbs.yaml":
                _, name = verb_card(group, cell["slot"])
            else:
                name = cell["slot"]
            seen.setdefault((cell["shape"], cell["example"]),
                            set()).add(name)
    return {k: v for k, v in seen.items() if len(v) > 1}


def paradigm_decks():
    """The paradigms, as one subdeck each. -> ([deck], cell count).

    The levels named in PARADIGM_PARENTS are kept even though nothing sits in
    them directly, since they are what you click to study a stem or the whole
    verb system at once. Any other subdeck that draws no cards is dropped.
    """
    decks = {name: genanki.Deck(PARADIGM_DECK_BASE + i,
                                f"Targumic Aramaic::{name}")
             for i, name in enumerate(PARADIGM_DECKS)}
    count = 0
    groups = paradigms.load_all()
    shared = syncretic(groups)
    for group in groups:
        verb = group["file"] == "verbs.yaml"
        notes = f"{group['notes']} Pattern {group['pattern']}."
        deck = decks[subdeck(group)]
        tags = tags_for(group)
        for cell in group["cells"]:
            if verb:
                context, name = verb_card(group, cell["slot"])
            else:
                context, name = paradigms.title(group), cell["slot"]
            also = sorted(shared.get((cell["shape"], cell["example"]), set())
                          - {name})
            body = notes
            if also:
                # the form stands alone on the front, so a form that answers
                # to more than one name has to say so, or the card asks
                # something it has not given enough to settle
                body = (f"This form is also the {', the '.join(also)}. "
                        + notes)
            deck.add_note(
                genanki.Note(
                    model=PARADIGM_MODEL,
                    fields=[cell["shape"], name, context,
                            example_html(cell["example"]), body],
                    # the lemma and the shape pin the cell; the reference
                    # would shift if the appendix were renumbered, and the
                    # subdeck is not in it, so cards can be refiled freely
                    tags=tags,
                    guid=genanki.guid_for(group["lemma"], cell["shape"]),
                )
            )
            count += 1
    keep = [n for n in PARADIGM_DECKS
            if decks[n].notes or n in PARADIGM_PARENTS]
    for name in keep:
        print(f"{decks[name].name}: {len(decks[name].notes)} cells")
    return [decks[name] for name in keep], count


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "targumic-aramaic.apkg"
    if not FONT_SRC.exists():
        raise SystemExit(
            f"{FONT_SRC} is missing; run python3 scripts/build_font.py")

    decks, total = [], 0

    for idx, (number, entries) in enumerate(vocab.load()):
        deck = genanki.Deck(DECK_BASE_ID + idx,
                            f"Targumic Aramaic::{vocab.deck_name(number)}")
        # Feeds the note guid, so changing it orphans the review history.
        slug = f"chapter-{number}"

        for entry in entries:
            deck.add_note(
                genanki.Note(
                    model=MODEL,
                    fields=["/".join(entry["aramaic"]),
                            " / ".join(entry["vocalization"]),
                            entry["gloss"], entry["pos"],
                            vocab.notes_text(entry),
                            vocab.deck_name(number)],
                    guid=genanki.guid_for(slug, entry["vocalization"][0]),
                )
            )

        print(f"{deck.name}: {len(entries)} entries")
        decks.append(deck)
        total += len(entries)

    paradigm, cells = paradigm_decks()
    decks.extend(paradigm)

    # genanki names media by basename, so the file has to exist under the name
    # @font-face asks for. Staged in a temp dir to leave nothing behind.
    with tempfile.TemporaryDirectory() as staging:
        staged = Path(staging) / FONT_MEDIA
        shutil.copyfile(FONT_SRC, staged)
        package = genanki.Package(decks)
        package.media_files = [str(staged)]
        package.write_to_file(out_path)

    cards = total * len(MODEL.templates) + cells * len(PARADIGM_MODEL.templates)
    print(f"\nwrote {out_path}  ({total} entries, {cells} paradigm cells, "
          f"{cards} cards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
