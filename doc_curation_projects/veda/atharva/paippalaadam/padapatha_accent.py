"""De-novo US Vedic accenting (यन्त्र-स्वरः) and ``पद-पाठः (यान्त्रिकः)`` builder for Atharvaveda Paippalāda.

Processes all remaining un-deduplicated / cross-Veda variant blocks after Stage 1–2 dedup:
- **Exact upstream matches**: skipped (already linked directly to accented RV/AV/etc. VP + ṭīkās).
- **Manually US-accented Paippalāda VPs**: VP text preserved verbatim; bulleted ``पद-पाठः (यान्त्रिकः)``
  generated from the manual accents and stored locally or in linked ``sarvASh_TIkAH/``.
- **Upstream-variant blocks** (local VP + linked upstream ``sarvASh_TIkAH``): aligns against the linked
  upstream mantra FIRST (then ``AV``/``RV``/``TS``/``VS-M``/``VS-K``/``MS`` reference witnesses +
  clause-aware Viterbi), updates local ``विश्वास-प्रस्तुतिः - {ऋक्|यजुः} (यन्त्र-स्वरः)``, and merges
  ``पद-पाठः (यान्त्रिकः - पैप्पलादम्)`` into the shared upstream ``sarvASh_TIkAH`` file.
- **Local & self-repeated AV-P blocks**: aligns parallel witnesses (including ``AV`` Śaunaka and
  pāda-level parallels) + Viterbi (with sister-śākhā ``AV`` boost), writes US-accented VP and
  ``पद-पाठः (यान्त्रिकः)``, and refreshes transitive ``js_include`` prefills across all callers.
"""
from __future__ import annotations

import dataclasses
import logging
import pathlib
import re
from collections import defaultdict
from collections.abc import Sequence

logger = logging.getLogger(__name__)


from doc_curation.md.content_processor.include import seeker as include_seeker
from doc_curation.md.content_processor.include import transformer
from doc_curation.sanskrit.accent import reconciler as accent_reconciler
from doc_curation.sanskrit.accent.provenance import (
  MAJOR_AUTO_CORPORA,
  VedicCorpusCounter,
  normalize_panini_abbreviations,
)
from doc_curation.sanskrit.accent.reconciler import (
  format_filled_vp_summary,
  has_us_accents,
)
from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi
from doc_curation.sanskrit.accent.shatapatha_solver import (
  _DEVANAGARI_RE,
  _MISSING_VEDIC_TINANTAS_DEVA,
  _MISSING_VEDIC_TINANTAS_HOMOGRAPHS_DEVA,
  ALWAYS_ANUDATTA_ENCLITICS,
  AMBIGUOUS_ENCLITICS,
  ANVADESHA_2432,
  ANVADESHA_2434,
  UPASARGA_DEVA_SET,
  UnifiedVedicLexicon,
  _detect_clause_contexts,
  _fast_apply_us_marks,
  _fast_syllable_count,
  _is_dual_accent_word,
  _normalize_lookup_key,
  _stem_final_syl_idx,
  split_vp_to_padas_with_clauses,
)
from doc_curation.sanskrit.accent.taittiriya_padapatha import (
  _project_us_marks_onto_padas,
  _split_chunk_with_avagraha_and_hints,
)
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim

from doc_curation_projects.veda.atharva.paippalaadam.dedup import (
  _build_paippalada_caller_roots,
)
from doc_curation_projects.veda.atharva.paippalaadam.prepare import DEFAULT_HUGO_BASE
from doc_curation_projects.veda.dedup import cascade
from doc_curation_projects.veda.dedup.block_parser import (
  format_details_block,
  group_mantra_units,
  render_tokens,
  replace_group_tokens,
  tokenize_markdown_body,
)
from doc_curation_projects.veda.dedup.commentary_merger import (
  _resolve_corpus_spec_for_ref,
  merge_tika_additions,
)
from doc_curation_projects.veda.dedup.matcher import classify_unit_kind
from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec, load_corpus_specs
from doc_curation_projects.veda.yajuH.ks_ms.padapatha_builder import (
  _VEDIC_VOCATIVE_WORDS,
  _align_parallel_mantra_padas,
  _build_provenance_for_pada,
  _project_solved_accents_to_vp,
  _solve_unaccented_padas_viterbi,
  normalize_ks_ms_orthography,
)
from doc_curation_projects.veda.yajuH.ks_ms.reference_index import (
  VedicReferenceIndex,
  _clean_vp_to_us,
  clean_vedic_text,
)

AVP_PROVENANCE_CORPORA: tuple[str, ...] = tuple(MAJOR_AUTO_CORPORA)
AVP_PREFER_SOURCES: tuple[str, ...] = ("AV", "RV", "TS", "VS-M", "VS-K", "MS")

_TRIPLE_PLUS_RE = re.compile(r"\+\+\+.*?\+\+\+", re.DOTALL)
_SUG_PICK_NEW_RE = re.compile(r"\[\[([^|\]]*)\|([^\]]*)\]\]")
_ALL_ACC_STRIP_RE = re.compile(r"[\u1cd0-\u1cff\u0951-\u0957\u0300-\u036f]")
_TITLE_ATTR_RE = re.compile(r'(\btitle=)(["\'])([^"\']*)\2')


@dataclasses.dataclass
class SolvedAvpResult:
  """Solved VP and ``पद-पाठः (यान्त्रिकः)`` output for a single Paippalāda mantra unit."""

  vp_summary: str
  vp_body: str
  pp_lines: list[str]
  padas_bare: list[str]
  padas_us: list[str]
  was_manual: bool
  unit_kind: str
  sandhi_ok: bool
  sandhi_detail: str
  par_aligned_padas: int = 0

  @property
  def pp_markdown(self) -> str:
    return "\n".join(self.pp_lines)


def _prepare_vp_for_splitting(vp_raw: str, *, keep_accents: bool) -> str:
  """Normalize Paippalāda VP for sandhi splitting, stripping GRETIL glosses, bold, and lacunae."""
  s = _SUG_PICK_NEW_RE.sub(r"\2", vp_raw)
  s = _TRIPLE_PLUS_RE.sub(" ", s)
  s = s.replace("(…)", " ").replace("…", " ")
  s = s.replace("**", "").replace("*", "")
  if not keep_accents:
    s = _ALL_ACC_STRIP_RE.sub("", s)
  # Preserve sentence/pāda delimiters as spaces/daṇḍas before KS/MS orthography normalization
  s = re.sub(r"\s+", " ", s).strip()
  return normalize_ks_ms_orthography(s)


def _extract_unit_kind(vp_raw: str, summary: str = "", url_hint: str = "") -> str:
  if "/Rk/" in url_hint or "ऋक्" in summary:
    return "rk"
  if "/yajuH/" in url_hint or "यजुः" in summary:
    return "yajuh"
  return "rk" if classify_unit_kind(vp_raw, summary=summary, default_brahmana=False) == "rk" else "yajuh"


