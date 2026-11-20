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

Do not directly alter svara-s in an accented text (especially in `विश्वास-प्रस्तुतिः`) — make the correction a reviewable inline suggestion in the `[[OLD|NEW]]` format from the `proofreader-hyphenator` skill, on the smallest span that carries the wrong accent, e.g. `[[अग्निमीळे|अ॒ग्निमी॑ळे]]`. State the source behind the suggestion (dictionary, corpus, or sūtra) in the same breath. Emit `[[OLD|NEW]]` suggestions in `विश्वास-प्रस्तुतिः` only for errors actually present in `विश्वास-प्रस्तुतिः` itself (never from `मूलम्`-only errors when `विश्वास-प्रस्तुतिः` is already right), and only when backed by solid corpus attestations or clear grammatical rules (`*TS*`, `*RV*`, `*TB*`, enclitics, finite verbs, vocatives, āmreḍita) — not uncertain `*MW*` stem guesses. Furthermore, when generating or applying `[[OLD|NEW]]` suggestions in `विश्वास-प्रस्तुतिः`:

- **Never skip bold tokens:** Keep markdown `**...**` delimiters outside the suggestion bracket (`**[[ये᳓नावृत᳓ङ्|ये᳓ना᳓वृतङ्]]**`), so bold words in `विश्वास-प्रस्तुतिः` are checked and suggested just like unbolded ones.
- **Match through external sandhi & endings:** Propagate every solid `पद-पाठः` correction even when saṁhitā fuses it with adjacent padas (`आवृत᳓म् → **आ᳓वृतम्**` inside `**ये᳓नावृत᳓ङ्**` → `**[[ये᳓नावृत᳓ङ्|ये᳓ना᳓वृतङ्]]**`, `त्या᳓गेनैके` → `त्या᳓गेनै᳓के`, `स्वध᳓ये᳓हि` → `स्वध᳓येहि`) or mutates its final (`-म्` → `-ं`/`-न्`/`-ञ्`/`-ङ्`/`-व्ँ`, `-ः` → `-ो`/`-र्`/`-स्`/`-श्`, `-त्` → `-च्`/`-द्`).
- **Align by occurrence, never blind `count=1`:** Repeated words such as *āmreḍita* (`शा᳓न्तिः शा᳓न्तिः शा᳓न्तिः`, `मा᳓ मा`, `म᳓धु म᳓धु`, `अस्मे᳓ अस्मे`) or clause pairs (`अस्मि` in `सो᳓ऽह᳓म् अस्मि` vs `यो᳓ऽह᳓म् अस्मि`, `ते` in `ते᳓ ... ते`) have different expected accents per position; align syllable-by-syllable so the suggestion lands on the exact offending occurrence(s).
- **Respect cross-pada sandhi accents (`पा॰ ८.२.४–६`), even across spaced avagraha (`Word1 ऽWord2`):**
  - Never flag or strip an accent at the end of a word in `विश्वास-प्रस्तुतिः` when it legitimately arises from *ekādeśa* with the next word: anudātta `-ए`/`-ओ`/`-अ`/`-आ` + udātta `अ᳓-` (elided as `ऽ` — never `पा॰ ८.२.६`, since the initial is not *anudātta*) yields **udātta (`᳓`)** by `पा॰ ८.२.५ एकादेश उदात्तेनोदात्तः`, e.g. `विद्यते` + `अ᳓यनाय` → `विद्यते᳓ ऽयनाय` (never `[[विद्यते᳓|विद्यते]] ऽयनाय`), `वा᳓चस्पते` + `अ᳓च्छिद्रया` → `वा᳓चस्पते᳓ ऽच्छिद्रया`, `ज्या᳓यः` + `अ᳓स्ति` → `ज्या᳓यो᳓ऽस्ति`, `विविच्यन्ते` + `अ᳓थ` → `विविच्यन्ते᳓ ऽथ`.
  - Udātta `-ए᳓`/`-ओ᳓` + anudātta `अ-` yields **svarita (`᳙`) or udātta (`᳓`)** by `पा॰ ८.२.६ स्वरितो वाऽनुदात्ते पदादौ` (`यो᳙ऽपां᳓`/`सो᳙ऽग्रीवः᳓`, or `यो᳓ऽस्मा᳓न्`); do not alter either valid choice, and note that *savarṇa-dīrgha* `आ᳓` + anudātta `अ-` obeys `पा॰ ८.२.५` (always `आ᳓`, never `आ᳙`, e.g. `आ᳓ ऽस्मा᳓सु`, `मा᳓ ऽह᳓म्`).
  - Udātta `इ᳓`/`उ᳓`/`ऋ᳓` + anudātta vowel (*yaṇ*) yields **svarita (`᳙`)** by `पा॰ ८.२.४ उदात्तस्वरितयोर्यणः स्वरितोऽनुदात्तस्य` (`देव्ये᳙तु`, `त्व᳙र्भुम᳓ते`, `ह्ये᳙व᳓`, and across spaced virāma `पाणि᳓ना ह्य् **[[अवम᳓र्शतु|अ᳙वम᳓र्शतु]]**` where vowelless `ह्य्` places the *kṣaipra svarita* on the following anudātta vowel `अ-`).
  - When `पद-पाठः (यान्त्रिकः)` updates either member across a sandhi boundary (`वि᳓विच्यन्ते → विविच्यन्ते` + `अथ᳓ → अ᳓थ`), propagate **both** the resulting *ekādeśa* on Word1 and any change on the unelided tail of `ऽWord2` (`[[वि᳓विच्यन्ते|विविच्यन्ते᳓]] [[ऽथा᳓|ऽथा]]`), and prune/re-validate any existing `[[OLD|NEW]]` whose `NEW` disagrees with `पद-पाठः` + `पा॰ ८.२.४–६` (programmatically via `doc_curation.sanskrit.accent.reconciler` and `doc_curation.sanskrit.accent.validator`).

The exceptions below — fake accents, wrong de-novo insertion, splitting errors — may be applied directly.

### De-novo accents (यन्त्र-स्वरः)

Do not accent classical Sanskrit, and do not insert accents of your own where the source has none — only when explicitly asked. When you do, both of these are mandatory:

