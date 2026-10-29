"""Local Sanskrit hyphenator (sandhi-preserving pada/samAsa splitter).

Implements the ``bare-hyphenator`` LLM instruction locally, without an LLM:

* Split separable word/stem boundaries, **without reverting sandhi**.
* **Never** split non-separable dIrgha / guNa / vRddhi mergers (absolute veto,
  even inside samAsa): ``dharmArtha``, ``mahotsava``, ``sadaiva`` stay joined.
* Separable: yaN (``ity evam``, ``madhv-ariH``), visarga (``rAmo 'sti``,
  ``namas te``), final ``m`` before vowels (``phalam aznute``), consonant
  assimilation (``tad dhi``), plus plain samAsa concatenation
  (``hetu-BAve``, ``brahma-jijJAsA``).
* Separator: hyphen ``-`` for samAsa-internal joints, space `` `` otherwise.

Method
------
Transliterate each Devanagari token to Harvard-Kyoto (HK) where vowels are
explicit, so separable sandhi is pure concatenation (``ity``+``evam`` =
``ityevam``).  Segment the HK token over *units* (aspirates ``kh``..``bh`` and
diphthongs ``ai``/``au`` are atomic) using a cost-minimising DP that validates
each candidate piece against the ``stardict-sanskrit`` wordlist
(``words_sa_dev.txt``):

* exact dictionary words;
* reverse-sandhi restorations: yaN (``ity``->``iti``, ``madhv``->``madhu``),
  visarga (``rAmo``->``rAmaH``, ``ataz``->``ataH``), avagraha
  (``'sti``->``asti``), consonant assimilation (``AsId``->``AsIt``);
* light sup/tiG stemming (``vedasya``->``veda``, ``mizraM``->``mizra``);
* upasarga+stem compounds (``samutpadyante``, ``duSprakRti``) - kept joined.

Guards (empirically tuned against विश्वास-प्रस्तुतिः / मूलम् pairs):

* **Merger veto** - a split is forbidden when the boundary vowel admits a
  dIrgha/guNa/vRddhi merger analysis of two exact dictionary words
  (``dayA``+``Ardra``, ``svaprakAza``+``advitIya``, ``dharma``+``artha``).
  This is what protects ``dharmArtha`` and ``svaprakAzAdvitIya``.
* A token that is itself a valid dictionary word (exact or inflected
  ``stem+ending``) is split **only** at high-precision sandhi boundaries
  (yaN / visarga / m-before-vowel / consonant assimilation): ``vRttasya``,
  ``kzaNikatvam``, ``zrutvA``, ``sarvajJa`` stay whole, while
  ``jagatkAraNa`` -> ``jagat-kAraNa`` (assimilation is separable).
* Every cut must be *witnessed* by its sandhi type - yaN cuts need a yaN
  surface (``ity``), visarga cuts need a visarga surface (``namas``,
  ``rAmo``, ``duSprakRter``), assimilation cuts need an assimilating final
  (``jagaj``, ``tad``); ``H -> z/S/r`` is only valid before its proper
  environments (r before vowels, s/z before voiceless).
* A yaN boundary requires a vowel-initial right piece (``madhv``+``ariH``,
  never ``madhv``+``riH``).
* Rare/unattested shards (single-source dictionary entries such as ``yeva``,
  ``manaz``) and bare endings (``sya``, ``tva``, ``tvam``) are rejected as
  pieces; particles and pronouns after a cut become separate padas.

Separator choice per boundary:

* vowel-final left + consonant (plain samAsa concat) -> ``-``;
* m-vowel, visarga-o (incl. avagraha) -> space;
* yaN / visarga-r-s / assimilation -> space by default, ``-`` when the joint
  is a known compound (dictionary prefix) or a recognised suffix/idiom
  (``-Adi``, ``-antara``, ``-artha``, ``-zabda``, ``madhv-ari``...).

Fast: ~O(L^2) dict lookups per token with memoised validation.  Evidence is
layered as
``doc_curation/data/vocabulary/sanskrit/{padas,nominal-stems,verb-stems,avyayas,dcs-stems,rAmAnujIya}.trie``
(all marisa-tries built on first use, rebuilt when their sources change):

* ``rAmAnujIya.trie`` - words + stems harvested from the rAmAnujIya
  prastuti corpus (sources and ingestion rules recorded in
  ``data/vocabulary/sanskrit/rAmAnujIya-sources.toml``); scored
  highest;
* ``dcs-stems.trie`` - DCS corpus stem frequencies from
  ``dcs-frequency.babylon``; scored next;
* ``padas.trie`` / ``nominal-stems.trie`` / ``verb-stems.trie`` /
  ``avyayas.trie`` - ``words_sa_dev.txt`` stardict headwords partitioned
  with the vyAkaraNa sources (vidyut subanta stems, vidyut tiNanta
  roots/stems, the svArAdi/cAdi gaNas) into padas, nominal stems,
  verb stems and indeclinables;
* ``rAmAnujIya-splits.trie`` - the corpus's own segmentations (joined
  surface -> hyphenated form; empty = attestably unsplit).  Consulted
  first by ``hyphenate_word`` and reusable as whole DP pieces;
* ``rAmAnujIya-ngram.trie`` - junction letter-context counts from the same
  corpus (longest context decides; >=2:1 attested hyphenation).  On a memo
  miss it refines the DP result: adds corpus-attested hyphens
  (``आकाशादि-विशेष-शब्दैर्``) and prefers ``-`` over `` `` at joints the
  corpus hyphenates (``जगत्-कारणे``);
* ``rAmAnujIya-attestations.trie`` - the corpus attestation memory: HK token -> bits
  (1 = the corpus itself uses the token, as a hyphen piece or whole plain
  token; 2 = an e/o-final piece the corpus joins onward).  A halant-final
  piece taken from a dictionary entry or inferred stem is vetoed unless the
  corpus itself uses that token.
* ``rAmAnujIya-seps.trie`` - separator memory: for every junction of every
  hyphenated corpus token, votes for ``-`` (a within-samAsa joint) versus
  ``–`` (the boundary between upapadas of a samAsa where the upapadas are
  themselves samAsas; spelled ``--`` in older text, sometimes with a space
  between the dashes in very long chains, and normalised to the preferred
  ``–``).  Dash-dominant junctions render with ``–``; memoised forms keep
  the corpus's own separators verbatim (``_memo_form_seps``).
* ``rAmAnujIya-badsplits.trie`` - negative split memory: junction contexts
  the analyzer, run over the corpus with the memo bypassed, cuts where the
  corpus keeps the text whole (or cuts where the corpus form cuts
  elsewhere).  Evidence >= ``_RA_BADSPLITS_MIN`` vetoes a boundary the
  corpus n-gram does not sanction, weaker evidence only penalises it.

Algorithm tuning data lives outside the module: seed words / bare suffixes /
sandhi keeps / weak rights / short pieces in ``misc_hyphenator_data.toml``
(beside this module) and the closed classes (avyayas, upasargas, pronouns) in
``data/vocabulary/sanskrit/misc-vocab.toml``, next to the tries.  Prastuti
piece-rejoining recreates sandhi with the ``sandhi`` package (build-time
only: ``_join_pieces``, ``_merge_editor_junction``; browsers load prebuilt
tries and never need it).

Already-hyphenated compounds are left untouched (pieces adjacent to ``-`` are
not re-processed), so running on pre-split प्रस्तुति-style text is safe.
"""

