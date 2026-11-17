---
name: accenting
description: Applies, converts, checks and repairs Vedic accent marks (US udAtta ᳓ / svarita ᳙, dependent ॒/॑/᳜) with indic_transliteration's accent module, recording provenance for any accent it invents.
---

Apply and evaluate Vedic accent marks (venv: `~/gitland/python_venv`). The helpers all live in one module:

```python
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent
```

## Changing accent notation

Match the notation to the block: `विश्वास-प्रस्तुतिः` normally uses **US accents** (`᳓` / `᳙`, using uniform `᳙` on independent svaritas such as *abhinihita* `सो᳙ऽकामयत`, matching `accent.to_US_accents`); `मूलम्` keeps the source's own notation (classically dependent `॒`/`॑`).

### US accents (᳓ / ᳙)

```python
accent.to_US_accents(text)  # Devanagari assumed
accent.to_US_accents(text, pauses=r"[।॥,;]+")  # recommended when odd/viṣama pādas wrap across newlines without ।
accent.to_US_accents(text, scheme=sanscript.SCHEMES[sanscript.TELUGU])  # other scripts
```

Converts traditional/dependent notation (`॒`/`॑`, or `᳚`/`᳛`) into independent udAtta (᳓) / svarita (᳙) marks; `+++(...)+++` annotations are skipped. By default `pauses=r"[।॥\n,;]+"` treats every newline as a pause; pass `pauses=r"[।॥,;]+"` when pādas wrap without a daṇḍa so line-start syllables do not acquire spurious phrase-initial udāttas. Note also one inherent notation ambiguity: an independent svarita (`᳙`) immediately following an udātta syllable (`परमे᳓ व्यो᳙मन्न्`) collapses to dependent `॑` (`पर॒मे व्यो॑मन्न्`), so `to_US_accents` drops `᳙` there even when the classical source intends `᳙`. The input must already carry dependent accents — unaccented (or already US-accented) text is returned unchanged. `scheme` takes a **scheme object** (`sanscript.SCHEMES[...]`), not an identifier like `sanscript.DEVANAGARI`.

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

### General rule: suggest, don't alter

Do not directly alter svara-s in an accented text (especially in `विश्वास-प्रस्तुतिः`) — make the correction a reviewable inline suggestion in the `[[OLD|NEW]]` format from the `proofreader-hyphenator` skill, on the smallest span that carries the wrong accent, e.g. `[[अग्निमीळे|अ॒ग्निमी॑ळे]]`. State the source behind the suggestion (dictionary, corpus, or sūtra) in the same breath. Emit `[[OLD|NEW]]` suggestions in `विश्वास-प्रस्तुतिः` only for errors actually present in `विश्वास-प्रस्तुतिः` itself (never from `मूलम्`-only errors when `विश्वास-प्रस्तुतिः` is already right), and only when backed by solid corpus attestations or clear grammatical rules (`*TS*`, `*RV*`, `*TB*`, enclitics, finite verbs, vocatives, āmreḍita) — not uncertain `*MW*` stem guesses. The exceptions below — fake accents, wrong de-novo insertion, splitting errors — may be applied directly.

### De-novo accents (यन्त्र-स्वरः)

Do not accent classical Sanskrit, and do not insert accents of your own where the source has none — only when explicitly asked. When you do, both of these are mandatory:

1. append `(यन्त्र-स्वरः)` to the `open`-ed details block name, i.e. `<details open><summary>विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)</summary>`;
2. add a `पद-पाठः (यान्त्रिकः)` block directly below the `मूलम्` and **above** Sanskrit commentaries (`*-टीका`) — one list item per pada in US accents (`᳓` / `᳙`), giving its accented form, concise source abbreviation(s) (`*TS*`, `*RV*`, `*TB*`, `*TK*`, `*AV*`, `*ŚB*`, `*MW*`, `पा० x.y.z`, `भास्करः`, `सायणः`), and any doubts. Title the block `<details><summary>पद-पाठः (यान्त्रिकः)</summary>` when `N == 0` (either de-novo or zero *vyatyasta* padas found); when auditing an already-accented source and correcting `N > 0` of `P` padas, title it `<details><summary>पद-पाठः (यान्त्रिकः - N/P व्यत्यस्त-स्वराः)</summary>` and write corrected padas as `- आङ्गीर᳓सः → **आङ्गीरसः᳓** (प्रातिपदिकम् आङ्गीरस᳓ (*MW*))` (unchanged padas omit any redundant prefix: `- आङ्गीरसः᳓ (प्रातिपदिकम् आङ्गीरस᳓ (*MW*))`).

