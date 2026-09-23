#!/usr/bin/env python3
"""Check the vocabulary and the paradigms over.

Glosses first: a gloss has to be unique within its chapter, or the card that
asks for the word from its meaning cannot be answered. Then the spelling
against the transliteration, two ways. Then nouns.yaml is loaded, which
validates it and re-derives every shape from the example beside it. The vowels: the Hebrew carries one Tiberian mark per transliterated
vowel, in the same order, so a disagreement means a mark is missing, doubled or
wrong. The letters: each transliterated consonant appears as its letter, in
order, allowing the two things the orthography requires -- a doubled consonant
is written once, and a long vowel may be carried by a mater.

Exits non-zero when anything disagrees, so it can gate a build.
"""
import functools
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paradigms
import vocab

POINT = {"ַ": "a", "ֶ": "a", "ֲ": "a", "ֱ": "a",
         "ָ": "ā", "ֳ": "o", "ֵ": "e", "ִ": "i",
         "ֹ": "o", "ֺ": "o", "ֻ": "u", "ְ": "ǝ"}
VOWEL = {"a": "a", "ā": "ā", "e": "e", "i": "i", "o": "o",
         "u": "u", "ǝ": "ǝ", "ə": "ǝ"}


def heb_vowels(s):
    return [POINT[c] for c in s if c in POINT]


def tr_vowels(s):
    """Vowels in order, ignoring the stress accents the textbook prints."""
    plain = "".join(c for c in unicodedata.normalize("NFD", s)
                    if c not in "́̀")
    return [VOWEL[c] for c in unicodedata.normalize("NFC", plain)
            if c in VOWEL]


def agree(heb, tr):
    """Equal, allowing a qamats to stand for either ā or o."""
    return len(heb) == len(tr) and all(
        h == t or (h == "ā" and t == "o") for h, t in zip(heb, tr))


CONS = {"ʔ": "א", "b": "ב", "g": "ג", "d": "ד", "h": "ה", "w": "ו", "z": "ז",
        "ḥ": "ח", "ṭ": "ט", "y": "י", "k": "כ", "ḵ": "כ", "l": "ל", "m": "מ",
        "n": "נ", "s": "ס", "ʕ": "ע", "p": "פ", "ṣ": "צ", "q": "ק", "r": "ר",
        "š": "ש", "ś": "ש", "t": "ת", "ṯ": "ת"}
FINAL = {"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"}
LONG_MATER = {"e": "י", "i": "י", "o": "ו", "u": "ו"}
VOWELS = set("aāeiouǝ")
END_MATER = "אה"


def base(ch):
    return FINAL.get(ch, ch)


def letters(hebrew):
    """The consonant letters of a spelling, points and maqaf dropped."""
    return [base(c) for c in unicodedata.normalize("NFC", hebrew)
            if "א" <= c <= "ת"]


def plan(translit):
    """-> a list of steps: ("c", letter) for a consonant, ("m", mater) for an
    optional mater a long vowel may license, ("e",) for a word-final vowel."""
    # Drop only the stress accents. An underdot or caron belongs to its
    # letter, and so does the acute of ś, which is held back from the
    # decomposition so the stripping cannot take it.
    s = translit.replace("ś", "\x01").replace("Ś", "\x02")
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if c not in "\u0301\u0300")
    s = unicodedata.normalize("NFC", s)
    s = s.replace("\x01", "ś").replace("\x02", "Ś").replace("-", "")
    steps, i = [], 0
    while i < len(s):
        c = s[i]
        # a proper noun capitalizes its first consonant
        if c not in CONS and c.lower() in CONS:
            c = c.lower()
            s = s[:i] + c + s[i + 1:]
        if c in CONS:
            letter = CONS[c]
            steps.append(("c", letter))
            # a doubled consonant is written once
            if i + 1 < len(s) and s[i + 1] == c:
                i += 1
            i += 1
            continue
        if c in VOWELS:
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if c in LONG_MATER:
                steps.append(("m", LONG_MATER[c]))
            if not nxt:                       # a final vowel takes alef or he
                steps.append(("e",))
            i += 1
            continue
        i += 1                                # anything else is not a letter
    return steps