import bisect
import glob
import math
import os
import regex
import tomllib
import unicodedata
import marisa_trie
from indic_transliteration import sanscript
import logging

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

from .constants import (
    _AVYAYAS,
    _AVYAYA_GANAS,
    _BARE_SUFFIXES,
    _COMPOUND_SUFFIXES,
    _DATA_DIR,
    _DCS_BABYLON,
    _DCS_TRIE_PATH,
    _DICT_TXT,
    _GANAPATHAH_PATH,
    _HIGH_KINDS,
    _LAYERED,
    _META_SUFFIXES,
    _MISC_DATA_TOML,
    _MISC_LOADED,
    _MISC_VOCAB_TOML,
    _PRONOUNS,
    _RA_ATTESTATIONS_TRIE_PATH,
    _RA_BADSPLITS_MAX_K,
    _RA_BADSPLITS_MAX_PIECE,
    _RA_BADSPLITS_MIN,
    _RA_BADSPLITS_TRIE_PATH,
    _RA_BADSPLITS_UNIT,
    _RA_BOOST,
    _RA_FORMS_TRIE_PATH,
    _RA_NGRAM_MAX_K,
    _RA_NGRAM_MIN_SPLITS,
    _RA_NGRAM_MIN_SUPPORT,
    _RA_NGRAM_RATIO,
    _RA_NGRAM_TRIE_PATH,
    _RA_SEPS_TRIE_PATH,
    _RA_SOURCES_TOML,
    _RA_TRIE_PATH,
    _RENDER_SPLIT_RE,
    _SANDHI_KEEP,
    _SEED_COUNT,
    _SEED_WORDS,
    _SEP_CAPTURE_RE,
    _SEP_GLYPHS,
    _SEP_SPLIT_RE,
    _SHORT_OK,
    _STEM_FINALS,
    _SUBANTA_GLOB,
    _SUP_ENDINGS,
    _TINANTA_GLOB,
    _TRIE_AVYAYAS,
    _TRIE_BADSPLITS,
    _TRIE_DCS,
    _TRIE_NOMINAL_STEMS,
    _TRIE_PADAS,
    _TRIE_RA,
    _TRIE_RA_ATTESTATIONS,
    _TRIE_RA_FORMS,
    _TRIE_RA_NGRAM,
    _TRIE_SEPS,
    _TRIE_VERB_STEMS,
    _UPASARGAS,
    _UPASARGA_HEADS,
    _VOWELS,
    _VYAKARANA_DIR,
    _WEAK_RIGHTS,
    _WEAK_RIGHTS_EXTRA,
    _WORD_TRIE_GLOBALS,
    _WORD_TRIE_PATHS,
    _load_misc_data,
    _read_toml_file
)

