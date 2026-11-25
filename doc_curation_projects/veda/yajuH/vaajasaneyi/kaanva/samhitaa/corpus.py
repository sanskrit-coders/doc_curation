"""VS-K alignment orchestration, Markdown rendering, coverage summary, and corpus validation."""
from __future__ import annotations

import pathlib
import re
from collections import defaultdict
from typing import Mapping, Sequence

from doc_curation.sanskrit.accent import samhita_splitter
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import (
  _VP_STRIP_RE,
  KANVA_AVATARIKA_SPECS,
  KANVA_PDF_DIR,
  KANVA_TIKA_SPECS,
  VSK_SAMHITA_DIR,
  VSK_SARVA_PRASTUTI_DIR,
  VSM_SARVA_PRASTUTI_DIR,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.padapatha import (
  reconcile_and_split_padapatha,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.prose_clean import (
  clean_raw_bhashya_text,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.repair import (
  build_kandika_heading,
  load_vsk_repaired_kandikas,
  normalize_vsk_text,
  split_kandika_clauses,
  to_devanagari_ordinal,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.ssu_indike import (
  align_vsm_blocks_to_kandikas,
  build_indike_sayana_fallback,
  parse_ssu_1978_sayana,
  parse_ssu_2011_vol4,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.vsm_matcher import (
  build_vsm_index,
  match_vsm_clauses,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.vsm_ocr import (
  _split_author_blocks_vsm,
  clean_vsm_lines,
  slice_vsm_volume_chapters,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina.samhitaa import bhashya_aligner


def hyphenate_vsk_vp_clauses(sub_vps: list[str], sub_padas: list[str]) -> list[str]:
  """Hyphenate VS-K ``विश्वास-प्रस्तुतिः`` guided cleanly by verified ``पदपाठः``."""
  out: list[str] = []
  for vp, pada in zip(sub_vps, sub_padas):
    hyp = samhita_splitter.hyphenate_samhita_with_padapatha(vp, pada)
    out.append(normalize_vsk_text(hyp, is_vp=True))
  return out


def plan_kanva_kandika_alignment(
  bhashyas_by_author: Mapping[str, str],
  cores: list[str],
  *,
  kandika_key: str,
) -> list[dict[str, dict[str, str]]]:
  """Split Sāyaṇa, Ānandabodha, and Anantācārya into avatārikā, viniyoga, and ṭīkā per sense unit."""
  n = len(cores)
  authors = ("sayana", "anandabodha", "anantacharya")
  non_pranava_idx = [
    i for i, c in enumerate(cores)
    if re.sub(r"[ॐओ३म्।॥\s]", "", _VP_STRIP_RE.sub("", c))
  ] or list(range(n))
  align_cores = [cores[i] for i in non_pranava_idx]

  clusters: list[dict[str, dict[str, str]]] = [{a: {} for a in authors} for _ in range(n)]
  for auth in authors:
    raw = (bhashyas_by_author.get(auth) or "").strip()
    cleaned = clean_raw_bhashya_text(raw, hyphenate=True) if raw else ""
    segs = bhashya_aligner._split_ka_sentences(cleaned) if cleaned else []
    assigned = bhashya_aligner._assign_segments_to_submantras(segs, align_cores, author=auth)
    for k_sub, real_i in enumerate(non_pranava_idx):
      by_role: dict[str, list[str]] = defaultdict(list)
      for item in assigned[k_sub]:
        by_role[item["role"]].append(item["text"])
      for role in ("avatarika", "viniyoga", "tika"):
        if by_role[role]:
          clusters[real_i][auth][role] = "\n\n".join(by_role[role])
  return clusters


def render_vsk_kandika_section(
  heading: str,
  sub_vps: list[str],
  sub_mulas: list[str],
  sub_griffs: list[str],
  sub_padas: list[str],
  plan: list[dict[str, dict[str, str]]],
) -> str:
  """Render one VS-K ``## NN pratīka`` section matching VS-M formatting conventions."""
  lines: list[str] = [heading.strip()]
  for i, (vp, mula) in enumerate(zip(sub_vps, sub_mulas)):
    cluster = plan[i] if i < len(plan) else {}
    upper = bhashya_aligner._format_sarva_avatarikah(cluster, author_specs=KANVA_AVATARIKA_SPECS)
    if upper:
      lines.append(upper.rstrip("\n"))
    lines.append(f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{vp.strip()}\n</details>\n")

    tika_kids: list[str] = []
    griff = sub_griffs[i].strip() if i < len(sub_griffs) else ""
    if griff:
      tika_kids.append(bhashya_aligner._format_details_block("Griffith", griff))
    tika_kids.append(bhashya_aligner._format_details_block("मूलम्", mula.strip()))
    pada = sub_padas[i].strip() if i < len(sub_padas) else ""
    if pada:
      tika_kids.append(bhashya_aligner._format_details_block("पदपाठः", pada))
    for auth_key, label in KANVA_TIKA_SPECS:
      t_body = cluster.get(auth_key, {}).get("tika", "").strip()
      if t_body:
        tika_kids.append(bhashya_aligner._format_details_block(label, t_body))
    lines.append("<details><summary>सर्वाष् टीकाः</summary>\n" + "\n".join(tika_kids) + "\n</details>")
  return "\n".join(lines).rstrip() + "\n"


def collect_all_vsk_sources(
  kandikas_by_ch: dict[int, list[dict]],
  *,
  pdf_dir: pathlib.Path = KANVA_PDF_DIR,
  indike_sayana_path: pathlib.Path | None = None,
) -> dict[tuple[int, int], dict[str, str]]:
  """Collect `(ch, k) -> {'pada', 'sayana', 'anandabodha', 'anantacharya'}` across Vols 1–4 + SSU 1978."""
  merged: dict[tuple[int, int], dict[str, str]] = defaultdict(
    lambda: {"pada": "", "sayana": "", "anandabodha": "", "anantacharya": ""}
  )
  vol_specs = [
    (pdf_dir / "b-r-sharmA_kANva-saMhitA_1.pdf.txt", range(1, 11), ("sayana", "anandabodha")),
    (pdf_dir / "b-r-sharmA_kANva-saMhitA_2.pdf.txt", range(11, 21), ("sayana", "anandabodha")),
    (pdf_dir / "b-r-sharmA_kANva-saMhitA_3.pdf.txt", range(21, 31), ("anandabodha", "anantacharya")),
  ]
  for txt_p, ch_rng, auths in vol_specs:
    if not txt_p.exists():
      continue
    slices = slice_vsm_volume_chapters(clean_vsm_lines(txt_p.read_text(encoding="utf-8")), ch_rng)
    for ch in ch_rng:
      aligned = align_vsm_blocks_to_kandikas(ch, _split_author_blocks_vsm(slices[ch], authors=auths), kandikas_by_ch[ch], authors=auths)
      for k_num, rec in aligned.items():
        tgt = merged[(ch, k_num)]
        for field in ("pada", *auths):
          if rec.get(field):
            tgt[field] = rec[field]

  ssu78_p = pdf_dir / "kANva-saMhitA-bhAShyam.pdf.txt"
  if ssu78_p.exists():
    for (ch, k_num), rec in parse_ssu_1978_sayana(ssu78_p, kandikas_by_ch).items():
      tgt = merged[(ch, k_num)]
      if rec.get("sayana") and not tgt["sayana"]:
        tgt["sayana"] = rec["sayana"]
      if rec.get("pada") and not tgt["pada"]:
        tgt["pada"] = rec["pada"]

  vol4_p = pdf_dir / "dvivedI_kANva-saMhitA-bhAShya-sangrahaH_4.pdf.txt"
  if vol4_p.exists():
    for (ch, k_num), txt in parse_ssu_2011_vol4(vol4_p, kandikas_by_ch).items():
      if txt and not merged[(ch, k_num)]["anandabodha"]:
        merged[(ch, k_num)]["anandabodha"] = txt

  if indike_sayana_path and indike_sayana_path.exists():
    for (ch, k_num), txt in build_indike_sayana_fallback(indike_sayana_path, kandikas_by_ch).items():
      if txt and not merged[(ch, k_num)]["sayana"]:
        merged[(ch, k_num)]["sayana"] = txt
  return dict(merged)


def format_vsk_coverage_block(stats: dict) -> str:
  """Format the `Commentary coverage` block for `sarva-prastutiH/_index.md` from observed counts."""
  def _fmt(refs: list[str], limit: int = 30) -> str:
    if not refs:
      return "none"
    return ", ".join(refs) if len(refs) <= limit else ", ".join(refs[:limit]) + f", ... ({len(refs)} total)"

  tot, cl_tot = stats["total_kandikas"], stats["total_clauses"]
  return "\n".join([
    "<details><summary>Commentary coverage</summary>",
    "",
    f"- **Total kaṇḍikās:** {tot:,} across 40 chapters ({cl_tot:,} sense-unit `विश्वास-प्रस्तुतिः`/`मूलम्` blocks).",
    f"- **Sāyaṇa (`सायण-टीका`):** present in {stats['sayana']:,} / {tot:,} kaṇḍikās (Ch 1–20 VSM Vols 1–2 with Indike fallback; Ch 21–40 SSU 1978 Athagarh palm-leaf edition). Unaligned: {_fmt(stats.get('missing_sayana_refs', []))}.",
    f"- **Ānandabodha (`आनन्दबोध-टीका`):** present in {stats['anandabodha']:,} / {tot:,} kaṇḍikās (Ch 1–30 VSM Vols 1–3; Ch 31–40 SSU 2011 Vol 4 `भाष्यसंग्रहः`, skipping Pratyaṅgirāsūkta appendix). Unaligned: {_fmt(stats.get('missing_anandabodha_refs', []))}.",
    f"- **Anantācārya (`अनन्ताचार्य-टीका`):** present in {stats['anantacharya']:,} / {stats['anantacharya_scope']:,} kaṇḍikās in Ch 21–30 (VSM Vol 3 `वेदार्थदीपिका`; absent outside Ch 21–30 in printed sources). Unaligned in Ch 21–30: {_fmt(stats.get('missing_anantacharya_refs', []))}.",
    f"- **Griffith (`Griffith`):** aligned from VS-M `sarva-prastutiH` on {stats['griffith_clauses']:,} / {cl_tot:,} sense-unit blocks (absent for unique Kāṇva mantras/clauses without Mādhyandina equivalents).",
    f"- **Padapāṭha (`पदपाठः`):** populated on {stats['pada_populated_clauses']:,} / {cl_tot:,} sense-unit blocks ({stats['pada_verified_clauses']:,} verified forward-sandhi clean against `मूलम्` via `sandhi_check`).",
    "</details>",
    "",
  ])


def _render_single_chapter(ch: int, ch_k: list[dict], sources: dict, vsm_idx: dict, stats: dict) -> str:
  """Render one complete VS-K chapter Markdown file and accumulate per-chapter & total stats."""
  sec_texts: list[str] = [f'+++\ntitle = "{to_devanagari_ordinal(ch)}"\n+++\n']
  ch_stats = {"kandikas": len(ch_k), "sayana": 0, "anandabodha": 0, "anantacharya": 0, "clauses": 0, "pada_verified": 0, "griffith": 0}
  for kr in ch_k:
    k_num, loc = kr["k"], kr["loc"]
    src = sources.get((ch, k_num), {})
    clauses = split_kandika_clauses(kr)
    raw_vps, raw_mulas = [vp for vp, _ in clauses], [m for _, m in clauses]
    vsm_matches = match_vsm_clauses(clauses, vsm_idx, ch_hint=ch)
    sub_griffs = [m["griffith"] for m in vsm_matches]
    sub_padas, verified = reconcile_and_split_padapatha(src.get("pada", ""), raw_mulas, vsm_matches)
    sub_vps = hyphenate_vsk_vp_clauses(raw_vps, sub_padas)
    plan = plan_kanva_kandika_alignment(src, [m.split("##")[0].strip() for m in raw_mulas], kandika_key=loc)
    heading_vp = next((v for v in raw_vps if re.sub(r"[ॐओ३म्।॥\s]", "", _VP_STRIP_RE.sub("", v))), kr["vp_full"])
    sec_texts.append(render_vsk_kandika_section(build_kandika_heading(k_num, heading_vp), sub_vps, raw_mulas, sub_griffs, sub_padas, plan))

    stats["total_kandikas"] += 1
    stats["total_clauses"] += len(clauses)
    ch_stats["clauses"] += len(clauses)
    g_n = sum(1 for g in sub_griffs if g)
    pv_n = sum(1 for v in verified if v)
    stats["griffith_clauses"] += g_n
    ch_stats["griffith"] += g_n
    stats["pada_verified_clauses"] += pv_n
    ch_stats["pada_verified"] += pv_n
    stats["pada_populated_clauses"] += sum(1 for p in sub_padas if p.strip())
    for field, miss_key in (("sayana", "missing_sayana_refs"), ("anandabodha", "missing_anandabodha_refs")):
      if src.get(field):
        stats[field] += 1
        ch_stats[field] += 1
      else:
        stats[miss_key].append(loc)
    if 21 <= ch <= 30:
      stats["anantacharya_scope"] += 1
      if src.get("anantacharya"):
        stats["anantacharya"] += 1
        ch_stats["anantacharya"] += 1
      else:
        stats["missing_anantacharya_refs"].append(loc)

  stats["per_chapter"][ch] = ch_stats
  return "\n\n".join(sec_texts).rstrip() + "\n"


def build_and_write_vsk_corpus(
  indike_all40_path: pathlib.Path,
  *,
  indike_sayana_path: pathlib.Path | None = None,
  vsm_sarva_dir: pathlib.Path = VSM_SARVA_PRASTUTI_DIR,
  vsk_samhita_dir: pathlib.Path = VSK_SAMHITA_DIR,
  pdf_dir: pathlib.Path = KANVA_PDF_DIR,
  out_sarva_dir: pathlib.Path | None = None,
  chapters: Sequence[int] | None = None,
  remove_old_top_chapters: bool = False,
) -> dict:
  """Build & write all VS-K `sarva-prastutiH/{01..40}.md` plus `_index.md` files and return coverage stats."""
  target_dir = out_sarva_dir or (vsk_samhita_dir / "sarva-prastutiH")
  target_dir.mkdir(parents=True, exist_ok=True)
  raw_dir = vsk_samhita_dir
  if raw_dir != VSK_SAMHITA_DIR and not any(raw_dir.glob("??.md")):
    raw_dir = VSK_SAMHITA_DIR

  kandikas_by_ch = load_vsk_repaired_kandikas(indike_all40_path, vsk_dir=raw_dir)
  vsm_idx = build_vsm_index(vsm_sarva_dir)
  sources = collect_all_vsk_sources(kandikas_by_ch, pdf_dir=pdf_dir, indike_sayana_path=indike_sayana_path)
  stats = {
    "total_kandikas": 0, "sayana": 0, "anandabodha": 0, "anantacharya": 0, "anantacharya_scope": 0,
    "total_clauses": 0, "griffith_clauses": 0, "pada_verified_clauses": 0, "pada_populated_clauses": 0,
    "missing_sayana_refs": [], "missing_anandabodha_refs": [], "missing_anantacharya_refs": [], "per_chapter": {},
  }
  for ch in (list(chapters) if chapters is not None else list(range(1, 41))):
    (target_dir / f"{ch:02d}.md").write_text(
      _render_single_chapter(ch, kandikas_by_ch[ch], sources, vsm_idx, stats), encoding="utf-8"
    )
  if chapters is None:
    (target_dir / "_index.md").write_text('+++\ntitle = "+सर्व-प्रस्तुतिः"\n+++\n\n' + format_vsk_coverage_block(stats), encoding="utf-8")
    sa_index = vsk_samhita_dir / "_index.md"
    if not sa_index.exists():
      sa_index.write_text('+++\ntitle = "+संहिता"\nunicode_script = "devanagari"\n+++\n', encoding="utf-8")
    if remove_old_top_chapters:
      for ch in range(1, 41):
        old_f = vsk_samhita_dir / f"{ch:02d}.md"
        if old_f.exists():
          old_f.unlink()
  return stats


def validate_vsk_corpus(sarva_dir: pathlib.Path = VSK_SARVA_PRASTUTI_DIR) -> dict:
  """Validate all VS-K chapters via `validate_samhita_markdown` & `<details>` balance."""
  issues: list[str] = []
  ch_count = 0
  for p in sorted(sarva_dir.glob("[0-9][0-9].md")):
    ch_count += 1
    txt = p.read_text(encoding="utf-8")
    if len(re.findall(r"<details(?:\s+open)?>", txt)) != len(re.findall(r"</details>", txt)):
      issues.append(f"{p.name}: unbalanced <details> tags")
    for e in samhita_splitter.validate_samhita_markdown(txt, doc_id=p.stem, check_griffith=False, allow_empty_pada=True):
      issues.append(f"{p.name}: [{e.kind}] {e.location}: {e.message}")
  return {"chapters": ch_count, "issue_count": len(issues), "issues": issues[:50]}
