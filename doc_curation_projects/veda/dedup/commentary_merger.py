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
  if not b or t in ("मूलम् (संयुक्तम्)", "परिचयः") or t.startswith("विस्तारः"):
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
    m_rec = re.fullmatch(r"मूलम्\s*\(([A-Za-z0-9_-]+)\)", t)
    if m_rec and src_spec.name != target_spec.name:
      if is_exact_reading and src_spec.name == "AV-P" and any(k.startswith("मूलम्") for k in existing_by_title):
        return None
      out_t = f"मूलम् - {src_spec.shAkha_label} ({m_rec.group(1)})"
    elif t == "मूलम् - विस्वरम्" and src_spec.name in ("SB-M", "SB-K") and not target_spec.name.startswith("SB-"):
      out_t = f"मूलम् - विस्वरम् ({src_spec.shAkha_label})"
    else:
      out_t = t
    cand_norm = normalize_phonetic(b, include_accents=True, fold_orthography=True)
    if any(normalize_phonetic(v, include_accents=True, fold_orthography=True) == cand_norm for v in existing_by_title.get(out_t, ())):
      return None
    return out_t, b

  if t in ("पदपाठः", "पद-पाठः"):
    return src_spec.pada_label, b

  if t.startswith("पद-पाठः (यान्त्रिकः"):
    if src_spec.name == target_spec.name:
      # Same recension already has its own native padapāṭha block in target; never duplicate/concatenate.
      if any(k.startswith("पद-पाठः (यान्त्रिकः") for k in existing_by_title):
        return None
      return t, b
    if is_exact_reading and "व्यत्यस्त" not in t and src_spec.name not in ("SB-M", "SB-K") and any(
      k.startswith(("पदपाठः", "पद-पाठः")) for k in existing_by_title
    ):
      return None
    if src_spec.shAkha_label in t:
      return t, b
    if src_spec.name in ("SB-M", "SB-K"):
      if src_spec.pada_label.startswith("पद-पाठः (यान्त्रिकः"):
        return _qualify_pada_label(src_spec.pada_label, t), b
      return _qualify_pada_label(f"पद-पाठः (यान्त्रिकः - {src_spec.shAkha_label})", t), b
    if "व्यत्यस्त" not in t and re.search(r"यान्त्रिकः\s*-\s*\S", t):
      return t, b
    return f"पद-पाठः (यान्त्रिकः - {src_spec.shAkha_label})", b

  if t.startswith("पदपाठः - ") or t.startswith("पद-पाठः - "):
    return t, b

  if t in ("सायणः", "सायण-टीका", "सायणटीका"):
    if src_spec.name in ("SB-M", "SB-K"):
      if target_spec.name == src_spec.name:
        if any(_similar_text(b, ex, threshold=0.88) for ex in existing_by_title.get("सायणः", ())):
          return None
        return "सायणः", b
      return src_spec.sayana_variant_label, b
    if src_spec.name == "VS-K":
      return src_spec.sayana_variant_label, b
    if "सायण-टीका" in existing_by_title:
      if any(_similar_text(b, ex, threshold=0.88) for ex in existing_by_title["सायण-टीका"]):
        return None
      return src_spec.sayana_variant_label, b
    return (src_spec.sayana_variant_label if target_spec.name in ("VS-M", "TS", "TB", "TK", "MS", "KS", "EK", "TA") else "सायण-टीका"), b

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

  if t == "Gemini 3.8 Flash":
    if "Gemini 3.8 Flash" in existing_by_title:
      if any(_similar_text(b, ex, threshold=0.80) for ex in existing_by_title["Gemini 3.8 Flash"]):
        return None
      return f"Gemini 3.8 Flash ({src_spec.shAkha_label})", b
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


def _extract_vyat_suffix(summary: str) -> str:
  m = re.search(r"(\d+/\d+\s*व्यत्यस्त-स्वराः)", summary)
  return m.group(1) if m else ""


def _qualify_pada_label(pada_label: str, inc_summary: str) -> str:
  vyat = _extract_vyat_suffix(inc_summary)
  if not vyat or vyat in pada_label:
    return pada_label
  if pada_label.endswith(")"):
    return f"{pada_label[:-1]} - {vyat})"
  return f"{pada_label} ({vyat})"


_TRANSLATION_SUMMARY_PREFIXES = (
  "Eggeling",
  "C R Swaminathan",
  "En - सिद्धार्थः",
  "सिद्धार्थः - En",
  "Griffith",
  "Ralph T H Griffith",
  "Keith",
  "Whitney",
  "Wilson",
  "Jamison Brereton",
  "Thomson & Solcum",
  "Thomson",
  "Gemini",
  "Geldner",
  "Hume",
  "Radhakrishnan",
)


