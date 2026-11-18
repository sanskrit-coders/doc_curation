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

Where the input contains blocks whose `<summary>` starts with `मूलम्` (e.g.
`<details><summary>मूलम्</summary>...</details>`), preserve those blocks and all
text within them verbatim and process only the surrounding text; otherwise,
process all Sanskrit text provided.

## Text cleanup and normalization

- Remove arbitrary print-column / hard-wrapped line breaks inside phrases, and
  separate sentences and syntactic phrases/clauses onto clean Markdown soft-break
  lines (`  \n`, see **Sentence and phrase line breaks** and **Final Markdown
  formatting**).
- Correct obvious typographical errors (e.g. a space in the middle of a word).
- Remove wasteful newlines, like those before `</details>` or between half-verses.
- Preserve intentional styles like **bold** and *italic*.
- Preserve existing headings and paragraphs; edit only what is asked.

## Source errors and doubtful readings

- **Distinct from sandhi separation:** fix clear spelling or grammatical errors
  in the *source words themselves*, suggesting the correction inline as
  `[[OLD|NEW]]` — e.g. `[[prarabvaṁ|prārabdhaṁ]]`.
- Never guess at illegible text: mark the smallest span (`…[[??]]`) and move on.
- Check `[[Pnnn]]` page markers against the printed folio, if one is provided —
  PDF/book offsets drift between volumes and even within one volume.

## Sanskrit hyphenation

Apply to every Sanskrit segment of the text — Devanagari or non-Devanagari
(romanized/IAST, Kannada, etc.) — even when embedded inside English or
other-language prose/words; those surrounding languages are never hyphenated.

Hyphenate everything outside `मूलम्`.* details blocks (unless explicitly asked to
process bare or `मूलम्` text). Hyphenate only after your editorial fixes are
settled — word fixes change where boundaries fall.

### Definitions and core principles

1. **Word or stem boundary:** The point where two words or stems are joined
   (possibly, though not always, involving sandhi) without a space or hyphen —
   the character sequence spanning the end of the first word/stem and the
   beginning of the second.
2. **The separation principle:** Identify separable boundaries and insert the
   right separator — a **hyphen (`-`)** inside compounds (`samāsa`, e.g.
   `पुण्य-पापैः`, `मध्व्-अरिः`) and a **space (` `)** for all other separable
   word joints (e.g. `इत्य् एवम्`, `रामो ऽस्ति`).
3. **Cardinal rule — never revert sandhi:** Split the *result* of the sandhi,
   do not undo it.
4. **Rule of precedence — non-separability is absolute (veto rule):**
   Non-separation rules **always** take precedence over separation rules. **If a
   boundary is non-separable, you MUST NOT split it for any reason, even if the
   words form a compound (`samāsa`).**

### Boundary types and examples

**A. Non-separable boundaries (MUST NOT be split):**

- **Vowel lengthening (`dīrgha` sandhi):** Two vowels merge into a single long
  vowel (`आ`, `ई`, `ऊ`, `ॠ`).
  - `दया + आर्द्र → दयार्द्र` (boundary `या` is non-separable).
  - `अपि + इच्छा → अपीच्छा` (boundary `पी` is non-separable).
  - **Crucial compound example:** `धर्म + अर्थ → धर्मार्थ` (`dīrgha` sandhi
    inside a compound **must remain `धर्मार्थ`**, never `धर्म-अर्थ` / `dharmArtha`).
  - **Error case study:** `स्वप्रकाशाद्वितीय` (from `स्वप्रकाश + अद्वितीय`)
    **must remain `स्वप्रकाशाद्वितीय`**, NOT `स्वप्रकाश-अद्वितीय`.
- **Vowel combination (`guṇa` / `vṛddhi` sandhi):** Two vowels merge into a new,
  single vowel (`ए`, `ओ`, `ऐ`, `औ`).
  - `महा + उत्सव → महोत्सव` (boundary `हो` is non-separable).
  - `राम + इति → रामेति` (boundary `मे` is non-separable).
  - `सदा + एव → सदैव` (boundary `दै` is non-separable).

**B. Separable boundaries (MUST be split unless vetoed above):**

- **Vowel to semivowel (`yaṇ` sandhi):** The transformed semivowel (`य्` or `व्`)
  stays with the first word.
  - `इति + एवम् → इत्येवम्` → `इत्य् एवम्` (`इ` became `य्`; `य्` is kept).
  - `मधु + अरिः → मध्वरिः` → `मध्व्-अरिः`.
- **Visarga (`ः`) sandhi:**
  - `visarga` to `ो`: `रामः + अस्ति → रामोऽस्ति` → `रामो ऽस्ति` (the avagraha
    `ऽ` is part of the boundary; keep it attached to the right word).
  - `visarga` to `र्`: `दुः + प्रकृतेः + अस्य → दुष्प्रकृतेरस्य` →
    `दुष्प्रकृतेर् अस्य`.
  - `visarga` to `स्/श्/ष्`: `नमः + ते → नमस्ते` → `नमस् ते`.
- **Final `म्` before a vowel:** Separate with a space.
  - `फलम् + अश्नुते → फलमश्नुते` → `फलम् अश्नुते`.
  - `अर्थम् + इति → अर्थमिति` → `अर्थम् इति`.
- **Consonant assimilation:**
  - `तत् + हि → तद्धि` → `तद् धि`.
- **Plain `samāsa` concatenation:** Compounds without a non-separable vowel
  merger split with `-` (e.g. `पुण्य-पापैः`).

### Processing algorithm

