---
name: vedic
description: Consolidates, structures, and maintains Vedic mantra corpora across śākhās (Śākala, AV, VS-M, VS-K, TS, TB, TK, KS, MS) — two-part static layout, cross-śākhā reuse & deduplication, variant disambiguation, and corpus/accent coordination. Use when editing, using or linking Vedic mantra files (`~/gitland/vishvAsa/vedAH*`), deduplicating shared mantras across recensions, or organizing static vs. host trees.
---

Manage Vedic mantra corpora across `~/gitland/vishvAsa/vedAH*` (`vedAH_Rk`, `vedAH_yajuH`, `vedAH`, `vedAH_sAma`) and host inclusions (venv: `~/gitland/python_venv`).

## Cross-śākhā Vedic reuse & deduplication (`विश्वास-प्रस्तुतिः` vs. `सर्वाष् टीकाः`)

When consolidating parallel mantras across Vedic śākhās (e.g. `Śākala`/`AV`/`VS-M`/`VS-K`/`TS`/`TB`/`TK`, see `doc_curation_projects.veda.dedup`, `doc_curation_projects/veda/dedup/cross_veda_targets.toml`, and `doc_curation_projects.veda.yajuH.vaajasaneyi.dedup`):

- **Normalize before comparing:** Ignore verse/kaṇḍikā numbers (`॥२४॥`), punctuation, whitespace/line wraps, `-` hyphens, `**...**`, `+++(...)+++` glosses, inter-word halant+vowel joins (`म् अ` ↔ `म`), `ऽ`/`ऽअ` hiatus orthography, and pure scribal gemination after `र्` (`र्द्ध`↔`र्ध`, `र्म्म`↔`र्म`). Preserve internal pluta digits (`२`/`३`), `ड`/`ळ` and nasal variants, and US accents (`᳓`/`᳙`) as significant. All shared `vishvAsa-prastutiH/` (and combined `yajuH/sarva-prastutiH/`) files must use **US accents only** (see the `accenting` skill).
- **Two-part static layout (no separate `mUlam/` dirs):** Across Śākala/AV/Yajurveda `Rk/`, static mantra trees consist of `vishvAsa-prastutiH/` + `sarvASh_TIkAH/` (do not create or keep separate `mUlam/` directories; put each śākhā's mūlam inside `sarvASh_TIkAH/` as `<details><summary>मूलम् - <Śākhā></summary>`).
- **No real pāṭha-bheda (exact normalized consonants + US accents):** Share and `js_include` **both** `vishvAsa-prastutiH/` **and** `sarvASh_TIkAH/` — or, for shared strict non-Ṛk blocks without a separate `sarvASh_TIkAH/` split, use a combined `yajuH/sarva-prastutiH/{ch:02d}/{k:02d}_{storage_name}.md` (`includetitle="false"`).
- **Minor pāṭha variant:** Keep `विश्वास-प्रस्तुतिः` **separate/local** in each host śākhā (do not share combined `yajuH/sarva-prastutiH/` on variants) and merge/`js_include` **only** `sarvASh_TIkAH/`. Inside the shared `sarvASh_TIkAH/` file, disambiguate variants explicitly:
  - Always qualify śākhā mūlams explicitly as `<summary>मूलम् - <Śākhā></summary>` (e.g. `मूलम् - शाकलम्`, `मूलम् - शौनकम्`, `मूलम् - माध्यन्दिनम्`, `मूलम् - काण्वम्`, `मूलम् - तैत्तिरीयम्`).
  - Add `<summary>पदपाठः - <Śākhā></summary>` (e.g. `पदपाठः - काण्वः`, `पदपाठः - दयानन्दादि`, `पदपाठः - तैत्तिरीयः`).
  - Qualify colliding commentator titles by śākhā (e.g. `<summary>सायण-टीका (काण्वी)</summary>` when Taittirīya/Śākala `<summary>सायण-टीका</summary>` can coexist).
- **Keep `सर्वा अवतारिकाः` local & align stanza granularity:** Keep `<details><summary>सर्वा अवतारिकाः</summary>` (`*विनियोगः`, `*अवतारिका`) per śākhā in the host file above `विश्वास-प्रस्तुतिः`/`js_include`. Merge split-hemistich Ṛk halves in a host when no liturgical viniyoga divides them (relocating misattached whole-stanza/next-clause viniyogas); if genuine split viniyoga separates the halves, split the shared `static` files and update all host includes across repos.
- **Corpus provenance:** After editing shared hosts, refresh transitive `js_include` prefills across `vishvAsa` repos (see the `website` skill) and verify `VedicCorpusCounter` (`doc_curation.sanskrit.accent.provenance`, see the `accenting` skill) excludes foreign `मूलम् - <OtherŚākhā>` blocks when ingesting shared hosts.

## Accents, validation & sibling skills

- **Vedic accents (`accenting` skill):**
  - Match notation to the block: `विश्वास-प्रस्तुतिः` always uses **US accents (`᳓`/`᳙`)** (`accent.to_US_accents` / `to_us_accents_markdown(..., preserve_existing_us=True)`), whereas `मूलम्` retains the source's own notation (classically dependent `॒`/`॑`).
  - Suggest svara corrections in accented text as `[[OLD|NEW]]` rather than silently overwriting (except fake accents, de-novo `(यन्त्र-स्वरः)`, and splitting fixes), and document mechanical/de-novo padapāṭha provenance in `<details><summary>पद-पाठः (यान्त्रिकः...)</summary>` (citing valid corpora `*TS*, *RV*, *TB*, *TK*, *AV*, *SB-M*, *SB-K*, *VS-M*, *VS-K*, *KS*, *MS*`, never `*TA*` or `*EK*`; see `grammar` skill §6 for padasvara/prakṛti-svara lookups).
  - Never embed `sarvASh_TIkAH/` or `पद-पाठः (यान्त्रिकः)` inside `vishvAsa-prastutiH/` files, and run `doc_curation.sanskrit.accent.validator`, `reconciler`, and `auditor` (`~/gitland/python_venv/bin/python -m doc_curation.sanskrit.accent.auditor <dirs...> --with-reconciler`) after accent or layout edits.
- **Markdown structure & wrappers (`md-processing` skill):** Treat `js_include` divs as atomic boundaries, preserve cluster invariants, and use `doc_curation.md.content_processor.commentary.helper.wrap_vedic_details` only on VP-bearing files (`sarva-prastutiH/` and standalone mantra files — never on single-layer `static/.../sarvASh_TIkAH/` or `static/.../vishvAsa-prastutiH/` files).
- **Commentaries & translations (`interleaver` skill):** Align commentaries/translations (`*विनियोगः`, `*- अवतारिका`, `विश्वास-प्रस्तुतिः`, translations, `मूलम्`, `*-टीका`) and never place `*विनियोगः` blocks inside Yajurveda `sarvASh_TIkAH/` files.
- **Sense-unit block creation/splitting (`text_to_blocks` skill):** Generate or split paired `विश्वास-प्रस्तुतिः` / `मूलम्` clusters while keeping `मूलम्` verbatim and converting `विश्वास-प्रस्तुतिः` to US accents.
- **Includes & prefills (`website` skill):** Resolve `js_include` targets via `include.resolve_include_file_path` and propagate edits across transitive hosts via `include.surgical_prefill_transitive`.
