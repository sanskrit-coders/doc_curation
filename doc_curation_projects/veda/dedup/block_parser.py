"""Unified section/stream block parser and partial-include sweeper across VS, TS, TB, and TK hosts."""
from __future__ import annotations

import dataclasses
import re
from typing import Sequence

from doc_curation.sanskrit.accent.reconciler import find_js_include_spans
from doc_curation.sanskrit.accent.samhita_splitter import parse_top_level_details
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.section_parser import render_js_include_stub
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import format_details_block

_URL_RE = re.compile(r"""url=["']([^"']+)["']""")


@dataclasses.dataclass
class HostToken:
  """One top-level token inside a Vedic Markdown file body preserving exact non-block text."""

  kind: str  # "text", "details", "include"
  raw: str
  title: str = ""
  body: str = ""
  url: str = ""
  is_open: bool = False


@dataclasses.dataclass
class MantraGroup:
  """Structured group corresponding to one mantra/vākya block in a host file."""

  av_token_idx: int | None
  vp_token_idx: int | None  # either inline <details>vp</details> OR <div class="js_include" url=...vp/combined>
  tika_token_indices: list[int]  # inline <details>सर्वाष् टीकाः</details> and/or include sarvASh_TIkAH/
  vp_summary: str = ""
  vp_text: str = ""
  is_vp_include: bool = False
  vp_include_url: str = ""
  inline_tika_items: list[tuple[str, str]] = dataclasses.field(default_factory=list)
  inline_tika_idx: int | None = None
  inline_tika_indices: list[int] = dataclasses.field(default_factory=list)
  sarva_include_url: str = ""
  sarva_include_idx: int | None = None
  is_combined_include: bool = False


def tokenize_markdown_body(body: str) -> list[HostToken]:
  """Tokenize body cleanly into non-overlapping top-level `text`, `details`, and `include` spans."""
  spans: list[tuple[int, int, str, object]] = []
  inc_spans = find_js_include_spans(body)
  for a, b in inc_spans:
    raw = body[a:b]
    m_url = _URL_RE.search(raw)
    spans.append((a, b, "include", (m_url.group(1) if m_url else "", raw)))
  for a, b, ttl, inner in parse_top_level_details(body):
    if any((ia <= a and b <= ib) or (a <= ia and ib <= b) for ia, ib in inc_spans):
      continue
    open_tag = body[a : body.find(">", a) + 1]
    spans.append((a, b, "details", (ttl.strip(), inner.strip(), " open" in open_tag)))
  spans.sort(key=lambda x: x[0])

  tokens: list[HostToken] = []
  cur = 0
  for a, b, kind, data in spans:
    if a > cur and body[cur:a]:
      tokens.append(HostToken(kind="text", raw=body[cur:a]))
    if kind == "include":
      url, raw = data  # type: ignore[misc]
      tokens.append(HostToken(kind="include", raw=raw, url=url))
    else:
      ttl, inner, is_open = data  # type: ignore[misc]
      tokens.append(HostToken(kind="details", raw=body[a:b], title=ttl, body=inner, is_open=is_open))
    cur = b
  if cur < len(body) and body[cur:]:
    tokens.append(HostToken(kind="text", raw=body[cur:]))
  return tokens


def _is_vp_details(tok: HostToken) -> bool:
  return tok.kind == "details" and tok.title.startswith("विश्वास-प्रस्तुतिः")


def _is_tika_details(tok: HostToken) -> bool:
  return tok.kind == "details" and tok.title == "सर्वाष् टीकाः"


def _is_av_details(tok: HostToken) -> bool:
  return tok.kind == "details" and "अवतारिका" in tok.title


def _is_vp_include(tok: HostToken) -> bool:
  return tok.kind == "include" and "/vishvAsa-prastutiH/" in tok.url


def _is_sarva_include(tok: HostToken) -> bool:
  return tok.kind == "include" and "/sarvASh_TIkAH/" in tok.url


def _is_combined_include(tok: HostToken) -> bool:
  return tok.kind == "include" and (
    "/yajuH/sarva-prastutiH/" in tok.url or "/brAhmaNam/sarva-prastutiH/" in tok.url
  )