_ALWAYS_ANUDATTA_ENCLITICS = frozenset({"च", "मे", "नः", "णः", "वः", "त्वा", "ह", "स्म", "उ", "इव", "समह"})

_AVP_SINGLE_TOKEN_SPLITS: dict[str, tuple[str, ...]] = {
  "चेह": ("च", "इह"),
  "नेह": ("न", "इह"),
  "ओते": ("आ", "उत"),
  "ष्व्": ("सु",),
}

_RAW_AVP_OOV_FRAGMENT_JOINS: dict[tuple[str, ...], tuple[str, ...]] = {
  ("अपि", "गणाः", "अपि", "गणम्"): ("अपि-गण", "अपि-गणम्"),
  ("अति", "दुह्नाम्"): ("अति-दुह्नाम्",),
  ("असि", "अवत"): ("अस्य", "अवत"),
  ("असि", "आवत"): ("अस्य", "अवत"),
  ("अवि", "दाम्"): ("अविदाम्",),
  ("सु-षू", "ऊदिम"): ("सुषूदिम",),
  ("वृषम्", "यन्ति"): ("वृषण्यन्ती",),
  ("प्र", "जायै"): ("प्र-जायै",),
  ("उप", "सद्ये"): ("उप-सद्ये",),
  ("चुक्", "आ", "कणि"): ("चुकाकणि",),
  ("काल्", "माषे", "यस्य"): ("काल्माषेयस्य",),
  ("खट्", "उरीम्"): ("खडुरीम्",),
  ("अम्प्", "अरीष्यन्"): ("अम्बरीष्यम्",),
  ("दृषत्", "रथा", "महम्"): ("दृषद्-रथाम्", "अहम्"),
  ("उरु", "कीम्"): ("उरुकीम्",),
  ("क्र", "कुम्"): ("क्रकुम्",),
  ("कुस्", "ऊलीम्"): ("कुसूलीम्",),
  ("शीर्", "शाण्य्"): ("शीर्शाण्य्",),
  ("शीर्", "शाणि"): ("शीर्शाणि",),
  ("अद्व", "इष्य", "प्रती-काशः"): ("अद्वेष्य-प्रतीकाशः",),
  ("सक्", "अलिक"): ("सगलिक",),
  ("पुष्", "अलिक"): ("पुषलिक",),
  ("करि", "क्र", "तीः"): ("करिक्रतीः",),
  ("विवस्व", "ग्वा", "ते"): ("विवस्वग्वाते",),
  ("सपत्न-हा", "शासम्", "सितः"): ("सपत्न-हा", "आशा-संसितः"),
  ("सपत्न-हा", "प्सम्", "सितः"): ("सपत्न-हा", "अप्-संसितः"),
}
_AVP_OOV_FRAGMENT_JOINS: dict[tuple[str, ...], tuple[str, ...]] = {
  tuple(_normalize_lookup_key(x) for x in k): v
  for k, v in _RAW_AVP_OOV_FRAGMENT_JOINS.items()
}


def _is_valid_par_map_entry(
  bare_w: str,
  mks: tuple[str, ...],
  lex: UnifiedVedicLexicon | None = None,
  *,
  is_clause_start: bool = False,
) -> bool:
  """Reject parallel alignments that copy sandhi svaritas, unlicensed 0-accent nominals, or corrupt enclitic accents."""
  n_acc = sum(1 for m in mks if m)
  if bare_w in _ALWAYS_ANUDATTA_ENCLITICS and n_acc > 0:
    return False
  if bare_w == "न" and n_acc == 0:
    return False
  if n_acc == 0:
    licensed_zero = (
      bare_w in _ALWAYS_ANUDATTA_ENCLITICS
      or bare_w in ALWAYS_ANUDATTA_ENCLITICS
      or bare_w in AMBIGUOUS_ENCLITICS
      or bare_w in ANVADESHA_2432
      or bare_w in ANVADESHA_2434
      or bare_w in UPASARGA_DEVA_SET
      or bare_w in ("उत्", "सम्", "निर्", "दुर्")
      or bare_w in _MISSING_VEDIC_TINANTAS_DEVA
      or bare_w in _MISSING_VEDIC_TINANTAS_HOMOGRAPHS_DEVA
    )
    if not licensed_zero and lex is not None:
      morph = lex.analyze_morph(bare_w)
      if morph["is_tinanta"] and bare_w not in (
        "आमयतः", "आर्षयः", "आस्य", "सद्ये", "अजानाम्", "जायै", "त्रायै", "वर्तम्", "अधा",
      ):
        licensed_zero = True
      elif not is_clause_start and (morph["voc_possible"] or bare_w in _VEDIC_VOCATIVE_WORDS):
        licensed_zero = True
    if not licensed_zero:
      return False
  if n_acc > 1 and not _is_dual_accent_word(bare_w) and bare_w != "वाव":
    return False
  if "S" in mks:
    try:
      rendered = _fast_apply_us_marks(bare_w, mks)
    except ValueError:
      return False
    for m_sv in re.finditer(r"(.{0,6})\u1cd9", rendered):
      if not re.search(r"्[यव][ािीुूृेैोौःंँ]*$", m_sv.group(1)):
        return False
  return True


