# Targumic Aramaic Anki Deck

This project can be used to generate `targumic-aramaic.apkg`, an Anki package
for the vocabulary found in Lambdin and Huehnergard's *The Aramaic of Targum
Onqelos*.

To add vocabulary to the deck, add a `chapter*.txt` file with the corresponding
vocabulary and re-render the package. The front of each card is the Aramaic
word set in the `Onqelos` font that ships inside the deck. The back adds the
gloss, part of speech and notes, with the transliteration in the corner.

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
| `make clean` | remove generated files |
| `make distclean` | also remove the downloaded base font |

The build scripts driving these targets are in `scripts/`.

## Adding vocabulary

Each entry for vocabulary follows the following format:

```
aramaic | vocalization | gloss. part-of-speech. optional notes
```

- `/` separates variants in either of the first two fields (`gubrā/gabrā`). The
  first vocalization fixes the note id, so do not reorder them.
- The part of speech is found by keyword (`verb`, `noun`, `prep`, …); anything
  after it becomes the notes.
- Blank lines and `#` comments are ignored.

The first field is Hebrew with ordinary Tiberian pointing, which the font
renders as Babylonian supralinear signs. Three conventions:

- Put the vowel on the consonant it follows and leave any mater bare: `yomā` is
  יֹומָא, not the usual Tiberian יוֹמָא.
- Write a doubled consonant once since there is no dagesh in the Babylonian
  system (i.e. `ʕammā` = עַמָא).
- Sheva only where the transliteration has `ǝ` (vocalized); a consonant that
  merely closes a syllable stays bare. `malkā` = מַלכָא, but `malkǝtā` = מַלכְתָא.

`make proof` is the way to check an entry after editing it.

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
