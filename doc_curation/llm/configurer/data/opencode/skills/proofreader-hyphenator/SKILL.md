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
- Insert an omitted sentence-ending daṇḍa (`।`) followed by `  \n` when syntax
  (and `मूलम्` context, if present) unmistakably shows two separate sentences or
  commentary glosses fused without punctuation (never add `।` mid-clause).
- Remove wasteful newlines, like those before `</details>` or between half-verses.
- Preserve intentional styles like **bold** and *italic*.
- Preserve existing titles, headings, and paragraphs; when adding or reorganizing navigation headings (see **Navigation headings** below), build cleanly around existing headings rather than dropping them.

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
3. **Cardinal rule for inline hyphenation — never revert sandhi:** Within a line,
   split the *result* of the sandhi, do not undo it. (Breaking sandhi across a
   syntactic phrase, clause, or quote newline is allowed — see **Sentence and
   phrase line breaks**.)
4. **Rule of precedence — non-separability is absolute inline (veto rule):**
   For inline hyphenation within a line, non-separation rules **always** take
   precedence over separation rules. **If an inline boundary is non-separable,
   you MUST NOT split it with a space or hyphen for any reason, even if the
   words form a compound (`samāsa`).** (Only syntactic clause, quote, or
   sentence newline breaks may undo a fused sandhi.)

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

- **Where to break:** Place a line break at every natural pause/virāma where a
  reader would naturally pause — not a paragraph break. Heuristics: recognise
  clause-boundary markers such as kvānta/lyabanta (`-त्वा`, `-य`) forms, and
  group words sharing the same vibhakti/case role.
- **Sentence boundaries within a paragraph:** Break with `  \n` after `।`, `॥`,
  `?`, `!`, or `;` (keeping any closing quote or immediate citation reference
  attached to the sentence). When a source omits `।` between syntactically
  disjoint sentences or commentary glosses — e.g. commentary on `निर्मिते भवने
  पित्रा यावदच्युतदर्शनम्`: `पित्रा सवित्रा यावद् अच्युतस्य श्री-कृष्णस्य दर्शनं
  तावन् निवसामि ॥` → `पित्रा सवित्रा।  \nयावद् अच्युतस्य श्री-कृष्णस्य दर्शनं तावन्
  निवसामि ॥` (where instrumental `पित्रा सवित्रा` closes the gloss on `निर्मिते`
  and cannot govern the active `निवसामि` clause) — insert the missing `।  \n`.
  Only insert `।` when the syntactic break (incompatible case/verb government
  or `मूलम्` parallel) is clear; for clauses within one sentence, use `  \n`
  without adding `।`.
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
  - **Gloss / meaning restatement (अर्थ-वचनम्):** When a commentary gives a
    word and then its gloss/meaning as a separate utterance, treat them as
    separate sentences/clauses — insert appropriate punctuation (`।`, `,`, `—`,
    as warranted) and `  \n`. E.g. `हे वीर ! दुर्दान्ताः अशिक्षिताः दुरवग्रहाः
    अपरायत्ताः।` → `हे वीर!  \nदुर्दान्ताः अशिक्षिताः।  \nदुरवग्रहाः अपरायत्ताः।`
    (each pair is a term followed by its gloss).
  - **Pratīka-grahaṇa (quoting a symbol/passage):** When introducing a quoted
    pratīka or cited passage (e.g. after `आह`, `निदर्शनमाह`, `उच्यते`), place
    a punctuation marker (`—`, `–`, `:`) and a `  \n` before the quoted text.
    E.g. `तत्र निदर्शनमाह एतैर्गोवृषैर्भिन्नानि...` → `तत्र निदर्शनमाह —  \nएतैर्
    गो-वृषैर् भिन्नानि...`
- **Virāma and sandhi:** `यत्र यत्र विरामः स्वीक्रियते, तत्र तत्र सन्धिः न भवति;
  परन्तु यत्र विरामः न स्वीक्रियते, तत्र अवश्यं सन्धिर्भवति।` — where a pause/virāma
  is taken, do not force sandhi across it; where there is no pause, sandhi must
  hold. A pratīka/quotation break therefore blocks sandhi
  (`तत्र निदर्शनमाह, एतैः...` / `तत्र निदर्शनमाह —  \nएतैः...`, not
  `*निदर्शनमाहैतैः`).
