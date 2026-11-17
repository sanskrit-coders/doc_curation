---
name: grammar
description: Answers Sanskrit grammar questions — how a form is derived, which sūtra applies, what a sūtra means, sandhi/declension/conjugation/kāraka rules, or the accent of a pāda — from Pāṇini with commentaries (ashtadhyayi.com data), our pāṇinīya notes, accent dictionaries and corpora, Whitney's Sanskrit Grammar, Deshpande's primer, and step-by-step derivation with vidyut/airaavata. Use for any vyākaraṇa question, including "why is this form thus?" and "what is the svara of this word?".
---

## Answering grammar questions

The sources below are read-only reference corpora. Choose by question type, then cross-check:

| Question | Start with |
|---|---|
| Which sūtra-s derive form X? | derivation steps (ashtadhyayi `shabdaprakriya.txt`, `dhatuforms_*`), vidyut/airaavata for anything not in them (section 5), and our `dhAtu-prakriyA` notes |
| What does sūtra N say, and how do commentaries read it? | aShTAdhyAyI `sutraani/` |
| What is the accent of pāda or stem X, and how is it justified? | accent dictionaries and corpora, then the rules — section 6 |
| General rule, paradigm, exception, historical/comparative note | Whitney |
| Learner-level explanation, lesson sequence, drills | Deshpande |
| Topic discussion, open questions, tabular summaries | our `pANinIyam/` notes |

## 1. Pāṇini with commentaries

