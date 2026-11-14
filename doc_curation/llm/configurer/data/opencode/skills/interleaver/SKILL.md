---
name: interleaver
description: Interleaves translations or commentaries into Markdown files containing mUlam blocks, generating mUlam blocks first when missing. Use when a translation or ṭīkā must be placed alongside the Sanskrit mUlam in a file.
---

Interleave translations or commentaries into the Markdown files you are given.
In doing this, heed what has been said in the `md-processing` skill.


**Required imports:**
```python
from doc_curation.md.content_processor.commentary import interleaver
```

## Preparation
- **Generate mUlam blocks if missing.** If the files have no `<details><summary>मूलम्</summary>` blocks, use the `text_to_blocks` skill to create them first.

## Commentary/ translation insertion
- **Editorial glosses & layer alignment:** `विश्वास-प्रस्तुतिः` often adds `+++(...)+++` glosses, supplied elliptical verbs, hyphens, and punctuation not present in `मूलम्`. Mask or strip `+++(...)+++` glosses and svaras (`[\u0951-\u0954\u1cd0-\u1cff]`) when aligning sentence segments or commentary pratīkas across layers, and never split on daṇḍas inside `+++(...)+++`, quotes, or parentheses.

### Sanskrit commentaries (ṭīkā) 
If you are interleaving a sanskrit commentary where a rough alignment, is explicitly allowed by the prompt, call:

```python
interleaver.interleave_TIkA_below_mUla(dest_file, commentary_file)
```
Both arguments are **file paths (str)**, not `MdFile` objects — the function calls `open()` internally.


### Translations
**Otherwise (translations above mUlam).** Follow the instructions in `~/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/interleave-translation/mUla_and_En_translation/Insert_above_mUla.md` — insert each translated segment directly above its corresponding `<details><summary>मूलम्</summary>` block, preserving the original Sanskrit text verbatim.

Report which step you ran and what changed.
