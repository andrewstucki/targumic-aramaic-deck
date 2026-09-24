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
# The leading underscore stops Anki's "check media" offering to delete these
# as unused, since only the @font-face rule names them. Both formats ship and
# both are named as sources: desktop Anki takes either, but iOS WebKit is
# stricter about what it will accept, and giving it a second format to try
# costs 6KB. The woff2 goes first so that clients happy with it fetch the
# smaller file.
FONTS = ((ROOT / "Onqelos-Regular.woff2", "_Onqelos-Regular.woff2"),
         (ROOT / "Onqelos-Regular.ttf", "_Onqelos-Regular.ttf"))

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

# Anki ships 20 new cards a day, which would take months to get through 2548
# of them. The review limit is raised with it because in current Anki it caps
# the day's cards rather than its reviews alone, so leaving it at genanki's
# 100 would hold the new cards back to that same 100.
NEW_PER_DAY = 100
REV_PER_DAY = 9999


def set_daily_limits():
    """Raise the daily limits in the deck options genanki writes.

    genanki hard-codes them into the collection it builds, so they are edited
    on the way past. The review limit goes first: raising the new limit to 100
    would otherwise make the review limit's own 100 ambiguous. Each edit is
    asserted, so a genanki upgrade that moves them fails here rather than
    quietly shipping the defaults.
    """
    import genanki.package
    col = genanki.package.APKG_COL
    for old, new in (('"perDay": 100', f'"perDay": {REV_PER_DAY}'),
                     ('"perDay": 20', f'"perDay": {NEW_PER_DAY}')):
        assert col.count(old) == 1, f"genanki deck options changed: {old}"
        col = col.replace(old, new)
    genanki.package.APKG_COL = col


