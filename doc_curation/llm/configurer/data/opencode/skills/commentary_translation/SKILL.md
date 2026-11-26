---
name: commentary_translation
description: Interleaves and wraps translations, commentaries, and avatārikās in Markdown files alongside विश्वास-प्रस्तुतिः and मूलम् blocks, including सर्वा अवतारिकाः / सर्वाष् टीकाः wrapper blocks, layer/pāṭha normalization, and cross-recension reuse/deduplication. Use when a translation, ṭīkā, or avatārikā must be aligned alongside core text, wrapped into commentary/avatārikā clusters, or consolidated across recensions.
---

Interleave and wrap translations, avatārikās, and commentaries into the Markdown files you are given.
In doing this, heed what has been said in the `md-processing` skill.


**Required imports:**
```python
from doc_curation.md.content_processor.commentary import helper, interleaver
```

## Preparation
- **Generate or split `मूलम्` blocks if missing or coarse.** If the files have no `<details><summary>मूलम्</summary>` blocks (or have coarse blocks that should be split to sense units), use the `text_to_blocks` skill first (`text_to_vipra_mula_blocks(..., use_local_hyphenator=True)` / local `hyphene` for fast clean-text hyphenation; `Qwen3-14B` `proofread_text` when OCR cleanup & discourse clause breaks are also needed).
- **Local DP aligners vs. `Qwen3-14B` LoRA (`doc_curation/llm/proofreader/README.md`):** Use the zero-GPU local DP aligners by default — `interleave_source_into_markdown(..., backend=None)` (`99.1%` segment-to-core & `100.0%` role in `<3 ms`/segment via Sandhi/Pratīka Viterbi DP) for Sanskrit commentaries, and `translation_matcher.insert_translation_details(..., backend=None)` (`100%` partition validity & `72.4%` span word-F1 in `~34 ms`/batch via Bilingual Monotonic DP) for instant zero-GPU plain-translation alignment; when specifically requested (or when free/idiomatic translations lack lexical anchors), `backend=ProofreaderBackend(...)` reaches `94.4%` span word-F1 (`0.77` words MAE, `68.8%` all-boundaries-exact) on `translation_matcher` and `100.0%` role / `93.8%` cutoff on `commentary_interleaver`.


## Commentary / translation insertion
### Matching & alignment
**Empty layer:** if the source has no commentary for a core text (e.g. only a colophon follows), omit it's commentary block for the group rather than leaving an empty block.

**Verifying alignment & digitization artifacts:** Never align solely by translation item numbers—verify lexical/semantic correspondence against the Sanskrit so shifted, misplaced, or duplicated translation passages are caught. Check section-level `> *Note:*` blocks carefully (print/OCR sources often leave the introductory note for section `N+1` at the end of section `N`, or duplicate an inline footnote) and place each note only at the section or block it actually introduces.

#### Normalization
- **Layer & pratīka alignment:** `विश्वास-प्रस्तुतिः` often adds `+++(...)+++` glosses, supplied elliptical verbs, hyphens, and punctuation not present in `मूलम्`. Mask or strip `+++(...)+++` glosses, svaras (`[\u0951-\u0954\u1cd0-\u1cff]`), and nasal/visarga variants when aligning sentence segments or commentary pratīkas across layers (including yaṇ-sandhi restoration `इ/ई → य्`, `उ/ऊ → व्`, `ऋ → र्`), and never split on daṇḍas inside `+++(...)+++`, quotes (`"..."`, `“...”`, `'...'`), or parentheses (`(...)`, `[...]`).
- **Cross-recension pāṭha comparison:** Before comparing parallel passages across recensions or śākhās (`doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm.normalize_phonetic` / `is_no_patha_bheda`), ignore verse/stanza/kaṇḍikā numbers (`॥२४॥`), punctuation, whitespace/line wraps, `-` hyphens, `**...**`, `+++(...)+++` glosses, inter-word halant+vowel joins (`म् अ` ↔ `म`), `ऽ`/`ऽअ` hiatus orthography, and pure scribal gemination after `र्` (`र्द्ध`↔`र्ध`, `र्म्म`↔`र्म`). Preserve internal pluta digits (`२`/`३`), `ड`/`ळ` and nasal variants, and — for accented texts — US accents (`᳓`/`᳙`) as significant.

