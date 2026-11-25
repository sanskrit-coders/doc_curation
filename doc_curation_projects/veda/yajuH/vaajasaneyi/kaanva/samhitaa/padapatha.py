"""Sandhi-verified Padapāṭha carving, splitting, and reconciliation helpers."""
from __future__ import annotations

import difflib
import re
from typing import Sequence

from doc_curation.sanskrit import fixer
from doc_curation.sanskrit.accent import samhita_splitter, sandhi_check
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import _VP_STRIP_RE
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.repair import _norm_skel
from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina.samhitaa import bhashya_aligner


def _subsequence_ratio(a: str, b: str) -> float:
  if not a or not b:
    return 0.0
  if a in b or b in a:
    return 1.0
  sm = difflib.SequenceMatcher(None, a, b)
  return sum(blk.size for blk in sm.get_matching_blocks()) / max(1, min(len(a), len(b)))


def _clean_pada_tokens(pada_raw: str) -> list[str]:
  """Clean VSM/SSU Drive-OCR Padapāṭha text into units, keeping `Xइति YऽZ` pairs unbroken."""
  t = re.sub(r"।{2,}", "॥", re.sub(r"(?<!\|)\|(?!\|)", "।", re.sub(r"\|\|", "॥", pada_raw)))
  t = re.sub(r"॥\s*[^\s॥]{1,6}\s*॥\s*[०-९\s()]+॥?", "।", t)
  t = re.sub(r"॥\s*[०-९\s()]+॥?", "।", t)
  toks: list[str] = []
  for unit in re.split(r"[।\n]+", t):
    u = " ".join(unit.split()).strip()
    if not u or not re.search(r"[अ-ह]", u):
      continue
    u_bare = _VP_STRIP_RE.sub("", u)
    if re.search(r"(?:इति|इती|[ेी]ति|[क-ह]िति)", u_bare) and len(u.split()) <= 4:
      toks.append(u)
    else:
      toks.extend(w for w in u.split() if re.search(r"[अ-ह]", w))
  return toks


def _pada_tok_eff_skel(tok: str) -> str:
  """Strip the repeated `Xइति` gloss half when estimating saṁhitā length of a Padapāṭha unit."""
  bare = _VP_STRIP_RE.sub("", tok)
  m = re.search(r"(?:इति|इती|[ेी]ति|[क-ह]िति)\s+(.+)$", bare)
  return _norm_skel(m.group(1) if m else bare)


def _looks_galita_or_short(pada_tokens: list[str], mula_text: str) -> bool:
  m_len = len(re.sub(r"\s+", "", _norm_skel(mula_text)))
  p_len = len("".join(_pada_tok_eff_skel(t) for t in pada_tokens))
  return p_len < 0.72 * m_len


def _format_pada_clause(tokens: list[str], clause_mula: str) -> str:
  """Format Padapāṭha tokens for a sense-unit clause with `।` separators matching VS-M style."""
  if not tokens:
    return ""
  clean_toks = [t.strip("।॥ ") for t in tokens if t.strip("।॥ ")]
  body = "। ".join(clean_toks) + "।"
  m_end = re.search(
    r"॥\s*(?:\([०-९]+\)\s*)?([०-९]+)(?:\s*(?:[।॥]+|\([०-९]+\)|\s)+[०-९।॥\s()]*)*$",
    clause_mula.strip(),
  )
  if m_end:
    body += f" {m_end.group(1)}।"
  return fixer.normalize_mAdhyandina(body, normalize_pre_vowel_avagrahas=False)


def _verify_pada_tokens(toks: Sequence[str], mula_i: str) -> bool:
  """Resolve ŚYV `इति`/`ऽ` analyses into samāsa-hyphenated tokens and check forward sandhi."""
  if not toks:
    return False
  joined = "। ".join(t.strip("।॥ ") for t in toks if t.strip("।॥ ")) + "।"
  resolved = samhita_splitter.extract_padapatha_words(joined.replace("ऽ", "-"), keep_avagraha=True)
  if not resolved:
    resolved = [t.replace("ऽ", "-") for t in toks]
  mula_core = mula_i.split("##")[0].strip()
  ok, *_ = sandhi_check.verify_mantra_sandhi(resolved, mula_core)
  return ok


def _carve_sub_pada(pada_raw: str, sub_mula: str) -> str | None:
  """Carve the contiguous token slice from a larger Padapāṭha that verifies `sub_mula` via `sandhi_check`."""
  toks = _clean_pada_tokens(pada_raw)
  sk_tgt = _norm_skel(sub_mula)
  if not toks or not sk_tgt:
    return None
  m_len = len(sk_tgt)
  first_tok_head = sk_tgt[:3]
  tok_sks = [_norm_skel(t) for t in toks]
  for s_i in range(len(toks)):
    ts = tok_sks[s_i]
    head_match = (
      not first_tok_head
      or not ts
      or ts[:2] == first_tok_head[:2]
      or first_tok_head[:2] in ts
      or (len(ts) == 1 and ts[0] == first_tok_head[0])
      or (ts == "आ" and first_tok_head[0] in ("आ", "ए", "ओ"))
    )
    if not head_match:
      continue
    acc = ""
    for e_i in range(s_i + 1, len(toks) + 1):
      acc += tok_sks[e_i - 1]
      if len(acc) >= int(0.8 * m_len):
        if len(acc) > int(1.9 * m_len) + 16:
          break
        if _verify_pada_tokens(toks[s_i:e_i], sub_mula):
          return _format_pada_clause(toks[s_i:e_i], sub_mula)
  return None