CSS = """
@font-face {
  font-family: "Onqelos";
  src: url("_Onqelos-Regular.woff2") format("woff2"),
       url("_Onqelos-Regular.ttf") format("truetype");
  font-display: block;
}

/* The word set in the embedded font: Tiberian codepoints in, Babylonian
   supralinear pointing out. Marks sit above the letters, so the line needs
   headroom a Latin line-height does not give it. The size scales with the
   viewport because the longest entries ("gubrā/gabrā") would otherwise run
   off a phone screen; it inherits the card color, so night mode needs no
   special handling the way an image did. */
.aramaic {
  font-size: 2.75em;
  font-family: "Onqelos", serif;
  direction: rtl;
  unicode-bidi: isolate;
  line-height: 1.5;
  margin: 30px auto 0;
}

/* The one size the card is built on. Everything else is an em multiple of
   it, so a single number moves the whole layout.

   Phones are told apart by the class Anki puts on the document, which is
   what the manual documents for this: .mobile, with .iphone, .ipad and
   .android beside it. Those sit on the <html> element while .card sits on
   the <body>, so the selector has to be a descendant one -- .card.mobile
   would never match. It is the class and not a width that decides, because
   a narrow desktop window is not a phone and should not be treated as one.

   Width queries do work here: AnkiMobile's wrapper carries
   <meta name="viewport" content="width=device-width;">, so the viewport is
   the screen. One is used below, but only to tell a tablet from a phone --
   Anki calls both of them .mobile. */
.card {
  font-family: -apple-system, "Helvetica Neue", "Segoe UI", Arial, sans-serif;
  /* WebKit's own text autosizing, off. It would inflate text on a small
     screen by a factor of its own choosing -- not uniform, lifting small
     text more than large -- and the phone size below is set to fill the
     screen to within a small margin of where the longest word would be cut
     off. That margin only holds if the size is the one that was asked for,
     so the multiplier has to go. */
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
  font-size: clamp(16px, 4.6vw, 24px);
  text-align: center;
  color: #1a1a1a;
  background: #fbfaf7;
  padding: 12px 14px;
}

/* THE MOBILE KNOB. Written both ways on purpose: the manual's own examples
   use the platform class as an ancestor (".mobile .example") and on the card
   element itself (".card.nightMode"), and which it is has moved between
   versions. Only one of the two can match, and it costs nothing to have
   both. */
.card.mobile, .mobile .card {
  /* 6vw fills the screen to about 91% of the width the longest single word
     needs. The ceiling on that is 6.3vw, worked out from the font metrics:
     across every screen width the binding item is the same one, the widest
     vocabulary entry, and it wants 5.09px of width for every px of font.
     Anything past 6.3vw cuts it off. */
  font-size: clamp(18px, 6vw, 26px);
  padding: 10px 12px;
}

/* A tablet is .mobile as well, and 13px is meant for a phone. This is what
   a width query is actually good for here. */
@media (min-width: 640px) {
  .card.mobile, .mobile .card {
    /* A tablet is .mobile as well, and the ceiling above is a phone's: on a
       1024px screen it leaves the type proportionally small. The coefficient
       drops because there is far more width to multiply, and the ceiling
       rises to a little above the desktop's, a tablet being held closer. */
    font-size: clamp(20px, 3.2vw, 24px);
    padding: 12px 14px;
  }
}
.night_mode .card, .nightMode .card { color: #e8e6e3; background: #2b2b2b; }

/* Vocalization, tucked in the corner for reference. */
.vocalization {
  font-size: 0.85em;
  position: absolute;
  top: 10px;
  right: 14px;
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

.gloss { font-size: 1.3em; line-height: 1.35; }
.pos {
  font-size: 0.85em;
  margin-top: 8px;
  font-style: italic;
  letter-spacing: .06em;
  text-transform: lowercase;
  color: #8a8579;
}
.notes {
  font-size: 0.92em;
  margin: 16px auto 4px;
  max-width: 32em;
  line-height: 1.45;
  color: #5c5a54;
}
.night_mode .notes, .nightMode .notes { color: #b8b4ae; }

/* The meaning asked as a question, on the recall card. Smaller than .gloss
   because it can run to a clause or two, and it is the prompt rather than the
   reward. */
.prompt {
  font-size: 1.45em;
  margin: 26px auto 0;
  max-width: 26em;
  line-height: 1.3;
}

/* Which chapter's vocabulary this is, opposite the corner the recognition
   card gives the transliteration. A meaning like "darkness" is answered by a
   different word in different chapters, so the recall card has to say which. */
.chapter {
  font-size: 0.8em;
  position: absolute;
  top: 10px;
  left: 14px;
  letter-spacing: .04em;
  color: #a9a49a;
}
.night_mode .chapter, .nightMode .chapter { color: #7c7871; }

/* On the recall card the transliteration is part of the answer, so it sits
   under the word instead of in the corner. */
.answer-vocalization {
  font-size: 1.0em;
  margin-top: 10px;
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
  font-size: 1.55em;
  margin: 26px auto 0;
  font-family: "SF Mono", Menlo, Consolas, monospace;
  letter-spacing: .02em;
}

/* The grammatical slot a shape fills, or the slots it fills when it is
   syncretic. */
.slot {
  font-size: 1.15em;
  margin: 26px auto 0;
  max-width: 24em;
  line-height: 1.35;
}

/* Which table this is, in the corner the vocabulary card gives the chapter. */
.paradigm {
  font-size: 0.8em;
  position: absolute;
  top: 10px;
  left: 14px;
  right: 14px;
  letter-spacing: .04em;
  color: #a9a49a;
}
.night_mode .paradigm, .nightMode .paradigm { color: #7c7871; }

/* The real word the shape was taken from: the pointed Aramaic and then its
   reading, or for the noun tables the reading alone. */
.example {
  font-size: 1.0em;
  margin-top: 14px;
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
  font-size: 2.0em;
  display: block;
  line-height: 1.4;
  margin: 0;
}

.example .reading {
  font-size: 0.92em;
  display: block;
  margin-top: 2px;
  letter-spacing: .01em;
}

/* Nothing may push the card sideways. Only bites on a genuine overflow, so
   it is a backstop to the sizes below rather than part of the layout. */
.shape, .slot, .prompt, .gloss, .example, .notes,
.paradigm, .vocalization, .chapter, .answer-vocalization {
  overflow-wrap: break-word;
}

/* The pointed word included. Breaking it mid-word strands a letter with its
   marks on the next line, which is ugly, but forbidding the break was worse:
   with nowhere to break it ran off both edges of the screen and the last
   letter was simply lost. A wrapped word can still be read. */
.aramaic { overflow-wrap: break-word; }

/* A cell can hold more than one spelling or pattern. They are alternatives,
   not a phrase, so each gets its own line: run together they make the
   longest cell 26 characters wide, which no size that keeps the pointing
   legible will fit on a phone, and stacked the widest is 14. Being one
   alternative each, they are then short enough to sit on one line at the
   sizes below without being forbidden to wrap. Forbidding it was worse than
   the problem: one item too wide to fit could not break, so the page grew a
   horizontal scroll, which threw the whole card off centre and ran it past
   the edge. Wrapping is the graceful failure; overflow is not. */
.variant { display: block; }

/* On a phone the corner labels flow with the document instead. Pinned, they
   overlap the word beneath them the moment they wrap, which a long paradigm
   title does at that width. */
.card.mobile .vocalization, .mobile .vocalization,
.card.mobile .chapter, .mobile .chapter,
.card.mobile .paradigm, .mobile .paradigm {
  position: static;
  margin: 0 auto 4px;
  text-align: center;
}

"""

