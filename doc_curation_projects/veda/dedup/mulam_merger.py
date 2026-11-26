"""Consolidate standalone `mUlam/` static trees into `sarvASh_TIkAH/` for RV and AV."""
from __future__ import annotations

import dataclasses
import logging
import os
import pathlib
import re
import shutil
from typing import Sequence

from doc_curation.md.content_processor.include import transformer
from doc_curation.sanskrit.accent.reconciler import find_js_include_spans
from doc_curation.sanskrit.accent.samhita_splitter import parse_top_level_details
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import normalize_phonetic
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.section_parser import _split_top_level_chunks
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import format_details_block


@dataclasses.dataclass(frozen=True)
class CorpusMulamSpec:
  """Configuration describing a corpus whose standalone `mUlam/` merges into `sarvASh_TIkAH/`."""

  name: str
  shAkha_label: str
  mula_dir: pathlib.Path
  sarva_dir: pathlib.Path
  mula_url_prefix: str
  vp_url_prefix: str
  sarva_url_prefix: str
  pada_summary: str


RV_MULAM_SPEC = CorpusMulamSpec(
  name="RV",
  shAkha_label="शाकलम्",
  mula_dir=pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/mUlam"),
  sarva_dir=pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static/shAkalam/saMhitA/sarvASh_TIkAH"),
  mula_url_prefix="/vedAH_Rk/shAkalam/saMhitA/mUlam/",
  vp_url_prefix="/vedAH_Rk/shAkalam/saMhitA/vishvAsa-prastutiH/",
  sarva_url_prefix="/vedAH_Rk/shAkalam/saMhitA/sarvASh_TIkAH/",
  pada_summary="पद-पाठः",
)

AV_MULAM_SPEC = CorpusMulamSpec(
  name="AV",
  shAkha_label="शौनकम्",
  mula_dir=pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH/static/atharva/shaunakam/rUDha-saMhitA/mUlam"),
  sarva_dir=pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH/static/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH"),
  mula_url_prefix="/vedAH/atharva/shaunakam/rUDha-saMhitA/mUlam/",
  vp_url_prefix="/vedAH/atharva/shaunakam/rUDha-saMhitA/vishvAsa-prastutiH/",
  sarva_url_prefix="/vedAH/atharva/shaunakam/rUDha-saMhitA/sarvASh_TIkAH/",
  pada_summary="पदपाठः",
)

AVP_MULAM_SPEC = CorpusMulamSpec(
  name="AV-P",
  shAkha_label="पैप्पलादम्",
  mula_dir=pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH/static/atharva/paippalAdam/saMhitA/mUlam"),
  sarva_dir=pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH/static/atharva/paippalAdam/saMhitA/sarvASh_TIkAH"),
  mula_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/mUlam/",
  vp_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/vishvAsa-prastutiH/",
  sarva_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/sarvASh_TIkAH/",
  pada_summary="पद-पाठः (यान्त्रिकः)",
)

DEFAULT_CALLER_ROOTS: tuple[pathlib.Path, ...] = (
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_Rk/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_Rk/static"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH/static"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/devaH/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content"),
  pathlib.Path("/home/vvasuki/gitland/vishvAsa/vedAH_sAma/static"),
)

_TAITTIRIYA_MULA_ALIASES = frozenset({
  "मूलम्",
  "तैत्तिरीयम् मूलम्",
  "मूलम् तैत्तिरीयम्",
  "तैत्तिरीयं मूलम्",
  "तैत्तिरीयम् - मूलम्",
})
_TAITTIRIYA_PADA_ALIASES = frozenset({
  "पद-पाठः-तैत्तिरीयः",
  "पद-पाठः- तैत्तिरीयः",
})


