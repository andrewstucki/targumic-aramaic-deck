# Targumic Aramaic Anki Deck

This project can be used to generate `targumic-aramaic.apkg`, an Anki package
for the vocabulary found in Lambdin and Huehnergard's *The Aramaic of Targum
Onqelos*.

To add vocabulary to the deck, add it to `vocabulary.yaml` and re-render the
package.

Every entry makes two cards, one in each direction:

- **Aramaic → Gloss** shows the word set in the `Onqelos` font that ships
  inside the deck, and answers with the gloss, part of speech and notes, the
  transliteration in the corner.
- **Gloss → Aramaic** shows the meaning, the part of speech and the chapter,
  and answers with the word. The transliteration is held back to the answer,
  since it gives the word away, and so are the notes, which quote forms and
  idioms.

Because the recall card is answered from the meaning alone, a gloss has to be
unique within its chapter. Three ways to separate two words that would
otherwise share one:

- If they differ by stem, name the stem: `to look (G)` and `to look (Dt)`.
- If they are only spellings of one word, make them one entry with two
  `aramaic` variants, the way `sānǝyā/sānǝʔā` is.
- Otherwise number them `(I)` and `(II)`, as `on, upon (I)` and
  `on, upon (II)` are.

Across chapters a gloss may repeat — the chapter in the corner tells them
apart.

## The paradigm cards

`nouns.yaml` holds the noun and adjective paradigms of Appendix A, as abstract
shapes rather than real words, so what varies between the cells of a table is
what you see. `C` stands for a root consonant, the vowels are spelled out, and
a hyphen separates the ending: `šappirǝtā` is `CaCCiC-ǝtā`.

```yaml
- paradigm: Unchanging base
  reference: A.1
  pattern: qattil
  lemma: šappir ‘beautiful’
  notes: The base never changes; only the ending does.
  cells:
    - slot: masculine singular emphatic, feminine singular absolute
      shape: CaCCiC-ā
      example: šappirā
```

- `pattern` names the base with the q-t-l dummy root, the convention the
  grammars use, so a type can be looked up.
- Where one shape fills several slots, `slot` names them all; that syncretism
  is itself worth learning, so those cells are one card rather than several.
- These cards run in both directions too. The shape and the example sit
  together on one side, being two views of one form, and the other side names
  that form: the slot for a noun or a suffix, and for a verb the stem and the
  form together, `G perfect 3ms`. Nothing stands in front of the form — which
  table it came from waits on the back, where knowing a verb was sound or
  hollow is worth having but naming it up front would only narrow the
  question. The other direction does keep it in front, since a name like
  `G perfect 3ms` belongs to all seven tables at once.
- A form can answer to more than one name: the D imperative ms is the D
  perfect 3ms, so `CaCCeC` and `כַתֵיב katteb` are both. Standing alone on the
  front, such a form does not settle which is wanted, so its back names the
  others too. 118 cards say so, worked out at build time rather than written
  into the yaml.
- A `shape` and a `slot` each have to be unique within a paradigm, and `lemma`
  has to be unique across the file, since that is what separates two sub-types
  of one paradigm.
- `make check` re-derives every shape from the example beside it, so a shape
  cannot drift from the word it came from.

`verbs.yaml` holds Appendix B the same way. A verb form is a stem base with a
person affix on it, and the affixes are the same for every stem and every
class, so the bases are carded once per stem and the affixes once for the
whole system rather than writing out every composition of the two.

The verb tables print no transliteration, so each example carries the pointed
Aramaic and a transliteration derived from it. A doubled consonant is spelled
once in this system, and is restored in the shape where the vowels require it:
a short, unaccented vowel in a syllable that would otherwise be open would
have reduced to sheva, so if it has not, the next consonant closes the
syllable — `כַתֵיב` is `katteb`, `CaCCeC`. Where the accent is what protects
the vowel instead, as in `kǝtabat`, nothing is doubled.

On the card the pointed half of an example is set in the embedded font, the
same one the vocabulary uses, so the paradigms show Babylonian pointing too;
the reading beside it stays in the serif. The yaml keeps the example as plain
text and the markup is put on when the deck is built, which is why `make
check` can still read it.

`suffixes.yaml` holds the pronominal suffixes. They attach to both nouns and
verbs, so they belong to neither appendix and get a file of their own, with
`reference` naming the lesson section rather than a paradigm number: the
possessive sets on a singular noun, on a feminine in `-ǝtā` and on the two
plurals, and the perfect with object suffixes, one paradigm per person of the
verb. These lessons do print a transliteration beside every form, so the
example carries the book's own reading and the decoded spelling only has to
agree with it. Two things it says are not carried over: the doubled `n` of
`kǝtab-innun`, which is written once and so is restored like any other
unmarked gemination, and spirantization, which the book marks in `hekal-ḵon`
and this deck marks nowhere.

The three files get a subdeck each — `Nouns`, `Verbs`, `Suffixes` — under a
notetype of their own, so they schedule separately from the vocabulary. The
verbs are split again by stem and then by mood:

```
Targumic Aramaic::Verbs
Targumic Aramaic::Verbs::G (Peal)
Targumic Aramaic::Verbs::G (Peal)::perfect
Targumic Aramaic::Verbs::G (Peal)::imperfect
Targumic Aramaic::Verbs::G (Peal)::imperative
Targumic Aramaic::Verbs::G (Peal)::non-finite
Targumic Aramaic::Verbs::G stative (Peal)::perfect
...
```