Where to find an accent and how to derive it: `grammar` skill, section 6.

Shape of the result (illustrative — fill provenance from the actual source):

````markdown
<details open><summary>विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)</summary>

ब्र᳓ह्म स᳓न्धत्तम् +++(मया सह)+++। त᳓न् +++(ब्रह्म)+++ मे जिन्वतम्+++(=प्रीणयतम्)+++ ॥
</details>

<details><summary>मूलम्</summary>

ब्रह्म॒ सन्ध॑त्त॒न्तन्मे॑ जिन्वतम् ।
</details>

<details><summary>पद-पाठः (यान्त्रिकः)</summary>

- ब्र᳓ह्म (*TS*, *RV*, *ŚB*)
- स᳓म् (*TS*, *RV*)
- धत्तम् (तिङन्तम् अनुदात्तम्, पा० ८.१.२८, *RV*, *ŚB*)
- त᳓त् (*TS*, *RV*)
- मे (अनुदात्तम्, पा० ८.१.१८, *TS*, *RV*)
- जिन्वतम् (तिङन्तम् अनुदात्तम्, पा० ८.१.२८, *RV*)
</details>
````

#### Pada-pāṭha decision procedure

Never split padas or assign accents mechanically from word lists alone. Decide the pada-pāṭha and each pada's expected svara in this order:

1. **Read interleaved commentaries and translations first:**
   - Check `भट्टभास्कर-टीका`, `सायण-टीका`, `रङ्ग-रामानुजः`, etc., and translations in the same mantra cluster before splitting. Commentaries bold or gloss each pada, give *vigraha-vākyas* for compounds, identify finite verbs and roots (e.g. `सुत` = 2nd pl. imperative of `षु प्रसवैश्वर्ययोः` "अनुजानीत", unaccented — not `सुतः`), and note Vedic Pāṇinian rules (`परादिश्छन्दसि` पा० ६.२.१९९, `चवायोगे प्रथमा` पा० ८.१.५९, `उदात्तवता तिङा`, `ऐकश्रुत्यम्`, `स्वरव्यत्ययः`).
   - Where a pāda or phrase has a parallel in `*TS*` or `*RV*`, follow its attested `<summary>पद-पाठः</summary>` / `rv-padapATha-dev` division.

2. **Split distinct sandhi-joined padas; never club non-compounds:**
   - Undo external vowel, visarga, and consonant sandhi into normalized isolated padas (`देवीर्भुवनसूवरीः` → `देवीः᳓` + `भुवन-सू᳓वरीः`; `उत्तानस् त्वाङ्गीरसः` → `उत्तानः᳓`, `त्वा`, `आङ्गीरसः᳓`; `सह सञ्चस्करर्धिया` → `सह᳓`, `सञ्चस्कर`, `ऋ᳓द्धिया`; visarga-lopa `पार्थिवस्यैक इद्वशी` → `पा᳓र्थिवस्य`, `ए᳓कः`, `इ᳓त्`, `वशी᳓`, never `एकम्`; `लोपः शाकल्यस्य` पा० ८.३.१९ prevocalic `वा᳓`/`वेह` → `वै᳓`, `-स्मा` → `-स्मै`; `-आँश्च`/`-ईँश्च`/`-ऊँश्च` via `पा० ८.३.७` → `-आन्`/`-ईन्`/`-ऊन्` + `च`; `भूर्भुवस्सुवः` → `भूः`, `भु᳓वः`, `स्वः᳙`; periphrastic perfects `मीमांसाम्` + `चक्रे`, `आम्` + `आस`).
   - **Never club `न` + word as a compound:** `नञ्-तत्पुरुष` drops `न्` (`पा० ६.३.७३ नलोपो नञः` → `अ-`/`अन्-`), so `नान्यः`, `नान्यत्`, `नैनम्` are always two separate padas (`न᳓` + `अन्यः᳓`), never `न-अन्यः`.
   - Likewise never club `मा`, standalone pronouns (`यः`, `सः`, `तम्`, `अहम्`, `अस्य`), particles/enclitics (`च`, `वा`, `हि`, `उ`, `ह`, `एव`, `इति`, `मे`, `ते`, `त्वा`, `नः`, `वः`), copulas/verbs (`-असि`, `-अस्मि`, `-अस्ति`, `-एति`), or case-inflected `सुबन्त`s unless a genuine Vedic *aluk* or *upapada* compound (`तपसः-पते`, `वाचः-पतिः`, `आयुः-दाः`, `स्वयम्-भु`, `तत्-पुरुषाय`, `द्यौः-इव`).

