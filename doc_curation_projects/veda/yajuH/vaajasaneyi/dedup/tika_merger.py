"""Shared commentary merging and `सर्वाष् टीकाः` block ordering for `Rk` and `yajuH` deduplication."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Sequence

from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.norm import normalize_phonetic

KANVA_TIKA_AUTHOR_MAP: tuple[tuple[str, str], ...] = (
  ("सायण-टीका", "सायण-टीका (काण्वी)"),
  ("आनन्दबोध-टीका", "आनन्दबोध-टीका"),
  ("अनन्ताचार्य-टीका", "अनन्ताचार्य-टीका"),
)
EARLY_CLASSICAL_SUMMARIES = frozenset({
  "उवट-टीका", "महीधर-टीका", "सायण-टीका", "सायणटीका", "भट्टभास्कर-टीका",
})
KANVA_MANAGED_TIKA_SUMMARIES = frozenset({
  "मूलम् - काण्वम्", "पदपाठः - काण्वः", "सायण-टीका (काण्वी)", "आनन्दबोध-टीका", "अनन्ताचार्य-टीका",
})


def format_details_block(summary: str, body: str, *, is_open: bool = False) -> str:
  """Render one `<details>` Markdown block."""
  open_attr = " open" if is_open else ""
  return f"<details{open_attr}><summary>{summary}</summary>\n\n{body.strip()}\n</details>"


def merge_author_bodies(bodies: Sequence[str], *, strip_trivial_crossref: bool = True) -> str:
  """Merge commentary strings cleanly, deduplicating repeats and suppressing trivial cross-refs when richer glosses exist."""
  cleaned = [b.strip() for b in bodies if b and b.strip()]
  if not cleaned:
    return ""
  if strip_trivial_crossref:
    substantive = [
      b for b in cleaned
      if not (len(re.sub(r"\s+", "", b)) < 90 and re.search(r"व्याख्यात|उक्तार्थ|गतम्", b))
    ]
    if substantive:
      cleaned = substantive
  deduped: list[str] = []
  seen_norm: set[str] = set()
  for b in cleaned:
    key = normalize_phonetic(b, include_accents=False, fold_orthography=True) or b
    if key not in seen_norm:
      seen_norm.add(key)
      deduped.append(b)
  return "\n\n".join(deduped)


def collect_kanva_tika_additions(vsk_entries: Sequence[dict]) -> tuple[bool, str, str, dict[str, str]]:
  """Collect deduplicated Kāṇva Mūlam, Padapāṭha, and ṭīkā bodies across matched VS-K occurrences."""
  has_variant = any(not e["is_exact_reading"] for e in vsk_entries)
  seen_mulas: list[str] = []
  seen_m_keys: set[str] = set()
  padas: list[str] = []
  seen_p_keys: set[str] = set()
  by_author: dict[str, list[str]] = defaultdict(list)

  for e in vsk_entries:
    kd = dict(e["tika_blocks"])
    m_txt = kd.get("मूलम्", "").strip()
    if m_txt:
      m_key = normalize_phonetic(m_txt, include_accents=True, fold_orthography=True)
      if m_key not in seen_m_keys:
        seen_m_keys.add(m_key)
        seen_mulas.append(m_txt)
    p_txt = kd.get("पदपाठः", "").strip()
    if p_txt:
      p_key = normalize_phonetic(p_txt, include_accents=True, fold_orthography=True)
      if p_key not in seen_p_keys:
        seen_p_keys.add(p_key)
        padas.append(p_txt)
    for src_lbl, dst_lbl in KANVA_TIKA_AUTHOR_MAP:
      val = kd.get(src_lbl, "").strip()
      if val:
        by_author[dst_lbl].append(val)

  author_merged = {
    dst_lbl: merged
    for _, dst_lbl in KANVA_TIKA_AUTHOR_MAP
    if (merged := merge_author_bodies(by_author.get(dst_lbl, ())))
  }
  return has_variant, "\n\n".join(seen_mulas), "\n\n".join(padas), author_merged


def merge_sarva_tikaa_chunks(
  chunks: Sequence[tuple[str, object]],
  vsk_entries: Sequence[dict],
) -> list[str]:
  """Merge Kāṇva blocks cleanly into ordered `सर्वाष् टीकाः` top-level blocks/includes."""
  has_variant, mula_k, pada_k, auth_map = collect_kanva_tika_additions(vsk_entries)
  base_chunks: list[tuple[str, str, str]] = []
  for kind, data in chunks:
    if kind == "details":
      ttl, inner = data  # type: ignore[misc]
      if ttl in KANVA_MANAGED_TIKA_SUMMARIES:
        continue
      if has_variant and ttl == "मूलम्":
        ttl = "मूलम् - माध्यन्दिनम्"
      base_chunks.append(("details", ttl, inner))
    else:
      _, raw_inc = data  # type: ignore[misc]
      base_chunks.append(("include", "", raw_inc))

  has_nested_inc = any(k == "include" for k, _, _ in base_chunks)
  out_blocks: list[str] = []
  inserted_mula_k = False
  inserted_pada_k = False
  inserted_tikas = False

  def _append_tikas() -> None:
    nonlocal inserted_tikas
    if inserted_tikas:
      return
    for _, dst_lbl in KANVA_TIKA_AUTHOR_MAP:
      if auth_map.get(dst_lbl):
        out_blocks.append(format_details_block(dst_lbl, auth_map[dst_lbl]))
    inserted_tikas = True

  last_classical_i = max(
    (i for i, (k_kind, ttl, _) in enumerate(base_chunks) if k_kind == "details" and ttl in EARLY_CLASSICAL_SUMMARIES),
    default=-1,
  )

  for idx, (k_kind, ttl, inner) in enumerate(base_chunks):
    if k_kind == "include":
      if has_variant and mula_k and not inserted_mula_k:
        out_blocks.append(format_details_block("मूलम् - काण्वम्", mula_k))
        inserted_mula_k = True
      if pada_k and not inserted_pada_k:
        out_blocks.append(format_details_block("पदपाठः - काण्वः", pada_k))
        inserted_pada_k = True
      out_blocks.append(inner.strip())
      continue

    out_blocks.append(format_details_block(ttl, inner))
    if has_variant and mula_k and not inserted_mula_k and ttl in ("मूलम् - माध्यन्दिनम्", "मूलम् - तैत्तिरीयम्", "मूलम्"):
      nxt_is_mula = idx + 1 < len(base_chunks) and base_chunks[idx + 1][1].startswith("मूलम्")
      if not nxt_is_mula:
        out_blocks.append(format_details_block("मूलम् - काण्वम्", mula_k))
        inserted_mula_k = True
    if pada_k and not inserted_pada_k and ("पदपाठः" in ttl or "पद-पाठः" in ttl):
      nxt_is_pada = idx + 1 < len(base_chunks) and (
        "पदपाठः" in base_chunks[idx + 1][1] or "पद-पाठः" in base_chunks[idx + 1][1]
      )
      if not nxt_is_pada:
        out_blocks.append(format_details_block("पदपाठः - काण्वः", pada_k))
        inserted_pada_k = True
    if not has_nested_inc and idx == last_classical_i:
      _append_tikas()

  if has_variant and mula_k and not inserted_mula_k:
    out_blocks.insert(0, format_details_block("मूलम् - काण्वम्", mula_k))
  if pada_k and not inserted_pada_k:
    pos_p = 1 if (out_blocks and "मूलम्" in out_blocks[0]) else 0
    out_blocks.insert(pos_p, format_details_block("पदपाठः - काण्वः", pada_k))
  if not inserted_tikas and not (
    has_nested_inc and all(len(re.sub(r"\s+", "", v)) < 90 and "व्याख्यात" in v for v in auth_map.values())
  ):
    _append_tikas()
  return out_blocks