def _postprocess_avp_padas(
  padas_bare: list[str],
  clause_ids: list[int],
  vp_bare_norm: str,
  lex: UnifiedVedicLexicon,
) -> tuple[list[str], list[int]]:
  """Repair common AV-P splitter artifacts (``चेह``, ``तत् + छिरः``, ``उद्-यासम्``, ``ओते``, OOV chops)."""
  out_pd: list[str] = []
  out_cid: list[int] = []
  idx = 0
  n = len(padas_bare)
  while idx < n:
    pd = padas_bare[idx]
    cid = clause_ids[idx]
    key = _normalize_lookup_key(pd)

    # 1. Exact OOV / spurious split multi-token repairs (look-ahead 4, 3, 2)
    matched_multi = False
    for klen in (4, 3, 2):
      if idx + klen <= n and all(clause_ids[idx + j] == cid for j in range(1, klen)):
        tup = tuple(_normalize_lookup_key(padas_bare[idx + j]) for j in range(klen))
        if tup in _AVP_OOV_FRAGMENT_JOINS:
          if tup in (("असि", "अवत"), ("असि", "आवत")) and (not out_pd or _normalize_lookup_key(out_pd[-1]) != "भूत्वा"):
            continue
          rep = _AVP_OOV_FRAGMENT_JOINS[tup]
          out_pd.extend(rep)
          out_cid.extend([cid] * len(rep))
          idx += klen
          matched_multi = True
          break
    if matched_multi:
      continue

    if idx + 2 < n and clause_ids[idx + 1] == cid and clause_ids[idx + 2] == cid:
      if key == "जीवात्" and _normalize_lookup_key(padas_bare[idx + 1]) == "अव" and _normalize_lookup_key(padas_bare[idx + 2]) == "इति":
        out_pd.append("जीवातवे")
        out_cid.append(cid)
        idx += 2
        continue

    if idx + 1 < n and clause_ids[idx + 1] == cid:
      nxt_raw = padas_bare[idx + 1]
      nxt_k = _normalize_lookup_key(nxt_raw)
      if key == "शीर्ष" and nxt_k.startswith(("हत्य", "रोग")):
        out_pd.append(f"शीर्ष-{nxt_raw}")
        out_cid.append(cid)
        idx += 2
        continue

    if key in _AVP_SINGLE_TOKEN_SPLITS:
      rep_s = _AVP_SINGLE_TOKEN_SPLITS[key]
      out_pd.extend(rep_s)
      out_cid.extend([cid] * len(rep_s))
      idx += 1
      continue

    if key == "आ-याव" or (pd == "अ-याव" and out_pd and _normalize_lookup_key(out_pd[-1]) in ("उत्", "उद्")):
      out_pd.append("अयाव")
      out_cid.append(cid)
      idx += 1
      continue

    if key == "आगुः" and (not out_pd or _normalize_lookup_key(out_pd[-1]) not in ("आ", "मा")):
      cand_pd = out_pd + ["आ", "अगुः"] + padas_bare[idx + 1 :]
      if verify_mantra_sandhi(cand_pd, vp_bare_norm)[0]:
        out_pd.extend(["आ", "अगुः"])
        out_cid.extend([cid, cid])
        idx += 1
        continue

    if key == "एयम्" and idx + 1 < n and _normalize_lookup_key(padas_bare[idx + 1]) in ("अगन्", "अगमम्"):
      cand_pd = out_pd + ["आ", "इयम्"] + padas_bare[idx + 1 :]
      if verify_mantra_sandhi(cand_pd, vp_bare_norm)[0]:
        out_pd.extend(["आ", "इयम्"])
        out_cid.extend([cid, cid])
        idx += 1
        continue

    if key == "निर्वपात्":
      cand_pd = out_pd + ["निर्", "वपात्"] + padas_bare[idx + 1 :]
      if verify_mantra_sandhi(cand_pd, vp_bare_norm)[0]:
        out_pd.extend(["निर्", "वपात्"])
        out_cid.extend([cid, cid])
        idx += 1
        continue

    if "-" in pd:
      p0, p_rest = pd.split("-", 1)
      rest_k = _normalize_lookup_key(p_rest)
      if (
        p0 in UPASARGA_DEVA_SET
        and rest_k
        and not lex.lookup_form(pd.replace("-", ""))
        and (lex.analyze_morph(rest_k)["is_tinanta"] or rest_k in _MISSING_VEDIC_TINANTAS_DEVA)
      ):
        p0_clean = "उत्" if p0 == "उद्" else p0
        cand_pd = out_pd + [p0_clean, p_rest] + padas_bare[idx + 1 :]
        if verify_mantra_sandhi(cand_pd, vp_bare_norm)[0]:
          out_pd.extend([p0_clean, p_rest])
          out_cid.extend([cid, cid])
          idx += 1
          continue
    # Restore chhatva `छ...` -> `श...` after `-त्`/`-च्`/`-न्` (पा॰ ८.४.६३) when `श...` is attested.
    if idx > 0 and key.startswith("छ") and len(key) >= 3 and out_pd and out_pd[-1].endswith(("त्", "च्", "न्")):
      cand_sha = "श" + pd[1:]
      sha_k = _normalize_lookup_key(cand_sha)
      if not lex.lookup_form(key) and (lex.lookup_form(sha_k) or lex.lookup_stem(sha_k)):
        cand_pd = out_pd + [cand_sha] + padas_bare[idx + 1 :]
        if verify_mantra_sandhi(cand_pd, vp_bare_norm)[0]:
          out_pd.append(cand_sha)
          out_cid.append(cid)
          idx += 1
          continue
    out_pd.append(pd)
    out_cid.append(cid)
    idx += 1
  return out_pd, out_cid


def _refine_avp_oov_marks_and_prov(
  pd: str,
  mks: tuple[str, ...],
  prov: str,
  lex: UnifiedVedicLexicon,
) -> tuple[tuple[str, ...], str]:
  """Replace unanalyzed ``अनाम्नातम्`` fallback with Pāṇinian/Phiṭ derivation and णत्व/षत्व lookup."""
  bare = _normalize_lookup_key(pd)
  n_syl = len(mks)
  if n_syl == 0:
    return mks, prov

  if bare == "उषासानक्ता" and "६.२.१४१" not in prov:
    return mks, f"देवताद्वन्द्वे च पा॰ ६.२.१४१, {prov}" if prov else "देवताद्वन्द्वे च पा॰ ६.२.१४१"

  if "अनाम्नातम्" not in prov and not (prov.strip() == "मूल-पाठः" and bare != "ओते"):
    return mks, prov

  end_idx = _stem_final_syl_idx(bare, n_syl)
  # 1. Nañ (`अ-`/`अन्-`) or `सु-`/`निर्-` prefix (unhyphenated compound / bahuvrīhi).
  if re.match(r"^(?:अन्[अआइईउऊऋएओ]|अ[क-ह])", bare) and n_syl >= 3 and not bare.startswith(("अति", "अधि", "अनु", "अभि", "अपि", "अव")):
    return tuple("U" if i == 0 else "" for i in range(n_syl)), "नञ्तत्पुरुषे पूर्वपदप्रकृतिस्वरः पा॰ ६.२.२"
  if bare.startswith(("सु", "निर्", "निः", "दुर्")) and n_syl >= 3:
    return tuple("U" if i == 0 else "" for i in range(n_syl)), "बहुव्रीहौ प्रकृत्या पूर्वपदम् पा॰ ६.२.१"

  # 2. Numeric or standard nominal bahuvrīhi/tatpuruṣa prefix compounds.
  if bare.startswith(("पञ्च", "शत", "सहस्र", "एक", "द्वि", "त्रि", "चतुर्", "हिरण्य", "विश्व", "सर्व", "महा", "अश्व", "सत्य")) and n_syl >= 3:
    return tuple("U" if i == 0 else "" for i in range(n_syl)), "बहुव्रीहौ प्रकृत्या पूर्वपदम् पा॰ ६.२.१"

  # 3. `-ति` (*ktin*) stems (`हू᳓त्याम्`).
  if re.search(r"ति(?:ः|म्|ना|ये|याः|याम्|योः|षु)?$|त्याम्?$", bare) and n_syl >= 2:
    return tuple("U" if i == 0 else "" for i in range(n_syl)), "मन्त्रे वृषेषपचमनविदभूवीरा उदात्तः पा॰ ३.३.९६, ञ्णित्यादिर्नित्यम् पा॰ ६.१.१९७"

  # 4. `-अन` (*lyuṭ*: `निषे᳓चनम्`, pre-suffix syllable accented by `लिति पा॰ ६.१.१९३`).
  if re.search(r"अन(?:ः|म्|स्य|ाय|ात्|े|ेन|ेषु|ा|ाम्|ानि)?$|अण(?:ः|म्|स्य|ाय|ात्|े|ेन|ेषु|ा|ाम्)?$", bare) and n_syl >= 3:
    pre_idx = max(0, min(end_idx - 1, n_syl - 2))
    return tuple("U" if i == pre_idx else "" for i in range(n_syl)), "लिति पा॰ ६.१.१९३"

  # 5. `-अक` (*ṇvul*: `चो᳓दकस्य`, initial root syllable by `लिति पा॰ ६.१.१९३` or pre-ak).
  if re.search(r"अक(?:ः|म्|स्य|ाय|ात्|े|ेन|ेषु|ाः|ान्)?$", bare) and n_syl >= 3:
    pre_idx = max(0, min(end_idx - 1, n_syl - 2))
    return tuple("U" if i == pre_idx else "" for i in range(n_syl)), "लिति पा॰ ६.१.१९३"

  # 6. `-ताति` suffix (`तातिल् पा॰ ४.४.१४२, लिति पा॰ ६.१.१९३`).
  if "ताति" in bare and n_syl >= 3:
    pre_idx = max(0, n_syl - 3)
    return tuple("U" if i == pre_idx else "" for i in range(n_syl)), "तातिल् पा॰ ४.४.१४२, लिति पा॰ ६.१.१९३"

  # 7. Phonetic णत्व / षत्व normalization (`ण->न`, `ष->स`) for lexical syllable pattern lookup.
  norm_alt = bare.replace("ण", "न").replace("ष", "स")
  if norm_alt != bare:
    alt_hits = lex.lookup_form(norm_alt)
    if alt_hits:
      best_mks = max(alt_hits.items(), key=lambda kv: sum(kv[1].values()))[0]
      if len(best_mks) == n_syl and sum(1 for m in best_mks if m) == 1:
        return best_mks, "णत्व-षत्व-समानान्तर-धातुस्वरः, पा॰ ८.४.१४, पा॰ ६.१.१६२"

  # 8. Hyphenated compound not caught by external corpus counts -> `समासस्य पा॰ ६.१.२२३` (or 6.2.1 if initial udātta).
  if "-" in pd:
    if any(mks) and mks[0] == "U":
      return mks, "पूर्वपदप्रकृतिस्वरः पा॰ ६.२.१"
    return tuple("U" if i == end_idx else "" for i in range(n_syl)), "समासस्य पा॰ ६.१.२२३"

  # 9. Remaining OOV primary stem: Śāntanava Phiṭ Sūtra (`फिषोऽन्त उदात्तः फि॰ १.१`).
  return tuple("U" if i == end_idx else "" for i in range(n_syl)), "फिषोऽन्त उदात्तः फि॰ १.१"


