---
name: transliteration-accenting
description: Transliterates Sanskrit across scripts with indic_transliteration (aksharamukha_helper for Tamil, sanscript otherwise) and applies Vedic accent marks (udAtta ᳓ / svarita ᳙) via to_US_accents(). Use when text must be transliterated or accented.
---

Transliterate and accent Sanskrit with `indic_transliteration` (venv: `~/gitland/python_venv`).

## Transliteration

- Tamil: `aksharamukha_helper.transliterate_tamil`
- Everything else: `sanscript.transliterate`

## Accenting

**Import:**
```python
from indic_transliteration.sanscript.schemes.brahmic.accent import to_US_accents
```

`to_US_accents()` converts to the udAtta (᳓) / svarita (᳙) accent scheme. **Accents only make sense for Vedic text** — do not apply to classical Sanskrit.

## Worked example

```python
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic.accent import to_US_accents

# Devanagari Vedic with numeric accents (1=udAtta, 3=svarita) → US accent marks
vedic = "agnimīḷe purohitaṁ"  # or "agnimI1Le purohitaM3"
accented = to_US_accents(sanscript.transliterate(vedic, sanscript.DEVANAGARI, sanscript.SLP1))
# → "agnimīḷe purohitaṁ" with ᳓/᳙ marks

# Scheme parameter: use sanscript.DEVANAGARI, sanscript.SLP1, sanscript.IAST, etc.
# Always specify source and target schemes explicitly.
```
