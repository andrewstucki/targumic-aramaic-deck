# Targumic Aramaic deck.
#
#   make           the font and the deck
#   make proof     the vocabulary as a PDF to read or check
#   make clean     drop everything generated (keeps .venv and the base font)

# Dependencies install into a local .venv, created on demand. Override
# PYTHON to use an interpreter you manage yourself, and the venv is skipped.
VENV   := .venv
PYTHON ?= $(VENV)/bin/python
STAMP  := $(VENV)/.installed
ifeq ($(PYTHON),$(VENV)/bin/python)
DEPS := $(STAMP)
endif

FONT  := Onqelos-Regular.ttf
DECK  := targumic-aramaic.apkg
PROOF := vocab-proof.pdf
VOCAB := $(wildcard chapter*.txt)

# Written by scripts/build_font.py alongside the .ttf.
FONT_ARTIFACTS := $(FONT) Onqelos-Regular.woff2 onqelos.fea onqelos-sheet.svg
# Downloaded by it on the first build.
BASE_ARTIFACTS := SILEOT.ttf EzraSIL-Licenses.txt

.PHONY: all font deck proof venv clean distclean help

all: font deck

venv: $(DEPS)

$(STAMP): requirements.txt
	python3 -m venv $(VENV)
	$(VENV)/bin/python -m pip install --quiet --upgrade pip
	$(VENV)/bin/python -m pip install --quiet -r requirements.txt
	@touch $@

font: $(FONT)

# The build script is the only input: it downloads and checksums its own base
# font on first run, so a fresh clone needs nothing else.
$(FONT): scripts/build_font.py $(DEPS)
	$(PYTHON) scripts/build_font.py

deck: $(DECK)

# The deck sets its cards in the font and ships it inside the .apkg, so the
# font has to exist first.
$(DECK): scripts/build_deck.py $(FONT) $(VOCAB) $(DEPS)
	$(PYTHON) scripts/build_deck.py

proof: $(PROOF)

$(PROOF): scripts/proof_sheet.py $(FONT) $(VOCAB) $(DEPS)
	$(PYTHON) scripts/proof_sheet.py

clean:
	rm -f $(DECK) $(PROOF) $(FONT_ARTIFACTS)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

# Also drops the downloaded Ezra SIL, so the next build re-fetches it.
distclean: clean
	rm -f $(BASE_ARTIFACTS)

help:
	@echo 'make           the font and the deck'
	@echo 'make font      $(FONT) (+ woff2, fea, coverage svg)'
	@echo 'make deck      $(DECK)'
	@echo 'make proof     $(PROOF)'
	@echo 'make venv      just the .venv, from requirements.txt'
	@echo 'make clean     remove generated files'
	@echo 'make distclean also remove the downloaded base font'
	@echo
	@echo
	@echo 'Python deps install themselves into .venv. make proof also needs'
	@echo 'hb-view on PATH (brew install harfbuzz).'