3. **Keep samasta-padas together with `-` at compound joints:**
   - Never split a *samasta-pada* across multiple bullets. Keep it as one item with `-` between compound members (`वायु-अ᳓श्वाः`, `रश्मि-प᳓तयः`, `म᳓रीचि-आत्मानः`, `भुवन-सू᳓वरीः`), undoing internal sandhi cleanly at `-`.
   - Keep `गतिकृदन्त` participles and verbal derivatives hyphenated as compounds (`नि-द᳓धत्`, `सं-भू᳓तः`, `वि-द᳓धत्`, `पा० ६.२.१३९ गतिकारकोपपदात्कृत्`) — never treat them as finite `तिङन्त` verbs (`पा० ८.१.२८` does not apply to participles).
   - Do **not** place `-` before *kṛt* or *taddhita* suffixes (`पुत्रवत्त्वा᳓य`, `आङ्गीरसः᳓`).

4. **Honor pause-final sandhi (`पा० ८.३.१५ खरवसानयोर्विसर्जनीयः`):**
   - Visarga (`-ः`) never drops before `।` or `॥`. Never "restore" `-ः` onto a word ending in `-अ` at pause (`मे सुत ।`, `इतोहित ।`).

5. **Separate or compound `upasarga` (`गति`) + finite verb (`तिङन्त`) by clause type:**
   - **Main clause (unaccented verb, `पा० ८.१.२८ तिङ्ङतिङः`):** Split `upasarga`(s) and the finite verb into separate padas (`सम॑वर्त॒ताधि॑` → `स᳓म्`, `अवर्तत`, `अ᳓धि`; `प्र᳓ति` + `गृह्णातु`; `आ᳓` + `यातु`), where the `upasarga` keeps its udātta (with `पा० ८.१.७० गतिर्गतावत्` when chained) and the verb is unaccented. Do not split simplex roots or `अ-` augments that merely resemble prefixes (`आस्ते`, `आहुः`, `अवतु`, `विद्यते`, `विवेश`, `अपश्यत्`, `अवसन्`).
   - **Subordinate clause (accented verb):** Check the clause (and any immediately preceding verbless relative pāda before a correlative `तद्`-वृत्त) for `यद्`-वृत्त words (`यः`, `यम्`, `यत्`, `येन`, `यस्य`, `यत्र`, `यदा`, `यथा`, `यदि`, etc. — `पा० ८.१.६६ यद्वृत्तान्नित्यम्`), `हि`/`चेत्`/`नेत्`/`कुवित्` (`पा० ८.१.३४`, `८.१.३०`), or `च`/`वा` verb coordination (`पा० ८.१.५९ चवायोगे प्रथमा`). Here the `तिङन्त` retains its accent, a preceding `गति` becomes anudātta (`पा० ८.१.७१ तिङि चोदात्तवति`), and `गति + तिङ्` compound into one pada per `उदात्तवता तिङा गतिः समस्यते` (`य᳓म् उदाजहा᳓र` → `उदाजहा᳓र`; `यो᳓ नः प्रचोद᳓यात्` → `प्रचोद᳓यात्`). Nominal relative clauses with an elliptical copula (e.g. `यो᳓ऽस्य ... वशी᳓ । यमं ... गाय`) do **not** carry `पा० ८.१.६६` to a main-clause verb (`गाय`) in the following pāda or sentence.