def _is_translation_summary(summary: str) -> bool:
  s = summary.strip()
  return any(s == p or s.startswith(f"{p} ") or s.startswith(f"{p}(") or s.startswith(f"{p} (") or s.startswith(f"{p} -") for p in _TRANSLATION_SUMMARY_PREFIXES)


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
      is_pada = dst_ttl.startswith(("पदपाठः", "पद-पाठः"))
      is_mula = dst_ttl.startswith("मूलम्")
      if dst_ttl in existing_by_title and (
        is_pada or (not is_mula and any(_similar_text(clean_b, ex, threshold=0.92) for ex in existing_by_title[dst_ttl]))
      ):
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
      merged = merge_author_bodies(
        [inner] + new_by_title[ttl],
        strip_trivial_crossref=False,
        include_accents=ttl.startswith("मूलम्"),
      )
      rendered.append((ttl, format_details_block(ttl, merged)))
      inserted_keys.add(ttl)
    else:
      rendered.append((ttl, format_details_block(ttl, inner)))

  mula_new = [(t, format_details_block(t, merge_author_bodies(new_by_title[t], strip_trivial_crossref=False, include_accents=True)))
              for t in new_by_title if t not in inserted_keys and t.startswith("मूलम्")]
  pada_new = [(t, format_details_block(t, merge_author_bodies(new_by_title[t], strip_trivial_crossref=False)))
              for t in new_by_title if t not in inserted_keys and (t.startswith("पदपाठः") or t.startswith("पद-पाठः"))]
  trans_new = [(t, format_details_block(t, merge_author_bodies(new_by_title[t], strip_trivial_crossref=False)))
               for t in new_by_title if t not in inserted_keys and _is_translation_summary(t)]
  comm_new = [(t, format_details_block(t, merge_author_bodies(new_by_title[t], strip_trivial_crossref=False)))
              for t in new_by_title if t not in inserted_keys
              and not t.startswith("मूलम्") and not t.startswith("पदपाठः") and not t.startswith("पद-पाठः")
              and not _is_translation_summary(t)]

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

  def _insert_before(seq: list[tuple[str, str]], add: list[tuple[str, str]], pred) -> list[tuple[str, str]]:
    if not add:
      return seq
    for idx, (t, _) in enumerate(seq):
      if pred(t):
        return seq[:idx] + add + seq[idx:]
    return add + seq

  if trans_new:
    if any(_is_translation_summary(t) for t, _ in rendered):
      rendered = _insert_after(rendered, trans_new, _is_translation_summary)
    else:
      rendered = _insert_before(rendered, trans_new, lambda t: t.startswith(("मूलम्", "पदपाठः", "पद-पाठः")))
  rendered = _insert_after(rendered, mula_new, lambda t: t.startswith("मूलम्"))
  rendered = _insert_after(rendered, pada_new, lambda t: t.startswith(("पदपाठः", "पद-पाठः", "मूलम्")))
  rendered = _insert_after(
    rendered,
    comm_new,
    lambda t: any(
      x in t for x in (
        "उवट", "महीधर", "सायण", "हरिस्वामी", "शङ्कर", "श्रीमद्वासुदेव", "श्रीनारायण",
        "मानसतरङ्गिणी", "भट्टभास्कर", "आनन्दबोध", "अनन्ताचार्य", "Schroeder",
        "हरदत्त", "त्रिभुवन", "रङ्ग", "विश्वास-टिप्पनी",
      )
    ),
  )

  new_body = "\n\n".join(blk for _, blk in rendered).strip()
  return f"{fm.rstrip()}\n\n{new_body}\n" if fm else f"{new_body}\n"


def _resolve_corpus_spec_for_ref(
  url_or_path: object,
  specs: dict[str, VedaCorpusSpec],
) -> VedaCorpusSpec | None:
  """Resolve a Hugo static URL or filesystem path to its matching ``VedaCorpusSpec``."""
  raw = str(url_or_path).replace("\\", "/")
  best_score = 0
  best_spec: VedaCorpusSpec | None = None

  def _consider(needle: str, spec: VedaCorpusSpec) -> None:
    nonlocal best_score, best_spec
    if not needle:
      return
    norm = needle.rstrip("/") + "/"
    pos = raw.find(norm)
    if pos == -1:
      return
    score = len(norm) + (10000 if raw.startswith(norm) else 0)
    if score > best_score:
      best_score = score
      best_spec = spec

  url_attrs = (
    "vp_url_prefix", "sarva_url_prefix",
    "yajuh_vp_url", "yajuh_sarva_url", "yajuh_sarva_prastuti_url",
    "brahmana_vp_url", "brahmana_sarva_url", "brahmana_sarva_prastuti_url",
  )
  path_attrs = (
    "content_dir", "vp_dir", "sarva_dir",
    "yajuh_vp_dir", "yajuh_sarva_dir", "yajuh_sarva_prastuti_dir",
    "brahmana_vp_dir", "brahmana_sarva_dir", "brahmana_sarva_prastuti_dir",
  )
  for spec in specs.values():
    for attr in url_attrs:
      _consider(getattr(spec, attr, "") or "", spec)
    for attr in path_attrs:
      p_val = getattr(spec, attr, None)
      if p_val is None:
        continue
      p_str = str(p_val).replace("\\", "/")
      _consider(p_str, spec)
      m_rel = re.search(r"/(vedAH(?:_[^/]+)?/.+)$", p_str)
      if m_rel:
        rel_sub = "/" + m_rel.group(1)
        _consider(rel_sub, spec)
        if attr in ("content_dir", "vp_dir", "sarva_dir"):
          url_base = re.sub(r"/(?:content|static)/", "/", rel_sub)
          url_base = re.sub(r"/(?:sarva-prastutiH|vishvAsa-prastutiH|sarvASh_TIkAH)/?$", "/", url_base)
          _consider(url_base, spec)
          content_base = re.sub(r"/(?:sarva-prastutiH|vishvAsa-prastutiH|sarvASh_TIkAH)/?$", "/", rel_sub)
          content_base = re.sub(r"/static/", "/content/", content_base)
          _consider(content_base, spec)
          static_base = re.sub(r"/content/", "/static/", content_base)
          _consider(static_base, spec)
  return best_spec


