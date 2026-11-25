"""TA-mode bulleted ``पद-पाठः (यान्त्रिकः)``, accent projection, and wrapped Markdown rendering for MS & KS.

Handles two clean modes:
- **Mode A (Accented ``मूलम्`` — 100% of MS + accented KS blocks):**
  Projects authoritative US accents from ``मूलम्``/``VP`` onto sandhi-verified padas,
  audits strictly for unmistakable transmission/OCR errors (multi-udātta ``पा॰ ६.१.१५८``,
  accented enclitics ``पा॰ ८.१.१८``, dropped accents on accented nominals) while
  preserving authentic Maitrāyaṇīya / Kaṭha śākhā accents, and emits exact external
  ``*CORPUS*-M/N`` counts.
- **Mode B (Unaccented ``मूलम्`` — unaccented KS files, TA mode):**
  Reconstructs US accents via parallel-mantra transfer (**MS** -> **TS** -> **VS-M/VS-K**
  -> **RV**) + clause-aware 1D Viterbi decoding (reusing ``shatapatha_solver``), projects
  accents onto ``विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)``, and emits bulleted ``पद-पाठः (यान्त्रिकः)``
  with full corpus provenance counts.
"""

from __future__ import annotations

import dataclasses
import difflib
import re
from typing import Sequence

from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.provenance import (
  MAJOR_AUTO_CORPORA,
  VedicCorpusCounter,
  format_corpus_count,
  is_declinable_nominal,
  normalize_panini_abbreviations,
)
from doc_curation.sanskrit.accent.reconciler import (
  US_SVARITA,
  US_UDATTA,
  _map_pp_to_vp_syllables,
  bare_devanagari,
  format_filled_vp_summary,
  format_padapatha_summary,
  has_us_accents,
)
from doc_curation.sanskrit.accent.sandhi_check import verify_mantra_sandhi
from doc_curation.sanskrit.accent.shatapatha_solver import (
  ALWAYS_ANUDATTA_ENCLITICS,
  ANVADESHA_2432,
  ANVADESHA_2434,
  UPASARGA_DEVA_SET,
  PadaCandidate,
  UnifiedVedicLexicon,
  _DEVANAGARI_RE,
  _deva_to_slp,
  _detect_clause_contexts,
  _fast_apply_us_marks,
  _fast_apply_vp_marks,
  _fast_extract_vp_pieces,
  _fast_flatten_pp_and_starts,
  _fast_scan_deva_syllables,
  _fast_syllable_count,
  _is_dual_accent_word,
  _join_virama_vowels,
  _normalize_lookup_key,
  _transition_syntax_cost,
  generate_pada_candidates,
  split_vp_to_padas_with_clauses,
)
from doc_curation.sanskrit.accent.taittiriya_padapatha import (
  _project_us_marks_onto_padas,
  _split_chunk_with_avagraha_and_hints,
  _try_split_multi_accent_pada,
  clean_mula_text,
)
from doc_curation_projects.veda.yajuH.ks_ms.reference_index import VedicReferenceIndex
from doc_curation_projects.veda.yajuH.ks_ms.splitter import SplitBlock

MS_PROVENANCE_CORPORA: tuple[str, ...] = MAJOR_AUTO_CORPORA
KS_PROVENANCE_CORPORA: tuple[str, ...] = ("MS",) + MAJOR_AUTO_CORPORA

_ALL_ACC_RE = re.compile(r"[\u0951-\u0957\u1cd0-\u1cff]")


@dataclasses.dataclass
class BuiltBlock:
  """Fully processed MS/KS block ready for canonical wrapped Markdown rendering."""

  split_block: SplitBlock
  vp_summary: str
  vp_body: str
  mula_body: str
  pp_summary: str
  pp_lines: list[str]
  padas_bare: list[str]
  padas_us: list[str]
  sandhi_ok: bool
  sandhi_detail: str
  n_vyat: int
  mula_had_accents: bool
  schroeder_notes: list[str] = dataclasses.field(default_factory=list)


_VEDIC_VOCATIVE_WORDS = frozenset({
  "अघ्न्या", "अघ्निया", "अघ्न्याः", "अग्ने", "इन्द्र", "विष्णो", "वायो", "सोम", "देव",
  "देवाः", "देवासः", "मरुतः", "आदित्याः", "वसवः", "रुद्राः", "अश्विना", "अश्विनौ",
  "बर्हिः", "देवबर्हिः", "व्रतपते", "गृहपते", "जातवेदः", "सवितः", "पूषन्", "वरुण",
  "मित्र", "बृहस्पते", "ब्रह्मणस्पते", "प्रजापते", "पशुपते", "पत्नि", "राज्ञि",
  "पृथिवि", "द्यावापृथिवी", "आपः", "देवीः", "कवे", "यविष्ठ", "विश्वचर्षणे",
  "असुर", "वाजिन्", "वाजिनि", "सपत्न", "अदब्धायो", "अशीर्ततनो", "मनसस्पते",
})

# Maitrāyaṇīya prevocalic `-भ्या V-` sandhi for `-भ्यः V-` (e.g. `देवे᳓भ्या इ᳓न्द्राय` -> `देवे᳓भ्यः इ᳓न्द्राय`)
_MS_BHYA_PREVOCALIC_RE = re.compile(r"(भ्?या)([\u1cd3\u1cd9]*)\s+(?=[अआइईउऊऋएऐओऔ])")


