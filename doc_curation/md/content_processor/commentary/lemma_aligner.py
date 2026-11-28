"""Quote-anchored alignment of Smṛti / Śāstra commentaries against root verses.

Splits commentary Markdown files that interleave quoted root-verse lemmata
(``> **...**``, standalone bold verses, or page-numbered lemma spans) with
prose exposition, Smṛti citations, per-verse italic avatārikās, prakaraṇa
introductions, and external footnote definitions into per-verse commentary
blocks and file-level prakaraṇa introductions with 100% prose conservation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import re as std_re

import regex
from indic_transliteration import sanscript

from doc_curation.llm.proofreader.interleave_aligner import normalize_for_alignment
from doc_curation.llm.proofreader.interleave_helper import sanitize_details_footnotes


_FRONTMATTER_RE = regex.compile(r"\A(?:\+\+\+.*?\n\+\+\+|\-\-\-.*?\n\-\-\-)[ \t]*(?:\n|$)", flags=regex.DOTALL)
_ITALIC_AVATARIKA_RE = regex.compile(r"^_[^\n]+_(?:\s*(?:।|॥|\.|-|\[\^[^\]]+\]))*\s*$")
_BRACKET_PREFIX_RE = regex.compile(r"^\*\*\[([^\]]+)\]\*\*(?:\s*\t?\s*(.*))?$")
_FOREIGN_CITE_RE = regex.compile(r"\((?:म्ध्|न्स्म्|क्स्म्|वध्|आप्ध्|बृ|का|गा|मनु|नारद|बौधायन|गौतम)")
_OPENING_TITLE_RE = regex.compile(
  r"^(?:"
  r"\*\*\[?(?:अथ|अथा|तत्र)[^*]*?(?:प्रकरण|पर्करण|टीकारम्भ|सटीक)[^*]*\]?\*\*\s*[।॥\.]*"
  r"|\*\*[^*]*(?:प्र|पर्)करणम्?\s*(?:[।॥\(\)\d०-९\s\-—]*)?\*\*\s*[।॥\.]*"
  r"|\[?अथ\s+सटीक[ा]?याज्ञव?ल्?क्यस्मृतौ\]?"
  r"|[\p{Devanagari}\s]+(?:प्र|पर्)करणम्\s*[।॥\(\)\d०-९\s]*\]"
  r"|\*\*\[तत्र\b[^\]]*\]\*\*"
  r"|\*\*\(?अथ\s+टीकारम्भः\)?\*\*"
  r"|\*\*स्नातकव्रतप्रकरणम्[^\n]*"
  r"|\*\*विनायकपूजाविधिप्रकरणम्[^\n]*"
  r"|\*\*भोज्याभोज्य[^\n]*प्रकरणम्[^\n]*"
  r")$"
)
_CLOSING_COLOPHON_RE = regex.compile(
  r"^(?:"
  r"\*\*(?:इति|इत्य्)\b[^\n]*"
  r"|\*\*(?:प्रभूत)?श्रीमद[^\n]*"
  r"|\*\*विश्वरूपकृत[^\n]*"
  r"|\*\*(?:प्रथमो|द्वितीयो|तृतीयो)\s*ऽध्यायः[^\n]*"
  r"|\*\*(?:समाप्त|समाप्तेयं)[^\n]*"
  r"|\*\*[^*]*काण्डं\s*\(प्रकरणं\)\s*समाप्तम्[^\n]*"
  r"|\*\*ऋणादानप्रकरणम्[^\n]*"
  r"|\*\*[^*]+विधिः?\s*॥\*\*"
  r"|\*\*[^*]+विधानम्\s*॥\*\*"
  r"|\*\*इति\s+दिव्यमातृका[^\n]*"
  r")$"
)
_NOISE_MARKER_RE = regex.compile(r"^(?:>\s*\*\*|>\s*|\*\*\s*)$")

# Definition block supporting both `[^id]: ...` and `[^id]- ...` with multiline continuations.
_FOOTNOTE_DEF_RE = regex.compile(
  r"(?m)^(?P<ref>\[\^(?P<id>[^\]\n]+?) *\])[:\-]"
  r"(?P<content>[^\n]*"
  r"(?:\n(?![ \t]*\n)(?!\[\^)(?!#)(?!<)[^\n]*)*"
  r"(?:(?:\n[ \t]*)+\n(?: {3,}|\t)[^\n]*"
  r"(?:\n(?![ \t]*\n)(?!\[\^)(?!#)(?!<)[^\n]*)*)*)"
)
_FOOTNOTE_REF_RE = regex.compile(r"\[\^([^\]\n]+?)\]")


@dataclass(frozen=True)
class VerseSpec:
  """Canonical root verse entry aligned against commentary lines."""

  index: int
  verse_id: str
  section_id: str
  text: str
  compact: str = ""
  title: str = ""
  grams: frozenset[str] = field(default_factory=frozenset)

  @classmethod
  def from_text(cls, index: int, verse_id: str, section_id: str, text: str, title: str = "") -> "VerseSpec":
    """Build a VerseSpec precomputing normalized text and 4-gram index set."""
    compact, grams = _compact_and_grams(text)
    return cls(
      index=index,
      verse_id=verse_id,
      section_id=section_id,
      text=text.strip(),
      compact=compact,
      title=title,
      grams=grams,
    )


@dataclass(frozen=True)
class _CandLine:
  file_idx: int
  section_id: str
  line_idx: int
  raw: str
  compact: str
  is_bold: bool
  group_id: int


def strip_frontmatter(text: str) -> tuple[str, str]:
  """Return ``(frontmatter_with_trailing_newlines, body)`` from Markdown text."""
  m = _FRONTMATTER_RE.match(text)
  if not m:
    return "", text
  return text[: m.end()], text[m.end() :]


def _digit_variants(fid: str) -> list[str]:
  fid = fid.strip()
  variants = [fid]
  deva = sanscript.transliterate(fid, sanscript.HK, sanscript.DEVANAGARI)
  ascii_v = sanscript.transliterate(fid, sanscript.DEVANAGARI, sanscript.HK)
  for v in (deva, ascii_v):
    if v and v not in variants:
      variants.append(v)
  return variants


def parse_footnotes_markdown(text: str) -> dict[str, str]:
  """Parse ``[^id]: body`` and ``[^id]- body`` footnote definitions from Markdown text.

  Returns a dictionary keyed by both original and Devanagari/ASCII digit variants.
  """
  _, body = strip_frontmatter(text)
  notes: dict[str, str] = {}
  for m in _FOOTNOTE_DEF_RE.finditer(body):
    fid = m.group("id").strip()
    raw_lines = m.group("content").splitlines()
    # Dedent uniform leading whitespace on continuation lines while keeping single clean paragraphs.
    cleaned_lines = [raw_lines[0].strip()] if raw_lines else []
    for ln in raw_lines[1:]:
      stripped = regex.sub(r"^(?:\t| {1,5})", "", ln.rstrip())
      cleaned_lines.append(stripped)
    val = "\n".join(cleaned_lines).strip()
    for key in _digit_variants(fid):
      notes[key] = val
  return notes


def inline_footnotes_for_block(text: str, footnotes_by_id: dict[str, str]) -> str:
  """Convert ``[^id]`` references to ``[id]`` and append matching definitions inside a details block."""
  if "[^" not in text:
    return text
  seen: list[str] = []
  for m in _FOOTNOTE_REF_RE.finditer(text):
    fid = m.group(1).strip()
    if fid not in seen:
      seen.append(fid)
  sanitized = sanitize_details_footnotes(text).rstrip()
  defs: list[str] = []
  for fid in seen:
    body = None
    for key in _digit_variants(fid):
      if key in footnotes_by_id:
        body = footnotes_by_id[key]
        break
    if body:
      if "\n" in body:
        indented = "\n".join(f"    {ln}" if ln else "" for ln in body.splitlines())
        defs.append(f"[{fid}]:\n{indented}")
      else:
        defs.append(f"[{fid}]: {body}")
  if not defs:
    return sanitized
  return f"{sanitized}\n\n" + "\n\n".join(defs)


def _strip_trailing_empty_markers(lines: list[str]) -> list[str]:
  end = len(lines)
  while end > 0 and lines[end - 1].strip() in ("", "> **", ">", "**"):
    if lines[end - 1].strip() == "" and end >= 2 and lines[end - 2].strip() in ("> **", ">", "**"):
      end -= 2
      continue
    if lines[end - 1].strip() in ("> **", ">", "**"):
      end -= 1
      continue
    break
  return lines[:end]


def _bold_coverage(stripped_no_gt: str) -> tuple[bool, bool]:
  """Return ``(starts_or_mostly_bold, has_marker)`` for a line stripped of leading ``>``."""
  no_page = regex.sub(r"\*\*\[[^\]]+\]\*\*|\*\*\[[^\]]+$", "", stripped_no_gt).strip()
  bold_spans = regex.findall(r"\*\*([^*]+)\*\*", no_page)
  if not bold_spans:
    return False, False
  total_chars = len(regex.sub(r"[\s।॥\[\]\d०-९\.\*\-]", "", no_page))
  bold_chars = len(regex.sub(r"[\s।॥\[\]\d०-९\.\*\-]", "", "".join(bold_spans)))
  if total_chars == 0:
    return False, False
  mostly_bold = (bold_chars / total_chars) >= 0.65
  return mostly_bold, True


def _clean_candidate_compact(line: str) -> str:
  cl = regex.sub(r"^(?:>\s*)+", "", line.strip())
  cl = regex.sub(r"\*\*\[[^\]]+\]\*\*|\*\*\[[^\]]+$", "", cl).replace("*", "")
  cl = regex.sub(r"॥[^॥]*॥", "", cl)
  cl = regex.sub(r"\[[^\]]*\]", "", cl)
  return normalize_for_alignment(cl)["compact"]


def _is_opening_title(line: str) -> bool:
  s = line.strip()
  return bool(s) and bool(_OPENING_TITLE_RE.match(s))


def _is_heading_or_colophon(line: str) -> bool:
  s = line.strip()
  return bool(s) and bool(_OPENING_TITLE_RE.match(s) or _CLOSING_COLOPHON_RE.match(s) or _NOISE_MARKER_RE.match(s))


def _score_candidate(cc: str, c_grams: set[str], verse: VerseSpec, same_section: bool) -> float:
  if not cc or not verse.compact:
    return 0.0
  if len(cc) >= 8 and cc in verse.compact:
    base = 1.0
  else:
    if not c_grams or not verse.grams:
      return 0.0
    ov = len(c_grams & verse.grams)
    if ov < 4:
      return 0.0
    base = ov / len(c_grams)
  return base + (0.20 if same_section else 0.0)


def _extract_section_cands(
  section_files: list[tuple[str, str]],
) -> tuple[list[list[str]], list[_CandLine]]:
  """Parse lines per file and identify contiguous candidate stanza groups."""
  file_lines: list[list[str]] = []
  cands: list[_CandLine] = []
  group_counter = 0

  for f_idx, (sec_id, raw_text) in enumerate(section_files):
    _, body = strip_frontmatter(raw_text)
    lines = _strip_trailing_empty_markers(body.splitlines())
    file_lines.append(lines)

    after_bracket = False
    in_cand_group = False
    for li, raw in enumerate(lines):
      s = raw.strip()
      if not s:
        # Allow a single blank line directly after a page marker inside one quote stanza.
        if not after_bracket:
          in_cand_group = False
        continue
      if _is_heading_or_colophon(s):
        after_bracket = False
        in_cand_group = False
        continue

      is_bracket = bool(_BRACKET_PREFIX_RE.match(s))
      no_gt = regex.sub(r"^(?:>\s*)+", "", s)
      mostly_bold, _ = _bold_coverage(no_gt)

      is_bold_line = False
      if s.startswith(">"):
        is_bold_line = mostly_bold
      elif mostly_bold and ("॥" in s or "।" in s or is_bracket or len(regex.sub(r"[*\s]", "", s)) >= 20):
        is_bold_line = True

      is_cand = is_bold_line or is_bracket or (after_bracket and s.startswith(">"))
      after_bracket = is_bracket
      if not is_cand:
        in_cand_group = False
        continue
      if not is_bold_line and _FOREIGN_CITE_RE.search(s):
        in_cand_group = False
        continue

      cc = _clean_candidate_compact(s)
      if len(cc) < 8:
        continue

      if not in_cand_group:
        group_counter += 1
        in_cand_group = True

      cands.append(
        _CandLine(
          file_idx=f_idx,
          section_id=sec_id,
          line_idx=li,
          raw=s,
          compact=cc,
          is_bold=is_bold_line,
          group_id=group_counter,
        )
      )

  return file_lines, cands


def _monotonic_dp_assign(cands: list[_CandLine], verses: list[VerseSpec]) -> dict[int, int]:
  """Pass 1: Global strictly non-decreasing DP alignment of candidate lines to root verses."""
  v_count = len(verses)
  if not cands or not v_count:
    return {}

  gram_idx: dict[str, list[int]] = defaultdict(list)
  for v in verses:
    for g in v.grams:
      gram_idx[g].append(v.index)

  nodes: list[tuple[int, int, float, int]] = [(-1, -1, 0.0, -1)]
  best_for_v = [0] * v_count
  best_v_val = [0.0] * v_count

  for ci, cand in enumerate(cands):
    c_grams = {cand.compact[k : k + 4] for k in range(max(1, len(cand.compact) - 3))}
    hit_verses: set[int] = set()
    for g in c_grams:
      for vi in gram_idx.get(g, ()):
        hit_verses.add(vi)
    thresh = 0.38 if cand.is_bold else 0.55

    updates: list[tuple[int, float, int]] = []
    for vi in hit_verses:
      sc = _score_candidate(cand.compact, c_grams, verses[vi], cand.section_id == verses[vi].section_id)
      raw_sc = sc - (0.20 if cand.section_id == verses[vi].section_id else 0.0)
      if raw_sc < thresh:
        continue
      prev_node = best_for_v[vi]
      prev_sc = best_v_val[vi]
      cur_node_v = nodes[prev_node][1]
      gain = sc if vi > cur_node_v else sc * 0.4
      updates.append((vi, prev_sc + gain, prev_node))

    if not updates:
      continue
    changed = False
    for vi, tot, par in updates:
      if tot > best_v_val[vi]:
        nid = len(nodes)
        nodes.append((ci, vi, tot, par))
        best_v_val[vi] = tot
        best_for_v[vi] = nid
        changed = True
    if changed:
      for v in range(1, v_count):
        if best_v_val[v - 1] > best_v_val[v]:
          best_v_val[v] = best_v_val[v - 1]
          best_for_v[v] = best_for_v[v - 1]

  assign: dict[int, int] = {}
  cur = best_for_v[v_count - 1]
  while cur > 0:
    ci, vi, _, par = nodes[cur]
    assign[ci] = vi
    cur = par
  return assign


def _reclaim_local_transposed(
  cands: list[_CandLine],
  assign: dict[int, int],
  verses: list[VerseSpec],
) -> None:
  """Pass 2: Reclaim unassigned bold stanza groups (transpositions or variant half-verses)."""
  if not cands or not verses:
    return

  sec_ranges: dict[str, tuple[int, int]] = {}
  for v in verses:
    if v.section_id not in sec_ranges:
      sec_ranges[v.section_id] = (v.index, v.index)
    else:
      lo, hi = sec_ranges[v.section_id]
      sec_ranges[v.section_id] = (lo, v.index)

  # Group consecutive unassigned bold cands sharing a contiguous stanza group
  groups: dict[int, list[int]] = defaultdict(list)
  for ci, cand in enumerate(cands):
    groups[cand.group_id].append(ci)

  anchor_cis = sorted(assign)
  v_count = len(verses)

  for gid, g_cis in groups.items():
    if any(ci in assign for ci in g_cis):
      continue
    if not any(cands[ci].is_bold for ci in g_cis):
      continue

    sec_id = cands[g_cis[0]].section_id
    s_lo, s_hi = sec_ranges.get(sec_id, (0, v_count - 1))
    lv = max((assign[x] for x in anchor_cis if x < g_cis[0]), default=s_lo)
    rv = min((assign[x] for x in anchor_cis if x > g_cis[-1]), default=s_hi)
    lo = max(0, min(lv, s_lo) - 10)
    hi = min(v_count - 1, max(rv, s_hi) + 10)

    # Try merged group text first, then individual lines
    merged_cc = "".join(cands[ci].compact for ci in g_cis)
    texts_to_try = [merged_cc] + [cands[ci].compact for ci in g_cis]
    best_vi, best_raw = None, 0.0
    for txt in texts_to_try:
      if len(txt) < 8:
        continue
      t_grams = {txt[k : k + 4] for k in range(max(1, len(txt) - 3))}
      for vi in range(lo, hi + 1):
        sc = _score_candidate(txt, t_grams, verses[vi], same_section=(verses[vi].section_id == sec_id))
        raw_sc = sc - (0.20 if verses[vi].section_id == sec_id else 0.0)
        if sc > best_raw + 0.001 and raw_sc >= 0.35:
          best_raw = sc
          best_vi = vi
    # Narrow 3-gram gap-fill strictly between unmatched verses inside tight anchor bounds
    if best_vi is None and lv + 1 < rv and (rv - lv) <= 6 and len(merged_cc) >= 16:
      used_vs = set(assign.values())
      g3_c = {merged_cc[k : k + 3] for k in range(len(merged_cc) - 2)}
      best_3 = 0.0
      for vi in range(lv + 1, rv):
        if vi in used_vs or len(verses[vi].compact) < 12:
          continue
        g3_v = {verses[vi].compact[k : k + 3] for k in range(len(verses[vi].compact) - 2)}
        ov3 = len(g3_c & g3_v) / len(g3_c)
        if ov3 >= 0.30 and ov3 > best_3:
          best_3 = ov3
          best_vi = vi
    if best_vi is not None:
      assign[g_cis[0]] = best_vi


def _is_standalone_avatarika(line: str) -> bool:
  s = line.strip()
  if not s or s.startswith((">", "-", "*", "#")):
    return False
  return bool(_ITALIC_AVATARIKA_RE.match(s))


def _pull_start_for_avatarika(lines: list[str], start_li: int, floor_li: int) -> int:
  """Pull boundary backward over blank lines to include page marker and standalone _avatārikā_."""
  pos = start_li
  while pos - 1 >= floor_li:
    j = pos - 1
    while j >= floor_li and not lines[j].strip():
      j -= 1
    if j < floor_li:
      break
    prev = lines[j].strip()
    if _BRACKET_PREFIX_RE.match(prev) and (not _is_standalone_avatarika(prev)):
      # Only pull bare `[NNN]` or `[NNN] _..._` if it's purely bracket+italic or standalone bracket
      m_b = _BRACKET_PREFIX_RE.match(prev)
      rest = (m_b.group(2) or "").strip() if m_b else ""
      if not rest or _is_standalone_avatarika(rest):
        pos = j
        continue
      break
    if _is_standalone_avatarika(prev) and len(prev) <= 320:
      pos = j
      continue
    break
  return pos


def _split_preamble(lines: list[str], end_li: int) -> tuple[str, str]:
  """Split file-top pre-verse-1 lines into ``(prakarana_avatarika, verse0_lead_in)``.

  Pure prakaraṇa title headers are omitted; short isolated italic transitions stay
  as ``verse0_lead_in`` inside the first verse's commentary block unless preceded by
  substantive prakaraṇa prose or verses.
  """
  if end_li <= 0:
    return "", ""
  kept_paras: list[str] = []
  cur: list[str] = []
  for raw in lines[:end_li]:
    s = raw.rstrip()
    if not s.strip():
      if cur:
        kept_paras.append("\n".join(cur))
        cur = []
      continue
    if _is_opening_title(s) or _NOISE_MARKER_RE.match(s.strip()):
      continue
    cur.append(s)
  if cur:
    kept_paras.append("\n".join(cur))

  if not kept_paras:
    return "", ""

  if len(kept_paras) == 1:
    p = kept_paras[0].strip()
    # A short single transition line directly introducing verse 1 goes with verse 1.
    if (
      not p.startswith(">")
      and "\n" not in p
      and (_is_standalone_avatarika(p) or (len(p) < 160 and p.endswith(("आह ।", "आह।", "प्रस्तूयते ।", "कथ्यते ।", "आरभते ।", "उच्यते ।"))))
    ):
      return "", p
    return p, ""

  # Multiple paragraphs before verse 1: detach trailing short transition (or editorial note before it) into verse 1.
  last = kept_paras[-1].strip()
  if (_is_standalone_avatarika(last) or "\n" not in last) and len(last) <= 220 and last.startswith("_"):
    lead = last
    rem = kept_paras[:-1]
    if len(rem) == 1 and rem[0].startswith("*** "):
      return "", f"{rem[0].strip()}\n\n{lead}"
    return "\n\n".join(rem).strip(), lead
  return "\n\n".join(kept_paras).strip(), ""


@dataclass
class CommentaryAlignment:
  """Extracted commentary slices and diagnostics for one commentary work/chapter."""

  per_verse: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
  per_section_avatarika: dict[str, str] = field(default_factory=dict)
  unassigned_bold_groups: list[tuple[str, int, str]] = field(default_factory=list)


def align_commentary_sections(
  section_files: list[tuple[str, str]],
  verses: list[VerseSpec],
  *,
  global_unmatched_verses: list[VerseSpec] | None = None,
) -> CommentaryAlignment:
  """Align a sequence of commentary prakaraṇa files to canonical ``verses``.

  Preserves 100% of commentary prose and embedded citations by partitioning
  every file strictly at matched lemma boundaries.
  """
  file_lines, cands = _extract_section_cands(section_files)
  assign = _monotonic_dp_assign(cands, verses)
  _reclaim_local_transposed(cands, assign, verses)

  # Optional cross-chapter global match for still-unassigned bold groups (e.g. Viśvarūpa 2.34 <-> 1.361).
  global_assign: dict[int, VerseSpec] = {}
  if global_unmatched_verses:
    groups_all: dict[int, list[int]] = defaultdict(list)
    for ci, cand in enumerate(cands):
      groups_all[cand.group_id].append(ci)
    for gid, g_cis in groups_all.items():
      if any(ci in assign for ci in g_cis) or not any(cands[ci].is_bold for ci in g_cis):
        continue
      merged_cc = "".join(cands[ci].compact for ci in g_cis)
      if len(merged_cc) < 12:
        continue
      g_grams = {merged_cc[k : k + 4] for k in range(max(1, len(merged_cc) - 3))}
      best_gv, best_sc = None, 0.0
      for gv in global_unmatched_verses:
        sc = _score_candidate(merged_cc, g_grams, gv, same_section=False)
        if sc > best_sc and sc >= 0.55:
          best_sc, best_gv = sc, gv
      if best_gv is not None:
        global_assign[g_cis[0]] = best_gv

  # Group per-file matched stanza segments cleanly so multi-line/multi-verse contiguous
  # blockquotes share a single start line owned by their opening verse.
  per_file_anchors: dict[int, list[tuple[int, int, str]]] = defaultdict(list)
  seen_groups: set[int] = set()
  by_group: dict[int, list[int]] = defaultdict(list)
  for ci, cand in enumerate(cands):
    by_group[cand.group_id].append(ci)

  result = CommentaryAlignment()

  for ci, cand in enumerate(cands):
    if cand.group_id in seen_groups:
      continue
    g_cis = by_group[cand.group_id]
    matched_vs: list[VerseSpec] = []
    for g_ci in g_cis:
      if g_ci in assign:
        matched_vs.append(verses[assign[g_ci]])
      elif g_ci in global_assign:
        matched_vs.append(global_assign[g_ci])
    seen_groups.add(cand.group_id)
    if not matched_vs:
      if any(cands[x].is_bold for x in g_cis):
        result.unassigned_bold_groups.append((cand.section_id, cand.line_idx + 1, cand.raw[:80]))
      continue
    owner_v = min(matched_vs, key=lambda x: x.index)
    start_li = cands[g_cis[0]].line_idx
    end_li = cands[g_cis[-1]].line_idx
    per_file_anchors[cand.file_idx].append((start_li, end_li, owner_v.verse_id))

  sec_first_verse: dict[str, VerseSpec] = {}
  for v in verses:
    sec_first_verse.setdefault(v.section_id, v)

  for f_idx, (sec_id, _) in enumerate(section_files):
    lines = file_lines[f_idx]
    anchors = sorted(per_file_anchors.get(f_idx, ()), key=lambda x: x[0])

    # Handle paraphrased opening verse 0 when section[0] wasn't metrically quoted (e.g. Aparārka 1.295).
    if not anchors or (sec_id in sec_first_verse and anchors[0][2] != sec_first_verse[sec_id].verse_id):
      v0 = sec_first_verse.get(sec_id)
      limit = anchors[0][0] if anchors else len(lines)
      if v0 is not None and limit > 0 and all(v0.verse_id != vid for _, _, vid in anchors):
        for li in range(limit - 1, -1, -1):
          s = lines[li].strip()
          if s.startswith(">") and regex.search(r"॥\s*[१२३]\.[०-९]+\s*॥", s):
            cc = _clean_candidate_compact(s)
            c_grams = {cc[k : k + 4] for k in range(max(1, len(cc) - 3))}
            recall = (len(c_grams & v0.grams) / len(v0.grams)) if v0.grams else 0.0
            if recall >= 0.35 or _score_candidate(cc, c_grams, v0, same_section=False) >= 0.25:
              anchors.insert(0, (li, li, v0.verse_id))
              break

    if not anchors:
      av, lead = _split_preamble(lines, len(lines))
      if av:
        result.per_section_avatarika[sec_id] = av
      if lead and sec_id in sec_first_verse:
        result.per_verse[sec_first_verse[sec_id].verse_id].append(lead)
      continue

    seg_starts: list[tuple[int, str]] = []
    floor = 0
    for s_li, _, vid in anchors:
      adj = _pull_start_for_avatarika(lines, s_li, floor)
      seg_starts.append((adj, vid))
      floor = s_li + 1

    first_start = seg_starts[0][0]
    av, lead = _split_preamble(lines, first_start)
    if av:
      result.per_section_avatarika[sec_id] = av

    for idx, (seg_s, vid) in enumerate(seg_starts):
      seg_e = seg_starts[idx + 1][0] if idx + 1 < len(seg_starts) else len(lines)
      cleaned = [ln for ln in _strip_trailing_empty_markers(lines[seg_s:seg_e]) if ln.strip() not in ("> **", "**")]
      chunk = "\n".join(cleaned).strip()
      if idx == 0 and lead:
        chunk = f"{lead}\n\n{chunk}" if chunk else lead
      if chunk:
        result.per_verse[vid].append(chunk)

  return result


def build_sarva_tikah_entry(
  mula_body: str,
  commentary_blocks: list[tuple[str, str]],
  extra_blocks: list[tuple[str, str]] = (),
) -> str:
  """Render unwrapped leaf ``<details>`` blocks for a static ``sarvASh_TIkAH/`` verse file."""
  blocks: list[str] = [f"<details><summary>मूलम्</summary>\n\n{mula_body.strip()}\n</details>"]
  for author_title, body in commentary_blocks:
    clean = body.strip()
    if clean:
      blocks.append(f"<details><summary>{author_title}</summary>\n\n{clean}\n</details>")
  for title, body in extra_blocks:
    clean = body.strip()
    if clean:
      blocks.append(f"<details><summary>{title}</summary>\n\n{clean}\n</details>")
  return "\n\n".join(blocks) + "\n"


def _norm_dev_digits(text: str) -> str:
  return text.translate(str.maketrans("०१२३४५६७८९", "0123456789"))


def _compact_and_grams(text: str) -> tuple[str, frozenset[str]]:
  cleaned = regex.sub(r"॥[^॥]*॥", "", text)
  cleaned = regex.sub(r"\[[^\]]*\]", "", cleaned)
  if len(regex.findall(r"\p{Devanagari}", cleaned)) >= 12:
    # Ignore English gloss notes (or unclosed +++(...)+++ prose) when aligning Sanskrit verses
    cleaned = regex.sub(r"\+\+\+\([^)]*\)\+\+\+", " ", cleaned)
    cleaned = regex.sub(r"[A-Za-z0-9’‘“”'\".,;:!?()/\\+\-=]+", " ", cleaned)
  compact = normalize_for_alignment(cleaned)["compact"]
  grams = frozenset(compact[k : k + 4] for k in range(max(0, len(compact) - 3)))
  return compact, grams


def _strip_all_footnote_defs(text: str) -> tuple[str, dict[str, str]]:
  """Extract ``[^id]: ...`` definitions and remove them from ``text``."""
  parsed = parse_footnotes_markdown(text)
  stripped = _FOOTNOTE_DEF_RE.sub("", text)
  stripped = regex.sub(r"\n{3,}", "\n\n", stripped).strip()
  return stripped, parsed


def _bind_inline_footnotes(text: str, footnote_pools: list[dict[str, str]]) -> str:
  """Inline referenced ``[^id]`` notes using ``footnote_pools`` and drop ``^``."""
  if not text.strip():
    return ""
  clean_body, local_defs = _strip_all_footnote_defs(text)
  merged: dict[str, str] = {}
  for pool in footnote_pools:
    merged.update(pool)
  merged.update(local_defs)
  refs = list(dict.fromkeys(m.group(1).strip() for m in _FOOTNOTE_REF_RE.finditer(clean_body)))
  resolved = {r: merged[r] for r in refs if r in merged}
  if resolved:
    out = inline_footnotes_for_block(clean_body, resolved)
  else:
    out = clean_body
  # Always remove stray ``^`` even if a footnote remained unlinked so <details> stays valid.
  return _FOOTNOTE_REF_RE.sub(r"[\1]", out).strip()


def parse_paired_details_sections(text: str, *, commentary_prefix: str) -> list[dict[str, str]]:
  """Parse paired ``मूलम्`` + ``<commentary_prefix>...`` ``<details>`` entries.

  Recovers malformed sections where a closing ``</details>`` tag is missing or
  where commentary lines leaked inside the preceding ``मूलम्`` block.
  """
  _, body = strip_frontmatter(text)
  tag_re = regex.compile(r"<details>\s*<summary>([^<]+)</summary>", flags=regex.DOTALL)
  matches = list(tag_re.finditer(body))
  if not matches:
    return []

  def _extract_block(start_pos: int, end_limit: int) -> tuple[str, str]:
    chunk = body[start_pos:end_limit]
    close_m = regex.search(r"</details>", chunk)
    if close_m:
      inner = chunk[: close_m.start()].strip()
      trailing = chunk[close_m.end() :].strip()
    else:
      inner = chunk.strip()
      trailing = ""
    return inner, trailing

  entries: list[dict[str, str]] = []
  for idx, m in enumerate(matches):
    summary = m.group(1).strip()
    end_limit = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
    inner, trailing = _extract_block(m.end(), end_limit)

    if summary == "मूलम्":
      mula = inner
      comm_body = ""
      # Recover commentary accidentally merged after verse number inside मूलम् only if not paired cleanly with next block
      nxt_is_comm = idx + 1 < len(matches) and matches[idx + 1].group(1).strip().startswith(commentary_prefix)
      if not nxt_is_comm:
        verse_end_m = regex.search(r"(॥\s*[०-९]+(?:\.[०-९–\-]+)?\s*॥\*\*)\s*\n+(.+)", mula, flags=regex.DOTALL)
        if verse_end_m and len(verse_end_m.group(2).strip()) > 10:
          mula = mula[: verse_end_m.end(1)].strip()
          comm_body = verse_end_m.group(2).strip()
      if trailing and not regex.fullmatch(r"[\s।॥०-९नोचोम्मेन्तर्य्]*", trailing):
        if regex.match(r"^[।॥\s०-९]+$", trailing):
          if comm_body and not comm_body.endswith("॥"):
            comm_body = f"{comm_body} {trailing}".strip()
        else:
          comm_body = f"{comm_body}\n\n{trailing}".strip() if comm_body else trailing
      elif trailing and regex.match(r"^[।॥\s०-९]+$", trailing) and comm_body and not comm_body.endswith("॥"):
        comm_body = f"{comm_body} {trailing}".strip()

      hint_m = regex.search(r"॥\s*[०-९]+\.([०-९]+)", mula)
      entries.append({
        "mula": mula,
        "label": "",
        "body": comm_body,
        "verse_hint": int(_norm_dev_digits(hint_m.group(1))) if hint_m else 0,
      })
    elif summary.startswith(commentary_prefix):
      full_body = inner
      if trailing and not regex.match(r"^[।॥\s०-९नोचोम्मेन्तर्य्]+$", trailing):
        full_body = f"{full_body}\n\n{trailing}".strip()
      if entries and not entries[-1]["body"]:
        entries[-1]["label"] = summary
        entries[-1]["body"] = full_body
      else:
        hint_m = regex.search(r"([०-९]+)(?!.*[०-९])", summary)
        entries.append({
          "mula": "",
          "label": summary,
          "body": full_body,
          "verse_hint": int(_norm_dev_digits(hint_m.group(1))) if hint_m else 0,
        })
  return entries


_INLINE_OCR_FN_RE = regex.compile(r"\(?\s*[(\[०-९0-9)]*\[\^([०-९0-9]+)\]\s+([^\n]*?)\s*(?:\"\)\)|\"\))\s*\*?\*?")
_CHAPTER_BANNER_RE = regex.compile(r"^\*\*\s*(?:अथा?|इति)?[^*]*?(?:ऽध्यायः|समाप्त|प्राप्तिस्थान|चौखम्बा)[^*]*\*\*\s*[।॥०-९]*\s*$")


def _extract_inline_merged_footnotes(text: str) -> tuple[str, dict[str, str]]:
  """Repair OCR-merged ``(१[^n] ... "))`` inline footnotes back to ref + def."""
  extra_defs: dict[str, str] = {}

  def _repl(m: regex.Match) -> str:
    fid = m.group(1).strip()
    note = m.group(2).strip().lstrip('"“ ').rstrip('"” ')
    if note:
      extra_defs[fid] = note
    return f"[^{fid}]"

  return _INLINE_OCR_FN_RE.sub(_repl, text), extra_defs


def _is_kulluka_shloka_end(line: str) -> int | None:
  """Return verse integer if ``line`` looks like a bold root-verse closing pāda."""
  s = line.strip()
  if not regex.search(r"\*\*[)\]\"']*\s*$", s):
    return None
  # Skip bracketed interpolated verses and quoted smṛti citations ending in `इति ॥n॥`
  if regex.match(r"^\*\*\\?[\[\"“]", s) or regex.match(r"^\*\*\s*\*\*", s):
    return None
  if regex.search(r"इति\s*(?:\\?।\\?।|॥)\s*[०-९]+\s*(?:\\?।\\?।|॥)?\s*\*\*\s*$", s):
    return None
  # Must end with bold verse number (not citation like **(म० स्मृ० १-११३)**)
  m = regex.search(r"(?:॥|।\s*\*\*|\\\.\\\.?)\s*([०-९]+)\s*(?:॥|\\?।\\?।|\\?।)?\s*\*\*[)\]\"']*\s*$", s)
  if m is None:
    m = regex.search(r"([०-९]+)\s*(?:॥|\\?।\\?।|\\?।)\s*\*\*[)\]\"']*\s*$", s)
  if m is None:
    return None
  # Reject chapter colophons/headings, author colophons, or inline prose citations
  stripped_bold = regex.sub(r"\*\*", "", s)
  if any(tok in stripped_bold for tok in ("अध्यायः", "समाप्त", "म० स्मृ", "अ० ", "मन्वर्थमुक्तावल", "कुल्लूकभट्ट", "जगतामधीशः")):
    return None
  # Must contain at least 16 Devanagari chars
  if len(regex.findall(r"\p{Devanagari}", stripped_bold)) < 16:
    return None
  return int(_norm_dev_digits(m.group(1)))


_CITE_LEAD_RE = regex.compile(
  r"(?:"
  r"(?:^|\s)(?:तथा|अत\s*एव|यथा|यथोक्तम्)\s*(?:च\s*)?[—:—]\s*$"
  r"|(?:बृहस्पति|यम|याज्ञवल्क्य|विष्णु|नारद|वसिष्ठ|गौतम|आप्?स्तम्ब|शङ्ख|कात्यायन|भविष्य|पुराण|स्मृत्यन्तर|गृह्य|श्रुति|पैठीनसि|देवल|काठक|बौधायन|व्यासा?|संवर्त|पराशर|उशन[साः]|स्मृतम्|प्रोक्तम्|व्यक्तीकृत|अप्युक्तम्|उक्तं\s*च|पराशरोक्तो\s*विशेष)[^\n]*[—:—]\s*$"
  r")"
)


def _looks_like_avatarika_para(para: str) -> bool:
  """True if ``para`` is a pre-verse avatārikā lead-in ending with dash/आह/वदति."""
  s = regex.sub(r"\s+", " ", para).strip()
  if not s:
    return False
  if regex.search(r"[—\-]\s*$", s) and len(s) < 260:
    return True
  if regex.search(r"(?:इत्यत\s*आह|अपेक्षायामाह|इत्यतआह|दृष्टान्तमाह|प्रयोजनमाह|आह)\s*[।:—\-]*\s*$", s) and len(s) < 200:
    return True
  return False


def extract_bold_shloka_sections(text: str) -> tuple[str, list[dict]]:
  """Parse a bold-śloka commentary edition (e.g. Kullūka) into structured verses.

  Returns ``(opening_intro, entries)``, where each entry contains ``mula``,
  ``verse_hint``, ``avatarika``, and ``body`` with all ``[^n]`` footnotes
  preserved locally inside each block as ``[n]``.
  """
  _, body = strip_frontmatter(text)
  repaired, inline_defs = _extract_inline_merged_footnotes(body)
  clean_text, parsed_defs = _strip_all_footnote_defs(repaired)
  all_defs = {**parsed_defs, **inline_defs}

  # Strip chapter colophon & appendix after द्वादशोऽध्यायः समाप्तः if present
  lines = clean_text.splitlines()
  filtered_lines: list[str] = []
  for ln in lines:
    if "परिशिष्टम्" in ln and "अविद्यमानानां" in clean_text[clean_text.find(ln) : clean_text.find(ln) + 200]:
      break
    filtered_lines.append(ln)

  n = len(filtered_lines)
  # Locate bold śloka blocks: each ends at a line detected by _is_kulluka_shloka_end
  shloka_spans: list[tuple[int, int, int]] = []
  in_bracket = False
  in_backslash_ksepaka = False
  i = 0
  while i < n:
    s = filtered_lines[i].strip()
    if _CHAPTER_BANNER_RE.match(s) or s.startswith("<MISSING_FIG"):
      i += 1
      continue
    if in_bracket:
      if regex.search(r"\\?\]", s):
        in_bracket = False
      i += 1
      continue
    if in_backslash_ksepaka:
      if s and not s.startswith("**") and not regex.search(r"॥\s*[०-९]+\s*(?:॥|\\?।\\?।)?\*\*", s):
        in_backslash_ksepaka = False
      else:
        if regex.search(r"\\?\]", s):
          in_backslash_ksepaka = False
        i += 1
        continue
    if regex.match(r"^(?:\*\*)?\s*\\?\[", s) and not regex.search(r"\\?\]\s*\*?\*?\s*$", s):
      in_bracket = True
      i += 1
      continue
    if regex.match(r"^\*\*\s*\\\p{Devanagari}", s):
      in_backslash_ksepaka = True
      i += 1
      continue
    v_hint = _is_kulluka_shloka_end(filtered_lines[i])
    if v_hint is not None:
      start = i
      # Look backwards across blank lines / immediately adjacent bold pāda line (1-2 prior lines)
      back = i - 1
      while back >= 0 and not filtered_lines[back].strip():
        back -= 1
      if back >= 0:
        prev = filtered_lines[back].strip()
        is_prev_bold_pada = (
          (prev.startswith("**") and prev.endswith("**") and not _CHAPTER_BANNER_RE.match(prev)
           and not regex.search(r"॥\s*[०-९]+\s*॥", prev))
          or (prev.startswith("**") and "॥" not in prev and len(regex.findall(r"\p{Devanagari}", prev)) >= 14 and not filtered_lines[i].strip().startswith("**"))
          or (prev.endswith("**") and regex.search(r"\*\*[^*]{10,}$", prev) and "॥" not in prev and len(regex.findall(r"\p{Devanagari}", prev)) >= 14)
        )
        # Also allow unbolded opening line directly above a bold second-line verse
        if not is_prev_bold_pada and not filtered_lines[i].strip().startswith("**") and len(regex.findall(r"\p{Devanagari}", prev)) >= 14 and "॥" not in prev and not prev.endswith("—"):
          is_prev_bold_pada = True
        if is_prev_bold_pada and (not shloka_spans or back > shloka_spans[-1][1]):
          start = back
          # Check one more blank+bold line in case of 3-line verse (e.g. Kulluka 11.1-2)
          back2 = back - 1
          while back2 >= 0 and not filtered_lines[back2].strip():
            back2 -= 1
          if back2 >= 0:
            prev2 = filtered_lines[back2].strip()
            if prev2.startswith("**") and not _CHAPTER_BANNER_RE.match(prev2) and "॥" not in prev2 and (not shloka_spans or back2 > shloka_spans[-1][1]):
              start = back2
      # Skip bracketed kṣepaka ślokas whose opening bracket sits on ``start``, or citations preceded by a Smṛti/Purāṇa speaker line
      span_text = "\n".join(filtered_lines[start : i + 1]).strip()
      if regex.match(r"^\s*(?:\*\*)?\s*\\?[\[\"“]", span_text):
        i += 1
        continue
      prev_nb = start - 1
      while prev_nb >= 0 and not filtered_lines[prev_nb].strip():
        prev_nb -= 1
      if prev_nb >= 0 and _CITE_LEAD_RE.search(filtered_lines[prev_nb].strip()):
        i += 1
        continue
      shloka_spans.append((start, i, v_hint))
    i += 1

  if not shloka_spans:
    return "", []

  def _join_clean(slice_lines: list[str]) -> str:
    kept = [ln for ln in slice_lines if not _CHAPTER_BANNER_RE.match(ln.strip()) and not ln.strip().startswith("<MISSING_FIG")]
    # Unwrap hard line breaks inside prose? Keep blank-line paragraphs clean and strip trailing artifact noise.
    raw = "\n".join(kept).strip()
    return _bind_inline_footnotes(raw, [all_defs])

  opening_intro = ""
  # Check if everything before shloka_spans[0] is mangala/essay OR check mangalas between śloka 1 and 2 in Ch 1!
  pre_first = _join_clean(filtered_lines[: shloka_spans[0][0]])
  if pre_first:
    opening_intro = pre_first

  entries: list[dict] = []
  for idx, (s_start, s_end, v_hint) in enumerate(shloka_spans):
    comm_end = shloka_spans[idx + 1][0] if idx + 1 < len(shloka_spans) else n
    mula_raw = "\n".join(ln.strip() for ln in filtered_lines[s_start : s_end + 1] if ln.strip())
    mula_clean = regex.sub(r"\*\*", "", mula_raw).strip()
    mula_text = _bind_inline_footnotes(mula_clean, [all_defs])

    comm_lines = list(filtered_lines[s_end + 1 : comm_end])
    # Extract trailing pre-verse avatārikā belonging to idx+1 if it ends before the next śloka
    next_av = ""
    if idx + 1 < len(shloka_spans):
      # Split into paragraphs
      comm_raw = "\n".join(ln for ln in comm_lines if not _CHAPTER_BANNER_RE.match(ln.strip()) and not ln.strip().startswith("<MISSING_FIG")).strip()
      paras = [p.strip() for p in regex.split(r"\n\s*\n", comm_raw) if p.strip()]
      if paras and _looks_like_avatarika_para(paras[-1]) and len(paras) >= 2:
        # Ensure previous paragraph already closed its verse commentary
        next_av = paras.pop()
      comm_body = _bind_inline_footnotes("\n\n".join(paras), [all_defs])
    else:
      comm_body = _join_clean(comm_lines)

    # Check previous entry's extracted trailing avatārikā
    entries.append({
      "mula": mula_text,
      "verse_hint": v_hint,
      "avatarika": "",
      "next_avatarika": _bind_inline_footnotes(next_av, [all_defs]) if next_av else "",
      "body": comm_body,
    })

  for idx in range(len(entries) - 1):
    if entries[idx]["next_avatarika"]:
      entries[idx + 1]["avatarika"] = entries[idx]["next_avatarika"]
    del entries[idx]["next_avatarika"]
  if entries and "next_avatarika" in entries[-1]:
    del entries[-1]["next_avatarika"]

  return opening_intro, entries


def align_entry_stream_to_verses(
  entries: list[dict],
  verses: list[VerseSpec],
  *,
  min_score: float = 0.22,
) -> dict[str, list[dict]]:
  """Monotonically align structured commentary entries to ``verses`` via DP."""
  if not entries or not verses:
    return {}

  cand_info: list[tuple[str, frozenset[str], int]] = []
  for e in entries:
    comp, grams = _compact_and_grams(e.get("mula") or e.get("body", "")[:250])
    cand_info.append((comp, grams, int(e.get("verse_hint") or 0)))

  def _vnum(v: VerseSpec) -> int:
    m = regex.search(r"(?:\.|^)(\d+)", v.verse_id)
    return int(m.group(1)) if m else 0

  v_nums = [_vnum(v) for v in verses]
  M, N = len(entries), len(verses)

  # Sparse top candidates per entry + DP monotonic assignment (allowing entry drops or merges)
  skip_verse_cost = 0.02
  drop_entry_cost = -0.30
  dp = [[-1e9] * (N + 1) for _ in range(M + 1)]
  bp: list[list[tuple[int, int] | None]] = [[None] * (N + 1) for _ in range(M + 1)]
  for j in range(N + 1):
    dp[0][j] = 0.0

  def _sim(i: int, j: int) -> float:
    comp, grams, hint = cand_info[i]
    v = verses[j]
    if grams and v.grams:
      rec = len(grams & v.grams) / max(1, len(v.grams))
      jacc = len(grams & v.grams) / max(1, len(grams | v.grams))
      txt_score = 0.65 * jacc + 0.35 * rec
    else:
      txt_score = 0.0
    if hint and v_nums[j]:
      diff = abs(hint - v_nums[j])
      if diff == 0:
        txt_score += 0.25
      elif diff <= 2:
        txt_score += 0.12
      elif diff <= 15:
        txt_score += 0.03
    return txt_score

  for i in range(1, M + 1):
    # Drop entry i-1
    for j in range(N + 1):
      best_val = dp[i - 1][j] + drop_entry_cost
      best_prev: tuple[int, int] | None = (i - 1, j)
      if j > 0:
        # Advance verse without consuming entry
        if dp[i][j - 1] - skip_verse_cost > best_val:
          best_val = dp[i][j - 1] - skip_verse_cost
          best_prev = (i, j - 1)
        # Pair entry i-1 with verse j-1
        s = _sim(i - 1, j - 1)
        if s >= min_score:
          cand_v = dp[i - 1][j - 1] + s
          if cand_v > best_val:
            best_val = cand_v
            best_prev = (i - 1, j - 1)
      dp[i][j] = best_val
      bp[i][j] = best_prev

  end_j = max(range(N + 1), key=lambda j: dp[M][j])
  assigned: dict[str, list[dict]] = defaultdict(list)
  i, j = M, end_j
  while i > 0 and j >= 0:
    prev = bp[i][j]
    if prev is None:
      break
    pi, pj = prev
    if pi == i - 1 and pj == j - 1:
      assigned[verses[j - 1].verse_id].append(entries[i - 1])
    i, j = pi, pj

  for vid in assigned:
    assigned[vid].reverse()
  return {v.verse_id: assigned[v.verse_id] for v in verses if v.verse_id in assigned}


def split_leading_and_trailing_italic_avatarika(
  body: str,
  extra_footnotes: dict[str, str] | None = None,
) -> tuple[str, str, str]:
  """Split leading and trailing ``_..._`` avatārikās out of a commentary block.

  Returns ``(leading_avatarika, remaining_body, trailing_avatarika)``. Any
  footnotes referenced inside an extracted avatārikā slice are bound inline
  inside that slice while footnotes exclusive to moved slices are removed from
  ``remaining_body``.
  """
  if not body.strip():
    return "", "", ""
  clean_no_fn, local_defs = _strip_all_footnote_defs(body)
  pool = {**(extra_footnotes or {}), **local_defs}
  lines = clean_no_fn.splitlines()

  # 1. Leading _..._ lines at start of block
  lead_idx = 0
  while lead_idx < len(lines) and not lines[lead_idx].strip():
    lead_idx += 1
  lead_lines: list[str] = []
  while lead_idx < len(lines) and _ITALIC_AVATARIKA_RE.match(lines[lead_idx].strip()):
    lead_lines.append(lines[lead_idx].strip())
    lead_idx += 1
    while lead_idx < len(lines) and not lines[lead_idx].strip():
      lead_idx += 1

  # 2. Trailing _..._ block at end of block (typically immediately after ॥ ch.v ॥)
  end_idx = len(lines) - 1
  while end_idx >= lead_idx and not lines[end_idx].strip():
    end_idx -= 1
  trail_lines: list[str] = []
  # Handle trailing italicized sentence (plus optional trailing quotation/fn on same tail after ॥ ch.v ॥)
  if end_idx >= lead_idx and _ITALIC_AVATARIKA_RE.match(lines[end_idx].strip()):
    trail_lines.insert(0, lines[end_idx].strip())
    end_idx -= 1
    while end_idx >= lead_idx and not lines[end_idx].strip():
      end_idx -= 1
    while end_idx >= lead_idx and _ITALIC_AVATARIKA_RE.match(lines[end_idx].strip()):
      trail_lines.insert(0, lines[end_idx].strip())
      end_idx -= 1
      while end_idx >= lead_idx and not lines[end_idx].strip():
        end_idx -= 1
  elif end_idx >= lead_idx:
    # Special case: trailing paragraph right after ॥ ch.v ॥ that starts with _..._ and ends with a quote + fn (e.g. 8.147)
    last_line = lines[end_idx].strip()
    if last_line.startswith("_") and "_" in last_line[1:] and regex.search(r"॥\s*[०-९]+\.[०-९]+\s*॥", "\n".join(lines[lead_idx:end_idx])):
      trail_lines.append(last_line)
      end_idx -= 1

  core_body_raw = "\n".join(lines[lead_idx : end_idx + 1]).strip()
  lead_text = "\n\n".join(lead_lines)
  trail_text = "\n\n".join(trail_lines)
  moved_refs = {m.group(1).strip() for m in _FOOTNOTE_REF_RE.finditer(lead_text + "\n" + trail_text)}
  core_refs = list(dict.fromkeys(m.group(1).strip() for m in _FOOTNOTE_REF_RE.finditer(core_body_raw)))
  # Preserve footnotes referenced in core OR any original local def not exclusive to moved slices
  keep_defs = list(core_refs)
  for fid in local_defs:
    if fid not in moved_refs and fid not in keep_defs:
      keep_defs.append(fid)
  for ref in reversed(keep_defs):
    if ref in local_defs:
      note_lines = local_defs[ref].splitlines()
      core_body_raw += f"\n\n\n[^{ref}]:\n     " + "\n     ".join(note_lines)

  lead_av = _bind_inline_footnotes(lead_text, [pool]) if lead_lines else ""
  trail_av = _bind_inline_footnotes(trail_text, [pool]) if trail_lines else ""
  return lead_av, core_body_raw.strip(), trail_av