def extract_mula_blocks(mula_text: str, shAkha_label: str) -> list[tuple[str, str]]:
  """Parse a standalone `mUlam/` file into ordered `(summary, body)` tuples."""
  _, body = split_frontmatter_verbatim(mula_text)
  top_details = parse_top_level_details(body)
  bare_parts: list[str] = []
  cursor = 0
  variant_blocks: list[tuple[str, str]] = []
  vh_blocks: list[tuple[str, str]] = []
  main_blocks: list[tuple[str, str]] = []

  for s_pos, e_pos, ttl, inner in top_details:
    if s_pos > cursor:
      frag = body[cursor:s_pos].strip()
      if frag:
        bare_parts.append(frag)
    cursor = e_pos
    title = ttl.strip()
    inner_clean = inner.strip()
    if not inner_clean:
      continue
    if title == "मूलम् (VS)":
      main_blocks.append((f"मूलम् - {shAkha_label}", inner_clean))
    elif title == "मूलम् (VH)":
      vh_blocks.append((f"मूलम् - {shAkha_label} (VH)", inner_clean))
    else:
      variant_blocks.append((title, inner_clean))
  if cursor < len(body):
    tail = body[cursor:].strip()
    if tail:
      bare_parts.append(tail)

  if bare_parts:
    main_blocks.insert(0, (f"मूलम् - {shAkha_label}", "\n\n".join(bare_parts)))
  return main_blocks + vh_blocks + variant_blocks


def _normalize_existing_summary(summary: str, *, is_rv: bool) -> str:
  if not is_rv:
    return summary
  if summary in _TAITTIRIYA_MULA_ALIASES:
    return "मूलम् - तैत्तिरीयम्"
  if summary in _TAITTIRIYA_PADA_ALIASES:
    return "पदपाठः - तैत्तिरीयः"
  return summary


def merge_mula_into_sarva_text(
  sarva_text: str,
  mula_blocks: Sequence[tuple[str, str]],
  spec: CorpusMulamSpec,
) -> str:
  """Merge extracted mūlam blocks into a `sarvASh_TIkAH` file without disturbing existing includes or comments."""
  fm, body = split_frontmatter_verbatim(sarva_text)
  chunks = _split_top_level_chunks(body)
  main_prefix = f"मूलम् - {spec.shAkha_label}"
  is_rv = spec.name == "RV"

  primary = [(t, b) for t, b in mula_blocks if t == main_prefix or t.startswith(main_prefix + " (")]
  extras = [(t, b) for t, b in mula_blocks if t != main_prefix and not t.startswith(main_prefix + " (")]

  cleaned_chunks: list[tuple[str, str, str]] = []
  existing_extra_norms: dict[str, set[str]] = {}
  for kind, data in chunks:
    if kind == "details":
      ttl, inner = data  # type: ignore[misc]
      norm_ttl = _normalize_existing_summary(ttl, is_rv=is_rv)
      if norm_ttl == main_prefix or norm_ttl.startswith(main_prefix + " ("):
        continue
      nkey = normalize_phonetic(inner, include_accents=True, fold_orthography=True) or inner
      existing_extra_norms.setdefault(norm_ttl, set()).add(nkey)
      cleaned_chunks.append(("details", norm_ttl, format_details_block(norm_ttl, inner)))
    else:
      _, raw_inc = data  # type: ignore[misc]
      cleaned_chunks.append(("include", "", raw_inc.strip()))

  extra_to_add: list[tuple[str, str, str]] = []
  for ttl, bdy in extras:
    nkey = normalize_phonetic(bdy, include_accents=True, fold_orthography=True) or bdy
    if nkey not in existing_extra_norms.get(ttl, ()):
      existing_extra_norms.setdefault(ttl, set()).add(nkey)
      extra_to_add.append(("details", ttl, format_details_block(ttl, bdy)))

  rendered_primary = [("details", t, format_details_block(t, b)) for t, b in primary]
  insert_idx: int | None = None
  for idx, (kind, ttl, _) in enumerate(cleaned_chunks):
    if kind == "details" and ttl == spec.pada_summary:
      insert_idx = idx
      break
  if insert_idx is None:
    for anchor in ("Vedaweb annotation", "Thomson & Solcum", "Griffith", "Whitney", "अधिमन्त्रम् - sa"):
      for idx, (kind, ttl, _) in enumerate(cleaned_chunks):
        if kind == "details" and ttl == anchor:
          insert_idx = idx + 1
          break
      if insert_idx is not None:
        break
  if insert_idx is None:
    insert_idx = 0

  ordered = cleaned_chunks[:insert_idx] + rendered_primary + cleaned_chunks[insert_idx:]
  if extra_to_add:
    after_pada = insert_idx + len(rendered_primary)
    if after_pada < len(ordered) and ordered[after_pada][0] == "details" and ordered[after_pada][1] == spec.pada_summary:
      after_pada += 1
    ordered = ordered[:after_pada] + extra_to_add + ordered[after_pada:]

  new_body = "\n\n".join(blk for _, _, blk in ordered).strip()
  return f"{fm.rstrip()}\n\n{new_body}\n" if fm else f"{new_body}\n"


