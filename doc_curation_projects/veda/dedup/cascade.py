"""Parameterized multi-stage cross-Veda deduplication cascade (`VS -> RV/AV -> TS -> TB -> TK -> MS -> KS`)."""
from __future__ import annotations

import logging
import pathlib
import re
import shutil
import subprocess
from typing import Sequence

from doc_curation.md.content_processor.include import transformer
from doc_curation.md.content_processor.include.seeker import resolve_include_file_path
from doc_curation.sanskrit.accent import us_converter
from doc_curation.sanskrit.accent.samhita_splitter import CLASSICAL_VEDIC_ACCENTS, parse_top_level_details
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim
from doc_curation_projects.veda.dedup.block_parser import (
  HostToken,
  MantraGroup,
  format_vp_summary_with_kind,
  group_mantra_units,
  render_host_include_pair,
  render_tokens,
  replace_group_tokens,
  tokenize_markdown_body,
)
from doc_curation_projects.veda.dedup.commentary_merger import merge_tika_additions
from doc_curation_projects.veda.dedup.matcher import (
  InvertedVedaIndex,
  TargetEntry,
  classify_unit_kind,
  looks_prose_brahmana,
)
from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec, load_corpus_specs
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import (
  format_static_title_and_stem,
  is_no_patha_bheda,
  normalize_phonetic,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.section_parser import (
  VskSubBlock,
  _split_top_level_chunks,
  merge_vsk_hemistich_pair,
  render_js_include_stub,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import format_details_block


def _balanced_tags(text: str) -> bool:
  return len(re.findall(r"<details\b", text)) == text.count("</details>") and len(re.findall(r"<div\b", text)) == text.count("</div>")


def _iter_md_files(dir_path: pathlib.Path | None) -> list[pathlib.Path]:
  if not dir_path or not dir_path.is_dir():
    return []
  return [
    fp for fp in sorted(dir_path.rglob("*.md"))
    if fp.is_file() and fp.name not in ("_index.md", "file_list.md")
  ]


def _detect_heading_level(text: str, spec: VedaCorpusSpec) -> int:
  m = re.search(r"""newlevelforh1=["'](\d+)["']""", text, re.I)
  if m:
    return int(m.group(1))
  if spec.heading_level > 0:
    return spec.heading_level
  if re.search(r"(?m)^###\s+\S", text):
    return 4
  return 3 if spec.name in ("VS-M", "VS-K", "SB-M", "SB-K") else 4


def _spec_by_url(url: str, all_specs: dict[str, VedaCorpusSpec]) -> VedaCorpusSpec | None:
  for sp in all_specs.values():
    for pref in (
      sp.vp_url_prefix,
      sp.sarva_url_prefix,
      sp.yajuh_vp_url,
      sp.yajuh_sarva_url,
      sp.yajuh_sarva_prastuti_url,
      sp.brahmana_vp_url,
      sp.brahmana_sarva_url,
      sp.brahmana_sarva_prastuti_url,
    ):
      if pref and url.startswith(pref + "/"):
        return sp
  return None


def _iter_two_part_trees(sp: VedaCorpusSpec) -> tuple[tuple[str, pathlib.Path | None, pathlib.Path | None, str, str], ...]:
  return (
    ("rk_2part", sp.vp_dir, sp.sarva_dir, sp.vp_url_prefix, sp.sarva_url_prefix),
    ("yajuh_2part", sp.yajuh_vp_dir, sp.yajuh_sarva_dir, sp.yajuh_vp_url, sp.yajuh_sarva_url),
    ("brahmana_2part", sp.brahmana_vp_dir, sp.brahmana_sarva_dir, sp.brahmana_vp_url, sp.brahmana_sarva_url),
  )


def _iter_combined_trees(sp: VedaCorpusSpec) -> tuple[tuple[str, pathlib.Path | None, str, pathlib.Path | None, str, pathlib.Path | None, str], ...]:
  return (
    (
      "yajuh_combined",
      sp.yajuh_sarva_prastuti_dir,
      sp.yajuh_sarva_prastuti_url,
      sp.yajuh_vp_dir,
      sp.yajuh_vp_url,
      sp.yajuh_sarva_dir,
      sp.yajuh_sarva_url,
    ),
    (
      "brahmana_combined",
      sp.brahmana_sarva_prastuti_dir,
      sp.brahmana_sarva_prastuti_url,
      sp.brahmana_vp_dir,
      sp.brahmana_vp_url,
      sp.brahmana_sarva_dir,
      sp.brahmana_sarva_url,
    ),
  )


def _has_any_static_dir(sp: VedaCorpusSpec) -> bool:
  return any((sp.sarva_dir, sp.yajuh_sarva_dir, sp.yajuh_sarva_prastuti_dir, sp.brahmana_sarva_dir, sp.brahmana_sarva_prastuti_dir))


def _has_only_core_mula_pp(tika_items: Sequence[tuple[str, str]]) -> bool:
  return all(t.strip().startswith(("मूलम्", "पदपाठः", "पद-पाठः")) for t, _ in tika_items)


def normalize_corpus_vp_us_accents(spec: VedaCorpusSpec, *, dry_run: bool = False) -> int:
  """Convert lingering dependent accents inside inline `विश्वास-प्रस्तुतिः` blocks to US notation."""
  changed = 0
  dirs = [
    spec.content_dir,
    spec.vp_dir,
    spec.yajuh_vp_dir,
    spec.yajuh_sarva_prastuti_dir,
    spec.brahmana_vp_dir,
    spec.brahmana_sarva_prastuti_dir,
  ]
  for root in dirs:
    for fp in _iter_md_files(root):
      raw = fp.read_text(encoding="utf-8")
      if not any(m in raw for m in CLASSICAL_VEDIC_ACCENTS):
        continue
      if root in (spec.vp_dir, spec.yajuh_vp_dir, spec.brahmana_vp_dir):
        new_raw = us_converter.to_us_accents_markdown(raw, pauses=us_converter.DEFAULT_US_PAUSES, preserve_existing_us=True)
      else:
        fm, body = split_frontmatter_verbatim(raw)
        tokens = tokenize_markdown_body(body)
        edited = False
        for tok in tokens:
          if tok.kind == "details" and tok.title.startswith("विश्वास-प्रस्तुतिः") and any(m in tok.body for m in CLASSICAL_VEDIC_ACCENTS):
            conv = us_converter.to_us_accents_markdown(tok.body, pauses=us_converter.DEFAULT_US_PAUSES, preserve_existing_us=True).strip()
            if conv != tok.body.strip():
              tok.body = conv
              tok.raw = format_details_block(tok.title, conv, is_open=tok.is_open)
              edited = True
        new_raw = render_tokens(fm, tokens) if edited else raw
      if new_raw != raw:
        if not _balanced_tags(new_raw):
          raise ValueError(f"Unbalanced tags after US normalization in {fp}")
        if not dry_run:
          fp.write_text(new_raw, encoding="utf-8")
        changed += 1
  return changed


def sweep_partial_inline_tikas(
  spec: VedaCorpusSpec,
  all_specs: dict[str, VedaCorpusSpec],
  caller_roots: Sequence[pathlib.Path],
  *,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  dry_run: bool = False,
) -> dict:
  """Merge leftover inline `<details><summary>सर्वाष् टीकाः</summary>` blocks next to existing upstream includes."""
  swept = 0
  files_touched: list[str] = []
  sarva_touched: set[pathlib.Path] = set()

  for fp in (
    _iter_md_files(spec.content_dir)
    + _iter_md_files(spec.yajuh_sarva_prastuti_dir)
    + _iter_md_files(spec.brahmana_sarva_prastuti_dir)
  ):
    raw = fp.read_text(encoding="utf-8")
    if "सर्वाष् टीकाः" not in raw or "js_include" not in raw:
      continue
    fm, body = split_frontmatter_verbatim(raw)
    tokens = tokenize_markdown_body(body)
    groups = group_mantra_units(tokens)
    h_lvl = _detect_heading_level(raw, spec)
    edited = False

    for grp in groups:
      if grp.inline_tika_idx is None or not grp.inline_tika_items:
        continue
      target_url = grp.sarva_include_url or (
        grp.vp_include_url.replace("/vishvAsa-prastutiH/", "/sarvASh_TIkAH/") if grp.is_vp_include else ""
      )
      if not target_url:
        continue
      target_spec = _spec_by_url(target_url, all_specs)
      if not target_spec or target_spec.name == spec.name:
        continue
      sarva_fp_str = resolve_include_file_path(url=target_url, hugo_base_dir=hugo_base_dir, current_file_path=str(fp))
      if not sarva_fp_str or not pathlib.Path(sarva_fp_str).is_file():
        continue
      sarva_fp = pathlib.Path(sarva_fp_str)

      # Sanity guard: verify inline Mūlam aligns with included target's Mūlam/VP before merging.
      vp_url = target_url.replace("/sarvASh_TIkAH/", "/vishvAsa-prastutiH/")
      vp_fp_str = resolve_include_file_path(url=vp_url, hugo_base_dir=hugo_base_dir, current_file_path=str(fp))
      inline_mula = next((b for t, b in grp.inline_tika_items if t.strip() == "मूलम्"), "")
      cmp_text = grp.vp_text or inline_mula
      exact_reading = False
      if vp_fp_str and pathlib.Path(vp_fp_str).is_file() and cmp_text:
        target_vp = re.sub(r"</?(?:div|details|summary)[^>]*>", "", split_frontmatter_verbatim(pathlib.Path(vp_fp_str).read_text(encoding="utf-8"))[1]).strip()
        if grp.is_vp_include and inline_mula:
          from doc_curation_projects.veda.dedup.matcher import classify_match
          ok_align, _, _ = classify_match(
            inline_mula,
            normalize_phonetic(inline_mula, include_accents=False, fold_orthography=True),
            target_vp,
            normalize_phonetic(target_vp, include_accents=False, fold_orthography=True),
            allow_variant=True,
            min_len_exact=12,
            min_len_var=12,
            min_ratio=0.70,
          )
          if not ok_align:
            continue
        exact_reading = is_no_patha_bheda(cmp_text, target_vp) if grp.vp_text else True
      elif grp.is_vp_include:
        exact_reading = True

      old_sarva = sarva_fp.read_text(encoding="utf-8")
      new_sarva = merge_tika_additions(
        old_sarva, target_spec, [(spec, exact_reading, grp.inline_tika_items, str(fp))], hugo_base_dir=hugo_base_dir,
      )
      if new_sarva != old_sarva:
        if not _balanced_tags(new_sarva):
          raise ValueError(f"Tag imbalance in {sarva_fp}")
        if not dry_run:
          sarva_fp.write_text(new_sarva, encoding="utf-8")
        sarva_touched.add(sarva_fp)

      new_stub = None
      if grp.sarva_include_idx is None:
        _, new_stub = render_host_include_pair(
          exact_reading=exact_reading, vp_url=vp_url, sarva_url=target_url, heading_level=h_lvl,
        )
      replace_group_tokens(tokens, grp, new_sarva_stub=new_stub, drop_inline_tika=True)
      swept += 1
      edited = True

    if edited:
      new_raw = render_tokens(fm, tokens)
      if not _balanced_tags(new_raw):
        raise ValueError(f"Tag imbalance after sweep in {fp}")
      if not dry_run:
        fp.write_text(new_raw, encoding="utf-8")
      files_touched.append(str(fp))

  return {"swept": swept, "files_touched": files_touched, "sarva_touched": sarva_touched}


def _resolve_own_sarva_for_url(
  sp: VedaCorpusSpec,
  sarva_url: str,
) -> tuple[pathlib.Path, str, str] | None:
  """Return ``(sarva_fp, unit_kind, rel)`` if ``sarva_url`` belongs to ``sp``'s own ``sarvASh_TIkAH`` tree."""
  if not sarva_url:
    return None
  candidates = (
    ("rk", sp.sarva_dir, sp.sarva_url_prefix),
    ("brahmana", sp.brahmana_sarva_dir, sp.brahmana_sarva_url),
    ("yajuh", sp.yajuh_sarva_dir, sp.yajuh_sarva_url),
  )
  for ukind, sdir, pref in candidates:
    if sdir is None or not pref:
      continue
    pref_slash = pref.rstrip("/") + "/"
    if sarva_url.startswith(pref_slash):
      rel = sarva_url[len(pref_slash) :]
      sfp = sdir / rel
      if sfp.is_file():
        return sfp, ukind, rel
  return None


def _resolve_two_part_dirs(
  sp: VedaCorpusSpec,
  unit_kind: str,
) -> tuple[pathlib.Path, pathlib.Path, str, str, str]:
  """Return ``(vp_dir, sarva_dir, vp_pref, sarva_pref, out_kind)`` for ``sp`` and ``unit_kind``."""
  if unit_kind == "rk" and sp.vp_dir and sp.sarva_dir:
    return sp.vp_dir, sp.sarva_dir, sp.vp_url_prefix, sp.sarva_url_prefix, "rk_2part"
  if unit_kind == "brahmana" and sp.brahmana_sarva_dir:
    sarva_dir = sp.brahmana_sarva_dir
    sarva_pref = sp.brahmana_sarva_url
    vp_dir = sp.brahmana_vp_dir or (sarva_dir.parent / "vishvAsa-prastutiH")
    vp_pref = sp.brahmana_vp_url or (sarva_pref.rsplit("/", 1)[0] + "/vishvAsa-prastutiH")
    return vp_dir, sarva_dir, vp_pref, sarva_pref, "brahmana_2part"
  sarva_dir = sp.yajuh_sarva_dir or sp.sarva_dir
  sarva_pref = sp.yajuh_sarva_url or sp.sarva_url_prefix
  if sarva_dir is None:
    sarva_dir = sp.brahmana_sarva_dir
    sarva_pref = sp.brahmana_sarva_url
    vp_dir = sp.brahmana_vp_dir or (sarva_dir.parent / "vishvAsa-prastutiH")  # type: ignore[union-attr]
    vp_pref = sp.brahmana_vp_url or (sarva_pref.rsplit("/", 1)[0] + "/vishvAsa-prastutiH")
    return vp_dir, sarva_dir, vp_pref, sarva_pref, "brahmana_2part"  # type: ignore[return-value]
  if sarva_dir == sp.sarva_dir:
    return sp.vp_dir, sarva_dir, sp.vp_url_prefix, sarva_pref, "rk_2part"  # type: ignore[return-value]
  vp_dir = sp.yajuh_vp_dir or (sarva_dir.parent / "vishvAsa-prastutiH")
  vp_pref = sp.yajuh_vp_url or (sarva_pref.rsplit("/", 1)[0] + "/vishvAsa-prastutiH")
  return vp_dir, sarva_dir, vp_pref, sarva_pref, "yajuh_2part"


def _infer_unit_kind_for_match(
  ent: TargetEntry,
  vp_text: str,
  vp_summary: str,
  *,
  default_brahmana: bool,
) -> str:
  if ent.kind == "rk_2part":
    return "rk"
  if ent.kind in ("brahmana_2part", "brahmana_combined"):
    return "brahmana"
  if ent.kind in ("yajuh_2part", "yajuh_combined"):
    return "yajuh"
  return classify_unit_kind(vp_text, summary=vp_summary, default_brahmana=default_brahmana)


def build_target_index(
  target_names: Sequence[str],
  all_specs: dict[str, VedaCorpusSpec],
  *,
  include_inline_content: bool = True,
) -> tuple[InvertedVedaIndex, dict[str, tuple[VedaCorpusSpec, pathlib.Path, int]]]:
  """Build prioritized 5-gram index over static trees (and optionally unique inline blocks)."""
  entries: list[TargetEntry] = []
  inline_hosts: dict[str, tuple[VedaCorpusSpec, pathlib.Path, int]] = {}

  for name in target_names:
    sp = all_specs[name]
    for kind, vp_root, sarva_root, vp_pref, sarva_pref in _iter_two_part_trees(sp):
      for vp_fp in _iter_md_files(vp_root):
        assert vp_root is not None and sarva_root is not None
        rel = vp_fp.relative_to(vp_root).as_posix()
        sarva_fp = sarva_root / rel
        if not sarva_fp.is_file():
          continue
        _, body = split_frontmatter_verbatim(vp_fp.read_text(encoding="utf-8"))
        if "js_include" in body:
          continue
        vp_clean = re.sub(r"</?(?:div|details|summary)[^>]*>", "", body).strip()
        pb = normalize_phonetic(vp_clean, include_accents=False, fold_orthography=True)
        if len(pb) < 16:
          continue
        entries.append(TargetEntry(
          corpus=name, kind=kind, rel=rel, vp=vp_clean, pb=pb,
          vp_path=str(vp_fp), sarva_path=str(sarva_fp),
          vp_url=f"{vp_pref}/{rel}", sarva_url=f"{sarva_pref}/{rel}",
        ))

    for comb_kind, comb_dir, comb_url, _, _, _, _ in _iter_combined_trees(sp):
      for y_fp in _iter_md_files(comb_dir):
        assert comb_dir is not None
        raw = y_fp.read_text(encoding="utf-8")
        _, body = split_frontmatter_verbatim(raw)
        chunks = _split_top_level_chunks(body)
        vps = [d for k, d in chunks if k == "details" and d[0].startswith("विश्वास-प्रस्तुतिः")]  # type: ignore[index]
        has_av = any(k == "details" and "अवतारिका" in d[0] for k, d in chunks)  # type: ignore[index]
        if len(vps) != 1 or has_av or "____" in body or "यन्त्र-स्वरः" in vps[0][0]:
          continue
        vp_clean = vps[0][1].strip()  # type: ignore[union-attr]
        pb = normalize_phonetic(vp_clean, include_accents=False, fold_orthography=True)
        if len(pb) < 20:
          continue
        rel = y_fp.relative_to(comb_dir).as_posix()
        entries.append(TargetEntry(
          corpus=name, kind=comb_kind, rel=rel, vp=vp_clean, pb=pb,
          vp_path=str(y_fp), sarva_path=str(y_fp),
          combined_url=f"{comb_url}/{rel}",
        ))

    if include_inline_content and sp.content_dir and _has_any_static_dir(sp):
      brahmana_capable = bool(sp.brahmana_sarva_prastuti_dir or sp.brahmana_sarva_dir)
      for c_fp in _iter_md_files(sp.content_dir):
        _, body = split_frontmatter_verbatim(c_fp.read_text(encoding="utf-8"))
        tokens = tokenize_markdown_body(body)
        for g_idx, grp in enumerate(group_mantra_units(tokens)):
          if grp.is_vp_include or not grp.vp_text.strip() or "यन्त्र-स्वरः" in grp.vp_summary:
            continue
          own_sarva = _resolve_own_sarva_for_url(sp, grp.sarva_include_url) if grp.sarva_include_url else None
          if grp.sarva_include_url and own_sarva is None:
            continue
          pb = normalize_phonetic(grp.vp_text, include_accents=False, fold_orthography=True)
          if brahmana_capable:
            if len(pb) < 22:
              continue
          elif len(pb) < 24 or looks_prose_brahmana(grp.vp_text, len(pb), summary=grp.vp_summary):
            continue
          rel = own_sarva[2] if own_sarva else c_fp.relative_to(sp.content_dir).as_posix()
          skey = f"{name}:{c_fp.relative_to(sp.content_dir).as_posix()}:{g_idx}"
          inline_hosts[skey] = (sp, c_fp, g_idx)
          entries.append(TargetEntry(
            corpus=name,
            kind="inline_vp_shared_sarva" if own_sarva else "inline",
            rel=rel,
            vp=grp.vp_text,
            pb=pb,
            vp_path="" if own_sarva else str(c_fp),
            sarva_path=str(own_sarva[0]) if own_sarva else "",
            sarva_url=grp.sarva_include_url if own_sarva else "",
            host_path=str(c_fp),
            slot_key=skey,
          ))

  return InvertedVedaIndex(entries, target_names), inline_hosts


_CALLER_URL_RE = re.compile(r"""url=(["'])(/[^"']+)\1""")


class UrlCallerIndex:
  """Single-pass reverse index mapping `js_include` URLs to caller `.md` files."""

  def __init__(self, caller_roots: Sequence[pathlib.Path]) -> None:
    self.by_url: dict[str, set[pathlib.Path]] = {}
    existing_roots = [str(r) for r in caller_roots if r.exists()]
    if not existing_roots:
      return
    rg_bin = shutil.which("rg")
    cand_files: list[pathlib.Path] = []
    if rg_bin:
      proc = subprocess.run(
        [rg_bin, "-l", "js_include", "-g", "*.md", *existing_roots],
        capture_output=True, text=True, check=False,
      )
      if proc.returncode in (0, 1):
        cand_files = [pathlib.Path(line) for line in proc.stdout.splitlines() if line.strip()]
    if not cand_files and not rg_bin:
      cand_files = [
        fp for r in caller_roots if r.exists() for fp in r.rglob("*.md") if fp.is_file()
      ]
    for fp in sorted(set(cand_files)):
      if not fp.is_file():
        continue
      txt = fp.read_text(encoding="utf-8", errors="ignore")
      if "js_include" not in txt:
        continue
      for m in _CALLER_URL_RE.finditer(txt):
        self.by_url.setdefault(m.group(2), set()).add(fp)

  def files_for(self, url: str) -> list[pathlib.Path]:
    return sorted(self.by_url.get(url, ()))

  def has_other_refs(self, url: str, exclude_prefix: pathlib.Path | None = None) -> bool:
    for fp in self.by_url.get(url, ()):
      if exclude_prefix and exclude_prefix in fp.parents:
        continue
      return True
    return False

  def record_rewrite(self, old_url: str, new_url: str | None, fp: pathlib.Path) -> None:
    self.by_url.get(old_url, set()).discard(fp)
    if new_url:
      self.by_url.setdefault(new_url, set()).add(fp)


def _rewrite_url_across_callers(
  old_url: str,
  new_url: str | None,
  replacement_html: str | None,
  caller_roots: Sequence[pathlib.Path],
  *,
  dry_run: bool,
  url_index: UrlCallerIndex | None = None,
) -> list[str]:
  """Update every `<div class="js_include"... url="{old_url}">` across all `vishvAsa` repos."""
  touched: list[str] = []
  url_attr_rx = re.compile(rf"""url=(["']){re.escape(old_url)}\1""")
  candidates = url_index.files_for(old_url) if url_index is not None else [
    fp for root in caller_roots if root.exists() for fp in sorted(root.rglob("*.md")) if fp.is_file()
  ]
  for fp in candidates:
    if not fp.is_file():
      continue
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    if old_url not in txt:
      continue
    new_txt = txt
    added_urls: list[str] = []
    if replacement_html is not None:
      from doc_curation.md.content_processor.include.transformer import find_js_include_divs
      spans = [(a, e) for a, _, _, _, e, tok in find_js_include_divs(txt) if url_attr_rx.search(tok)]
      for a, e in reversed(spans):
        new_txt = new_txt[:a] + replacement_html + new_txt[e:]
      added_urls = [m.group(2) for m in _CALLER_URL_RE.finditer(replacement_html)]
    elif new_url is not None:
      new_txt = url_attr_rx.sub(f'url="{new_url}"', txt)
      added_urls = [new_url]
    if new_txt != txt:
      if not _balanced_tags(new_txt):
        raise ValueError(f"Unbalanced tags after rewriting {old_url} in {fp}")
      if not dry_run:
        fp.write_text(new_txt, encoding="utf-8")
        if url_index is not None:
          url_index.by_url.get(old_url, set()).discard(fp)
          for au in added_urls:
            url_index.by_url.setdefault(au, set()).add(fp)
      touched.append(str(fp))
  return touched


def _url_still_referenced(
  url: str,
  caller_roots: Sequence[pathlib.Path],
  exclude_prefix: pathlib.Path | None = None,
  url_index: UrlCallerIndex | None = None,
) -> bool:
  if url_index is not None:
    return url_index.has_other_refs(url, exclude_prefix=exclude_prefix)
  for root in caller_roots:
    if not root.exists():
      continue
    for fp in root.rglob("*.md"):
      if not fp.is_file() or (exclude_prefix and exclude_prefix in fp.parents):
        continue
      if url in fp.read_text(encoding="utf-8", errors="ignore"):
        return True
  return False


def _split_combined_yajuh_target(
  ent: TargetEntry,
  sp: VedaCorpusSpec,
  caller_roots: Sequence[pathlib.Path],
  *,
  dry_run: bool,
  url_index: UrlCallerIndex | None = None,
  downstream_shares_vp: bool = False,
) -> tuple[pathlib.Path | None, pathlib.Path, str, str, list[str]]:
  """Convert combined ``sarva-prastutiH/`` target to 2-part (>=2 exact callers) or inline-VP + shared ``sarvASh_TIkAH/``."""
  is_br = ent.kind == "brahmana_combined"
  eff_kind = "brahmana" if is_br else "yajuh"
  comb_dir = sp.brahmana_sarva_prastuti_dir if is_br else sp.yajuh_sarva_prastuti_dir
  comb_url = sp.brahmana_sarva_prastuti_url if is_br else sp.yajuh_sarva_prastuti_url
  vp_cfg_dir = sp.brahmana_vp_dir if is_br else sp.yajuh_vp_dir
  vp_cfg_url = sp.brahmana_vp_url if is_br else sp.yajuh_vp_url
  sarva_cfg_dir = sp.brahmana_sarva_dir if is_br else sp.yajuh_sarva_dir
  sarva_cfg_url = sp.brahmana_sarva_url if is_br else sp.yajuh_sarva_url
  assert sarva_cfg_dir and comb_dir
  src_fp = pathlib.Path(ent.vp_path)
  rel = ent.rel
  vp_out_dir = vp_cfg_dir or (comb_dir.parent / "vishvAsa-prastutiH")
  vp_out_url = vp_cfg_url or (comb_url.rsplit("/", 1)[0] + "/vishvAsa-prastutiH")
  vp_dest = vp_out_dir / rel
  sarva_dest = sarva_cfg_dir / rel
  vp_url = f"{vp_out_url}/{rel}"
  sarva_url = f"{sarva_cfg_url}/{rel}"
  touched: list[str] = []

  if url_index is not None:
    existing_callers = url_index.files_for(ent.combined_url)
  else:
    existing_callers = [
      fp for root in caller_roots if root.exists() for fp in root.rglob("*.md")
      if fp.is_file() and ent.combined_url in fp.read_text(encoding="utf-8", errors="ignore")
    ]
  keep_2part_vp = (len(existing_callers) + (1 if downstream_shares_vp else 0)) >= 2

  if src_fp.is_file():
    raw = src_fp.read_text(encoding="utf-8")
    fm, body = split_frontmatter_verbatim(raw)
    chunks = _split_top_level_chunks(body)
    vp_summary = "विश्वास-प्रस्तुतिः"
    vp_body = ""
    tika_inner = ""
    for k, d in chunks:
      if k == "details" and d[0].startswith("विश्वास-प्रस्तुतिः"):  # type: ignore[index]
        vp_summary = d[0].strip()  # type: ignore[index]
        vp_body = d[1].strip()  # type: ignore[index]
      elif k == "details" and d[0] == "सर्वाष् टीकाः":  # type: ignore[index]
        tika_inner = d[1].strip()  # type: ignore[index]

    if not dry_run:
      sarva_dest.parent.mkdir(parents=True, exist_ok=True)
      sarva_dest.write_text((fm.rstrip() + "\n\n" if fm else "") + tika_inner + "\n", encoding="utf-8")
      if keep_2part_vp:
        vp_dest.parent.mkdir(parents=True, exist_ok=True)
        vp_dest.write_text((fm.rstrip() + "\n\n" if fm else "") + vp_body + "\n", encoding="utf-8")

    h_lvl = _detect_heading_level("", sp)
    if keep_2part_vp:
      vp_stub, tk_stub = render_host_include_pair(exact_reading=True, vp_url=vp_url, sarva_url=sarva_url, heading_level=h_lvl)
    else:
      vp_stub, tk_stub = render_host_include_pair(
        exact_reading=False,
        local_vp_text=vp_body,
        local_vp_summary=format_vp_summary_with_kind(vp_summary, eff_kind),
        sarva_url=sarva_url,
        heading_level=h_lvl,
      )
    rep_html = f"{vp_stub}\n{tk_stub}"
    touched = _rewrite_url_across_callers(ent.combined_url, None, rep_html, caller_roots, dry_run=dry_run, url_index=url_index)
    if not dry_run and not _url_still_referenced(ent.combined_url, caller_roots, url_index=url_index):
      src_fp.unlink()

  ent.kind = ("brahmana_2part" if is_br else "yajuh_2part") if keep_2part_vp else "inline_vp_shared_sarva"
  ent.vp_path = str(vp_dest) if keep_2part_vp else ""
  ent.sarva_path = str(sarva_dest)
  ent.vp_url = vp_url if keep_2part_vp else ""
  ent.sarva_url = sarva_url
  ent.combined_url = ""
  if not keep_2part_vp and existing_callers:
    ent.host_path = str(existing_callers[0])
  return (vp_dest if keep_2part_vp else None), sarva_dest, (vp_url if keep_2part_vp else ""), sarva_url, touched


def _promote_inline_target(
  ent: TargetEntry,
  is_exact: bool,
  all_specs: dict[str, VedaCorpusSpec],
  inline_hosts: dict[str, tuple[VedaCorpusSpec, pathlib.Path, int]],
  caller_roots: Sequence[pathlib.Path],
  *,
  is_rk_like: bool,
  dry_run: bool,
  url_index: UrlCallerIndex | None = None,
  prefer_2part: bool = False,
  unit_kind: str | None = None,
  share_vp: bool = True,
) -> list[str]:
  """Promote an upstream inline block (`VS-M`, `TS`, `TB`, `SB-M`) into static (keeping single-caller VP inline)."""
  sp, host_fp, g_idx = inline_hosts[ent.slot_key]
  raw = host_fp.read_text(encoding="utf-8")
  fm, body = split_frontmatter_verbatim(raw)
  tokens = tokenize_markdown_body(body)
  grps = group_mantra_units(tokens)
  grp = grps[g_idx] if g_idx < len(grps) and not grps[g_idx].is_vp_include and normalize_phonetic(grps[g_idx].vp_text, include_accents=False, fold_orthography=True) == ent.pb else next(
    g for g in grps if not g.is_vp_include and normalize_phonetic(g.vp_text, include_accents=False, fold_orthography=True) == ent.pb
  )
  rel_parent = host_fp.relative_to(sp.content_dir).with_suffix("").as_posix()  # type: ignore[arg-type]
  num_str = f"{g_idx + 1:02d}"
  title_txt, stem = format_static_title_and_stem(grp.vp_text, num_prefix=num_str)
  if stem == "mantraH" and ent.rel:
    stem = ent.rel.replace("/", "_").replace(".md", "")
  rel = f"{rel_parent}/{num_str}_{stem}.md"
  title_line = f'+++\ntitle = "{title_txt}"\nunicode_script = "devanagari"\n+++\n\n'
  h_lvl = _detect_heading_level(raw, sp)
  sarva_blocks_md = "\n\n".join(format_details_block(t, b) for t, b in grp.inline_tika_items)
  has_suggestions = "[[" in grp.vp_text
  extract_vp = is_exact and share_vp and (not has_suggestions)

  eff_kind = unit_kind or ("rk" if is_rk_like else "yajuh")
  use_rk = eff_kind == "rk" and bool(sp.vp_dir and sp.sarva_dir)
  use_br = (not use_rk) and eff_kind == "brahmana" and bool(sp.brahmana_sarva_prastuti_dir or sp.brahmana_sarva_dir)

  comb_dir = sp.brahmana_sarva_prastuti_dir if use_br else sp.yajuh_sarva_prastuti_dir
  comb_url_pref = sp.brahmana_sarva_prastuti_url if use_br else sp.yajuh_sarva_prastuti_url

  if not use_rk and extract_vp and comb_dir and not prefer_2part:
    dest = comb_dir / rel
    if not dry_run:
      dest.parent.mkdir(parents=True, exist_ok=True)
      vp_hdr = grp.vp_summary.strip() or "विश्वास-प्रस्तुतिः"
      combined_md = format_details_block(vp_hdr, grp.vp_text, is_open=True) + "\n\n" + format_details_block("सर्वाष् टीकाः", sarva_blocks_md)
      dest.write_text(title_line + combined_md + "\n", encoding="utf-8")
    comb_url = f"{comb_url_pref}/{rel}"
    new_vp, new_tk = render_host_include_pair(exact_reading=True, combined_url=comb_url, heading_level=h_lvl)
    replace_group_tokens(tokens, grp, new_vp_raw=new_vp, new_sarva_stub=new_tk, drop_inline_tika=True)
    rendered = render_tokens(fm, tokens)
    if not _balanced_tags(rendered):
      raise ValueError(f"Unbalanced tags after promotion in {host_fp}")
    if not dry_run:
      host_fp.write_text(rendered, encoding="utf-8")
      if url_index is not None:
        url_index.by_url.setdefault(comb_url, set()).add(host_fp)
    ent.kind = "brahmana_combined" if use_br else "yajuh_combined"
    ent.vp_path = str(dest)
    ent.sarva_path = str(dest)
    ent.combined_url = comb_url
    return [str(host_fp)]

  vp_dir, sarva_dir, vp_pref, sarva_pref, out_kind = _resolve_two_part_dirs(sp, eff_kind)

  vp_dest = vp_dir / rel
  sarva_dest = sarva_dir / rel
  vp_url = f"{vp_pref}/{rel}"
  sarva_url = f"{sarva_pref}/{rel}"
  if not dry_run:
    sarva_dest.parent.mkdir(parents=True, exist_ok=True)
    sarva_dest.write_text(title_line + sarva_blocks_md + "\n", encoding="utf-8")
    if extract_vp:
      vp_dest.parent.mkdir(parents=True, exist_ok=True)
      vp_dest.write_text(title_line + grp.vp_text.strip() + "\n", encoding="utf-8")

  if not extract_vp:
    new_vp, new_tk = render_host_include_pair(
      exact_reading=False,
      local_vp_text=grp.vp_text,
      local_vp_summary=format_vp_summary_with_kind(grp.vp_summary or "विश्वास-प्रस्तुतिः", eff_kind),
      sarva_url=sarva_url,
      heading_level=h_lvl,
    )
    replace_group_tokens(tokens, grp, new_vp_raw=new_vp, new_sarva_stub=new_tk, drop_inline_tika=True)
  else:
    new_vp, new_tk = render_host_include_pair(exact_reading=True, vp_url=vp_url, sarva_url=sarva_url, heading_level=h_lvl)
    replace_group_tokens(tokens, grp, new_vp_raw=new_vp, new_sarva_stub=new_tk, drop_inline_tika=True)

  rendered = render_tokens(fm, tokens)
  if not _balanced_tags(rendered):
    raise ValueError(f"Unbalanced tags after promotion in {host_fp}")
  if not dry_run:
    host_fp.write_text(rendered, encoding="utf-8")
    if url_index is not None:
      if extract_vp:
        url_index.by_url.setdefault(vp_url, set()).add(host_fp)
      url_index.by_url.setdefault(sarva_url, set()).add(host_fp)
  ent.kind = out_kind if extract_vp else "inline_vp_shared_sarva"
  ent.vp_path = str(vp_dest) if extract_vp else ""
  ent.sarva_path = str(sarva_dest)
  ent.vp_url = vp_url if extract_vp else ""
  ent.sarva_url = sarva_url
  return [str(host_fp)]


def _promote_inline_vp_to_2part(
  ent: TargetEntry,
  all_specs: dict[str, VedaCorpusSpec],
  inline_hosts: dict[str, tuple[VedaCorpusSpec, pathlib.Path, int]],
  *,
  dry_run: bool,
  url_index: UrlCallerIndex | None = None,
  unit_kind: str = "rk",
) -> list[str]:
  """Extract an ``inline_vp_shared_sarva`` upstream VP to ``vishvAsa-prastutiH/`` once a 2nd exact caller matches."""
  if ent.slot_key not in inline_hosts:
    return []
  sp, host_fp, g_idx = inline_hosts[ent.slot_key]
  raw = host_fp.read_text(encoding="utf-8")
  fm, body = split_frontmatter_verbatim(raw)
  tokens = tokenize_markdown_body(body)
  grps = group_mantra_units(tokens)
  grp = grps[g_idx] if g_idx < len(grps) and not grps[g_idx].is_vp_include and normalize_phonetic(grps[g_idx].vp_text, include_accents=False, fold_orthography=True) == ent.pb else next(
    (g for g in grps if not g.is_vp_include and normalize_phonetic(g.vp_text, include_accents=False, fold_orthography=True) == ent.pb),
    None,
  )
  if grp is None or "[[" in grp.vp_text:
    return []
  own = _resolve_own_sarva_for_url(sp, ent.sarva_url)
  eff_kind = own[1] if own else unit_kind
  vp_dir, sarva_dir, vp_pref, _, out_kind = _resolve_two_part_dirs(sp, eff_kind)
  sarva_fp = pathlib.Path(ent.sarva_path)
  rel = own[2] if own else sarva_fp.relative_to(sarva_dir).as_posix()
  vp_dest = vp_dir / rel
  vp_url = f"{vp_pref}/{rel}"
  title_txt, _ = format_static_title_and_stem(grp.vp_text, num_prefix=f"{g_idx + 1:02d}")
  sarva_title = ""
  if sarva_fp.is_file():
    m_title = re.search(r'^title\s*=\s*"([^"]*)"', sarva_fp.read_text(encoding="utf-8"), flags=re.M)
    if m_title:
      sarva_title = m_title.group(1)
  title_line = f'+++\ntitle = "{sarva_title or title_txt}"\nunicode_script = "devanagari"\n+++\n\n'
  if not dry_run:
    vp_dest.parent.mkdir(parents=True, exist_ok=True)
    vp_dest.write_text(title_line + grp.vp_text.strip() + "\n", encoding="utf-8")

  h_lvl = _detect_heading_level(raw, sp)
  vp_stub = render_js_include_stub(vp_url, title="विश्वास-प्रस्तुतिः", collapsed=False, heading_level=h_lvl)
  replace_group_tokens(tokens, grp, new_vp_raw=vp_stub)
  rendered = render_tokens(fm, tokens)
  if not _balanced_tags(rendered):
    raise ValueError(f"Unbalanced tags after 2-part VP promotion in {host_fp}")
  if not dry_run:
    host_fp.write_text(rendered, encoding="utf-8")
    if url_index is not None:
      url_index.by_url.setdefault(vp_url, set()).add(host_fp)
  ent.kind = out_kind
  ent.vp_path = str(vp_dest)
  ent.vp_url = vp_url
  return [str(host_fp)]


def _migrate_combined_yajuh_tree(
  src_spec: VedaCorpusSpec,
  index: InvertedVedaIndex,
  all_specs: dict[str, VedaCorpusSpec],
  inline_hosts: dict[str, tuple[VedaCorpusSpec, pathlib.Path, int]],
  caller_roots: Sequence[pathlib.Path],
  *,
  hugo_base_dir: str,
  dry_run: bool,
  stats: dict,
  url_index: UrlCallerIndex | None = None,
) -> list[str]:
  """Migrate single-mantra `{yajuH,brAhmaNam}/sarva-prastutiH/` files against upstream targets."""
  changed_paths: list[str] = []
  for src_kind, comb_dir, comb_url, vp_out_cfg_dir, vp_out_cfg_url, sarva_cfg_dir, sarva_cfg_url in _iter_combined_trees(src_spec):
    for y_fp in _iter_md_files(comb_dir):
      assert comb_dir is not None
      raw = y_fp.read_text(encoding="utf-8")
      fm, body = split_frontmatter_verbatim(raw)
      chunks = _split_top_level_chunks(body)
      vp_pairs = [(d[0].strip(), d[1].strip()) for k, d in chunks if k == "details" and d[0].startswith("विश्वास-प्रस्तुतिः")]  # type: ignore[index]
      vp_items = [p[1] for p in vp_pairs]
      tk_items = [(k_i[0], k_i[1]) for k, d in chunks if k == "details" and d[0] == "सर्वाष् टीकाः" for _, _, k_i0, k_i1 in parse_top_level_details(d[1]) for k_i in [(k_i0.strip(), k_i1.strip())]]  # type: ignore[index]
      has_av = any(k == "details" and "अवतारिका" in d[0] for k, d in chunks)  # type: ignore[index]
      if len(vp_items) != 1 or has_av or "____" in body:
        continue
      rel = y_fp.relative_to(comb_dir).as_posix()
      hit = index.find_best(
        vp_items[0],
        src_corpus=src_spec.name,
        src_rel=rel,
        allow_target_variants_from_inline=(src_spec.name in ("SB-M", "SB-K")),
      )
      if hit is None:
        continue
      ent, _, is_exact = hit
      shares_vp = is_exact and ("[[" not in vp_items[0])
      if ent.kind == "inline":
        ukind = classify_unit_kind(ent.vp, default_brahmana=bool(all_specs[ent.corpus].brahmana_sarva_prastuti_dir or all_specs[ent.corpus].brahmana_sarva_dir))
        changed_paths.extend(_promote_inline_target(
          ent, is_exact, all_specs, inline_hosts, caller_roots, is_rk_like=(ukind == "rk"), dry_run=dry_run, url_index=url_index, unit_kind=ukind, share_vp=shares_vp,
        ))
        stats["promoted_targets"] += 1
      elif ent.kind == "inline_vp_shared_sarva" and shares_vp and ent.slot_key in inline_hosts:
        ukind = classify_unit_kind(ent.vp, default_brahmana=bool(all_specs[ent.corpus].brahmana_sarva_prastuti_dir or all_specs[ent.corpus].brahmana_sarva_dir))
        promoted = _promote_inline_vp_to_2part(
          ent, all_specs, inline_hosts, dry_run=dry_run, url_index=url_index, unit_kind=ukind,
        )
        if promoted:
          changed_paths.extend(promoted)
          stats["promoted_targets"] += 1
      elif ent.kind in ("yajuh_combined", "brahmana_combined") and not shares_vp:
        _, _, _, _, sp_ch = _split_combined_yajuh_target(
          ent, all_specs[ent.corpus], caller_roots, dry_run=dry_run, url_index=url_index, downstream_shares_vp=False,
        )
        changed_paths.extend(sp_ch)

      old_url = f"{comb_url}/{rel}"
      h_lvl = _detect_heading_level("", src_spec)
      target_fp = pathlib.Path(ent.sarva_path)
      if target_fp.is_file() and ent.kind in ("yajuh_combined", "brahmana_combined") and shares_vp:
        comb_raw = target_fp.read_text(encoding="utf-8")
        c_fm, c_body = split_frontmatter_verbatim(comb_raw)
        c_toks = tokenize_markdown_body(c_body)
        for c_tok in c_toks:
          if c_tok.kind == "details" and c_tok.title == "सर्वाष् टीकाः":
            c_tok.body = merge_tika_additions(c_tok.body, all_specs[ent.corpus], [(src_spec, True, tk_items, str(y_fp))], hugo_base_dir=hugo_base_dir).strip()
            c_tok.raw = format_details_block("सर्वाष् टीकाः", c_tok.body)
        if not dry_run:
          target_fp.write_text(render_tokens(c_fm, c_toks), encoding="utf-8")
        changed_paths.append(str(target_fp))
        rep = f'<div class="js_include" includetitle="false" newlevelforh1="{h_lvl}" unfilled url="{ent.combined_url}"></div>'
        changed_paths.extend(_rewrite_url_across_callers(old_url, None, rep, caller_roots, dry_run=dry_run, url_index=url_index))
        stats["static_exact"] += 1
      elif ent.kind in ("yajuh_combined", "brahmana_combined") and shares_vp:
        stats["static_exact"] += 1
      else:
        if target_fp.is_file():
          old_t = target_fp.read_text(encoding="utf-8")
          new_t = merge_tika_additions(old_t, all_specs[ent.corpus], [(src_spec, is_exact, tk_items, str(y_fp))], hugo_base_dir=hugo_base_dir)
          if new_t != old_t:
            if not _balanced_tags(new_t):
              raise ValueError(f"Unbalanced tags in {target_fp}")
            if not dry_run:
              target_fp.write_text(new_t, encoding="utf-8")
            changed_paths.append(str(target_fp))
        eff_exact = is_exact and bool(ent.vp_url) and "[[" not in vp_items[0]
        if eff_exact:
          vp_stub, tk_stub = render_host_include_pair(exact_reading=True, vp_url=ent.vp_url, sarva_url=ent.sarva_url, heading_level=h_lvl)
          changed_paths.extend(_rewrite_url_across_callers(old_url, None, f"{vp_stub}\n{tk_stub}", caller_roots, dry_run=dry_run, url_index=url_index))
          stats["static_exact"] += 1
        else:
          assert sarva_cfg_url and sarva_cfg_dir
          callers = url_index.files_for(old_url) if url_index is not None else []
          if len(callers) >= 2 and "[[" not in vp_items[0]:
            vp_out_dir = vp_out_cfg_dir or (comb_dir.parent / "vishvAsa-prastutiH")
            vp_out_url = vp_out_cfg_url or (comb_url.rsplit("/", 1)[0] + "/vishvAsa-prastutiH")
            vp_dest = vp_out_dir / rel
            if not dry_run:
              vp_dest.parent.mkdir(parents=True, exist_ok=True)
              vp_dest.write_text((fm.rstrip() + "\n\n" if fm else "") + vp_items[0] + "\n", encoding="utf-8")
            vp_stub, tk_stub = render_host_include_pair(exact_reading=True, vp_url=f"{vp_out_url}/{rel}", sarva_url=ent.sarva_url, heading_level=h_lvl)
          else:
            uk_comb = "brahmana" if src_kind == "brahmana_combined" else "yajuh"
            vp_stub, tk_stub = render_host_include_pair(
              exact_reading=False,
              local_vp_text=vp_items[0],
              local_vp_summary=format_vp_summary_with_kind(vp_pairs[0][0], uk_comb),
              sarva_url=ent.sarva_url,
              heading_level=h_lvl,
            )
          changed_paths.extend(_rewrite_url_across_callers(old_url, None, f"{vp_stub}\n{tk_stub}", caller_roots, dry_run=dry_run, url_index=url_index))
          stats["static_variant"] += 1
      stats["matches"].append(("combined", rel, ent.corpus, ent.rel, is_exact, round(hit[1], 3)))
      if not dry_run and not _url_still_referenced(old_url, caller_roots, url_index=url_index):
        y_fp.unlink()
        stats["static_deleted"] += 1
  return changed_paths


def _clear_group_tokens(tokens: list[HostToken], grp: MantraGroup) -> None:
  """Blank out a secondary merged `MantraGroup` (`VS-K` second hemistich) from `tokens`."""
  idxs = [i for i in [grp.vp_token_idx, *grp.tika_token_indices] if i is not None]
  for i in idxs:
    tokens[i] = HostToken(kind="text", raw="")
    if i + 1 < len(tokens) and tokens[i + 1].kind == "text" and not tokens[i + 1].raw.strip():
      tokens[i + 1] = HostToken(kind="text", raw="")


def _group_gap_clean(tokens: Sequence[HostToken], g0: MantraGroup, g1: MantraGroup) -> bool:
  end0 = max([i for i in [g0.vp_token_idx, *g0.tika_token_indices] if i is not None], default=-1) + 1
  start1 = g1.vp_token_idx if g1.vp_token_idx is not None else len(tokens)
  for k in range(end0, start1):
    t = tokens[k]
    if t.kind != "text" or "____" in t.raw or re.search(r"(?m)^##+\s", t.raw):
      return False
  return True


def run_stage_cascade(
  src_name: str,
  target_names: Sequence[str],
  caller_roots: Sequence[pathlib.Path],
  *,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  include_inline_targets: bool = True,
  allow_self_static: bool = False,
  dry_run: bool = False,
) -> dict:
  """Execute one full cross-Veda stage: US clean, sweep, static migration, content dedup, and transitive prefill."""
  all_specs = load_corpus_specs()
  src_spec = all_specs[src_name]
  us_fixed = normalize_corpus_vp_us_accents(src_spec, dry_run=dry_run)
  sweep_res = sweep_partial_inline_tikas(src_spec, all_specs, caller_roots, hugo_base_dir=hugo_base_dir, dry_run=dry_run)

  index, inline_hosts = build_target_index(target_names, all_specs, include_inline_content=include_inline_targets)
  url_index = UrlCallerIndex(caller_roots)
  changed_paths: list[str] = list(sweep_res["files_touched"]) + [str(p) for p in sweep_res["sarva_touched"]]
  stats = {
    "stage": f"{src_name} -> {'/'.join(target_names)}",
    "us_fixed": us_fixed,
    "partial_swept": sweep_res["swept"],
    "static_exact": 0,
    "static_variant": 0,
    "static_deleted": 0,
    "content_exact": 0,
    "content_variant": 0,
    "promoted_targets": 0,
    "matches": [],
  }

  # 1. Migrate existing src static 2-part Rk/yajuH/brAhmaNam trees into upstream static targets.
  for tree_kind, vp_dir, sarva_dir, vp_pref, sarva_pref in (() if allow_self_static and src_name in target_names else _iter_two_part_trees(src_spec)):
    for vp_fp in _iter_md_files(vp_dir):
      assert vp_dir is not None and sarva_dir is not None
      rel = vp_fp.relative_to(vp_dir).as_posix()
      sarva_fp = sarva_dir / rel
      if not sarva_fp.is_file():
        continue
      vp_raw = split_frontmatter_verbatim(vp_fp.read_text(encoding="utf-8"))[1]
      if "js_include" in vp_raw:
        continue
      vp_text = re.sub(r"</?(?:div|details|summary)[^>]*>", "", vp_raw).strip()
      is_rk_like = (tree_kind == "rk_2part") if src_name != "EK" else ("\n" in vp_text.strip())
      hit = index.find_best(
        vp_text,
        src_summary="ऋक्" if is_rk_like else "",
        src_corpus=src_name,
        src_rel=rel,
        allow_target_variants_from_inline=(src_name in ("SB-M", "SB-K")),
        allow_self_static=allow_self_static,
      )
      if hit is None:
        continue
      ent, ratio, is_exact = hit
      src_vp_url = f"{vp_pref}/{rel}"
      src_sarva_url = f"{sarva_pref}/{rel}"
      has_vp_only_callers = bool(set(url_index.files_for(src_vp_url)) - set(url_index.files_for(src_sarva_url)))
      if ent.kind == "inline":
        ukind = classify_unit_kind(ent.vp, summary=("ऋक्" if is_rk_like else ""), default_brahmana=bool(all_specs[ent.corpus].brahmana_sarva_prastuti_dir or all_specs[ent.corpus].brahmana_sarva_dir))
        promoted = _promote_inline_target(
          ent, is_exact, all_specs, inline_hosts, caller_roots,
          is_rk_like=(ukind == "rk"), dry_run=dry_run, url_index=url_index, prefer_2part=has_vp_only_callers, unit_kind=ukind, share_vp=is_exact,
        )
        changed_paths.extend(promoted)
        stats["promoted_targets"] += 1
      elif ent.kind == "inline_vp_shared_sarva" and is_exact and ent.slot_key in inline_hosts:
        ukind = classify_unit_kind(ent.vp, summary=("ऋक्" if is_rk_like else ""), default_brahmana=bool(all_specs[ent.corpus].brahmana_sarva_prastuti_dir or all_specs[ent.corpus].brahmana_sarva_dir))
        promoted = _promote_inline_vp_to_2part(
          ent, all_specs, inline_hosts, dry_run=dry_run, url_index=url_index, unit_kind=ukind,
        )
        if promoted:
          changed_paths.extend(promoted)
          stats["promoted_targets"] += 1
      elif ent.kind in ("yajuh_combined", "brahmana_combined") and (not is_exact or has_vp_only_callers):
        _, _, _, _, split_ch = _split_combined_yajuh_target(
          ent, all_specs[ent.corpus], caller_roots, dry_run=dry_run, url_index=url_index, downstream_shares_vp=is_exact,
        )
        changed_paths.extend(split_ch)

      src_sarva_raw = sarva_fp.read_text(encoding="utf-8")
      tika_items = [
        (d[0], d[1]) for k, d in _split_top_level_chunks(split_frontmatter_verbatim(src_sarva_raw)[1]) if k == "details"  # type: ignore[index]
      ]
      if ent.sarva_url and ent.sarva_url in src_sarva_raw and not tika_items:
        continue
      target_sarva_fp = pathlib.Path(ent.sarva_path)
      if ent.kind in ("yajuh_combined", "brahmana_combined") and is_exact:
        comb_raw = target_sarva_fp.read_text(encoding="utf-8")
        c_fm, c_body = split_frontmatter_verbatim(comb_raw)
        c_toks = tokenize_markdown_body(c_body)
        for c_tok in c_toks:
          if c_tok.kind == "details" and c_tok.title == "सर्वाष् टीकाः":
            merged_tk = merge_tika_additions(c_tok.body, all_specs[ent.corpus], [(src_spec, True, tika_items, str(sarva_fp))], hugo_base_dir=hugo_base_dir)
            c_tok.body = merged_tk.strip()
            c_tok.raw = format_details_block("सर्वाष् टीकाः", c_tok.body)
        if not dry_run:
          target_sarva_fp.write_text(render_tokens(c_fm, c_toks), encoding="utf-8")
        changed_paths.append(str(target_sarva_fp))
        h_lvl = _detect_heading_level("", src_spec)
        ch_callers = _rewrite_url_across_callers(f"{vp_pref}/{rel}", None, f'<div class="js_include" includetitle="false" newlevelforh1="{h_lvl}" unfilled url="{ent.combined_url}"></div>', caller_roots, dry_run=dry_run, url_index=url_index)
        ch_callers += _rewrite_url_across_callers(f"{sarva_pref}/{rel}", None, "", caller_roots, dry_run=dry_run, url_index=url_index)
        changed_paths.extend(ch_callers)
      elif target_sarva_fp.is_file():
        old_t = target_sarva_fp.read_text(encoding="utf-8")
        new_t = merge_tika_additions(old_t, all_specs[ent.corpus], [(src_spec, is_exact, tika_items, str(sarva_fp))], hugo_base_dir=hugo_base_dir)
        if new_t != old_t:
          if not _balanced_tags(new_t):
            raise ValueError(f"Unbalanced tags in {target_sarva_fp}")
          if not dry_run:
            target_sarva_fp.write_text(new_t, encoding="utf-8")
          changed_paths.append(str(target_sarva_fp))
        changed_paths.extend(_rewrite_url_across_callers(f"{sarva_pref}/{rel}", ent.sarva_url, None, caller_roots, dry_run=dry_run, url_index=url_index))
        if is_exact and ent.vp_url:
          changed_paths.extend(_rewrite_url_across_callers(f"{vp_pref}/{rel}", ent.vp_url, None, caller_roots, dry_run=dry_run, url_index=url_index))

      stats["matches"].append(("static_2part", rel, ent.corpus, ent.rel, is_exact, round(ratio, 3)))
      eff_exact = is_exact and (ent.kind in ("yajuh_combined", "brahmana_combined") or bool(ent.vp_url))
      if eff_exact:
        stats["static_exact"] += 1
        if not dry_run:
          if not _url_still_referenced(f"{sarva_pref}/{rel}", caller_roots, url_index=url_index):
            sarva_fp.unlink()
            stats["static_deleted"] += 1
          if not _url_still_referenced(f"{vp_pref}/{rel}", caller_roots, url_index=url_index):
            vp_fp.unlink()
            stats["static_deleted"] += 1
      else:
        stats["static_variant"] += 1
        if not dry_run and not _url_still_referenced(f"{sarva_pref}/{rel}", caller_roots, url_index=url_index):
          sarva_fp.unlink()
          stats["static_deleted"] += 1

  if not (allow_self_static and src_name in target_names):
    changed_paths.extend(
      _migrate_combined_yajuh_tree(
        src_spec, index, all_specs, inline_hosts, caller_roots,
        hugo_base_dir=hugo_base_dir, dry_run=dry_run, stats=stats, url_index=url_index,
      )
    )

  # 2. Match remaining unlinked src content blocks (and non-single static yajuH/brAhmaNam files).
  host_work_items: list[tuple[pathlib.Path, pathlib.Path, str]] = [
    (p, src_spec.content_dir, "content") for p in _iter_md_files(src_spec.content_dir) if src_spec.content_dir
  ]
  for _, comb_dir, _, _, _, _, _ in _iter_combined_trees(src_spec):
    for p in _iter_md_files(comb_dir):
      assert comb_dir is not None
      raw_chk = p.read_text(encoding="utf-8")
      if "____" in raw_chk or "अवतारिका" in raw_chk or raw_chk.count("विश्वास-प्रस्तुतिः") != 1:
        host_work_items.append((p, comb_dir, "yajuh_inner"))

  for c_fp, base_root, match_kind in host_work_items:
    raw = c_fp.read_text(encoding="utf-8")
    fm, body = split_frontmatter_verbatim(raw)
    tokens = tokenize_markdown_body(body)
    groups = group_mantra_units(tokens)
    h_lvl = _detect_heading_level(raw, src_spec)
    c_rel = c_fp.relative_to(base_root).as_posix()
    edited = False

    gi = 0
    while gi < len(groups):
      grp = groups[gi]
      if grp.is_vp_include or grp.sarva_include_url or not grp.vp_text.strip():
        gi += 1
        continue

      merged_pair = False
      use_vp = grp.vp_text
      use_sum = grp.vp_summary
      use_tikas = grp.inline_tika_items
      hit = index.find_best(
        use_vp,
        src_summary=use_sum,
        src_corpus=src_name,
        src_rel=c_rel,
        exclude_path=str(c_fp),
        allow_target_variants_from_inline=(src_name in ("SB-M", "SB-K")),
        allow_self_static=allow_self_static,
      )

      if src_name == "VS-K" and gi + 1 < len(groups):
        g1 = groups[gi + 1]
        if (
          not g1.is_vp_include
          and not g1.sarva_include_url
          and g1.vp_text.strip()
          and g1.av_token_idx is None
          and _group_gap_clean(tokens, grp, g1)
        ):
          comb_vp = grp.vp_text.strip() + "  \n" + g1.vp_text.strip()
          pair_hit = index.find_best(comb_vp, src_summary="VS-K", src_corpus="VS-K", exclude_path=str(c_fp))
          if pair_hit is not None:
            comb_len = len(normalize_phonetic(comb_vp, include_accents=False, fold_orthography=True))
            g0_len = len(normalize_phonetic(grp.vp_text, include_accents=False, fold_orthography=True))
            tgt_len = len(pair_hit[0].pb)
            if hit is None or abs(comb_len - tgt_len) + 10 < abs(g0_len - tgt_len):
              b_merged, _ = merge_vsk_hemistich_pair(
                VskSubBlock([], grp.vp_text, grp.inline_tika_items),
                VskSubBlock([], g1.vp_text, g1.inline_tika_items),
              )
              use_vp = b_merged.vp
              use_sum = "विश्वास-प्रस्तुतिः"
              use_tikas = b_merged.tika_blocks
              hit = pair_hit
              merged_pair = True

      if hit is None:
        gi += 1
        continue
      ent, ratio, is_exact = hit
      if (src_name in ("SB-M", "SB-K") or ent.corpus in ("SB-M", "SB-K")) and ("[[" in use_vp or "[[" in ent.vp):
        is_exact = re.sub(r"\s+", " ", use_vp.strip()) == re.sub(r"\s+", " ", ent.vp.strip())
      if allow_self_static and ent.corpus == src_name:
        uk_self = classify_unit_kind(use_vp, summary=use_sum, default_brahmana=bool(src_spec.brahmana_sarva_prastuti_dir or src_spec.brahmana_sarva_dir))
        if (not is_exact) or (uk_self not in ("rk", "yajuh") and not _has_only_core_mula_pp(use_tikas)):
          gi += 1
          continue
      downstream_shares_vp = is_exact and ("[[" not in use_vp)
      if ent.kind == "inline":
        tgt_sp = all_specs[ent.corpus]
        tgt_br = bool(tgt_sp.brahmana_sarva_prastuti_dir or tgt_sp.brahmana_sarva_dir)
        ukind = (
          classify_unit_kind(ent.vp, summary=("ऋक्" if "ऋक्" in use_sum else ""), default_brahmana=tgt_br)
          if tgt_br
          else ("rk" if ("ऋक्" in use_sum or "\n" in use_vp.strip() or "\n" in ent.vp.strip()) else "yajuh")
        )
        promoted = _promote_inline_target(
          ent, is_exact, all_specs, inline_hosts, caller_roots,
          is_rk_like=(ukind == "rk"), dry_run=dry_run, url_index=url_index, unit_kind=ukind, share_vp=downstream_shares_vp,
        )
        changed_paths.extend(promoted)
        stats["promoted_targets"] += 1
      elif ent.kind == "inline_vp_shared_sarva" and downstream_shares_vp and ent.slot_key in inline_hosts:
        tgt_sp = all_specs[ent.corpus]
        tgt_br = bool(tgt_sp.brahmana_sarva_prastuti_dir or tgt_sp.brahmana_sarva_dir)
        ukind = (
          classify_unit_kind(ent.vp, summary=("ऋक्" if "ऋक्" in use_sum else ""), default_brahmana=tgt_br)
          if tgt_br
          else ("rk" if ("ऋक्" in use_sum or "\n" in use_vp.strip() or "\n" in ent.vp.strip()) else "yajuh")
        )
        promoted = _promote_inline_vp_to_2part(
          ent, all_specs, inline_hosts, dry_run=dry_run, url_index=url_index, unit_kind=ukind,
        )
        if promoted:
          changed_paths.extend(promoted)
          stats["promoted_targets"] += 1
      elif ent.kind in ("yajuh_combined", "brahmana_combined") and not downstream_shares_vp:
        old_comb_url = ent.combined_url
        _, _, u_vp, u_tk, split_ch = _split_combined_yajuh_target(
          ent, all_specs[ent.corpus], caller_roots, dry_run=dry_run, url_index=url_index, downstream_shares_vp=False,
        )
        changed_paths.extend(split_ch)
        if old_comb_url and u_vp:
          rep_v, rep_s = render_host_include_pair(exact_reading=True, vp_url=u_vp, sarva_url=u_tk, heading_level=h_lvl)
          for p_tok in tokens:
            if p_tok.kind == "include" and old_comb_url in p_tok.raw:
              p_tok.raw = f"{rep_v}\n{rep_s}"
              p_tok.url = u_vp

      target_fp = pathlib.Path(ent.sarva_path)
      if ent.kind in ("yajuh_combined", "brahmana_combined") and is_exact:
        if target_fp.is_file():
          comb_raw = target_fp.read_text(encoding="utf-8")
          c_fm, c_body = split_frontmatter_verbatim(comb_raw)
          c_toks = tokenize_markdown_body(c_body)
          for c_tok in c_toks:
            if c_tok.kind == "details" and c_tok.title == "सर्वाष् टीकाः":
              c_tok.body = merge_tika_additions(c_tok.body, all_specs[ent.corpus], [(src_spec, True, use_tikas, str(c_fp))], hugo_base_dir=hugo_base_dir).strip()
              c_tok.raw = format_details_block("सर्वाष् टीकाः", c_tok.body)
          if not dry_run:
            target_fp.write_text(render_tokens(c_fm, c_toks), encoding="utf-8")
          changed_paths.append(str(target_fp))
        new_vp, new_tk = render_host_include_pair(exact_reading=True, combined_url=ent.combined_url, heading_level=h_lvl)
        replace_group_tokens(tokens, grp, new_vp_raw=new_vp, new_sarva_stub=new_tk, drop_inline_tika=True, drop_sarva_include=True)
        if not dry_run and ent.combined_url:
          url_index.by_url.setdefault(ent.combined_url, set()).add(c_fp)
        if merged_pair:
          _clear_group_tokens(tokens, groups[gi + 1])
        stats["content_exact"] += 1
        stats["matches"].append(("vsk_pair" if merged_pair else match_kind, f"{c_rel}#{gi}", ent.corpus, ent.rel, True, round(ratio, 3)))
        edited = True
        gi += 2 if merged_pair else 1
        continue

      if target_fp.is_file():
        old_t = target_fp.read_text(encoding="utf-8")
        new_t = merge_tika_additions(old_t, all_specs[ent.corpus], [(src_spec, is_exact, use_tikas, str(c_fp))], hugo_base_dir=hugo_base_dir)
        if new_t != old_t:
          if not _balanced_tags(new_t):
            raise ValueError(f"Unbalanced tags in {target_fp}")
          if not dry_run:
            target_fp.write_text(new_t, encoding="utf-8")
          changed_paths.append(str(target_fp))

      eff_exact = is_exact and bool(ent.vp_url) and "[[" not in use_vp
      uk_caller = _infer_unit_kind_for_match(
        ent,
        use_vp,
        use_sum,
        default_brahmana=bool(src_spec.brahmana_sarva_prastuti_dir or src_spec.brahmana_sarva_dir),
      )
      vp_sum = format_vp_summary_with_kind(use_sum or "विश्वास-प्रस्तुतिः", uk_caller)
      new_vp, new_tk = render_host_include_pair(
        exact_reading=eff_exact, local_vp_text=use_vp, local_vp_summary=vp_sum,
        vp_url=ent.vp_url, sarva_url=ent.sarva_url, heading_level=h_lvl,
      )
      replace_group_tokens(tokens, grp, new_vp_raw=new_vp, new_sarva_stub=new_tk, drop_inline_tika=True)
      if not dry_run:
        if ent.sarva_url:
          url_index.by_url.setdefault(ent.sarva_url, set()).add(c_fp)
        if eff_exact and ent.vp_url:
          url_index.by_url.setdefault(ent.vp_url, set()).add(c_fp)
      if merged_pair:
        _clear_group_tokens(tokens, groups[gi + 1])
      stats["content_exact" if eff_exact else "content_variant"] += 1
      stats["matches"].append(("vsk_pair" if merged_pair else match_kind, f"{c_rel}#{gi}", ent.corpus, ent.rel, eff_exact, round(ratio, 3)))
      edited = True
      gi += 2 if merged_pair else 1

    if edited:
      new_raw = render_tokens(fm, tokens)
      if not _balanced_tags(new_raw):
        raise ValueError(f"Tag imbalance in {c_fp}")
      if not dry_run:
        c_fp.write_text(new_raw, encoding="utf-8")
      changed_paths.append(str(c_fp))

  # 3. Prefill updated files and propagate upward through transitive outer containers.
  if changed_paths and not dry_run:
    for p_str in sorted(set(changed_paths)):
      fp = pathlib.Path(p_str)
      if not fp.is_file():
        continue
      txt = fp.read_text(encoding="utf-8", errors="ignore")
      if "js_include" not in txt:
        continue
      new_txt, n = transformer.surgical_prefill_content(txt, str(fp), hugo_base_dir=hugo_base_dir, only_if_prefilled=True)
      if n and new_txt != txt and _balanced_tags(new_txt) and not dry_run:
        fp.write_text(new_txt, encoding="utf-8")

    # Fill newly inserted unfilled host stubs in src content files and promoted hosts
    skip_dirs = {
      d for sp in all_specs.values()
      for d in (sp.vp_dir, sp.sarva_dir, sp.yajuh_vp_dir, sp.yajuh_sarva_dir, sp.brahmana_vp_dir, sp.brahmana_sarva_dir)
      if d is not None
    }
    for p_str in sorted(set(changed_paths)):
      fp = pathlib.Path(p_str)
      if not fp.is_file() or any(sp_d in fp.parents for sp_d in skip_dirs):
        continue
      txt = fp.read_text(encoding="utf-8", errors="ignore")
      if "js_include" not in txt:
        continue
      new_txt, n = transformer.surgical_prefill_content(txt, str(fp), hugo_base_dir=hugo_base_dir)
      if n and new_txt != txt and _balanced_tags(new_txt) and not dry_run:
        fp.write_text(new_txt, encoding="utf-8")

    transformer.surgical_prefill_transitive(
      caller_roots, changed_paths, hugo_base_dir=hugo_base_dir,
      skip_sources_with_empty_includes=False, only_if_prefilled=True, dry_run=dry_run,
    )

  return stats


def default_caller_roots(specs: dict[str, VedaCorpusSpec] | None = None) -> list[pathlib.Path]:
  """Infer unique `<repo>/{content,static}` caller roots from Vedic corpus specifications."""
  loaded = specs if specs is not None else load_corpus_specs()
  roots: set[pathlib.Path] = set()
  for sp in loaded.values():
    for d in (
      sp.content_dir, sp.vp_dir, sp.yajuh_vp_dir, sp.brahmana_vp_dir,
      sp.yajuh_sarva_prastuti_dir, sp.brahmana_sarva_prastuti_dir,
    ):
      if d is None:
        continue
      for anc in (d, *d.parents):
        if anc.name in ("content", "static"):
          if anc.exists():
            roots.add(anc)
          sibling = anc.parent / ("static" if anc.name == "content" else "content")
          if sibling.exists():
            roots.add(sibling)
          break
  return sorted(roots)


def run_sb_dedup_cascade(
  caller_roots: Sequence[pathlib.Path] | None = None,
  *,
  upstreams: Sequence[str] = ("RV", "AV", "VS-M", "TS", "TB", "TK", "MS", "KS"),
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  dry_run: bool = False,
  run_self_static_pass: bool = True,
) -> dict[str, object]:
  """Run 3-stage cross-Veda & Śatapatha (`SB-M`, `SB-K`) mantra/brāhmaṇa dedup cascade."""
  roots = list(caller_roots) if caller_roots is not None else default_caller_roots()
  s1 = run_stage_cascade("SB-M", upstreams, roots, hugo_base_dir=hugo_base_dir, dry_run=dry_run)
  s2 = run_stage_cascade("SB-K", (*upstreams, "SB-M"), roots, hugo_base_dir=hugo_base_dir, dry_run=dry_run)
  stages = [s1, s2]
  if run_self_static_pass:
    s3 = run_stage_cascade(
      "SB-M",
      ("SB-M",),
      roots,
      hugo_base_dir=hugo_base_dir,
      include_inline_targets=False,
      allow_self_static=True,
      dry_run=dry_run,
    )
    stages.append(s3)
  return {"dry_run": dry_run, "stages": stages}