def _qualify_cross_corpus_title(title: str, src_spec: VedaCorpusSpec) -> str:
  from doc_curation.sanskrit.accent.provenance import is_unqualified_sb_pp_header

  t = title.strip()
  if t == "मूलम्":
    return f"मूलम् - {src_spec.shAkha_label}"
  m_rec = re.fullmatch(r"मूलम्\s*\(([A-Za-z0-9_-]+)\)", t)
  if m_rec:
    return f"मूलम् - {src_spec.shAkha_label} ({m_rec.group(1)})"
  if t == "मूलम् - विस्वरम्":
    return f"मूलम् - विस्वरम् ({src_spec.shAkha_label})"
  if t in ("पदपाठः", "पद-पाठः"):
    if "यान्त्रिकः" not in src_spec.pada_label and (" - " in src_spec.pada_label or "(" in src_spec.pada_label):
      return src_spec.pada_label
    return f"पद-पाठः - {src_spec.shAkha_label}"
  if is_unqualified_sb_pp_header(t):
    return t.replace("पद-पाठः (यान्त्रिकः", f"पद-पाठः (यान्त्रिकः - {src_spec.shAkha_label}", 1)
  return t


def qualify_cross_corpus_sarva_tika(
  rendered_block: str,
  *,
  src_url: str,
  caller_fp: object,
) -> str:
  """Qualify unqualified source headers and preserve ŚB PP adjacency after cross-corpus ``sarvASh_TIkAH`` inlining."""
  from doc_curation_projects.veda.dedup.targets import load_corpus_specs

  specs = load_corpus_specs()
  src_spec = _resolve_corpus_spec_for_ref(src_url, specs)
  caller_spec = _resolve_corpus_spec_for_ref(caller_fp, specs)
  if src_spec is None or caller_spec is None or src_spec.name == caller_spec.name:
    return rendered_block

  m_wrap = re.match(
    r"^\s*(<details(?:\s+open)?>\s*<summary>\s*सर्वाष् टीकाः\s*</summary>)\s*(.*?)\s*</details>\s*$",
    rendered_block,
    re.DOTALL,
  )
  open_tag = m_wrap.group(1) if m_wrap else ""
  body = m_wrap.group(2) if m_wrap else rendered_block

  norm_chunks: list[tuple[str, str, str]] = []
  for kind, data in _split_top_level_chunks(body):
    if kind != "details":
      _, raw_inc = data  # type: ignore[misc]
      norm_chunks.append(("include", "", raw_inc.strip()))
      continue
    ttl, inner = data  # type: ignore[misc]
    new_ttl = _qualify_cross_corpus_title(ttl, src_spec)
    norm_chunks.append(("details", new_ttl, format_details_block(new_ttl, inner)))

  if caller_spec.name in ("SB-M", "SB-K"):
    sb_side_tok = "माध्यन्दिन" if caller_spec.name == "SB-M" else "काण्व"
    def _is_caller_sb_pp(ttl: str) -> bool:
      return ttl.startswith("पद-पाठः (यान्त्रिकः") and sb_side_tok in ttl

    if any(_is_caller_sb_pp(t) for k, t, _ in norm_chunks if k == "details"):
      trad_pada = src_spec.pada_label if ("यान्त्रिकः" not in src_spec.pada_label and (" - " in src_spec.pada_label or "(" in src_spec.pada_label)) else f"पद-पाठः - {src_spec.shAkha_label}"
      foreign_mp: list[tuple[str, str, str]] = []
      kept: list[tuple[str, str, str]] = []
      for item in norm_chunks:
        k, t, blk = item
        if k == "details" and t.startswith(("मूलम्", "पदपाठः", "पद-पाठः")) and (
          src_spec.shAkha_label in t or t == trad_pada
        ) and not _is_caller_sb_pp(t):
          foreign_mp.append(item)
        else:
          kept.append(item)
      if foreign_mp:
        last_sb_pp = max(idx for idx, (k, t, _) in enumerate(kept) if k == "details" and _is_caller_sb_pp(t))
        norm_chunks = kept[: last_sb_pp + 1] + foreign_mp + kept[last_sb_pp + 1 :]

  rebuilt_body = "\n\n".join(blk for _, _, blk in norm_chunks).strip()
  if m_wrap:
    return f"{open_tag}\n\n{rebuilt_body}\n</details>"
  return rebuilt_body