1. append `(यन्त्र-स्वरः)` to the `open`-ed details block name, i.e. `<details open><summary>विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)</summary>`;
2. add a `पद-पाठः (यान्त्रिकः)` block directly below the `मूलम्` and **above** Sanskrit commentaries (`*-टीका`) — one list item per pada in US accents (`᳓` / `᳙`), giving its accented form, concise source abbreviation(s) with exact and across-all-cases corpus occurrence counts (`*TS*-2/14, *RV*-0/5, *TB*-3`, `*TK*-M/N`, `*AV*-M/N`, `*SB-M*-M/N`, `*SB-K*-M/N`, `*VS*-M/N`, `*KS*-M/N`, `*MS*-M/N`, plus legacy `*ŚB*` alias for Mādhyandina, via `doc_curation.sanskrit.accent.provenance.annotate_padapatha_markdown_counts`: for accented declinable nominals (`सुबन्त`s), show `*CORPUS*-M/N` where `M` is the exact inflected pada count and `N` is the count across all `सुप्` case forms of that stem with consistent lexical svara whenever `N > M` — including `*CORPUS*-0/N` when only other cases occur in that corpus, and surfacing major corpora `*TS*, *RV*, *TB*, *AV*, *SB-M*, *SB-K*, *VS*` whenever `N > 0` — and show a single `*CORPUS*-M` when `N == M` or for indeclinables, finite `तिङन्त` verbs, enclitics, and vocatives; **never** leave a `*CORPUS*` tag without `-M` or `-M/N` (`N >= 1`), and **never** emit bare `*-0` or `*-M/0`; dictionary tags `*MW*`, `*Macdonell*`, `*Lanman*` omit counts; **never** use `*TA*` (Taittirīya Āraṇyaka) or `*EK*` (Ekāgnikāṇḍa) as sources for `पद-पाठः (यान्त्रिकः)` since their traditional svara-s are dubious, whereas `*SB-M*` (Mādhyandina Śatapatha), `*SB-K*` (Kāṇva Śatapatha), and legacy `*ŚB*` are permitted; **never** rubber-stamp unattested words as `(मूल-पाठः (अनाम्नातम्))`, `(आरण्यक-पाठः (अनाम्नातम्))`, or bare `समासस्वरः` — always derive the accent by Pāṇinian vyākaraṇa (`पा॰`, `उणादि॰`, `फि॰`) + lexica/commentaries, correcting `मूलम्` via `OLD → **NEW**` whenever vyākaraṇa proves `मूलम्` wrong (especially in verses that already contain accent errors); **never** invent fake or oxymoronic sūtra names like `बहुव्रीहौ समासस्य` — verify every sūtra against Aṣṭādhyāyī; always write Pāṇinian sūtra references with `पा॰` `U+0970` Devanagari abbreviation sign, **never** `पा०` `U+0966` digit zero, e.g. `पा॰ x.y.z`, `भास्करः`, `सायणः`), and any doubts. Title the block `<details><summary>पद-पाठः (यान्त्रिकः)</summary>` when `N == 0` (either de-novo or zero *vyatyasta* padas found); when auditing an already-accented source and correcting `N > 0` of `P` padas, title it `<details><summary>पद-पाठः (यान्त्रिकः - N/P व्यत्यस्त-स्वराः)</summary>` and write corrected padas as `- आङ्गीर᳓सः → **आङ्गीरसः᳓** (प्रातिपदिकम् आङ्गीरस᳓ (*MW*))` (unchanged padas omit any redundant prefix: `- आङ्गीरसः᳓ (प्रातिपदिकम् आङ्गीरस᳓ (*MW*))`).

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

- ब्र᳓ह्म (*TS*-70/157, *RV*-96/237, *SB-M*-138/203)
- स᳓म् (*TS*-589, *RV*-654)
- धत्तम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*-18, *SB-M*-2)
- त᳓त् (*TS*-687/2840, *RV*-552/3110)
- मे (अनुदात्तम्, पा॰ ८.१.१८, *TS*-396, *RV*-690)
- जिन्वतम् (तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८, *RV*-11)
</details>
````

#### Pada-pāṭha decision procedure

Never split padas or assign accents mechanically from word lists alone. Decide the pada-pāṭha and each pada's expected svara in this order:

1. **Read interleaved commentaries and translations first (mandatory for every pada):**
   - Check `भट्टभास्कर-टीका`, `सायण-टीका`, `रङ्ग-रामानुजः`, etc., and translations in the same mantra cluster **before** classifying any pada or assigning accents. Commentaries gloss each pada's exact sense, part of speech, gender/case/number, compound *vigraha*, finite verb root/person, and Vedic Pāṇinian rules (`परादिश्छन्दसि` पा॰ ६.२.१९९, `चवायोगे प्रथमा` पा॰ ८.१.५९, `उपाद् द्व्यजजिनमगौरादयः` पा॰ ६.२.१९४, `छान्दसं दीर्घत्वम्/ह्रस्वत्वम्`, `स्वरव्यत्ययः`):
     - **Subanta/kṛdanta vs tiṅanta vs āmantrita:** Never guess from surface endings (`प्रसूती` in `यतः प्रसूता जगतः प्रसूती` = nom. sg. fem. `प्र᳓-सूतिः` with *chāndasa* `-ई` per Bhāskara `"प्रसूती त्रिगुणात्मिका प्रकृतिः ... छान्दसं दीर्घत्वम्"` & Sāyaṇa `"प्रसूतिः सृष्टिः"`, never an unsplit or unaccented verb; `प्र-दुघे᳓` = fem. dual *kṛdanta* `"प्रकर्षेण दोग्ध्र्यौ"`, not a finite verb; `दिश` in `दि᳓शो दिश` = 2sg *loṭ* `"प्रयच्छ / देहि"`, not *āmreḍita* `दिशः`; `सुत` = 2pl *loṭ* `"अनुजानीत"`, not `सुतः`; `तरसे` in `सुत᳓रसि तरसे! न᳓मः` = non-initial vocative per Bhāskara).
     - **Underlying case/gender behind *parasavarṇa* & Vedic endings:** Check commentaries to undo `पा॰ ८.४.५८ अनुस्वारस्य ययि परसवर्णः` (`गन्धद्वारान् दुराधर्षान् नित्यपुष्टाम्` → fem. acc. sg. `गन्ध᳓-द्वाराम्`, `दुर्-आधर्षा᳓म्` modifying `श्रियम्`; `सहस्रशीर्षन् देवम्` → masc. acc. sg. `सह᳓स्र-शीर्षम्` modifying `देवम्`, never vocative `स᳓हस्र-शीर्षन्`; `यस्मान् न` → `य᳓स्मात्`; `सवितारन् नृचक्षसम्` → `सविता᳓रम्`) and Vedic neut. pl. `-आ` (`पा॰ ६.१.७०`: `दुः-इता᳓`, `जाता᳓` — never `-आः`).
     - **Two-pada sandhi vs single compound:** Use commentary glosses to distinguish *yaṇ*-joined separate padas (`अ-कार्य-कारी᳓` + `अव-कीर्णी᳓` in `अकार्यकार्य᳙वकीर्णी᳓` via `पा॰ ८.२.४`, `ब्र᳓ह्म` + `पूता᳓`) from genuine single compounds (`प्रज᳓या सम्-विदानः᳓` — never phantom `स᳓न्` + `विदानः᳓`; `घोर-घो᳓र-तरेभ्यः` per Bhāskara `"घोरघोरतरेभ्यः"`).
   - Where a pāda or phrase has a parallel in `*TS*` or `*RV*`, follow its attested `<summary>पद-पाठः</summary>` / `rv-padapATha-dev` division.

