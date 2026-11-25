"""Rk matching, VS-M static commentary merging, and VS-K js_include replacement."""
from __future__ import annotations

import difflib
import pathlib
import re
from collections import defaultdict
from typing import Sequence

from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim

from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import (
  STATIC_URL_RK_TK,
  STATIC_URL_RK_VP,
  VSM_RK_DIR,
  chapter_distance,
  is_no_patha_bheda,
  normalize_phonetic,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.section_parser import (
  VskSubBlock,
  _split_top_level_chunks,
  merge_vsk_hemistich_pair,
  parse_vsk_section,
  render_js_include_stub,
  render_vsk_section,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import merge_sarva_tikaa_chunks


def load_rk_index(rk_dir: pathlib.Path = VSM_RK_DIR) -> tuple[list[dict], dict[str, set[int]]]:
  """Load all static `Rk/vishvAsa-prastutiH/` entries and build a 5-gram bare index."""
  vp_root = rk_dir / "vishvAsa-prastutiH"
  entries: list[dict] = []
  grams: dict[str, set[int]] = defaultdict(set)

  for fp in sorted(vp_root.rglob("*.md")):
    if not fp.is_file() or fp.name == "_index.md":
      continue
    rel = fp.relative_to(vp_root).as_posix()
    raw = fp.read_text(encoding="utf-8")
    if "js_include" in raw:
      m = re.search(r"</summary>(.*?)</details>", raw, flags=re.S)
      vp_body = m.group(1).strip() if m else split_frontmatter_verbatim(raw)[1].strip()
    else:
      vp_body = split_frontmatter_verbatim(raw)[1].strip()
    pb = normalize_phonetic(vp_body, include_accents=False, fold_orthography=True)
    m_ch = int(rel.split("/")[0])
    m_k_match = re.match(r"(\d+)", pathlib.Path(rel).name)
    m_k = int(m_k_match.group(1)) if m_k_match else 0
    idx = len(entries)
    entries.append({
      "rel": rel, "ch": m_ch, "k": m_k, "vp": vp_body, "pb": pb,
      "sarva_path": rk_dir / "sarvASh_TIkAH" / rel,
    })
    for pos in range(max(1, len(pb) - 4)):
      grams[pb[pos : pos + 5]].add(idx)
  return entries, grams


def _score_rk_candidate(
  cand_pb: str,
  first_clause_pb: str,
  span_len: int,
  vsk_ch: int,
  vsk_k: int,
  rk_entries: list[dict],
  grams: dict[str, set[int]],
) -> dict | None:
  if len(cand_pb) < 16:
    return None
  cands: dict[int, int] = defaultdict(int)
  for pos in range(max(1, len(cand_pb) - 4)):
    for ri in grams.get(cand_pb[pos : pos + 5], ()):
      cands[ri] += 1
  if not cands:
    return None
  top_indices = sorted(cands, key=lambda x: -cands[x])[:24]
  scored: list[tuple[float, int, int, int]] = []
  for ri in top_indices:
    ent = rk_entries[ri]
    rb = ent["pb"]
    if abs(len(rb) - len(cand_pb)) > max(18, int(0.28 * len(cand_pb))):
      continue
    ratio = 1.0 if cand_pb == rb else difflib.SequenceMatcher(None, cand_pb, rb).ratio()
    if ratio < 0.82:
      continue
    if span_len == 2:
      pref_r = difflib.SequenceMatcher(None, first_clause_pb, rb[: len(first_clause_pb) + 8]).ratio()
      if pref_r < 0.55:
        continue
    bucket = 1000 if ratio == 1.0 else round(ratio * 100)
    scored.append((bucket + ratio, -chapter_distance(vsk_ch, ent["ch"]), -abs(vsk_k - ent["k"]), ri))
  if not scored:
    return None
  scored.sort(reverse=True)
  return rk_entries[scored[0][3]]


def match_and_rewrite_vsk_sections(
  vsk_dir: pathlib.Path,
  rk_entries: list[dict],
  grams: dict[str, set[int]],
  *,
  dry_run: bool = False,
) -> tuple[dict[str, list[dict]], dict]:
  """Match VS-K blocks/hemistich-pairs to `static/Rk`, merge hemistichs, and rewrite VS-K with `js_include`s."""
  merged_by_rk: dict[str, list[dict]] = defaultdict(list)
  stats = {"rk_exact_blocks": 0, "rk_variant_blocks": 0, "hemistich_pairs_merged": 0}

  for ch in range(1, 41):
    fp = vsk_dir / f"{ch:02d}.md"
    txt = fp.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^(?=## )", txt)
    out_secs: list[str] = []

    for k_idx, sec in enumerate(parts[1:], 1):
      heading, subs = parse_vsk_section(sec, ch, k_idx)
      sub_pbs = [
        "" if sub.is_js_include else normalize_phonetic(sub.vp, include_accents=False, fold_orthography=True)
        for sub in subs
      ]
      matched_spans: dict[int, tuple[int, dict]] = {}
      used: set[int] = set()
      for span_len in (2, 1):
        for j in range(len(subs) - span_len + 1):
          if any(j + x in used or subs[j + x].is_js_include or not sub_pbs[j + x] for x in range(span_len)):
            continue
          cand_pb = "".join(sub_pbs[j + x] for x in range(span_len))
          hit = _score_rk_candidate(cand_pb, sub_pbs[j], span_len, ch, k_idx, rk_entries, grams)
          if hit is not None:
            matched_spans[j] = (span_len, hit)
            for x in range(span_len):
              used.add(j + x)

      new_subs: list[VskSubBlock] = []
      j = 0
      while j < len(subs):
        if j in matched_spans:
          span_len, hit = matched_spans[j]
          if span_len == 2:
            nxt = subs[j + 2] if j + 2 < len(subs) else None
            stanza, nxt_upd = merge_vsk_hemistich_pair(subs[j], subs[j + 1], nxt)
            if nxt_upd is not None and j + 2 < len(subs):
              subs[j + 2] = nxt_upd
            stats["hemistich_pairs_merged"] += 1
          else:
            stanza = subs[j]

          rel = hit["rel"]
          exact = is_no_patha_bheda(stanza.vp, hit["vp"])
          merged_by_rk[rel].append({
            "kandika_ref": f"{ch}.{k_idx}",
            "is_exact_reading": exact,
            "vp": stanza.vp,
            "tika_blocks": stanza.tika_blocks,
          })
          vp_url = f"{STATIC_URL_RK_VP}/{rel}"
          tk_url = f"{STATIC_URL_RK_TK}/{rel}"
          tk_stub = render_js_include_stub(tk_url, title="सर्वाष् टीकाः", collapsed=True)
          if exact:
            vp_stub = render_js_include_stub(vp_url, title="विश्वास-प्रस्तुतिः", collapsed=False)
            new_subs.append(
              VskSubBlock(
                av_blocks=stanza.av_blocks, vp="", tika_blocks=[],
                is_js_include=True, raw_html=f"{vp_stub}\n{tk_stub}",
                kandika_ref=stanza.kandika_ref,
              )
            )
            stats["rk_exact_blocks"] += 1
          else:
            new_subs.append(
              VskSubBlock(
                av_blocks=stanza.av_blocks, vp=stanza.vp, tika_blocks=[],
                is_js_include=True, raw_html=tk_stub,
                kandika_ref=stanza.kandika_ref,
              )
            )
            stats["rk_variant_blocks"] += 1
          j += span_len
        else:
          new_subs.append(subs[j])
          j += 1
      out_secs.append(render_vsk_section(heading, new_subs))

    if not dry_run:
      fp.write_text(parts[0] + "\n".join(out_secs).rstrip() + "\n", encoding="utf-8")
  return dict(merged_by_rk), stats


def merge_kanva_into_rk_tiikaa(
  rk_sarva_path: pathlib.Path,
  vsk_entries: Sequence[dict],
  *,
  dry_run: bool = False,
) -> bool:
  """Merge Kāṇva Mūlam, Padapāṭha, Sāyaṇa (काण्वी), Ānandabodha, Anantācārya into a `static/Rk/sarvASh_TIkAH/` file."""
  raw = rk_sarva_path.read_text(encoding="utf-8")
  fm, body = split_frontmatter_verbatim(raw)
  chunks = _split_top_level_chunks(body)
  out_blocks = merge_sarva_tikaa_chunks(chunks, vsk_entries)
  new_raw = (fm.rstrip() + "\n" if fm else "") + "\n".join(out_blocks).rstrip() + "\n"
  if new_raw == raw:
    return False
  if not dry_run:
    rk_sarva_path.write_text(new_raw, encoding="utf-8")
  return True