def _collect_avp_parallel_padas(
  padas_bare: Sequence[str],
  vp_bare_norm: str,
  lex: UnifiedVedicLexicon,
  ref_idx: VedicReferenceIndex | None,
  *,
  clause_starts: set[int] | None = None,
  linked_vp_us: str = "",
  linked_corpus: str = "",
) -> dict[int, tuple[tuple[str, ...], str]]:
  """Collect parallel US-accented pada alignments from linked witness + AV/RV/TS/VS/MS index."""
  par_map: dict[int, tuple[tuple[str, ...], str]] = {}
  eff_starts = clause_starts or {0}

  if linked_vp_us and has_us_accents(linked_vp_us):
    for ti, val in _align_parallel_mantra_padas(padas_bare, linked_vp_us, linked_corpus or "समानान्तरम्", lex).items():
      if _is_valid_par_map_entry(_normalize_lookup_key(padas_bare[ti]), val[0], lex, is_clause_start=(ti in eff_starts)):
        par_map[ti] = val

  if ref_idx is None or len(par_map) >= len(padas_bare):
    return par_map

  whole_hit = ref_idx.find_best_parallel_mantra(
    vp_bare_norm,
    prefer_sources=AVP_PREFER_SOURCES,
    min_overlap=0.58,
  )
  if whole_hit is not None:
    u_hit, _ = whole_hit
    if has_us_accents(u_hit.vp_us):
      for ti, val in _align_parallel_mantra_padas(padas_bare, u_hit.vp_us, u_hit.source, lex).items():
        if _is_valid_par_map_entry(_normalize_lookup_key(padas_bare[ti]), val[0], lex, is_clause_start=(ti in eff_starts)):
          par_map.setdefault(ti, val)

  # Line/pāda-level parallel alignment for mixed verses that borrow individual hemistichs/pādas.
  if len(par_map) < len(padas_bare):
    clauses = [c.strip() for c in re.split(r"[।॥\n]+", vp_bare_norm) if len(c.strip().split()) >= 2]
    if len(clauses) >= 2:
      for cl in clauses:
        cl_hit = ref_idx.find_best_parallel_mantra(
          cl,
          prefer_sources=AVP_PREFER_SOURCES,
          min_overlap=0.72,
        )
        if cl_hit is not None and has_us_accents(cl_hit[0].vp_us):
          for ti, val in _align_parallel_mantra_padas(padas_bare, cl_hit[0].vp_us, cl_hit[0].source, lex).items():
            if _is_valid_par_map_entry(_normalize_lookup_key(padas_bare[ti]), val[0], lex, is_clause_start=(ti in eff_starts)):
              par_map.setdefault(ti, val)

  return par_map