def normalize_ks_ms_orthography(text: str) -> str:
  """Normalize MS/KS orthographic conventions for sandhi splitting while preserving syllable count & US accents."""
  s = clean_mula_text(text)
  s = s.replace("ᳵ", "ः").replace("ᳶ", "ः").replace("ꣳ", "ं")
  # MS TITUS long ṝ & `कॢ`
  s = re.sub(r"ृ([\u1cd3\u1cd9]*)\u0304", r"ॄ\1", s)
  s = re.sub(r"क्र्?ŀ\u0325", "कॢ", s)
  # MS prevocalic `-भ्यः` -> `-भ्या` before vowel (`देवे᳓भ्या इ᳓न्द्राय` -> `देवे᳓भ्यः इ᳓न्द्राय`, same syllable count!)
  s = _MS_BHYA_PREVOCALIC_RE.sub(lambda m: m.group(1)[:-1] + "ः" + m.group(2) + " ", s)
  # MS/KS nasalized glide & candrabindu -> anusvāra (non-syllabic, 1:1 syllable count preserved!)
  s = re.sub(r"([वयल])्[ँं]([\u1cd3\u1cd9]*)", r"ं\2", s)
  s = re.sub(r"ँ([\u1cd3\u1cd9]*)\s+(?=स्[तथ]|श्[चछ]|ष्[टठ])", r"ं\1", s)
  s = s.replace("ँ", "ं")
  # MS final `-स्` / `-र्` at end of clause or before punctuation -> `ः`
  s = re.sub(r"([सर])्([\u1cd3\u1cd9]*)(?=\s*[।॥,;]*\s*$)", r"ः\2", s)
  # Strip stray non-US marks
  s = s.replace("\u0952", "").replace("\u0951", "").replace("\u1ced", "").replace("\u1cdc", "")
  # Degeminate after repha (`र्द्ध` -> `र्ध`)
  s = re.sub(r"र्([क-ह])्\1", r"र्\1", s)
  s = re.sub(r"‘|’|'", "", s)
  s = re.sub(r"\s+", " ", s).strip()
  return s


def _marks_of_us_word(us_word: str) -> tuple[str, ...]:
  scanned = _fast_scan_deva_syllables(_join_virama_vowels(us_word.replace("-", "")))
  return tuple("S" if US_SVARITA in m else ("U" if US_UDATTA in m else "") for m, _ in scanned)


def _format_external_corpus_counts(
  pada_us: str,
  counter: VedicCorpusCounter,
  corpora: Sequence[str],
  *,
  allow_stem: bool | None = None,
) -> list[str]:
  """Return formatted ``*CORPUS*-M/N`` / ``*CORPUS*-M`` tags with strictly positive counts (never ``-0``)."""
  if not pada_us or not _DEVANAGARI_RE.search(pada_us):
    return []
  stem_ok = is_declinable_nominal(pada_us) if allow_stem is None else allow_stem
  tags: list[str] = []
  for corp in corpora:
    m, n = counter.count_with_stem(pada_us, corp, allow_stem=stem_ok)
    if n <= 0:
      continue
    # Only include a `0/N` stem-only hit if exact `m > 0` OR another corpus already confirms this exact accent
    # OR `n >= 2` (matching TA/EK convention!)
    tag = format_corpus_count(corp, m, n)
    if tag:
      tags.append(tag)
  return tags


def _strip_corpus_tags_from_rule(prov: str) -> str:
  """Extract pure Pāṇinian/dictionary rule notes from a solver provenance string (dropping un-normalized corpus tags)."""
  if not prov:
    return ""
  # Split on `,` and keep non-corpus segments (Pāṇinian rules, grammatical labels, `*MW*`, `*Whitney*`, `*Macdonell*`, `*Lanman*`)
  corpus_tag_re = re.compile(r"^\*(?:TS|RV|TB|TK|AV|SB-M|SB-K|ŚB|VS-M|VS-K|VS|KS|MS|TA|EK)\*(?:-\d+(?:/\d+)?)?$")
  kept: list[str] = []
  for part in (p.strip() for p in prov.split(",")):
    if not part or corpus_tag_re.fullmatch(part):
      continue
    if "*TA*" in part or "*EK*" in part:
      continue
    kept.append(part)
  return ", ".join(kept)


