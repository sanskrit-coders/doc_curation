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
- **Generate or split `मूलम्` blocks if missing or coarse.** If the files have no `<details><summary>मूलम्</summary>` blocks (or have coarse blocks that should be split to sense units), use the `text_to_blocks` skill first.


## Commentary / translation insertion
### Matching & alignment
**Editorial glosses & layer alignment:** `विश्वास-प्रस्तुतिः` often adds `+++(...)+++` glosses, supplied elliptical verbs, hyphens, and punctuation not present in `मूलम्`. Mask or strip `+++(...)+++` glosses, svaras (`[\u0951-\u0954\u1cd0-\u1cff]`), and nasal/visarga variants when aligning sentence segments or commentary pratīkas across layers (including yaṇ-sandhi restoration `इ/ई → य्`, `उ/ऊ → व्`, `ऋ → र्`), and never split on daṇḍas inside `+++(...)+++`, quotes (`"..."`, `“...”`, `'...'`), or parentheses (`(...)`, `[...]`).

**Empty layer:** if the source has no commentary for a core text (e.g. only a colophon follows), omit it's commentary block for the group rather than leaving an empty block. 

**Cross-recension alignment:** When interleaving a translation based on a different recension (e.g. Sāyaṇa pāṭha vs. Drāviḍa pāṭha), align by parallel mantra/clause boundaries while leaving the host file's `मूलम्` and `विश्वास-प्रस्तुतिः` text unchanged.

**Verifying alignment & digitization artifacts:** Never align solely by translation item numbers—verify lexical/semantic correspondence against the Sanskrit so shifted, misplaced, or duplicated translation passages are caught. Check section-level `> *Note:*` blocks carefully (print/OCR sources often leave the introductory note for section `N+1` at the end of section `N`, or duplicate an inline footnote) and place each note only at the section or block it actually introduces.

#### Sanskrit commentary - rough alignment
If you are interleaving a Sanskrit commentary where a rough alignment is explicitly allowed by the prompt, call:

```python
interleaver.interleave_TIkA_below_mUla(dest_file, commentary_file)
```
Both arguments are **file paths (str)**, not `MdFile` objects — the function calls `open()` internally. Note that `interleaver.py` matches `<details><summary>टीका</summary>` by default (`TIKA_RE` / `TIKA_FMT`); when a specific summary title (such as `भट्टभास्कर-टीका` or `सायण-टीका`) is used, set or rename the `<summary>` tag accordingly.


### Order
**Block order within each unit cluster (vedic example below):**