# Anki wraps the card HTML in a body of its own, and if that happens inside
# an iframe the outer viewport declaration does not reach it. A meta in the
# body is not valid HTML, but WebKit honours one wherever it finds it, and a
# card template has nowhere else to put it. Without it a width query has no
# screen width to match against.
VIEWPORT = ('<meta name="viewport" '
            'content="width=device-width, initial-scale=1">\n')
FRONT = VIEWPORT + """<div class="aramaic">{{Aramaic}}</div>"""

BACK = VIEWPORT + """<div class="vocalization">{{Vocalization}}</div>
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
REVERSE_FRONT = VIEWPORT + """<div class="chapter">{{Chapter}}</div>
<div class="prompt">{{Gloss}}</div>
{{#POS}}<div class="pos">{{POS}}</div>{{/POS}}"""

REVERSE_BACK = VIEWPORT + """<div class="chapter">{{Chapter}}</div>
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
PARADIGM_FRONT = VIEWPORT + """<div class="shape">{{Shape}}</div>
<div class="example">{{Example}}</div>"""

PARADIGM_BACK = VIEWPORT + """<div class="shape">{{Shape}}</div>
<div class="example">{{Example}}</div>

<hr id="answer">

<div class="slot">{{Slot}}</div>
<div class="paradigm">{{Paradigm}}</div>
{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}
"""

PARADIGM_REVERSE_FRONT = VIEWPORT + """<div class="paradigm">{{Paradigm}}</div>
<div class="slot">{{Slot}}</div>"""

PARADIGM_REVERSE_BACK = VIEWPORT + """<div class="paradigm">{{Paradigm}}</div>
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


def stack(text):
    """Alternatives one to a line, each forbidden to wrap.

    Every value goes through this, not just the ones with alternatives, so
    that a single long pattern is held to one line as well.
    """
    return "".join(f'<span class="variant">{p}</span>'
                   for p in text.split("/"))


def example_html(example):
    """The example with its pointed half set in the deck's own font.

    The yaml keeps the example as plain text, which is what `make check`
    reads; the markup is put on here so that only the built cards carry it.
    """
    word, _, reading = example.partition(" ")
    if not HEBREW.search(word):
        return stack(example)               # a noun table, reading only
    out = f'<span class="aramaic">{stack(word)}</span>'
    if reading:
        out += f'<span class="reading">{stack(reading)}</span>'
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
                    fields=[stack(cell["shape"]), name, context,
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
    for source, _ in FONTS:
        if not source.exists():
            raise SystemExit(
                f"{source} is missing; run python3 scripts/build_font.py")
    set_daily_limits()

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
                    fields=[stack("/".join(entry["aramaic"])),
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
        staged = []
        for source, name in FONTS:
            path = Path(staging) / name
            shutil.copyfile(source, path)
            staged.append(str(path))
        package = genanki.Package(decks)
        package.media_files = staged
        package.write_to_file(out_path)

    cards = total * len(MODEL.templates) + cells * len(PARADIGM_MODEL.templates)
    print(f"\nwrote {out_path}  ({total} entries, {cells} paradigm cells, "
          f"{cards} cards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
