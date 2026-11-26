"""Cross-Veda and intra-Paippalāda deduplication for Atharvaveda Paippalāda Saṁhitā.

Stages:
1. Cross-Veda cascade (``AV-P -> RV, AV, VS-M, VS-K, TS, TB, TK, MS, KS, SB-M, SB-K``)
   using ``doc_curation_projects.veda.dedup.cascade.run_stage_cascade``.
2. Intra-Paippalāda self-repeat deduplication promoting repeated local mantras (>= 2
   occurrences across or within sūktas, excluding accented/manual/lacunose clusters) to
   ``vedAH/static/atharva/paippalAdam/saMhitA/{Rk,yajuH}/{vishvAsa-prastutiH,sarvASh_TIkAH}/``.
3. Single-caller static cleanup + transitive ``js_include`` prefill propagation.
"""
from __future__ import annotations

import pathlib
import re
from collections import defaultdict
from collections.abc import Sequence

from doc_curation.md.content_processor.include import transformer
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim

from doc_curation_projects.veda.atharva.paippalaadam.prepare import (
  DEFAULT_HUGO_BASE,
  _collect_all_vishvasa_scan_roots,
)
from doc_curation_projects.veda.dedup import cascade, static_fixer
from doc_curation_projects.veda.dedup.block_parser import (
  format_details_block,
  format_vp_summary_with_kind,
  group_mantra_units,
  render_host_include_pair,
  render_tokens,
  replace_group_tokens,
  tokenize_markdown_body,
)
from doc_curation_projects.veda.dedup.matcher import classify_unit_kind
from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec, load_corpus_specs
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import (
  format_static_title_and_stem,
  normalize_phonetic,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import (
  merge_author_bodies,
)

DEFAULT_UPSTREAM_TARGETS: tuple[str, ...] = (
  "RV",
  "AV",
  "VS-M",
  "VS-K",
  "TS",
  "TB",
  "TK",
  "MS",
  "KS",
  "SB-M",
  "SB-K",
)

_MIN_SELF_REPEAT_PB_LEN = 20
_US_ACCENT_RE = re.compile(r"[\u1cd3\u1cd9]")
_RUBRIC_PRATIKA_RE = re.compile(
  r"(?:इति|इत्य्)\s+(?:एका|द्वे|तिस्रः|चतस्रः|पञ्च|षट्|सप्त|अष्ट|नव|दश)\s*[।॥\s]*$"
)


def _self_repeat_key(vp_text: str) -> tuple[str, str] | None:
  """Return canonical dedup key for an AV-P mantra, or None if ineligible for merging."""
  if any(marker in vp_text for marker in ("…", "[[", "**", "+++")):
    return None
  if _RUBRIC_PRATIKA_RE.search(vp_text.strip()):
    return None
  pb = normalize_phonetic(vp_text, include_accents=False, fold_orthography=True)
  if len(pb) < _MIN_SELF_REPEAT_PB_LEN:
    return None
  if _US_ACCENT_RE.search(vp_text):
    return ("acc", normalize_phonetic(vp_text, include_accents=True, fold_orthography=True))
  return ("bare", pb)


def _merge_tika_item_lists(item_lists: Sequence[Sequence[tuple[str, str]]]) -> list[tuple[str, str]]:
  """Combine commentary ``(title, body)`` lists in deterministic order with deduplication."""
  ordered_titles: list[str] = []
  by_title: dict[str, list[str]] = {}
  for items in item_lists:
    for ttl, body in items:
      t_clean = ttl.strip()
      b_clean = body.strip()
      if not t_clean or not b_clean:
        continue
      if t_clean not in by_title:
        ordered_titles.append(t_clean)
        by_title[t_clean] = []
      by_title[t_clean].append(b_clean)
  out: list[tuple[str, str]] = []
  for ttl in ordered_titles:
    merged = merge_author_bodies(by_title[ttl], strip_trivial_crossref=False, include_accents=True)
    if merged:
      out.append((ttl, merged))
  return out


def _build_paippalada_caller_roots(
  hugo_base_dir: pathlib.Path,
  specs: dict[str, VedaCorpusSpec],
) -> list[pathlib.Path]:
  roots: list[pathlib.Path] = []
  seen: set[pathlib.Path] = set()
  for p in [*cascade.default_caller_roots(specs), *_collect_all_vishvasa_scan_roots(hugo_base_dir)]:
    rp = p.resolve()
    if rp.exists() and rp not in seen:
      seen.add(rp)
      roots.append(rp)
  return roots


def dedup_avp_self_repeats(
  avp_spec: VedaCorpusSpec,
  caller_roots: Sequence[pathlib.Path],
  *,
  hugo_base_dir: pathlib.Path = DEFAULT_HUGO_BASE,
  dry_run: bool = False,
) -> dict:
  """Extract repeated local AV-P mantras (>= 2 callers) into static ``{Rk,yajuH}/`` files."""
  stats: dict = {
    "self_repeat_clusters": 0,
    "self_repeat_callers": 0,
    "linked_to_existing_static": 0,
    "promoted_new_static": 0,
    "sample_clusters": [],
  }
  if avp_spec.content_dir is None or not avp_spec.content_dir.is_dir():
    return stats

  # 1. Index existing 2-part static AV-P entries so identical inline mantras link directly.
  existing_static: dict[tuple[str, str], tuple[str, pathlib.Path, str, str]] = {}
  for tree_kind, vp_dir, sarva_dir, vp_pref, sarva_pref in cascade._iter_two_part_trees(avp_spec):
    unit_kind = "rk" if tree_kind == "rk_2part" else "yajuh"
    for vp_fp in cascade._iter_md_files(vp_dir):
      assert vp_dir is not None and sarva_dir is not None
      rel = vp_fp.relative_to(vp_dir).as_posix()
      sv_fp = sarva_dir / rel
      vp_raw = split_frontmatter_verbatim(vp_fp.read_text(encoding="utf-8"))[1].strip()
      if "js_include" in vp_raw:
        continue
      k = _self_repeat_key(vp_raw)
      if k is not None and k not in existing_static:
        existing_static[k] = (unit_kind, sv_fp, f"{vp_pref}/{rel}", f"{sarva_pref}/{rel}")

  # 2. Collect inline mantra groups from content_dir.
  parsed_files: dict[pathlib.Path, tuple[str, list, list, int, str]] = {}
  occs_by_key: dict[tuple[str, str], list[tuple[pathlib.Path, int]]] = defaultdict(list)

  for c_fp in cascade._iter_md_files(avp_spec.content_dir):
    raw = c_fp.read_text(encoding="utf-8")
    fm, body = split_frontmatter_verbatim(raw)
    tokens = tokenize_markdown_body(body)
    groups = group_mantra_units(tokens)
    h_lvl = cascade._detect_heading_level(raw, avp_spec)
    rel_parent = c_fp.relative_to(avp_spec.content_dir).with_suffix("").as_posix()
    parsed_files[c_fp] = (fm, tokens, groups, h_lvl, rel_parent)
    for gi, grp in enumerate(groups):
      if grp.is_vp_include or grp.sarva_include_url or not grp.vp_text.strip():
        continue
      k = _self_repeat_key(grp.vp_text)
      if k is not None:
        occs_by_key[k].append((c_fp, gi))

  # 3. Promote repeated clusters (>= 2 inline occurrences, or >= 1 matching existing static).
  used_rels: set[str] = set()
  for _, vp_dir, _, _, _ in cascade._iter_two_part_trees(avp_spec):
    for fp in cascade._iter_md_files(vp_dir):
      assert vp_dir is not None
      used_rels.add(fp.relative_to(vp_dir).as_posix())

  # Map host_fp -> [(gi, unit_kind, vp_url, sarva_url), ...]
  host_replacements: dict[pathlib.Path, list[tuple[int, str, str, str]]] = defaultdict(list)
  changed_paths: list[str] = []

  for key, occs in sorted(occs_by_key.items(), key=lambda kv: (kv[1][0][0].as_posix(), kv[1][0][1])):
    if key not in existing_static and len(occs) < 2:
      continue

    all_tika_lists = [parsed_files[fp][2][gi].inline_tika_items for fp, gi in occs]
    merged_tikas = _merge_tika_item_lists(all_tika_lists)

    if key in existing_static:
      unit_kind, sv_fp, vp_url, sarva_url = existing_static[key]
      if sv_fp.is_file() and merged_tikas:
        sv_fm, sv_body = split_frontmatter_verbatim(sv_fp.read_text(encoding="utf-8"))
        existing_items = [
          (d[0], d[1]) for ck, d in cascade._split_top_level_chunks(sv_body) if ck == "details"  # type: ignore[index]
        ]
        combined_items = _merge_tika_item_lists([existing_items, merged_tikas])
        new_sv_body = "\n\n".join(format_details_block(t, b) for t, b in combined_items)
        new_sv = (sv_fm.rstrip() + "\n\n" if sv_fm else "") + new_sv_body + "\n"
        old_sv = sv_fp.read_text(encoding="utf-8")
        if new_sv != old_sv and not dry_run:
          if not cascade._balanced_tags(new_sv):
            raise ValueError(f"Unbalanced tags in existing AV-P sarva {sv_fp}")
          sv_fp.write_text(new_sv, encoding="utf-8")
          changed_paths.append(str(sv_fp))
      stats["linked_to_existing_static"] += 1
    else:
      fp0, gi0 = occs[0]
      _, _, groups0, _, rel_parent = parsed_files[fp0]
      grp0 = groups0[gi0]
      unit_kind = "rk" if classify_unit_kind(grp0.vp_text, summary=grp0.vp_summary, default_brahmana=False) == "rk" else "yajuh"
      vp_dir_t, sv_dir_t, vp_pref_t, sv_pref_t, _ = cascade._resolve_two_part_dirs(avp_spec, unit_kind)
      num_str = f"{gi0 + 1:02d}"
      title_txt, stem = format_static_title_and_stem(grp0.vp_text, num_prefix=num_str)
      cand_rel = f"{rel_parent}/{num_str}_{stem}.md"
      suffix_n = 2
      while cand_rel in used_rels:
        cand_rel = f"{rel_parent}/{num_str}_{stem}_{suffix_n}.md"
        suffix_n += 1
      used_rels.add(cand_rel)

      vp_dest = vp_dir_t / cand_rel
      sv_dest = sv_dir_t / cand_rel
      vp_url = f"{vp_pref_t}/{cand_rel}"
      sarva_url = f"{sv_pref_t}/{cand_rel}"
      fm_hdr = f'+++\ntitle = "{title_txt}"\nunicode_script = "devanagari"\n+++\n\n'
      sarva_blocks_md = "\n\n".join(format_details_block(t, b) for t, b in merged_tikas)
      if not dry_run:
        vp_dest.parent.mkdir(parents=True, exist_ok=True)
        sv_dest.parent.mkdir(parents=True, exist_ok=True)
        vp_dest.write_text(fm_hdr + grp0.vp_text.strip() + "\n", encoding="utf-8")
        sv_dest.write_text(fm_hdr + (sarva_blocks_md + "\n" if sarva_blocks_md else ""), encoding="utf-8")
        changed_paths.extend([str(vp_dest), str(sv_dest)])
      stats["promoted_new_static"] += 1

    stats["self_repeat_clusters"] += 1
    stats["self_repeat_callers"] += len(occs)
    if len(stats["sample_clusters"]) < 20:
      stats["sample_clusters"].append((occs[0][0].relative_to(avp_spec.content_dir).as_posix(), occs[0][1], len(occs), vp_url))

    for fp, gi in occs:
      host_replacements[fp].append((gi, unit_kind, vp_url, sarva_url))

  for c_fp, reps in sorted(host_replacements.items()):
    fm, tokens, groups, h_lvl, _ = parsed_files[c_fp]
    for gi, unit_kind, vp_url, sarva_url in reps:
      grp = groups[gi]
      vp_hdr = format_vp_summary_with_kind("विश्वास-प्रस्तुतिः", unit_kind)
      new_vp, new_tk = render_host_include_pair(
        exact_reading=True,
        local_vp_summary=vp_hdr,
        vp_url=vp_url,
        sarva_url=sarva_url,
        heading_level=h_lvl,
      )
      replace_group_tokens(tokens, grp, new_vp_raw=new_vp, new_sarva_stub=new_tk, drop_inline_tika=True)
    rendered = render_tokens(fm, tokens)
    if not cascade._balanced_tags(rendered):
      raise ValueError(f"Unbalanced tags after AV-P self-repeat rewrite in {c_fp}")
    if not dry_run:
      c_fp.write_text(rendered, encoding="utf-8")
    changed_paths.append(str(c_fp))

  if changed_paths and not dry_run:
    for p_str in sorted(set(changed_paths)):
      fp = pathlib.Path(p_str)
      if not fp.is_file():
        continue
      txt = fp.read_text(encoding="utf-8", errors="ignore")
      if "js_include" not in txt:
        continue
      new_txt, n = transformer.surgical_prefill_content(txt, str(fp), hugo_base_dir=str(hugo_base_dir))
      if n and new_txt != txt and cascade._balanced_tags(new_txt):
        fp.write_text(new_txt, encoding="utf-8")
    transformer.surgical_prefill_transitive(
      list(caller_roots),
      changed_paths,
      hugo_base_dir=str(hugo_base_dir),
      skip_sources_with_empty_includes=False,
      only_if_prefilled=True,
      dry_run=dry_run,
    )

  return stats


def run_paippalada_dedup(
  *,
  hugo_base_dir: pathlib.Path = DEFAULT_HUGO_BASE,
  upstream_targets: Sequence[str] = DEFAULT_UPSTREAM_TARGETS,
  caller_roots: Sequence[pathlib.Path] | None = None,
  specs: dict[str, VedaCorpusSpec] | None = None,
  dry_run: bool = False,
  run_single_caller_cleanup: bool = False,
) -> dict:
  """Execute cross-Veda dedup followed by intra-Paippalāda self-repeat extraction."""
  loaded_specs = specs if specs is not None else load_corpus_specs()
  roots = list(caller_roots) if caller_roots is not None else _build_paippalada_caller_roots(hugo_base_dir, loaded_specs)

  cross_stats = cascade.run_stage_cascade(
    "AV-P",
    upstream_targets,
    roots,
    hugo_base_dir=str(hugo_base_dir),
    include_inline_targets=True,
    allow_self_static=False,
    dry_run=dry_run,
  )

  self_stats = dedup_avp_self_repeats(
    loaded_specs["AV-P"],
    roots,
    hugo_base_dir=hugo_base_dir,
    dry_run=dry_run,
  )

  cleanup_stats: dict = {}
  if run_single_caller_cleanup:
    # Note: static_fixer expects `<repo>/static` root (`parent.name` == repo name).
    # We leave cleanup off unless whole-repo cleanup is explicitly requested.
    avp_static_root = hugo_base_dir / "vedAH" / "static"
    if avp_static_root.is_dir():
      cleanup_stats = static_fixer.inline_single_caller_veda_static(
        static_roots=[avp_static_root],
        all_vishvasa_root=hugo_base_dir,
        hugo_base_dir=str(hugo_base_dir),
        dry_run=dry_run,
      )

  return {
    "cross_veda": cross_stats,
    "self_repeat": self_stats,
    "single_caller_cleanup": cleanup_stats,
  }


def main(argv: Sequence[str] | None = None) -> int:
  import argparse
  import json

  parser = argparse.ArgumentParser(description="Deduplicate Atharvaveda Paippalāda cross-Veda and self-repeats.")
  parser.add_argument("--dry-run", action="store_true")
  args = parser.parse_args(argv)
  res = run_paippalada_dedup(dry_run=args.dry_run)
  print(json.dumps(res, ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
