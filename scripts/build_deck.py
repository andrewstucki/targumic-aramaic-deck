#!/usr/bin/env python3
"""Build an Anki deck of Targumic Aramaic vocabulary.

Reads vocabulary.yaml from the project root; see vocab.py for the format. The
aramaic field is pointed Hebrew in Tiberian codepoints, which the Onqelos font
renders as Babylonian supralinear pointing.

Each entry makes two cards: the word asking for its meaning, and the meaning
asking for the word.

Usage:  python3 scripts/build_deck.py [output.apkg]
"""

import shutil
import sys
import tempfile
from pathlib import Path

import genanki

sys.path.insert(0, str(Path(__file__).resolve().parent))
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

    # genanki names media by basename, so the file has to exist under the name
    # @font-face asks for. Staged in a temp dir to leave nothing behind.
    with tempfile.TemporaryDirectory() as staging:
        staged = Path(staging) / FONT_MEDIA
        shutil.copyfile(FONT_SRC, staged)
        package = genanki.Package(decks)
        package.media_files = [str(staged)]
        package.write_to_file(out_path)

    cards = total * len(MODEL.templates)
    print(f"\nwrote {out_path}  ({total} entries, {cards} cards)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
