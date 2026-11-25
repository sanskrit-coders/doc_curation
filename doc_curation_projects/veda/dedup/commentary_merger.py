"""General cross-śākhā commentary disambiguation and `सर्वाष् टीकाः` merging."""
from __future__ import annotations

import difflib
import os
import re
from typing import Sequence

from doc_curation.md.content_processor.include.seeker import resolve_include_file_path
from doc_curation.sanskrit.accent.reconciler import find_js_include_spans
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim
from doc_curation_projects.veda.dedup.targets import VedaCorpusSpec
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import normalize_phonetic
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.section_parser import _split_top_level_chunks
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import (
  format_details_block,
  merge_author_bodies,
)

URL_ATTR_RE = re.compile(r"""url=["']([^"']+)["']""")


def inline_nested_tika_includes(
  body: str,
  container_path: str = "",
  *,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
) -> str:
  """Inline any nested static `js_include` (such as `bhaTTa-bhAskara-TIkA`) inside commentary text."""
  if "js_include" not in body:
    return body.strip()
  spans = find_js_include_spans(body)
  if not spans:
    return body.strip()

  out = body
  for a, b in reversed(spans):
    chunk = out[a:b]
    m_url = URL_ATTR_RE.search(chunk)
    replacement = chunk
    if m_url:
      fp = resolve_include_file_path(url=m_url.group(1), hugo_base_dir=hugo_base_dir, current_file_path=container_path)
      if fp and os.path.isfile(fp):
        _, inc_body = split_frontmatter_verbatim(open(fp, encoding="utf-8").read())
        replacement = inc_body.strip()
    if replacement == chunk:
      # Fallback to stripped prefilled inner body if external file missing.
      inner = re.sub(r"^<div\b[^>]*>|</div>\s*$", "", chunk, flags=re.S).strip()
      replacement = inner
    out = out[:a] + "\n\n" + replacement.strip() + "\n\n" + out[b:]
  return re.sub(r"\n{3,}", "\n\n", out).strip()


def _similar_text(a: str, b: str, *, threshold: float = 0.85) -> bool:
  na = re.sub(r"\s+", " ", a.strip()).lower()
  nb = re.sub(r"\s+", " ", b.strip()).lower()
  if not na or not nb:
    return False
  if na == nb:
    return True
  if min(len(na), len(nb)) > 400:
    return difflib.SequenceMatcher(None, na[:400], nb[:400]).ratio() >= threshold
  return difflib.SequenceMatcher(None, na, nb).ratio() >= threshold


