---
name: transliteration-accenting
description: Transliterates Sanskrit across scripts with indic_transliteration (aksharamukha_helper for Tamil, sanscript otherwise) and applies Vedic accent marks (udAtta ᳓ / svarita ᳙) via to_US_accents(). Use when text must be transliterated or accented.
---

Transliterate and accent Sanskrit with `indic_transliteration` (venv: `~/gitland/python_venv`).

## Transliteration

- Tamil: `aksharamukha_helper.transliterate_tamil`
- Everything else: `sanscript.transliterate`

## Accenting

`indic_transliteration/sanscript/schemes/brahmic/accent.py` has `to_US_accents()` to convert to the udAtta (᳓) / svarita (᳙) accent scheme.