def solve_avp_mantra(
  vp_raw: str,
  lex: UnifiedVedicLexicon,
  counter: VedicCorpusCounter,
  ref_idx: VedicReferenceIndex | None,
  *,
  unit_kind: str = "rk",
  vp_summary_hint: str = "",
  linked_vp_us: str = "",
  linked_corpus: str = "",
) -> SolvedAvpResult:
  """Solve (or Mode-A analyze) one Paippalāda mantra into US accents and bulleted padapāṭha."""
  eff_kind = unit_kind or _extract_unit_kind(vp_raw, vp_summary_hint)
  base_vp_hdr = "विश्वास-प्रस्तुतिः - ऋक्" if eff_kind == "rk" else "विश्वास-प्रस्तुतिः - यजुः"
  was_manual = has_us_accents(vp_raw) and "यन्त्र-स्वरः" not in vp_summary_hint
  vp_work = vp_raw.strip() if was_manual else _ALL_ACC_STRIP_RE.sub("", vp_raw).strip()
  if not was_manual:
    vp_work = re.sub(r"त्रायैते(?=\s|$|[।॥,])", "त्रायेते", vp_work)
  vp_bare_norm = _prepare_vp_for_splitting(vp_work, keep_accents=False)

  if not vp_bare_norm or not _DEVANAGARI_RE.search(vp_bare_norm):
    return SolvedAvpResult(
      vp_summary=(vp_summary_hint.strip() or base_vp_hdr),
      vp_body=vp_raw.strip(),
      pp_lines=[],
      padas_bare=[],
      padas_us=[],
      was_manual=was_manual,
      unit_kind=eff_kind,
      sandhi_ok=True,
      sandhi_detail="",
    )

  padas_bare, clause_ids = split_vp_to_padas_with_clauses(vp_bare_norm, lex)
  expanded_bare: list[str] = []
  expanded_cids: list[int] = []
  for pd, cid in zip(padas_bare, clause_ids):
    if "ऽ" in pd and not pd.startswith("ऽ"):
      sub = _split_chunk_with_avagraha_and_hints(pd, lex)
      expanded_bare.extend(sub)
      expanded_cids.extend([cid] * len(sub))
    else:
      expanded_bare.append(pd)
      expanded_cids.append(cid)
  padas_bare, clause_ids = _postprocess_avp_padas(expanded_bare, expanded_cids, vp_bare_norm, lex)

  if not padas_bare:
    return SolvedAvpResult(
      vp_summary=(vp_summary_hint.strip() or base_vp_hdr),
      vp_body=vp_raw.strip(),
      pp_lines=[],
      padas_bare=[],
      padas_us=[],
      was_manual=was_manual,
      unit_kind=eff_kind,
      sandhi_ok=True,
      sandhi_detail="",
    )

  clause_starts = {0} | {i for i in range(1, len(clause_ids)) if clause_ids[i] != clause_ids[i - 1]}
  ctxs = _detect_clause_contexts(padas_bare, vp_bare_norm, lex, clause_ids=clause_ids)

  if was_manual:
    vp_norm_acc = _prepare_vp_for_splitting(vp_work, keep_accents=True)
    pada_marks, _ = _project_us_marks_onto_padas(
      padas_bare, vp_norm_acc, set(), lex, clause_starts=clause_starts
    )
    padas_us = [_fast_apply_us_marks(pd, mks) for pd, mks in zip(padas_bare, pada_marks)]
    pp_lines = []
    for i, (pd, us_w, mks) in enumerate(zip(padas_bare, padas_us, pada_marks)):
      nxt = padas_bare[i + 1] if i + 1 < len(padas_bare) else ""
      prev_k = _normalize_lookup_key(padas_bare[i - 1]) if i > 0 else ""
      r_hint = (
        "तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८"
        if not any(mks) and prev_k == "मा" and _normalize_lookup_key(pd) == "यवम्"
        else ""
      )
      prov = _build_provenance_for_pada(
        us_w, pd, mks, ctxs[i], nxt, lex, counter, AVP_PROVENANCE_CORPORA, rule_hint=r_hint, from_mula=True
      )
      _mks_r, prov_r = _refine_avp_oov_marks_and_prov(pd, mks, prov, lex)
      # Preserve manual VP verbatim; use refined provenance rule in PP cleanly when needed.
      if "अनाम्नातम्" not in prov_r and "मूल-पाठः" not in prov_r:
        prov = prov_r
      pp_lines.append(f"- {us_w} ({normalize_panini_abbreviations(prov)})")
    # Keep manual accents intact and keep non-yantra-svara header.
    vp_summary = re.sub(r"\s*\(यन्त्र-स्वरः\)", "", (vp_summary_hint or base_vp_hdr)).strip() or base_vp_hdr
    vp_final = vp_raw.strip()
    par_count = 0
  else:
    par_map = _collect_avp_parallel_padas(
      padas_bare,
      vp_bare_norm,
      lex,
      ref_idx,
      clause_starts=clause_starts,
      linked_vp_us=linked_vp_us,
      linked_corpus=linked_corpus,
    )
    # Force prohibitive `मा ... हिंसीः` anudātta (`पा॰ ८.१.२८`) in clause.
    ma_clauses = {clause_ids[j] for j, p in enumerate(padas_bare) if _normalize_lookup_key(p) == "मा"}
    for j, pd in enumerate(padas_bare):
      if clause_ids[j] in ma_clauses and _normalize_lookup_key(pd) in ("हिंसीः", "रिषः", "रिषत्"):
        par_map[j] = (tuple("" for _ in range(_fast_syllable_count(pd))), "तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८")

    par_count = len(par_map)
    solved = _solve_unaccented_padas_viterbi(
      padas_bare,
      ctxs,
      lex,
      counter,
      AVP_PROVENANCE_CORPORA,
      parallel_pada_map=par_map,
      sister_corpus="AV",
    )
    solved_marks: list[tuple[str, ...]] = []
    pp_lines = []
    padas_us = []
    for i, (pd, (mks, rule_h)) in enumerate(zip(padas_bare, solved)):
      nxt = padas_bare[i + 1] if i + 1 < len(padas_bare) else ""
      bare_i = _normalize_lookup_key(pd)
      if bare_i == "न" and not any(mks):
        mks = ("U",)
        rule_h = ""
      us_w = _fast_apply_us_marks(pd, mks)
      prov = _build_provenance_for_pada(
        us_w, pd, mks, ctxs[i], nxt, lex, counter, AVP_PROVENANCE_CORPORA, rule_hint=rule_h, from_mula=False
      )
      mks_r, prov_r = _refine_avp_oov_marks_and_prov(pd, mks, prov, lex)
      if mks_r != mks:
        mks = mks_r
        us_w = _fast_apply_us_marks(pd, mks)
        prov = _build_provenance_for_pada(
          us_w, pd, mks, ctxs[i], nxt, lex, counter, AVP_PROVENANCE_CORPORA, rule_hint=prov_r, from_mula=False
        )
      else:
        prov = prov_r
      solved_marks.append(mks)
      padas_us.append(us_w)
      pp_lines.append(f"- {us_w} ({normalize_panini_abbreviations(prov)})")

    vp_final = _project_solved_accents_to_vp(vp_work, padas_bare, solved_marks)
    vp_summary = format_filled_vp_summary(base_vp_hdr, 0, len(padas_bare), mula_has_accents=False)
    # Apply sandhi/abhinihita/ekādeśa/yan svarita rules unconditionally on every non-manual block for reconciler parity.
    tmp_md = (
      f"<details open><summary>{vp_summary}</summary>\n\n{vp_final}\n</details>\n\n"
      f"<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\n" + "\n".join(pp_lines) + "\n</details>\n"
    )
    rec_md, rec_logs = accent_reconciler.reconcile_markdown_blocks(tmp_md)
    if rec_logs and rec_md != tmp_md:
      chunks = cascade._split_top_level_chunks(rec_md)
      for ck, d in chunks:
        if ck == "details":
          vp_final = d[1].strip()  # type: ignore[index]
          break

  s_res = verify_mantra_sandhi(padas_bare, vp_bare_norm)
  return SolvedAvpResult(
    vp_summary=vp_summary,
    vp_body=vp_final,
    pp_lines=pp_lines,
    padas_bare=padas_bare,
    padas_us=padas_us,
    was_manual=was_manual,
    unit_kind=eff_kind,
    sandhi_ok=bool(s_res[0]),
    sandhi_detail="" if s_res[0] else repr(s_res[1:]),
    par_aligned_padas=par_count,
  )


