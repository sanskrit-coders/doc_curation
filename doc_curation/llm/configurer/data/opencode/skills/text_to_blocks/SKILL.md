---
name: text_to_blocks
description: Splits Sanskrit Markdown text into finer विश्वास-प्रस्तुतिः, मूलम् and commentary details blocks, one sense-unit per block. Use when bare Sanskrit text must be wrapped in mUlam blocks or existing blocks must be split finer.
---

**Goal:** Split the text (or existing blocks) into the smallest विश्वास-प्रस्तुतिः, मूलम्, commentary blocks that still make complete sense on their own.

Apply the procedures below as need.

**Required imports:**
```python
from doc_curation.md import library
from doc_curation.md.content_processor.details import maker
from doc_curation.md.file import MdFile
```

## Common non-details text
In most cases, the below suffices -

```python
library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args, **kwargs: maker.generic_sanskrit_vipra_mUla(c))
```
splits non-detail text in the passed paths to sentences which are placed in विश्वास-प्रस्तुतिः and मूलम् blocks.

This internally uses

```python
from doc_curation.sanskrit import split_to_sentences
```

## Common text in details blocks
- **Editorial glosses in `विश्वास-प्रस्तुतिः` (`+++(...)+++`):** Always mask `+++(...)+++` when splitting on daṇḍas (`।`/`॥`). If `विश्वास-प्रस्तुतिः` explicitly supplies an elliptical finite verb inside `+++(...)+++` (e.g. `+++(निरमिमीत)+++`, `+++(आदधाति)+++`, `+++(भवति)+++`), treat that segment as having its finite verb (self-contained); only truly verb-less short segments (such as bare datives of purpose `रक्षसाम् अपहत्यै ।`, `सुवर्गस्य लोकस्य समष्ट्यै ।`, or bare `अथ + accusative` list items `अथ श्मश्रूणि ।` with no supplied verb and no `एव`) attach to the preceding action sentence under Test 5.


### Implementation notes for multi-layer Vedic files

- **Vedic accents in `विश्वास-प्रस्तुतिः`:** When generating new `विश्वास-प्रस्तुतिः` and `मूलम्` blocks from bare Vedic text (which has `॒`/`॑` accent marks), convert the `विश्वास-प्रस्तुतिः` text to udātta (`᳓`) / svarita (`᳙`) accents using `indic_transliteration.sanscript.schemes.brahmic.accent.to_US_accents` (see `transliteration-accenting` skill), while keeping the original `॒`/`॑` text in `मूलम्` (and stripping `+++(...)+++` editorial glosses if they were added to the bare text before block creation).
- **Parallel splitting of paired layers:** When splitting an existing multi-layer cluster into `k` fine blocks, emit `k` complete sub-clusters, each containing its paired `विश्वास-प्रस्तुतिः`, translations (if present), `मूलम्`, and corresponding `*टीका` slice (see `interleaver` skill for commentary/translation alignment and viniyoga separation).

## Split clause text

**Definitions:**
- **Sentence segment:** A string ending in a daNDa, either `।` or `॥`. Do not split inside a segment.
- **Block:** One or more sentence segments kept together (within विश्वास-प्रस्तुतिः, मूलम्, टीका details blocks) because they form a single sense unit.
- **Boundary:** The point between two consecutive sentence segments. The decision is made boundary by boundary.

**Default rule:** By default, every sentence segment goes to a separate block. Do not split at a boundary if any of the tests below applies. Check the tests in this order. If a boundary passes an earlier test, keep the segments together and do not need the later tests.

**1. Same Rk:** If several sentence segments together form one Rk, mantra, or verse, keep them together. The metrical unity overrides the daNDa. The Rk is one block even if it contains multiple daNDas.

**2. Same conditional-correlative unit:** This is the Sanskrit `yad` / `tad` construction, not the English word "if" alone. It covers pairs like `yaH / saH`, `yat / tat`, `yatra / tatra`, `yadA / tadA`, `yathA / tathA`, `yAni / tAni`, `yad / etad`, and similar. A boundary is inside one conditional unit when: **(a) Protasis first:** The left segment opens with a `yad`-word, and the right segment gives its correlative or consequence. **(b) Main clause first:** The left segment is a main statement, and the right segment opens with a `yad`-word that explains, qualifies, or defines it. **(c) Continuation:** The left segment is already inside an open conditional, and the right segment continues, elaborates, or concludes it, even if it has no explicit `tad`-word. In other words, a `yad`-segment attaches to its counterpart, whether that counterpart comes before it or after it.

Examples:

> यः का॒मये॑त॒ दान॑कामा मे प्र॒जाः स्यु॒रिति॑ । स पूर्व॑योः॒ फल्गु॑न्योर॒ग्निमाद॑धीत ॥