def matches(translit, hebrew):
    got = letters(hebrew)
    steps = plan(translit)

    @functools.lru_cache(maxsize=None)
    def walk(si, gi):
        if si == len(steps):
            return gi == len(got)
        kind = steps[si][0]
        if kind == "c":
            return (gi < len(got) and got[gi] == steps[si][1]
                    and walk(si + 1, gi + 1))
        if kind == "m":                       # the mater is optional
            if gi < len(got) and got[gi] == steps[si][1] and walk(si + 1, gi + 1):
                return True
            return walk(si + 1, gi)
        if gi < len(got) and got[gi] in END_MATER and walk(si + 1, gi + 1):
            return True
        return walk(si + 1, gi)

    ok = walk(0, 0)
    walk.cache_clear()
    return ok


def check(aramaic, vocalization):
    """-> list of (spelling, transliteration) pairs whose letters disagree."""
    forms = vocalization
    if len(forms) == 1:
        forms = forms * len(aramaic)
    bad = []
    for heb, tr in zip(aramaic, forms):
        hw, tw = heb.split(), tr.split()
        if len(hw) != len(tw):
            bad.append((heb, tr))
            continue
        if not all(matches(t, h) for h, t in zip(hw, tw)):
            bad.append((heb, tr))
    return bad

# an abbreviation, not a geminate: the divine name is written with two yods
ABBREVIATIONS = {"Yy", "Ywy"}


def letters_agree(hebrew, translit):
    """Whether a spelling has the consonants its transliteration asks for."""
    if translit in ABBREVIATIONS:
        return True
    hw, tw = hebrew.split(), translit.split()
    return len(hw) == len(tw) and all(matches(t, h) for h, t in zip(hw, tw))


def duplicate_glosses(number, entries):
    """Glosses more than one entry in a chapter shares.

    The recall card asks for the word from its meaning and the chapter, so two
    entries in one chapter with one gloss make a card that cannot be answered.
    """
    seen = {}
    for entry in entries:
        seen.setdefault(entry["gloss"].lower(), []).append(
            "/".join(entry["vocalization"]))
    return {g: v for g, v in seen.items() if len(v) > 1}


# the transliteration letters a shape writes as C
RADICALS = set("ʔbgdhwzḥṭyklmnsʕpṣqrśštṯḵ")


def unaccented(word):
    """word without its stress mark, which no shape writes.

    Only the acute is taken off; a macron is left to recompose, so that the
    long ā of kǝtábā does not come back as a short a.
    """
    return unicodedata.normalize(
        "NFC", "".join(c for c in unicodedata.normalize("NFD", word)
                       if c not in "\u0301\u0300"))


def skeleton_fits(shape, word):
    """Whether `word` is an instance of `shape`.

    A shape is read against the word position by position: C stands for any
    one consonant, and every other character has to be itself. That checks
    each vowel and each spelled-out affix, while leaving the shape free to
    write a consonant literally where it is not a radical -- the ʔ or y a
    hollow verb puts in place of its middle radical, say.
    """
    word = unaccented(word)
    template = shape.replace("-", "")
    if len(template) != len(word):
        return False
    for t, c in zip(template, word):
        if t == "C":
            if c not in RADICALS:
                return False
        elif t != c:
            return False
    return True


# The book marks stress only where it is not on the last syllable, and that
# happens before an inflectional ending that is unstressed itself. -at, -it,
# -nā and -tā are endings wherever they stand in a perfect, so they are
# enough on their own -- note that bǝnāt ends in -āt and is not one of them.
# A bare -u, -i or -ā is not enough, since the same letter can belong to a
# III-weak root: the -i of the perfect banni carries the stress while the -i
# of the imperative kǝtúbi does not, so there the slot decides. Nothing
# outside the perfect and the imperative is marked, because the imperfect's
# -un, -in and -ān and the participles' nominal endings take the stress.
# An ending retracts the stress when it adds a syllable of its own, so -t
# does not and -tā does, even though the syllable it leaves in front is
# closed either way: bārékt(ā) beside bārekt. Each is tied to the slots that
# can carry it, because the same letters are stem elsewhere -- the -it of
# mannit is the fused i of manni plus a consonantal -t, and man-nit is
# stressed on its last syllable like manni itself, so only a 1cs may take it.
# -tun and -tin add a syllable but are stressed themselves, which the book
# states outright, so they are left out.
STRESS_ENDINGS = {"at": lambda s: "3fs" in s,
                  "it": lambda s: s in ("1cs", "1cs, longer variant"),
                  "nā": lambda s: "1cp" in s,
                  "tā": lambda s: "2ms" in s}
