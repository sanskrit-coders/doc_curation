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
- **Generate or split `मूलम्` blocks if missing or coarse.** If the files have no `<details><summary>मूलम्</summary>` blocks (or have coarse blocks that should be split to sense units), use the `text_to_blocks` skill first. Commentary and translation boundaries can also help identify mantra/clause boundaries during splitting.

## Commentary / translation insertion
### Matching & alignment
- **Editorial glosses & layer alignment:** `विश्वास-प्रस्तुतिः` often adds `+++(...)+++` glosses, supplied elliptical verbs, hyphens, and punctuation not present in `मूलम्`. Mask or strip `+++(...)+++` glosses, svaras (`[\u0951-\u0954\u1cd0-\u1cff]`), and nasal/visarga variants when aligning sentence segments or commentary pratīkas across layers (including yaṇ-sandhi restoration `इ/ई → य्`, `उ/ऊ → व्`, `ऋ → र्`), and never split on daṇḍas inside `+++(...)+++`, quotes (`"..."`, `“...”`, `'...'`), or parentheses (`(...)`, `[...]`).

**Block order within each unit cluster (vedic example below):**

1. Optional `<details><summary>*विनियोगः</summary>` (`भास्करोक्त-विनियोगः`, `सायणोक्त-विनियोगः`, etc.) at the top of the unit, **above** `विश्वास-प्रस्तुतिः`.
2. `<details open><summary>विश्वास-प्रस्तुतिः...</summary>`
3. Optional translation blocks (e.g. `<details><summary>Houben</summary>`, `<details><summary>त्रिभुवनः</summary>`) placed **above** `<details><summary>मूलम्</summary>` (and below `विश्वास-प्रस्तुतिः`).
4. `<details><summary>मूलम्</summary>`
5. Sanskrit commentary blocks (`<details><summary>भट्टभास्कर-टीका</summary>`, `<details><summary>सायण-टीका</summary>`, `<details><summary>टीका</summary>`, etc.) placed **below** `<details><summary>मूलम्</summary>`.

A similar pattern holds elsewhere.

- **Cross-recension alignment:** When interleaving a translation based on a different recension (e.g. Sāyaṇa pāṭha vs. Drāviḍa pāṭha), align by parallel mantra/clause boundaries while leaving the host file's `मूलम्` and `विश्वास-प्रस्तुतिः` text unchanged.


### Splitting
- **Distributing multi-sentence commentary across fine `मूलम्` blocks:** When commentary blocks span multiple `मूलम्` blocks, split commentary sentences quote-safely (respecting quotes and parentheses so quoted mantras with internal `।`/`॥` are not broken) and align them monotonically to the `मूलम्` blocks using pratīka matching (`... इति`, quoted phrases, and normalized Devanagari stems).
- **Viniyoga separation:** In Vedic commentaries (Bhaṭṭa Bhāskara, Sāyaṇa, etc.), separate leading ritual application (viniyoga) statements at the start of commentary blocks into `<details><summary>भास्करोक्त-विनियोगः</summary>` / `<details><summary>सायणोक्त-विनियोगः</summary>` placed above the corresponding `विश्वास-प्रस्तुतिः` block, and keep trailing verse summaries in `<details><summary>विनियोगसङ्ग्रहः</summary>`.
  - The same applies to **avatArikA separation** in other cases.

