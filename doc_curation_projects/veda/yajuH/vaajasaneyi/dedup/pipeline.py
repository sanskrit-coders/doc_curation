"""End-to-end orchestrator, include prefill refresher, and structural validator for VS-M / VS-K dedup."""
from __future__ import annotations

import pathlib
import re
from typing import Sequence

from doc_curation.md.content_processor.include import transformer
from doc_curation.sanskrit.accent.reconciler import find_js_include_spans

from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import (
  VSK_SARVA_DIR,
  VSM_RK_DIR,
  VSM_SARVA_DIR,
  VSM_YAJUH_DIR,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.rk_merger import (
  load_rk_index,
  match_and_rewrite_vsk_sections,
  merge_kanva_into_rk_tiikaa,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.yajuh_merger import (
  extract_and_link_shared_yajuh,
)

DEFAULT_INCLUDE_REPOS: tuple[pathlib.Path, ...] = (
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/devaH/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content"),
)


def refresh_all_prefills(
  roots: Sequence[pathlib.Path] = DEFAULT_INCLUDE_REPOS,
  rk_dir: pathlib.Path = VSM_RK_DIR,
  *,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
) -> dict:
  """Surgically refresh `vAjasaneyam/mAdhyandinam/saMhitA/{Rk,yajuH}` prefills across hosts and nested static."""
  files_updated = 0
  divs_updated = 0
  url_rx = r"vAjasaneyam/mAdhyandinam/saMhitA/(?:Rk|yajuH)/"

  # Refresh nested static js_includes (such as 17/70 referencing 12/02) first.
  for fp in sorted(rk_dir.rglob("*.md")):
    if not fp.is_file() or fp.name == "_index.md":
      continue
    txt = fp.read_text(encoding="utf-8")
    if "js_include" not in txt:
      continue
    new_txt, n = transformer.surgical_prefill_content(txt, str(fp), hugo_base_dir=hugo_base_dir)
    if n:
      fp.write_text(new_txt, encoding="utf-8")
      files_updated += 1
      divs_updated += n

  for root in roots:
    if not root.exists():
      continue
    for fp in sorted(root.rglob("*.md")):
      if not fp.is_file():
        continue
      txt = fp.read_text(encoding="utf-8", errors="ignore")
      if "vAjasaneyam/mAdhyandinam/saMhitA/" not in txt:
        continue
      new_txt, n = transformer.surgical_prefill_content(
        txt, str(fp), url_filter=url_rx, hugo_base_dir=hugo_base_dir,
      )
      if n:
        fp.write_text(new_txt, encoding="utf-8")
        files_updated += 1
        divs_updated += n
  return {"prefilled_files": files_updated, "prefilled_divs": divs_updated}


def run_full_vsk_vsm_dedup(
  *,
  vsm_sarva_dir: pathlib.Path = VSM_SARVA_DIR,
  vsk_sarva_dir: pathlib.Path = VSK_SARVA_DIR,
  vsm_rk_dir: pathlib.Path = VSM_RK_DIR,
  vsm_yajuh_dir: pathlib.Path = VSM_YAJUH_DIR,
  include_repos: Sequence[pathlib.Path] = DEFAULT_INCLUDE_REPOS,
  dry_run: bool = False,
) -> dict:
  """Run Ṛk matching/merging, shared non-Ṛk `yajuH` extraction, and prefill refreshes end-to-end."""
  rk_entries, grams = load_rk_index(vsm_rk_dir)
  rk_norm_set = {e["pb"] for e in rk_entries}

  merged_by_rk, rk_stats = match_and_rewrite_vsk_sections(vsk_sarva_dir, rk_entries, grams, dry_run=dry_run)
  rk_sarva_updated = 0
  for rel, entries in merged_by_rk.items():
    sarva_p = vsm_rk_dir / "sarvASh_TIkAH" / rel
    if sarva_p.is_file() and merge_kanva_into_rk_tiikaa(sarva_p, entries, dry_run=dry_run):
      rk_sarva_updated += 1

  yajuh_stats = extract_and_link_shared_yajuh(
    vsm_dir=vsm_sarva_dir, vsk_dir=vsk_sarva_dir, yajuh_dir=vsm_yajuh_dir,
    rk_norm_set=rk_norm_set, dry_run=dry_run,
  )

  prefill_stats = {"prefilled_files": 0, "prefilled_divs": 0}
  if not dry_run:
    prefill_stats = refresh_all_prefills(roots=include_repos, rk_dir=vsm_rk_dir)

  return {
    **rk_stats,
    "rk_sarva_files_updated": rk_sarva_updated,
    **yajuh_stats,
    **prefill_stats,
  }


def validate_dedup_integrity(
  *,
  vsm_sarva_dir: pathlib.Path = VSM_SARVA_DIR,
  vsk_sarva_dir: pathlib.Path = VSK_SARVA_DIR,
  vsm_rk_dir: pathlib.Path = VSM_RK_DIR,
  vsm_yajuh_dir: pathlib.Path = VSM_YAJUH_DIR,
  hugo_base_dir: pathlib.Path = pathlib.Path("/home/vvasuki/gitland/vishvAsa"),
) -> dict:
  """Verify tag balance, resolved include targets, and US accents across VS-M, VS-K, `Rk/`, and `yajuH/`."""
  issues: list[str] = []
  checked_files = 0
  checked_includes = 0

  scan_dirs = [vsm_sarva_dir, vsk_sarva_dir, vsm_rk_dir]
  if vsm_yajuh_dir.exists():
    scan_dirs.append(vsm_yajuh_dir)

  for root in scan_dirs:
    for fp in sorted(root.rglob("*.md")):
      if not fp.is_file():
        continue
      checked_files += 1
      txt = fp.read_text(encoding="utf-8")
      if len(re.findall(r"<details(?:\s+open)?>", txt)) != len(re.findall(r"</details>", txt)):
        issues.append(f"{fp}: unbalanced <details>")
      if len(re.findall(r"<div\b", txt)) != len(re.findall(r"</div>", txt)):
        issues.append(f"{fp}: unbalanced <div>")
      for s_pos, e_pos in find_js_include_spans(txt):
        checked_includes += 1
        m_url = re.search(r"""url=["']([^"']+)["']""", txt[s_pos:e_pos])
        if not m_url:
          issues.append(f"{fp}: js_include missing url")
          continue
        url = m_url.group(1)
        rel_parts = url.lstrip("/").split("/", 1)
        if len(rel_parts) == 2:
          tgt = hugo_base_dir / rel_parts[0] / "static" / rel_parts[1]
          if not tgt.is_file():
            issues.append(f"{fp}: broken include target {url}")

      # Check no dependent accents remain in static Rk/vishvAsa-prastutiH or yajuH VP blocks
      if vsm_rk_dir / "vishvAsa-prastutiH" in fp.parents and fp.name != "_index.md":
        if re.search(r"[\u0951\u0952]", txt):
          issues.append(f"{fp}: dependent accents remain in Rk vishvAsa-prastutiH")
      if vsm_yajuh_dir in fp.parents and fp.name != "_index.md":
        m_vp = re.search(r"<details open><summary>विश्वास-प्रस्तुतिः[^<]*</summary>(.*?)</details>", txt, flags=re.S)
        if not m_vp or re.search(r"[\u0951\u0952]", m_vp.group(1)):
          issues.append(f"{fp}: missing or non-US विश्वास-प्रस्तुतिः in yajuH")

  return {"checked_files": checked_files, "checked_includes": checked_includes, "issue_count": len(issues), "issues": issues[:50]}