- **Breaking sandhi at phrase / clause / quote newlines:**
  - When a separable seam already sits cleanly at the break, prefer splitting
    without reverting sandhi (`निश्चयादयं` → `निश्चयाद्  \nअयं`,
    `वह्नेर्दाह्यसन्निधौ` → `वह्नेर्  \nदाह्य-सन्निधौ`, `अप्युपपद्यते` →
    `अप्य्  \nउपपद्यते`, `ब्रह्मणोऽभिधेयतया` → `ब्रह्मणो  \nऽभिधेयतया`).
  - When external sandhi (`dīrgha`, `guṇa`, `vṛddhi`, `yaṇ`, or `visarga`)
    fuses two distinct clauses, a `>` blockquote boundary, or a trailing `इति` /
    participial / locative-absolute clause that belongs on its own line, you
    **may break (revert) the sandhi across the newline** (never inline within a
    line):
    - `dīrgha` broken across clause/`इति` breaks: `निश्चिते सतीक्षणादयः` →
      `निश्चिते सति  \nईक्षणादयः`; `जीवस्यानादि...` → `जीवस्य  \nअनादि-कर्म-रूपाविद्या-तिरोहित-स्वरूपस्य`;
      `भवतीति` → `भवति  \nइति शक्यं वक्तुम्,`
    - `guṇa` / `vṛddhi` broken across quote/`इति`/clause breaks:
      `अत्रौदनोपसेचनसूचितोऽत्ता ... उत परमात्मेति सन्दिह्यते` →
      `अत्र\n\n> ओदनोपसेचन-सूचितो ऽत्ता ...\nउत परमात्मा\n\nइति सन्दिह्यते ।`;
      `प्रधानस्याचेतनस्यैवंरूपो` → `प्रधानस्याचेतनस्य  \nएवं-रूपो`
    - `visarga` restored at major clause breaks: `पृष्टो मृत्युस्तस्यार्थस्य` →
      `पृष्टो मृत्युः  \nतस्यार्थस्य`; `परस्य ब्रह्मणश्शरीरतया` →
      `परस्य ब्रह्मणः\n\nशरीरतया`
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

### Special hyphenation tools (only when specifically requested)

> **Recommendation:** Use local `hyphene` (`doc_curation.sanskrit.hyphenator`) for fast clean-text hyphenation; use `Qwen3-14B` (`proofread_text` / `ProofreaderBackend` in `doc_curation.llm.proofreader`, when requested) when OCR cleanup (`[[OLD|NEW]]`) and discourse clause breaks (including cross-newline sandhi restoration) are also needed. See `doc_curation/llm/proofreader/README.md` and `doc_curation/llm/proofreader/distill/README.md`.
>
> **Mandatory random quality check & redo:** Whenever you run `hyphene`, `proofread_text` / `ProofreaderBackend`, or batch `gemini`, inspect a random sample of paragraphs/blocks across the file(s) (and review `git diff` hunks) for merger-veto violations, missed or bad splits (*yaṇ*, *visarga*, final-*m*, compounds), awkward `  \n` clause breaks, missed OCR typos or false `[[OLD|NEW]]` proposals, and untouched `मूलम्` / `+++(...)+++` spans. Redo or hand-correct any subpar passages directly (and fix `doc_curation` if you spot a systematic lexicon/rule gap).

**Distilled local SLP1 neural hyphenator (`doc_curation.sanskrit.hyphenator`)** — fast local ONNX model (`doc_curation/data/models/sanskrit-hyphenator-slp1/hyphenator_slp1.onnx`, `60/60` on `hyphenations.toml`, `~3–16 ms`/sentence via `onnxruntime`, zero GPU/server needed), backed by `<2 ms` memory-mapped `BytesTrie` merger-veto & lexicon witnesses (`lexicon.py`, vocabulary in `doc_curation/llm/proofreader/data/vocabulary/`). Performs hyphenation and optional syntactic clause soft-breaks (`clause_newlines=True/False`) without editorial source-word changes, while preserving `<details><summary>मूलम्...</summary>` blocks, `+++(...)+++` glosses, and Vedic US accents (`᳓`/`᳙`):

```python
from doc_curation.md import library
from doc_curation.md.file import MdFile
from doc_curation.sanskrit.hyphenator import hyphene, hyphenate_word

# Single string or word:
clean_hyphenated = hyphene(text, clause_newlines=False)

# Bulk directory transform:
library.apply_function(
    fn=MdFile.transform, dir_path=dir_path,
    content_transformer=lambda c, *args, **kwargs: hyphene(c, clause_newlines=True),
)
```