def _upsert_local_padapatha(tika_items: Sequence[tuple[str, str]], pp_markdown: str) -> list[tuple[str, str]]:
  """Insert or replace ``पद-पाठः (यान्त्रिकः)`` cleanly right after ``मूलम्*`` inside local ṭīkās."""
  filtered = [(t, b) for t, b in tika_items if t.strip() != "पद-पाठः (यान्त्रिकः)"]
  new_entry = ("पद-पाठः (यान्त्रिकः)", pp_markdown.strip())
  insert_idx = 0
  for idx, (t, _) in enumerate(filtered):
    if t.strip().startswith("मूलम्"):
      insert_idx = idx + 1
  return [*filtered[:insert_idx], new_entry, *filtered[insert_idx:]]


def _extract_us_mantra_from_sarva_file(sarva_fp: pathlib.Path, vp_dir_hint: pathlib.Path | None = None) -> str:
  """Extract clean US-accented mantra text from an upstream ``sarvASh_TIkAH/`` target (or sibling VP)."""
  if vp_dir_hint is not None:
    # Direct sibling check when standard /sarvASh_TIkAH/ -> /vishvAsa-prastutiH/
    s_str = sarva_fp.as_posix()
    if "/sarvASh_TIkAH/" in s_str:
      vp_sib = pathlib.Path(s_str.replace("/sarvASh_TIkAH/", "/vishvAsa-prastutiH/", 1))
      if vp_sib.is_file():
        _, vp_b = split_frontmatter_verbatim(vp_sib.read_text(encoding="utf-8"))
        vp_c = clean_vedic_text(vp_b, keep_us_accents=True)
        if has_us_accents(vp_c):
          return vp_c
  if not sarva_fp.is_file():
    return ""
  txt = sarva_fp.read_text(encoding="utf-8", errors="ignore")
  _, body = split_frontmatter_verbatim(txt)
  leaves: list[tuple[str, str]] = []
  def _walk(s: str) -> None:
    for ck, d in cascade._split_top_level_chunks(s):
      if ck != "details":
        continue
      hdr_s, blk_body = d[0], d[1]  # type: ignore[index]
      if "<details" in blk_body:
        _walk(blk_body)
      else:
        leaves.append((hdr_s.strip(), blk_body))
  _walk(body)
  # Priority order: VP -> Thomson & Solcum -> मूलम् (classical/US)
  for prefix in ("विश्वास-प्रस्तुतिः", "Thomson & Solcum", "मूलम्"):
    for hdr, b in leaves:
      if hdr.startswith(prefix) and "पैप्पलाद" not in hdr and "(GR)" not in hdr:
        us = _clean_vp_to_us(b if prefix != "मूलम्" else "", b if prefix == "मूलम्" else "")
        if has_us_accents(us):
          return us
  return ""


def _resolve_upstream_target(
  sarva_url: str,
  specs: dict[str, VedaCorpusSpec],
  hugo_base_dir: pathlib.Path,
  caller_fp: pathlib.Path,
  cache: dict[str, tuple[VedaCorpusSpec | None, pathlib.Path | None, str]],
) -> tuple[VedaCorpusSpec | None, pathlib.Path | None, str]:
  if sarva_url in cache:
    return cache[sarva_url]
  resolved_path = include_seeker.resolve_hugo_include_file_path(
    url=sarva_url,
    hugo_base_dir=str(hugo_base_dir),
    current_file_path=str(caller_fp),
  )
  sarva_fp = pathlib.Path(resolved_path) if resolved_path else None
  tgt_spec = _resolve_corpus_spec_for_ref(sarva_url, specs) or (
    _resolve_corpus_spec_for_ref(str(sarva_fp), specs) if sarva_fp else None
  )
  vp_us = _extract_us_mantra_from_sarva_file(sarva_fp, tgt_spec.vp_dir if tgt_spec else None) if sarva_fp else ""
  val = (tgt_spec, sarva_fp, vp_us)
  cache[sarva_url] = val
  return val


def _update_static_caller_titles(
  caller_files: Sequence[pathlib.Path],
  static_vp_url: str,
  new_title: str,
  *,
  dry_run: bool,
) -> list[str]:
  touched: list[str] = []
  for fp in caller_files:
    if not fp.is_file():
      continue
    txt = fp.read_text(encoding="utf-8")
    divs = transformer.find_js_include_divs(txt)
    edits: list[tuple[int, int, str]] = []
    for s_open, e_open, _, _, _, open_tag in divs:
      if static_vp_url not in open_tag or 'includetitle="false"' in open_tag.lower():
        continue
      new_tag, n = _TITLE_ATTR_RE.subn(rf'\g<1>\2{new_title}\2', open_tag, count=1)
      if n and new_tag != open_tag:
        edits.append((s_open, e_open, new_tag))
    if edits:
      edits.sort(key=lambda x: x[0], reverse=True)
      out = txt
      for s_o, e_o, rep in edits:
        out = out[:s_o] + rep + out[e_o:]
      if not dry_run:
        fp.write_text(out, encoding="utf-8")
      touched.append(str(fp))
  return touched


