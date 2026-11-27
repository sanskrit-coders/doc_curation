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

Match the notation to the block: `विश्वास-प्रस्तुतिः` always uses **US accents** (`᳓` / `᳙`, using uniform `᳙` on independent svaritas such as *abhinihita* `सो᳙ऽकामयत`; use `to_us_accents_markdown(..., preserve_existing_us=True)` when files mix dependent and US marks so conversion is not skipped), especially in shared `static/.../vishvAsa-prastutiH/` and `yajuH/sarva-prastutiH/` files (`commentary_translation` and `vedic` skills); `मूलम्` keeps the source's own notation (classically dependent `॒`/`॑`).

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

- **Never skip bold tokens or split combining marks across `**`/`[[...]]`:** Keep markdown `**...**` delimiters outside the suggestion bracket (`**[[ये᳓नावृत᳓ङ्|ये᳓ना᳓वृतङ्]]**`), so bold words in `विश्वास-प्रस्तुतिः` are checked and suggested just like unbolded ones. **Never** close `**` or `[[...]]` between a Devanagari base character and trailing vowel signs, anusvāra, visarga, virāma, or svara marks (`᳓`/`᳙`) — e.g., never `**मा**᳓` or `**[[मा|मा᳓]]**᳓`; keep all combining marks inside (`**[[मा|मा᳓]]**`, checked/repaired by `validator.find_vp_integrity_issues` and `reconciler.normalize_vp_bolding_splits`).
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
2. add a `पद-पाठः (यान्त्रिकः)` block directly below the `मूलम्` and **above** Sanskrit commentaries (`*-टीका`) — one list item per pada in US accents (`᳓` / `᳙`), giving its accented form, concise source abbreviation(s) with exact and across-all-cases corpus occurrence counts (`*TS*-2/14, *RV*-0/5, *TB*-3`, `*TK*-M/N`, `*AV*-M/N`, `*SB-M*-M/N`, `*SB-K*-M/N`, `*VS-M*-M/N`, `*VS-K*-M/N`, `*KS*-M/N`, `*MS*-M/N`, plus legacy `*ŚB*` and `*VS*` aliases for Mādhyandina, via `doc_curation.sanskrit.accent.provenance.annotate_padapatha_markdown_counts`: for accented declinable nominals (`सुबन्त`s), show `*CORPUS*-M/N` where `M` is the exact inflected pada count and `N` is the count across all `सुप्` case forms of that stem with consistent lexical svara whenever `N > M` — including `*CORPUS*-0/N` when only other cases occur in that corpus, and surfacing major corpora `*TS*, *RV*, *TB*, *AV*, *SB-M*, *SB-K*, *VS-M*, *VS-K*` whenever `N > 0` — and show a single `*CORPUS*-M` when `N == M` or for indeclinables, finite `तिङन्त` verbs, enclitics, and vocatives; **never** leave a `*CORPUS*` tag without `-M` or `-M/N` (`N >= 1`), and **never** emit bare `*-0` or `*-M/0`; dictionary tags `*MW*`, `*Macdonell*`, `*Lanman*` omit counts; **never** use `*TA*` (Taittirīya Āraṇyaka) or `*EK*` (Ekāgnikāṇḍa) as sources for `पद-पाठः (यान्त्रिकः)` since their traditional svara-s are dubious, whereas `*SB-M*` (Mādhyandina Śatapatha), `*SB-K*` (Kāṇva Śatapatha), `*VS-M*` (Mādhyandina Vājasaneya Saṁhitā), `*VS-K*` (Kāṇva Vājasaneya Saṁhitā), and legacy `*ŚB*`/`*VS*` are permitted; **never** rubber-stamp unattested words as `(मूल-पाठः (अनाम्नातम्))`, `(आरण्यक-पाठः (अनाम्नातम्))`, or bare `समासस्वरः` — always derive the accent by Pāṇinian vyākaraṇa (`पा॰`, `उणादि॰`, `फि॰`) + lexica/commentaries, correcting `मूलम्` via `OLD → **NEW**` whenever vyākaraṇa proves `मूलम्` wrong (especially in verses that already contain accent errors); **never** invent fake or oxymoronic sūtra names like `बहुव्रीहौ समासस्य` — verify every sūtra against Aṣṭādhyāyī; always write Pāṇinian sūtra references with `पा॰` `U+0970` Devanagari abbreviation sign, **never** `पा०` `U+0966` digit zero, e.g. `पा॰ x.y.z`, `भास्करः`, `सायणः`), and any doubts (preserve trailing `+++(...!!)+++` review comments at line end after `(...)`; bulk-backfill new corpus counts safely via `python -m doc_curation.sanskrit.accent.backfill --dir <dir> --corpora ...`). Title the block `<details><summary>पद-पाठः (यान्त्रिकः)</summary>` when `N == 0` (either de-novo or zero *vyatyasta* padas found); when auditing an already-accented source and correcting `N > 0` of `P` padas, title it `<details><summary>पद-पाठः (यान्त्रिकः - N/P व्यत्यस्त-स्वराः)</summary>` and write corrected padas as `- आङ्गीर᳓सः → **आङ्गीरसः᳓** (प्रातिपदिकम् आङ्गीरस᳓ (*MW*))` (unchanged padas omit any redundant prefix: `- आङ्गीरसः᳓ (प्रातिपदिकम् आङ्गीरस᳓ (*MW*))`).

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

##### 1. Read interleaved commentaries and parallels first

Check `भट्टभास्कर-टीका`, `सायण-टीका`, `रङ्ग-रामानुजः`, etc., and translations in the same mantra cluster **before** classifying any pada or assigning accents. Commentaries gloss each pada's exact sense, part of speech, gender/case/number, compound *vigraha*, finite verb root/person, and Vedic Pāṇinian rules (`परादिश्छन्दसि` पा॰ ६.२.१९९, `चवायोगे प्रथमा` पा॰ ८.१.५९, `उपाद् द्व्यजजिनमगौरादयः` पा॰ ६.२.१९४, `छान्दसं दीर्घत्वम्/ह्रस्वत्वम्`, `स्वरव्यत्ययः`):

###### Part-of-speech & underlying-form disambiguation

- **Subanta/kṛdanta vs tiṅanta vs āmantrita:** Never guess from surface endings (`प्रसूती` in `यतः प्रसूता जगतः प्रसूती` = nom. sg. fem. `प्र᳓-सूतिः` with *chāndasa* `-ई` per Bhāskara `"प्रसूती त्रिगुणात्मिका प्रकृतिः ... छान्दसं दीर्घत्वम्"` & Sāyaṇa `"प्रसूतिः सृष्टिः"`, never an unsplit or unaccented verb; `प्र-दुघे᳓` = fem. dual *kṛdanta* `"प्रकर्षेण दोग्ध्र्यौ"`, not a finite verb; `दिश` in `दि᳓शो दिश` = 2sg *loṭ* `"प्रयच्छ / देहि"`, not *āmreḍita* `दिशः`; `सुत` = 2pl *loṭ* `"अनुजानीत"`, not `सुतः`; `तरसे` in `सुत᳓रसि तरसे! न᳓मः` = non-initial vocative per Bhāskara).
- **Avoid false `पा॰ ८.१.२८` nominal/participle misclassifications:** Never misclassify `-तः` directional adverbs (`अन्ततः`, `उत्तरतः`, `दक्षिणतः`, `पुरतः`, `पृष्ठतः`, `उभयतः`, `अन्यतः`, `अग्रतः`, `मध्यतः`, `परतः`, `स्वतः`, `एकतः`) or non-finite `-ताम्`/`-तः`/`-ये` nominals (`व्यस्त᳓ये`, `लुट्`/participle homographs lacking explicit verb provenance; note periphrastic future `लुट्` itself is immune via `पा॰ ८.१.२९ न लुट्`) as `पा॰ ८.१.२८` finite verbs.
- **Distinguish homophonous suffixes:** Separate active *divādi* (`श्यन्` `पा॰ ३.१.६९`) participles (`दी᳓प्यमानः`, `पा॰ ६.१.१९७`) from homophonous passive `यक्` (`पा॰ ३.१.६७`), non-`नुम्` `शतृ` before `ङीप्`/vowel endings (`प्र-मृशतः᳓` via `पा॰ ६.१.१७३ शतुरनुमो नद्यजादी`), and `नित्` `कन्` (`म᳓न्थाककः` `पा॰ ५.३.७५` + `पा॰ ६.१.१९७` — never `कन् पा॰ ३.१.३`!) from plain `क` (`पा॰ ३.१.३`).
- **Underlying case/gender behind *parasavarṇa* & Vedic endings:** Check commentaries to undo `पा॰ ८.४.५८ अनुस्वारस्य ययि परसवर्णः` (`गन्धद्वारान् दुराधर्षान् नित्यपुष्टाम्` → fem. acc. sg. `गन्ध᳓-द्वाराम्`, `दुर्-आधर्षा᳓म्` modifying `श्रियम्`; `सहस्रशीर्षन् देवम्` → masc. acc. sg. `सह᳓स्र-शीर्षम्` modifying `देवम्`, never vocative `स᳓हस्र-शीर्षन्`; `यस्मान् न` → `य᳓स्मात्`; `सवितारन् नृचक्षसम्` → `सविता᳓रम्`) and Vedic neut. pl. `-आ` (`पा॰ ६.१.७०`: `दुः-इता᳓`, `जाता᳓` — never `-आः`).

###### Two-pada sandhi vs single compound

- **Separate sandhi-joined padas:** Use commentary glosses to identify *yaṇ*/vowel-joined separate padas (`अ-कार्य-कारी᳓` + `अव-कीर्णी᳓` in `अकार्यकार्य᳙वकीर्णी᳓` via `पा॰ ८.२.४`; `ब्र᳓ह्म` + `पूता᳓`; `विष्ण॑वे॒ ते` = non-initial vocative `विष्णो` `पा॰ ८.१.१९` + `एते᳓` per *RV* 7.99.3 & Bhāskara/Sāyaṇa `"हे विष्णो"`, never dative `वि᳓ष्णवे` + `ते᳓`).
- **Preserve commentary-attested compounds:** Keep genuine single compounds joined (`प्रज᳓या सम्-विदानः᳓` — never phantom `स᳓न्` + `विदानः᳓`; `घोर-घो᳓र-तरेभ्यः` per Bhāskara; `उच्चैर्-वादि᳓` per Haradatta `"उच्चैर्वादयतीति उच्चैर्वादि"` — never split a commentary-attested compound into `उच्चैः → **उच्चैः᳓**` + `वादि᳓`, which fabricates a *vyatyasta* and corrupts `विश्वास-प्रस्तुतिः`).