Iterate through each potential word/stem boundary in strict order:

1. **First check (the veto):** Is the boundary a non-separable `dīrgha`,
   `guṇa`, or `vṛddhi` sandhi? If **YES**, do nothing and move to the next
   boundary.
2. **Second check (separation):** Is it one of the separable types above (or
   plain compound concatenation)? If **NO**, do nothing and move on.
3. **Apply separator:** Insert `-` if the words form a compound (`samāsa`, e.g.
   `पुण्य-पापैः`, `मध्व्-अरिः`), or a space (` `) for all other separable cases
   (e.g. `इत्य् एवम्`).

### Sentence and phrase line breaks

In Sanskrit prose (commentaries and multi-clause `विश्वास-प्रस्तुतिः` / prose
blocks), separate sentences and distinct syntactic phrases/clauses onto their own
lines ended with two trailing spaces (`  `, Markdown soft break). Use blank
lines (`\n\n`) only between distinct paragraphs, blockquotes (`>`), or blocks —
never insert blank lines between every sentence inside one paragraph.

- **Sentence boundaries within a paragraph:** Break with `  \n` after `।`, `॥`,
  `?`, `!`, or `;` (keeping any closing quote or immediate citation reference
  attached to the sentence).
- **Syntactic phrase / clause boundaries within a sentence:** Break with `  \n`
  at natural sense-unit boundaries (matching curated `rAmAnujIya` formatting):
  - **Absolutive / gerundial phrases (`-त्वा`, `-य`):** e.g.
    `तीर्थे गत्वा,  \nशुचौ देशे, पादौ प्रक्षाल्य,  \nआचम्य,`
  - **Causal ablatives (`-त्वात्`, `-आत्`) and reason clauses:** e.g.
    `... सापेक्षत्वात्  \nतद्-अप्रतिपत्त्या प्रसिद्धि-प्राचुर्यस्य सापवादत्वात् ।`
  - **Locative absolutes (*sati saptamī*) and participial phrases (`-अन्`,
    `-मानः`):** e.g.
    `... **प्रकाशितासु**  \nसर्वैर् अपि ... **अशक्यतां बुद्ध्वा**  \nनिवृत्तोद्योगः ... **उपालभते** –`
  - **Quotative (`इति`), correlative (`यत्`/`तत्`), and comma/dash-delimited
    clauses:** e.g. `अर्थान्तर-परिग्रहः अनुपपन्नः इति,  \nभाष्यादिषु स्थापितम् ।`
  - **Long parallel modifiers or compound chains:** break before distinct
    predicates/appositives or at major `--`/`–` boundaries when a long chain
    spans multiple clauses (e.g. `जीवात्मनः स्वरूपं  \nदेव-मनुष्यादि-प्रकृति-परिणाम-विशेष-रूप--  \nनाना-विध--**भेद-रहितं**  \nज्ञानानन्दैक-गुणम्।`).
- **Keep intact (do not over-split):**
  - Leave short single-clause sentences on one line.
  - Never break inside a compound unit (unless at a major `--`/`–` sub-phrase
    seam in a very long chain), across tight noun-modifier pairs, inside
    `[[OLD|NEW]]` / `+++(...)+++`, or so as to strand clitics (`च`, `वा`, `अपि`,
    `एव`, `हि`, `न`, `तु`) alone on a line.
  - Keep verse/śloka pādas one pāda per line ending with `  `.

### Optional sandhi-recreation variants (only when requested)

- **Recreate sandhi:** If the source has an unnatural separation (e.g.
  `अथ स्थापकः अनिरुद्धः`), recreate the correct sandhi (`अथ स्थापको ऽनिरुद्धो`)
  unless punctuation (`।` or `,`) justifies the pause. Never remove a
  pre-existing avagraha (`ऽ`).

### Special hyphenation tools (only when explicitly directed)

**Gemini free Flash (`llm/gemini`)** — non-thorough job, for cursory sanskrit-only
processing:

```python
import os
from doc_curation import llm
from doc_curation.llm import gemini
from doc_curation.md import library

prompt_path = os.path.expanduser("~/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md")
library.apply_function(
    fn=gemini.process_text_chunks_with_keys, dir_path=...,
    prompt=llm.get_prompt(prompt_path),
    dry_run=False,
)
```

To process only details blocks, use `gemini.process_details_with_keys` instead
(using `bare-hyphenator.md` in the same directory when processing `मूलम्` or
standalone detail blocks).

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

Importing it loads a 57 MB wordlist and can take 2–3 minutes cold (agents may time-box it as a hang), so batch a whole directory in one run rather than file by file.

## Final Markdown formatting

- **Quotes & mantras**: quotes under five words in `"..."`; longer quotes and mantras as blockquotes (`>`).
- **Structure**: end verse pāda lines, prose sentence lines within a paragraph, and separated syntactic phrase/clause lines with two trailing spaces (`  `, soft break); use a blank line (`\n\n`) only between paragraphs, blockquotes, or blocks.
- **Page numbers**: format page numbers (e.g. `६४`) as `[[P64]]` at the precise break point, even mid-paragraph.
- **Footnotes**: Markdown footnote syntax `[^n]`, definitions placed next to the paragraph containing the reference, references unique and reflecting the source numbering where possible (e.g. page-12's footnote 1 → `12_1`).
- Preserve `<details><summary>मूलम्...</summary>...</details>` blocks untouched and process only text outside them.

## Report

Report the edits and hyphenation performed, and list anything left for a human
— doubtful readings, missing source images, style rules that did not apply.
