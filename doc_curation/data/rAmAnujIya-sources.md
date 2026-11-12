# rAmAnujIya.trie — sources and build rules

Word/stem frequency trie for the rAmAnujIya prastuti corpus, used by
`doc_curation/sanskrit/hyphenator.py` as the highest-priority evidence layer
(above `dcs-frequency.trie`, above `sanskrit-words.trie`).

Rebuild (also happens automatically when a source file is newer than the
trie):

```python
import doc_curation.sanskrit.hyphenator as h
h.rebuild_ra_trie()
```

## Sources

Only `<details>` blocks whose `<summary>` label starts with
`विश्वास-प्रस्तुतिः` or `नीलमेघ` (e.g. `नीलमेघः (सं)`) are harvested.

| # | Root | Notes |
|---|------|-------|
| 1 | `/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/venkaTa-nAtha-shAkhA/venkaTanAthaH/rahasya-traya-sAraH/sarva-prastutiH` | all `.md` recursively |
| 2 | `/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH` | only rel-paths `< 1_ayoga-vyavachChedaH/08_AkAshAdhikaraNam.md` (i.e. `1_ayoga-vyavachChedaH/01_jijnAsAdhikaraNam/**` … `07_antaradhikaraNam.md`); `08_AkAshAdhikaraNam.md` and later are **held out** for evaluation |
| 3 | `/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/Agama-prAmANyam/sarva-prastutiH` | all `.md` recursively |
| 4 | `/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/chatush-shlokI/sarva-prastutiH` | all `.md` recursively |
| 5 | `/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/yAmunaH/siddhi-trayam/sarva-prastutiH/02_Atma-siddhiH` | all `.md` recursively |

## Extraction rules

* Prastuti text is pada-split with `-` at samAsa joints.  The hyphen pieces
  are recorded as **words**.  The hyphen-joined chunk is deliberately *not*
  recorded (as a whole "exact" word it would swallow the internal splits the
  corpus itself makes).
* Tokens containing non-Devanagari / non-hyphen chars (citations like
  `(तै.भृ.१.२)`, markdown, Latin) are skipped; edge dandas/digits/emphasis
  are stripped; interior dandas/digits are rejected.
* **Stems**: mechanical light-stemmer truncation (longest sup/tiG ending of
  `_SUP_ENDINGS`, plus `_STEM_FINALS` restorations), kept only when the stem
  is itself known (in this corpus, DCS, or the stardict wordlist).  A stem
  inherits its source word's occurrence count.
* Trie values are occurrence counts (capped at 65535).