Anki studies a parent deck together with everything under it, so the three
levels are three ways into one set of cards: `Verbs` is the whole system,
`Verbs::D (Pael)` one stem, `Verbs::D (Pael)::perfect` one table. A card can
only live in one deck, so the hierarchy is what gives all three without
duplicating notes and splitting their history. The upper two levels hold
nothing themselves and are built empty for that reason; a stem-and-mood deck
that draws no cells is dropped instead, though as things stand all 28 of them
fill.

Note that drilling one leaf tells you most of the answer — in
`Verbs::D (Pael)::perfect` every card answers `D perfect` and something. The
parent decks are where the recall is real.

Each paradigm note is also tagged with where it sits: `paradigm::verbs`, and
for a verb `stem::d-pael` and `mood::perfect` as two separate dimensions. The
deck tree has to nest in one order, stem then mood; tags do not, so
`tag:mood::perfect` is every perfect across all seven stems, which no deck
corresponds to. They matter for a second reason: importing an updated deck
does not move cards that already exist, so the tags are what make refiling an
already-imported collection a search (`tag:stem::d-pael tag:mood::perfect` →
Change Deck) rather than a hunt.

A `lemma` has to be unique across the three files, since it is half of each
note's id. The subdeck is not part of that id, so cards can be refiled in Anki
without orphaning their history — and conversely, re-importing does not move
cards that are already filed somewhere.

To study one direction only, suspend the other card type in Anki: browse by
`card:"Gloss -> Aramaic"`, select all and suspend.

Re-importing an updated deck updates the existing cards and keeps their review
history, since note ids come from the chapter and the first vocalization.

## Building

```sh
make
```

| target | output |
|---|---|
| `make` | `Onqelos-Regular.ttf`, then `targumic-aramaic.apkg` |
| `make proof` | `vocab-proof.pdf` — the vocabulary, a page per chapter (needs `hb-view` on PATH — `brew install harfbuzz`) |
| `make check` | report an ambiguous gloss, or a spelling that disagrees with its transliteration |
| `make clean` | remove generated files |
| `make distclean` | also remove the downloaded base font |

The build scripts driving these targets are in `scripts/`.

## Adding vocabulary

All of it lives in `vocabulary.yaml`, a list of chapters:

```yaml
- chapter: 1
  entries:
    - aramaic: [גֻוברָא, גַברָא]
      vocalization: [gubrā, gabrā]
      gloss: man
      pos: noun
      notes: (sometimes gabrā).
      hebrew: ʔîš
```

- Each chapter becomes its own subdeck. `chapter` is a lesson number, or a
  label for material that is not a numbered lesson (`Appendix - Genesis
  12-16`); labelled chapters come last. Chapter order fixes the deck ids and
  the first vocalization of an entry fixes its note id, so reordering either
  orphans review history.
- `aramaic` and `vocalization` are parallel lists, so the nth spelling goes
  with the nth transliteration. A word spelled several ways but pronounced one
  way gives a single vocalization for all of its spellings.
- `gloss` is the definition alone; grammatical detail, forms, idioms and
  derived stems belong in `notes`. It is required, and `pos`, `notes` and
  `hebrew` may be left out.
- `hebrew` is the equivalent the textbook glossary gives. It is a field of its
  own rather than prose so it can be read on its own; the card shows it after
  the notes.

`aramaic` is Hebrew with ordinary Tiberian pointing, which the font
renders as Babylonian supralinear signs. Three conventions:

- Put the vowel on the consonant it follows and leave any mater bare: `yomā` is
  יֹומָא, not the usual Tiberian יוֹמָא.
- Write a doubled consonant once since there is no dagesh in the Babylonian
  system (i.e. `ʕammā` = עַמָא).
- Sheva only where the transliteration has `ǝ` (vocalized); a consonant that
  merely closes a syllable stays bare. `malkā` = מַלכָא, but `malkǝtā` = מַלכְתָא.

`make proof` is the way to check an entry after editing it. `make check`
enforces the rules above: it reports a gloss shared within a chapter, and
compares every spelling with its transliteration twice over — the vowel marks
in order, and then the consonants, allowing for matres and for a doubled
consonant being written once — so a mark left off or a wrong letter is caught.

## Typing the pointing

Any Hebrew keyboard will do — the font redraws each Tiberian mark as its
Babylonian counterpart and moves it above the letter.

| sign | type | also accepts |
|---|---|---|
| a | patah | segol, hataf patah, hataf segol |
| ā | qamats | |
| e | tsere | |
| i | hiriq | |
| o | holam | holam haser, qamats qatan, hataf qamats |
| u | qubuts | |
| ǝ | sheva | |

Dagesh, rafe, shin/sin dots, meteg and the accents have no sign here and render
as nothing, so pasted Tiberian text loses them quietly. A shuruq is vav +
dagesh, so it arrives as a bare vav — write `u` as a qubuts instead.

To use the font elsewhere, install `Onqelos-Regular.ttf` or declare the
`.woff2` with `@font-face`, and set `direction: rtl`.

Built from [Ezra SIL](https://software.sil.org/ezra/) 2.51, under the OFL.

## License

The code here — `scripts/`, the `Makefile` — is MIT; see [LICENSE](LICENSE).

`Onqelos-Regular.ttf` is **not** MIT. It is a Modified Version of
[Ezra SIL](https://software.sil.org/ezra/), and OFL 1.1 §5 requires a modified
OFL font to be distributed under the OFL and under no other license. The build
writes SIL's copyright notice and the license reference into the font's own
name table, which is where §2 accepts them, and keeps the full text alongside
as `EzraSIL-Licenses.txt`. `targumic-aramaic.apkg` embeds the font, so that
applies to the deck as well.