def group_mantra_units(tokens: Sequence[HostToken]) -> list[MantraGroup]:
  """Group sequential top-level tokens into logical mantra/vākya units without disturbing headings/prose."""
  groups: list[MantraGroup] = []
  pending_av: int | None = None
  i = 0
  while i < len(tokens):
    tok = tokens[i]
    if tok.kind == "text":
      if "____" in tok.raw or re.search(r"(?m)^##+\s", tok.raw):
        pending_av = None
      i += 1
      continue
    if _is_av_details(tok):
      pending_av = i
      i += 1
      continue

    if _is_combined_include(tok):
      groups.append(
        MantraGroup(
          av_token_idx=pending_av,
          vp_token_idx=i,
          tika_token_indices=[],
          is_vp_include=True,
          vp_include_url=tok.url,
          is_combined_include=True,
        )
      )
      pending_av = None
      i += 1
      continue

    if _is_vp_details(tok) or _is_vp_include(tok):
      grp = MantraGroup(
        av_token_idx=pending_av,
        vp_token_idx=i,
        tika_token_indices=[],
        vp_summary=tok.title if tok.kind == "details" else "विश्वास-प्रस्तुतिः",
        vp_text=tok.body if tok.kind == "details" else "",
        is_vp_include=(tok.kind == "include"),
        vp_include_url=tok.url if tok.kind == "include" else "",
      )
      pending_av = None
      j = i + 1
      while j < len(tokens):
        nt = tokens[j]
        if nt.kind == "text":
          if nt.raw.strip():
            break
          j += 1
          continue
        if _is_tika_details(nt):
          grp.tika_token_indices.append(j)
          if grp.inline_tika_idx is None:
            grp.inline_tika_idx = j
          grp.inline_tika_indices.append(j)
          grp.inline_tika_items.extend((k.strip(), v.strip()) for _, _, k, v in parse_top_level_details(nt.body))
          j += 1
          continue
        if _is_sarva_include(nt):
          grp.tika_token_indices.append(j)
          grp.sarva_include_idx = j
          grp.sarva_include_url = nt.url
          j += 1
          continue
        break
      groups.append(grp)
      i = j
      continue

    pending_av = None
    i += 1
  return groups


def replace_group_tokens(
  tokens: list[HostToken],
  grp: MantraGroup,
  *,
  new_vp_raw: str | None = None,
  new_sarva_stub: str | None = None,
  drop_inline_tika: bool = False,
  drop_sarva_include: bool = False,
) -> None:
  """Update tokens for a single `MantraGroup` in-place while preserving intervening whitespace."""
  if new_vp_raw is not None and grp.vp_token_idx is not None:
    tokens[grp.vp_token_idx] = HostToken(kind="include", raw=new_vp_raw)
  t_idxs = grp.inline_tika_indices or ([grp.inline_tika_idx] if grp.inline_tika_idx is not None else [])
  if drop_inline_tika and t_idxs:
    for ti in t_idxs:
      tokens[ti] = HostToken(kind="text", raw="")
      if ti + 1 < len(tokens) and tokens[ti + 1].kind == "text" and not tokens[ti + 1].raw.strip():
        tokens[ti + 1] = HostToken(kind="text", raw="")
  if drop_sarva_include and grp.sarva_include_idx is not None:
    tokens[grp.sarva_include_idx] = HostToken(kind="text", raw="")
  if new_sarva_stub is not None:
    if grp.sarva_include_idx is not None:
      tokens[grp.sarva_include_idx] = HostToken(kind="include", raw=new_sarva_stub)
    elif grp.inline_tika_idx is not None and not drop_inline_tika:
      tokens[grp.inline_tika_idx] = HostToken(kind="include", raw=new_sarva_stub)
    elif grp.inline_tika_idx is not None and drop_inline_tika:
      tokens[grp.inline_tika_idx] = HostToken(kind="include", raw="\n\n" + new_sarva_stub)
    elif grp.vp_token_idx is not None:
      tokens[grp.vp_token_idx].raw = tokens[grp.vp_token_idx].raw.rstrip() + "\n\n" + new_sarva_stub


def render_tokens(fm: str, tokens: Sequence[HostToken]) -> str:
  body = "".join(t.raw for t in tokens)
  body = re.sub(r"\n{3,}", "\n\n", body).strip()
  return f"{fm.rstrip()}\n\n{body}\n" if fm else f"{body}\n"


def render_host_include_pair(
  *,
  exact_reading: bool,
  local_vp_text: str = "",
  local_vp_summary: str = "विश्वास-प्रस्तुतिः",
  vp_url: str = "",
  sarva_url: str = "",
  combined_url: str = "",
  heading_level: int = 4,
) -> tuple[str | None, str | None]:
  """Build standard stub pair ``(new_vp_raw_or_None, new_sarva_stub_or_None)`` for a host group."""
  if exact_reading and combined_url:
    return (
      f'<div class="js_include" includetitle="false" newlevelforh1="{heading_level}" unfilled url="{combined_url}"></div>',
      None,
    )
  tk_stub = render_js_include_stub(sarva_url, title="सर्वाष् टीकाः", collapsed=True, heading_level=heading_level)
  if exact_reading and vp_url:
    vp_stub = render_js_include_stub(vp_url, title="विश्वास-प्रस्तुतिः", collapsed=False, heading_level=heading_level)
    return vp_stub, tk_stub
  vp_local = format_details_block(local_vp_summary, local_vp_text, is_open=True)
  return vp_local, tk_stub