2. **Split distinct sandhi-joined padas; never club non-compounds:**
   - Undo external vowel, visarga, and consonant sandhi into normalized isolated padas (`देवीर्भुवनसूवरीः` → `देवीः᳓` + `भुवन-सू᳓वरीः`; `उत्तानस् त्वाङ्गीरसः` → `उत्तानः᳓`, `त्वा`, `आङ्गीरसः᳓`; `सह सञ्चस्करर्धिया` → `सह᳓`, `सञ्चस्कर`, `ऋ᳓द्धिया`; visarga-lopa `पार्थिवस्यैक इद्वशी` → `पा᳓र्थिवस्य`, `ए᳓कः`, `इ᳓त्`, `वशी᳓`, never `एकम्`; `लोपः शाकल्यस्य` पा॰ ८.३.१९ prevocalic `वा᳓`/`वेह` → `वै᳓`, `-स्मा` → `-स्मै`; `-आँश्च`/`-ईँश्च`/`-ऊँश्च` via `पा॰ ८.३.७` → `-आन्`/`-ईन्`/`-ऊन्` + `च`; `भूर्भुवस्सुवः` → `भूः`, `भु᳓वः`, `स्वः᳙`; periphrastic perfects `मीमांसाम्` + `चक्रे`, `आम्` + `आस`).
   - **Never club `न` + word as a compound:** `नञ्-तत्पुरुष` drops `न्` (`पा॰ ६.३.७३ नलोपो नञः` → `अ-`/`अन्-`), so `नान्यः`, `नान्यत्`, `नैनम्` (`न᳓` + `एनम्`), `नाणीयः` (`न᳓` + `अ᳓णीयः`), `नापरम्` (`न᳓` + `अ᳓परम्`) are always two separate padas, never `न-अन्यः` or `नैनम्`.
   - Likewise never club `मा`, standalone pronouns/indefinites (`यः`, `सः`, `तम्`, `अहम्`, `अस्य`, `एनम्`, `एतत्`, `इयम्`), particles/enclitics (`च`, `चन`, `चित्`, `वा`, `हि`, `उ`, `ह`, `एव`, `इति`, `मे`, `ते`, `त्वा`, `नः`, `वः`), copulas/verbs (`-असि`, `-अस्मि`, `-अस्ति`, `-एति`), or case-inflected `सुबन्त`s — even when sandhi/anunāsika binds them or when the source leaves a space (`सञ् च` → `स᳓म्` + `च`, never `स᳓ञ्च`; `महद्भिश्च` → `महद्भिः᳓` + `च`; `किञ्च` → `कि᳓म्` + `च`; `किञ्चन`/`कश्चन`/`किञ्चित्`/`कश्चित्` → `कि᳓म्`/`कः᳓` + `चन`/`चित्` per *TS*/*RV* padapāṭha `किम् । चन`, `कः । चन`, `कः । चित्`; `अहमस्मि` → `अह᳓म्` + `अस्मि`; `ब्रह्माहमस्मि` → `ब्र᳓ह्म` + `अह᳓म्` + `अस्मि`; `घर्मैतत्` → `घ᳓र्म` + `एत᳓त्`; `धारितेयम्` → `धारिता᳓` + `इय᳓म्`; `सामभिराक्तखन्त्वा` → `सा᳓मभिः` + `आ᳓क्त-खम्` + `त्वा`) — unless a genuine Vedic *aluk*, *iva*-samāsa (`द्यौः᳓-इव`, *RV* `ऽइव`), or *upapada* compound (`तपसः-पते`, `वाचः-पतिः`, `आयुः-दाः`, `स्वयम्-भु`, `तत्-पुरुषाय`). Keep *vīpsā* iteratives (`पा॰ ८.१.४` e.g. `सप्त-सप्त`, `दमे-दमे`, `दिवे-दिवे`, `अहः-अहः`) hyphenated like *TS*/*RV* `ऽ`/`-`, whereas clausal *āmreḍita* repetitions (`पा॰ ८.१.३` e.g. `आ᳓पम् आपाम्`) remain two separate bullets (`आ᳓पम्`, `आपाम्`).

3. **Keep samasta-padas together with `-` at compound joints:**
   - Never split a *samasta-pada* across multiple bullets. Keep it as one item with `-` between compound members (`वायु-अ᳓श्वाः`, `रश्मि-प᳓तयः`, `म᳓रीचि-आत्मानः`, `भुवन-सू᳓वरीः`), undoing internal sandhi cleanly at `-`.
   - Keep `गतिकृदन्त` participles and verbal derivatives hyphenated as compounds (`नि-द᳓धत्`, `सं-भू᳓तः`, `वि-द᳓धत्`, `पा॰ ६.२.१३९ गतिकारकोपपदात्कृत्`) — never treat them as finite `तिङन्त` verbs (`पा॰ ८.१.२८` does not apply to participles).
   - Do **not** place `-` before *kṛt* or *taddhita* suffixes (`पुत्रवत्त्वा᳓य`, `आङ्गीरसः᳓`).

4. **Honor pause-final sandhi (`पा॰ ८.३.१५ खरवसानयोर्विसर्जनीयः`):**
   - Visarga (`-ः`) never drops before `।` or `॥`. Never "restore" `-ः` onto a word ending in `-अ` at pause (`मे सुत ।`, `इतोहित ।`).

5. **Separate or compound `upasarga` (`गति`) + finite verb (`तिङन्त`) by clause type, respecting `पादादि` (`पा॰ ८.१.१८`):**
   - **Main clause (unaccented verb, `पा॰ ८.१.२८ तिङ्ङतिङः`):** Split **every** main-clause `upasarga`(s) + finite verb combination into separate padas — even when the finite verb already lost its accent cleanly without `→` (`सम॑वर्त॒ताधि॑` → `स᳓म्`, `अवर्तत`, `अ᳓धि`; `सञ्चस्कर` → `सम्`, `चस्कर`; `उपह्वये` → `उ᳓प`, `ह्वये`; `प्रसृपत` → `प्र`, `सृपत`; `आ᳓वह` → `आ᳓`, `वह`), where the `upasarga` keeps its udātta (with `पा॰ ८.१.७० गतिर्गतावत्` when chained, e.g. `अ᳓प` + `प्र` + `सृपत`) and the verb is unaccented. In particular, when `मूलम्` has `-आ᳓` + verb (`जैत्र्या॒यावि॑शताम्`, `मामा वि॑शतात्`, `ज्योति॒षागुः`, `इ॒हाग॑ताम्`), hypothesize `आ᳓` (`upasarga`, yielding `-आ᳓` by `पा॰ ८.२.५` with 0 vyatyasta: `जै᳓त्र्याय` + `आ᳓` + `विशताम्`, `ज्यो᳓तिषा` + `आ᳓` + `अगुः`, double avagraha `ऽऽ` in `विश्वास-प्रस्तुतिः`) rather than inventing a vyatyasta on the preceding word + an `अ-`verb (`अविशताम्`), and never emit double-canceling `आ → **आ᳓**` + `अ᳓गात् → **अगात्**` arrows when `आ᳓ + अगात् = आ᳓गात्` already matches `मूलम्`. When an accented `upasarga` compounds before another `upasarga` and finite verb in an audited source (`अभि᳓संबभूव`), split them and keep only the accented `upasarga` udātta (`अभि᳓` accented, `सम्` unaccented; never cite `*TA*` or `*EK*` as a source). Do not split simplex roots or `अ-`/`आ-` augments that merely resemble prefixes (`आस्ते`, `आहुः`, `आशत`, `अवतु`, `विद्यते`, `विवेश`, `अपश्यत्`, `अवसन्`, `अतिरम्`), nor noun/kṛt compounds (`सु-कृ᳓ताम्`, `प्रति-ष्ठा᳓म्`).
   - **`पादादि`, `तिङः परं तिङ्`, & `आमन्त्रितं पूर्वमविद्यमानवत्` exemptions (`पा॰ ८.१.१८`, `८.१.२८`, `८.१.७२`):** *Svaranighāta* (`पा॰ ८.१.२८ तिङ्ङतिङः`) applies **only** to *non-pāda-initial* finite verbs immediately following an *atiṅ*:
     - A finite verb immediately after another `तिङन्त` is **not** de-accented (`वान्ति पत᳓यन्ति`, `आ᳓ वह माद᳓यस्व`, `जिहते पि᳓न्वते`, `आ᳓ववर्तिन्न् अ᳓भूद्`).
     - By **`पा॰ ८.१.७२ आमन्त्रितं पूर्वमविद्यमानवत्`**, a pāda-initial vocative is treated as non-existent for the following word's nighāta, so a finite verb right after a pāda-initial vocative (`मृ᳓त्तिके ह᳓न`, `मृ᳓त्तिके दे᳓हि`) stands at *pādādi* and **retains its udātta** (whereas in `वित᳓स्तया ऽऽर्जीकीये श्रुणुहि`, treating pāda-initial `आ᳓र्जीकीये` as non-existent still leaves `वित᳓स्तया` before `श्रुणुहि`, so `श्रुणुहि` becomes anudātta).
     - A finite verb standing at the start of **any** metrical *pāda* or sentence (after `।`, `॥`, or at an unmarked 8/11/12-syllable *pāda* boundary — e.g. `आ᳓पम्` in `आ᳓पम् आपाम्`, `ल᳓म्बति`, `वोचे᳓म`, `ज᳓हाति`, `जी᳓वामि`, `पुन᳓न्तु`, `विधे᳓म`) retains its udātta; never flag it with `पा॰ ८.१.२८` or strip its accent in `विश्वास-प्रस्तुतिः`. Note however that when `गति + तिङन्त` opens a main-clause pāda (`उ᳓द् दीप्यस्व`, `प्र᳓ त्नोषि`, `स᳓म् तापयति`), the `गति` occupies *pādādi* and keeps its udātta while the following `तिङन्त` follows an *atiṅ* (`गति`) and becomes anudātta (`पा॰ ८.१.२८`). Distinguish participles, gerundives, and nominal forms (`प्र-दुघे᳓`, `उच्च᳓रत्`, `रेज᳓ती`, `निधा᳓य्यः`, `सम्-दृ᳓शे`) from finite verbs.
   - **Subordinate / nighāta-blocked clause (accented verb):** Check the *same* clause for `यद्`-वृत्त words (`यः`, `यम्`, `यत्`, `येन`, `यस्य`, `यत्र`, `यदा`, `यथा`, `यदि` — `पा॰ ८.१.६६ यद्वृत्तान्नित्यम्`, e.g. `यो᳓ ... प᳓श्यत`, `य᳓च् च ... श्रूय᳓ते`, `य᳓थै᳓क ऋ᳓षिर् वि-जा᳓नते`), `हि` (`पा॰ ८.१.३४ हि च`) vs `चेत्`/`नेत्`/`कुवित्`/`यत्र` (`पा॰ ८.१.३०` — scoped strictly to its own clause and **exclusively to finite `तिङन्त` verbs**: **never** cite `पा॰ ८.१.२८–६८` on non-`तिङन्त` pronouns/particles/upasargas/nominals such as `अस्य`, `मम`, `वाम्`, `अहम्`, `ते`, `उत्`, `परि`, and **never** bleed `हि च` or `यद्वृत्तान्नित्यम्` into preceding main clauses like `उदीर्ष्वातः पतिवती ह्येषा` / `अग्निः प्राश्नातु प्रथमः स हि वेद` or following `मा`/`नो`/`उ`/`तत्`/`सः`/`तस्मै`/`एवम्` main clauses like `मा रिषामा वयं तव`), `च`/`वा` verb coordination (`पा॰ ८.१.५९ चवायोगे प्रथमा`: `स्वां᳓ चाग्ने तनु᳓वं पिप्र᳓यस्वास्म᳓भ्यं च ... आ᳓ यजस्व`), or `चादिलोपे विभाषा` (`पा॰ ८.१.६३`: `सं᳓ बाहु᳓भ्यान् न᳓मति सं᳓ प᳓तत्रैः`). Here the `तिङन्त` retains its accent, and an immediately adjacent preceding `गति` becomes anudātta (`पा॰ ८.१.७१ तिङि चोदात्तवति`) and compounds as a single bullet with the `तिङ्` (`उदाजहा᳓र`, `प्रचोद᳓यात्`, `अभि-ऐ᳓रयन्त`, `वि-भ्रा᳓जते`, `अव-म᳓र्शतु`). However, when a particle or other word **intervenes** (*tmesis* / व्यवधान, e.g. `च`, `उ`, `अपि`, `बाहु᳓भ्याम्`), `पा॰ ८.१.७१` and `गति + तिङ्` compounding do **not** cross the intervening word: split each `गति`, intervening word, and accented verb as its own bullet preserving original udāttas (`- स᳓म्`, `- च`, `- वि᳓`, `- च`, `- ए᳓ति`). Correlative `तद्`-clauses (`य᳓द् ... त᳓द् अ᳓प गच्छतात्`) and main clauses following verbless relative pādas (`यो᳓ऽस्य ... वशी᳓ । यमं ... गाय`) are main clauses governed by `पा॰ ८.१.२८`, never `पा॰ ८.१.६६`.

6. **Verify the forward-sandhi round-trip invariant:**
   - Joining the proposed `पद-पाठः` sequence with Pāṇinian and Vedic sandhi rules must reconstruct `मूलम्` (programmatically via `doc_curation.sanskrit.accent.sandhi_check.verify_mantra_sandhi`; modulo recensional allographs such as `ळ/ड`, `व्ँ/ं`, and gemination after `र्`). Without an intervening daṇḍa (`।`/`॥`), samhitā sandhi still applies across *viṣama-pāda* line wraps (`\n`): e.g. `भव्य॑म् आ \nइ॒दन्` is *visarga-lopa* (`आः + इदम् → आ इदम्`, verified in commentaries as `आसीत्`), never `आ + इदम्`. Any discrepancy — e.g. `एकम् + इत् → एकमित् ≠ एक इत्` (`एकः + इत्`), `आ + इदम् → एदम् ≠ आ इदम्` (`आः + इदम्`), `सुप्रयतौ + इह → सुप्रयताविह ≠ सुप्रयतेह` (`सु-प्रयते + ह`), or `हिंसीः + जातवेदः → हिंसीर्जातवेदो ≠ हिंसीज्जातवेदो` (`हिंसीत्`) — proves a wrong inflection or split and must be repaired before checking accents. Do not allow unconstrained `V + V` hiatus in forward-sandhi checks; accept hiatus only across `।`/`॥` pauses, grammatically licensed splits (*pragṛhya* `-ई`/`-ऊ`/`-ए` duals & `-ओ` nipātas, `लोपः शाकल्यस्य` `-ए`/`-ऐ`/`-ओ`, `-आः`/`-अः` visarga-lopa), or documented metrical hiatuses.

7. **Project sandhi accents from `मूलम्` and evaluate `वाक्य-स्वरः` before lexical lookup:**
   - **Ground truth, newline pauses, & classical `॑`-after-udātta ambiguity (`पा॰ ८.२.५ एकादेश उदात्तेनोदात्तः`):** Always project `पद-पाठः` accents strictly from `मूलम्` (`accent.to_US_accents(text, pauses=r"[।॥,;]+")` when line breaks lack `।`/`॥` so `\n` is not treated as a pause), never from `विश्वास-प्रस्तुतिः` (which is checked separately for `[[OLD|NEW]]` suggestions), and never mistake classical dependent svarita `॑` (one syllable *after* the udātta, e.g. `य॒मो ह॑वे॒ह` = `यमो᳓ ह वेह᳓`, where `ह` is unaccented) for an udātta on the marked syllable. Crucially, when `मूलम्` places `॑` immediately after an udātta syllable (with no intervening `॒`, e.g. `पर॒मे व्यो॑मन्न्`, matching *TS* `प॒र॒मे । व्यो॑म॒न्`), classical notation leaves dependent svarita and independent `᳙` indistinguishable: `to_US_accents` omits `᳙` on `व्यो`, even though `मूलम्` can perfectly well be read as `व्यो᳙मन्न्`. Do **not** flag such a pada as a `vyatyasta-svara` (`व्योमन्न् → **व्यो᳙मन्न्**`) — record `- व्यो᳙मन्न् (*TS*)` directly and do not count it in `N/P`, while still checking whether US-accented `विश्वास-प्रस्तुतिः` itself dropped `᳙` (`[[व्योमन्|व्यो᳙मन्]]`). Attribute a merged boundary udātta (`-त + अ᳓- → -ता᳓-` in `अवर्तता᳓धि`, `-अ + ऋ᳓- → -अर्᳓-` in `सञ्चस्कर᳓र्धिया`) using each pada's syntactic role and attested accent (`अवर्तत` unaccented + `अ᳓धि`; `सञ्चस्कर` unaccented + `ऋ᳓द्धिया`). Sandhi-induced independent svarita `᳙` (*kṣaipra* `व्य᳙शेम`, *abhinihita* `यो᳙ऽपा᳓म्`) corresponds to padapāṭha udātta `᳓` (`वि᳓`, `यः᳓`); keep `᳙` in padapāṭha only on lexical svaritas (`स्वः᳙`, `क्व᳙`, `वीर्य᳙म्`).
   - **Āmreḍita (`पा॰ ८.१.३ अनुदात्तं च`):** The repeated second word (`आ᳓पम् आपाम्`, `अस्मा᳓त् अस्मात्`) must be unaccented.
   - **Vocatives (`आमन्त्रित`):** Clause/pāda-initial vocatives are *ādyudātta* (`पा॰ ६.१.१९८`); non-initial vocatives are unaccented (`पा॰ ८.१.१९`).
   - **Enclitics & homophone disambiguation (`पा॰ ८.१.१८`):** `मे`, `ते`, `त्वा`, `मा`, `नः`, `वः`, `च`, `वा`, `उ`, `ह`, `स्म`, and unemphatic anaphoric `इदम्`/`एतद्` forms (`अस्य`, `अस्मै`, `एनम्`, `पा॰ २.४.३२`) are unaccented (`पा॰ ८.१.१८`) and never stand at clause/pāda start. Never misclassify their accented homophones as enclitics: prohibitive `मा᳓` (`माङ्`, always udātta at clause start or before injunctives / `मे` / `नः` / `मम` / `मा`) vs enclitic `मा` ("me"); demonstrative nom. pl. `ते᳓` (`तद्`) vs enclitic `ते`; particle `वै᳓` (prevocalic `वा᳓`, `ह वै᳓` — ignore saṁhitā `'वा᳓'` attestations in TB/TK/AV when resolving enclitic `वा`) vs enclitic `वा` ("or").
   - **Compound accents (`समास-स्वरः` — never apply mechanical `पा॰ ६.१.२२३` *antodātta* or single-member *MW* extrapolation blindly):**
     - *Bahuvrīhi* (`पा॰ ६.२.१ बहुव्रीहौ प्रकृत्या पूर्वपदम्`): keeps the *pūrvapada*'s *prakṛtisvara* (`हि᳓रण्य-कक्ष्यान्`, `अ᳓यस्-शफान्`, `गन्ध᳓-द्वारान्`, `ए᳓क-नीळम्`, `स᳓र्व-रूपाः`, `अग्नि᳓-वर्णाम्`, `वि᳓ष्णु-क्रान्ते`, `ऊर्ध्व᳓-रेतम्`, `नारायण᳓-परम्`, `शत᳓-बाहुना`, `त्रि᳓-सुपर्णम्`, `पु᳓ष्कर-स्रजा`, `आदित्य᳓-वर्णम्`), overridden only by explicit Pāṇinian *apavāda*s: `विश्व` epithets (`पा॰ ६.२.१०६ बहुव्रीहौ विश्वं संज्ञायाम्` *pūrvapada-antodātta*: `विश्व᳓-कर्मणः`, `विश्व᳓-शं-भुवम्`, `विश्व᳓-रूपाय`, `विश्व᳓-आत्मानम्`); `सु` + `-मन्`/`-अस्` (`पा॰ ६.२.११७`: `सु-म᳓नाभिः`); `सु` + disyllabic `आद्युदात्त` uttarapada in Chandas (`पा॰ ६.२.११९ आद्युदात्तं द्व्यच् छन्दसि`: `सु-धु᳓रान्`, `सु-सो᳓मया`); remaining `नञ्`/`सु` bahuvrīhis (`पा॰ ६.२.१७२ नञ्सुभ्याम्` *antodātta*: `अक्रतु᳓म्`, `अनन्त᳓म्`); *svāṅga* `-अक्ष`/`-सक्थ` (`पा॰ ५.४.११३ + ६.१.१६३` `षच्` *antodātta*: `हिरण्य-अक्षा᳓न्`, `विश्व-अक्ष᳓म्`, `विरूप-अक्ष᳓म्`, `सहस्र-अक्ष᳓स्य`); `-मुख` blocked after *avyaya* (`पा॰ ६.२.१६८`: `विश्व᳓तः-मुखः`, `अधो᳓-मुखम्`, `प्रत्य᳓ङ्-मुखाः`); and *vanaspati*-class dual-udātta compounds (`पा॰ ६.२.१४० उभे वनस्पत्यादिषु युगपत्`: `ब्र᳓ह्मणस्-प᳓तिः`, `बृ᳓हस्-प᳓तिः`).
     - *Tatpuruṣa* & *gati/kāraka/upapada*: `नञ्` (`अन्`/`अ`), *avyaya*, *tṛtīyā*, *saptamī*, *upamāna* retain *pūrvapada* *prakṛtisvara* (`पा॰ ६.२.२`, `६.२.४८`, `६.२.४९ गतिरनन्तरः`: `अ᳓नश्यतः`, `अ᳓जायमानः`, `ब्र᳓ह्म-पूता`, `नि᳓र्मुक्तः`, `प्र᳓-ओतः`), **except** `गतिकारकोपपदात् कृत्` (`पा॰ ६.२.१३९` — *kṛdanta* *uttarapada* keeps its `कृत्` *prakṛtisvara*: `ल्यु`/`ल्युट्` `पा॰ ६.१.१९३ लिति` penult udātta in *kartṛ*/*karaṇa*/*adhikaraṇa* or after `गति` such as `वाल-ब᳓न्धनः`, `अघ-म᳓र्षणः`, `अमृत-अपिधा᳓नम्`, `कल-विक᳓रणाय`, `णिनिः` `पा॰ ३.१.३` — never `नित्`! — such as `लोक-धारि᳓णी`, `अन्ते-वासि᳓नम्`, `क्विप्` `अग्र-भु᳓क्`, `पुण्य-कृ᳓तः`, `ण्यत्` `भिक्षा-चर्य᳙म्`, `क्वसु`/participles `सव्ँ-विदानः᳓`, `शत्रु-ह᳓त्यै`, `गुरु-तल्प-गः᳓`, `पुरमद्ध्य-सँस्थ᳓म्`, `सद्यो-जात᳓म्`), overridden in turn by explicit `६.२.१३९` *apavāda*s: `पा॰ ६.२.१४४ थाथघञ्क्ताजबित्रकाणाम्` (`प्र-बोधः᳓`, `जीवन-प्रदः᳓`, `पराङ्-गताः᳓`, `निधि-गोपः᳓`), `पा॰ ६.२.१४५ सूपमानात् क्तः` (`सु-तृप्त᳓म्`), `पा॰ ६.२.१५० अनो भावकर्मवचनः` (*bhāva*/*karman* `-अन` after non-*gati* *kāraka*, e.g. `अति-आशना᳓त्`, `वेद-अनुवचन᳓म्`), and `नञ्` + `कृत्य` (`पा॰ ६.२.१६०`: `अनाधृष्यः᳓`). Plain *karmadhāraya*/*ṣaṣṭhī*/*dvandva* without apavāda follow `पा॰ ६.१.२२३ समासस्य` (`अन्न-पाने᳓`, `इष्टा-पूर्त᳓म्`, `विश्वाधि᳓कः`, `सन्न्यास-योगा᳓त्`, `ज्योतिर्-आत्मा᳓`).
     - **Single-accent & non-zero-accent invariants (`पा॰ ६.१.१५८ अनुदात्तं पदमेकवर्जम्`):**
       - **No zero-accent non-nighāta padas:** Every Sanskrit pada carries **one** accent (`᳓` or `᳙`, or two under `पा॰ ६.२.१४०`) unless de-accented by an explicit Pāṇinian rule cited in its provenance (`पा॰ ८.१.२८` main-clause `तिङन्त` with any `गति` split off as its own accented pada, `पा॰ ८.१.१८` enclitics, `पा॰ ८.१.१९` non-initial vocatives such as `देवि`, `शर्व`, `वृषभ`, `पा॰ ८.१.३` *āmreḍita*, `पा॰ ८.१.७०–७१` *gati*, `पा॰ २.४.३२ / २.४.३४` *anvādeśa* `अस्य`, `एनम्`). **Never** leave a *subanta*, *kṛdanta*, compound, adverb, or main-clause *upasarga* with 0 accents (`प्र-सूती → **प्र᳓-सूती**`, `जात्यै → **जा᳓त्यै**`, `दन्तिः → **दन्तिः᳓**`, `स्तब्धः → **स्तब्धः᳓**`, `महा-ज्ञेयम् → **महा-ज्ञेय᳓म्**`, `प्र → **प्र᳓**`), **never** leave `→ **?**` unresolved, and **never** rubber-stamp an unaccented or unanalyzed form as `(आरण्यक-पाठः (अनाम्नातम्))`. Watch for word-initial udāttas hidden in `पा॰ ८.२.५` *ekādeśa* with the prior word (`नाति॑भवे` = `न᳓` + `अ᳓ति-भवे`, `वि॒तस्त॒या ऽऽर्जी॑कीये` = `वित᳓स्तया` + `आ᳓र्जीकीये`) or lost behind a prior word's dependent `॑` in corrupt prints (`तं प्र॑पद्यामि`, `सोऽक्ष॑रः`, `कि॒ञ्चिज्ज॑गत्य॒स्मिन्`).
       - **No unresolved multi-udātta padas:** Resolve every multi-udātta compound via the rules above rather than leaving `**?**`, checking whether `to_US_accents` duplicated an *ekādeśa* udātta across internal vowel sandhi (`विश्वा᳓त्मन्` → `विश्व᳓-आ᳓त्मानम्`, `सप्ता᳓र्चिषः` → `सप्त᳓-अर्चि᳓षः`) or misread missing `॒` marks in printed `मूलम्`. Always validate with `doc_curation.sanskrit.accent.validator` (`validate_accented_markdown` / `validate_paired_vp_and_tk`, which enforces header counts, `पा॰ ६.१.१५८` non-zero accents, no `→ **?**`, and no unsplit `पा॰ ८.१.२८` `upasarga + tiṅanta`).
   - **Attestation before stem extrapolation, multi-accent homograph disambiguation, & Taittirīya normalization:** Prefer attested Vedic forms (`*TS*`, `*RV*`, `*TB*`, `*TK*`, `*AV*`, `*SB-M*`, `*SB-K*`, legacy `*ŚB*`, `*VS*`, `*KS*`, `*MS*` — **never** use `*TA*` Taittirīya Āraṇyaka or `*EK*` Ekāgnikāṇḍa as sources since their traditional svara-s are dubious; `*SB-M*` (Mādhyandina Śatapatha), `*SB-K*` (Kāṇva Śatapatha), and legacy `*ŚB*` are fine) over `*MW*` stem extrapolation, normalize Taittirīya anunāsika (`व्ँ`/`य्ँ`/`ल्ँ` ↔ `ं`) when matching against `*TS*`/`*TB*`, and do not override a valid single-accent Vedic form with an unattested `*MW*` homograph stem. Crucially, whenever a pada or stem has **multiple genuine lexical, inflectional, or śākhā accents** (e.g. `वे᳓द` 'Śruti/knowledge' `पा॰ ६.१.२०३` vs `वेद᳓` 'darbha-muṣṭi/wealth' `घञ्`; `ध᳓र्म` 'sacred duty/law' vs `धर्म᳓` 'bearer'; `ब्र᳓ह्मन्` neut. 'Brahman/Veda' vs `ब्रह्म᳓न्` masc. 'Brahmā/priest'; `अ᳓न्तक` 'Death/ender' vs `अन्तक᳓` 'border'; `म᳓हः` neut. 'greatness/light' vs `महः᳓` oblique of `मह्` `पा॰ ६.१.१६८`; `वा᳓चः`/`रा᳓यः`/`दि᳓शः`/`ऊ᳓र्जः` nom./acc. pl. vs `वाचः᳓`/`रायः᳓`/`दिशः᳓`/`ऊर्जः᳓` gen./abl. sg. `पा॰ ६.१.१६८`; `वैदेहः᳓` `अण्` 'of the bodiless' vs `वै᳓देहः` `अञ्` 'king of Videha'; `सह᳓` adv. vs `स᳓हः` neut.; `सु-कृत᳓म्` adj. `पा॰ ६.२.१४५` vs `सु᳓-कृतम्` neut. `पा॰ ६.२.२`), select the accent required by context/commentaries and **list the alternative accent(s) inside the parentheses**, stating why the chosen form is preferred (sense, gender, case, *vigraha*, or recension — e.g. `- वे᳓द᳓म् → **वे᳓दम्** (श्रुत्यर्थे वे᳓दम् आद्युदात्तम् श्रेयः, वृषादिः पा॰ ६.१.२०३, *AV*, *RV* वे᳓दः, *TB*; दर्भमुष्टौ धने वा वेद᳓म् अन्तोदात्तम्, *TS* वेदः᳓, *MW*)`).

### Fake accents

Some Vedic texts (e.g. some taittirīya āraṇyaka sections) carry fake accents — typically mechanically applied runs of udAtta. Detect:

```python
accent.detect_fake_US_accents(text)  # → suspicious runs of >5 consecutive ᳓; empty list = nothing found
```

If you are explicitly asked, you may also spot other fake-accented US text beyond what the above detector finds. Here direct correction is allowed:

1. Remove **all** accents from that `विश्वास-प्रस्तुतिः` block (`accent.strip_accents(text)`), or keep the unaccented text if that was already done by hand. In both cases, append `(स्वराः पूर्याः)` ("accents still to be supplied") to the details block name, i.e. `<details open><summary>विश्वास-प्रस्तुतिः (स्वराः पूर्याः)</summary>`.
2. Re-insert accents only when asked — and when filling US svara-s into an unaccented or `(स्वराः पूर्याः)` `विश्वास-प्रस्तुतिः` block whose `मूलम्` carried accents:
   - Ensure `<details><summary>पद-पाठः (यान्त्रिकः...)</summary>` is present and clean below `मूलम्`, then populate US accents directly onto `विश्वास-प्रस्तुतिः` (`doc_curation.sanskrit.accent.reconciler.fill_vp_accents_from_padapatha`).
   - Update the `विश्वास-प्रस्तुतिः` summary (via `format_filled_vp_summary`) to append `(स्वराः व्यत्यस्ताः D/P)` when `D > 0` of `P` padas differed from `मूलम्` (mirroring `पद-पाठः (यान्त्रिकः - D/P व्यत्यस्त-स्वराः)`, e.g. `<details open><summary>विश्वास-प्रस्तुतिः (स्वराः व्यत्यस्ताः 5/25)</summary>`), omit the suffix when `D == 0` (`<details open><summary>विश्वास-प्रस्तुतिः</summary>`), or use `(यन्त्र-स्वरः)` when `मूलम्` itself was completely unaccented.

### Splitting errors

Typical `मूलम्`-block errors are at the beginnings and terminations of split blocks, e.g.

> "सम्मा॑ऽऽसिञ्चन्तु म॒रुत॒स् समिन्द्र॒स् सं बृह॒स्पतिः॑ । सम्मा॒यम॒ग्निस् सि॑ञ्च॒त्वायु॑षा च॒ बले॑न॒ चायु॑ष्मन्तङ् करोत॒ मा" इति।

has a missing svarita at the end. These errors likely arose from faulty splitting by a human. Where an error is found, fix it in the `मूलम्` block and in the corresponding `विश्वास-प्रस्तुतिः` block. In such cases, you can correct directly, without the [[OLD|NEW]] suggestion.

## Local hyphenation & specialist models (only when specifically requested)

**Recommendation (`doc_curation/llm/proofreader/README.md`):** Use local `hyphene` (`doc_curation.sanskrit.hyphenator`, `distill/README.md`) for fast clean-text hyphenation of US-accented `विश्वास-प्रस्तुतिः` (`᳓`/`᳙` preserved losslessly); use `Qwen3-14B` (`proofread_text` when OCR cleanup & discourse clause breaks are also needed, or `accent_helper` below only when specifically requested as a RAG-grounded `पद-पाठः` draft assistant).

**Mandatory random quality check & redo:** Whenever `hyphene`, `accent_helper`, `reconciler`, or `proofread_text` is run, randomly spot-check sampled mantra clusters (checking commentary glosses, `पा॰ ६.१.१५८` / `६.२.*` / `८.१.२८` / `८.२.४–६`, compound splits, and `[[OLD|NEW]]` spans) in addition to running `sandhi_check` and `validator`, and redo any flawed padas or blocks directly.

1. **Distilled local SLP1 neural hyphenator (`doc_curation.sanskrit.hyphenator.hyphene`):** Used automatically by `doc_curation.sanskrit.accent.samasa.decompose_samasa_for_padasvara` (alongside `<2 ms` memory-mapped `BytesTrie` lexicon lookup in `lexicon.py`), and can be called directly (`hyphene(vp_text, clause_newlines=True)`) on CPU in `~3–16 ms`/sentence.
2. **Fine-tuned `Qwen3-14B` LoRA `पद-पाठः (यान्त्रिकः)` draft assistant (`doc_curation.llm.proofreader.accent_helper`, only when specifically requested):** Grounds `doc_curation/data/models/qwen3-14b-sanskrit-lora/` (`~46.5%` draft char similarity) with retrieved `*RV*`/`*TS*`/`*AV*`/`*MW*` Babylon candidates — always run the deterministic sandhi/accent validators afterward:

```python
from doc_curation.llm.proofreader import PADAPATHA_ACCENT_SYSTEM_PROMPT, ProofreaderBackend
from doc_curation.llm.proofreader.accent_helper import format_padapatha_user_prompt, retrieve_accent_candidates
from doc_curation.sanskrit.accent import reconciler, sandhi_check, validator

backend = ProofreaderBackend(base_url="https://<tunnel>/v1")
hits = retrieve_accent_candidates(mula_text)
prompt = format_padapatha_user_prompt(
    mula_text, commentary_text=tika_text, translation_text=trans_text, lexicon_hits=hits,
)
padapatha_block = backend.new_chat(PADAPATHA_ACCENT_SYSTEM_PROMPT).send_text(prompt)
# Always verify forward sandhi & पा॰ ६.१.१५८ / ८.१.२८ invariants deterministically:
# sandhi_check.verify_mantra_sandhi(...), validator.validate_accented_markdown(...), reconciler.reconcile_markdown_blocks(...)
```
