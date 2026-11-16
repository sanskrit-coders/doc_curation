---
name: accenting
description: Applies, converts, checks and repairs Vedic accent marks (US udAtta ᳓ / svarita ᳙, dependent ॒/॑/᳜) with indic_transliteration's accent module, recording provenance for any accent it invents.
---

Apply and evaluate Vedic accent marks (venv: `~/gitland/python_venv`). The helpers all live in one module:

```python
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent
```

## Policy: accents come from a source

- Do not accent classical Sanskrit, and do not invent accents where the source has none — unless explicitly instructed to.
- Match the notation to the block: `विश्वास-प्रस्तुतिः` normally uses **US accents**; `मूलम्` keeps the source's own notation (classically dependent `॒`/`॑`).
- **De-novo accents (यन्त्र-स्वरः)** — when you do insert accents on your own, both of these are mandatory:
  1. append `(यन्त्र-स्वरः)` to that details block name;
  2. add a `पद-पाठः (यान्त्रिकः)` block below the `मूलम्` — one list item per pada, giving its accented form, the source(s) of the accent (e.g. `rv-padapATha`, `shatapatha-brAhmaNa`, "Pāṇini 6.1.xx"), and any doubts you have.

Where to find an accent and how to derive it: `grammar` skill, section 6.

Shape of the result (illustrative — fill provenance from the actual source):

````markdown
<details open><summary>विश्वास-प्रस्तुतिः</summary>

ब्र᳓ह्म स᳓न्धत्तम् +++(मया सह)+++। त᳓न् +++(ब्रह्म)+++ मे जिन्वतम्+++(=प्रीणयतम्)+++ ॥ (यन्त्र-स्वरः)
</details>

<details><summary>मूलम्</summary>

ब्रह्म॒ सन्ध॑त्त॒न्तन्मे॑ जिन्वतम् ।
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- ब्रह्म — ब्र᳓ह्म (*shatapatha-brAhmaNa*, …)
- सन्धत्तम् — स᳓न्धत्तम् (*shatapatha-brAhmaNa*, …)
- तन् — त᳓न् (doubt: पद-स्वरः or वाक्य-स्वरः?)
- मे — मे, unaccented
- जिन्वतम् — जिन्वतम् (*rv-padapATha*…), matching the note
</details>
````

## Changing accent notation

### US accents (᳓ / ᳙)

```python
accent.to_US_accents(text)  # Devanagari assumed
accent.to_US_accents(text, scheme=sanscript.SCHEMES[sanscript.TELUGU])  # other scripts
```

Converts traditional/dependent notation (`॒`/`॑`, or `᳚`/`᳛`) into independent udAtta (᳓) / svarita (᳙) marks; `+++(...)+++` annotations are skipped. The input must already carry dependent accents — unaccented (or already US-accented) text is returned unchanged. `scheme` takes a **scheme object** (`sanscript.SCHEMES[...]`), not an identifier like `sanscript.DEVANAGARI`.

### Dependent accents (॒ / ॑ / ᳜)

```python
accent.add_dependent_accents(text, UDATTA_NEW="", DEP_SVARITA="॑")
```

The inverse of `to_US_accents`: an anudAtta rising to a following accent gets a sannatara (॒), one falling from a preceding udAtta becomes a dependent svarita, and independent svaritas (᳙) are left alone. By default it leaves the udAtta alone as well.

With `UDATTA_NEW=""` and `DEP_SVARITA="॑"` it round-trips classical Yajurveda print:

```python
classical == accent.add_dependent_accents(accent.to_US_accents(classical), UDATTA_NEW="", DEP_SVARITA="॑")
```

## Checking and correcting bad accents
Generally, for correcting accented texts, don't directly alter svara-s (especially in विश्वास-प्रस्तुतिः) -  just make suggestions in the [[OLD|NEW]] format specified in the proofreading skill. Exceptions are noted below.

### Fake accents

Some Vedic texts (e.g. some taittirīya āraṇyaka sections) carry fake accents — typically mechanically applied runs of udAtta. Detect and strip them:

```python
accent.detect_fake_US_accents(text)  # → suspicious runs of >5 consecutive ᳓; empty list = nothing found
accent.strip_accents(text)           # → text with all accent marks removed
```

If you are explicitly asked, you may also spot badly accented US text beyond what the detector finds.

#### Repair policy

1. Remove **all** accents from that `विश्वास-प्रस्तुतिः` block. If accents were already removed there by hand, keep the unaccented text as is.
2. Re-insert accents only when asked — and then follow the de-novo rules in the policy above, so the provenance lands in a `पद-पाठः (यान्त्रिकः)` block.

### Splitting errors

Typical `मूलम्`-block errors are at the beginnings and terminations of split blocks, e.g.

> "सम्मा॑ऽऽसिञ्चन्तु म॒रुत॒स् समिन्द्र॒स् सं बृह॒स्पतिः॑ । सम्मा॒यम॒ग्निस् सि॑ञ्च॒त्वायु॑षा च॒ बले॑न॒ चायु॑ष्मन्तङ् करोत॒ मा" इति।

has a missing svarita at the end. These errors likely arose from faulty splitting by a human. Where an error is found, fix it in the `मूलम्` block and in the corresponding `विश्वास-प्रस्तुतिः` block.