## Final Markdown formatting

- **Quotes & mantras**: quotes under five words in `"..."`; longer quotes and mantras as blockquotes (`>`).
- **Structure**: end verse pāda lines, prose sentence lines within a paragraph, and separated syntactic phrase/clause lines with two trailing spaces (`  `, soft break); use a blank line (`\n\n`) only between paragraphs, blockquotes, or blocks.
- **Navigation headings**:
  - **Prose and long articles (outside `<details>`):** Add concise, informative topic-level Markdown headings (`##`, `###`, `####`) to make navigation and browsing easy (and `## A`–`## Z` letter headings for alphabetical indices); leave trivial single-topic notes unsplit.
  - **Respect existing headings:** Keep existing titles and structural headings (e.g. `# Title`, `## Intro`, `## Lecture One`), normalize malformed or out-of-order heading transitions so hierarchy stays strictly monotonic (never skip levels, e.g. `##` → `####`), and nest newly inserted `##` / `###` / `####` subheadings cleanly beneath them.
  - **Placement invariants:** Never insert a heading directly before an unrelated footnote definition (`[^id]:`), a mid-sentence continuation paragraph, a trailing attribution line (e.g. `[First published: ...]`), or joined on the same line cluster as `[[Pnnn]]` without a blank line; if a topic change occurs mid-paragraph, split at a sentence boundary first and re-pair each `[^id]:` definition with the half-paragraph referencing it.
  - **Inside `<details>` blocks:** Never use Markdown `#` headings inside `<details>...</details>` blocks — format internal section labels inside details blocks as bold lines (`**...**  `) instead (and never edit `<details><summary>मूलम्...</summary>` blocks).
- **Page numbers**: format page numbers (e.g. `६४`) as `[[P64]]` at the precise break point, even mid-paragraph.
- **Footnotes**: Markdown footnote syntax `[^n]`, definitions placed next to the paragraph containing the reference, references unique and reflecting the source numbering where possible (e.g. page-12's footnote 1 → `12_1`).
- Preserve `<details><summary>मूलम्...</summary>...</details>` blocks untouched and process only text outside them.

## Specialist & batch LLM tools

**1. Fine-tuned `Qwen3-14B` Sanskrit proofreader LoRA (`doc_curation.llm.proofreader`) — only when specifically requested** — covers the **full skill** when OCR cleanup (`[[OLD|NEW]]` source-error suggestions, `[[??]]` illegible spans, `[[P64]]` page tags, footnotes), discourse-aware syntactic clause soft-breaks (including cross-newline sandhi restoration), and sandhi-preserving hyphenation are needed together (pass `suggest_corrections=False` for hyphenation/formatting only; see `doc_curation/llm/proofreader/README.md`). Local adapter weights live at `doc_curation/data/models/qwen3-14b-sanskrit-lora/` (Kaggle: `vishvasvasuki/qwen3-14b-sanskrit-proofreader-lora`), wrapped with deterministic `मूलम्` masking, inline merger-veto snap-back, and `[[OLD|NEW]]` silent-edit guards (`guards.py`). Use via an OpenAI-compatible `vLLM` Colab/Kaggle tunnel (`proofread_text` or `ProofreaderBackend` with `text_chunker` / `detail_chunker`) or offline Kaggle batch jobs (`kaggle_runner.stage_batch_dataset` / `apply_downloaded_outputs`):

```python
from doc_curation.llm import text_chunker
from doc_curation.llm.proofreader import ProofreaderBackend, build_system_prompt, proofread_text
from doc_curation.md import library

backend = ProofreaderBackend(base_url="https://<tunnel>/v1")

# Single string:
cleaned = proofread_text(raw_md, backend=backend, clause_newlines=True, suggest_corrections=True)

# Whole directory:
prompt = build_system_prompt(clause_newlines=True, suggest_corrections=True)
library.apply_function(
    fn=text_chunker.process_text_chunks, dir_path=dir_path,
    prompt=prompt, backend=backend,
)
```

**2. Gemini free Hydrogen (`llm/gemini`) — can be used at will (but note that its quota may run out)**:

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

## Report

Report the edits and hyphenation performed, which random spot-checks you ran (and any blocks you redid/fixed after tool execution), and list anything left for a human — doubtful readings, missing source images, style rules that did not apply.
