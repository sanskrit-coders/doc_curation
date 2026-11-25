"""VS-M reference indexer & Griffith / Padapāṭha clause matcher for VS-K."""
from __future__ import annotations

import difflib
import pathlib
import re
from collections import defaultdict

from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import (
  VSM_SARVA_PRASTUTI_DIR,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.padapatha import (
  _carve_sub_pada,
  _clean_pada_tokens,
  _format_pada_clause,
  _subsequence_ratio,
  _verify_pada_tokens,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.repair import _norm_skel


def build_vsm_index(vsm_sarva_dir: pathlib.Path = VSM_SARVA_PRASTUTI_DIR) -> dict:
  """Index all 1,975 VS-M kaṇḍikās and sub-clauses (paired strictly per `विश्वास-प्रस्तुतिः` block)."""
  secs: list[dict] = []
  grams: dict[str, set[int]] = defaultdict(set)
  clause_exact: dict[str, tuple[str, str, str]] = {}

  for ch in range(1, 41):
    txt = (vsm_sarva_dir / f"{ch:02d}.md").read_text()
    for v_idx, sec in enumerate((s for s in re.split(r"(?m)^(?=## )", txt) if s.startswith("## ")), 1):
      sub_chunks = re.split(r"(?=<summary>(?:<h3>)?विश्वास-प्रस्तुतिः)", sec)
      subs = []
      for ch_blk in sub_chunks[1:]:
        m_m = re.search(r"<summary>मूलम्</summary>\s*(.*?)\s*</details>", ch_blk, flags=re.S)
        if not m_m:
          continue
        ms = m_m.group(1).strip()
        sk = _norm_skel(ms)
        m_g = re.search(r"<summary>Griffith</summary>\s*(.*?)\s*</details>", ch_blk, flags=re.S)
        m_p = re.search(r"<summary>पदपाठः[^<]*</summary>\s*(.*?)\s*</details>", ch_blk, flags=re.S)
        g = m_g.group(1).strip() if m_g else ""
        p = m_p.group(1).strip() if m_p else ""
        subs.append({"sk": sk, "mula": ms, "griffith": g, "pada": p})
        if sk:
          prev = clause_exact.get(sk)
          score_new = (2 if g else 0) + (2 if p else 0)
          score_old = ((2 if prev[1] else 0) + (2 if prev[2] else 0)) if prev else -1
          if score_new > score_old:
            clause_exact[sk] = (ms, g, p)
      full_sk = "".join(sub["sk"] for sub in subs)
      doc_i = len(secs)
      secs.append({"ch": ch, "v": v_idx, "sk": full_sk, "subs": subs})
      for k in range(0, max(1, len(full_sk) - 5), 2):
        grams[full_sk[k : k + 6]].add(doc_i)
  return {"secs": secs, "grams": grams, "clause_exact": clause_exact}


def _partition_pada_for_clauses(pada_raw: str, mulas: list[str]) -> list[str] | None:
  """Partition a single VS-M Padapāṭha across multiple consecutive VS-K clauses using `sandhi_check`."""
  toks = _clean_pada_tokens(pada_raw)
  if len(toks) < len(mulas):
    return None
  out: list[str] = []
  pos, n = 0, len(mulas)
  for i, m in enumerate(mulas):
    if i == n - 1:
      slice_toks = toks[pos:]
      if not _verify_pada_tokens(slice_toks, m):
        return None
      out.append(_format_pada_clause(slice_toks, m))
      break
    tgt_sk = len(_norm_skel(m))
    acc, candidates, best_j = "", [], None
    for j in range(pos + 1, len(toks) - (n - 1 - i) + 1):
      acc += _norm_skel(toks[j - 1])
      if abs(len(acc) - tgt_sk) <= max(10, int(0.35 * tgt_sk)):
        candidates.append(j)
      if len(acc) > tgt_sk + max(14, int(0.45 * tgt_sk)):
        break
    candidates.sort(key=lambda j: abs(sum(len(_norm_skel(t)) for t in toks[pos:j]) - tgt_sk))
    for j in candidates:
      if _verify_pada_tokens(toks[pos:j], m):
        best_j = j
        break
    if best_j is None:
      return None
    out.append(_format_pada_clause(toks[pos:best_j], m))
    pos = best_j
  return out


def _split_griffith_across_clauses(griffith: str, mulas: list[str]) -> list[str]:
  """Split a multi-clause Griffith paragraph across VS-K sub-clauses by punctuation & length."""
  g, n = griffith.strip(), len(mulas)
  if not g or n <= 1:
    return [g] + [""] * (n - 1) if n >= 1 else []
  segs = [s.strip() for s in re.split(r"(?<=[.;?!])\s+", g) if s.strip()]
  if len(segs) < n:
    segs = [s.strip() for s in re.split(r"(?<=[,;:])\s+", g) if s.strip()]
  if len(segs) < n:
    return [g] + [""] * (n - 1)
  sk_lens = [max(1, len(_norm_skel(m))) for m in mulas]
  tot_sk, tot_g = sum(sk_lens), len(g)
  out, pos = [], 0
  for i in range(n):
    if i == n - 1:
      out.append(" ".join(segs[pos:]).strip())
      break
    target_chars = tot_g * (sk_lens[i] / tot_sk)
    chosen = [segs[pos]]
    pos += 1
    while pos < len(segs) - (n - 1 - i) and len(" ".join(chosen)) + len(segs[pos]) * 0.5 < target_chars:
      chosen.append(segs[pos])
      pos += 1
    out.append(" ".join(chosen).strip())
  return out


def _select_candidate_sections(kandika_clauses: list[tuple[str, str]], vsm_index: dict, ch_hint: int | None) -> list[dict]:
  """Select top candidate VS-M sections matching 6-gram frequencies of `kandika_clauses`."""
  grams, secs = vsm_index["grams"], vsm_index["secs"]
  full_sk = "".join(_norm_skel(m) for _, m in kandika_clauses)
  cands: dict[int, int] = defaultdict(int)
  for i in range(0, max(1, len(full_sk) - 5), 2):
    for di in grams.get(full_sk[i : i + 6], ()):
      cands[di] += 1
  if ch_hint is None:
    return [secs[di] for di, _ in sorted(cands.items(), key=lambda kv: -kv[1])[:6]]
  top_local = [
    secs[di]
    for di, _ in sorted(
      ((di, cnt) for di, cnt in cands.items() if abs(secs[di]["ch"] - ch_hint) <= 2),
      key=lambda kv: (-kv[1], abs(secs[kv[0]]["ch"] - ch_hint)),
    )[:6]
  ]
  top_global = [secs[di] for di, _ in sorted(cands.items(), key=lambda kv: (-kv[1], abs(secs[kv[0]]["ch"] - ch_hint)))[:6]]
  seen_di, top_secs = set(), []
  for s in top_local + top_global:
    key = (s["ch"], s["v"])
    if key not in seen_di:
      seen_di.add(key)
      top_secs.append(s)
  return top_secs


def _match_one_to_many_clauses(
  kandika_clauses: list[tuple[str, str]],
  pool_subs: list[dict],
  results: list[dict],
  unmatched_indices: list[int],
) -> None:
  """Apply symmetric 1-VS-M -> N consecutive VS-K clause matching and substring containment."""
  if len(kandika_clauses) >= 2 and unmatched_indices and pool_subs:
    mulas = [m for _, m in kandika_clauses]
    skels = [_norm_skel(m) for m in mulas]
    i = 0
    while i < len(kandika_clauses):
      if results[i]["exact_pada_ok"] or i not in unmatched_indices:
        i += 1
        continue
      best_span, best_sub, best_r = None, None, 0.0
      for j in range(i + 2, min(len(kandika_clauses) + 1, i + 6)):
        if any(results[k]["exact_pada_ok"] for k in range(i, j)):
          break
        comb_sk = "".join(skels[i:j])
        if not comb_sk:
          continue
        max_diff = max(18, int(0.28 * len(comb_sk)))
        for sub in pool_subs:
          sub_sk = sub["sk"]
          if not sub_sk or abs(len(sub_sk) - len(comb_sk)) > max_diff:
            continue
          r = difflib.SequenceMatcher(None, comb_sk, sub_sk).ratio()
          if r > best_r:
            best_r, best_span, best_sub = r, j, sub
            if best_r >= 0.97:
              break
        if best_r >= 0.97:
          break
      if best_sub and best_r >= 0.78 and best_span is not None:
        p_parts = _partition_pada_for_clauses(best_sub["pada"], mulas[i:best_span]) if best_sub["pada"] else None
        g_parts = _split_griffith_across_clauses(best_sub["griffith"], mulas[i:best_span])
        for off, k_i in enumerate(range(i, best_span)):
          results[k_i] = {
            "griffith": g_parts[off] or results[k_i]["griffith"],
            "vsm_pada": p_parts[off] if p_parts else results[k_i]["vsm_pada"],
            "exact_pada_ok": bool(p_parts) or results[k_i]["exact_pada_ok"],
          }
        i = best_span
      else:
        i += 1
  for idx, (_, mula) in enumerate(kandika_clauses):
    if results[idx]["griffith"] and results[idx]["exact_pada_ok"]:
      continue
    sk = _norm_skel(mula)
    if len(sk) < 8:
      continue
    best_host, best_cont = None, 0.0
    for sub in pool_subs:
      sub_sk = sub["sk"]
      if len(sub_sk) < len(sk) - 6:
        continue
      if sk in sub_sk:
        cont = 1.0
      elif sk[:5] in sub_sk or sk[-5:] in sub_sk or _subsequence_ratio(sk[:24], sub_sk) >= 0.75:
        cont = _subsequence_ratio(sk, sub_sk)
      else:
        continue
      if cont > best_cont:
        best_cont, best_host = cont, sub
        if cont == 1.0 and sub["pada"]:
          break
    if best_host and best_cont >= 0.85:
      g_new = results[idx]["griffith"] or best_host["griffith"]
      p_new, ex_new = results[idx]["vsm_pada"], results[idx]["exact_pada_ok"]
      if not ex_new and best_host["pada"]:
        carved = _carve_sub_pada(best_host["pada"], mula)
        if carved:
          p_new, ex_new = carved, True
      results[idx] = {"griffith": g_new, "vsm_pada": p_new, "exact_pada_ok": ex_new}


def match_vsm_clauses(
  kandika_clauses: list[tuple[str, str]],
  vsm_index: dict,
  *,
  ch_hint: int | None = None,
) -> list[dict]:
  """Match each VS-K `(vp, mula)` clause to VS-M `griffith` and `pada` (1-to-1, N-to-1, 1-to-N, & containment)."""
  clause_exact = vsm_index["clause_exact"]
  top_secs = _select_candidate_sections(kandika_clauses, vsm_index, ch_hint)
  pool_subs = [sub for sec in top_secs for sub in sec["subs"]]
  results: list[dict] = [{"griffith": "", "vsm_pada": "", "exact_pada_ok": False} for _ in kandika_clauses]
  unmatched_indices: list[int] = []

  for idx, (_, mula) in enumerate(kandika_clauses):
    sk = _norm_skel(mula)
    if not sk:
      continue
    if sk in clause_exact:
      _, g, p = clause_exact[sk]
      results[idx] = {"griffith": g, "vsm_pada": p, "exact_pada_ok": bool(p)}
      continue
    matched_slice, best_cov = None, 0.0
    for sec in top_secs:
      subs = sec["subs"]
      for s_i in range(len(subs)):
        acc = ""
        for e_i in range(s_i + 1, min(len(subs) + 1, s_i + 8)):
          acc += subs[e_i - 1]["sk"]
          if abs(len(acc) - len(sk)) <= max(18, int(0.28 * len(sk))):
            r = difflib.SequenceMatcher(None, sk, acc).ratio()
            if r > best_cov:
              best_cov, matched_slice = r, subs[s_i:e_i]
              if best_cov >= 0.97:
                break
          if len(acc) > len(sk) + 25:
            break
        if best_cov >= 0.97:
          break
      if best_cov >= 0.97:
        break
    best_single, best_single_r = None, 0.0
    if best_cov < 0.97:
      max_diff = max(18, int(0.32 * len(sk)))
      for sub in pool_subs:
        sub_sk = sub["sk"]
        if not sub_sk or abs(len(sub_sk) - len(sk)) > max_diff:
          continue
        r = difflib.SequenceMatcher(None, sk, sub_sk).ratio()
        if r > best_single_r:
          best_single_r, best_single = r, sub
          if best_single_r >= 0.97:
            break
    if matched_slice and best_cov >= max(0.75, best_single_r):
      griffs = [x["griffith"] for x in matched_slice if x["griffith"]]
      padas = [x["pada"] for x in matched_slice if x["pada"]]
      p_joined = " ".join(padas).strip() if len(padas) == len(matched_slice) else ""
      results[idx] = {
        "griffith": " ".join(griffs).strip() if len(griffs) == len(matched_slice) else "",
        "vsm_pada": p_joined,
        "exact_pada_ok": best_cov >= 0.94 and bool(p_joined),
      }
      if best_cov < 0.78:
        unmatched_indices.append(idx)
    elif best_single and best_single_r >= 0.72:
      results[idx] = {
        "griffith": best_single["griffith"],
        "vsm_pada": best_single["pada"],
        "exact_pada_ok": best_single_r >= 0.94 and bool(best_single["pada"]),
      }
      if best_single_r < 0.78:
        unmatched_indices.append(idx)
    else:
      unmatched_indices.append(idx)

  _match_one_to_many_clauses(kandika_clauses, pool_subs, results, unmatched_indices)
  return results
