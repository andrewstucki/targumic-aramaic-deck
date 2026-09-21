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
