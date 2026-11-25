"""Structured Markdown section parser, hemistich merger, and renderer for VS-K/VS-M deduplication."""
from __future__ import annotations

import dataclasses
import re
from typing import Sequence

from doc_curation.sanskrit.accent.reconciler import find_js_include_spans
from doc_curation.sanskrit.accent.samhita_splitter import parse_top_level_details

from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import (
  format_details_block,
  merge_author_bodies,
)


@dataclasses.dataclass
class VskSubBlock:
  """One sense-unit block in a VS-K or VS-M section (either inline `<details>` or `<div class='js_include'>`)."""

  av_blocks: list[tuple[str, str]]
  vp: str
  tika_blocks: list[tuple[str, str]]
  is_js_include: bool = False
  raw_html: str = ""
  kandika_ref: str = ""


def _parse_details_children(inner: str) -> list[tuple[str, str]]:
  return [(ttl.strip(), body.strip()) for _, _, ttl, body in parse_top_level_details(inner)]


def _split_top_level_chunks(body: str) -> list[tuple[str, object]]:
  """Split section body cleanly into ordered ('details', title, inner) and ('include', url, raw) chunks."""
  inc_spans = find_js_include_spans(body)
  chunks: list[tuple[str, object]] = []
  cursor = 0
  for s_pos, e_pos in inc_spans:
    if s_pos > cursor:
      for _, _, ttl, inner in parse_top_level_details(body[cursor:s_pos]):
        chunks.append(("details", (ttl.strip(), inner.strip())))
    raw_inc = body[s_pos:e_pos]
    m_url = re.search(r"""url=["']([^"']+)["']""", raw_inc)
    chunks.append(("include", (m_url.group(1) if m_url else "", raw_inc)))
    cursor = e_pos
  if cursor < len(body):
    for _, _, ttl, inner in parse_top_level_details(body[cursor:]):
      chunks.append(("details", (ttl.strip(), inner.strip())))
  return chunks


def parse_vsk_section(section_text: str, ch: int, k_idx: int) -> tuple[str, list[VskSubBlock]]:
  """Parse a VS-K section heading and sense-unit blocks while keeping `js_include`s intact."""
  lines = section_text.splitlines()
  heading = lines[0].strip()
  chunks = _split_top_level_chunks("\n".join(lines[1:]))
  subs: list[VskSubBlock] = []
  pending_av: list[tuple[str, str]] = []
  i = 0
  while i < len(chunks):
    kind, data = chunks[i]
    if kind == "details":
      ttl, inner = data  # type: ignore[misc]
      if "अवतारिका" in ttl:
        pending_av.extend(_parse_details_children(inner))
        i += 1
        continue
      if ttl == "विश्वास-प्रस्तुतिः":
        tika_kids: list[tuple[str, str]] = []
        if i + 1 < len(chunks) and chunks[i + 1][0] == "details" and chunks[i + 1][1][0] == "सर्वाष् टीकाः":  # type: ignore[index]
          tika_kids = _parse_details_children(chunks[i + 1][1][1])  # type: ignore[index]
          i += 2
        elif i + 1 < len(chunks) and chunks[i + 1][0] == "include":
          _, raw_inc = chunks[i + 1][1]  # type: ignore[misc]
          subs.append(VskSubBlock(pending_av, inner, [], is_js_include=True, raw_html=raw_inc, kandika_ref=f"{ch}.{k_idx}"))
          pending_av = []
          i += 2
          continue
        else:
          i += 1
        subs.append(VskSubBlock(pending_av, inner, tika_kids, kandika_ref=f"{ch}.{k_idx}"))
        pending_av = []
        continue
      subs.append(
        VskSubBlock(
          pending_av, "", _parse_details_children(inner) if ttl == "सर्वाष् टीकाः" else [(ttl, inner)],
          kandika_ref=f"{ch}.{k_idx}",
        )
      )
      pending_av = []
      i += 1
    else:
      _, raw_inc = data  # type: ignore[misc]
      combined = raw_inc
      if (
        "Rk/vishvAsa-prastutiH/" in raw_inc
        and i + 1 < len(chunks)
        and chunks[i + 1][0] == "include"
        and "Rk/sarvASh_TIkAH/" in chunks[i + 1][1][0]  # type: ignore[index]
      ):
        combined = raw_inc + "\n" + chunks[i + 1][1][1]  # type: ignore[index]
        i += 2
      else:
        i += 1
      subs.append(VskSubBlock(pending_av, "", [], is_js_include=True, raw_html=combined, kandika_ref=f"{ch}.{k_idx}"))
      pending_av = []
  return heading, subs


def _merge_av_blocks(existing: list[tuple[str, str]], extra: list[tuple[str, str]]) -> list[tuple[str, str]]:
  by_title: dict[str, list[str]] = {}
  order: list[str] = []
  for ttl, body in list(existing) + list(extra):
    if ttl not in by_title:
      by_title[ttl] = []
      order.append(ttl)
    by_title[ttl].append(body)
  return [(ttl, merge_author_bodies(by_title[ttl], strip_trivial_crossref=False)) for ttl in order]