def rewrite_mula_callers_in_text(text: str, spec: CorpusMulamSpec) -> tuple[str, int]:
  """Remove redundant `mUlam/` `js_include`s where `sarvASh_TIkAH/` is present; redirect lone callers cleanly."""
  if spec.mula_url_prefix not in text:
    return text, 0

  url_rx = re.compile(r"""url=(["'])([^"']+)\1""")
  raw_spans = [(a, e) for a, _, _, _, e, _ in transformer.find_js_include_divs(text)]
  edits: list[tuple[int, int, str]] = []

  for a, b in raw_spans:
    block = text[a:b]
    m_url = url_rx.search(block)
    if not m_url or not m_url.group(2).startswith(spec.mula_url_prefix):
      continue
    url = m_url.group(2)
    sarva_url = spec.sarva_url_prefix + url[len(spec.mula_url_prefix) :]
    vp_url = spec.vp_url_prefix + url[len(spec.mula_url_prefix) :]

    if sarva_url in text:
      s_del, e_del = a, b
      while e_del < len(text) and text[e_del] in " \t":
        e_del += 1
      if e_del < len(text) and text[e_del] == "\n":
        e_del += 1
      edits.append((s_del, e_del, ""))
      continue

    open_end = block.find(">")
    open_tag = block[: open_end + 1]
    if 'includetitle="false"' in open_tag.lower() or "includetitle='false'" in open_tag.lower():
      new_block = block[: m_url.start(2)] + vp_url + block[m_url.end(2) :]
      edits.append((a, b, new_block))
    else:
      nl_m = re.search(r"""newlevelforh1=(["'])([^"']+)\1""", open_tag, re.I)
      nl_attr = f' newLevelForH1="{nl_m.group(2)}"' if nl_m else ""
      edits.append((a, b, f'<div class="js_include collapsed" title="सर्वाष् टीकाः" url="{sarva_url}"{nl_attr}> </div>'))

  if not edits:
    return text, 0
  out = text
  for s_pos, e_pos, rep in sorted(edits, key=lambda x: x[0], reverse=True):
    out = out[:s_pos] + rep + out[e_pos:]
  out = re.sub(r"\n{3,}", "\n\n", out)
  return out, len(edits)


def _check_balanced_tags(text: str) -> bool:
  return (
    len(re.findall(r"<details\b", text)) == text.count("</details>")
    and len(re.findall(r"<div\b", text)) == text.count("</div>")
  )