###### Commentator attributions & parallel padapāṭhas

- **Verify every commentator attribution locally:** Never append `— हरदत्तः`, `— भास्करः`, `— सायणः`, etc. unless that commentator's block exists in the same mantra cluster **and** actually discusses that pada's gloss, *vigraha*, or svara rule. Reserve trailing `— <commentator>` stamps for explicit grammatical/svara citations; when citing a commentator solely for a *vigraha* or gloss (not a svara rule), quote it inline (e.g. `'उच्चैर्वादयतीति उच्चैर्वादि' इति हरदत्तः`) and supply the Pāṇinian svara rule separately.
- **Follow attested corpus padapāṭhas:** Where a pāda or phrase has a parallel in `*TS*` or `*RV*`, follow its attested `<summary>पद-पाठः</summary>` / `rv-padapATha-dev` division.

##### 2. Split distinct sandhi-joined padas; never club non-compounds

###### External sandhi & pause-final boundaries

- **Undo external vowel, visarga, and consonant sandhi:** Split into normalized isolated padas (`देवीर्भुवनसूवरीः` → `देवीः᳓` + `भुवन-सू᳓वरीः`; `उत्तानस् त्वाङ्गीरसः` → `उत्तानः᳓`, `त्वा`, `आङ्गीरसः᳓`; `सह सञ्चस्करर्धिया` → `सह᳓`, `सञ्चस्कर`, `ऋ᳓द्धिया`; visarga-lopa `पार्थिवस्यैक इद्वशी` → `पा᳓र्थिवस्य`, `ए᳓कः`, `इ᳓त्`, `वशी᳓`, never `एकम्`; `लोपः शाकल्यस्य` `पा॰ ८.३.१९` prevocalic `वा᳓`/`वेह` → `वै᳓`, `-स्मा` → `-स्मै`; `-आँश्च`/`-ईँश्च`/`-ऊँश्च` via `पा॰ ८.३.७` → `-आन्`/`-ईन्`/`-ऊन्` + `च`; `भूर्भुवस्सुवः` → `भूः`, `भु᳓वः`, `स्वः᳙`; periphrastic perfects `मीमांसाम्` + `चक्रे`, `आम्` + `आस`).
- **Honor pause-final sandhi (`पा॰ ८.३.१५ खरवसानयोर्विसर्जनीयः`):** Visarga (`-ः`) never drops before `।` or `॥`. Never "restore" `-ः` onto a word ending in `-अ` at pause (`मे सुत ।`, `इतोहित ।`).

###### Non-compounds that must stay separate

