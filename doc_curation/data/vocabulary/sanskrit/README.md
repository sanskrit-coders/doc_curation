# Sanskrit vocabulary data for the hyphenator

Data consumed by
[`doc_curation/sanskrit/hyphenator.py`](../../../sanskrit/hyphenator.py)
(sandhi-aware pāda-splitting of Sanskrit text).  All `*.trie` files are
[marisa tries](https://github.com/s-yata/marisa-trie), built lazily on first
use and rebuilt automatically whenever a source file is newer than the trie
(`_load_words`); they can be force-rebuilt with `rebuild_word_tries()`,
`rebuild_dcs_trie()` and `rebuild_ra_trie()`.

The same tries are exported as `HYP1` `.bin.gz` files for the in-browser
hyphenator page (`vishvAsa/sanskrit/content/lekhanam/hyphenator/`), so the
browser loads prebuilt data and never rebuilds anything.

## Word tries — `RecordTrie("H")`, HK key → u16 count

`words_sa_dev.txt` (stardict headwords, from `indic-dict`) is partitioned
into four category tries using the
`indic-dict/dicts/stardict-sanskrit-vyAkaraNa` sources (vidyut subanta
tables, vidyut tiNanta tables, the aṣṭādhyāyī gaṇapāṭha):

| trie | contents | category source |
| --- | --- | --- |
| `padas.trie` | inflected words / everything not identified below | wordlist remainder |
| `nominal-stems.trie` | nominal stems | first column of each vidyut subanta headword (`subanta/vidyut/*`) |
| `verb-stems.trie` | verb roots/stems | first two columns of each vidyut tiNanta headword (`tiNanta/vidyut/*`) |
| `avyayas.trie` | indeclinables; **also the source of the hyphenator's `_AVYAYAS` closed class** | स्वरादि / चादि gaṇas of `aShTAdhyAyI/gaNapAThaH/gaNapAThaH.babylon` + DCS entries glossed `indeclinable ind` |
| `dcs-stems.trie` | DCS corpus stem frequencies | `stardict-sanskrit-kAvya/dcs-frequency/dcs-frequency.babylon`, tier-mapped |

Words claimed by more than one category go to the more specific bucket
(avyaya > verb stem > nominal stem); e.g. `गज` is both a nominal and a verb
stem and lands in `verb-stems.trie`.

## rAmAnujIya corpus tries

Sources and ingestion rules: `rAmAnujIya-sources.toml`.

| trie | format | contents |
| --- | --- | --- |
| `rAmAnujIya.trie` | `RecordTrie("H")`, HK → u16 count | corpus words + mechanically inferred stems (highest-scored layer) |
| `rAmAnujIya-attestations.trie` | `RecordTrie("H")`, HK → bit flags | the corpus attestation memory: bit 1 = the corpus itself uses the token (as a hyphen piece or as a whole unhyphenated token — halant-final candidates like `सर्व्`/`अपास्` are vetoed unless flagged); bit 2 = e/o-final piece the corpus joins onward (`गणे-श्वरम्`, `पङ्के-रुह`, implies bit 1) |
| `rAmAnujIya-splits.trie` | `BytesTrie`, joined devanagari surface → bytes | corpus's own segmentation memory: `b""` = attestably left unsplit (never split it); `b"<permille>\t<form>"` = the winning hyphenated form plus its normalized frequency (per-mille of the surface's occurrences; see `_ra_form_confidence`) |
| `rAmAnujIya-ngram.trie` | `RecordTrie("II")` | junction letter-context counts from the same segmentations: key `left\x1fright` in devanagari (≤3 letters each side) → `(n_split, n_plain)`; the longest attested context decides |
| `rAmAnujIya-seps.trie` | `RecordTrie("II")` | separator glyph preference per junction (HK context) → `(n_hyphen, n_dash)`: `-` = within-samāsa joint, `–` = boundary between upapadas of a samāsa whose upapadas are themselves samāsas (spelled `--` in older corpus text, sometimes with a space between the dashes in very long chains; `–` is the preferred output glyph) |
| `rAmAnujIya-badsplits.trie` | `RecordTrie("H")` | negative split evidence: junction contexts where the analyzer, run over the corpus with the memo bypassed, cuts text the corpus keeps whole (or cuts the corpus form lacks) → evidence weight |

Build-time only: prastuti pieces are rejoined into the mūla surface with the
`sandhi` package (`_join_pieces`, `_merge_editor_junction`); the browser
never needs it.

## TOML files

* `rAmAnujIya-sources.toml` — the corpus sources (paths + accepted
  `<details>` labels) that feed all `rAmAnujIya*` tries.  Edit this to add
  or drop corpora; the tries rebuild on next use.
* `misc-vocab.toml` — closed-class vocabulary used by the module
  (`upasargas`, `pronouns`; avyayas come from `avyayas.trie`).
* `misc_hyphenator_data.toml` — the hyphenator's algorithmic tuning data
  (seed words, bare suffixes, sandhi keeps, weak rights, short pieces, sup
  endings, stem finals), kept with the tries.

`bad-splits.md` is scratch space for noting mis-splits; it is not read by
the code.