#### Cross-recension alignment, reuse & deduplication (`विश्वास-प्रस्तुतिः` vs. `सर्वाष् टीकाः`)
When consolidating parallel passages across recensions or śākhās (Smṛti, Epics, Śāstra, Veda, etc.):

- **Two-part static layout (no separate `mUlam/` dirs):** Shared static trees consist of `vishvAsa-prastutiH/` + `sarvASh_TIkAH/` (do not create or keep separate `mUlam/` directories; put each recension's mūlam inside `sarvASh_TIkAH/` as `<details><summary>मूलम् - <Recension/Śākhā></summary>`).
- **No real pāṭha-bheda (exact normalized text, and matching US accents when accented):** Share and `js_include` **both** `vishvAsa-prastutiH/` (`title="विश्वास-प्रस्तुतिः"`) **and** `sarvASh_TIkAH/` (`title="सर्वाष् टीकाः"`) — or, for shared strict blocks without a separate `sarvASh_TIkAH/` split (e.g. non-Ṛk `yajuH/sarva-prastutiH/`), use a combined `sarva-prastutiH/...md` with `includetitle="false"`. Shared `vishvAsa-prastutiH/` and combined `sarva-prastutiH/` files must use **US accents only** when accented (see the `accenting` skill).
- **Minor pāṭha variant:** Keep `विश्वास-प्रस्तुतिः` **separate/local** in each host (do not share combined `sarva-prastutiH/` on variants) and merge/`js_include` **only** `sarvASh_TIkAH/` (`title="सर्वाष् टीकाः"`). Inside the shared `sarvASh_TIkAH/` file or `सर्वाष् टीकाः` block, disambiguate variants explicitly:
  - Always qualify recension/śākhā mūlams explicitly as `<summary>मूलम् - <Recension/Śākhā></summary>` (e.g. `मूलम् - द्राविडः`, `मूलम् - शाकलम्`, `मूलम् - शौनकम्`, `मूलम् - माध्यन्दिनम्`, `मूलम् - काण्वम्`, `मूलम् - तैत्तिरीयम्`).
  - Add `<summary>पदपाठः - <Recension/Śākhā></summary>` when present (e.g. `पदपाठः - काण्वः`, `पदपाठः - दयानन्दादि`, `पदपाठः - तैत्तिरीयः`).
  - Qualify colliding commentator titles by recension/śākhā (e.g. `<summary>सायण-टीका (काण्वी)</summary>` when multiple recensions' Sāyaṇa commentaries coexist).
- **Interleaving a different recension into a single host file:** When interleaving a commentary or translation based on another recension (e.g. Sāyaṇa pāṭha vs. Drāviḍa pāṭha) into a single host file, align by parallel verse/mantra/clause boundaries while leaving the host's `मूलम्` and `विश्वास-प्रस्तुतिः` unchanged.
- **Keep `सर्वा अवतारिकाः` local & align unit granularity:** Keep `<details><summary>सर्वा अवतारिकाः</summary>` (`*- अवतारिका`, `*विनियोगः`) local per recension/context in the host file above `विश्वास-प्रस्तुतिः`/`js_include`. Align stanza/verse granularity across shared `static` files and update all host includes across repos when splitting or merging units.
- **Propagation & Vedic specifics:** After editing shared hosts or `static/` targets, refresh transitive `js_include` prefills across `vishvAsa` repos (see the `website` skill). For Vedic dedup pipelines, split-hemistich viniyoga rules, and `VedicCorpusCounter` provenance checks, see the `vedic` skill.

#### Sanskrit commentary - alignment engines
1. **Multi-role Vedic & Śāstric interleaving (`interleave_source_into_markdown`, zero retyping):**
   Slices source text quote-safely (never cutting inside `"..."`, `“...”`, Sanskrit `'...'`, `(...)`, or `+++...+++`), extracts sandhi-restored pratīkas (`**bold**`, unquoted `... इति`, dash lead-ins, opening headwords, stem-IDF overlap — while masking `'...' इति` sūtra citations), classifies `/commentary_translation` roles (`heading`, `viniyoga` + *kalpa* continuations, `avatarika` including multi-ṛk *chandas* & edition notes, `tika` including single-ṛk *chandas* notes, `translation`, `note`, `viniyoga_sangraha`), solves global Monotonic Viterbi DP, and runs the 6-point verification checklist automatically:

```python
from doc_curation.llm.proofreader import interleave_source_into_markdown

res = interleave_source_into_markdown(
    host_md,
    source_commentary_text,
    author_label="भट्टभास्करः",
    is_sarvash_tikah=is_sarvash_tikah,
    backend=None,  # Pure local sandhi/pratīka Viterbi DP (no GPU/LLM needed)
)
assert res["verification"]["ok"], res["verification"]
updated_md = res["markdown"]
host_only_viniyogas = res["withheld_viniyogas"]
```

2. **Plain `*-टीका` below `मूलम्` (`interleave_TIkA_below_mUla`):**
   When placing a single-role Sanskrit commentary directly below `<details><summary>मूलम्</summary>` from file paths:

```python
interleaver.interleave_TIkA_below_mUla(dest_file, commentary_file, tika_title="भट्टभास्कर-टीका")
interleaver.verify_sentence_order(dest_file, commentary_file, tika_title="भट्टभास्कर-टीका")
```
Both file arguments are **file paths (str)**, not `MdFile` objects; `tika_title` defaults to `"टीका"` across `interleave_TIkA_below_mUla`, `verify_sentence_order`, `remove_commentary_blocks`, and `realign_TIkA_below_mUla`.

#### Plain translation streams - alignment engine
When placing a plain English/vernacular translation stream above `<details><summary>मूलम्</summary>` (and below `विश्वास-प्रस्तुतिः`) with **zero retyping**, use `doc_curation.llm.translation_matcher.insert_translation_details`. With `generate_fn=None` (default when `backend=None`), it runs the fast local bilingual Monotonic DP aligner (`doc_curation.llm.proofreader.translation_aligner.local_translation_generate_fn` — discourse-pivot, sūtra-number, technical-lexicon, and IAST→SLP1 stem anchors at `~34 ms/batch` with `100%` partition validity):

```python
from doc_curation.llm import translation_matcher

translation_matcher.insert_translation_details(
    dest_md_path,
    translation_md_path,
    backend=None,        # Pure local bilingual Monotonic DP (no GPU/LLM needed)
    generate_fn=None,
    translation_title="Thibaut",  # Custom <AuthorName> summary; defaults to "Translation"
    dry_run=False,
)
```


### Order & cluster anatomy
**Block order within each unit cluster (e.g. Śāstric, Smṛti, Vedānta, or Vedic text):**

1. Optional `<details><summary>सर्वा अवतारिकाः</summary>` (wrapping pre-presentation blocks such as `<details><summary>*- अवतारिका</summary>`, `*- प्रस्तावः`, `*- भूमिका`, `*विनियोगः`, `भास्करोक्त-विनियोगः`, `सायणोक्त-विनियोगः`, `त्रिभुवनः - विनियोगः`, etc.) at the top of the unit, **above** `विश्वास-प्रस्तुतिः` (or above an included `js_include`).
2. `<details open><summary>विश्वास-प्रस्तुतिः...</summary>` (or a `js_include` of `vishvAsa-prastutiH/` with `title="विश्वास-प्रस्तुतिः"`).
3. **By default, wrap non-`विश्वास-प्रस्तुतिः` post-presentation blocks into `<details><summary>सर्वाष् टीकाः</summary>` — especially when there are multiple such blocks** (or use `<div class="js_include collapsed" title="सर्वाष् टीकाः" ...>` when included from `sarvASh_TIkAH/`), ordering the inner blocks as:
   1. Optional translation blocks (e.g. `<details><summary>Houben</summary>`, `<details><summary>त्रिभुवनः</summary>`) placed **above** `<details><summary>मूलम्</summary>` (and below `विश्वास-प्रस्तुतिः`).
   2. `<details><summary>मूलम्</summary>` (plus optional `पद-पाठः` / `पद-पाठः (यान्त्रिकः)`).
   3. Sanskrit commentary blocks (`<details><summary>भट्टभास्कर-टीका</summary>`, `<details><summary>सायण-टीका</summary>`, `<details><summary>टीका</summary>`, etc.) placed **below** `<details><summary>मूलम्</summary>`.

Section-intro blocks (`विस्तारः (द्रष्टुं नोद्यम्)`), explicitly-`open` `विश्वास-टिप्पनी`, and trailing summaries (`विनियोगसङ्ग्रहः`) sit outside individual unit clusters (and stay unwrapped).  
Unless specified otherwise, insert each translated segment directly above its corresponding `<details><summary>मूलम्</summary>` block (and below `विश्वास-प्रस्तुतिः`), preserving the original Sanskrit text verbatim.  
Commentaries are inserted after `मूलम्`.

### Wrapping clusters (`सर्वा अवतारिकाः` / `सर्वाष् टीकाः`)
Applies across **all** commentary-bearing texts (Śāstric, Smṛti, Vedānta, Gītā, Kāvya, Vedic — not Veda-specific):

- **Default wrapping rule:** By default, wrap non-`विश्वास-प्रस्तुतिः` blocks in a cluster into `<details><summary>सर्वाष् टीकाः</summary>` — especially whenever there are multiple post-`विश्वास-प्रस्तुतिः` blocks (e.g. translation + `मूलम्` + `*-टीका`, or multiple commentaries/translations) — and wrap pre-`विश्वास-प्रस्तुतिः` avatārikā/viniyoga/bhūmikā blocks into `<details><summary>सर्वा अवतारिकाः</summary>`.
- Use `doc_curation.md.content_processor.commentary.helper.wrap_commentaries_in_details(..., block_name="सर्वाष् टीकाः", exclude=(r"विश्वास-प्रस्तुति", r"^विनियोगसङ्ग्रहः$"), avatarika_block_name="सर्वा अवतारिकाः", skip_js_includes=True, exclude_open_patterns=(r"^विश्वास-टिप्पनी",))` (or `helper.wrap_vedic_details`, which is a preset alias with those exact defaults). It:
  - treats balanced `js_include` divs as atomic boundaries,
  - splits contiguous commentary vs. avatārikā runs (`DEFAULT_AVATARIKA_PATTERNS`: `अवतारिका`, `विनियोग(?!सङ्ग्रह|संग्रह)`, `प्रस्तावः`, `भूमिका`, `^विषयः$`, `^त्रिभुवनः - Note$`) between `विश्वास-प्रस्तुतिः` blocks,
  - routes leading-compatible blocks (`मूलम् (संयुक्तम्)`, `संयुक्त-मूलम्`, `विस्तारः`, `विश्वास-टिप्पनी*`) and file-top bhūmikās to `सर्वा अवतारिकाः` when pre-VP / paired with avatārikā, and post-VP translations/`मूलम्`/commentaries to `सर्वाष् टीकाः`,
  - leaves `विश्वास-प्रस्तुतिः*`, `विनियोगसङ्ग्रहः`, explicitly-`open` `विश्वास-टिप्पनी`, and VP-containing container blocks unwrapped.
- **Include titles & never wrapping single-layer `static/` files:** Always include `sarvASh_TIkAH/` files with `title="सर्वाष् टीकाः"` (typically `class="js_include collapsed"`) and `vishvAsa-prastutiH/` files with `title="विश्वास-प्रस्तुतिः"`. **Never wrap single-layer `static/.../sarvASh_TIkAH/` or `static/.../vishvAsa-prastutiH/` files** internally — host pages already wrap them via `title="सर्वाष् टीकाः"` / `title="विश्वास-प्रस्तुतिः"`. Wrap only VP-bearing files (`sarva-prastutiH/` and standalone core-text files), then refresh transitive prefills (see the `website` skill).
- **Nested-`<details>` leaf-regex hazard:** Once commentaries/translations/`मूलम्`/padapāṭha live inside `<details><summary>सर्वाष् टीकाः</summary>` (or `सर्वा अवतारिकाः`), naive non-nested `<details[^>]*><summary>([^<]*)</summary>(.*?)</details>` regexes swallow the first inner child `<details>` into the wrapper. Parse hierarchically with `details.common.parse_top_level_details` or forbid nested opens (`(?:(?!<details\b).)*?`) when matching leaf `<details>` blocks (see the `md-processing` skill).

### Block naming
Unless specified otherwise (in the prompt or surrounding context), translations and commentaries are wrapped in `<details><summary><AuthorName></summary>\n\n...\n</details>`

### Commentary Splitting
- Core Text splitting was explained in the `text_to_blocks` skill.
- **Distributing multi-sentence commentary across fine `मूलम्` blocks:** When commentary blocks span multiple `मूलम्` blocks, split commentary sentences quote-safely (respecting quotes and parentheses so quoted verses/mantras with internal `।`/`॥` are not broken) and align them monotonically to the `मूलम्` blocks using pratīka matching (`... इति`, quoted phrases, and normalized Devanagari stems).

#### Viniyoga and AvatArikA separation
- **Pre-block and Lead-ins:** source prose before the first quote (introduction, often ending in a lead-in) becomes a commentary-only block (with suffix "अवतारिका" or "विनियोगः" as the case may be) placed before the first group, directly under the section heading.
- **Viniyoga separation:** In Vedic commentaries and translations (Bhaṭṭa Bhāskara, Sāyaṇa, Tribhuvana, etc.), separate leading ritual application (viniyoga) statements and genuine ritual/rubric footnotes (`*(Mantra ...)*`, `*(Kaṇḍikā ...)*`, etc., describing sacrificial use or prayer purpose) into `<details><summary>भास्करोक्त-विनियोगः</summary>`, `<details><summary>सायणोक्त-विनियोगः</summary>`, or `<details><summary><Translator> - विनियोगः</summary>` (e.g. `<details><summary>त्रिभुवनः - विनियोगः</summary>`) placed together **above** the corresponding `विश्वास-प्रस्तुतिः` block (or above a `js_include`), stripping the `[P...]` viniyoga marker from the translation block.
  - **Never in yajur-veda `sarvASh_TIkAH` files:** No `*विनियोगः` block may ever be placed in a yajur-veda `sarvASh_TIkAH/` file (viniyoga is ritual/host-specific, whereas `sarvASh_TIkAH/` holds only mantra-intrinsic translations and commentaries). Place `*विनियोगः` blocks only in `sarva-prastutiH/` files (either in the host file above the `js_include` or in a shared ritual `sarva-prastutiH/` file; see the `vedic` skill).
  - **Viniyoga vs. Avatārikā vs. pure chandas, and kalpa continuations:** Extract genuine ritual application statements (e.g., `विनियोगः`, `कल्पः`, `जपति`, `जुहोति`, `उपतिष्ठते`, `आदत्ते`, `अभ्यादधाति`, `विनियुज्यते`, explicit ritual/ section/ brick-placement intro such as `हृदयेष्टका` / `षोडशेष्टका` even when followed by a meter note like `अथ सप्तहोतुः हृदयेष्टका आन्तादनुवाकस्य - इन्द्र इति द्विपदा त्रिष्टुप् ॥`) along with any immediately continuing explanatory *kalpa* gloss sentences (e.g. `तदिति स्कन्नमाज्यमुच्यते। ...`) into `*विनियोगः`. Contextual/thematic/stuti lead-ins that state the topic, deity, or praise context before `... इति ॥` / `-` without prescribing ritual action (e.g. `एवमिन्द्रस्यात्मनाऽविभागेन दशहोता स्तुतः, इदानीं इन्द्राभेदेनापि स्तूयते - अन्तः प्रविष्ट इति ॥`, `... स्तौति`, `... स्तूयन्ते`, `इदानीम् ... आह`, `तदेवाह`) should **not** be collapsed into `*-टीका`, nor mislabeled as `*विनियोगः` — mark them as `<details><summary><Author> - अवतारिका</summary>` (e.g. `<details><summary>भट्टभास्करः - अवतारिका</summary>`), placed above `विश्वास-प्रस्तुतिः` (or above the `js_include` when host-flow-specific).
  - **Translator/editorial notes (`त्रिभुवनः - अवतारिका` vs. `त्रिभुवनः - विनियोगः`):** Editorial, text-critical, edition-variant, concordance, and Prapāṭhaka/Anuvāka/Kaṇḍikā numbering notes (e.g. `Sāyaṇa considers this Prapathaka as the third Anuvaka of the VIII Prapathaka. Regular number of the kaṇḍikās have not been given...`, `Hume does not give the Prayer-Mantra.`, `Prapathaka V according to Commentator Bhaṭṭa Bhāskara...`, `*(Mantras)* Identical with the First Anuvaka except for certain changes of tense.`, `*(Mantras)* Peace chanted once more in the Ānandāśrama edition.`, `A Yajus Mantra.`), as well as pure narrative/anecdote introductions without ritual prescription, belong in `<details><summary><Translator> - अवतारिका</summary>` (e.g. `<details><summary>त्रिभुवनः - अवतारिका</summary>`), **not** `- विनियोगः`. If a single note combines editorial/numbering info with a genuine ritual rubric, split them into `<Translator> - अवतारिका` and `<Translator> - विनियोगः` above `विश्वास-प्रस्तुतिः` (closing śānti repetitions belong in `<Translator> - शान्तिपाठः (समाप्तिः)`).
  - For pure meter/chandas-only notes, distinguish **single-ṛk** vs. **multi-ṛk / group-level**: pure chandas notes that describe only **that single ṛk/mantra** (`त्रिपदा त्रिष्टुप् ॥`, `गायत्री ॥`, `प्रथमा षट्पदा जगती ।`, etc.) stay inside that mantra's `*-टीका`; by contrast, chandas or group lead-ins that talk about **multiple ṛks/mantras or a whole section/sūkta** (e.g. `वेदेत्यादयः तिस्रस्त्रिष्टुभः ॥`, `यो देवेभ्य इत्याद्ये अनुष्टुभौ ॥ अधुना स एव आदित्वो वर्ण्यते ।`, `अतः परं तिस्रो गायत्र्यः - आ यस्मिन्निति ॥`, `सर्वास्त्रिष्टुभः, विशेषो वक्ष्यते ।`) do **not** belong inside a single mantra's `*-टीका` (nor inside any `sarvASh_TIkAH/` file) — extract them into `<details><summary><Author> - अवतारिका</summary>` placed above `विश्वास-प्रस्तुतिः` (in the host file right above the `js_include` of the first mantra of that group when individual ṛks are included from `sarvASh_TIkAH/`).


#### Trailing summaries
Keep trailing verse summaries in `<details><summary>विनियोगसङ्ग्रहः</summary>`.

#### Footnotes & endnotes inside `<details>` blocks
Place any short footnotes/endnotes belonging to a translated segment inside the **same** `<details><summary><TranslatorName/ CommentatorName></summary>` block (and place section/anuvāka introductory notes in a `<details><summary><TranslatorName/ CommentatorName></summary>` block at the start of that section/anuvāka). Replace Markdown footnote syntax (`[^32]`) by removing the `^` (e.g. `[32]`), so that the notes render inline inside the `<details>` block rather than being hoisted by the Markdown renderer to the bottom of the page outside the `<details>` block.

However, longer footnotes should be placed in an adjascent `<details><summary><TranslatorName/ CommentatorName> - Note</summary>` block.


### Include directives
**`js_include` (`vishvAsa-prastutiH` / `sarvASh_TIkAH` / shared `sarva-prastutiH`) targets:**

- **Required `title` attributes:** Include `vishvAsa-prastutiH/` files with `title="विश्वास-प्रस्तुतिः"`, include `sarvASh_TIkAH/` files with `title="सर्वाष् टीकाः"` (typically `class="js_include collapsed"`), and include combined `sarva-prastutiH/` files (which already contain both inner `<details>` blocks) with `includetitle="false"`.
- When a mantra or passage is included via `js_include` from a `sarvASh_TIkAH` file or a shared `sarva-prastutiH` file, place its intrinsic translation (e.g. `<details><summary>त्रिभुवनः</summary>`) and any missing commentary directly inside that included `sarvASh_TIkAH` / shared `sarva-prastutiH` file (alongside existing translations above `मूलम्` and commentaries below `मूलम्`) — stripping host-specific numbering (`1\. `, `2\. `) and host-context viniyoga footnotes — and run `transformer.prefill_includes` / `surgical_prefill_transitive` (see the `website` skill).  

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

When explicitly asked to run `/commentary_translation` with the fine-tuned `Qwen3-14B` Sanskrit interleaver LoRA (`doc_curation/data/models/qwen3-14b-sanskrit-lora/`, Kaggle: `vishvasvasuki/qwen3-14b-sanskrit-proofreader-lora`), use `ProofreaderBackend` and `interleave_helper` — both operate strictly by **0-based JSON indices ("no retyping, ever")**:

1. **Plain translation streams (`doc_curation.llm.translation_matcher`):** Pass `backend=ProofreaderBackend(base_url="https://<tunnel>/v1")` and `translation_title="<AuthorName>"` to `translation_matcher.insert_translation_details(...)` (`backend.generate_content` pre-indexes `TRANSLATION WORDS:` with unambiguous `[0]..[W-1]` word tags + `BILINGUAL ANCHOR PRIOR` cues and post-guards replies with `refine_translation_mapping` — repairing `2×` whitespace-split index offsets, snapping `±1` boundaries to sentence/dash starts, enforcing `skip` consistency, and falling back to `local_translation_generate_fn` on invalid partitions).
2. **Multi-role commentaries & Vedic translations (`interleave_source_into_markdown` with `ProofreaderBackend`):**
   Pass `backend=ProofreaderBackend(...)` to enrich prompts with sandhi-resolved `{cue: CORE k via '...', role=...}` hints + `UPCOMING CORES` lookahead and post-guard LLM JSON replies with `refine_interleave_plan`:

```python
from doc_curation.llm.proofreader import ProofreaderBackend, interleave_source_into_markdown

backend = ProofreaderBackend(base_url="https://<tunnel>/v1")
res = interleave_source_into_markdown(
    host_md,
    source_commentary_text,
    author_label="भट्टभास्करः",
    is_sarvash_tikah=is_sarvash_tikah,
    backend=backend,
)
assert res["verification"]["ok"], res["verification"]
updated_md = res["markdown"]
withheld_viniyogas = res["withheld_viniyogas"]
```

## Verification checklist
1. **Coverage**: every source content line appears verbatim in the page after stripping `>`, surrounding quotes, and heading markers → expect `missing: []`.
2. `<details>` count == `</details>` count.
3. Summary census matches intent; every `विश्वास-प्रस्तुतिः` block `open`.
4. Host sections not being edited are byte-identical before/after.
5. No stray sentinel text (e.g. `None`).
6. Structural lint: block order within each group; no empty blocks; no commentary block starts or ends with a `**…॥**` heading; verse markers all still present, each once.
7. **Random semantic spot-check & redo (mandatory whenever alignment tools are used):** Programmatic coverage/tag assertions catch dropped text, not semantic boundary drift. Always sample several random clusters across the page (early, middle, late, short/skip-adjacent cores, and section-boundary `> *Note:*` blocks) to verify that each translation/commentary slice truly explains its paired `मूलम्` block and carries the right role (`*विनियोगः` vs `*- अवतारिका` vs `*-टीका`, single-ṛk vs multi-ṛk *chandas*); re-slice or redo any misaligned blocks directly.



## Final report
Report which step you ran and what changed.