- **Never club `न` + word as a compound:** `नञ्-तत्पुरुष` drops `न्` (`पा॰ ६.३.७३ नलोपो नञः` → `अ-`/`अन्-`), so `नान्यः`, `नान्यत्`, `नैनम्` (`न᳓` + `एनम्`), `नाणीयः` (`न᳓` + `अ᳓णीयः`), `नापरम्` (`न᳓` + `अ᳓परम्`) are always two separate padas, never `न-अन्यः` or `नैनम्`.
- **Never club pronouns, particles, enclitics, copulas, or inflected words:** Keep `मा`, standalone pronouns/indefinites (`यः`, `सः`, `तम्`, `अहम्`, `अस्य`, `एनम्`, `एतत्`, `इयम्`), particles/enclitics (`च`, `चन`, `चित्`, `वा`, `हि`, `उ`, `ह`, `एव`, `इति`, `मे`, `ते`, `त्वा`, `नः`, `वः`), copulas/verbs (`-असि`, `-अस्मि`, `-अस्ति`, `-एति`), and case-inflected `सुबन्त`s separate — even when sandhi/anunāsika binds them or when the source leaves a space (`सञ् च` → `स᳓म्` + `च`, never `स᳓ञ्च`; `महद्भिश्च` → `महद्भिः᳓` + `च`; `किञ्च` → `कि᳓म्` + `च`; `किञ्चन`/`कश्चन`/`किञ्चित्`/`कश्चित्` → `कि᳓म्`/`कः᳓` + `चन`/`चित्` per *TS*/*RV* padapāṭha `किम् । चन`, `कः । चन`, `कः । चित्`; `अहमस्मि` → `अह᳓म्` + `अस्मि`; `ब्रह्माहमस्मि` → `ब्र᳓ह्म` + `अह᳓म्` + `अस्मि`; `घर्मैतत्` → `घ᳓र्म` + `एत᳓त्`; `धारितेयम्` → `धारिता᳓` + `इय᳓म्`; `सामभिराक्तखन्त्वा` → `सा᳓मभिः` + `आ᳓क्त-खम्` + `त्वा`).
- **Permitted compound/iterative exceptions:** Keep genuine Vedic *aluk* (`पा॰ ६.३.१`, `६.३.२१`, etc.), *iva*-samāsa (`द्यौः᳓-इव`, *RV* `ऽइव`), *upapada* compounds (`तपसः-पते`, `वाचः-पतिः`, `आयुः-दाः`, `स्वयम्-भु`), and *vīpsā* iteratives (`पा॰ ८.१.४ नित्यवीप्सयोः`, e.g. `सप्त-सप्त`, `दमे-दमे`, `दिवे-दिवे`, `अहः-अहः`) hyphenated like *TS*/*RV* `ऽ`/`-`, whereas clausal *āmreḍita* repetitions (`पा॰ ८.१.३`) remain two separate bullets (`आ᳓पम्`, `आपाम्`).

##### 3. Keep samasta-padas together with `-` at compound joints

###### Hyphenation & suffix boundaries

- **Keep compound members on one bullet:** Never split a *samasta-pada* across multiple bullets. Keep it as one item with `-` between compound members (`वायु-अ᳓श्वाः`, `रश्मि-प᳓तयः`, `म᳓रीचि-आत्मानः`, `भुवन-सू᳓वरीः`), undoing internal sandhi cleanly at `-`.
- **Keep `गतिकृदन्त` compounds hyphenated:** Participles and verbal derivatives with `गति` (`नि-द᳓धत्`, `सं-भू᳓तः`, `वि-द᳓धत्`, `पा॰ ६.२.१३९ गतिकारकोपपदात्कृत्`) remain hyphenated compounds — never treat them as finite `तिङन्त` verbs (`पा॰ ८.१.२८` does not apply to participles).
- **Do not hyphenate before derivational suffixes:** Never place `-` before *kṛt* or *taddhita* suffixes (`पुत्रवत्त्वा᳓य`, `आङ्गीरसः᳓`).

##### 4. Separate or compound `upasarga` (`गति`) + finite verb (`तिङन्त`) by clause type

###### Main clause (unaccented verb, `पा॰ ८.१.२८ तिङ्ङतिङः`)

- **Split every main-clause `upasarga + तिङन्त`:** Separate them into distinct padas even when the finite verb already lost its accent cleanly without `→` (`सम॑वर्त॒ताधि॑` → `स᳓म्`, `अवर्तत`, `अ᳓धि`; `सञ्चस्कर` → `सम्`, `चस्कर`; `उपह्वये` → `उ᳓प`, `ह्वये`; `प्रसृपत` → `प्र᳓`, `सृपत`; `आ᳓वह` → `आ᳓`, `वह`), where the `गति` keeps its udātta and the finite verb is unaccented.
- **Chained `गति`s (`पा॰ ८.१.७० गतिर्गतौ`):** When consecutive `गति`s precede a main-clause verb, each preceding `गति` becomes **anudātta** before the following `गति`, so only the **final** `गति` in the chain retains its udātta (`अनु` + `आ᳓` + `वर्ते` → `अन्वा᳓वर्ते`; `अप` + `प्र᳓` + `सृपत`; `अभि` + `स᳓म्` + `बभूव`; `उत्` + `आ᳓` + `हरति` — never cite `गतिर्गतावत्`). Where an audited passage shows an initial `अभि᳓` accented before a compound verb (`अभि᳓ संबभूवुः᳓`), verify whether `अभि᳓` is a *karmapravacanīya* (`पा॰ १.४.९१ अभिरभागे`, not a `गति`); never cite `*TA*` or `*EK*` as a source.
- **Boundary `-आ᳓` + verb sandhi (`पा॰ ८.२.५`):** When `मूलम्` has `-आ᳓` + verb (`जैत्र्या॒यावि॑शताम्`, `मामा वि॑शतात्`, `ज्योति॒षागुः`, `इ॒हाग॑ताम्`), hypothesize `आ᳓` (`upasarga`, yielding `-आ᳓` by `पा॰ ८.२.५` with 0 vyatyasta: `जै᳓त्र्याय` + `आ᳓` + `विशताम्`, `ज्यो᳓तिषा` + `आ᳓` + `अगुः`, double avagraha `ऽऽ` in `विश्वास-प्रस्तुतिः`) rather than inventing a vyatyasta on the preceding word + an `अ-`verb (`अविशताम्`), and never emit double-canceling `आ → **आ᳓**` + `अ᳓गात् → **अगात्**` arrows when `आ᳓ + अगात् = आ᳓गात्` already matches `मूलम्`.
- **Do not over-split:** Never split simplex roots or `अ-`/`आ-` augments that merely resemble prefixes (`आस्ते`, `आहुः`, `आशत`, `अवतु`, `विद्यते`, `विवेश`, `अपश्यत्`, `अवसन्`, `अतिरम्`), nor noun/kṛt compounds (`सु-कृ᳓ताम्`, `प्रति-ष्ठा᳓म्`).

###### `पादादि`, `तिङः परं तिङ्`, & vocative exemptions (`पा॰ ८.१.१८`, `८.१.२८`, `८.१.७२–७३`)

- **Clause scope (`एकतिङ् वाक्यम्` / `समानवाक्ये`):** *Svaranighāta* (`पा॰ ८.१.२८ तिङ्ङतिङः`) operates within a single finite-verb clause (`समानवाक्ये`) and **only** on *non-pāda-initial* finite verbs immediately following an *atiṅ* (`अ᳓दर्शम् ज्योतिः, अ᳓विदाम देवान्`).
- **Finite verb after finite verb (`तिङः परं तिङ्`):** A finite verb immediately after another `तिङन्त` is **not** de-accented (`वान्ति पत᳓यन्ति`, `आ᳓ वह माद᳓यस्व`, `जिहते पि᳓न्वते`, `आ᳓ववर्तिन्न् अ᳓भूद्`).
- **Vocative visibility (`पा॰ ८.१.७२–७३`):**
  - By `पा॰ ८.१.७२ आमन्त्रितं पूर्वमविद्यमानवत्`, a pāda-initial vocative is treated as non-existent for the following word's nighāta, so a finite verb right after it stands at *pādādi* and retains its udātta (`मृ᳓त्तिके ह᳓न`, `मृ᳓त्तिके दे᳓हि`), whereas if another non-vocative word precedes (`वित᳓स्तया ऽऽर्जीकीये श्रुणुहि`), `श्रुणुहि` still becomes anudātta.
  - By `पा॰ ८.१.७३ नामन्त्रिते समानाधिकरणे सामान्यवचनम्`, a pāda-initial generic qualifier vocative (`सामान्यवचन`) followed by a co-referential vocative (`अ᳓ग्ने गृहपते`) is **not** *avidyamānavat*, so the following vocative/verb still undergoes *nighāta*.
- **Metrical *pādādi* verbs:** A finite verb standing at the start of **any** metrical *pāda* or sentence (after `।`, `॥`, or at an unmarked 8/11/12-syllable *pāda* boundary — e.g. `आ᳓पम्` in `आ᳓पम् आपाम्`, `ल᳓म्बति`, `वोचे᳓म`, `ज᳓हाति`, `जी᳓वामि`, `पुन᳓न्तु`, `विधे᳓म`) retains its udātta; never flag it with `पा॰ ८.१.२८` or strip its accent in `विश्वास-प्रस्तुतिः`. When `गति + तिङन्त` opens a main-clause pāda (`उ᳓द् दीप्यस्व`, `प्र᳓ त्नोषि`, `स᳓म् तापयति`), the `गति` occupies *pādādi* and keeps its udātta while the following `तिङन्त` follows an *atiṅ* (`गति`) and becomes anudātta (`पा॰ ८.१.२८`). Distinguish participles, gerundives, and nominal forms (`प्र-दुघे᳓`, `उच्च᳓रत्`, `रेज᳓ती`, `निधा᳓य्यः`, `सम्-दृ᳓शे`) from finite verbs.

###### Subordinate & nighāta-blocked clauses (accented verb, `पा॰ ८.१.२९–६८`, `८.१.७१`)

- **Primary Vedic & syntactic blockers:** Check the *same* clause for:
  - `यद्`-वृत्त words (`यः`, `यम्`, `यत्`, `येन`, `यस्य`, `यत्र`, `यदा`, `यथा`, `यदि` — `पा॰ ८.१.६६ यद्वृत्तान्नित्यम्`, e.g. `यो᳓ ... प᳓श्यत`, `य᳓च् च ... श्रूय᳓ते`, `य᳓थै᳓क ऋ᳓षिर् वि-जा᳓नते`);
  - `हि` (`पा॰ ८.१.३४ हि च`, including linked verbs in Chandas via `पा॰ ८.१.३५ छन्दस्यनेकमपि साकाङ्क्षम्`);
  - `यदि`/`हन्त`/`कुवित्`/`नेत्`/`चेत्`/`चण्`/`कच्चित्`/`यत्र` (`पा॰ ८.१.३० निपातैर्यद्यदिहन्तकुविन्नेच्चेच्चण्कच्चिद्यत्रयुक्तम्`);
  - `यावत्`/`यथा` (`पा॰ ८.१.३६ यावद्यथाभ्याम्`, constrained by `पा॰ ८.१.३७–३८ पूजायां नानन्तरम्` / `उपसर्गव्यपेतं च`);
  - `किम्`-वृत्त + `चित्` (`पा॰ ८.१.४८ किम्वृत्तं च चिदुत्तरम्`, e.g. `क᳓श्चिद् भुङ्क्ते᳓`, `के᳓नचित् करो᳓ति`);
  - `च`/`वा` verb coordination (`पा॰ ८.१.५९ चवायोगे प्रथमा`: `स्वां᳓ चाग्ने तनु᳓वं पिप्र᳓यस्वास्म᳓भ्यं च ... आ᳓ यजस्व`) and ellipsis (`पा॰ ८.१.६३ चादिलोपे विभाषा`: `सं᳓ बाहु᳓भ्यान् न᳓मति सं᳓ प᳓तत्रैः`);
  - `वै`/`वाव` (`पा॰ ८.१.६४ वैवावेति च च्छन्दसि` optional *nighāta* block in Vedic, e.g. `न᳓ वै᳓ ... जघा᳓न`);
  - following particles in Chandas (`पा॰ ८.१.५६ यद्धितुपरं छन्दसि`: verb immediately followed by `यत्`/`हि`/`तु` retains accent, e.g. `उद᳓सृजो य᳓द् अङ्गिरः`, `उश᳓न्ति हि᳓`);
  - post-verb `चन`/`चित्`/`इव`/etc. without `गति` (`पा॰ ८.१.५७ चनचिदिवगोत्रादितद्धिताम्रेडितेष्वगतेः`, e.g. `प᳓चति चित्`, `प᳓चतीव`) and post-verb `चादि` (`पा॰ ८.१.५८ चादिषु च`);
  - periphrastic future `लुट्` (`पा॰ ८.१.२९ न लुट्`: `कर्ता᳓`, `कर्ता᳓रौ`, `कर्ता᳓रः` never lose their accent).
- **Additional particle & mood exemptions (`पा॰ ८.१.३१–५५, ६०–६८`):** `नह` (`८.१.३१`), `सत्यम्` (`८.१.३२`), `अङ्ग` (`८.१.३३`), praise `तु`/`पश्य`/`पश्यत`/`अह`/`अहो` (`८.१.३९–४१`), `पुरा` (`८.१.४२`), `ननु` (`८.१.४३`), `किम्`-question & elision (`८.१.४४–४५`), `एहिमन्ये लृट्` (`८.१.४६`), `जातु` (`८.१.४७`), `आहो`/`उताहो` (`८.१.४९–५०`), `गत्यर्थ-लोट्` + `लृङ्`/`लोट्`/`हन्त` (`८.१.५१–५४`), `आम्` (`८.१.५५`), `ह`/`अह` (`८.१.६०–६२`), and Vedic `एक`/`अन्य` (`८.१.६५`) — **except** `पा॰ ८.१.६७–६८ पूजनात् पूजितमनुदात्तं काष्ठादिभ्यः / सगतिरपि तिङ्` where `काष्ठादि` praise restores *nighāta* even with `यद्`/`गति`.
- **Strict scoping to finite `तिङन्त`s in the same clause:** Never cite `पा॰ ८.१.२८–६८` or `पा॰ ८.१.७१` on non-`तिङन्त` pronouns, particles, upasargas, *kṛdantas*/`क्त`-participles, or nominals (e.g. `प्रसूता` after `यतः` is a `क्त`-participle *subanta* governed by `पा॰ ६.२.४९ गतिरनन्तरः → प्र᳓-सूता`, not a finite verb under `पा॰ ८.१.६६`/`८.१.७१`; likewise never on `अस्य`, `मम`, `वाम्`, `अहम्`, `ते`, `उत्`, `परि`). Never bleed `हि च` or `यद्वृत्तान्नित्यम्` into preceding main clauses (`उदीर्ष्वातः पतिवती ह्येषा`, `अग्निः प्राश्नातु प्रथमः स हि वेद`), following `मा`/`नो`/`उ`/`तत्`/`सः`/`तस्मै`/`एवम्` main clauses (`मा रिषामा वयं तव`), correlative `तद्`-clauses (`य᳓द् ... त᳓द् अ᳓प गच्छतात्`), or main clauses following verbless relative pādas (`यो᳓ऽस्य ... वशी᳓ । यमं ... गाय`). Prohibitive `मा` (`माङ्`) with injunctives or *s*-aorists (`मा ... हिंसीः`, `मा ... वोचः`, `मा ... उद्वधीत्` — note `हिंसीः`/`हिंसीत्`/`लेखीः` are finite *s*-aorists) obeys `पा॰ ८.१.२८` *anudātta*, never `*SB-M*-15`/`*SB-K*-32`, `पा॰ ८.१.६६`, or isolated subordinate `*RV*` hits.
- **`गति` treatment under `पा॰ ८.१.७१ तिङि चोदात्तवति`:** When the `तिङन्त` retains its accent, an immediately adjacent preceding `गति` becomes anudātta (`पा॰ ८.१.७१`) and compounds as a single bullet with the `तिङ्` (`उदाजहा᳓र`, `प्रचोद᳓यात्`, `अभि-ऐ᳓रयन्त`, `वि-भ्रा᳓जते`, `अव-म᳓र्शतु` — except in ŚB where `forbid_compound_upasarga_tinanta` keeps the `पा॰ ८.१.७१` anudātta `गति` on its own bullet). Whenever a particle or other word **intervenes** (*tmesis* / व्यवधान, e.g. `च`, `उ`, `अपि`, `बाहु᳓भ्याम्`), `पा॰ ८.१.७१` and `गति + तिङ्` compounding do **not** cross it: split each `गति`, intervening word, and accented verb as its own bullet preserving original udāttas (`- स᳓म्`, `- च`, `- वि᳓`, `- च`, `- ए᳓ति`).

##### 5. Verify the forward-sandhi round-trip invariant

###### Programmatic reconstruction & hiatus rules

- **Verify round-trip reconstruction:** Joining the proposed `पद-पाठः` sequence with Pāṇinian and Vedic sandhi rules must reconstruct `मूलम्` via `doc_curation.sanskrit.accent.sandhi_check.verify_mantra_sandhi` (modulo recensional allographs such as `ळ/ड`, `व्ँ/ं`, and gemination after `र्`).
- **Handle line wraps without daṇḍa:** Without an intervening `।`/`॥`, samhitā sandhi still applies across *viṣama-pāda* line wraps (`\n`): e.g. `भव्य॑म् आ \nइ॒दन्` is *visarga-lopa* (`आः + इदम् → आ इदम्`, verified in commentaries as `आसीत्`), never `आ + इदम्`.
- **Treat mismatches as split/inflection bugs:** Any discrepancy (`एकम् + इत् → एकमित् ≠ एक इत्` [`एकः + इत्`], `आ + इदम् → एदम् ≠ आ इदम्` [`आः + इदम्`], `सुप्रयतौ + इह → सुप्रयताविह ≠ सुप्रयतेह` [`सु-प्रयते + ह`], or `हिंसीः + जातवेदः → हिंसीर्जातवेदो ≠ हिंसीज्जातवेदो` [`हिंसीत्`]) proves a wrong inflection or split and must be repaired before checking accents.
- **Constrain `V + V` hiatus:** Never allow unconstrained hiatus in forward-sandhi checks; accept hiatus only across `।`/`॥` pauses, grammatically licensed splits (*pragṛhya* `-ई`/`-ऊ`/`-ए` duals & `-ओ` nipātas, `लोपः शाकल्यस्य` `-ए`/`-ऐ`/`-ओ`, `-आः`/`-अः` visarga-lopa), or documented metrical hiatuses.

##### 6. Project sandhi accents from `मूलम्` and evaluate `वाक्य-स्वरः`

###### Mūla projection, `॑`-after-udātta ambiguity, & no fake sandhi arrows (`पा॰ ८.२.४–६`, `६.१.१६१`)

- **Project strictly from `मूलम्`:** Derive `पद-पाठः` accents from `मूलम्` (`accent.to_US_accents(text, pauses=r"[।॥,;]+")` when line breaks lack `।`/`॥` so `\n` is not treated as a pause), never from `विश्वास-प्रस्तुतिः` (which is checked separately for `[[OLD|NEW]]` suggestions), and never mistake classical dependent svarita `॑` (one syllable *after* the udātta, e.g. `य॒मो ह॑वे॒ह` = `यमो᳓ ह वेह᳓`, where `ह` is unaccented) for an udātta on the marked syllable.
- **Respect `॑`-immediately-after-udātta ambiguity:** When `मूलम्` places `॑` immediately after an udātta syllable without intervening `॒` (`पर॒मे व्यो॑मन्न्`, matching *TS* `प॒र॒मे । व्यो॑म॒न्`), classical notation leaves dependent svarita and independent `᳙` indistinguishable so `to_US_accents` omits `᳙` on `व्यो`. Do **not** flag such a pada as a `vyatyasta-svara` (`व्योमन्न् → **व्यो᳙मन्न्**`) — record `- व्यो᳙मन्न् (*TS*-12/13)` directly and omit it from `N/P`, while still checking whether US-accented `विश्वास-प्रस्तुतिः` dropped `᳙` (`[[व्योमन्|व्यो᳙मन्]]`).
- **Attribute merged boundary udāttas & block fake sandhi arrows:** Attribute a merged boundary udātta (`-त + अ᳓- → -ता᳓-` in `अवर्तता᳓धि`, `-अ + ऋ᳓- → -अर्᳓-` in `सञ्चस्कर᳓र्धिया`) using each pada's syntactic role and attested accent (`अवर्तत` unaccented + `अ᳓धि`; `सञ्चस्कर` unaccented + `ऋ᳓द्धिया`). **Never emit a fake `ar → **ref**` correction when `ref` under external or compound-internal sandhi (`पा॰ ६.१.७७/८७/८८/१०१/१०९` + `पा॰ ८.२.४–६`) already yields `मूलम्`'s exact saṁhitā svara** — e.g. *yaṇ* udātta + udātta (`पोषयित्नु᳓` + `आ᳓` → `पोषयि॒त्न्वा`, `वाचि᳓` + `अ᳓पि` → `वा॒च्यपि॑`, where `पा॰ ८.२.४` produces svarita **only** before an *anudātta* vowel!), *ekādeśa* (`वित᳓स्तया` + `आ᳓र्जीकीये` → `वि॒तस्त॒या ऽऽर्जी॑कीये`, `हि᳓` + `ए᳓कः` → `ह्येको॑`, `शत᳓-अङ्कुरा` → `श॒ताङ्कु॑रा`, `चन᳓` + `आममत्` → `च॒नाम॑मत्`), or *kṣaipra*/*abhinihita* svarita (`वि᳓` + `अस्तभ्नात्` → `व्य॑ष्टभ्नात्`, `अजः᳓` + `असि` → `अ॒जो॑ऽसि`) — nor when `ar` and `ref` differ only by hyphenation (`वि᳓धृते → **वि᳓-धृते**`); `validator.find_fake_sandhi_svara_arrows` flags all such fake arrows.
- **Map independent svarita `᳙` accurately:** Sandhi-induced independent svarita `᳙` (*kṣaipra* `व्य᳙शेम`, *abhinihita* `यो᳙ऽपा᳓म्`) corresponds to padapāṭha udātta `᳓` (`वि᳓`, `यः᳓`); keep `᳙` in padapāṭha only on lexical svaritas (`स्वः᳙`, `क्व᳙`, `वीर्य᳙म्`), never misread an independent svarita `᳙` in `मूलम्` as udātta `᳓`, and whenever citing `पा॰ ८.२.४` (*yaṇ*-svarita), verify that `᳙` lands on the syllable carrying the `यण्` (`य्`/`व्`/`र्`/`ल्`).
- **Udātta deletion before anudātta (`पा॰ ६.१.१६१ अनुदात्तस्य च यत्रोदात्तलोपः`):** When an udātta vowel drops before an anudātta suffix or vowel (`भस्य टेर्लोपः` `पा॰ ७.१.८८` or `ई` deletion), the following anudātta becomes udātta (`कुमार᳓` + `ई` → `कुमारी᳓`, `पथि᳓न्` + `ए` → `पथे᳓`, `कुमुद᳓` + `मतुप्` → `कुमुद्वा᳓न्`).

###### Āmreḍita (`पा॰ ८.१.३–४`, `८.१.१०`)

- **De-accent repeated word only:** The repeated second word (`आ᳓पम् आपाम्`, `अस्मा᳓त् अस्मात्`) must be unaccented (`पा॰ ८.१.३ अनुदात्तं च`).
- **Do not over-apply `पा॰ ८.१.३`:** Apply it only to genuine single-word *dvivacana* (`पा॰ ८.१.४`), **never** across separate clauses or *pādādi* (`श्वेता᳓य वैदर्वा᳓य न᳓मो । न᳓मः श्वेता᳓य वैदर्वा᳓य`, `अपादादौ पा॰ ८.१.१८`), homophonous enclitics (`ते᳓ ते`, `मा᳓ मा` 'do not ... me' under `पा॰ ८.१.१८` / `८.१.१०`), or `<vocative> + <nominative>` across sandhi (`अहिँस-अतिबलः᳓` → `अ᳓-हिँस` voc. `पा॰ ६.१.१९८` + `अति-बलः᳓`).

###### Vocatives (`आमन्त्रित`: `पा॰ ६.१.१९८`, `८.१.१९`, `८.१.७२–७३`)

- **Position determines svara:** Clause/pāda-initial vocatives are *ādyudātta* (`पा॰ ६.१.१९८`); non-initial vocatives are unaccented (`पा॰ ८.१.१९`), except when preceded by a distinct non-co-referential vocative (`पा॰ ८.१.७२`, vs co-referential generic qualifier vocatives `पा॰ ८.१.७३`: `अ᳓ग्ने गृहपते`).
- **Verify boundary & commentary before restoring:** Always verify actual metrical pāda/clause start before citing `पा॰ ६.१.१९८`, and check local commentary (`"हे ..."`, `"सम्बुद्धौ"`, e.g. `सी᳓रा` per Haradatta `"सम्बुद्धौ चाकारः"`) and `विश्वास-प्रस्तुतिः` (`"!"`) before "restoring" an accent onto a 0-accent pada that may actually be a non-initial vocative (`विष्णो`, `देवि`, `शर्व`, `वृषभ`).

###### Enclitics, *anvādeśa* pronouns, & homophones (`पा॰ ८.१.१८–२३`, `२.४.३२–३४`)

- **Always-unaccented enclitics:** `मे`, `ते`, `त्वा`, `मा`, `नः`, `वः`, `वाम्`, `नौ` (`पा॰ ८.१.२०–२३`, contrasting accented `म᳓म`, `त᳓व`, `तु᳓भ्यम्`, `म᳓ह्यम्`) and `च`, `वा`, `उ`, `ह`, `स्वित्`, `स्म` (`पा॰ ८.१.१८ अनुदात्तं सर्वमपादादौ`) never stand at clause/pāda start — never override enclitic `स्वित्` with rare `*RV*` `स्वि᳓त्`/`स्वि᳙त्` hits. Note also that `वाव` is an attested dual-accent particle (`वा᳓व᳓`, exempted in `validator.find_multi_udatta_padas`).
- ***Anvādeśa* pronouns:** Unemphatic anaphoric `इदम्`/`एतद्` forms lose their accent via `पा॰ २.४.३२ इदमोऽन्वादेशेऽशनुदात्तस्तृतीयादौ` (oblique `अस्य`, `अस्मै`, `अस्मात्`, `अस्मिन्`, `आभ्याम्`, `एभिः`), `पा॰ २.४.३३ एतदस्त्रतसोस्त्रतसौ चानुदात्तौ` (`एतस्मिन्`, `एतस्मात्`, `अत्र`, `अतः`), and `पा॰ २.४.३४ द्वितीयाटौस्स्वेनः` (+ *vārttika*: `एनम्`, `एनेन`, `एनयोः`, `एनत्`).
- **Disambiguate accented homophones:** Never misclassify prohibitive `मा᳓` (`माङ्`, always udātta at clause start or before injunctives / `मे` / `नः` / `मम` / `मा`) vs enclitic `मा` ("me"); demonstrative nom. pl. `ते᳓` (`तद्`) vs enclitic `ते`; or particle `वै᳓` (prevocalic `वा᳓`, `ह वै᳓` — ignore saṁhitā `'वा᳓'` attestations in TB/TK/AV when resolving enclitic `वा`) vs enclitic `वा` ("or").

##### 7. Derive & verify pada-level svara (`प्रत्यय-धातु-सुबन्त-समास-स्वरः`)

###### Suffix, root, particle, & augment accents (`प्रत्यय-धात्वागम-स्वरः`)

- **General defaults (`पा॰ ३.१.१–४`, `६.१.१६२`, `फि॰ १.१`, `४.१२–१७`):** Suffixes default to initial udātta (`पा॰ ३.१.३ आद्युदात्तश्च`), except `सुप्` and `पित्` which are anudātta (`पा॰ ३.१.४ अनुदात्तौ सुप्पितौ`), throwing accent onto the root-final vowel (`पा॰ ६.१.१६२ धातोः`: `प᳓चति`, `प᳓ठति`, `ऊर्णो᳓ति`, `गोपाय᳓ति`, `या᳓ति`). Underived *prātipadikas* default to *antodātta* (`फि॰ १.१ फिषोऽन्त उदात्तः`); *nipātas* default to *ādyudātta* (`फि॰ ४.१२`), *upasargas* likewise *ādyudātta* except `अभि᳓` (`फि॰ ४.१३ उपसर्गाश्चाभिवर्जम्`: `प्र᳓`, `उ᳓प`, `अ᳓प`, `प᳓रि`), `एवादीनाम्` *antodātta* (`फि॰ ४.१४`), `चादि`s *anudātta* (`फि॰ ४.१६`), `यथा` *antodātta* at pāda end (`फि॰ ४.१७`), and time `-दा` (`पा॰ ५.३.१५` + `३.१.३`: `सर्वदा᳓`, `एकदा᳓`, `यदा᳓`).
- **It-letter rules (`चित्`/`कितः`/`तित्`/`लित्`/`ञित्`/`नित्`/`रित्`):**
  - `चित्` (`पा॰ ६.१.१६३ चितः`, `६.१.१६४ तद्धितस्य`): *antodātta* (`घुरच्` `भङ्गुर᳓म्`, `डतमच्` `पा॰ ५.३.९३` `कतमः᳓`, `षच्` `हिरण्य-अक्षः᳓`).
  - `कितः` (`पा॰ ६.१.१६५ कितः`): *taddhita* *antodātta* (`फक्` `नाडायनः᳓`).
  - `तित्` (`पा॰ ६.१.१८५ तित्स्वरितम्`): suffix-initial *svarita* (`ण्यत्` `कार्य᳙म्`, `चिकीर्ष्य᳙म्`), overridden by `पा॰ ६.१.२१३ यतोऽनावः` (disyllabic `यत्` other than `नाव्य᳙म्` → *ādyudātta*: `चे᳓यम्`, `जे᳓यम्`, `तु᳓ल्य-`) and `पा॰ ६.१.२१४ ईडवन्दवृशंसदुहां ण्यतः` (`ई᳓ड्यम्`, `व᳓न्द्यम्`, `वा᳓र्यम्`, `श᳓स्यम्`, `दो᳓ह्या`).
  - `लित्` (`पा॰ ६.१.१९३ लिति`): syllable immediately preceding the suffix (`ल्युट्` `द᳓र्शनम्`, `निर्व᳓चनम्`; `ण्वुल्` `चिकी᳓र्षकः`, `आ-ख्या᳓यिकाः`; `तसिल्` `विश्व᳓तः`; `त्रल्` `अ᳓त्र`, `य᳓त्र`; `तल्` `अर्वाचीन᳓ता`).
  - `ञित्`/`नित्` (`पा॰ ६.१.१९७ ञ्नित्यादिर्नित्यम्`): stem-initial *ādyudātta* (`तुमुन्` `क᳓र्तुम्`, `क्तिन्` `स्मृ᳓तिः`, `ष्ट्रन्` `सू᳓त्रम्`, `तृन्` `दा᳓ता`, `यञ्` `गा᳓र्ग्यः`, `ईयसुन्` `श्रे᳓यान्`, `श्यन्` `दी᳓प्यमानः`, `संज्ञायां कन्` `म᳓न्थाककः`, `घञ्` `दो᳓षः`), overridden by `पा॰ ६.१.१५९ कर्षात्वतो घञोऽन्त उदात्तः` (`कर्षः᳓` of *bhvādi* `कृष्`, `पाकः᳓`, `त्यागः᳓`, `रागः᳓`, `दायः᳓`, `धायः᳓`, vs `रा᳓मः`).
  - `रित्` (`पा॰ ६.१.२१७ उपोत्तमं रिति`): penultimate syllable of the word (`अनीयर्` `करणी᳓यम्`, `हरणी᳓यम्`).
- **Unprefixed `निष्ठा` (`क्त`) exceptions:** `पा॰ ६.१.२०५ निष्ठा च द्व्यजनात्` (disyllabic non-`आ`-initial *saṃjñā*: `द᳓त्तः`, `गु᳓प्तः`, `बु᳓द्धः`), `पा॰ ६.१.२०६ शुष्कधृष्टौ` (`शु᳓ष्कः`, `धृ᳓ष्टः`), `पा॰ ६.१.२०७ आशितः कर्ता`, `पा॰ ६.१.२०८ रिक्ते विभाषा`, and `पा॰ ६.१.२०९ जुष्टार्पिते च छन्दसि` (`जु᳓ष्टः`/`जुष्टः᳓`, `अ᳓र्पितः`/`अर्पितः᳓`).
- **`ल-सार्वधातुक` (`तिङ्`, `शतृ`, `शानच्`), `विकरण`, & `अदुपदेश` (`पा॰ ६.१.१८६`):** After `तासि`, `अनुदात्तेत्` roots (`आ᳓स्ते`, `व᳓स्ते`), `ङित्` roots (`सू᳓ते`, `शे᳓ते` — except `ह्नुङ्`/`इङ्`, e.g. `अधीते᳓`), and `अदुपदेश` (`अकारान्तोपदेश`: `शप्`, `यक्`, `श्यन्`, `शः`), `ल-सार्वधातुक` endings/`शतृ`/`शानच्` are anudātta (`प᳓चति`, `भ᳓वामः`, `नि-षी᳓दत्`, `रक्ष्य᳓माणम्`, `दी᳓प्यमानः`, `तुद᳓तः`). Athematic non-`अदुपदेश` classes (`अदादि` `शब्लुक्`, `जुहोत्यादि` `श्लु`, `स्वादि` `श्नु`, `रुधादि` `श्नम्`, `तनादि` `उ`, `क्र्यादि` `श्ना`) keep `पा॰ ३.१.३` on non-`पित्` vikaraṇas/endings (`जुहुमः᳓`, `विधूनुते᳓`, `विद्महे᳓`; `पा॰ ६.१.१८९ अभ्यस्तानामादिः` before vowel-initial non-`इट्` endings `द᳓दति`, `द᳓धति`).
- **Augments & optative `यासुट्`:** Augments are anudātta except `पा॰ ६.४.७१–७२ लुङ्लङ्लृङ्क्ष्वडुदात्तः / आडजादीनाम्` (`अट्`/`आट्` in `लुङ्`/`लङ्`/`लृङ्`: `अ᳓दर्शम्`, `अ᳓विदाम`, `ऐ᳓रयन्त`) and `पा॰ ३.४.१०३ यासुट् परस्मैपदेषूदात्तो ङिच्च` (`कुर्युः᳓`).
- **`मतुप्` & feminine `-ई`:** `पा॰ ६.१.१७६ ह्रस्वनुड्भ्यां मतुप्` (*antodātta* stem ending in short vowel or `नुट्` shifts udātta onto `मतुप्`: `अग्निमा᳓न्`, `वायुमा᳓न्`, `पशुमा᳓न्`, `अक्षण्वता᳓` — not *ādyudātta* `व᳓सुमान्`, `पु᳓ष्पवान्`); `पा॰ ६.१.२१९–२२१` (`उदुम्बरा᳓वती`, `अजिरवती᳓`, `अहीवती᳓`); feminine `ङीप्` (`३.१.४` anudātta) vs `ङीष्` (`३.१.३` udātta).

###### Case-ending shift in subantas (`विभक्ति-स्वरः`, `पा॰ ६.१.१६८–१८२`)

- **Monosyllabic *antodātta* stems (`पा॰ ६.१.१६८–१६९`):** By `पा॰ ६.१.१६८ सावेकाचस्तृतीयादिर्विभक्तिः`, stems monosyllabic in nom. sg. (`सु`) shift udātta to 3rd–7th case endings (`वाचा᳓`, `वाग्भ्या᳓म्`, `अप्सु᳓`; `वाचः᳓`/`महः᳓` abl./gen. sg. vs `वा᳓चः`/`म᳓हः` nom./acc. pl.); by `पा॰ ६.१.१६९ अन्तोदात्तादुत्तरपदादन्यतरस्यामनित्यसमासे`, non-*nitya* compounds with a monosyllabic *antodātta* final shift optionally (`परम-वा᳓चा` or `परम-वाचा᳓`).
- **Special stems (`पा॰ ६.१.१७०–१७१`):** Vedic `-अञ्च्` stems (`पा॰ ६.१.१७० अञ्चेश्छन्दस्यसर्वनामस्थानम्`: `प्रतीचः᳓`, `दधीचः᳓`) and *antodātta* `ऊठ्`, deictic `इदम्` (`आभ्या᳓म्`, `एभिः᳓`, overcoming `२.४.३२`), `पदादि`, `अप्`, `पुंस्` (`पुंसा᳓`), `रै`, `दिव्` (`पा॰ ६.१.१७१ ऊडिदम्पदाद्यप्पुम्रैद्युभ्यः`) take udātta on all non-*sarvanāmasthāna* endings.
- **Participles & post-consonantal `यण्`/`न्` (`पा॰ ६.१.१७३–१७५`, `१७७`):** Non-`नुम्` `शतृ` (`पा॰ ६.१.१७३ शतुरनुमो नद्यजादी` + `वा॰ बृहन्महतोरुपसंख्यानम्`: `तुदती᳓`, `तुदता᳓`, `प्र-मृशतः᳓`, `बृहते᳓`, `महते᳓`, vs `नुम्` `तुद᳓न्ती` via `८.२.५`); post-consonantal udātta `यण्`/`न्` (`पा॰ ६.१.१७४ उदात्तयणो हल्पूर्वात्` + `वा॰ नकारग्रहणम्`: `कर्त्री᳓`, `कर्त्रा᳓`, `प्रसवित्रा᳓`, blocked for `ऊङ्`/root-`उ`/`इ` by `पा॰ ६.१.१७५ नोङ्धात्वोः` → `ब्रह्मबन्ध्वा᳙` via `८.२.४`); and optional gen. pl. `-नाम्` (`पा॰ ६.१.१७७ नामन्यतरस्याम्`: `अग्नीना᳓म्`/`अग्नी᳓नाम्`, `बहूना᳓म्`/`बहू᳓नाम्`).
- **Blocking exceptions (`पा॰ ६.१.१८२ न गोश्वन्त्साववर्णराडङ्क्रुङ्कृद्भ्यः`):** Blocks `६.१.१६८`/`१७१` for `गो` (`ग᳓वा`, `सु-ग᳓वे`), `श्वन्` (`शु᳓ना`), `अवर्णान्त` pronouns (`ये᳓भ्यः`, `ते᳓भ्यः`, `के᳓भ्यः`), `राज्`, non-Chandas `-अञ्च्`, `क्रुञ्च्`, and monosyllabic `कृत्` nouns (`कृ᳓ता`, `कृ᳓ते`).

###### Compound accents (`समास-स्वरः`): Bahuvrīhi & Dvandva

Never apply mechanical `पा॰ ६.१.२२३` *antodātta* or single-member `*MW*` extrapolation blindly:

- **Default *bahuvrīhi* (`पा॰ ६.२.१ बहुव्रीहौ प्रकृत्या पूर्वपदम्`):** Keeps the *pūrvapada*'s *prakṛtisvara* (`हि᳓रण्य-कक्ष्यान्`, `अ᳓यस्-शफान्`, `गन्ध᳓-द्वारान्`, `ए᳓क-नीळम्`, `स᳓र्व-रूपाः`, `अग्नि᳓-वर्णाम्`, `वि᳓ष्णु-क्रान्ते`, `ऊर्ध्व᳓-रेतम्`, `नारायण᳓-परम्`, `शत᳓-बाहुना`, `त्रि᳓-सुपर्णम्`, `पु᳓ष्कर-स्रजा`, `आदित्य᳓-वर्णम्`), including `स-` (`सहस्य सः` `पा॰ ६.३.८२`, retaining `स᳓-` initial udātta via `पा॰ ६.२.१` — do **not** split non-`सह` *taddhita* stems such as `सरस्यकाः᳓` `पा॰ ३.१.३` into `स-रस्यकाः`!).
- ***Bahuvrīhi* *apavāda*s:**
  - `विश्व` epithets (`पा॰ ६.२.१०६ बहुव्रीहौ विश्वं संज्ञायाम्` *pūrvapada-antodātta*: `विश्व᳓-कर्मणः`, `विश्व᳓-शं-भुवम्`, `विश्व᳓-रूपाय`, `विश्व᳓-आत्मानम्`).
  - `नञ्` + `जर`/`मर`/`मित्र`/`मृत` (`पा॰ ६.२.११६ नञो जरमरमित्रमृताः` *uttarapada-ādyudātta*: `अ-ज᳓रः`, `अ-म᳓रः`, `अ-मि᳓त्रः`, `अ-मृ᳓तः`).
  - `सु` + `-मन्`/`-अस्` (`पा॰ ६.२.११७ सोर्मनसी अलोमोषसी`: `सु-क᳓र्मा`, `सु-म᳓नाभिः`), `सु` + `क्रत्वादि` (`पा॰ ६.२.११८`: `सु-क्र᳓तुः`, `सु-दृ᳓शीकः`, `सु-प्र᳓तीकः`, `सु-ह᳓व्यः`, `सु-भ᳓गः`), `सु` + disyllabic `आद्युदात्त` in Chandas (`पा॰ ६.२.११९ आद्युदात्तं द्व्यच् छन्दसि`: `सु-धु᳓रान्`, `सु-सो᳓मया`, `स्व᳓श्वः`, `सु-र᳓थः`), and `सु` + `वीर`/`वीर्य` (`पा॰ ६.२.१२० वीरवीर्यौ च`: `सु-वी᳓रः`, `सु-वी᳓र्यस्य`).
  - Remaining `नञ्`/`सु`/`बहु` *bahuvrīhi*s (`पा॰ ६.२.१७२ नञ्सुभ्याम्` *antodātta*: `अक्रतु᳓म्`, `अनन्त᳓म्`), with `-कप्` (`पा॰ ६.२.१७३ कपि पूर्वम्` `अ-कुमारी᳓कः`; `पा॰ ६.२.१७४ ह्रस्वान्तेऽन्त्यात् पूर्वम्` `अ-य᳓वकः`, `सु-य᳓वकः`), and `बहु` abundance (`पा॰ ६.२.१७५ बहोर्नञ्वदुत्तरपदभूम्नि`: `बहु-व्रीहिः᳓`, `बहु-ज᳓रः`, `बहु-य᳓वकः`).
  - *Svāṅga* `-अक्ष`/`-सक्थ` (`पा॰ ५.४.११३ + ६.१.१६३` `षच्` *antodātta*: `हिरण्य-अक्षा᳓न्`, `विश्व-अक्ष᳓म्`, `विरूप-अक्ष᳓म्`, `सहस्र-अक्ष᳓स्य`); `-मुख` blocked after *avyaya*/etc. (`पा॰ ६.२.१६८`: `विश्व᳓तः-मुखः`, `अधो᳓-मुखम्`, `प्रत्य᳓ङ्-मुखाः`); optional *antodātta* on `द्वि`/`त्रि` + `पाद्`/`दत्`/`मूर्धन्` (`पा॰ ६.२.१९७ द्वित्रिभ्यां पाद्दन्मूर्धसु बहुव्रीहौ`: `द्वि᳓-पात्`/`द्वि-पा᳓त्`, `द्वि᳓-मूर्धा`/`द्वि-मूर्धा᳓`).
- **Dual-udātta `वनस्पत्यादि` & `देवताद्वन्द्व` (`पा॰ ६.२.१४०–१४२`):** `पा॰ ६.२.१४० उभे वनस्पत्यादिषु युगपत्` (`ब्र᳓ह्मणस्-प᳓तिः`, `बृ᳓हस्-प᳓तिः`); `पा॰ ६.२.१४१ देवताद्वन्द्वे च` (`इ᳓न्द्रा-सो᳓मा`, `इ᳓न्द्रा-व᳓रुणा`, `इ᳓न्द्रा-बृ᳓हस्-प᳓ती`), blocked when the second member is *anudāttādi* except `पृथिवी`/`रुद्र`/`पूषन्`/`मन्थिन्` (`पा॰ ६.२.१४२ नोत्तरपदेऽनुदात्तादावपृथिवीरुद्रपूषमन्थिषु`: `इन्द्राग्नी᳓`, `इन्द्रवायू᳓` vs `द्या᳓वा-पृथिवी᳓`, `सो᳓मा-रुद्रा᳓`).

###### Compound accents (`समास-स्वरः`): Avyayībhāva, Tatpuruṣa, Kṛdanta, & Chandas

- **Avyayībhāva apavādas:** Default *avyayībhāva* follows `पा॰ ६.१.२२३` unless overridden by `पा॰ ६.२.१२१ कूलतीरतूलमूलशालाऽक्षसममव्ययीभावे` (*uttarapada-ādyudātta*: `परि-कू᳓लम्`, `उप-शा᳓लम्`, `उप-अ᳓क्षम्`, `सु-ष᳓मम्`, `वि-ष᳓मम्`) or `पा॰ ६.२.३३ परिप्रत्युपापा वर्ज्यमानाहोरात्रावयवेषु` (*pūrvapada-prakṛtisvara*: `प्र᳓ति-पूर्वाह्णम्`, `अ᳓प-त्रिगर्तम्`).
- ***Tatpuruṣa* *pūrvapada-prakṛtisvara* (`पा॰ ६.२.२`, `१८–१९`, `२२`, `३८`, `४६–५०`):**
  - `पा॰ ६.२.२ तत्पुरुषे तुल्यार्थतृतीयासप्तम्युपमानाव्ययद्वितीयाकृत्याः`: `तुल्यार्थ` (`तु᳓ल्य-श्वेतः`), `तृतीया` (`शङ्कुला᳓-खण्डः`), `सप्तमी` (`अक्ष᳓-शौण्डः`), `उपमान` (`हंस᳓-गद्गदा`), `अव्यय` including `नञ्` (`अ᳓-ब्राह्मणः` *ādyudātta* in *tatpuruṣa* vs `६.२.१७२` *antodātta* in *bahuvrīhi*; `प्र᳓-कृतः`), `द्वितीया` (`मुहूर्त᳓-सुखम्`), and `कृत्य` (`भोज्य᳙-लवणम्`, `पानी᳓य-शीतम्`).
  - Named *pūrvapada* rules: `पा॰ ६.२.१८ पत्यावैश्वर्ये` (`गण᳓-पतिः`, `गृह᳓-पतिः`) vs `पा॰ ६.२.१९ न भूवाक्चिद्दिधिषु` (`भूपतिः᳓`, `वाक्पतिः᳓`, `चित्पतिः᳓`, `दिधिषूपतिः᳓`); `पा॰ ६.२.२२ पूर्वे भूतपूर्वे` (`कृत᳓-पूर्वम्`, `आढ्य᳓-पूर्वः`); `पा॰ ६.२.३८ महान् व्रीह्यपराह्णगृष्टीष्वासजाबालभारभारतहैलिहिलरौरवप्रवृद्धेषु` (`महा᳓-व्रीहिः`, `महे᳓ष्वासः`, `महा᳓-भारः`).
  - Before `क्त` / `त`-initial `नित्` `कृत्`: `पा॰ ६.२.४६ कर्मधारयेऽनिष्ठा` (`श्रे᳓णि-कृताः`, `निध᳓न-कृताः`), `पा॰ ६.२.४७ अहीने द्वितीया` (`कष्ट᳓-श्रितः`, `ग्रा᳓म-गतः`), `पा॰ ६.२.४८ तृतीया कर्मणि` (`अहि᳓-हतः`, `वज्र᳓-हतः`), `पा॰ ६.२.४९ गतिरनन्तरः` for **karmaṇi `क्त`** immediately after `गति` (including `च्वि`/`ऊर्यादि` `पा॰ १.४.६१`: `सरली᳓-कृतम्`; `अ᳓नश्यतः`, `अ᳓जायमानः`, `ब्र᳓ह्म-पूता`, `नि᳓र्मुक्तः`, `प्र᳓-ओतः`, `प्र᳓-सूता`; stacked *gatis* retain inner `गति`'s accent via `६.२.४९` + `६.२.१३९`, e.g. `समा᳓हिताः` per *Svara-siddhānta-candrikā*, never `३.१.३`/`फि॰ १.१`), and `पा॰ ६.२.५० तादौ च निति कृत्यतौ` for non-`-अत्` `त`-initial `नित्` `कृत्` (`तृन्` `प्र᳓-कर्ता`, `तुमुन्` `प्र᳓-कर्तुम्`, `क्तिन्` `प्र᳓-सूती`/`प्र᳓-सूत्यै`, `स᳓म्-ऋद्धीः`, `नि᳓र्-ऋतिः` — never cite `६.२.४९` or `उणादिप्रत्ययस्वरः` for `क्तिन्`, and never apply `६.२.५०` to `पाकन्` `प्रजल्पा᳓कः` or `तुन्` `आगन्तुः᳓`).
- ***Tatpuruṣa* *uttarapada-ādyudātta* (`पा॰ ६.२.१२२–१२५`, `१३२`):** `द्विकं᳓सः` (`६.२.१२२`), `ब्राह्मण-शा᳓लम्` (`६.२.१२३` neut.), `सौशमि-क᳓न्थम्` (`६.२.१२४` neut.), `राज-पु᳓त्रः` (`६.२.१३२`).
- **`गतिकारकोपपदात् कृत्` (`पा॰ ६.२.१३९`) & Paribhāṣā 28:** *Kṛdanta* *uttarapada* keeps its `कृत्` *prakṛtisvara*, including two-layer `[कारक + [गति + कृत्]]` (`कृद्ग्रहणे गतिकारकपूर्वस्यापि ग्रहणम्`): `ल्यु`/`ल्युट्` `पा॰ ६.१.१९३ लिति` (`इध्म-प्रव्र᳓श्चनः`, `वाल-ब᳓न्धनः`, `अघ-म᳓र्षणः`, `अमृत-उपस्त᳓रणम्`, `अमृत-अपिधा᳓नम्`, `द्वार-पिधा᳓नः`, `कल-विक᳓रणाय`; `च्वि` `स्वादूक᳓रणम्` `पा॰ १.४.६१`); `ण्वुल्` `पा॰ ६.१.१९३ लिति` (`आ-ख्या᳓यिकाः`, `अधि-आ᳓यकः` — never `३.१.३`!); `णिनिः` `पा॰ ३.१.३` (never `नित्`!; Vedic `-वादिन्` `पा॰ ३.२.७८ + ३.१.३ + ६.२.१३९` retains `-दि᳓-` rather than classical `पा॰ ६.२.७९ णिनि` ādyudātta: `लोक-धारि᳓णी`, `अन्ते-वासि᳓नम्`, `उच्चैर्-वादि᳓`, `ब्रह्म-वादि᳓नः`, `प्रिय-वादि᳓नम्`); `क्विप्` (`अग्र-भु᳓क्`, `पुण्य-कृ᳓तः`); `ण्यत्` `पा॰ ६.१.१८५ तित्स्वरितम्` (never `६.१.२१३ यतोऽनावः`!: `भिक्षा-चर्य᳙म्`, `उप-आस्य᳙म्`); `क्वसु`/participles (`सव्ँ-विदानः᳓`, `शत्रु-ह᳓त्यै`, `गुरु-तल्प-गः᳓`, `पुरमद्ध्य-सँस्थ᳓म्`, `सद्यो-जात᳓म्`); `शतृ` before `ङीप्`/vowel *sup* (`पा॰ ६.१.१७३`: `प्र-मृशतः᳓`); active *divādi* `श्यन्` (`पा॰ ३.१.६९, ६.१.१९७`: `दी᳓प्यमानः`, never `यक् पा॰ ३.१.६७`); `संज्ञायां कन्` (`पा॰ ५.३.७५ + ६.१.१९७`: `म᳓न्थाककः`, never `कन् पा॰ ३.१.३`).
- **`६.२.१३९` *apavāda*s, default `६.१.२२३`, & Vedic `६.२.१९९`:**
  - `पा॰ ६.२.१४४ थाथघञ्क्ताजबित्रकाणाम्` (`क्थन्` `सुनीथः᳓`, `अवभृथः᳓`; `घञ्` `प्र-बोधः᳓`; `अच्` `प्र-क्षयः᳓`; `अप्` `प्र-लवः᳓`; `इत्र` `प्र-लवित्र᳓म्`; `क` `जीवन-प्रदः᳓`, `निधि-गोपः᳓`; *kartari* `क्त` `प्र-सूता᳓`; and *kāraka*-preceded or non-adjacent-`गति` `क्त` `पराङ्-गताः᳓`, `आतप-शुष्कः᳓`, `दूराद्-आगतः᳓`); `पा॰ ६.२.१४५ सूपमानात् क्तः` (`सु-तृप्त᳓म्`); `पा॰ ६.२.१५० अनो भावकर्मवचनः` (`अति-आशना᳓त्`, `वेद-अनुवचन᳓म्`); `पा॰ ६.२.१५१` (`छन्दो-व्याख्यान᳓म्`, `गो-स्थान᳓म्`); `पा॰ ६.२.१९१ अतेरकृत्पदे` (`अति-बलः᳓`, `अत्यङ्कुशः᳓`); `पा॰ ६.२.१६०` (`नञ्` + `कृत्य`: `अनाधृष्यः᳓`).
  - Non-*kāraka* *karmadhāraya* (`परम-कारक᳓म्`), *śeṣa-ṣaṣṭhī* (`देवदत्त-कारकः᳓`), and *dvandva* without apavāda follow `पा॰ ६.१.२२३ समासस्य` (`अन्न-पाने᳓`, `इष्टा-पूर्त᳓म्`, `विश्वाधि᳓कः`, `सन्न्यास-योगा᳓त्`, `ज्योतिर्-आत्मा᳓`).
  - Vedic overrides (`पा॰ ६.२.१९९ परादिश्छन्दसि बहुलम्` — *"परादिश्च परान्तश्च पूर्वान्तश्चापि दृश्यते। पूर्वादयश्च दृश्यन्ते व्यत्ययो बहुलं ततः"*): e.g. `अञ्जि-स᳓क्थम्`, `लोमश-स᳓क्थौ`, `ऋजु-बा᳓हुः`, `वाक्-प᳓तिः`, `चित्-प᳓तिः`.

###### Single-accent & non-zero-accent invariants (`पा॰ ६.१.१५८`) & automated audits

- **No zero-accent non-nighāta padas:** Every Sanskrit pada carries **one** accent (`᳓` or `᳙`, or two under `पा॰ ६.२.१४०–१४२`) unless de-accented by an explicit Pāṇinian rule cited in its provenance (`पा॰ ८.१.२८` main-clause `तिङन्त` with any `गति` split off as its own accented pada, `पा॰ ८.१.१८–२३` enclitics, `पा॰ ८.१.१९` non-initial vocatives such as `देवि`, `शर्व`, `वृषभ`, `पा॰ ८.१.३` *āmreḍita*, `पा॰ ८.१.७०–७१` *gati*, `पा॰ २.४.३२–३४` *anvādeśa* `अस्य`, `एतस्मिन्`, `एनम्`). **Never** leave a *subanta*, *kṛdanta*, compound, adverb, or main-clause *upasarga* with 0 accents (`प्र-सूती → **प्र᳓-सूती**`, `जात्यै → **जा᳓त्यै**`, `दन्तिः → **दन्तिः᳓**`, `स्तब्धः → **स्तब्धः᳓**`, `महा-ज्ञेयम् → **महा-ज्ञेय᳓म्**`, `प्र → **प्र᳓**`), **never** leave `→ **?**` unresolved, and **never** rubber-stamp an unaccented or unanalyzed form as `(आरण्यक-पाठः (अनाम्नातम्))`. Watch for word-initial udāttas hidden in `पा॰ ८.२.५` *ekādeśa* with the prior word (`नाति॑भवे` = `न᳓` + `अ᳓ति-भवे`, `वि॒तस्त॒या ऽऽर्जी॑कीये` = `वित᳓स्तया` + `आ᳓र्जीकीये`) or lost behind a prior word's dependent `॑` in corrupt prints (`तं प्र॑पद्यामि`, `सोऽक्ष॑रः`, `कि॒ञ्चिज्ज॑गत्य॒स्मिन्`).
- **No unresolved multi-udātta padas:** Resolve every multi-udātta compound via the rules above rather than leaving `**?**`, checking whether `to_US_accents` duplicated an *ekādeśa* udātta across internal vowel sandhi (`विश्वा᳓त्मन्` → `विश्व᳓-आ᳓त्मानम्`, `सप्ता᳓र्चिषः` → `सप्त᳓-अर्चि᳓षः`) or misread missing `॒` marks in printed `मूलम्`. Where printed `मूलम्` has a spurious dual udātta on a non-`६.२.१४०` stem (`म᳓न्थाककः᳓`), resolve to the single Pāṇinian accent (`म᳓न्थाककः`) rather than inventing `पा॰ ३.१.३`.
- **Mandatory deterministic validation & cross-repo sync:** Always run **both** `doc_curation.sanskrit.accent.validator` (`validate_accented_markdown` / `validate_paired_vp_and_tk`, enforcing header counts, `पा॰ ६.१.१५८` non-zero accents, no `→ **?**`, no unsplit `पा॰ ८.१.२८` `upasarga + tiṅanta` including nominal homograph guards, no `split_combining_after_markup` / malformed bolding, and commentator attribution) **and** `doc_curation.sanskrit.accent.auditor` (`audit_directory_trees`, or CLI `~/gitland/python_venv/bin/python -m doc_curation.sanskrit.accent.auditor <dirs...> --with-reconciler --with-corpus-counter`, which runs `validator` + `reconciler` plus heuristics for false commentator stamps, `पा॰ ८.२.४` *yaṇ*-svarita placement, *ekādeśa* multi-accent arrows, non-initial `पा॰ ६.१.१९८` vocatives, `MW`-only arrows, `मूलम्` svarita misreads, false compounds, `false_corpus_citation`, `weak_rv_av_override`, `missing_yv_corpus_counts`, `known_false_svara_antipattern`, and `vp_includes_tiikaa` nesting — on large trees, pre-filter candidate files via `rg -l` before `--with-corpus-counter` scans). Never include `sarvASh_TIkAH/` or embed `पद-पाठः (यान्त्रिकः)` blocks inside `vishvAsa-prastutiH/` files; remember `vedAH_yajuH/static` and `vedAH_yajuH/content` can be separate git repos, and after editing included `static/` files, refresh downstream prefilled containers via `doc_curation.md.content_processor.include.transformer.surgical_prefill_transitive([content_dir, static_dir], changed_paths, only_if_prefilled=True)` (distinguishing śākhā-specific `पद-पाठः` headers like `SB-M` vs `SB-K` across `js_include`s).

###### Attestation priority, Taittirīya normalization, & multi-accent homographs

- **Prefer attested Vedic forms over extrapolation:** Prefer attested forms (`*TS*`, `*RV*`, `*TB*`, `*TK*`, `*AV*`, `*SB-M*`, `*SB-K*`, legacy `*ŚB*`, `*VS-M*`, `*VS-K*`, legacy `*VS*`, `*KS*`, `*MS*` — **never** use `*TA*` Taittirīya Āraṇyaka or `*EK*` Ekāgnikāṇḍa as sources since their traditional svara-s are dubious) over `*MW*` stem extrapolation.
- **Normalize Taittirīya & guard weak overrides:** Normalize Taittirīya anunāsika (`व्ँ`/`य्ँ`/`ल्ँ` ↔ `ं`) when matching against `*TS*`/`*TB*`, and never cite bare unverified `*CORPUS*` tags (`NEW` 0 hits while `OLD` is attested), override a valid single-accent or YV-attested `OLD` form with weak (`<=2`/bare) non-Pāṇinian `*RV*`/`*AV*` hits (`यमत् → **य᳓मत्**`, `स्वि᳓त्`, `व᳓धीत्`, `वो᳓चः`), or override it with an unattested `*MW*` homograph stem.
- **Disambiguate multi-accent homographs explicitly:** Whenever a pada or stem has **multiple genuine lexical, inflectional, or śākhā accents** (`वे᳓द` 'Śruti/knowledge' `पा॰ ६.१.२०३` vs `वेद᳓` 'darbha-muṣṭi/wealth' `घञ्`; `ध᳓र्म` 'sacred duty/law' vs `धर्म᳓` 'bearer'; `ब्र᳓ह्मन्` neut. 'Brahman/Veda' vs `ब्रह्म᳓न्` masc. 'Brahmā/priest'; `अ᳓न्तक` 'Death/ender' vs `अन्तक᳓` 'border'; `म᳓हः` neut. 'greatness/light' vs `महः᳓` oblique of `मह्` `पा॰ ६.१.१६८`; `वा᳓चः`/`रा᳓यः`/`दि᳓शः`/`ऊ᳓र्जः` nom./acc. pl. vs `वाचः᳓`/`रायः᳓`/`दिशः᳓`/`ऊर्जः᳓` gen./abl. sg. `पा॰ ६.१.१६८`; `वैदेहः᳓` `अण्` 'of the bodiless' vs `वै᳓देहः` `अञ्` 'king of Videha'; `सह᳓` adv. vs `स᳓हः` neut.; `सु-कृत᳓म्` adj. `पा॰ ६.२.१४५` vs `सु᳓-कृतम्` neut. `पा॰ ६.२.२`), select the accent required by context/commentaries and **list the alternative accent(s) inside the parentheses**, stating why the chosen form is preferred (sense, gender, case, *vigraha*, or recension — e.g. `- वे᳓द᳓म् → **वे᳓दम्** (श्रुत्यर्थे वे᳓दम् आद्युदात्तम् श्रेयः, वृषादिः पा॰ ६.१.२०३, *AV*, *RV* वे᳓दः, *TB*; दर्भमुष्टौ धने वा वेद᳓म् अन्तोदात्तम्, *TS* वेदः᳓, *MW*)`).

### Fake accents

Some Vedic texts (e.g. some taittirīya āraṇyaka sections) carry fake accents — typically mechanically applied runs of udAtta. Detect:

```python
accent.detect_fake_US_accents(text)  # → suspicious runs of >5 consecutive ᳓; empty list = nothing found
```

If you are explicitly asked, you may also spot other fake-accented US text beyond what the above detector finds. Here direct correction is allowed:

1. Remove **all** accents from that `विश्वास-प्रस्तुतिः` block (`accent.strip_accents(text)`), or keep the unaccented text if that was already done by hand. In both cases, append `(स्वराः पूर्याः)` ("accents still to be supplied") to the details block name, i.e. `<details open><summary>विश्वास-प्रस्तुतिः (स्वराः पूर्याः)</summary>`.
2. Re-insert accents only when asked — and when filling US svara-s into an unaccented or `(स्वराः पूर्याः)` `विश्वास-प्रस्तुतिः` block whose `मूलम्` carried accents:
   - Ensure `<details><summary>पद-पाठः (यान्त्रिकः...)</summary>` is present and clean below `मूलम्`, then populate US accents directly onto `विश्वास-प्रस्तुतिः` (`doc_curation.sanskrit.accent.reconciler.fill_vp_accents_from_padapatha`).
   - Update the `विश्वास-प्रस्तुतिः` summary (via `format_filled_vp_summary`) to append `(D/P व्यत्यस्त-स्वराः)` when `D > 0` of `P` padas differed from `मूलम्` (mirroring `पद-पाठः (यान्त्रिकः - D/P व्यत्यस्त-स्वराः)`, e.g. `<details open><summary>विश्वास-प्रस्तुतिः (5/25 व्यत्यस्त-स्वराः)</summary>`), omit the suffix when `D == 0` (`<details open><summary>विश्वास-प्रस्तुतिः</summary>`), or use `(यन्त्र-स्वरः)` when `मूलम्` itself was completely unaccented. Use `reconcile_and_sync_markdown_blocks` (or `reconcile_markdown_blocks(..., sync_vp_summaries=True, fixed_point=True)`) to reconcile `[[OLD|NEW]]` spans, direct-filled blocks, and `<summary>` counts to fixed point.

### Splitting errors

Typical `मूलम्`-block errors are at the beginnings and terminations of split blocks, e.g.

> "सम्मा॑ऽऽसिञ्चन्तु म॒रुत॒स् समिन्द्र॒स् सं बृह॒स्पतिः॑ । सम्मा॒यम॒ग्निस् सि॑ञ्च॒त्वायु॑षा च॒ बले॑न॒ चायु॑ष्मन्तङ् करोत॒ मा" इति।

has a missing svarita at the end. These errors likely arose from faulty splitting by a human. Where an error is found, fix it in the `मूलम्` block and in the corresponding `विश्वास-प्रस्तुतिः` block. In such cases, you can correct directly, without the [[OLD|NEW]] suggestion.

### Interactive review workflow (`pada_svara`) & corpus backfill

- **Review GUI (`~/gitland/python_venv/bin/pada_svara --dir <path>` / `~/gitland/python_venv/bin/python -m pada_svara --dir <path>`, packaged at `/home/vvasuki/gitland/sanskrit-coders/diff_san/vishvAsa/pada_svara`):** Presents `[[OLD|NEW]]` suggestions alongside aligned `मूलम्` / `पद-पाठः` context (default filter `Pending` `Alt+P`, excluding `!!` feedback items from pending counts and filter; `Accept`/`Reject`/`Feedback` `Alt+1`/`Alt+2`/`Alt+3`, `Enter` submit / `Ctrl+Enter` accept+submit, `Ctrl+R` rescan, `Ctrl+Z` undo, `←`/`→` collapse/expand, GoldenDict & IntelliJ links) backed by `pada_svara.review`. Accept/Reject edits `विश्वास-प्रस्तुतिः`, feedback inserts `+++(FEEDBACK!!)+++` at the corresponding line/item, and paired `static/`/`content/` prefill snapshots are synced. **Important:** `pada_svara` caches per-item `विश्वास-प्रस्तुतिः` block snapshots from the last scan to locate exact suggestion offsets; if underlying files are modified on disk (e.g. while fixing `!!` flags externally), press **`Ctrl+R`** in the GUI to rescan before submitting further decisions so edits do not fail with `"Could not locate target विश्वास-प्रस्तुतिः block"`.
- **Resolving `!!` feedback end-to-end:** When resolving a flagged `!!` comment: (1) inspect local commentary (`हरदत्तः`, `भास्करः`, `सायणः`), recensional `mUlam/`, and adjacent/parallel mantra clusters (`2_17/09–12`); (2) fix both `sarvASh_TIkAH/` (`पद-पाठः` + `N/P` header, removing `!!`) and paired `vishvAsa-prastutiH/` (`[[OLD|NEW]]` or unwrap cleanly); (3) **scan the rest of `ekAgnikANDam` and `vedAH_yajuH`** (`static/` and `content/`) for analogous instances of the same root-cause bug (e.g. `कन् पा॰ ३.१.३`, `पा॰ ८.१.३` on enclitic `मा᳓ मा`/`ते᳓ ते` or separate-clause `न᳓मः`, `वै`/`वाव` `पा॰ ८.१.६४` vs `पा॰ ८.१.२८`, `<vocative>+<nominative>` compound merges) and harden `validator`/`auditor`/`shatapatha_solver` + unit tests against regressions; (4) sync prefilled containers via `surgical_prefill_transitive(..., only_if_prefilled=True)` and verify with `validator`, `auditor --with-corpus-counter`, and `pytest`.
- **Corpus-count backfill CLI (`~/gitland/python_venv/bin/python -m doc_curation.sanskrit.accent.backfill --dir <dir> --corpora ...`):** Safely backfills newly added corpora into `पद-पाठः (यान्त्रिकः)` blocks with pre-write structural/tag guards and optional `surgical_prefill_transitive` refresh.

## Local hyphenation & specialist models (only when specifically requested)

**Recommendation (`doc_curation/llm/proofreader/README.md`):** Use local `hyphene` (`doc_curation.sanskrit.hyphenator`, `distill/README.md`) for fast clean-text hyphenation of US-accented `विश्वास-प्रस्तुतिः` (`᳓`/`᳙` preserved losslessly); use `Qwen3-14B` (`proofread_text` when OCR cleanup & discourse clause breaks are also needed, or `accent_helper` below only when specifically requested as a RAG-grounded `पद-पाठः` draft assistant).

**Mandatory random quality check & redo:** Whenever `hyphene`, `accent_helper`, `reconciler`, or `proofread_text` is run, randomly spot-check sampled mantra clusters (checking commentary glosses, `पा॰ ६.१.१५८` / `६.२.*` / `८.१.२८` / `८.२.४–६`, compound splits, and `[[OLD|NEW]]` spans) in addition to running `sandhi_check`, `validator`, and `auditor` (`python -m doc_curation.sanskrit.accent.auditor <dirs...> --with-reconciler --with-corpus-counter`), and redo any flawed padas or blocks directly.

1. **Distilled local SLP1 neural hyphenator (`doc_curation.sanskrit.hyphenator.hyphene`):** Used automatically by `doc_curation.sanskrit.accent.samasa.decompose_samasa_for_padasvara` (alongside `<2 ms` memory-mapped `BytesTrie` lexicon lookup in `lexicon.py`), and can be called directly (`hyphene(vp_text, clause_newlines=True)`) on CPU in `~3–16 ms`/sentence.
2. **Fine-tuned `Qwen3-14B` LoRA `पद-पाठः (यान्त्रिकः)` draft assistant (`doc_curation.llm.proofreader.accent_helper`, only when specifically requested):** Grounds `doc_curation/data/models/qwen3-14b-sanskrit-lora/` (`~46.5%` draft char similarity) with retrieved `*RV*`/`*TS*`/`*AV*`/`*MW*` Babylon candidates — always run the deterministic sandhi/accent validators afterward:

```python
from doc_curation.llm.proofreader import PADAPATHA_ACCENT_SYSTEM_PROMPT, ProofreaderBackend
from doc_curation.llm.proofreader.accent_helper import format_padapatha_user_prompt, retrieve_accent_candidates
from doc_curation.sanskrit.accent import auditor, reconciler, sandhi_check, validator

backend = ProofreaderBackend(base_url="https://<tunnel>/v1")
hits = retrieve_accent_candidates(mula_text)
prompt = format_padapatha_user_prompt(
    mula_text, commentary_text=tika_text, translation_text=trans_text, lexicon_hits=hits,
)
padapatha_block = backend.new_chat(PADAPATHA_ACCENT_SYSTEM_PROMPT).send_text(prompt)
# Always verify forward sandhi, पा॰ ६.१.१५८ / ८.१.२८ invariants, & heuristic audit deterministically:
# sandhi_check.verify_mantra_sandhi(...), validator.validate_accented_markdown(...), reconciler.reconcile_markdown_blocks(...), auditor.audit_directory_trees(...)
```
