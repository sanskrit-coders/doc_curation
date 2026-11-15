---
name: accenting
description: Applies, converts, checks and repairs Vedic accent marks (US udAtta ᳓ / svarita ᳙, and dependent ॒/॑/᳜) with indic_transliteration's accent module.
---

Apply and evaluate Vedic accent marks (venv: `~/gitland/python_venv`). The helpers all live in one module:

```python
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent
```

## Changing accent notation
### Accent styles
Match the notation to the block: `विश्वास-प्रस्तुतिः` blocks normally use **US accents**; `मूलम्` blocks keep the source's own notation (classically dependent `॒`/`॑`).


### US accents (᳓ / ᳙)

```python
accent.to_US_accents(text)  # Devanagari assumed
accent.to_US_accents(text, scheme=sanscript.SCHEMES[sanscript.TELUGU])  # other scripts
```

Converts traditional/dependent notation (`॒`/`॑`, or `᳚`/`᳛`) into independent udAtta (᳓) / svarita (᳙) marks; `+++(...)+++` annotations are skipped. Note the input must already carry dependent accents — unaccented (or already US-accented) text is returned unchanged. `scheme` takes a **scheme object** (`sanscript.SCHEMES[...]`), not an identifier like `sanscript.DEVANAGARI`.

### Dependent accents (॒ / ॑ / ᳜)

```python
accent.add_dependent_accents(text, UDATTA_NEW="", DEP_SVARITA="॑")
```

The inverse of `to_US_accents`: an anudAtta rising to a following accent gets a sannatara (॒), one falling from a preceding udAtta becomes a dependent svarita, and independent svaritas (᳙) are left alone. By default it leaves the udAtta alone as well.

With `UDATTA_NEW=""` and `DEP_SVARITA="॑"` it round-trips classical Yajurveda print:

```python
classical == accent.add_dependent_accents(accent.to_US_accents(classical), UDATTA_NEW="", DEP_SVARITA="॑")
```

## Checking and fixing bad accents
### De-novo accents only if asked to
Do not accent classical Sanskrit by yourself, and do not invent accents where the source has none (unless explicitly instructed to).

When you do insert de-novo accents, add a suffix (यन्त्र-स्वरः) to the विश्वास-प्रस्तुतिः block sentence where you do this, and add a पद-पाठः (यान्त्रिकः) block below the मूलम्, where for each पद, as a list item, you provide the accent, and source(s) of the accent (eg. rv-padapATha, shatapatha-brAhmaNa, pANini's rule xyz etc.), plus any doubts you may have.

### Fake accents
Some Vedic texts (e.g. some taittirīya āraṇyaka sections) carry fake accents — typically mechanically applied runs of udAtta. Detect and strip them:

```python
accent.detect_fake_US_accents(text)  # → suspicious runs of >5 consecutive ᳓; empty list = nothing found
accent.strip_accents(text)           # → text with all accent marks removed
```

If you are explicitly asked, you may also spot badly accented US text beyond what the detector finds. 

Repair policy:

1. Remove **all** accents from that `विश्वास-प्रस्तुतिः` block. If accents were already removed there by hand, keep the unaccented text as is.
2. Insert de-novo accents only when specifically requested.

### Splitting errors
Typical `मूलम्`-block errors are at the beginnings and terminations of split blocks, e.g.

> "सम्मा॑ऽऽसिञ्चन्तु म॒रुत॒स् समिन्द्र॒स् सं बृह॒स्पतिः॑ । सम्मा॒यम॒ग्निस् सि॑ञ्च॒त्वायु॑षा च॒ बले॑न॒ चायु॑ष्मन्तङ् करोत॒ मा" इति।

has a missing svarita at the end. These errors likely arose from faulty splitting by a human. Where an error is found, fix it in the `मूलम्` block and in the corresponding `विश्वास-प्रस्तुतिः` block.