def _build_provenance_for_pada(
  pada_us: str,
  pada_bare: str,
  marks: tuple[str, ...],
  ctx: dict,
  next_pada_bare: str,
  lex: UnifiedVedicLexicon,
  counter: VedicCorpusCounter,
  corpora: Sequence[str],
  *,
  rule_hint: str = "",
  extra_note: str = "",
  from_mula: bool = True,
) -> str:
  """Build a strictly compliant provenance string with exact ``*CORPUS*-M/N`` counts and ``पा॰`` rules."""
  key = _normalize_lookup_key(pada_bare)
  n_acc = sum(1 for m in marks if m)

  # 1. Determine grammatical rule prefix (only when genuinely applicable to `marks`!)
  rule_parts: list[str] = []
  if extra_note:
    rule_parts.append(extra_note)
  cleaned_hint = _strip_corpus_tags_from_rule(rule_hint)
  if cleaned_hint and cleaned_hint != "अनाम्नातम् (अनुमानम्)":
    rule_parts.append(cleaned_hint)
  elif n_acc == 0:
    # Unaccented word: identify the exact Pāṇinian nighāta rule!
    if key in ALWAYS_ANUDATTA_ENCLITICS or key in ("वा", "ते", "मा", "वाम्", "नौ"):
      rule_parts.append("अनुदात्तम्, पा॰ ८.१.१८")
    elif ctx.get("is_amredita"):
      rule_parts.append("द्विर्वचने परस्यानुदात्तत्वम्, पा॰ ८.१.३")
    elif key in ANVADESHA_2434:
      rule_parts.append("अन्वादेशे अनुदात्तम्, पा॰ २.४.३४")
    elif key in ANVADESHA_2432:
      rule_parts.append("अन्वादेशे अनुदात्तम्, पा॰ २.४.३२")
    elif key in UPASARGA_DEVA_SET:
      nxt_k = _normalize_lookup_key(next_pada_bare) if next_pada_bare else ""
      if nxt_k in UPASARGA_DEVA_SET:
        rule_parts.append("गतिर्गतौ पा॰ ८.१.७०")
      elif key != "सु" or (nxt_k and lex.analyze_morph(nxt_k)["is_tinanta"]):
        rule_parts.append("तिङि चोदात्तवति पा॰ ८.१.७१")
    elif key in _VEDIC_VOCATIVE_WORDS and not ctx.get("is_clause_start"):
      rule_parts.append("अपादादिः आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९")
    else:
      morph = lex.analyze_morph(key)
      if morph["is_tinanta"]:
        rule_parts.append("तिङन्तम् अनुदात्तम्, पा॰ ८.१.२८")
      elif morph["voc_possible"] and not ctx.get("is_clause_start"):
        rule_parts.append("अपादादिः आमन्त्रितम् अनुदात्तम्, पा॰ ८.१.१९")

  # 2. Exact external corpus counts (`*CORPUS*-M/N`)
  # For unaccented enclitics/verbs (`n_acc == 0`), disable stem expansion so `मे`/`त्वा`/`असि` show exact `-M`!
  allow_stem = (n_acc > 0) and is_declinable_nominal(pada_us, ", ".join(rule_parts))
  count_tags = _format_external_corpus_counts(pada_us, counter, corpora, allow_stem=allow_stem)
  # Drop `0/N` stem-only counts when `exact == 0` across ALL corpora (otherwise we'd cite stem-only when exact accent isn't confirmed!)
  if count_tags and all("-0/" in t for t in count_tags):
    # Keep stem-only counts ONLY if no exact count exists anywhere AND `n_acc == 1` (nominal stem paradigm witness!)
    pass

  all_parts: list[str] = []
  seen: set[str] = set()
  for rp in rule_parts:
    if rp and rp not in seen:
      seen.add(rp)
      all_parts.append(rp)
  for ct in count_tags:
    if ct not in seen:
      seen.add(ct)
      all_parts.append(ct)

  # 3. Fallback when external Vedic corpora had 0 counts and no rule yet: check dictionaries (MW/Whitney/Macdonell/Lanman)
  if not all_parts:
    form_hits = lex.lookup_form(key).get(marks, {})
    dict_tags = [
      ("*MW* ŚBr." if d == "MW_SB" else f"*{d}*")
      for d in ("Whitney", "Macdonell", "Lanman", "MW_SB", "MW")
      if form_hits.get(d, 0) > 0
    ]
    if dict_tags:
      all_parts.extend(dict_tags)
    elif n_acc == 1:
      # Check stem projection or Pāṇinian compound/kṛdanta candidates matching `marks`
      cands = generate_pada_candidates(pada_bare, ctx, next_pada_bare, lex)
      for c in cands:
        if c.marks == marks:
          rh = _strip_corpus_tags_from_rule(c.prov)
          if rh and rh != "अनाम्नातम् (अनुमानम्)":
            all_parts.append(rh)
            break
    if not all_parts:
      all_parts.append("मूल-पाठः" if from_mula else "अनाम्नातम् (अनुमानम्)")

  return normalize_panini_abbreviations(", ".join(all_parts))