STRESS_SLOTS = {"3mp", "3fp", "1cs", "1cs, longer variant", "fs", "mp", "fp"}
STRESS_MOODS = ("perfect", "imperative")
VOWELS = "aāeēiīoōuūǝ"


def expected_stress(word, paradigm, slot):
    """`word` with the mark the book would put on it, if any."""
    plain = unaccented(word)
    if paradigms.mood(paradigm) not in STRESS_MOODS:
        return plain
    if not (any(plain.endswith(e) and fits(slot)
                for e, fits in STRESS_ENDINGS.items())
            or (slot in STRESS_SLOTS and plain.endswith(("u", "i", "ā")))):
        return plain
    at = [i for i, c in enumerate(plain) if c in VOWELS]
    if len(at) < 2 or plain[at[-2]] == "ǝ":   # a reduced vowel cannot take it
        return plain
    i = at[-2]
    return unicodedata.normalize("NFC", plain[:i + 1] + "\u0301"
                                 + plain[i + 1:])


def check_stress():
    """Every verb form carries the mark its ending and mood call for."""
    bad = 0
    verbs = os.path.join(paradigms.ROOT, "verbs.yaml")
    for group in paradigms.load(verbs):
        for cell in group["cells"]:
            for word in cell["example"].split()[-1].split("/"):
                want = expected_stress(word, group["paradigm"], cell["slot"])
                if word != want:
                    bad += 1
                    print(f"  {paradigms.title(group)} {cell['slot']}: "
                          f"{word} should be stressed {want}")
    return bad


def check_paradigms():
    """Every shape has to fit the example it sits beside, and the other way.

    A verb example carries the pointed Aramaic as well, since the tables print
    no transliteration; the transliteration is the part without Hebrew letters.
    """
    bad = 0
    try:
        groups = paradigms.load_all()
    except ValueError as exc:          # a malformed file, not a wrong shape
        print(f"  {exc}")
        return 1
    for group in groups:
        for cell in group["cells"]:
            shapes = cell["shape"].split("/")
            words = []
            for example in cell["example"].split("/"):
                plain = [w for w in example.split()
                         if not any("\u05d0" <= c <= "\u05ea" for c in w)]
                words.extend(plain[-1:] if plain else [])
            if not words:
                continue
            for shape in shapes:
                if not any(skeleton_fits(shape, w) for w in words):
                    bad += 1
                    print(f"  {paradigms.title(group)}: no example fits "
                          f"{shape} ({cell['example']})")
            for word in words:
                if not any(skeleton_fits(s, word) for s in shapes):
                    bad += 1
                    print(f"  {paradigms.title(group)}: {word} fits no shape "
                          f"({cell['shape']})")
    return bad


def main():
    bad = 0
    for number, entries in vocab.load():
        for gloss, words in duplicate_glosses(number, entries).items():
            bad += 1
            print(f"  {vocab.deck_name(number)}: {', '.join(words)} share the "
                  f"gloss {gloss!r}, so the recall card is ambiguous")
        for i, entry in enumerate(entries, 1):
            spellings = entry["aramaic"]
            forms = entry["vocalization"]
            # one shared vocalization applies to every spelling
            if len(forms) == 1:
                forms = forms * len(spellings)
            for h, t in zip(spellings, forms):
                hv, tv = heb_vowels(h), tr_vowels(t)
                if not agree(hv, tv):
                    bad += 1
                    print(f"  {vocab.deck_name(number)} entry {i}: {t} "
                          f"pointing={''.join(hv) or '-'} "
                          f"expected={''.join(tv)}")
                    print(f"        {h}")
                elif not letters_agree(h, t):
                    bad += 1
                    print(f"  {vocab.deck_name(number)} entry {i}: {t} "
                          f"letters={''.join(letters(h))}")
                    print(f"        {h}")
    bad += check_paradigms()
    bad += check_stress()
    print(f"{bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