def run_paippalada_padapatha_and_accent(
  *,
  hugo_base_dir: pathlib.Path = DEFAULT_HUGO_BASE,
  specs: dict[str, VedaCorpusSpec] | None = None,
  caller_roots: Sequence[pathlib.Path] | None = None,
  lex: UnifiedVedicLexicon | None = None,
  counter: VedicCorpusCounter | None = None,
  ref_idx: VedicReferenceIndex | None = None,
  kanda_filter: Sequence[str] | None = None,
  file_paths: Sequence[pathlib.Path] | None = None,
  max_files: int | None = None,
  dry_run: bool = False,
) -> dict:
  """Accent remaining Paippalāda mantras and add ``पद-पाठः (यान्त्रिकः)`` across content & static files."""
  loaded_specs = specs if specs is not None else load_corpus_specs()
  avp_spec = loaded_specs["AV-P"]
  roots = list(caller_roots) if caller_roots is not None else _build_paippalada_caller_roots(hugo_base_dir, loaded_specs)
  lex_obj = lex if lex is not None else UnifiedVedicLexicon.load_or_build(include_sb_m=True)
  cnt_obj = counter if counter is not None else VedicCorpusCounter.load_or_build()
  if ref_idx is None:
    ref_obj = VedicReferenceIndex.load_or_build()
    ref_obj.add_av_mantras()
  else:
    ref_obj = ref_idx

  stats: dict = {
    "files_scanned": 0,
    "files_updated": 0,
    "skipped_exact_upstream": 0,
    "static_manual_processed": 0,
    "static_accented": 0,
    "content_local_manual": 0,
    "content_local_accented": 0,
    "content_variant_accented": 0,
    "upstream_sarva_merged": 0,
    "sandhi_failures": 0,
    "total_padas": 0,
    "par_aligned_padas": 0,
    "sandhi_failure_samples": [],
    "sample_outputs": [],
  }

  upstream_cache: dict[str, tuple[VedaCorpusSpec | None, pathlib.Path | None, str]] = {}
  # upstream sarva_fp -> [(target_spec, host_fp, pp_markdown), ...]
  upstream_additions: dict[pathlib.Path, tuple[VedaCorpusSpec, list[tuple[pathlib.Path, str]]]] = {}
  changed_static_or_upstream: list[str] = []
  changed_content: list[str] = []

  # Map AV-P static vp_url -> companion sarva_include_url seen inside content_dir (handles 19/024/12 merged to RV).
  static_vp_to_sarva_url: dict[str, list[tuple[pathlib.Path, str]]] = defaultdict(list)

  content_files = cascade._iter_md_files(avp_spec.content_dir)
  if file_paths is not None:
    target_set = {pathlib.Path(p).resolve() for p in file_paths}
    content_files = [fp for fp in content_files if fp.resolve() in target_set]
  elif kanda_filter:
    kset = {k.zfill(2) for k in kanda_filter}
    content_files = [
      fp for fp in content_files
      if avp_spec.content_dir and fp.relative_to(avp_spec.content_dir).parts[0] in kset
    ]
  if max_files is not None:
    content_files = content_files[:max_files]

  # 1. Scan & process inline / upstream-variant groups in sarva-prastutiH/.
  for c_fp in content_files:
    stats["files_scanned"] += 1
    if stats["files_scanned"] % 100 == 0:
      logger.info(
        "AV-P progress: %d/%d files (local=%d, var=%d, sandhi_fail=%d)",
        stats["files_scanned"], len(content_files),
        stats["content_local_accented"], stats["content_variant_accented"], stats["sandhi_failures"],
      )
    raw = c_fp.read_text(encoding="utf-8")
    fm, body = split_frontmatter_verbatim(raw)
    tokens = tokenize_markdown_body(body)
    groups = group_mantra_units(tokens)
    edited = False

    for grp in groups:
      if grp.is_vp_include:
        if grp.vp_include_url and "/paippalAdam/" in grp.vp_include_url and grp.sarva_include_url:
          static_vp_to_sarva_url[grp.vp_include_url].append((c_fp, grp.sarva_include_url))
        else:
          stats["skipped_exact_upstream"] += 1
        continue

      vp_raw = grp.vp_text.strip()
      if not vp_raw:
        continue

      u_kind = _extract_unit_kind(vp_raw, grp.vp_summary)

      if grp.sarva_include_url and "/paippalAdam/" not in grp.sarva_include_url:
        # Upstream variant: align first against linked upstream mantra, update local VP, merge PP to upstream sarva!
        tgt_spec, up_sarva_fp, linked_vp_us = _resolve_upstream_target(
          grp.sarva_include_url, loaded_specs, hugo_base_dir, c_fp, upstream_cache
        )
        res = solve_avp_mantra(
          vp_raw,
          lex_obj,
          cnt_obj,
          ref_obj,
          unit_kind=u_kind,
          vp_summary_hint=grp.vp_summary,
          linked_vp_us=linked_vp_us,
          linked_corpus=(tgt_spec.name if tgt_spec else ""),
        )
        stats["total_padas"] += len(res.padas_bare)
        stats["par_aligned_padas"] += res.par_aligned_padas
        if not res.sandhi_ok:
          stats["sandhi_failures"] += 1
          if len(stats["sandhi_failure_samples"]) < 15:
            stats["sandhi_failure_samples"].append((c_fp.name, res.padas_bare, res.sandhi_detail))

        if res.was_manual:
          stats["content_local_manual"] += 1
        else:
          stats["content_variant_accented"] += 1
          new_vp_blk = format_details_block(res.vp_summary, res.vp_body, is_open=True)
          replace_group_tokens(tokens, grp, new_vp_raw=new_vp_blk)
          edited = True

        if res.pp_lines and tgt_spec is not None and up_sarva_fp is not None and up_sarva_fp.is_file():
          existing_entry = upstream_additions.get(up_sarva_fp)
          if existing_entry is None:
            upstream_additions[up_sarva_fp] = (tgt_spec, [(c_fp, res.pp_markdown)])
          else:
            existing_entry[1].append((c_fp, res.pp_markdown))
      else:
        # Local mantra (either unaccented or manually US-accented)
        res = solve_avp_mantra(
          vp_raw,
          lex_obj,
          cnt_obj,
          ref_obj,
          unit_kind=u_kind,
          vp_summary_hint=grp.vp_summary,
        )
        stats["total_padas"] += len(res.padas_bare)
        stats["par_aligned_padas"] += res.par_aligned_padas
        if not res.sandhi_ok:
          stats["sandhi_failures"] += 1
          if len(stats["sandhi_failure_samples"]) < 15:
            stats["sandhi_failure_samples"].append((c_fp.name, res.padas_bare, res.sandhi_detail))

        if res.was_manual:
          stats["content_local_manual"] += 1
          new_vp_blk = None
        else:
          stats["content_local_accented"] += 1
          new_vp_blk = format_details_block(res.vp_summary, res.vp_body, is_open=True) if res.pp_lines else None

        if res.pp_lines:
          updated_tikas = _upsert_local_padapatha(grp.inline_tika_items, res.pp_markdown)
          sarva_inner = "\n\n".join(format_details_block(t, b) for t, b in updated_tikas)
          new_sv_blk = format_details_block("सर्वाष् टीकाः", sarva_inner, is_open=False)
          replace_group_tokens(tokens, grp, new_vp_raw=new_vp_blk, new_sarva_stub=new_sv_blk)
          edited = True

        if len(stats["sample_outputs"]) < 10 and not res.was_manual and res.pp_lines:
          stats["sample_outputs"].append((c_fp.name, res.vp_body, res.pp_lines[:4]))

    if edited:
      rendered = render_tokens(fm, tokens)
      if not cascade._balanced_tags(rendered):
        raise ValueError(f"Unbalanced tags after padapatha/accenting in {c_fp}")
      stats["files_updated"] += 1
      changed_content.append(str(c_fp))
      if not dry_run:
        c_fp.write_text(rendered, encoding="utf-8")

  # 2. Process static 2-part AV-P mantras (full run or explicitly requested static files).
  static_target_rels: set[str] | None = None
  if file_paths is not None:
    static_target_rels = set()
    for p in file_paths:
      ps = str(pathlib.Path(p).resolve()).replace("\\", "/")
      if "/paippalAdam/saMhitA/" in ps and ("/sarvASh_TIkAH/" in ps or "/vishvAsa-prastutiH/" in ps):
        static_target_rels.add(ps.split("/sarvASh_TIkAH/", 1)[-1].split("/vishvAsa-prastutiH/", 1)[-1])
    if not static_target_rels:
      static_target_rels = set()

  if max_files is None and (static_target_rels is None or static_target_rels):
    avp_all_files = cascade._iter_md_files(avp_spec.content_dir) if (kanda_filter or file_paths is not None) else content_files
    # Detect which static AV-P URLs currently use `(यन्त्र-स्वरः)` titles so re-runs stay idempotent.
    static_yantra_urls: set[str] = set()
    for cf in avp_all_files:
      txt_c = cf.read_text(encoding="utf-8", errors="ignore")
      for m_tag in re.finditer(r'<div\b[^>]*\bclass=["\'][^"\']*\bjs_include\b[^>]*>', txt_c):
        tg = m_tag.group(0)
        if "यन्त्र-स्वरः" in tg:
          m_u = re.search(r'\burl=(["\'])([^"\']+)\1', tg)
          if m_u:
            static_yantra_urls.add(m_u.group(2))

    for tree_kind, vp_dir, sarva_dir, vp_pref, sarva_pref in cascade._iter_two_part_trees(avp_spec):
      u_kind = "rk" if tree_kind == "rk_2part" else "yajuh"
      for vp_fp in cascade._iter_md_files(vp_dir):
        assert vp_dir is not None and sarva_dir is not None
        rel = vp_fp.relative_to(vp_dir).as_posix()
        if static_target_rels is not None and rel not in static_target_rels:
          continue
        if kanda_filter and rel.split("/")[0] not in {k.zfill(2) for k in kanda_filter}:
          continue
        vp_fm, vp_body = split_frontmatter_verbatim(vp_fp.read_text(encoding="utf-8"))
        vp_raw = vp_body.strip()
        if not vp_raw or "js_include" in vp_raw:
          continue

        vp_url = f"{vp_pref}/{rel}"
        sv_fp = sarva_dir / rel
        # Find any external upstream sarva link if sibling sarva_fp was deduped (e.g. 19/024/12 -> RV)
        linked_vp_us = ""
        linked_corpus = ""
        ext_sarva_target: tuple[VedaCorpusSpec, pathlib.Path] | None = None
        if not sv_fp.is_file():
          for ref_caller, ref_sv_url in static_vp_to_sarva_url.get(vp_url, []):
            if "/paippalAdam/" not in ref_sv_url:
              tgt_spec, up_sv_fp, up_vp_us = _resolve_upstream_target(
                ref_sv_url, loaded_specs, hugo_base_dir, ref_caller, upstream_cache
              )
              if tgt_spec and up_sv_fp and up_sv_fp.is_file():
                ext_sarva_target = (tgt_spec, up_sv_fp)
                linked_vp_us = up_vp_us
                linked_corpus = tgt_spec.name
                break

        res = solve_avp_mantra(
          vp_raw,
          lex_obj,
          cnt_obj,
          ref_obj,
          unit_kind=u_kind,
          vp_summary_hint=("विश्वास-प्रस्तुतिः - " + ("ऋक्" if u_kind == "rk" else "यजुः") + " (यन्त्र-स्वरः)") if vp_url in static_yantra_urls else "",
          linked_vp_us=linked_vp_us,
          linked_corpus=linked_corpus,
        )
        stats["total_padas"] += len(res.padas_bare)
        stats["par_aligned_padas"] += res.par_aligned_padas
        if not res.sandhi_ok:
          stats["sandhi_failures"] += 1

        if res.was_manual:
          stats["static_manual_processed"] += 1
        else:
          stats["static_accented"] += 1
          if not dry_run:
            vp_fp.write_text((vp_fm.rstrip() + "\n\n" if vp_fm else "") + res.vp_body + "\n", encoding="utf-8")
          changed_static_or_upstream.append(str(vp_fp))
          _update_static_caller_titles(avp_all_files, vp_url, res.vp_summary, dry_run=dry_run)

        if res.pp_lines:
          if sv_fp.is_file():
            sv_fm, sv_body = split_frontmatter_verbatim(sv_fp.read_text(encoding="utf-8"))
            sv_items = [
              (d[0], d[1]) for ck, d in cascade._split_top_level_chunks(sv_body) if ck == "details"  # type: ignore[index]
            ]
            new_sv_items = _upsert_local_padapatha(sv_items, res.pp_markdown)
            new_sv_txt = (sv_fm.rstrip() + "\n\n" if sv_fm else "") + "\n\n".join(
              format_details_block(t, b) for t, b in new_sv_items
            ) + "\n"
            if not cascade._balanced_tags(new_sv_txt):
              raise ValueError(f"Unbalanced tags in static AV-P sarva {sv_fp}")
            if not dry_run:
              sv_fp.write_text(new_sv_txt, encoding="utf-8")
            changed_static_or_upstream.append(str(sv_fp))
          elif ext_sarva_target is not None:
            tgt_spec, up_sv_fp = ext_sarva_target
            existing_entry = upstream_additions.get(up_sv_fp)
            if existing_entry is None:
              upstream_additions[up_sv_fp] = (tgt_spec, [(vp_fp, res.pp_markdown)])
            else:
              existing_entry[1].append((vp_fp, res.pp_markdown))

  # 3. Merge collected Paippalāda padapāṭhas into shared upstream sarvASh_TIkAH/ files.
  avp_pp_old_re = re.compile(
    r"\n*<details>\s*<summary>पद-पाठः \(यान्त्रिकः - पैप्पलादम्\)</summary>.*?</details>\s*",
    re.DOTALL,
  )
  for up_sv_fp, (tgt_spec, entries) in sorted(upstream_additions.items()):
    if not up_sv_fp.is_file():
      continue
    old_t = up_sv_fp.read_text(encoding="utf-8")
    old_cleaned = avp_pp_old_re.sub("\n\n", old_t)
    additions = [
      (avp_spec, False, [("पद-पाठः (यान्त्रिकः - पैप्पलादम्)", pp_md)], str(src_fp))
      for src_fp, pp_md in entries[:1]  # one Paippalāda padapāṭha per shared target slot
    ]
    new_t = merge_tika_additions(old_cleaned, tgt_spec, additions, hugo_base_dir=str(hugo_base_dir))
    if new_t != old_t:
      if not cascade._balanced_tags(new_t):
        raise ValueError(f"Unbalanced tags merging AV-P padapatha into {up_sv_fp}")
      stats["upstream_sarva_merged"] += 1
      if not dry_run:
        up_sv_fp.write_text(new_t, encoding="utf-8")
      changed_static_or_upstream.append(str(up_sv_fp))

  # 4. Transitive js_include prefill propagation for modified static AV-P & upstream sarvASh_TIkAH/.
  if changed_static_or_upstream and not dry_run:
    transformer.surgical_prefill_transitive(
      roots,
      changed_static_or_upstream,
      hugo_base_dir=str(hugo_base_dir),
      skip_sources_with_empty_includes=False,
      only_if_prefilled=True,
      dry_run=dry_run,
    )

  return stats


def main(argv: Sequence[str] | None = None) -> int:
  import argparse
  import json

  parser = argparse.ArgumentParser(description="Accent remaining Paippalāda mantras and add padapāṭha.")
  parser.add_argument("--kandas", nargs="*", default=None, help="Optional kāṇḍa numbers (e.g. 01 19)")
  parser.add_argument("--dry-run", action="store_true")
  args = parser.parse_args(argv)
  logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
  res = run_paippalada_padapatha_and_accent(kanda_filter=args.kandas, dry_run=args.dry_run)
  print(json.dumps(res, ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
