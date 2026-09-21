#!/usr/bin/env python3
"""Check the vocabulary over.

Glosses first: a gloss has to be unique within its chapter, or the card that
asks for the word from its meaning cannot be answered. Then the spelling
against the transliteration, two ways. The vowels: the Hebrew carries one Tiberian mark per transliterated
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
    print(f"{bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