6. **Verify the forward-sandhi round-trip invariant:**
   - Joining the proposed `पद-पाठः` sequence with Pāṇinian and Vedic sandhi rules must reconstruct `मूलम्` (programmatically via `doc_curation.sanskrit.sandhi_check.verify_mantra_sandhi`; modulo recensional allographs such as `ळ/ड`, `व्ँ/ं`, and gemination after `र्`). Without an intervening daṇḍa (`।`/`॥`), samhitā sandhi still applies across *viṣama-pāda* line wraps (`\n`): e.g. `भव्य॑म् आ \nइ॒दन्` is *visarga-lopa* (`आः + इदम् → आ इदम्`, verified in commentaries as `आसीत्`), never `आ + इदम्`. Any discrepancy — e.g. `एकम् + इत् → एकमित् ≠ एक इत्` (`एकः + इत्`), `आ + इदम् → एदम् ≠ आ इदम्` (`आः + इदम्`), `सुप्रयतौ + इह → सुप्रयताविह ≠ सुप्रयतेह` (`सु-प्रयते + ह`), or `हिंसीः + जातवेदः → हिंसीर्जातवेदो ≠ हिंसीज्जातवेदो` (`हिंसीत्`) — proves a wrong inflection or split and must be repaired before checking accents. Do not allow unconstrained `V + V` hiatus in forward-sandhi checks; accept hiatus only across `।`/`॥` pauses, grammatically licensed splits (*pragṛhya* `-ई`/`-ऊ`/`-ए` duals & `-ओ` nipātas, `लोपः शाकल्यस्य` `-ए`/`-ऐ`/`-ओ`, `-आः`/`-अः` visarga-lopa), or documented metrical hiatuses.