def consolidate_corpus_mula(
  spec: CorpusMulamSpec,
  caller_roots: Sequence[pathlib.Path] = DEFAULT_CALLER_ROOTS,
  *,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  dry_run: bool = False,
  delete_mula_dir: bool = False,
) -> dict:
  """Merge `spec.mula_dir` into `spec.sarva_dir`, update callers & prefills, and optionally delete `mula_dir`."""
  sarva_updated = 0
  if spec.mula_dir.is_dir():
    for fp in sorted(spec.mula_dir.rglob("*.md")):
      if not fp.is_file() or fp.name in ("_index.md", "file_list.md"):
        continue
      rel = fp.relative_to(spec.mula_dir)
      sarva_fp = spec.sarva_dir / rel
      if not sarva_fp.is_file():
        raise FileNotFoundError(f"Missing matching sarvASh_TIkAH file for {fp}: {sarva_fp}")
      mula_blocks = extract_mula_blocks(fp.read_text(encoding="utf-8"), spec.shAkha_label)
      old_sarva = sarva_fp.read_text(encoding="utf-8")
      new_sarva = merge_mula_into_sarva_text(old_sarva, mula_blocks, spec)
      if not _check_balanced_tags(new_sarva):
        raise ValueError(f"Tag imbalance after merging {fp} into {sarva_fp}")
      if new_sarva != old_sarva:
        if not dry_run:
          sarva_fp.write_text(new_sarva, encoding="utf-8")
        sarva_updated += 1

  # Normalize any remaining RV sarvASh_TIkAH files without a mUlam sibling (e.g. merged stanzas).
  if spec.name == "RV" and spec.sarva_dir.is_dir():
    for sarva_fp in sorted(spec.sarva_dir.rglob("*.md")):
      if not sarva_fp.is_file() or sarva_fp.name in ("_index.md", "file_list.md"):
        continue
      if (spec.mula_dir / sarva_fp.relative_to(spec.sarva_dir)).is_file():
        continue
      old_sarva = sarva_fp.read_text(encoding="utf-8")
      new_sarva = merge_mula_into_sarva_text(old_sarva, (), spec)
      if new_sarva != old_sarva:
        if not dry_run:
          sarva_fp.write_text(new_sarva, encoding="utf-8")
        sarva_updated += 1

  callers_rewritten = 0
  divs_removed_or_redirected = 0
  prefilled_files = 0
  prefilled_divs = 0
  changed_paths: list[str] = []
  url_rx = f"(?:{re.escape(spec.sarva_url_prefix)}|{re.escape(spec.vp_url_prefix)})"

  for root in caller_roots:
    if not root.exists():
      continue
    for fp in sorted(root.rglob("*.md")):
      if not fp.is_file() or spec.mula_dir in fp.parents:
        continue
      txt = fp.read_text(encoding="utf-8", errors="ignore")
      touched = False
      if spec.mula_url_prefix in txt:
        txt, n_rw = rewrite_mula_callers_in_text(txt, spec)
        if n_rw:
          callers_rewritten += 1
          divs_removed_or_redirected += n_rw
          touched = True
      if spec.sarva_url_prefix in txt or (touched and spec.vp_url_prefix in txt):
        new_txt, n_pf = transformer.surgical_prefill_content(
          txt,
          str(fp),
          url_filter=url_rx,
          hugo_base_dir=hugo_base_dir,
          only_if_prefilled=True,
        )
        if n_pf:
          txt = new_txt
          prefilled_files += 1
          prefilled_divs += n_pf
          touched = True
      if touched:
        if not _check_balanced_tags(txt):
          raise ValueError(f"Tag imbalance in caller {fp}")
        changed_paths.append(str(fp))
        if not dry_run:
          fp.write_text(txt, encoding="utf-8")

  # Refresh transitive containers (e.g. ArSheya/devaH/TS-subfiles wrapping TS/TB/Apastamba includes).
  if changed_paths:
    trans_touched = transformer.surgical_prefill_transitive(
      caller_roots,
      changed_paths,
      hugo_base_dir=hugo_base_dir,
      skip_sources_with_empty_includes=False,
      only_if_prefilled=True,
      dry_run=dry_run,
    )
    prefilled_files += len(trans_touched)

  remaining_refs = 0
  for root in caller_roots:
    if not root.exists():
      continue
    for fp in root.rglob("*.md"):
      if fp.is_file() and spec.mula_dir not in fp.parents:
        if spec.mula_url_prefix in fp.read_text(encoding="utf-8", errors="ignore"):
          remaining_refs += 1
          logging.warning("Remaining mUlam reference in %s", fp)

  deleted = False
  if delete_mula_dir and not dry_run and remaining_refs == 0 and spec.mula_dir.is_dir():
    for idx_fp in spec.mula_dir.rglob("_index.md"):
      _, idx_body = split_frontmatter_verbatim(idx_fp.read_text(encoding="utf-8"))
      if idx_body.strip():
        raise ValueError(f"Refusing to delete non-empty _index.md: {idx_fp}")
    shutil.rmtree(spec.mula_dir)
    deleted = True

  return {
    "corpus": spec.name,
    "sarva_updated": sarva_updated,
    "callers_rewritten": callers_rewritten,
    "divs_removed_or_redirected": divs_removed_or_redirected,
    "prefilled_files": prefilled_files,
    "prefilled_divs": prefilled_divs,
    "remaining_refs": remaining_refs,
    "deleted_mula_dir": deleted,
  }