def _disambiguate_incoming_entry(
  ttl: str,
  body: str,
  src_spec: VedaCorpusSpec,
  target_spec: VedaCorpusSpec,
  existing_by_title: dict[str, list[str]],
  *,
  is_exact_reading: bool,
) -> tuple[str, str] | None:
  """Return disambiguated ``(target_summary, clean_body)`` or ``None`` if redundant."""
  t = ttl.strip()
  b = body.strip()
  if not b or t == "मूलम् (संयुक्तम्)":
    return None

  if t == "मूलम्":
    cand_norm = normalize_phonetic(b, include_accents=True, fold_orthography=True)
    for k, vals in existing_by_title.items():
      if k.startswith("मूलम्") and any(
        normalize_phonetic(v, include_accents=True, fold_orthography=True) == cand_norm for v in vals
      ):
        return None
    if is_exact_reading and any(
      normalize_phonetic(v, include_accents=False, fold_orthography=True) == normalize_phonetic(b, include_accents=False, fold_orthography=True)
      for k, vals in existing_by_title.items() if k.startswith("मूलम्")
      for v in vals
    ):
      return None
    return f"मूलम् - {src_spec.shAkha_label}", b

  if t.startswith("मूलम् - ") or t.startswith("मूलम् ("):
    cand_norm = normalize_phonetic(b, include_accents=True, fold_orthography=True)
    if any(normalize_phonetic(v, include_accents=True, fold_orthography=True) == cand_norm for v in existing_by_title.get(t, ())):
      return None
    return t, b

  if t in ("पदपाठः", "पद-पाठः"):
    return src_spec.pada_label, b

  if t.startswith("पद-पाठः (यान्त्रिकः"):
    if is_exact_reading and any(k.startswith(("पदपाठः", "पद-पाठः")) for k in existing_by_title):
      return None
    if "यान्त्रिकः" in t and "-" in t and t != "पद-पाठः (यान्त्रिकः)":
      return t, b
    return f"पद-पाठः (यान्त्रिकः - {src_spec.shAkha_label})", b

  if t.startswith("पदपाठः - ") or t.startswith("पद-पाठः - "):
    return t, b

  if t in ("सायण-टीका", "सायणटीका"):
    if src_spec.name == "VS-K":
      return src_spec.sayana_variant_label, b
    if "सायण-टीका" in existing_by_title:
      if any(_similar_text(b, ex, threshold=0.88) for ex in existing_by_title["सायण-टीका"]):
        return None
      return src_spec.sayana_variant_label, b
    return (src_spec.sayana_variant_label if target_spec.name in ("VS-M", "TS", "TB") else "सायण-टीका"), b

  if t == "भट्टभास्कर-टीका":
    if "भट्टभास्कर-टीका" in existing_by_title:
      if any(_similar_text(b, ex, threshold=0.85) for ex in existing_by_title["भट्टभास्कर-टीका"]):
        return None
      return (src_spec.bb_variant_label or f"भट्टभास्कर-टीका ({src_spec.shAkha_label})"), b
    return t, b

  if t == "Griffith":
    if "Griffith" in existing_by_title:
      if any(_similar_text(b, ex, threshold=0.80) for ex in existing_by_title["Griffith"]):
        return None
      return f"Griffith ({src_spec.shAkha_label})", b
    return t, b

  if t == "Keith":
    if "Keith" in existing_by_title:
      if any(_similar_text(b, ex, threshold=0.80) for ex in existing_by_title["Keith"]):
        return None
      return (src_spec.keith_variant_label or f"Keith ({src_spec.shAkha_label})"), b
    return t, b

  if t.startswith("दयानन्द-सरस्वती"):
    if t in existing_by_title:
      if any(_similar_text(b, ex, threshold=0.82) for ex in existing_by_title[t]):
        return None
      qual = src_spec.dayananda_qual or src_spec.shAkha_label
      if " - " in t:
        head, rest = t.split(" - ", 1)
        if head.endswith(")"):
          new_t = f"{head[:-1]}, {qual}) - {rest}"
        else:
          new_t = f"{head} ({qual}) - {rest}"
        return new_t, b
      return f"{t} ({qual})", b
    return t, b

  return t, b


def _normalize_target_blocks(
  chunks: Sequence[tuple[str, object]],
  target_spec: VedaCorpusSpec,
  *,
  has_variant: bool,
) -> list[tuple[str, str, str]]:
  out: list[tuple[str, str, str]] = []
  for kind, data in chunks:
    if kind == "details":
      ttl, inner = data  # type: ignore[misc]
      if has_variant and ttl == "मूलम्":
        ttl = f"मूलम् - {target_spec.shAkha_label}"
      out.append(("details", ttl, inner))
    else:
      _, raw_inc = data  # type: ignore[misc]
      out.append(("include", "", raw_inc.strip()))
  return out