7. **Project sandhi accents from `मूलम्` and evaluate `वाक्य-स्वरः` before lexical lookup:**
   - **Ground truth, newline pauses, & classical `॑`-after-udātta ambiguity (`पा० ८.२.५ एकादेश उदात्तेनोदात्तः`):** Always project `पद-पाठः` accents strictly from `मूलम्` (`accent.to_US_accents(text, pauses=r"[।॥,;]+")` when line breaks lack `।`/`॥` so `\n` is not treated as a pause), never from `विश्वास-प्रस्तुतिः` (which is checked separately for `[[OLD|NEW]]` suggestions), and never mistake classical dependent svarita `॑` (one syllable *after* the udātta, e.g. `य॒मो ह॑वे॒ह` = `यमो᳓ ह वेह᳓`, where `ह` is unaccented) for an udātta on the marked syllable. Crucially, when `मूलम्` places `॑` immediately after an udātta syllable (with no intervening `॒`, e.g. `पर॒मे व्यो॑मन्न्`, matching *TS* `प॒र॒मे । व्यो॑म॒न्`), classical notation leaves dependent svarita and independent `᳙` indistinguishable: `to_US_accents` omits `᳙` on `व्यो`, even though `मूलम्` can perfectly well be read as `व्यो᳙मन्न्`. Do **not** flag such a pada as a `vyatyasta-svara` (`व्योमन्न् → **व्यो᳙मन्न्**`) — record `- व्यो᳙मन्न् (*TS*)` directly and do not count it in `N/P`, while still checking whether US-accented `विश्वास-प्रस्तुतिः` itself dropped `᳙` (`[[व्योमन्|व्यो᳙मन्]]`). Attribute a merged boundary udātta (`-त + अ᳓- → -ता᳓-` in `अवर्तता᳓धि`, `-अ + ऋ᳓- → -अर्᳓-` in `सञ्चस्कर᳓र्धिया`) using each pada's syntactic role and attested accent (`अवर्तत` unaccented + `अ᳓धि`; `सञ्चस्कर` unaccented + `ऋ᳓द्धिया`). Sandhi-induced independent svarita `᳙` (*kṣaipra* `व्य᳙शेम`, *abhinihita* `यो᳙ऽपा᳓म्`) corresponds to padapāṭha udātta `᳓` (`वि᳓`, `यः᳓`); keep `᳙` in padapāṭha only on lexical svaritas (`स्वः᳙`, `क्व᳙`, `वीर्य᳙म्`).
   - **Āmreḍita (`पा० ८.१.३ अनुदात्तं च`):** The repeated second word (`आ᳓पम् आपाम्`, `अस्मा᳓त् अस्मात्`) must be unaccented.
   - **Vocatives (`आमन्त्रित`):** Clause/pāda-initial vocatives are *ādyudātta* (`पा० ६.१.१९८`); non-initial vocatives are unaccented (`पा० ८.१.१९`).
   - **Enclitics & homophone disambiguation (`पा० ८.१.१८`):** `मे`, `ते`, `त्वा`, `मा`, `नः`, `वः`, `च`, `वा`, `उ`, `ह`, `स्म`, and unemphatic anaphoric `इदम्`/`एतद्` forms (`अस्य`, `अस्मै`, `एनम्`, `पा० २.४.३२`) are unaccented (`पा० ८.१.१८`) and never stand at clause/pāda start. Never misclassify their accented homophones as enclitics: prohibitive `मा᳓` (`माङ्`, always udātta at clause start or before injunctives / `मे` / `नः` / `मम` / `मा`) vs enclitic `मा` ("me"); demonstrative nom. pl. `ते᳓` (`तद्`) vs enclitic `ते`; particle `वै᳓` (prevocalic `वा᳓`, `ह वै᳓` — ignore saṁhitā `'वा᳓'` attestations in TB/TK/AV when resolving enclitic `वा`) vs enclitic `वा` ("or").
   - **Attestation before stem extrapolation & Taittirīya normalization:** Prefer attested Vedic forms (`*TS*`, `*RV*`, `*TB*`, `*TK*`, `*AV*`, `*ŚB*`) over `*MW*` stem extrapolation, normalize Taittirīya anunāsika (`व्ँ`/`य्ँ`/`ल्ँ` ↔ `ं`) when matching against `*TS*`/`*TB*`, and do not override a valid single-accent Vedic form with an unattested `*MW*` homograph stem.

### Fake accents

Some Vedic texts (e.g. some taittirīya āraṇyaka sections) carry fake accents — typically mechanically applied runs of udAtta. Detect:

```python
accent.detect_fake_US_accents(text)  # → suspicious runs of >5 consecutive ᳓; empty list = nothing found
```

If you are explicitly asked, you may also spot other fake-accented US text beyond what the above detector finds. Here direct correction is allowed:

1. Remove **all** accents from that `विश्वास-प्रस्तुतिः` block (`accent.strip_accents(text)`), or keep the unaccented text if that was already done by hand. In both cases, append `(स्वराः पूर्याः)` ("accents still to be supplied") to the details block name, i.e. `<details open><summary>विश्वास-प्रस्तुतिः (स्वराः पूर्याः)</summary>`.
2. Re-insert accents only when asked — and then follow the de-novo rules above.

### Splitting errors

Typical `मूलम्`-block errors are at the beginnings and terminations of split blocks, e.g.

> "सम्मा॑ऽऽसिञ्चन्तु म॒रुत॒स् समिन्द्र॒स् सं बृह॒स्पतिः॑ । सम्मा॒यम॒ग्निस् सि॑ञ्च॒त्वायु॑षा च॒ बले॑न॒ चायु॑ष्मन्तङ् करोत॒ मा" इति।

has a missing svarita at the end. These errors likely arose from faulty splitting by a human. Where an error is found, fix it in the `मूलम्` block and in the corresponding `विश्वास-प्रस्तुतिः` block. In such cases, you can correct directly, without the [[OLD|NEW]] suggestion.