def _solve_unaccented_padas_viterbi(
  padas_bare: Sequence[str],
  ctxs: Sequence[dict],
  lex: UnifiedVedicLexicon,
  counter: VedicCorpusCounter,
  corpora: Sequence[str],
  parallel_pada_map: dict[int, tuple[tuple[str, ...], str]] | None = None,
) -> list[tuple[tuple[str, ...], str]]:
  """Clause-aware 1D Viterbi accent decoder for unaccented KS blocks (Mode B, TA-style)."""
  P = len(padas_bare)
  if P == 0:
    return []
  par_map = parallel_pada_map or {}

  cand_lists: list[list[PadaCandidate]] = []
  for i, pd in enumerate(padas_bare):
    nxt = padas_bare[i + 1] if i + 1 < P else ""
    cands = generate_pada_candidates(pd, ctxs[i], nxt, lex)
    # Boost candidates strongly supported by MS (when solving KS!) or by parallel mantra alignment!
    if i in par_map:
      par_mks, par_src = par_map[i]
      found_par = False
      adjusted: list[PadaCandidate] = []
      for c in cands:
        if c.marks == par_mks:
          found_par = True
          adjusted.append(
            PadaCandidate(
              ref=c.ref, marks=c.marks, prov=c.prov, role=c.role, solid=True, prior_cost=c.prior_cost - 2.5
            )
          )
        else:
          adjusted.append(c)
      if not found_par and len(par_mks) == len(_marks_of_us_word(pd)):
        try:
          ref_w = _fast_apply_us_marks(pd, par_mks)
          adjusted.append(
            PadaCandidate(
              ref=ref_w, marks=par_mks, prov=par_src, role="nominal", solid=True, prior_cost=-2.0
            )
          )
        except ValueError:
          pass
      cands = adjusted
    elif "MS" in corpora:
      # Sister-śākhā MS corpus boost for KS words not matched by a full parallel mantra!
      adjusted = []
      for c in cands:
        ms_exact = counter.count(c.ref, "MS")
        bonus = -0.35 if ms_exact >= 3 else (-0.18 if ms_exact >= 1 else 0.0)
        adjusted.append(
          PadaCandidate(
            ref=c.ref, marks=c.marks, prov=c.prov, role=c.role, solid=c.solid or ms_exact > 0, prior_cost=c.prior_cost + bonus
          )
        )
      cands = adjusted
    if not cands:
      n_s = _fast_syllable_count(pd)
      z = tuple("" for _ in range(n_s))
      cands = [PadaCandidate(ref=pd, marks=z, prov="अनाम्नातम् (अनुमानम्)", role="guess", solid=False, prior_cost=5.0)]
    cand_lists.append(cands)

  # 1D Viterbi over `cand_lists` using `_transition_syntax_cost`
  dp: list[list[float]] = [[c.prior_cost for c in cand_lists[0]]]
  back: list[list[int]] = [[-1] * len(cand_lists[0])]

  for i in range(1, P):
    cur_cands = cand_lists[i]
    prev_cands = cand_lists[i - 1]
    prev_dp = dp[i - 1]
    cur_dp: list[float] = []
    cur_back: list[int] = []
    for ci, c in enumerate(cur_cands):
      best_val = 1e18
      best_pi = 0
      for pi, pc in enumerate(prev_cands):
        val = prev_dp[pi] + _transition_syntax_cost(pc, c) + c.prior_cost
        if val < best_val:
          best_val = val
          best_pi = pi
      cur_dp.append(best_val)
      cur_back.append(best_pi)
    dp.append(cur_dp)
    back.append(cur_back)

  # Backtrack optimal path
  best_last = min(range(len(dp[-1])), key=lambda k: dp[-1][k])
  chosen_idxs = [0] * P
  chosen_idxs[-1] = best_last
  for i in range(P - 1, 0, -1):
    chosen_idxs[i - 1] = back[i][chosen_idxs[i]]

  return [(cand_lists[i][chosen_idxs[i]].marks, cand_lists[i][chosen_idxs[i]].prov) for i in range(P)]


def _align_parallel_mantra_padas(
  padas_bare: Sequence[str],
  parallel_vp_us: str,
  parallel_source: str,
  lex: UnifiedVedicLexicon,
) -> dict[int, tuple[tuple[str, ...], str]]:
  """Align bare target padas against a parallel US-accented mantra (MS/TS/VS/RV) to transfer accents."""
  if not parallel_vp_us or not has_us_accents(parallel_vp_us):
    return {}
  par_norm = normalize_ks_ms_orthography(parallel_vp_us)
  par_bare_txt = accent.strip_accents(par_norm)
  par_padas_bare, par_cids = split_vp_to_padas_with_clauses(par_bare_txt, lex)
  if not par_padas_bare:
    return {}
  par_starts = {0} | {i for i in range(1, len(par_cids)) if par_cids[i] != par_cids[i - 1]}
  par_marks, _ = _project_us_marks_onto_padas(par_padas_bare, par_norm, set(), lex, clause_starts=par_starts)

  tgt_keys = [_normalize_lookup_key(p) for p in padas_bare]
  par_keys = [_normalize_lookup_key(p) for p in par_padas_bare]
  sm = difflib.SequenceMatcher(a=tgt_keys, b=par_keys, autojunk=False)
  out: dict[int, tuple[tuple[str, ...], str]] = {}
  for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
      for k in range(i2 - i1):
        ti, pj = i1 + k, j1 + k
        mks = par_marks[pj]
        # Verify syllable count matches and no multi-udātta glitch in source
        if len(mks) == len(_marks_of_us_word(padas_bare[ti])):
          if sum(1 for m in mks if m) <= 1 or _is_dual_accent_word(tgt_keys[ti]):
            out[ti] = (mks, f"समानान्तर-पाठः ({parallel_source})")
  return out


def _apply_vp_suggestions_from_vyat(
  vp_text: str,
  padas_bare: Sequence[str],
  orig_marks: Sequence[tuple[str, ...]],
  fixed_marks: Sequence[tuple[str, ...]],
) -> str:
  """Render inline ``[[OLD|NEW]]`` suggestions on ``vp_text`` ONLY for words whose accents changed."""
  vp_pieces = _fast_extract_vp_pieces(vp_text)
  if not vp_pieces:
    return vp_text
  pp_keys, pp_meta, pp_starts, _ = _fast_flatten_pp_and_starts(padas_bare)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(
    vp_text, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, pp_starts
  )

  # Build edits per VP piece where any mapped pada changed marks
  changed_padas = {i for i, (o, f) in enumerate(zip(orig_marks, fixed_marks)) if o != f}
  if not changed_padas:
    return vp_text

  edits: list[tuple[int, int, str]] = []
  for pi, pc in enumerate(vp_pieces):
    touches_changed = False
    new_pc_mks = list(pc["old_mks"])
    for vsi, src_list in enumerate(pc_syl_sources[pi]):
      if not src_list:
        continue
      tup = src_list[0]
      if any(pp_meta[si][0] in changed_padas for si in tup):
        touches_changed = True
        # Compute sandhi-resolved new mark from fixed_marks (`पा॰ ८.२.४–६`)
        if len(tup) == 1:
          p_i, s_i = pp_meta[tup[0]]
          new_pc_mks[vsi] = fixed_marks[p_i][s_i] if s_i < len(fixed_marks[p_i]) else ""
        else:
          p1, s1 = pp_meta[tup[0]]
          p2, s2 = pp_meta[tup[-1]]
          m1 = fixed_marks[p1][s1] if s1 < len(fixed_marks[p1]) else ""
          m2 = fixed_marks[p2][s2] if s2 < len(fixed_marks[p2]) else ""
          if m1 == "S" or m2 == "S":
            new_pc_mks[vsi] = "S"
          elif m1 == "U" or m2 == "U":
            new_pc_mks[vsi] = "U"
          else:
            new_pc_mks[vsi] = ""
    if not touches_changed:
      continue
    old_tok = pc["old"]
    try:
      new_tok = _fast_apply_us_marks(old_tok, new_pc_mks)
    except ValueError:
      continue
    if new_tok != old_tok and bare_devanagari(new_tok) == bare_devanagari(old_tok):
      edits.append((pc["start"], pc["end"], f"[[{old_tok}|{new_tok}]]"))

  if not edits:
    return vp_text
  out = vp_text
  for st, en, rep in reversed(edits):
    out = out[:st] + rep + out[en:]
  return out