1. Optional `<details><summary>*विनियोगः</summary>` (`भास्करोक्त-विनियोगः`, `सायणोक्त-विनियोगः`, `त्रिभुवनः - विनियोगः`, etc.) at the top of the unit, **above** `विश्वास-प्रस्तुतिः` (or above an included mantra's `js_include`).
2. `<details open><summary>विश्वास-प्रस्तुतिः...</summary>`
3. Optional translation blocks (e.g. `<details><summary>Houben</summary>`, `<details><summary>त्रिभुवनः</summary>`) placed **above** `<details><summary>मूलम्</summary>` (and below `विश्वास-प्रस्तुतिः`).
4. `<details><summary>मूलम्</summary>`
5. Sanskrit commentary blocks (`<details><summary>भट्टभास्कर-टीका</summary>`, `<details><summary>सायण-टीका</summary>`, `<details><summary>टीका</summary>`, etc.) placed **below** `<details><summary>मूलम्</summary>`.

A similar pattern holds elsewhere.  
Unless specified otherwise, insert each translated segment directly above its corresponding `<details><summary>मूलम्</summary>` block (and below `विश्वास-प्रस्तुतिः`), preserving the original Sanskrit text verbatim.  
Commentaries are inserted after mUla.

### Block naming
Unless specified otherwise (in the prompt or surrounding context), translations and commentaries are wrapped in `<details><summary><AuthorName></summary>\n\n...\n</details>`

### Commentary Splitting
- Core Text splitting was explained in a previous section.
- **Distributing multi-sentence commentary across fine `मूलम्` blocks:** When commentary blocks span multiple `मूलम्` blocks, split commentary sentences quote-safely (respecting quotes and parentheses so quoted mantras with internal `।`/`॥` are not broken) and align them monotonically to the `मूलम्` blocks using pratīka matching (`... इति`, quoted phrases, and normalized Devanagari stems).

#### Viniyoga and AvatArikA separation
- **Pre-block and Lead-ins:** source prose before the first quote (introduction, often ending in a lead-in) becomes a commentary-only block (with suffix "अवतारिका" or "विनियोगः" as the case may be) placed before the first group, directly under the section heading.
- **Viniyoga separation:** In Vedic commentaries and translations (Bhaṭṭa Bhāskara, Sāyaṇa, Tribhuvana, etc.), separate leading ritual application (viniyoga) statements and genuine ritual/rubric footnotes (`*(Mantra ...)*`, `*(Kaṇḍikā ...)*`, etc., describing sacrificial use or prayer purpose) into `<details><summary>भास्करोक्त-विनियोगः</summary>`, `<details><summary>सायणोक्त-विनियोगः</summary>`, or `<details><summary><Translator> - विनियोगः</summary>` (e.g. `<details><summary>त्रिभुवनः - विनियोगः</summary>`) placed together **above** the corresponding `विश्वास-प्रस्तुतिः` block (or above a `js_include`), stripping the `[P...]` viniyoga marker from the translation block.
  - **Never in yajur-veda `sarvASh_TIkAH` files:** No `*विनियोगः` block may ever be placed in a yajur-veda `sarvASh_TIkAH/` file (viniyoga is ritual/host-specific, whereas `sarvASh_TIkAH/` holds only mantra-intrinsic translations and commentaries). Place `*विनियोगः` blocks only in `sarva-prastutiH/` files (either in the host file above the `js_include` or in a shared ritual `sarva-prastutiH/` file).
  - **Viniyoga vs. Avatārikā vs. pure chandas, and kalpa continuations:** Extract genuine ritual application statements (e.g., `विनियोगः`, `कल्पः`, `जपति`, `जुहोति`, `उपतिष्ठते`, `आदत्ते`, `अभ्यादधाति`, `विनियुज्यते`, explicit ritual/ section/ brick-placement intro such as `हृदयेष्टका` / `षोडशेष्टका` even when followed by a meter note like `अथ सप्तहोतुः हृदयेष्टका आन्तादनुवाकस्य - इन्द्र इति द्विपदा त्रिष्टुप् ॥`) along with any immediately continuing explanatory *kalpa* gloss sentences (e.g. `तदिति स्कन्नमाज्यमुच्यते। ...`) into `*विनियोगः`. Contextual/thematic/stuti lead-ins that state the topic, deity, or praise context before `... इति ॥` / `-` without prescribing ritual action (e.g. `एवमिन्द्रस्यात्मनाऽविभागेन दशहोता स्तुतः, इदानीं इन्द्राभेदेनापि स्तूयते - अन्तः प्रविष्ट इति ॥`, `... स्तौति`, `... स्तूयन्ते`, `इदानीम् ... आह`, `तदेवाह`) should **not** be collapsed into `*-टीका`, nor mislabeled as `*विनियोगः` — mark them as `<details><summary><Author> - अवतारिका</summary>` (e.g. `<details><summary>भट्टभास्करः - अवतारिका</summary>`), placed above `विश्वास-प्रस्तुतिः` (or above the `js_include` when host-flow-specific).
  - **Translator/editorial notes (`त्रिभुवनः - अवतारिका` vs. `त्रिभुवनः - विनियोगः`):** Editorial, text-critical, edition-variant, concordance, and Prapāṭhaka/Anuvāka/Kaṇḍikā numbering notes (e.g. `Sāyaṇa considers this Prapathaka as the third Anuvaka of the VIII Prapathaka. Regular number of the kaṇḍikās have not been given...`, `Hume does not give the Prayer-Mantra.`, `Prapathaka V according to Commentator Bhaṭṭa Bhāskara...`, `*(Mantras)* Identical with the First Anuvaka except for certain changes of tense.`, `*(Mantras)* Peace chanted once more in the Ānandāśrama edition.`, `A Yajus Mantra.`), as well as pure narrative/anecdote introductions without ritual prescription, belong in `<details><summary><Translator> - अवतारिका</summary>` (e.g. `<details><summary>त्रिभुवनः - अवतारिका</summary>`), **not** `- विनियोगः`. If a single note combines editorial/numbering info with a genuine ritual rubric, split them into `<Translator> - अवतारिका` and `<Translator> - विनियोगः` above `विश्वास-प्रस्तुतिः` (closing śānti repetitions belong in `<Translator> - शान्तिपाठः (समाप्तिः)`).
  - For pure meter/chandas-only notes, distinguish **single-ṛk** vs. **multi-ṛk / group-level**: pure chandas notes that describe only **that single ṛk/mantra** (`त्रिपदा त्रिष्टुप् ॥`, `गायत्री ॥`, `प्रथमा षट्पदा जगती ।`, etc.) stay inside that mantra's `*-टीका`; by contrast, chandas or group lead-ins that talk about **multiple ṛks/mantras or a whole section/sūkta** (e.g. `वेदेत्यादयः तिस्रस्त्रिष्टुभः ॥`, `यो देवेभ्य इत्याद्ये अनुष्टुभौ ॥ अधुना स एव आदित्वो वर्ण्यते ।`, `अतः परं तिस्रो गायत्र्यः - आ यस्मिन्निति ॥`, `सर्वास्त्रिष्टुभः, विशेषो वक्ष्यते ।`) do **not** belong inside a single mantra's `*-टीका` (nor inside any `sarvASh_TIkAH/` file) — extract them into `<details><summary><Author> - अवतारिका</summary>` placed above `विश्वास-प्रस्तुतिः` (in the host file right above the `js_include` of the first mantra of that group when individual ṛks are included from `sarvASh_TIkAH/`).


#### Trailing summaries
Keep trailing verse summaries in `<details><summary>विनियोगसङ्ग्रहः</summary>`.

#### Footnotes & endnotes inside `<details>` blocks
Place any short footnotes/endnotes belonging to a translated segment inside the **same** `<details><summary><TranslatorName/ CommentatorName></summary>` block (and place section/anuvāka introductory notes in a `<details><summary><TranslatorName/ CommentatorName></summary>` block at the start of that section/anuvāka). Replace Markdown footnote syntax (`[^32]`) by removing the `^` (e.g. `[32]`), so that the notes render inline inside the `<details>` block rather than being hoisted by the Markdown renderer to the bottom of the page outside the `<details>` block.

However, longer footnotes should be placed in an adjascent `<details><summary><TranslatorName/ CommentatorName> - Note</summary>` block.


### Include directives
**`js_include` (`sarvASh_TIkAH` / shared `sarva-prastutiH`) targets:** When a mantra or passage is included via `js_include` from a `sarvASh_TIkAH` file or a shared `sarva-prastutiH` file, place its mantra-intrinsic translation (e.g. `<details><summary>त्रिभुवनः</summary>`) and any missing commentary directly inside that included `sarvASh_TIkAH` / shared `sarva-prastutiH` file (alongside existing translations above `मूलम्` and commentaries below `मूलम्`) — stripping host-specific mantra numbering (`1\. `, `2\. `) and host-context viniyoga footnotes — and run `transformer.prefill_includes`.  

Never place duplicate inline translation/commentary blocks adjacent to the `js_include` in host files, and never place any `*विनियोगः` block inside a yajur-veda `sarvASh_TIkAH/` file;  
only host-context additions (such as a `*विनियोगः` / `त्रिभुवनः - विनियोगः` / `*- अवतारिका` block in a `sarva-prastutiH/` host above the include, or an appended ritual utterance like `Om Peace, Peace, Peace.`) stay in the host file.

### Headings
A source heading opening a commentary block is hoisted to a real `###` heading immediately before the group's `विश्वास-प्रस्तुतिः` (one blank line before, none between); a heading after prose has begun stays bold inside the block (`**name॥**` plus hard break). A source heading already mirrored by the host's own `##` is dropped (its label may still be hoisted as `###`). No commentary block may start or end with a bold heading.
- **Never rstrip** source prose lines: trailing double spaces are hard breaks, one clause per line.

## Build technique (no retyping, ever)
- Work from the source file plus a saved copy of the pre-change host page (back it up before overwriting); once installed, the page is already re-cut and the script is not re-runnable.
- Use a build script: slice the source by **line ranges**; split host blocks with `split_seq(text, markers)` where each marker is asserted unique (`text.count(marker) == 1`).
- If a split point is hidden by sandhi, restore the sandhi **only in the `मूलम्` being split**, never globally.

## Specialist model (only when specifically requested)

When explicitly asked to run `/interleaver` with the fine-tuned `Qwen3-14B` Sanskrit interleaver LoRA (`doc_curation/data/models/qwen3-14b-sanskrit-lora/`, Kaggle: `vishvasvasuki/qwen3-14b-sanskrit-proofreader-lora`), use `ProofreaderBackend` and `interleave_helper` — both operate strictly by **0-based JSON indices ("no retyping, ever")**:

1. **Plain translation streams (`doc_curation.llm.translation_matcher`):** Pass `backend=ProofreaderBackend(base_url="https://<tunnel>/v1")` (`backend.generate_content` automatically annotates `TRANSLATION WORDS:` with `[0] w0 [1] w1 ...` word indices matching the model's cursor-alignment training).
2. **Multi-role commentaries & Vedic translations (`doc_curation.llm.proofreader.interleave_helper`):**

```python
from doc_curation.llm.proofreader import INTERLEAVER_SYSTEM_PROMPT, ProofreaderBackend
from doc_curation.llm.proofreader.interleave_helper import (
    assemble_cluster_blocks,
    format_interleave_prompt,
    parse_interleave_json,
    split_quote_safe_segments,
)

backend = ProofreaderBackend(base_url="https://<tunnel>/v1")
segments = split_quote_safe_segments(source_commentary_text)
prompt = format_interleave_prompt(core_mula_list, segments, author_label="भट्टभास्करः", is_sarvash_tikah=is_sarvash_tikah)
raw_json = backend.new_chat(INTERLEAVER_SYSTEM_PROMPT).send_text(prompt)
plan = parse_interleave_json(raw_json, num_cores=len(clusters), num_segments=len(segments))
assembled_md, withheld_viniyogas = assemble_cluster_blocks(
    clusters, segments, plan, author_label="भट्टभास्करः", is_sarvash_tikah=is_sarvash_tikah,
)
```

## Verification checklist
1. **Coverage**: every source content line appears verbatim in the page after stripping `>`, surrounding quotes, and heading markers → expect `missing: []`.
2. `<details>` count == `</details>` count.
3. Summary census matches intent; every `विश्वास-प्रस्तुतिः` block `open`.
4. Host sections not being edited are byte-identical before/after.
5. No stray sentinel text (e.g. `None`).
6. Structural lint: block order within each group; no empty blocks; no commentary block starts or ends with a `**…॥**` heading; verse markers all still present, each once.



## Final report
Report which step you ran and what changed.