from .corpus_ra import (
    _INDEPENDENT_VOWELS,
    _RA_ANNOT_RE,
    _RA_BAD_RE,
    _RA_DETAILS_RE,
    _RA_EDGE,
    _SANDHI,
    _SANDHI_CACHE,
    _bad_add,
    _build_ra_attestations_trie,
    _build_ra_badsplits,
    _build_ra_forms_trie,
    _build_ra_ngram_trie,
    _build_ra_trie,
    _extract_ra_corpus,
    _extract_ra_word_counts,
    _form_positions,
    _join_pieces,
    _load_ra_sources,
    _merge_editor_junction,
    _ngram_add,
    _ngram_ctx,
    _ra_file_bodies,
    _ra_file_configs,
    _ra_source_files,
    _sandhi_single
)

from .tries import (
    _CACHE_RA_FORM,
    _DCS_VEDIC_LABELS,
    _DCS_VEDIC_SUFFIXES,
    _LayeredWords,
    _WordTrie,
    _babylon_head_lines,
    _build_dcs_trie,
    _build_tries,
    _category_word_sets,
    _dcs_label_is_vedic,
    _dcs_tier,
    _get_scheme_map,
    _invalidate_trie_caches,
    _load_words,
    _parse_dcs,
    _ra_form_confidence,
    _ra_split_form,
    _word_sources_mtime,
    export_browser_data,
    rebuild_dcs_trie,
    rebuild_ra_trie,
    rebuild_word_trie,
    rebuild_word_tries
)

from .validate import (
    _BASE_ATTESTED_MIN,
    _CACHE_CHAIN,
    _CACHE_CORE,
    _CACHE_DICT,
    _CACHE_ELEFT,
    _CACHE_GLOBAL_MERGER,
    _CACHE_RA_ATTESTED,
    _CACHE_RELIABLE,
    _CACHE_STEM,
    _CACHE_STEM_BASE_PIECE,
    _CACHE_STEM_PIECE,
    _CACHE_VETO,
    _CACHE_VIS_RESTORE,
    _CACHE_WITNESS,
    _CACHE_YAN_LEFT,
    _CACHE_YAN_RESTORE,
    _DIRGHA_MAP,
    _GUNA_MAP,
    _MERGER_MIN,
    _RELIABLE_MIN,
    _STEM_BASE_MIN,
    _VRDDHI_MAP,
    _attested,
    _base_attested,
    _chain_end_ok,
    _chain_word_ok,
    _core_valid,
    _count_of,
    _dict_attested,
    _halant_final,
    _has_global_merger_uncached,
    _has_visarga_restore,
    _has_yan_restore,
    _is_veto_split_uncached,
    _joined_left_attested,
    _junction_dict_ok,
    _left_final_witness,
    _memo_form_seps,
    _memo_piece_split,
    _merger_chain_uncached,
    _merger_exps,
    _piece_ending_ok,
    _piece_reliable,
    _prefix_in_dict,
    _reliable,
    _restores_of,
    _stem_base_piece,
    _stem_base_piece_uncached,
    _stem_valid,
    _stem_valid_piece,
    _stem_valid_piece_uncached,
    _stem_valid_uncached,
    _tight_merger_surface,
    _valid_piece_kind,
    _veto_side_ok,
    _whole_kind,
    _yan_restored_left,
    _yan_restored_left_uncached,
    has_global_merger,
    is_veto_split,
    merger_chain_valid
)

from .seps import (
    _CACHE_SEP,
    _boundary_kind,
    _build_ra_seps_trie,
    _sep,
    _sep_add,
    _sep_dash
)

from .segment import (
    _ANNO_RE,
    _ASPIRATE_FIRST,
    _CACHE_BAD,
    _CACHE_MEMO_PIECE,
    _CACHE_MEMO_SEPS,
    _CACHE_TOKEN,
    _DEV_DISJ_RE,
    _MAX_UNITS,
    _QUALITY,
    _WORD_RE,
    _badsplit_evidence,
    _freq_quality,
    _hyphenate_hk_token,
    _hyphenate_hk_token_uncached,
    _junction_ngram_plain,
    _ngram_cell,
    _ngram_refine,
    _ngram_votes_hyphen,
    _segment,
    hk_to_units,
    hyphen,
    hyphenate,
    hyphenate_text,
    hyphenate_word,
    hyphene
)