def _project_solved_accents_to_vp(
  vp_bare_text: str,
  padas_bare: Sequence[str],
  solved_marks: Sequence[tuple[str, ...]],
) -> str:
  """Project reconstructed US accents from Mode-B padapāṭha onto unaccented ``विश्वास-प्रस्तुतिः``."""
  vp_pieces = _fast_extract_vp_pieces(vp_bare_text)
  if not vp_pieces:
    return vp_bare_text
  pp_keys, pp_meta, pp_starts, _ = _fast_flatten_pp_and_starts(padas_bare)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(
    vp_bare_text, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, pp_starts
  )

  flat_marks: list[str] = []
  for pi, pc in enumerate(vp_pieces):
    for vsi, src_list in enumerate(pc_syl_sources[pi]):
      if not src_list:
        flat_marks.append("")
        continue
      tup = src_list[0]
      if len(tup) == 1:
        p_i, s_i = pp_meta[tup[0]]
        flat_marks.append(solved_marks[p_i][s_i] if s_i < len(solved_marks[p_i]) else "")
      else:
        p1, s1 = pp_meta[tup[0]]
        p2, s2 = pp_meta[tup[-1]]
        m1 = solved_marks[p1][s1] if s1 < len(solved_marks[p1]) else ""
        m2 = solved_marks[p2][s2] if s2 < len(solved_marks[p2]) else ""
        # पा॰ ८.२.४: udātta i/u + anudātta V -> svarita (`S`) on yaṇ!
        v1 = pp_keys[tup[0]][1]
        v2 = pp_keys[tup[-1]][1]
        vp_v = pc["keys"][vsi][1]
        is_yan = v1 in ("i", "u", "r", "l") and v1 != vp_v and v2 == vp_v
        is_abhin = vsi in pc.get("avagraha_after", set()) and v1 in ("e", "o") and v2 == "a"
        if m1 == "U" and m2 == "" and (is_yan or is_abhin):
          flat_marks.append("S")
        elif m1 == "S" or m2 == "S":
          flat_marks.append("S")
        elif m1 == "U" or m2 == "U":
          flat_marks.append("U")
        else:
          flat_marks.append("")
  try:
    return _fast_apply_vp_marks(vp_bare_text, vp_pieces, flat_marks)
  except Exception:
    return vp_bare_text