### When the source quotes the core text (source-driven re-segmentation)
When the incoming commentary presents the core text passage by passage (each passage quoted, then explained), its quotes are the **segmentation authority**: every quoted core-text passage opens a new group, and all host layers are re-cut — split or merged — at those boundaries so that each group treats the same unit of text. New layers (presentation + incoming commentary) come from the source; host layers (`मूलम्`, existing commentaries) are only re-cut, never rewritten.
- **Core-text quotes vs inline citations:** only quotes of the host core text open groups. Citations of other texts, pūrvapakṣa pratīkas, and quotes of other commentaries stay inline inside the commentary block with their `>` markers kept. Test: a group needs host `मूलम्` to cut — a quote with no host counterpart cannot be a group.
- **Pre-block:** source prose before the first quote (introduction, often ending in a lead-in) becomes a commentary-only block placed before the first group, directly under the section heading.
- **Lead-ins stay behind:** a sentence introducing the next quote stays at the end of the preceding commentary block.
- **Headings:** a source heading opening a commentary block is hoisted to a real `###` heading immediately before the group's `विश्वास-प्रस्तुतिः` (one blank line before, none between); a heading after prose has begun stays bold inside the block (`**name॥**` plus hard break). A source heading already mirrored by the host's own `##` is dropped (its label may still be hoisted as `###`). No commentary block may start or end with a bold heading.
- **Empty layer:** if the source has no prose for a quote (e.g. only a colophon follows), omit that layer's block for the group rather than leaving an empty block. Colophons and end markers keep the host's existing rendering.
- **Verse markers** stay inside `मूलम्` where they fall, even mid-block after a merge; every marker remains present exactly once. Fidelity beats alignment.
- **Never rstrip** source prose lines: trailing double spaces are hard breaks, one clause per line.

### Build technique (no retyping, ever)
- Work from the source file plus a saved copy of the pre-change host page (back it up before overwriting); once installed, the page is already re-cut and the script is not re-runnable.
- Use a build script: slice the source by **line ranges**; split host blocks with `split_seq(text, markers)` where each marker is asserted unique (`text.count(marker) == 1`).
- If a split point is hidden by sandhi, restore the sandhi **only in the `मूलम्` being split**, never globally.

### Verification checklist
1. **Coverage**: every source content line appears verbatim in the page after stripping `>`, surrounding quotes, and heading markers → expect `missing: []`.
2. `<details>` count == `</details>` count.
3. Summary census matches intent; every `विश्वास-प्रस्तुतिः` block `open`.
4. Host sections not being edited are byte-identical before/after.
5. No stray sentinel text (e.g. `None`).
6. Structural lint: block order within each group; no empty blocks; no commentary block starts or ends with a `**…॥**` heading; verse markers all still present, each once.

### Footnotes & endnotes inside inserted `<details>` blocks
Place any short footnotes/endnotes belonging to a translated segment inside the **same** `<details><summary><TranslatorName/ CommentatorName></summary>` block (and place section/anuvāka introductory notes in a `<details><summary><TranslatorName/ CommentatorName></summary>` block at the start of that section/anuvāka). Replace Markdown footnote syntax (`[^32]`) by removing the `^` (e.g. `[32]`), so that the notes render inline inside the `<details>` block rather than being hoisted by the Markdown renderer to the bottom of the page outside the `<details>` block.

However, longer footnotes should be placed in an adjascent `<details><summary><TranslatorName/ CommentatorName> - Note</summary>` block.

### Sanskrit commentaries (ṭīkā)
If you are interleaving a Sanskrit commentary where a rough alignment is explicitly allowed by the prompt, call:

```python
interleaver.interleave_TIkA_below_mUla(dest_file, commentary_file)
```
Both arguments are **file paths (str)**, not `MdFile` objects — the function calls `open()` internally. Note that `interleaver.py` matches `<details><summary>टीका</summary>` by default (`TIKA_RE` / `TIKA_FMT`); when a specific summary title (such as `भट्टभास्कर-टीका` or `सायण-टीका`) is used, set or rename the `<summary>` tag accordingly.

### Translations
Follow the instructions in `~/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/interleave-translation/mUla_and_En_translation/Insert_above_mUla.md` — insert each translated segment wrapped in `<details><summary><TranslatorName></summary>\n\n...\n</details>` directly above its corresponding `<details><summary>मूलम्</summary>` block (and below `विश्वास-प्रस्तुतिः`), preserving the original Sanskrit text verbatim.


## Final report
Report which step you ran and what changed.
