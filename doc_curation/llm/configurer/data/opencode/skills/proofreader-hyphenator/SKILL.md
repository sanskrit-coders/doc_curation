---
name: proofreader-hyphenator
description: >
  Proofreads and edits Markdown (cleanup, page markers, footnotes, doubtful
  readings) and hyphenates its Sanskrit — a space at separable word joints and
  a hyphen inside samAsa-sama compounds — including Sanskrit embedded within
  other-language text. Use for scanned/OCR'd or newly converted Markdown, or
  whenever you're asked to proofread anything or hyphenate sanskrit.
---

Proofread and edit the given Markdown (possibly with the aid of a parallel scan
PDF), then hyphenate its Sanskrit — including Sanskrit embedded within text in
other languages.

## Text cleanup and normalization

- Remove hard-wrapped line breaks to create continuous paragraphs.
- Correct obvious typographical errors (e.g. a space in the middle of a word).
- Remove wasteful newlines, like those before `</details>` or between half-verses.
- Preserve intentional styles like **bold** and *italic*.
- Preserve existing headings and paragraphs; edit only what is asked.

## Source errors and doubtful readings

- Fix clear spelling or grammar errors in the *source words* themselves,
  suggesting the correction inline as `[[OLD|NEW]]` — e.g. `[[prarabvaṁ|prārabdhaṁ]]`.
- Never guess at illegible text: mark the smallest span (`…[[??]]`) and move on.
- Check `[[Pnnn]]` page markers against the printed folio, if one is provided —
  PDF/book offsets drift between volumes and even within one volume.

## Sanskrit hyphenation

Apply to every Sanskrit segment of the text — Devanagari or romanized — even when
it is embedded inside English or other-language prose/ words; those surrounding
languages are never hyphenated.

Hyphenate everything outside `मूलम्`.* details blocks: insert a space at
separable word joints and a hyphen inside compounds, but only at *separable*
boundaries.

- **Never revert sandhi** — split the *result* of the sandhi, do not undo it.
  Non-separable mergers (dIrgha, guNa, vRddhi — `dharmArtha`, `mahotsava`,
  `sadaiva`) stay joined even inside a samAsa.
- Hyphenate only after your editorial fixes are settled — word fixes change
  where boundaries fall.
- More rules: `~/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md`.

### Special hyphenation tools (only when explicitly directed)

**Gemini free Flash (`llm/gemini`)** — non-thorough job, for cursory sanskrit-only
processing:

```python
from doc_curation import llm
from doc_curation.llm import gemini
from doc_curation.md import library

library.apply_function(
    fn=gemini.process_text_chunks_with_keys, dir_path=...,
    prompt=llm.get_prompt("~/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md"),
    dry_run=False,
)
```

To process only details blocks, use `gemini.process_details_with_keys` instead.

**Heuristic hyphenator** — approximate, with some errors:

```python
from doc_curation.sanskrit.hyphenator import hyphene
```

`hyphene(text)` implements the split rules without an LLM: space at word
joints, hyphen at samAsa joints. Do not apply it to headings, frontmatter, or
`<details>` content. Applied over a directory:

```python
from doc_curation.md import library
library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: hyphene(c))
```

Importing it loads a 57 MB wordlist and can take two-plus minutes cold, so batch a whole directory in one run rather than file by file.

## Final Markdown formatting

- **Quotes & mantras**: quotes under five words in `"..."`; longer quotes and mantras as blockquotes (`>`).
- **Structure**: end verse lines with two trailing spaces (soft break); blank line between paragraphs.
- **Page numbers**: format page numbers (e.g. `६४`) as `[[P64]]` at the precise break point, even mid-paragraph.
- **Footnotes**: Markdown footnote syntax `[^n]`, definitions placed next to the paragraph containing the reference, references unique and reflecting the source numbering where possible (e.g. page-12's footnote 1 → `12_1`).

## Report

Report the edits and hyphenation performed, and list anything left for a human
— doubtful readings, missing source images, style rules that did not apply.
