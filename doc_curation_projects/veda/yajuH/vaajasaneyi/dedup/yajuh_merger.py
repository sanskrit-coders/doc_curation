"""Extract shared non-Ṛk Yajuḥ blocks into `static/.../yajuH/sarva-prastutiH/` and link both VS-M and VS-K."""
from __future__ import annotations

import pathlib
import re
from collections import defaultdict
from typing import Sequence

from curation_utils import file_helper
from doc_curation.sanskrit.accent import us_converter
from doc_curation.sanskrit.accent.samhita_splitter import strip_vedic_accents
from indic_transliteration import sanscript

from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import (
  STATIC_URL_YAJUH,
  VSK_SARVA_DIR,
  VSM_SARVA_DIR,
  VSM_YAJUH_DIR,
  chapter_distance,
  normalize_phonetic,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.section_parser import (
  VskSubBlock,
  parse_vsk_section,
  render_js_include_stub,
  render_vsk_section,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import (
  merge_author_bodies,
  merge_sarva_tikaa_chunks,
)

_DEVA_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def _short_opening_words(vp: str, *, max_words: int = 3, max_chars: int = 36) -> str:
  bare = strip_vedic_accents(re.sub(r"\+\+\+.*?\+\+\+|\[\^[^\]]+\]", "", vp, flags=re.S))
  bare = re.sub(r"[०-९0-9\*।\.\,\!\?\|\-—–\(\)]+", " ", bare)
  out: list[str] = []
  total = 0
  for w in [x for x in bare.split() if x][:max_words]:
    if out and total + len(w) + 1 > max_chars:
      break
    out.append(w)
    total += len(w) + (1 if len(out) > 1 else 0)
  return " ".join(out) or "मन्त्रः"


def _make_yajuh_rel_path(vsm_ch: int, vsm_k: int, vp: str, used_rels: set[str]) -> str:
  stem = file_helper.get_storage_name(_short_opening_words(vp), source_script=sanscript.DEVANAGARI, max_length=45) or "mantraH"
  cand = f"{vsm_ch:02d}/{vsm_k:02d}_{stem}.md"
  suffix = 2
  while cand in used_rels:
    cand = f"{vsm_ch:02d}/{vsm_k:02d}_{stem}_{suffix}.md"
    suffix += 1
  used_rels.add(cand)
  return cand


def _ensure_yajuh_index_files(yajuh_dir: pathlib.Path, chapters: set[int]) -> None:
  for d, title in ((yajuh_dir.parent, "यजुः"), (yajuh_dir, "+सर्व-प्रस्तुतिः")):
    d.mkdir(parents=True, exist_ok=True)
    idx_f = d / "_index.md"
    if not idx_f.exists():
      idx_f.write_text(f'+++\ntitle = "{title}"\nunicode_script = "devanagari"\n+++\n', encoding="utf-8")
  for ch in sorted(chapters):
    ch_dir = yajuh_dir / f"{ch:02d}"
    ch_dir.mkdir(parents=True, exist_ok=True)
    ch_idx = ch_dir / "_index.md"
    if not ch_idx.exists():
      dev_ch = f"{ch:02d}".translate(_DEVA_DIGITS)
      ch_idx.write_text(f'+++\ntitle = "{dev_ch}"\nunicode_script = "devanagari"\n+++\n', encoding="utf-8")


def _load_vsm_non_rk_sections(vsm_dir: pathlib.Path) -> tuple[dict, list[dict]]:
  parsed_by_ch: dict = {}
  slots: list[dict] = []
  for ch in range(1, 41):
    parts = re.split(r"(?m)^(?=## )", (vsm_dir / f"{ch:02d}.md").read_text(encoding="utf-8"))
    sec_list: list[tuple[str, list[VskSubBlock]]] = []
    for k_idx, sec in enumerate(parts[1:], 1):
      _, subs = parse_vsk_section(sec, ch, k_idx)
      sec_list.append((sec, subs))
      vp_indices = [idx for idx, s in enumerate(subs) if not s.is_js_include and s.vp.strip()]
      trailing_idx = (
        vp_indices[0] + 1
        if len(vp_indices) == 1
        and len(subs) == vp_indices[0] + 2
        and not subs[-1].is_js_include
        and not subs[-1].vp.strip()
        and not subs[-1].av_blocks
        else None
      )
      for idx in vp_indices:
        s = subs[idx]
        pb = normalize_phonetic(s.vp, include_accents=False, fold_orthography=True)
        if len(pb) < 8:
          continue
        slots.append({
          "slot_id": len(slots), "ch": ch, "k": k_idx, "sub_idx": idx, "trailing_idx": trailing_idx,
          "vp": s.vp, "pb": pb, "pa": normalize_phonetic(s.vp, include_accents=True, fold_orthography=True),
        })
    parsed_by_ch[ch] = (parts[0], sec_list)
  return parsed_by_ch, slots


def _match_vsk_chapters_to_yajuh(
  vsk_dir: pathlib.Path,
  by_pa: dict[str, list[dict]],
  rk_set: set[str],
) -> tuple[dict[int, list[dict]], dict, int, int]:
  vsk_matches_by_slot: dict[int, list[dict]] = defaultdict(list)
  vsk_parsed_by_ch: dict = {}
  matched_vsk_blocks = 0
  merged_vsk_span2 = 0

  for ch in range(1, 41):
    parts = re.split(r"(?m)^(?=## )", (vsk_dir / f"{ch:02d}.md").read_text(encoding="utf-8"))
    sec_records = []
    for k_idx, sec in enumerate(parts[1:], 1):
      _, subs = parse_vsk_section(sec, ch, k_idx)
      repl: dict[int, tuple[int, int]] = {}
      used: set[int] = set()
      for sp in (2, 1):
        for j in range(len(subs) - sp + 1):
          if any(j + x in used or subs[j + x].is_js_include or not subs[j + x].vp.strip() for x in range(sp)):
            continue
          if sp == 2 and subs[j + 1].av_blocks:
            continue
          comb_vp = "  \n".join(subs[j + x].vp.strip() for x in range(sp))
          pb = normalize_phonetic(comb_vp, include_accents=False, fold_orthography=True)
          if len(pb) < 8 or pb in rk_set:
            continue
          cands = by_pa.get(normalize_phonetic(comb_vp, include_accents=True, fold_orthography=True))
          if not cands:
            continue
          sid = min(cands, key=lambda sl: (chapter_distance(ch, sl["ch"]), abs(k_idx - sl["k"])))["slot_id"]
          repl[j] = (sp, sid)
          used.update(range(j, j + sp))
          tika_kids = subs[j].tika_blocks if sp == 1 else _merge_two_tika_lists(subs[j].tika_blocks, subs[j + 1].tika_blocks)
          vsk_matches_by_slot[sid].append({"kandika_ref": f"{ch}.{k_idx}", "is_exact_reading": True, "vp": comb_vp, "tika_blocks": tika_kids})
          matched_vsk_blocks += 1
          merged_vsk_span2 += int(sp == 2)
      sec_records.append((sec, subs, repl))
    vsk_parsed_by_ch[ch] = (parts[0], sec_records)
  return vsk_matches_by_slot, vsk_parsed_by_ch, matched_vsk_blocks, merged_vsk_span2


def _rewrite_hosts_with_yajuh_includes(
  vsm_dir: pathlib.Path,
  vsk_dir: pathlib.Path,
  vsm_parsed: dict,
  vsm_slots: list[dict],
  vsk_parsed_by_ch: dict,
  slot_rel: dict[int, str],
) -> None:
  slots_by_vsm_sec: dict[tuple[int, int], list[dict]] = defaultdict(list)
  for sid in slot_rel:
    sl = vsm_slots[sid]
    slots_by_vsm_sec[(sl["ch"], sl["k"])].append(sl)
  for ch in range(1, 41):
    preamble, sec_list = vsm_parsed[ch]
    out_secs: list[str] = []
    ch_changed = False
    for k_idx, (orig_sec, subs) in enumerate(sec_list, 1):
      sec_hits = slots_by_vsm_sec.get((ch, k_idx))
      if not sec_hits:
        out_secs.append(orig_sec.rstrip() + "\n")
        continue
      ch_changed = True
      by_sub_idx = {sl["sub_idx"]: sl for sl in sec_hits}
      skip_trailing = {sl["trailing_idx"] for sl in sec_hits if sl["trailing_idx"] is not None}
      new_subs: list[VskSubBlock] = []
      for idx, sub in enumerate(subs):
        if idx in skip_trailing:
          continue
        if idx in by_sub_idx:
          stub = render_js_include_stub(f"{STATIC_URL_YAJUH}/{slot_rel[by_sub_idx[idx]['slot_id']]}", includetitle="false")
          new_subs.append(VskSubBlock(sub.av_blocks, "", [], is_js_include=True, raw_html=stub))
        else:
          new_subs.append(sub)
      out_secs.append(render_vsk_section(orig_sec.splitlines()[0].strip(), new_subs))
    if ch_changed:
      (vsm_dir / f"{ch:02d}.md").write_text(preamble + "\n".join(out_secs).rstrip() + "\n", encoding="utf-8")

  for ch in range(1, 41):
    preamble, sec_records = vsk_parsed_by_ch[ch]
    out_secs = []
    ch_changed = False
    for orig_sec, subs, repl in sec_records:
      if not repl:
        out_secs.append(orig_sec.rstrip() + "\n")
        continue
      ch_changed = True
      new_subs, j = [], 0
      while j < len(subs):
        if j in repl:
          sp, sid = repl[j]
          stub = render_js_include_stub(f"{STATIC_URL_YAJUH}/{slot_rel[sid]}", includetitle="false")
          new_subs.append(VskSubBlock(subs[j].av_blocks, "", [], is_js_include=True, raw_html=stub))
          j += sp
        else:
          new_subs.append(subs[j])
          j += 1
      out_secs.append(render_vsk_section(orig_sec.splitlines()[0].strip(), new_subs))
    if ch_changed:
      (vsk_dir / f"{ch:02d}.md").write_text(preamble + "\n".join(out_secs).rstrip() + "\n", encoding="utf-8")


def extract_and_link_shared_yajuh(
  vsm_dir: pathlib.Path = VSM_SARVA_DIR,
  vsk_dir: pathlib.Path = VSK_SARVA_DIR,
  yajuh_dir: pathlib.Path = VSM_YAJUH_DIR,
  rk_norm_set: set[str] | None = None,
  *,
  dry_run: bool = False,
) -> dict:
  """Extract common strict non-Ṛk blocks into `static/.../yajuH/sarva-prastutiH/` and link VS-M and VS-K."""
  rk_set = rk_norm_set or set()
  vsm_parsed, vsm_slots = _load_vsm_non_rk_sections(vsm_dir)
  by_pa: dict[str, list[dict]] = defaultdict(list)
  for sl in vsm_slots:
    if sl["pb"] not in rk_set:
      by_pa[sl["pa"]].append(sl)

  vsk_matches_by_slot, vsk_parsed_by_ch, matched_vsk_blocks, merged_vsk_span2 = _match_vsk_chapters_to_yajuh(
    vsk_dir, by_pa, rk_set,
  )
  used_rels: set[str] = set()
  slot_rel: dict[int, str] = {}
  touched_chapters: set[int] = set()
  for sid in sorted(vsk_matches_by_slot):
    sl = vsm_slots[sid]
    slot_rel[sid] = _make_yajuh_rel_path(sl["ch"], sl["k"], sl["vp"], used_rels)
    touched_chapters.add(sl["ch"])

  if not dry_run and slot_rel:
    _ensure_yajuh_index_files(yajuh_dir, touched_chapters)
    for sid, rel in slot_rel.items():
      _write_shared_yajuh_file(yajuh_dir / rel, vsm_slots[sid], vsm_parsed, vsk_matches_by_slot[sid])
    _rewrite_hosts_with_yajuh_includes(vsm_dir, vsk_dir, vsm_parsed, vsm_slots, vsk_parsed_by_ch, slot_rel)

  return {
    "yajuh_shared_files": len(slot_rel),
    "vsk_yajuh_blocks_linked": matched_vsk_blocks,
    "vsk_yajuh_span2_merged": merged_vsk_span2,
  }


def _merge_two_tika_lists(t1: Sequence[tuple[str, str]], t2: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
  d1, d2 = dict(t1), dict(t2)
  out: list[tuple[str, str]] = []
  for ttl in list(dict.fromkeys([t for t, _ in t1] + [t for t, _ in t2])):
    v1, v2 = d1.get(ttl, "").strip(), d2.get(ttl, "").strip()
    if ttl == "Griffith":
      val = " ".join(x for x in (v1, v2) if x)
    elif ttl == "मूलम्":
      val = (v1 + "  \n" + v2).strip() if (v1 and v2) else (v1 or v2)
    elif ttl == "पदपाठः":
      val = (re.sub(r"[।\s]*[०-९]+\s*।?\s*$", "", v1).strip() + " " + v2).strip() if (v1 and v2) else (v1 or v2)
    else:
      val = merge_author_bodies([v1, v2])
    if val:
      out.append((ttl, val))
  return out


def _write_shared_yajuh_file(
  target_path: pathlib.Path,
  slot: dict,
  vsm_parsed: dict,
  vsk_entries: Sequence[dict],
) -> None:
  _, sec_list = vsm_parsed[slot["ch"]]
  _, subs = sec_list[slot["k"] - 1]
  sub = subs[slot["sub_idx"]]
  vsm_tika = list(sub.tika_blocks)
  if slot["trailing_idx"] is not None:
    vsm_tika.extend(subs[slot["trailing_idx"]].tika_blocks)
  merged_tika_blocks = merge_sarva_tikaa_chunks([("details", pair) for pair in vsm_tika], vsk_entries)

  vp_us = us_converter.to_us_accents_markdown(slot["vp"], pauses=r"[।॥,;]+", preserve_existing_us=True).strip()
  dev_k = f"{slot['k']:02d}".translate(_DEVA_DIGITS)
  content = (
    f'+++\ntitle = "{dev_k} {_short_opening_words(vp_us)}"\nunicode_script = "devanagari"\n+++\n'
    f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{vp_us}\n</details>\n\n"
    "<details><summary>सर्वाष् टीकाः</summary>\n" + "\n".join(merged_tika_blocks) + "\n</details>\n"
  )
  target_path.parent.mkdir(parents=True, exist_ok=True)
  target_path.write_text(content, encoding="utf-8")