def merge_vsk_hemistich_pair(
  b1: VskSubBlock,
  b2: VskSubBlock,
  next_sub: VskSubBlock | None = None,
) -> tuple[VskSubBlock, VskSubBlock | None]:
  """Merge two consecutive VS-K hemistich blocks matching one Ṛk, relocating any misattached H2 avatārikā."""
  k1, k2 = dict(b1.tika_blocks), dict(b2.tika_blocks)
  h1_av = list(b1.av_blocks)
  moved_mid, moved_tail, next_out = "", "", next_sub

  for ttl, body in b2.av_blocks:
    if "कुविद्" in body and next_out is not None:
      next_out = dataclasses.replace(next_out, av_blocks=_merge_av_blocks(next_out.av_blocks, [(ttl, body)]))
    elif ttl == "आनन्दबोधः - अवतारिका" and "मण्डलं प्रत्याह" in body:
      moved_mid = body
    elif ttl == "आनन्दबोधः - अवतारिका" and body.lstrip().startswith("इत उत्तरं"):
      moved_tail = body
    else:
      h1_av = _merge_av_blocks(h1_av, [(ttl, body)])

  vp_merged = b1.vp.strip() + "  \n" + b2.vp.strip()
  tika_out: list[tuple[str, str]] = []
  all_titles = list(dict.fromkeys([t for t, _ in b1.tika_blocks] + [t for t, _ in b2.tika_blocks]))
  for ttl in all_titles:
    v1, v2 = k1.get(ttl, "").strip(), k2.get(ttl, "").strip()
    if ttl == "Griffith":
      merged_val = " ".join(x for x in (v1, v2) if x)
    elif ttl == "मूलम्":
      merged_val = (v1 + "  \n" + v2).strip() if (v1 and v2) else (v1 or v2)
    elif ttl == "पदपाठः":
      p1_clean = re.sub(r"[।\s]*[०-९]+\s*।?\s*$", "", v1).strip() if v1 else ""
      merged_val = (p1_clean + " " + v2).strip() if (p1_clean and v2) else (v1 or v2)
    elif ttl == "आनन्दबोध-टीका":
      merged_val = merge_author_bodies([p for p in (v1, moved_mid, v2, moved_tail) if p])
    else:
      merged_val = merge_author_bodies([v1, v2])
    if merged_val:
      tika_out.append((ttl, merged_val))

  if not any(t == "आनन्दबोध-टीका" for t, _ in tika_out) and (moved_mid or moved_tail):
    tika_out.append(("आनन्दबोध-टीका", "\n\n".join(p for p in (moved_mid, moved_tail) if p)))
  return VskSubBlock(h1_av, vp_merged, tika_out, kandika_ref=b1.kandika_ref), next_out


def render_sarva_avatarikah(av_blocks: Sequence[tuple[str, str]]) -> str:
  """Render `<details><summary>सर्वा अवतारिकाः</summary>` containing author blocks."""
  kids = [format_details_block(ttl, body) for ttl, body in av_blocks if body.strip()]
  return "<details><summary>सर्वा अवतारिकाः</summary>\n" + "\n".join(kids) + "\n</details>" if kids else ""


def render_inline_vp_and_sarva(vp: str, tika_blocks: Sequence[tuple[str, str]]) -> str:
  """Render inline `विश्वास-प्रस्तुतिः` + `सर्वाष् टीकाः` blocks."""
  parts: list[str] = []
  if vp.strip():
    parts.append(format_details_block("विश्वास-प्रस्तुतिः", vp.strip(), is_open=True) + "\n")
  if tika_blocks:
    kids = [format_details_block(ttl, body) for ttl, body in tika_blocks if body.strip()]
    if kids:
      parts.append("<details><summary>सर्वाष् टीकाः</summary>\n" + "\n".join(kids) + "\n</details>")
  return "\n".join(parts)


def render_js_include_stub(url: str, *, title: str | None = None, collapsed: bool = False, includetitle: str | None = None) -> str:
  """Render an unfilled `<div class='js_include'>` placeholder matching VS-M/Taittirīya conventions."""
  cls = "js_include collapsed" if collapsed else "js_include"
  if includetitle is not None:
    return f'<div class="{cls}" includetitle="{includetitle}" newlevelforh1="3" unfilled url="{url}">\n</div>'
  sum_tag = "<details>" if collapsed else "<details open>"
  return (
    f'<div class="{cls}" newlevelforh1="3" title="{title}" unfilled url="{url}">\n'
    f"{sum_tag}<summary><h3>{title} ...{{Loading}}...</h3></summary>\n</details>\n</div>"
  )


def render_vsk_section(heading: str, subs: Sequence[VskSubBlock]) -> str:
  """Serialize a parsed/updated VS-K section cleanly back to Markdown."""
  out: list[str] = [heading]
  for sub in subs:
    if av_txt := render_sarva_avatarikah(sub.av_blocks):
      out.append(av_txt)
    if sub.is_js_include:
      if sub.vp.strip():
        out.append(format_details_block("विश्वास-प्रस्तुतिः", sub.vp.strip(), is_open=True) + "\n")
      out.append(sub.raw_html.strip())
    elif rendered := render_inline_vp_and_sarva(sub.vp, sub.tika_blocks):
      out.append(rendered)
  return "\n".join(out).rstrip() + "\n"