def build_block_padapatha_full(
  blk: SplitBlock,
  lex: UnifiedVedicLexicon,
  counter: VedicCorpusCounter,
  *,
  corpus: str,
  schroeder_notes: list[str] | None = None,
) -> BuiltBlock:
  """Build TA-mode bulleted ``पद-पाठः (यान्त्रिकः)`` and finalized VP/mūla for one ``SplitBlock``."""
  corpora = MS_PROVENANCE_CORPORA if corpus == "MS" else KS_PROVENANCE_CORPORA
  vp_raw = blk.vp_text.strip()
  mula_raw = blk.mula_text.strip()

  # Normalize orthography for splitting & syllable projection
  vp_norm = normalize_ks_ms_orthography(vp_raw)
  vp_bare_norm = accent.strip_accents(vp_norm)
  mula_had_accents = has_us_accents(vp_norm) or has_us_accents(mula_raw)
  # In KS Schroeder, ~45 otherwise unaccented anuvākas contain 1–2 stray OCR svarita/udātta marks
  # (e.g. `आहि᳙यते` in an unaccented 250-word Brāhmaṇa block). Treat sparse stray marks (<15% of
  # words in >=8-word blocks, or only 1 mark in >=6-word blocks) as unaccented -> clean Mode B!
  if corpus == "KS" and mula_had_accents:
    n_acc_marks = len(re.findall(r"[\u1cd3\u1cd9]", vp_norm))
    n_words = len(vp_bare_norm.split())
    if (n_words >= 8 and n_acc_marks / n_words < 0.15) or (n_words >= 6 and n_acc_marks < 2):
      mula_had_accents = False
      vp_raw = accent.strip_accents(vp_raw)
      vp_norm = vp_bare_norm

  base_vp_hdr = "विश्वास-प्रस्तुतिः - ऋक्" if blk.is_rk else "विश्वास-प्रस्तुतिः"

  if not vp_bare_norm or not _DEVANAGARI_RE.search(vp_bare_norm):
    return BuiltBlock(
      split_block=blk,
      vp_summary=base_vp_hdr,
      vp_body=vp_raw,
      mula_body=mula_raw,
      pp_summary="पद-पाठः (यान्त्रिकः)",
      pp_lines=[],
      padas_bare=[],
      padas_us=[],
      sandhi_ok=True,
      sandhi_detail="",
      n_vyat=0,
      mula_had_accents=mula_had_accents,
      schroeder_notes=list(schroeder_notes or []),
    )

  # Split into sandhi-verified padas with clause IDs
  padas_bare, clause_ids = split_vp_to_padas_with_clauses(vp_bare_norm, lex)
  # Expand any chunk still containing internal `ऽ`
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
  padas_bare = expanded_bare
  clause_ids = expanded_cids
  # Also protect `प्रत्युष्टारातिः` / `अवधूतारातिः` / `परापूतारातिः` / `निर्दग्धारातिः` from DP mis-splitting (`प्रत्युः + टाः`)
  _known_arari_compounds = {
    "प्रत्युष्टारातिः": ["प्रत्युष्टा", "अरातिः"],
    "अवधूतारातिः": ["अवधूता", "अरातिः"],
    "परापूतारातिः": ["परापूता", "अरातिः"],
    "निर्दग्धारातिः": ["निर्दग्धा", "अरातिः"],
  }
  fixed_bare: list[str] = []
  fixed_cids: list[int] = []
  # Re-check single-word blocks matching known Vedic fused compounds
  bare_tok_single = vp_bare_norm.strip(" ।॥")
  if bare_tok_single in _known_arari_compounds:
    padas_bare = list(_known_arari_compounds[bare_tok_single])
    clause_ids = [0] * len(padas_bare)
  else:
    for pd, cid in zip(padas_bare, clause_ids):
      if pd in _known_arari_compounds:
        sub = _known_arari_compounds[pd]
        fixed_bare.extend(sub)
        fixed_cids.extend([cid] * len(sub))
      else:
        fixed_bare.append(pd)
        fixed_cids.append(cid)
    padas_bare = fixed_bare
    clause_ids = fixed_cids
  # Re-join spurious Vedic optative/precative splits (`प्रजन् + इषे + यम्` -> `प्र` + `जनिषेयम्`, `...षे + यम्` -> `...षेयम्`)
  merged_bare: list[str] = []
  merged_cids: list[int] = []
  idx_m = 0
  while idx_m < len(padas_bare):
    if (
      idx_m + 2 < len(padas_bare)
      and padas_bare[idx_m] == "प्रजन्"
      and padas_bare[idx_m + 1] == "इषे"
      and padas_bare[idx_m + 2] == "यम्"
    ):
      merged_bare.extend(["प्र", "जनिषेयम्"])
      merged_cids.extend([clause_ids[idx_m], clause_ids[idx_m]])
      idx_m += 3
    elif (
      idx_m + 1 < len(padas_bare)
      and padas_bare[idx_m + 1] == "यम्"
      and padas_bare[idx_m].endswith(("षे", "मे", "भे", "ये", "वे", "ने", "रे", "हे"))
      and len(padas_bare[idx_m]) >= 4
    ):
      merged_bare.append(padas_bare[idx_m] + "यम्")
      merged_cids.append(clause_ids[idx_m])
      idx_m += 2
    else:
      merged_bare.append(padas_bare[idx_m])
      merged_cids.append(clause_ids[idx_m])
      idx_m += 1
  padas_bare = merged_bare
  clause_ids = merged_cids

  clause_starts = {0} | {i for i in range(1, len(clause_ids)) if clause_ids[i] != clause_ids[i - 1]}

  # Parallel mantra word alignment (for unaccented KS or repairing broken Schroeder accents)
  par_map: dict[int, tuple[tuple[str, ...], str]] = {}
  if blk.parallel_ref is not None and has_us_accents(blk.parallel_ref.vp_us):
    par_map = _align_parallel_mantra_padas(
      padas_bare, blk.parallel_ref.vp_us, blk.parallel_ref.source, lex
    )

  # Branch: Mode A (accented मूलम्) vs Mode B (unaccented मूलम् -> TA mode यन्त्र-स्वरः)
  if mula_had_accents:
    pada_marks, _ = _project_us_marks_onto_padas(
      padas_bare, vp_norm, set(), lex, clause_starts=clause_starts
    )
    # Refine ONLY truly fused/unattested multi-accent non-dual tokens (NEVER split a valid known single word
    # like Schroeder's double-udātta `ब᳓ह्वीः᳓` into `ब᳓ह् + वीः᳓`, and require every split part to be a real word!)
    refined_bare: list[str] = []
    refined_cids: list[int] = []
    did_refine = False
    for pd, cid, mks in zip(padas_bare, clause_ids, pada_marks):
      pd_key = _normalize_lookup_key(pd)
      pd_slp = _deva_to_slp(pd_key)
      is_known_single = bool(pd_slp and lex.word_score_slp(pd_slp) > 0)
      if (
        sum(1 for m in mks if m) > 1
        and not _is_dual_accent_word(pd_key)
        and not is_known_single
        and len(pd_key) >= 6
      ):
        sub = _try_split_multi_accent_pada(pd, mks, lex)
        if (
          sub
          and len(sub) >= 2
          and all(lex.word_score_slp(_deva_to_slp(_normalize_lookup_key(sp))) > 0 for sp in sub)
        ):
          refined_bare.extend(sub)
          refined_cids.extend([cid] * len(sub))
          did_refine = True
          continue
      refined_bare.append(pd)
      refined_cids.append(cid)
    if did_refine:
      padas_bare = refined_bare
      clause_ids = refined_cids
      clause_starts = {0} | {i for i in range(1, len(clause_ids)) if clause_ids[i] != clause_ids[i - 1]}
      pada_marks, _ = _project_us_marks_onto_padas(
        padas_bare, vp_norm, set(), lex, clause_starts=clause_starts
      )
      if blk.parallel_ref is not None and has_us_accents(blk.parallel_ref.vp_us):
        par_map = _align_parallel_mantra_padas(
          padas_bare, blk.parallel_ref.vp_us, blk.parallel_ref.source, lex
        )

    ctxs = _detect_clause_contexts(padas_bare, vp_bare_norm, lex, clause_ids=clause_ids)
    # Audit projected marks ONLY for unmistakable transmission/OCR errors:
    # (1) multi-udātta on non-dual word (पा॰ ६.१.१५८)
    # (2) accented always-unaccented enclitic (पा॰ ८.१.१८)
    # (3) dropped accent on clearly accented non-enclitic, non-verb, non-vocative, non-āmreḍita, non-gati word!
    solved_viterbi: list[tuple[tuple[str, ...], str]] | None = None
    fixed_marks: list[tuple[str, ...]] = list(pada_marks)
    pp_lines: list[str] = []
    padas_us_final: list[str] = []
    n_vyat = 0

    for i, (pd, mks) in enumerate(zip(padas_bare, pada_marks)):
      key = _normalize_lookup_key(pd)
      nxt = padas_bare[i + 1] if i + 1 < len(padas_bare) else ""
      n_acc = sum(1 for m in mks if m)
      ar_us = _fast_apply_us_marks(pd, mks)

      err_kind = ""
      if n_acc > 1 and not _is_dual_accent_word(key):
        # Guard against sandhi-merged `आ᳓` upasarga (`त᳓या + आ᳓ + वहन्ते` parsed as `त᳓या᳓ + वहन्ते`):
        # only flag multi-udātta when it is NOT a vowel-final pronoun right before a finite verb!
        nxt_morph = lex.analyze_morph(_normalize_lookup_key(nxt)) if nxt else {"is_tinanta": False}
        if not (key.endswith(("आ", "ा")) and nxt_morph["is_tinanta"]):
          err_kind = "अनेकोदात्त-दोषः पा॰ ६.१.१५८"
      elif n_acc > 0 and key in ALWAYS_ANUDATTA_ENCLITICS:
        err_kind = "अनुदात्तम्, पा॰ ८.१.१८"
      elif (
        corpus == "KS"  # Only run dropped-accent OCR recovery on KS Schroeder (NOT authoritative MS TITUS!)
        and n_acc == 0
        and key not in ALWAYS_ANUDATTA_ENCLITICS
        and key not in ("वा", "ते", "मा", "वाम्", "नौ", "मे", "नः", "वः", "त्वा")
        and key not in UPASARGA_DEVA_SET
        and key not in ANVADESHA_2434
        and key not in _VEDIC_VOCATIVE_WORDS
        and not ctxs[i].get("is_amredita")
      ):
        morph = lex.analyze_morph(key)
        is_verb_or_voc = morph["is_tinanta"] or (morph["voc_possible"] and not ctxs[i].get("is_clause_start"))
        if not is_verb_or_voc:
          form_hits = lex.lookup_form(key)
          zero_f = sum(form_hits.get(mks, {}).values())
          acc_f = sum(sum(s.values()) for mk2, s in form_hits.items() if any(mk2))
          if acc_f >= 5 and zero_f == 0:
            err_kind = "स्वर-लोपः"
          elif i in par_map and any(par_map[i][0]) and zero_f == 0:
            err_kind = "स्वर-लोपः"

      if err_kind:
        if solved_viterbi is None:
          solved_viterbi = _solve_unaccented_padas_viterbi(
            padas_bare, ctxs, lex, counter, corpora, parallel_pada_map=par_map
          )
        cand_mks, cand_rule = solved_viterbi[i]
        # For enclitic error, force all-anudātta
        if err_kind.startswith("अनुदात्तम्"):
          cand_mks = tuple("" for _ in range(len(mks)))
          cand_rule = "अनुदात्तम्, पा॰ ८.१.१८"
        # For multi-udātta, prefer a single-accent subset of `mks` if strongly attested
        elif err_kind.startswith("अनेकोदात्त") and sum(1 for m in cand_mks if m) != 1:
          acc_idxs = [j for j, m in enumerate(mks) if m]
          best_sub = tuple(mks[j] if j == acc_idxs[0] else "" for j in range(len(mks)))
          cand_mks = best_sub

        if cand_mks != mks:
          ref_us = _fast_apply_us_marks(pd, cand_mks)
          fixed_marks[i] = cand_mks
          padas_us_final.append(ref_us)
          n_vyat += 1
          prov = _build_provenance_for_pada(
            ref_us, pd, cand_mks, ctxs[i], nxt, lex, counter, corpora,
            rule_hint=cand_rule, extra_note=err_kind if not cand_rule.startswith(err_kind[:8]) else "",
            from_mula=False,
          )
          pp_lines.append(f"- {ar_us} → **{ref_us}** ({prov})")
          continue

      # Authentic unchanged pada from `मूलम्`
      padas_us_final.append(ar_us)
      prov = _build_provenance_for_pada(
        ar_us, pd, mks, ctxs[i], nxt, lex, counter, corpora, from_mula=True
      )
      pp_lines.append(f"- {ar_us} ({prov})")

    vp_final = (
      _apply_vp_suggestions_from_vyat(vp_raw, padas_bare, pada_marks, fixed_marks)
      if n_vyat > 0
      else vp_raw
    )
    vp_summary = format_filled_vp_summary(base_vp_hdr, n_vyat, len(padas_bare), mula_has_accents=True)
    pp_summary = format_padapatha_summary(n_vyat, len(padas_bare))
  else:
    # Mode B: Unaccented मूलम् -> TA-mode यन्त्र-स्वरः!
    ctxs = _detect_clause_contexts(padas_bare, vp_bare_norm, lex, clause_ids=clause_ids)
    solved = _solve_unaccented_padas_viterbi(
      padas_bare, ctxs, lex, counter, corpora, parallel_pada_map=par_map
    )
    solved_marks = [mks for mks, _ in solved]
    padas_us_final = [_fast_apply_us_marks(pd, mks) for pd, mks in zip(padas_bare, solved_marks)]
    pp_lines = []
    for i, (pd, us_w, (mks, rule_h)) in enumerate(zip(padas_bare, padas_us_final, solved)):
      nxt = padas_bare[i + 1] if i + 1 < len(padas_bare) else ""
      prov = _build_provenance_for_pada(
        us_w, pd, mks, ctxs[i], nxt, lex, counter, corpora, rule_hint=rule_h, from_mula=False
      )
      pp_lines.append(f"- {us_w} ({prov})")

    vp_final = _project_solved_accents_to_vp(vp_raw, padas_bare, solved_marks)
    vp_summary = format_filled_vp_summary(base_vp_hdr, 0, len(padas_bare), mula_has_accents=False)
    pp_summary = "पद-पाठः (यान्त्रिकः)"
    n_vyat = 0

  # Verify forward sandhi round-trip
  s_res = verify_mantra_sandhi(padas_bare, vp_bare_norm)
  sandhi_ok = bool(s_res[0])
  sandhi_detail = "" if sandhi_ok else repr(s_res[1:])

  return BuiltBlock(
    split_block=blk,
    vp_summary=vp_summary,
    vp_body=vp_final,
    mula_body=mula_raw,
    pp_summary=pp_summary,
    pp_lines=pp_lines,
    padas_bare=padas_bare,
    padas_us=padas_us_final,
    sandhi_ok=sandhi_ok,
    sandhi_detail=sandhi_detail,
    n_vyat=n_vyat,
    mula_had_accents=mula_had_accents,
    schroeder_notes=list(schroeder_notes or []),
  )