`~/gitland/sanskrit/raw_etexts/vyAkaraNam/aShTAdhyAyI-com-data/` — the dataset behind ashtadhyayi.com (edit upstream via the website; don't edit here).

### `sutraani/`
- `data.txt` — JSON, all 3983 sūtra-s. Fields: `a`,`p`,`n` (adhyāya, pāda, number); `s` mūla text; `ss` sūtra read with anuvṛtti filled in; `pc` padaccheda (`शब्द$S$vibhakti$vacana$##...`); `an` anuvṛtti sources (`वृद्धिः$11001`); `ad` adhikāra span (`प्रत्ययः$3.1.1`); `type` topic and type (`S`/`V`/`P` = saṃjñā/vidhi/paribhāṣā, `AD$` marking an adhikāra); `e` transliteration.
- **id is compressed**, not dotted: `1.1.1` → `"11001"`, `8.4.68` → `"84068"`.
- Commentaries, each `{id: text}` JSON: `kashika`, `nyaas`, `padamanjari`, `bhashya`, `balamanorama`, `kaumudi`, `laghukaumudi`, `prakriyasarvasvam`, `praudhamanorama`, `sarala`, `sudha`, `laghushabdendushekhar`, plus `sutrartha_english` (English gloss) and `sutra_prayogas` (attested kāvya usages, keyed **dotted** `"1.1.5"`).
- Āhnika-wise Mahābhāṣya: `../mahabhashyam/{1,2}.txt`.
- Only the main commentaries (`kashika`, `balamanorama`, `prakriyasarvasvam`, `nyaas`, `padamanjari`, `sutrartha_english`) cover all sūtra-s; `sudha` (~400), `praudhamanorama` (~460), `sarala` (~250), `laghushabdendushekhar` (~90) are partial. A missing id or empty string means that commentary does not gloss the sūtra — not that nothing is said anywhere.

### Forms and derivations
- `shabda/data2.txt` — stems: `word`, `linga` (P/S/N), meanings, `forms` (24 cells = 8 vibhaktis × 3 vacanas), `baseindex`.
- `shabda/shabdaprakriya.txt` — the derivation of a form as ordered `steps`, each with its `sutras` — the fastest answer to "why is this form thus".
- `dhatu/data.txt` — dhātus with `gana`, `pada`, `settva`, meanings, `baseindex` (`01.0001`); `dhatu/dhatuforms_*.txt` — tiṅ forms keyed by that baseindex.
- Others: `krut/`, `unaadi/`, `ganapath/`, `linganushasanam/`, `pratyahara/`, `shiksha/`, `kosha/` (Amarakośa, MW, …), `paribhashendushekhar/`, `paramalaghumanjoosha/`, `vakyapadeeyam/`, `tarkasangraha/`, `fit/`, `courses/`.

```python
import json, os
B = os.path.expanduser("~/gitland/sanskrit/raw_etexts/vyAkaraNam/aShTAdhyAyI-com-data")
S = json.load(open(f"{B}/sutraani/data.txt"))["data"]
sid = "11001"                                  # 1.1.1; or search s["s"] for a word
print(next(s for s in S if s["i"] == sid)["s"])
for c in ["kashika", "balamanorama", "padamanjari", "sutrartha_english"]:
    print(c, ":", json.load(open(f"{B}/sutraani/{c}.txt")).get(sid, "")[:300])
```

Sūtra pages: `https://ashtadhyayi.github.io/suutra/<a>.<p>/<a>.<p>.<n>` (note `suutra`).

## 2. Our notes

`~/gitland/vishvAsa/sanskrit/content/vyAkaraNam/pANinIyam/`

| Subdir | Content |
|---|---|
| `saMjJNA/` | saṃjñā-s — varṇa, dhātu/pratyaya, prādi, śabda- and prakriyā-related terms |
| `paribhAShA/` | interpretative conventions, it-saṃjñā, sūtrāvagati |
| `sandhiH/` | sandhi rules, `padAnte`, `mahAbaleshvaraH` |
| `prAtipadika-prakriyA/` | nominal stems, `lingam/lingAnushAsanam`, it-saṃjñā |
| `dhAtu-pratyaya-vidhiH/` | pratyaya-vidhi — lakāra-s (`la`, `luN`, `lArthAH`), `kRt`, pratyayādeśa, vivakṣāṅga |
| `dhAtu-prakriyA/` | actual derivations — `prakriyAH/tiNantAni`, `kRdantAni`, `la/` (lakāra-s), `angAni` |
| `dhAtu-siddhiH/` | dhātu-pāṭha copy, dhātu-kārikā-s, dhātu-nirmāṇa |
| `samAsaH/` | compounds — `prakriyA/`, `mahAbaleshvaraH` |
| `vAkya-staram/` | sentence level — kāraka, vibhakti, prayoga, dvirukti, gati |
| `svaraH/` | accent rules and sources — see section 6 |
| `avyutpannAH/`, `meta/` | unanalysed words; administrative notes and articles |
| `mUlAni/` | source texts we host — `aShTAdhyAyI_vishvAsa-prastutiH.md`, `gaNapAThaH.md`, `kAshikA/`, `nAgeshaH/`, `mahA-bhAShyam/` |

- Topics come as prose `.md` **plus** a same-named `.toml` holding the tabular rows rendered in site widgets — read both.
- `dhAtu-prakriyA/prakriyAH/tiNantAni/*.md` is our worked-derivation format: every step is `अक्षर 1.3.1 → भू,तिप् (सूत्रम् [A](link))`, ideal for citing a full derivation.
- `mUlAni/aShTAdhyAyI_vishvAsa-prastutiH.md` is our hyphenated, `+++(...)+++`-annotated edition, one sūtra per line prefixed `a.p.n` — not bare mūla text.

## 3. Whitney

`~/gitland/vishvAsa/sanskrit/content/vyAkaraNam/whitney/` — `01`–`23` chapters (alphabet, pronunciation, sandhi, declension, nouns/adjectives, numerals, pronouns, conjugation, present/perfect/aorist/future systems, verbal adjectives, secondary conjugation, periphrastic and compound conjugation, indeclinables, derivation, compounds), then appendix, Sanskrit and general indexes. Paragraphs are numbered `321.` with `a.`/`b.` sub-items — cite "Whitney §321". It is OCR'd; verify odd glyphs before quoting.

## 4. Deshpande

`~/gitland/vishvAsa/sanskrit/content/vyAkaraNam/deshpANDe.md` — *A Sanskrit Primer* (18k lines), lessons as `## 01` … `## 44` (e.g. 04 conjugations 4/6/10, 05 cases, 12 gerunds and infinitives, 16 passive, 17 future), with `### CONTENTS`, `## GLOSSARY`, `## ADDITIONAL SANSKRIT READINGS`. Cite "Deshpande, Lesson 7". Its OCR garbles some Devanagari headers (stray digits like `37` for `अकारान्त`) — infer from context.

## 5. Deriving a form on demand — vidyut via airaavata

`~/gitland/sanskrit-coders/airaavata/airaavata/prakriyaa.py` wraps vidyut's `Vyakarana.derive` and prints each step as `सूत्र-num → intermediate form (sūtra text + link)` — the same format as our `tiNantAni` notes, because this is the script that generated them (`dump_tinantas`, `dump_subantas`, `dump_kRdantas`). Use it whenever a form is not in `shabdaprakriya.txt` (that file has ~4.9k entries only).

Run with the venv python (~1.5 s to load the engine):

```python
import sys, os, logging
sys.path.insert(0, os.path.expanduser("~/gitland/sanskrit-coders/airaavata"))
from vidyut.prakriya import (Pada, Dhatu, Gana, Lakara, Purusha, Vacana,
                            Prayoga, Pratipadika, Krt, Linga, Vibhakti)
from vidyut.kosha import PadaEntry
from indic_transliteration.vidyut_helper import slp
from airaavata.prakriyaa import lookup_and_derive, kosha
logging.getLogger().setLevel(logging.ERROR)  # the module switches on DEBUG at import

p = Pada.Tinanta(dhatu=Dhatu.mula(aupadeshika="BU", gana=Gana.Bhvadi),
                 prayoga=Prayoga.Kartari, lakara=Lakara.Lat,
                 purusha=Purusha.Prathama, vacana=Vacana.Eka)
print(list(lookup_and_derive(p)))     # ['भवति'], values hold the full derivation

s = Pada.Subanta(pratipadika=Pratipadika.basic("rAma"), linga=Linga.Pum,
                 vibhakti=Vibhakti.Prathama, vacana=Vacana.Eka)
print(list(lookup_and_derive(s)))     # ['रामः']
```

- Inputs to `Dhatu.mula` / `Pratipadika.basic` are **SLP1** (`BU`, `rAma`), while `lookup_and_derive("राम")` takes Devanagari and derives every kosha parse of that pāda.
- `Dhatu.mula(aupadeshika=..., gana=...)` for roots; secondary roots via `dhatu.with_sanadi((Sanadi.san,))`, `Pratipadika.krdanta(dhatu, Krt.kta)` for kṛdantas, `Dhatu.nama(...)` for nominal verbs.
- `lookup_and_derive(pada, out_file_path=...)` writes a site-format derivation page (`## <form>` + step lines); `PRAKRIYA_DHATU`/`PRAKRIYA_SUP` are the target dirs for `tiNantAni`/`kRdantAni`/`sup`.
- The kosha is keyed by **inflected padas, not roots**: `lookup_and_derive("भवति")` gives tiṅantas, while `lookup_and_derive("भू")` gives only the subanta parses of that spelling (several forms, e.g. `भू` and `भा`), and `type=PadaEntry.Tinanta` on it yields `None`. Start from a root by building `Pada.Tinanta` yourself, or lift the root out of a form: `[x for x in kosha.get(slp("भवति")) if isinstance(x, PadaEntry.Tinanta)][0].dhatu_entry.dhatu`. `type=` only filters the parses of one spelling.
- Results are a **dict keyed by the final form**, so two different sūtra paths to the same form collapse to one. For alternatives, `from airaavata.prakriyaa import v` and iterate `v.derive(entry)` yourself.
- `DATA_PATH` at the top of `prakriyaa.py` must point at a built vidyut-data (`.../vidyut-latest/{prakriya,kosha}`); edit the constant if it moved.
- Never run the bulk `dump_*` functions on the local machine — those go to Kaggle/Colab.

Verify each generated step against `sutraani/data.txt` before quoting it in an answer: the step text is vidyut's summary, and a code missing from `code_to_sutra` prints as `(??)`.

## 6. Accent determination

Look for attestation first; derive only when nothing attests the form. Order of work:

### 6.1 Padasvara dictionaries — the primary tool

`~/gitland/sanskrit/raw_etexts/koshaH/indic-dict/kAvya/` (StarDict copies on the external drive: `/media/vvasuki/vData/dicts/stardict/indic-dict/stardict-sanskrit-kAvya/`)

| Dict | Gives |
|---|---|
| `rv-padasvara-dev` | Ṛgveda word forms with accents, plus occurrences (`1 72 7 d` = maṇḍala, sūkta, ṛk, pāda) |
| `av-padasvara` | Atharvaveda word forms with accents, plus occurrences (`/20/136/12`) |
| `kyv-ts-padasvara` | Kṛṣṇa-Yajurveda-TS word forms with dependent accents |
| `rv-padapATha-dev` | Ṛgveda pādas: unaccented saṃhitā head → accented saṃhitā + accented pada-pāṭha + reference |

Heads are `|`-separated; in the padasvara dicts a trailing `+` marks the pre-sandhi pada, so search the bare word. All of these are Babylon files — blank-line separated entries, head line first:

```python
import os

DICTS = os.path.expanduser("~/gitland/sanskrit/raw_etexts/koshaH/indic-dict")

def lookup(babylon_path, word, limit=5):
    text = open(babylon_path, encoding="utf-8", errors="ignore").read()
    hits = []
    for entry in text.split("\n\n"):
        head, _, body = entry.partition("\n")
        if word in head.split("|"):
            hits.append(body.strip())
            if len(hits) >= limit:
                break
    return hits

print(lookup(f"{DICTS}/kAvya/rv-padasvara-dev/rv-padasvara-dev.babylon", "अभवः"))
# → ['अ॑भवः<br>1 72 7 d, 1 91 2 d, …']
print(lookup(f"{DICTS}/kAvya/rv-padapATha-dev/rv-padapATha-dev.babylon", "अग्निमीळे पुरोहितं"))
# → ['1 1 1 a<br>अ॒ग्निमी॑ळे पु॒रोहि॑तं<br>अ॒ग्निम् ईळे पु॒रोहि॑तम्']
```

### 6.2 Accent-marked dictionaries

`~/gitland/sanskrit/raw_etexts/koshaH/indic-dict/sanskrit/sa-head/en-entries/` (StarDict: `…/stardict-sanskrit/sa-head/en-entries/`) — same `lookup()` works, but big files (MW ~60 MB) take a second:

| Dict | Accent convention |
|---|---|
| `mw-cologne` | appends `॑` to the accented syllable (`अग्नि॑`) — the best general source, ~42k marks |
| `lanman`, `macdonell` | Vedic accent as a combining acute (`aṅganā́`) |
| `whitney-roots` | accented roots |
| `shabda-sAgara`, `vaidya` | a handful of `॑` only |

`edgerton-buddhist-hybrid`, `wilson`, `apte-1890`, `apte-1957`, `spokensanskrit`, `Vedic-Index-of-Names-and-Subjects` carry **no** accents; `benfey` has only a few. Don't promise an accent from these.

### 6.3 Accented corpora

Use when the word is not in the dictionaries above, or when you need to decide among different accents based on context:

- /home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH (has pada-pATha too)
- /home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH (has pada-pATha too)
- /home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/kAThakam/sarva-prastutiH
- /home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/brAhmaNam/sarva-prastutiH
- `~/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/brAhmaNam/sarva-prastutiH/`
- `~/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/kAThakam/sarva-prastutiH/`
- `~/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/shatapatha-brAhmaNam/sarva-prastutiH/`
- `/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/mAdhyandinam/saMhitA/sarva-prastutiH`
- `/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/vAjasaneyam/kANvam/saMhitA`
- `/home/vvasuki/gitland/vishvAsa/vedAH/content/atharva/shaunakam/rUDha-saMhitA/sarva-prastutiH`
- `/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/kaTha-kapiShTalAH/saMhitA/mUlam/schroeder/`

`grep -rn "<word>" <dir>` gives the accented occurrence in context. These carry dependent accents in `मूलम्` blocks and US accents in `विश्वास-प्रस्तुतिः` blocks.

### 6.4 The rules

`~/gitland/vishvAsa/sanskrit/content/vyAkaraNam/pANinIyam/svaraH/` — `pada-svaraH.md` (common pada-accent rules), `phiT-sUtrANi.md` (Phiṭ-sūtras used in accent derivation), `sandhiH.md`, `vAkyasvaraH.md`, `pramANAni.md`, `shrInivAsa-svara-siddhAnta-chandrikA/`. Whitney's pronunciation chapter and the `svara`-related sūtra-s (`6.1.…`, `8.2.…`, `phiṭ`) supplement these.

### 6.5 Answering

- Attested in a dictionary or corpus → give the accented form **with its source and reference**; prefer the padasvara dict, since MW's single `॑` under-specifies.
- Only the stem's accent attested → say so explicitly, and don't silently extrapolate.
- Derived from rules → mark it per the `accenting` skill: tag the block `<details open><summary>विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)</summary>` and add a `पद-पाठः (यान्त्रिकः)` block giving each pada, its accent, provenance, and doubts.
- Editing an accented text: suggest, don't rewrite — give the correction as `[[OLD|NEW]]` (see `accenting`); re-accenting, fake-accent stripping and splitting fixes are the exceptions that may be applied directly.
- Never harmonise silently: keep the text's own accents unless a source contradicts them, and then say which source.

## How to answer

1. Locate the sūtra-s: search `s` in `data.txt`, read the derivation steps for the form, or derive it with vidyut when it isn't cached.
2. Read at least Kāśikā + Bālamanoramā (or Padamañjarī/Nyāsa) + the English gloss; add Mahābhāṣya or Śabdenduśekhara for contested points.
3. Check our notes for the topic and for a ready-made derivation.
4. Bring in Whitney (rule shape, exceptions, history) and Deshpande (learner framing) as needed.
5. For accents, follow section 6 — attestation before derivation, provenance always.
6. Present: the rule (`1.1.1 वृद्धिरादैच्`), the step-by-step application with sūtra numbers, options/exceptions, and a citation per claim.

- Never invent a sūtra number or wording — verify in `data.txt` and quote `s` verbatim.
- Keep bhāṣya/kārikā positions distinct from our own notes, and say which commentary says what.
- When writing site content, hyphenate Sanskrit to our conventions but leave quoted sūtra-s unhyphenated so they stay verifiable.