def _linear_split_kanva_pada(
  kanva_toks: list[str],
  sub_mulas: list[str],
  out_padas: list[str],
  verified: list[bool],
) -> None:
  """Split full-span Kāṇva Drive-OCR Padapāṭha tokens linearly across `sub_mulas`."""
  n = len(sub_mulas)
  pos = 0
  for i, mula_i in enumerate(sub_mulas):
    head_sk = _norm_skel(mula_i)[:2]
    if verified[i] and i < n - 1:
      tgt_len = len(_norm_skel(mula_i))
      acc = ""
      while pos < len(kanva_toks) and len(acc) < tgt_len * 0.9:
        acc += _pada_tok_eff_skel(kanva_toks[pos])
        pos += 1
      continue
    if verified[i]:
      continue
    if i > 0 and head_sk:
      for sh in range(pos, min(len(kanva_toks) - (n - 1 - i), pos + 5)):
        if _pada_tok_eff_skel(kanva_toks[sh]).startswith(head_sk):
          pos = sh
          break
    if i == n - 1:
      cand_toks = kanva_toks[pos:]
    else:
      tgt_len = len(_norm_skel(mula_i))
      end_p, acc = pos, ""
      while end_p < len(kanva_toks) and len(acc) < tgt_len:
        acc += _pada_tok_eff_skel(kanva_toks[end_p])
        end_p += 1
      best_cut, best_toks = end_p, kanva_toks[pos:end_p]
      if best_toks and not _verify_pada_tokens(best_toks, mula_i):
        for delta in (-1, 1, -2, 2):
          alt_e = end_p + delta
          if pos < alt_e <= len(kanva_toks) - (n - 1 - i) and _verify_pada_tokens(kanva_toks[pos:alt_e], mula_i):
            best_cut, best_toks = alt_e, kanva_toks[pos:alt_e]
            break
      cand_toks, pos = best_toks, best_cut
    if cand_toks:
      ok = _verify_pada_tokens(cand_toks, mula_i)
      c_sk = "".join(_norm_skel(t) for t in cand_toks)
      m_sk = _norm_skel(mula_i)
      if ok or bhashya_aligner.pratika_overlap_score(" ".join(cand_toks), mula_i) >= 0.45 or _subsequence_ratio(c_sk, m_sk) >= 0.72:
        out_padas[i] = _format_pada_clause(cand_toks, mula_i)
        verified[i] = ok


def reconcile_and_split_padapatha(
  raw_kanva_pada: str,
  sub_mulas: list[str],
  vsm_matches: list[dict],
) -> tuple[list[str], list[bool]]:
  """Build verified per-clause `पदपाठः` strings aligned to `sub_mulas` using `sandhi_check`."""
  n = len(sub_mulas)
  out_padas: list[str] = [""] * n
  verified: list[bool] = [False] * n

  # Step 1: Adopt VS-M Padapāṭha whenever it verifies against VS-K `mula_i` via `_verify_pada_tokens`.
  for i, (mula_i, vsm_m) in enumerate(zip(sub_mulas, vsm_matches)):
    vsm_p = vsm_m.get("vsm_pada", "")
    if vsm_p and vsm_m.get("exact_pada_ok"):
      toks = _clean_pada_tokens(vsm_p)
      if _verify_pada_tokens(toks, mula_i):
        out_padas[i] = _format_pada_clause(toks, mula_i)
        verified[i] = True
  if all(verified):
    return out_padas, verified

  # Step 2: Check Kāṇva Drive-OCR Padapāṭha (`_carve_sub_pada` first, then full-span linear split).
  kanva_toks = _clean_pada_tokens(raw_kanva_pada)
  if kanva_toks:
    for i, mula_i in enumerate(sub_mulas):
      if not verified[i]:
        carved = _carve_sub_pada(raw_kanva_pada, mula_i)
        if carved:
          out_padas[i], verified[i] = carved, True
    if not all(verified) and not _looks_galita_or_short(kanva_toks, " ".join(sub_mulas)):
      _linear_split_kanva_pada(kanva_toks, sub_mulas, out_padas, verified)
    elif not all(verified) and n == 1 and not out_padas[0]:
      ok = _verify_pada_tokens(kanva_toks, sub_mulas[0])
      if ok or (
        not _looks_galita_or_short(kanva_toks, sub_mulas[0])
        and bhashya_aligner.pratika_overlap_score(" ".join(kanva_toks), sub_mulas[0]) >= 0.50
      ):
        out_padas[0], verified[0] = _format_pada_clause(kanva_toks, sub_mulas[0]), ok

  # Step 3: Remaining VS-M candidates; prefer clean curated VS-M when `exact_pada_ok` over noisy unverified OCR.
  for i, (mula_i, vsm_m) in enumerate(zip(sub_mulas, vsm_matches)):
    if verified[i]:
      continue
    vsm_p = vsm_m.get("vsm_pada", "")
    if vsm_p:
      toks = _clean_pada_tokens(vsm_p)
      if _verify_pada_tokens(toks, mula_i):
        out_padas[i], verified[i] = _format_pada_clause(toks, mula_i), True
      elif (vsm_m.get("exact_pada_ok") or not out_padas[i]) and bhashya_aligner.pratika_overlap_score(" ".join(toks), mula_i) >= 0.55:
        out_padas[i] = _format_pada_clause(toks, mula_i)
  return out_padas, verified