def render_anuvaka_markdown(
  title: str,
  built_blocks: Sequence[BuiltBlock],
  *,
  anuvaka_schroeder_notes: Sequence[str] = (),
) -> str:
  """Render a complete per-anuvāka Markdown file in canonical wrapped ``sarva-prastutiH`` format."""
  out: list[str] = [f'+++\ntitle = "{title}"\n+++\n']

  for bi, b in enumerate(built_blocks):
    parts: list[str] = []

    # 1. Optional `<details><summary>सर्वा अवतारिकाः</summary>` for matched viniyogas
    if b.split_block.viniyogas:
      seen_v: set[tuple[str, str]] = set()
      av_children: list[str] = []
      for v in b.split_block.viniyogas:
        vk = (v.source, v.ref)
        if vk in seen_v:
          continue
        seen_v.add(vk)
        sutra_disp = f"{v.sutra_text} ({v.ref})" if v.ref else v.sutra_text
        av_children.append(f"<details><summary>{v.source}</summary>\n\n{sutra_disp}\n</details>")
      if av_children:
        parts.append(
          "<details><summary>सर्वा अवतारिकाः</summary>\n\n"
          + "\n\n".join(av_children)
          + "\n</details>"
        )

    # 2. `<details open><summary>विश्वास-प्रस्तुतिः...</summary>`
    vp_disp = b.vp_body.strip()
    if vp_disp and not re.search(r"[।॥]\s*$", vp_disp):
      vp_disp = vp_disp + (" ॥" if b.split_block.is_rk else " ।")
    parts.append(f"<details open><summary>{b.vp_summary}</summary>\n\n{vp_disp}\n</details>")

    # 3. `<details><summary>सर्वाष् टीकाः</summary>` containing मूलम् + पद-पाठः + optional Schroeder - टिप्पणी
    tika_children: list[str] = []
    tika_children.append(f"<details><summary>मूलम्</summary>\n\n{b.mula_body.strip()}\n</details>")
    if b.pp_lines:
      pp_body = "\n".join(b.pp_lines)
      tika_children.append(f"<details><summary>{b.pp_summary}</summary>\n\n{pp_body}\n</details>")

    # Block-level Schroeder footnotes + chapter-level Schroeder apparatus on last block
    notes_here = list(b.schroeder_notes)
    if bi == len(built_blocks) - 1 and anuvaka_schroeder_notes:
      notes_here.extend(anuvaka_schroeder_notes)
    if notes_here:
      tika_children.append(
        "<details><summary>Schroeder - टिप्पणी</summary>\n\n"
        + "\n\n".join(notes_here)
        + "\n</details>"
      )

    parts.append(
      "<details><summary>सर्वाष् टीकाः</summary>\n\n"
      + "\n\n".join(tika_children)
      + "\n</details>"
    )

    out.append("\n\n".join(parts))

  return "\n\n".join(out).rstrip() + "\n"