Protasis first, apodosis second. One block.

> अ॒र्य॒म्णो वा ए॒तन्नक्ष॑त्रम् । यत्पूर्वे॒ फल्गु॑नी ।

Main statement first, explanatory `yat` second. One block.

A conditional can extend beyond a pair. All segments that complete the same conditional stay together:

> य᳓ एवं᳓ विद्वा᳓न् लोहितायसे᳓न नि᳓वर्त᳓यते ॥
> एत᳓द् एव᳓ रूपं᳓ कृत्वा᳓ नि᳓वर्तयते ॥
> स᳓ त᳓तः श्वः᳓_श्वो भू᳓यान् भ᳓वन्न् एति ॥
> प्र᳓_एव᳓ जायते ॥

- **Self-contained `yad` sentences in Test 2:** A single-daṇḍa segment opening with `yad` that already contains its `tad`-correlative (`स`, `सा`, `तत्`, `तेन`, etc., or comma-separated apodosis within the same segment) is already a complete conditional-correlative unit and does not force-merge with the next segment.


**3. Quotation inside a conditional:** If a quotation is embedded inside a conditional, do not split at the quotation boundary. The whole span, protasis plus embedded quote plus resolution, is one block. The quotation does not break the conditional, and the conditional does not break the quotation.

Example:

> स᳓ य᳓द् ब्रूया᳓त् ॥
> क᳓स् ता᳓नि नि᳓रमिमी᳓त_इ᳓ति ॥
> प्रजा᳓पतिर् इ᳓ति ब्रूयात् ॥

Here `sa yad brUyAt` opens the conditional, the middle segment is the quoted question, and the last segment is the quoted answer. All three stay together.

**4. Same quotation:** If several segments belong to one quoted speech, keep them together with its quotative frame. A boundary is inside one quotation when: **(a)** The left segment is the frame, such as `so'bravIt`, `tadAhuH`, `brahmavAdino vadanti`, `iti brUyAt`, and the right segment begins the quote. **(b)** Both segments are inside the same quote, between the frame and the closing `iti`. **(c)** The quote itself contains several sentences. They are not split from each other or from the frame.

Example:

> सो॑ऽब्रवीत् ।
> स॒प्त॒द॒शेन॑ ह्रि॒यमा॑णो॒ व्य॑लेशिषि । भि॒षज्य॑त॒मेति॑ ।

Reference numbers like `१। ५। ११। २॥ ५६` are not sentence segments. They stay attached to the following text and do not create a split.

- **Distinguishing `इति` from `√i` (`एति`) verbs in Test 4:** Do not confuse 3rd-singular verbs from `√i` (`उपैति`, `पर्येति`, `अवेति`, `समवेति`, `प्रैति`, `अभ्येति`, `अन्वेति`, `अत्येति`, `व्येति`, `समेति`, `पुनरेति`, `अन्तरेति`, `अपेति`, `अप्येति`, `उदेति`, `प्रत्येति`, `अध्येति`, `आयुरेति`) with sandhi-fused `इति`, while still recognizing genuine sandhi-fused `इति` (e.g. `उपैतीति` = `उपैति + इति`).

**5. Same sequential action:** If one segment states a prior action and the next segment states the action that completes it, keep them together. Typically the first segment ends in an absolutive, such as `-tvA` or `-ya`, and is syntactically incomplete without the main verb in the next segment.

Example:

> स तप॑स्त॒प्त्वा । (33)
> अन्नं॒ ब्रह्मेति॒ व्य॑जानात् ।

`taptvA` alone does not complete the sense. It must stay with `vyajAnAt`.

### General notes
**Combination rule:** Merging is transitive. If segment A merges with B, and B merges with C, then A, B, and C form one block, even if A and C were merged under different tests. If none of the tests above applies at a boundary, split there.

**Exception:** If different viniyoga-s apply to different parts of a block (eg. different parts of a Rk), it should be split accordingly, even if the above rules (eg. single Rk) suggest otherwise.

**In doubtful cases:** Keep together. A split that breaks sense is worse than a slightly longer block.

- **Reference / pañcāti / anuvāka markers mid-sentence:** Reference numbers (like `१। ५। ११। २॥ ५६`, `(2)`, `[41]`) and mechanical pañcāti or anuvāka divisions in Vedic texts often fall in the middle of a Ṛk or prose sentence. Keep cross-pañcāti and cross-anuvāka sentences/mantras together in a single block (keeping the marker in place at its token position), using the metre, syntax, commentary pratīkas, and translations to identify true sentence/mantra boundaries.


## Report
Report which section you ran and what changed.