def merge_tika_additions(
  target_sarva_text: str,
  target_spec: VedaCorpusSpec,
  additions: Sequence[tuple[VedaCorpusSpec, bool, Sequence[tuple[str, str]], str]],
  *,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
) -> str:
  """Merge commentary blocks from one or more downstream corpora into a `sarvASh_TIkAH` file."""
  fm, body = split_frontmatter_verbatim(target_sarva_text)
  chunks = _split_top_level_chunks(body)
  has_variant = any(not is_ex for _, is_ex, _, _ in additions)
  base_blocks = _normalize_target_blocks(chunks, target_spec, has_variant=has_variant)

  existing_by_title: dict[str, list[str]] = {}
  for kind, ttl, inner in base_blocks:
    if kind == "details":
      existing_by_title.setdefault(ttl, []).append(inner)

  new_by_title: dict[str, list[str]] = {}
  for src_spec, is_ex, items, src_fp in additions:
    for ttl, raw_b in items:
      inlined = inline_nested_tika_includes(raw_b, container_path=src_fp, hugo_base_dir=hugo_base_dir)
      resolved = _disambiguate_incoming_entry(
        ttl, inlined, src_spec, target_spec, existing_by_title, is_exact_reading=is_ex,
      )
      if resolved is None:
        continue
      dst_ttl, clean_b = resolved
      if dst_ttl in existing_by_title and any(_similar_text(clean_b, ex, threshold=0.92) for ex in existing_by_title[dst_ttl]):
        continue
      existing_by_title.setdefault(dst_ttl, []).append(clean_b)
      new_by_title.setdefault(dst_ttl, []).append(clean_b)

  if not new_by_title:
    rendered_base = [
      format_details_block(ttl, inner) if k == "details" else inner
      for k, ttl, inner in base_blocks
    ]
    cand = (fm.rstrip() + "\n\n" if fm else "") + "\n\n".join(rendered_base).strip() + "\n"
    return cand

  # Update existing matching details titles cleanly, and insert new categories near logical siblings.
  rendered: list[tuple[str, str]] = []
  inserted_keys: set[str] = set()
  for k, ttl, inner in base_blocks:
    if k != "details":
      rendered.append(("__inc__", inner))
      continue
    if ttl in new_by_title:
      merged = merge_author_bodies([inner] + new_by_title[ttl], strip_trivial_crossref=False)
      rendered.append((ttl, format_details_block(ttl, merged)))
      inserted_keys.add(ttl)
    else:
      rendered.append((ttl, format_details_block(ttl, inner)))

  mula_new = [(t, format_details_block(t, merge_author_bodies(new_by_title[t], strip_trivial_crossref=False)))
              for t in new_by_title if t not in inserted_keys and t.startswith("मूलम्")]
  pada_new = [(t, format_details_block(t, merge_author_bodies(new_by_title[t], strip_trivial_crossref=False)))
              for t in new_by_title if t not in inserted_keys and (t.startswith("पदपाठः") or t.startswith("पद-पाठः"))]
  trans_new = [(t, format_details_block(t, merge_author_bodies(new_by_title[t], strip_trivial_crossref=False)))
               for t in new_by_title if t not in inserted_keys and (t.startswith("Griffith") or t.startswith("Keith"))]
  comm_new = [(t, format_details_block(t, merge_author_bodies(new_by_title[t], strip_trivial_crossref=False)))
              for t in new_by_title if t not in inserted_keys
              and not t.startswith("मूलम्") and not t.startswith("पदपाठः") and not t.startswith("पद-पाठः")
              and not t.startswith("Griffith") and not t.startswith("Keith")]

  def _insert_after(seq: list[tuple[str, str]], add: list[tuple[str, str]], pred) -> list[tuple[str, str]]:
    if not add:
      return seq
    pos = None
    for idx, (t, _) in enumerate(seq):
      if pred(t):
        pos = idx + 1
    if pos is None:
      return seq + add
    return seq[:pos] + add + seq[pos:]

  rendered = _insert_after(rendered, trans_new, lambda t: t in ("Griffith", "Keith", "Whitney", "Wilson"))
  rendered = _insert_after(rendered, mula_new, lambda t: t.startswith("मूलम्"))
  rendered = _insert_after(rendered, pada_new, lambda t: t.startswith(("पदपाठः", "पद-पाठः", "मूलम्")))
  rendered = _insert_after(
    rendered,
    comm_new,
    lambda t: any(x in t for x in ("उवट", "महीधर", "सायण", "भट्टभास्कर", "आनन्दबोध", "अनन्ताचार्य")),
  )

  new_body = "\n\n".join(blk for _, blk in rendered).strip()
  return f"{fm.rstrip()}\n\n{new_body}\n" if fm else f"{new_body}\n"
