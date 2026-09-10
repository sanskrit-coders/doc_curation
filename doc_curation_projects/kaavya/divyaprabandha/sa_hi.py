#!/usr/bin/env python3
"""Structure raw sa_hi Bhagavad-vishayam files into verse-wise <details> blocks.

Source: OCR of the Hindi/Sanskrit Bhagavad-vishayam (36k Idu) books, e.g.
  .../12k_vAdikesari-jIyar__36k_IDu.../sa_hi/01.md
which mixes Sanskrit commentary (avatArikA, mUlam, TIkA) with Hindi
arthas (bhAvArtha + verse renderings).

Output per verse (verse number = local number from the ``||n||`` ending,
NOT the global OCR ``###`` running number)::

  ## <set>          (dashaka/set separator; each set restarts at 1)
  ### <verse>
  <details><summary>avatArikA - <verse></summary> ... </details>
  <details open><summary>mUlam - <verse></summary> ... </details>
  <details><summary>TIkA - <verse></summary> ... </details>
  <details><summary>hindI - <verse></summary> ... </details>

Hindi vs Sanskrit separation: paragraphs are scored -- standalone
``hai/mem/haim``-type Hindi function words mark Hindi, ``~N``
(avagraha) and ``iti/ity/cet``-type words mark Sanskrit. Explicit
markers (``bhAvArtha``, ``+``/``^``-led verse renderings, ``mUlam``,
``avatArikA``) always win over the score.

Page numbers (bare ``44``, ``-68`` ...) become ``[[P44]]`` inline at the
break point. Footnotes (``1. ...``) become ``[^set_verse_fn]`` with the
definition placed right after the referencing paragraph.

Usage::

  python3 sa_hi.py RAW_01.md OUT_01.md
"""

import argparse
import re
import sys
from pathlib import Path

DEVA = "०१२३४५६७८९"


def deva_to_arab(s):
  out = ""
  for ch in s:
    if ch in DEVA:
      out += str(DEVA.index(ch))
    elif ch.isdigit():
      out += ch
  return out or "0"


def arab_to_deva(n):
  return "".join(DEVA[int(d)] for d in str(n))


# ---------------------------------------------------------------------------
# Language scoring: Hindi (hai/mem/haim ...) vs Sanskrit (~N/iti/ity ...).
# Only trailing Devanagari boundaries are required so that sandhi-glued
# Sanskrit (sarpoyam-iti) still counts while words like itihAsa do not.
# ---------------------------------------------------------------------------

# NOTE: ये/था/तो/यदि/हम are deliberately absent -- they collide with
# Sanskrit विषये, तथा/यथा/स्वस्था, ततो, यदि (yadi = "if") and
# visarga-dropped अहम्. पर is absent (Sanskrit पर); तथा likewise.
_HINDI_WORDS = (
  "है|हैं|थी|थे|होगा|होगी|में|ने|को|से|द्वारा|लिये|"
  "गया|गयी|गये|हुआ|हुई|हुए|रहा|रही|रहे|किया|किये|कहा|कहते|"
  "बताया|बताते|नहीं|कैसे|क्या|यह|वह|वे|इस|उस|इन|उन|जिन|"
  "अपनी|अपने|तुम|आप|लोग|वाला|वाली|वाले|और|क्योंकि|लेकिन|"
  "जब|तब|यहाँ|वहाँ|होता|होती|होते|करना|करें|करो|लो|भी|ही|जो"
)
_SANSKRIT_WORDS = (
  "इति|इत्य|इत्याह|चेत्|ननु|अत्र|तत्र|यत्र|तदा|यथा|कथम्|किम्|किमर्थम्|"
  "कुतः|तर्हि|यद्वा|अथवा|एवम्|एव|तद्|एतद्|अस्य|तस्य|एतस्य|भवति|"
  "भवेत्|उच्यते|आह|प्राह|उवाच|अवोचत्|अर्थः|इत्यर्थः|अतः|खलु|हि|"
  "तु|अपि|अस्ति|नास्ति"
)
# Sandhi-glued "-ित्य-" (इत्युक्तम्, इत्याह, ...) has no independent इ;
# it counts only mid-word before more Devanagari (नित्यता-style Hindi
# lookalikes are rare here).
_SANSKRIT_GLUED_RE = re.compile(r"ित्य(?=[\u0900-\u097F])")
# A lone weak hit (को/के/से ...) proves nothing; singletons only count
# when they are high-precision markers.
_STRONG_HINDI = {"है", "हैं", "में", "नहीं", "क्या"}
_HINDI_RE = re.compile(r"(?:%s)(?![\u0900-\u097F])" % _HINDI_WORDS)
_SANSKRIT_RE = re.compile(r"(?:%s)(?![\u0900-\u097F])" % _SANSKRIT_WORDS)


def score_paragraph(text):
  """Return (hindi_hits, sanskrit_hits) for a paragraph."""
  h = len(_HINDI_RE.findall(text))
  s = 2 * text.count("ऽ") + len(_SANSKRIT_RE.findall(text))
  return h, s


def classify_paragraph(text):
  """Classify a paragraph as hindi / sanskrit / unknown.

  Standalone hai/mem/haim-type words mark Hindi; ~N (avagraha) and
  iti/ity/cet-type words mark Sanskrit. Hyphenated line-breaks are
  rejoined for scoring only (so "त- \\n था" cannot fake a hit). Ties
  with substance go to Hindi (Sanskrit TIkA almost never accumulates
  Hindi function words, while Hindi prose often embeds Sanskrit
  terms); lone weak hits (को/के/से ...) stay unknown.
  """
  joined = re.sub(r"-\s*\n\s*", "", text)
  h_list = _HINDI_RE.findall(joined)
  h = len(h_list)
  s = 2 * joined.count("ऽ") + len(_SANSKRIT_RE.findall(joined)) + len(
    _SANSKRIT_GLUED_RE.findall(joined))
  if h >= 2 and h >= s:
    return "hindi"
  if s > h:
    return "sanskrit"
  if h == 1 and s == 0 and h_list[0] in _STRONG_HINDI:
    return "hindi"
  if s >= 1:
    return "sanskrit"
  return "unknown"


# ---------------------------------------------------------------------------
# Structural patterns.
# ---------------------------------------------------------------------------

VERSE_END_RE = re.compile(
  r"(?:॥|\|{2}|\.\.|।{2})\s*([०-९0-9ई]*)\s*"
  r"(?:॥|\|{2}|\.\.|।{2}|\|(?![|]))")
# Dangling opener ("...मच्छरीरम् || " with the closer lost in OCR).
DANGLING_END_RE = re.compile(r"(?:॥|\|{2})\s*$")
# Mangled OCR verse endings ("F1:", "§") cut the mUlam like real ones.
MANGLED_END_RE = re.compile(r"(?:F1?:|§)\s*[0-9०-९]*")


def verse_end_num(m):
  """int number from a VERSE_END_RE match, or None. ई = ९ (OCR)."""
  g = m.group(1)
  if not g:
    return None
  if set(g) == {"ई"}:
    return 9
  try:
    return int(deva_to_arab(g))
  except ValueError:
    return None
MULAM_START_RE = re.compile(
  r"^\*?\*?\s*(?:मूलम्|मलम्)(?:\s*[-–—:]+\s*|\s+)")
AVAT_MARK_RE = re.compile(
  r"अवं?तारिका\*?\*?\s*[-–—:]+"
  r"|(?:^|\n)\*?\*?अवं?तारिका\*?\*?\s+(?=[\u0900-\u097F])")
# Mid-line mUlam markers always start new lines: all observed mid-line
# occurrences are genuine verse mUlams (no bare commentary mentions use
# the "mUlam -" form). Mid-line avatArikA markers only split after a
# daNDa, so "X-दशक - अवतारिका-" titles stay intact.
_MIDLINE_MULAM_RE = re.compile(
  r"\s*(?=\*?\*?(?:मूलम्|मलम्)\s*[-–—:])")
_MIDLINE_AVAT_RE = re.compile(
  r"(?<=[।.!?])\s*(?=\*?\*?अवतारिका\s*[-–—:])")
DASHAKA_TITLE_RE = re.compile(r"^[^\n]*दशक\s*-\s*अवतारिका")
# Flexible ordinals (long/short/fused): prathamA, tRtIya, prathama-gAthA ...
_ORD = (r"(?:प्रथम|द्वितीय|तृतीय|चतुर्थ|पञ्चम|षष्ठ|सप्तम|अष्टम|नवम|"
        r"दशम|एकादश)[ाी]?")
GATHA_LABEL_ONLY_RE = re.compile(
  r"^[\s+↑f|i:;.\-–—0-9०-९()\[\]]*" + _ORD +
  r"(?:\s+या\s+" + _ORD + r")?"
  r"\s+गा(?:था|या)[\s+↑f|i:;.\-–—]*$")
GATHA_PREFIX_RE = re.compile(
  r"^(?:\*\*?)?\s*" + _ORD + r"\s*गाथा\s*[-–—:]+\s*")
GATHA_FUSED_TAIL_RE = re.compile(
  r"\s*(?:और)?" + _ORD + r"\s*गाथा\s*$")
GATHA_BRACKET_RE = re.compile(r"\[\s*प्रथमा गाथा\s*\]")
EXTRA_START_RES = [
  re.compile(p) for p in (
    r"द्रविडोपनिषत्", r"सङ्गत", r"रत्नावली", r"सारश्लोक", r"सारार्थसंग्रह",
    r"उपो?द्धात", r"दशकार्थप्रदर्शन", r"इति श्री .*(?:व्याख्याने|समाप्तम्)",
    r"सारस्सारस्वतानां",
  )]
FOOT_DEF_RE = re.compile(r"^\s*([०-९0-9]+)[.\-)]\s*(.*\S)\s*$")
FOOT_REF_KEYWORDS_RE = re.compile(
  r"(स०|रा०|वि०|तै०|गी०|तिरु|मुं०|छा०|बृ०|श्वे०|कठ०|पाठ|"
  r"मूलानुसारी|आकर|इति)")
GUJ = "૦૧૨૩૪૫૬૭૮૯"
_JUNK_LINES = {
  "►", "1", "4", "+", "|", ".", ":", "-", "–", "—", "_", "*", "**", "***",
  "{", "}", "•", "·", "S", "T", "A", "f", ",", "..", "......",
  "...........................................................",
  "..........................................................",
  "0", "2", "3", "5", "6", "7", "8", "9",
}
_DROP_LINE_RES = [
  re.compile(r"^###\s+[०-९0-9]+\s*$"),  # global OCR running number
  re.compile(r"^\.+$"),                   # dotted separator
]
_RUNNING_HEAD_RE = re.compile(r"^सहस्रगीत")
_GARBAGE_RE = re.compile(r"[0-9OCESUNGOBh]{10,}")


def is_extra_start(text):
  return any(r.search(text) for r in EXTRA_START_RES)


def parse_page_number(s):
  """Bare page-number line -> arabic int, else None."""
  t = s.replace(" ", "").replace(".", "").replace("-", "").replace("+", "")
  tmp = ""
  for ch in t:
    if ch in DEVA:
      tmp += str(DEVA.index(ch))
    elif ch in GUJ:
      tmp += str(GUJ.index(ch))
    elif ch.isdigit():
      tmp += ch
    else:
      return None
  if tmp and len(tmp) <= 3 and len(s) <= 6:
    try:
      pn = int(tmp)
    except ValueError:
      return None
    if 30 <= pn <= 300:
      return pn
  return None


# ---------------------------------------------------------------------------
# Line cleanup + paragraph assembly.
# ---------------------------------------------------------------------------

def clean_lines(raw_text):
  """Drop headings/junk/running-heads; page numbers -> [[Pnn]] lines."""
  expanded = []
  for ln in raw_text.split("\n"):
    for piece in _MIDLINE_MULAM_RE.split(ln):
      if DASHAKA_TITLE_RE.match(piece.strip()):
        expanded.append(piece)
      else:
        expanded.extend(_MIDLINE_AVAT_RE.split(piece))
  out = []
  for ln in expanded:
    s = ln.strip()
    if not s:
      out.append("")
      continue
    if s in _JUNK_LINES:
      continue
    if any(r.match(s) for r in _DROP_LINE_RES):
      continue
    if _RUNNING_HEAD_RE.match(s):
      continue
    if _GARBAGE_RE.fullmatch(s):
      continue
    if GATHA_BRACKET_RE.search(s):
      s = GATHA_BRACKET_RE.sub("", s).strip()
      if not s:
        continue
    if GATHA_LABEL_ONLY_RE.match(s):
      continue
    pn = parse_page_number(s)
    if pn is not None:
      out.append("[[P%d]]" % pn)
      continue
    # Leading folio digits glued to content ("1 महासागर...", "१५ 1. देह").
    s = re.sub(r"^[0-9०-९]{1,3}\s+(?=[क-ह+↑f])", "", s).strip()
    if not s:
      continue
    # Glued trailing gAthA label ("... औरप्रथमा गाथा") -> strip the label.
    s2 = GATHA_FUSED_TAIL_RE.sub("", s).strip()
    if not s2:
      continue
    out.append(s2)
  return out


def is_starter_line(s):
  if not s or s == "[[P0]]":
    return False
  if s.startswith("[[P"):
    return False
  if AVAT_MARK_RE.search(s) and not DASHAKA_TITLE_RE.match(s):
    return True
  if MULAM_START_RE.match(s):
    return True
  if s.startswith("भावार्थ") or re.match(r"^\*?\*?भावार्थ", s):
    return True
  if re.match(r"^[+↑f]\s+\S", s):
    return True
  if DASHAKA_TITLE_RE.match(s):
    return True
  if FOOT_DEF_RE.match(s):
    return True
  if is_extra_start(s):
    return True
  return False


def ends_with_verse(s):
  s = s.strip()
  m = None
  for m in VERSE_END_RE.finditer(s):
    pass
  if m is not None and m.end() >= len(s) - 2:
    return True
  return bool(DANGLING_END_RE.search(s))


def assemble_paragraphs(lines):
  """Join OCR lines into paragraphs.

  A new paragraph starts at structural markers and after verse endings;
  ``[[Pnn]]``-only lines terminate the current paragraph (page break at a
  paragraph boundary) while staying inline via the marker text. Footnote
  definitions absorb their continuation lines (anecdotes often run on).
  """
  paras = []
  buf = []
  pending_page = None

  def buf_is_def():
    return bool(buf) and bool(FOOT_DEF_RE.match(buf[0].strip()))

  def flush():
    if buf:
      paras.append("\n".join(buf).strip())
      buf.clear()

  for ln in lines:
    s = ln.strip()
    if not s:
      if pending_page:
        buf.append(pending_page)
        pending_page = None
      flush()
      continue
    if s.startswith("[[P") and re.fullmatch(r"\[\[P\d+\]\]", s):
      if buf:
        buf[-1] = buf[-1] + " " + s
        flush()
      else:
        pending_page = (pending_page + " " + s).strip() if pending_page \
          else s
      continue
    if pending_page:
      s = pending_page + " " + s
      pending_page = None
    if is_starter_line(s):
      flush()
      buf.append(s)
      if ends_with_verse(s):
        # A verse ending never continues a footnote: keep it separate.
        flush()
      # Footnote-def lines stay open: following plain lines are their
      # continuations (glued until the next starter/blank/verse-end).
      continue
    if buf and buf_is_def():
      if ends_with_verse(s):
        # A verse ending never continues a footnote: flush the def first.
        flush()
        buf.append(s)
        flush()
        continue
      if is_hindi_para(s):
        # Hindi content (bhAvArtha/intro) after a footnote starts fresh.
        flush()
    buf.append(s)
    if ends_with_verse(s) and not buf_is_def():
      flush()
  if pending_page:
    buf.append(pending_page)
  flush()
  flush()
  # Split mid-paragraph tails after a verse ending (mUlam tail = TIkA start,
  # Hindi rendering tail = label/extra) when the head is a marked block.
  fixed = []
  for p in paras:
    ms = list(VERSE_END_RE.finditer(p))
    head_marked = bool(
      MULAM_START_RE.match(p) or p.startswith("भावार्थ")
      or re.match(r"^[+↑f]\s+\S", p))
    if ms and head_marked:
      m = ms[0]
      head, tail = p[:m.end()].strip(), p[m.end():].strip()
      fixed.append(head)
      if tail and not GATHA_LABEL_ONLY_RE.match(tail):
        fixed.append(tail)
    else:
      fixed.append(p)
  return [p for p in fixed if p]


# ---------------------------------------------------------------------------
# Footnotes, scoped per verse/intro/extras block.
# ---------------------------------------------------------------------------

def split_multi_defs(lines):
  expanded = []
  for ln in lines:
    parts = re.split(r"(?=(?:^|\s)[०-९0-9]+[.\-]\s)", ln)
    if len(parts) > 1 and all(
        re.match(r"^\s*[०-९0-9]+[.\-]", p) for p in parts if p.strip()):
      expanded.extend([p for p in parts if p.strip()])
    else:
      parts2 = re.split(r"(?<=\S)\s+(?=[०-९0-9]+\s*[-–]\s)", ln)
      expanded.extend([p for p in (parts2 if len(parts2) > 1 else [ln])
                       if p.strip()])
  return expanded


def insert_footnote_refs(text, defs, prefix):
  defined = {k for k in defs if k.isdigit() and 1 <= int(k) <= 15}
  spans = [m.span() for m in VERSE_END_RE.finditer(text)]

  def repl(mo):
    if any(a <= mo.start(2) < b for a, b in spans):
      return mo.group(0)  # verse numbers are never footnote refs
    pre, dg, post = mo.group(1), mo.group(2), mo.group(3)
    numa = deva_to_arab(dg)
    if numa in defined:
      return "%s[^%s_%s]%s" % (pre, prefix, numa, post)
    return mo.group(0)

  return re.sub(
    r"([^\d०-९\[^/।॥\n])\s*([०-९0-9])(\s*[।,;)\]\s'\"’])",
    repl, text)


def render_with_footnotes(paras, prefix):
  """Attach footnote refs+defs; defs sit next to the referencing para."""
  cleaned, raw_defs = collect_verse_defs([paras])
  paras = cleaned[0]
  fid_defs = {"%s_%s" % (prefix, k): v for k, v in raw_defs.items()}
  out = []
  emitted = set()
  for p in paras:
    p = insert_footnote_refs(p, raw_defs, prefix)
    out.append(p)
    for r in re.findall(r"\[\^([^\]]+)\]", p):
      if r in fid_defs and r not in emitted:
        out.append("[^%s]: %s" % (r, fid_defs[r]))
        emitted.add(r)
  referenced = set(re.findall(r"\[\^([^\]]+)\]", "\n".join(out)))
  leftovers = ["[^%s]: %s" % (f, d) for f, d in fid_defs.items()
               if f not in referenced]
  if leftovers:
    out.append("\n\n".join(leftovers))
  return "\n\n".join(out).strip()


# ---------------------------------------------------------------------------
# Verse parsing inside one dashaka chunk.
# ---------------------------------------------------------------------------

class Verse(object):
  def __init__(self):
    self.local = None
    self.avat = []
    self.pre_hindi = []
    self.mulam = ""
    self.tika = []
    self.hindi = []
    self._comm_raw = []    # ordered commentary paras, classified later
    self._anchor_idx = -1
    self._stray_defs = []  # footnote-def paras consumed during recovery
    self._mangled = False  # mUlam end mangled (F1:/§/empty): complete text


def split_mulam_para(p):
  """(head, tail, local_number_or_None, mangled_end_bool).

  head runs up to the first proper ``||n||`` ending (``|| ई ||`` reads
  as 9, empty ``|| ||`` stays numberless), or up to a mangled OCR
  ending (``F1:``, ``§``). tail is the rest (usually TIkA start).
  """
  q = MULAM_START_RE.sub("", p).strip()
  ms = list(VERSE_END_RE.finditer(q))
  mangled = None
  if ms:
    m = ms[0]
  else:
    m = None
  mm = MANGLED_END_RE.search(q)
  if mm and (m is None or mm.start() < m.start()):
    head = q[:mm.end()].strip()
    tail = re.sub(r"^[|lI1:;.\-–—\s]+", "", q[mm.end():]).strip()
    return head, tail, None, True
  if not ms:
    dm = DANGLING_END_RE.search(q)
    if dm:
      return q[:dm.end()].strip(), q[dm.end():].strip(), None, False
    return q, "", None, False
  m = ms[0]
  num = verse_end_num(m)
  head = q[:m.end()].strip()
  tail = q[m.end():].strip()
  if m.group(1) == "ई":
    head += " " + MUDRITA_I_NOTE
  return head, tail, num, False


def find_avat_idx(paras, start, end):
  for i in range(start, end):
    if AVAT_MARK_RE.search(paras[i]) \
        and not DASHAKA_TITLE_RE.match(paras[i]):
      return i
  return None


def strip_avat_mark(p):
  p = re.sub(r"^[।|·:\s]+", "", p).strip()
  p = GATHA_PREFIX_RE.sub("", p).strip()
  p = re.sub(r"^\*?\*?अवं?तारिका\*?\*?\s*[-–—:]+\s*", "", p).strip()
  p = re.sub(r"^\*?\*?अवं?तारिका\*?\*?\s+(?=[\u0900-\u097F])", "", p).strip()
  return p


def is_hindi_para(q):
  if q.startswith("भावार्थ") or re.match(r"^\*?\*?भावार्थ", q):
    return True
  if re.match(r"^[+↑f]\s+\S", q):
    return True
  return classify_paragraph(q) == "hindi"


def sort_avats(paras, to_avat, to_hindi):
  """Sort avatArikA-region paras with a strict Hindi bar.

  Everything here follows an explicit avatArikA marker, so Sanskrit is
  the default: only explicitly marked (bhAvArtha, +/f-led) or
  overwhelmingly Hindi (3+ hits beating Sanskrit) paras go to Hindi.
  """
  for p in paras:
    q = strip_avat_mark(p)
    if not q or GATHA_LABEL_ONLY_RE.match(q):
      continue
    if q.startswith("भावार्थ") or re.match(r"^\*?\*?भावार्थ", q):
      to_hindi.append(q)
    elif re.match(r"^[+↑f]\s+\S", q):
      to_hindi.append(q)
    else:
      joined = re.sub(r"-\s*\n\s*", "", q)
      h = len(_HINDI_RE.findall(joined))
      s = 2 * joined.count("ऽ") + len(
        _SANSKRIT_RE.findall(joined)) + len(
        _SANSKRIT_GLUED_RE.findall(joined))
      if h >= 3 and h > s:
        to_hindi.append(q)
      else:
        to_avat.append(q)


def sort_region(region_paras, to_avat, to_hindi, is_first_of_set):
  """Sort pre-mUlam paragraphs; Hindi bits -> hindi, rest -> avat/intro."""
  for p in region_paras:
    q = GATHA_PREFIX_RE.sub("", p).strip()
    if not q or GATHA_LABEL_ONLY_RE.match(q):
      continue
    if q.startswith("भावार्थ") or re.match(r"^\*?\*?भावार्थ", q):
      to_hindi.append(q)
    elif re.match(r"^[+↑f]\s+\S", q):
      to_hindi.append(q)
    elif classify_paragraph(q) == "hindi":
      to_hindi.append(q)
    else:
      to_avat.append(q)


def parse_chunk(paras):
  """Parse one dashaka chunk -> (intro_paras, [Verse], None).

  Verse spans are anchored on mUlam markers; each verse's avatArikA is
  searched backwards from its mUlam so consecutive verses never overlap.
  Commentary stays raw here; recover_chunk() classifies it after
  mUlam completion / bare-mUlam promotion.
  """
  anchors = []
  for i, p in enumerate(paras):
    if MULAM_START_RE.match(p):
      head, tail, num, mangled = split_mulam_para(p)
      anchors.append({"idx": i, "head": head, "tail": tail, "num": num,
                      "mangled": mangled})
  if not anchors:
    return [], [], paras
  av_idx = []
  for v, a in enumerate(anchors):
    start = anchors[v - 1]["idx"] + 1 if v > 0 else 0
    av_idx.append(find_avat_idx(paras, start, a["idx"]))
  comm_end = []
  for v, a in enumerate(anchors):
    if v + 1 < len(anchors):
      av2 = av_idx[v + 1]
      comm_end.append(av2 if av2 is not None else anchors[v + 1]["idx"])
    else:
      comm_end.append(len(paras))
  intro, verses = [], []
  for v, a in enumerate(anchors):
    verse = Verse()
    verse.mulam = a["head"]
    verse.local = a["num"]
    verse._mangled = a["mangled"]
    verse._anchor_idx = a["idx"]
    region_start = comm_end[v - 1] if v > 0 else 0
    region_end = av_idx[v] if av_idx[v] is not None else a["idx"]
    region = paras[region_start:region_end]
    avat_paras = paras[av_idx[v]:a["idx"]] if av_idx[v] is not None else []
    if v == 0:
      # Leading non-avatArikA text = set intro (dashaka title + upodghAta).
      for p in region:
        q = GATHA_PREFIX_RE.sub("", p).strip()
        if not q or GATHA_LABEL_ONLY_RE.match(q):
          continue
        intro.append(q)
    else:
      sort_region(region, verse.avat, verse.pre_hindi, False)
    sort_avats(avat_paras, verse.avat, verse.pre_hindi)
    verse._comm_raw = ([a["tail"]] if a["tail"] else []) + \
      paras[a["idx"] + 1:comm_end[v]]
    verses.append(verse)
  return intro, verses, None


def classify_comm(verse):
  for p in verse._comm_raw:
    q = p.strip()
    if not q or GATHA_LABEL_ONLY_RE.match(q):
      continue
    if is_hindi_para(q):
      verse.hindi.append(q)
    else:
      verse.tika.append(q)


# Systematic Devanagari OCR confusion ९ -> ६ at the 9th verse.
MUDRITA_NOTE = "<!-- mudrite ||6|| -->"
MUDRITA_I_NOTE = "<!-- mudrite ||I|| -->"


def correct_six_to_nine(verse, warnings, set_no=None):
  verse.local = 9
  verse.mulam = (verse.mulam + " " + MUDRITA_NOTE).strip()
  where = ("set %d " % set_no) if set_no else ""
  warnings.append("%sverse 9 printed as ||6||; heading corrected" % where)


def complete_split_mulam(verse, expected, warnings, set_no=None):
  """Glue a marker-less mUlam ending (later ||n|| para) onto the head.

  The scan skips footnote defs (pooled), page markers (kept inline) and
  Hindi paras (kept as Hindi); it stops at the first Sanskrit para
  ending with the expected number, or at any structural marker. Nothing
  is consumed unless the ending is found (deferred commit).
  """
  if VERSE_END_RE.search(verse.mulam) \
      or DANGLING_END_RE.search(verse.mulam) or verse._mangled:
    return
  pages, hindi_tmp, stray_tmp = [], [], []
  consumed = 0
  found = None
  for p in verse._comm_raw:
    q = p.strip()
    if MULAM_START_RE.match(q) or (
        AVAT_MARK_RE.search(q) and not DASHAKA_TITLE_RE.match(q)):
      break
    if not q:
      continue
    mpage = re.match(r"^(?:\[\[P\d+\]\]\s*)+", q)
    if mpage:
      pages.append(mpage.group(0).strip())
      q = q[mpage.end():].strip()
      if not q:
        consumed += 1
        continue
    if FOOT_DEF_RE.match(q):
      stray_tmp.append(q)
      consumed += 1
      continue
    if is_hindi_para(q):
      hindi_tmp.append(q)
      consumed += 1
      continue
    ms = list(VERSE_END_RE.finditer(q))
    if ms and ms[-1].end() >= len(q) - 2:
      num = verse_end_num(ms[-1])
      if num == expected or (num == 6 and expected == 9):
        found = q
        consumed += 1
        if num == 6 and expected == 9:
          found += " " + MUDRITA_NOTE
        break
      warnings.append("set %s verse %s: unexpected ||%s|| while "
                      "completing mUlam" % (set_no, expected, num))
      return
    if len(q) > 60:
      return
    consumed += 1  # short stray line inside the split mUlam; skip
  if found is None:
    warnings.append("set %s verse %s: mUlam has no ||n|| ending"
                    % (set_no, expected))
    return
  verse._stray_defs.extend(stray_tmp)
  verse.hindi.extend(hindi_tmp)
  verse.mulam = (verse.mulam + " " + " ".join(pages + [found])).strip()
  verse._comm_raw = verse._comm_raw[consumed:]


def bare_mulam_match(q, expected):
  """Bare (marker-less) mUlam line ending with the expected number?"""
  q = re.sub(r"\s*(?:" + _ORD + r"(?:\s+या\s+" + _ORD + r")?\s+गा(?:था|या)"
             r"[\s:;.\-–—]*)$", "", q).strip()
  if not q or len(q) > 300:
    return False
  if MULAM_START_RE.match(q) or FOOT_DEF_RE.match(q):
    return False
  if q.startswith("भावार्थ") or re.match(r"^[+↑f]\s+\S", q):
    return False
  if classify_paragraph(q) == "hindi":
    return False
  ms = list(VERSE_END_RE.finditer(q))
  if not ms or ms[-1].end() < len(q) - 2:
    return False
  num = verse_end_num(ms[-1])
  if num is None:
    return False
  return num == expected or (num == 6 and expected == 9)


def fill_local_numbers(verses, start_hint=None):
  prev = start_hint
  for verse in verses:
    if verse.local is None:
      verse.local = (prev + 1) if prev else 1
    prev = verse.local


def recover_chunk(intro, verses, set_no, warnings):
  """Fill numbers, fix OCR ९->६, complete split mUlams, promote bare ones."""
  fill_local_numbers(verses)
  # 1. Sequential 6 -> 9 correction (anchored verses).
  prev = None
  for verse in verses:
    exp = (prev + 1) if prev else verse.local
    if verse.local == 6 and exp == 9:
      correct_six_to_nine(verse, warnings, set_no)
    elif prev is not None and verse.local != exp:
      warnings.append("set %s: verse ||%s|| out of sequence (expected %s)"
                      % (set_no, verse.local, exp))
    prev = verse.local
  # 2. Complete marker-less split mUlams (no ||n|| in the head).
  for verse in verses:
    if not VERSE_END_RE.search(verse.mulam):
      complete_split_mulam(verse, verse.local, warnings, set_no)
  # 3. Split off trailing dashaka/shataka extras (last verse only).
  extras = []
  if verses:
    cut = next((j for j, p in enumerate(verses[-1]._comm_raw)
                if is_extra_start(p)), None)
    if cut is not None:
      extras = verses[-1]._comm_raw[cut:]
      verses[-1]._comm_raw = verses[-1]._comm_raw[:cut]
  # 4. Promote bare mUlams hiding in commentary.
  i = 0
  while i < len(verses):
    verse = verses[i]
    exp_next = verse.local + 1 if verse.local not in (None, 11) else None
    hit = None
    if exp_next is not None:
      for k, p in enumerate(verse._comm_raw):
        if bare_mulam_match(p.strip(), exp_next):
          hit = k
          break
    if hit is None:
      i += 1
      continue
    bare = verse._comm_raw[hit].strip()
    new = Verse()
    new.local = exp_next
    new.mulam = bare
    if exp_next == 9 and verse_end_num(
        list(VERSE_END_RE.finditer(bare))[-1]) == 6:
      new.mulam += " " + MUDRITA_NOTE
    region = verse._comm_raw[:hit]
    after = verse._comm_raw[hit + 1:]
    amark = None
    for j in range(len(region) - 1, -1, -1):
      if AVAT_MARK_RE.search(region[j]) \
          and not DASHAKA_TITLE_RE.match(region[j]):
        amark = j
        break
    if amark is not None:
      sort_avats(region[amark:], new.avat, new.pre_hindi)
      verse._comm_raw = region[:amark]
    else:
      warnings.append("set %s verse %s: bare mUlam, empty avatArikA"
                      % (set_no, exp_next))
      verse._comm_raw = region
    # Everything after the bare mUlam belongs to the new verse.
    new._comm_raw = after
    i += 1
    verses.insert(i, new)
    i += 1
  for verse in verses:
    classify_comm(verse)
  return intro, verses, extras


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------

def collect_verse_defs(lists):
  """Extract footnote defs from all of a verse's para-lists (shared pool).

  Returns (cleaned_lists, raw_defs) where raw_defs maps the bare footnote
  number (e.g. "1") to its text. Mixed paragraphs keep their non-def lines.
  """
  defs = {}

  def add(m, val):
    key = deva_to_arab(m.group(1))
    if key in defs:
      i = 2
      while "%s_%d" % (key, i) in defs:
        i += 1
      key = "%s_%d" % (key, i)
    defs[key] = val

  def is_def(line):
    s = line.strip()
    m = FOOT_DEF_RE.match(s)
    return bool(m and len(s) < 300
                and (FOOT_REF_KEYWORDS_RE.search(m.group(2))
                     or len(m.group(2)) < 80))

  cleaned = []
  for paras in lists:
    kept = []
    for p in paras:
      lines = split_multi_defs(p.split("\n"))
      if len(lines) == 1:
        m = FOOT_DEF_RE.match(p.strip())
        if m and is_def(p):
          add(m, m.group(2).strip())
          continue
        kept.append(p)
      else:
        # Multi-line para from def-gluing: a def line absorbs its
        # following non-def, non-Hindi continuation lines; def-looking
        # lines always split out; Hindi lines stay separate content.
        rest = []
        cur = None
        for ln in lines:
          if re.fullmatch(r"[0-9०-९,;.\-–—\s|]+", ln.strip()):
            continue  # stray number/punctuation line: drop
          m = FOOT_DEF_RE.match(ln.strip())
          if m and is_def(ln):
            if cur is not None:
              defs[cur[0]] = cur[1]
            cur = None
            key = deva_to_arab(m.group(1))
            if key in defs:
              i = 2
              while "%s_%d" % (key, i) in defs:
                i += 1
              key = "%s_%d" % (key, i)
            cur = [key, m.group(2).strip()]
          elif cur is not None and ln.strip() and not is_hindi_para(ln):
            cur[1] += " " + ln.strip()
          elif ln.strip():
            if cur is not None:
              defs[cur[0]] = cur[1]
              cur = None
            rest.append(ln.strip())
        if cur is not None:
          defs[cur[0]] = cur[1]
        if rest:
          kept.append("\n".join(rest))
    cleaned.append(kept)
  return cleaned, defs


def render_verse(verse, set_ara, warnings):
  loc = verse.local
  loc_deva = arab_to_deva(loc)
  prefix = "%d_%d" % (set_ara, loc)
  cleaned, raw_defs = collect_verse_defs(
    [verse.avat, [verse.mulam] if verse.mulam else [],
     verse.tika, verse.pre_hindi + verse.hindi, verse._stray_defs])
  # NOTE: stray defs (cleaned[4]) only feed the pool; not rendered.
  avat, mulam_l, tika, hindi = cleaned[:4]
  fid_defs = {"%s_%s" % (prefix, k): v for k, v in raw_defs.items()}

  def render_list(paras, emitted):
    out = []
    for p in paras:
      p = insert_footnote_refs(p, raw_defs, prefix)
      out.append(p)
      for r in re.findall(r"\[\^([^\]]+)\]", p):
        if r in fid_defs and r not in emitted:
          out.append("[^%s]: %s" % (r, fid_defs[r]))
          emitted.add(r)
    return "\n\n".join(out).strip()

  emitted = set()
  avat_md = render_list(avat, emitted)
  mulam_md = render_list(mulam_l, emitted)
  tika_md = render_list(tika, emitted)
  hindi_md = render_list(hindi, emitted)
  referenced = set(re.findall(r"\[\^([^\]]+)\]",
                              avat_md + mulam_md + tika_md + hindi_md))
  leftovers = ["[^%s]: %s" % (f, d) for f, d in fid_defs.items()
               if f not in referenced]
  if leftovers:
    tika_md = (tika_md + "\n\n" + "\n\n".join(leftovers)).strip()
  if not verse.avat:
    warnings.append("set %d verse %d: empty avatArikA" % (set_ara, loc))
  if not verse.mulam:
    warnings.append("set %d verse %d: empty mUlam" % (set_ara, loc))
  if not verse.tika:
    warnings.append("set %d verse %d: empty TIkA" % (set_ara, loc))
  if not verse.pre_hindi + verse.hindi:
    warnings.append("set %d verse %d: empty Hindi" % (set_ara, loc))
  missing = "<!-- source mein spashta khanda nahin mila -->"
  out = []
  out.append("### %s" % loc_deva)
  out.append("<details><summary>अवतारिका - %s</summary>" % loc_deva)
  out.append("")
  out.append(avat_md if avat_md else missing)
  out.append("")
  out.append("</details>")
  out.append("<details open><summary>मूल - %s</summary>" % loc_deva)
  out.append("")
  out.append(mulam_md if mulam_md else missing)
  out.append("")
  out.append("</details>")
  out.append("<details><summary>टीका - %s</summary>" % loc_deva)
  out.append("")
  out.append(tika_md if tika_md else missing)
  out.append("")
  out.append("</details>")
  out.append("<details><summary>हिन्दी - %s</summary>" % loc_deva)
  out.append("")
  out.append(hindi_md if hindi_md else missing)
  out.append("")
  out.append("</details>")
  return "\n".join(out)


# ---------------------------------------------------------------------------
# Top-level file structuring.
# ---------------------------------------------------------------------------

PREAMBLE_VERSES = 9


def renumber_preamble(preamble):
  for n in range(1, PREAMBLE_VERSES + 1):
    old = "### " + arab_to_deva(n).rjust(3, "०")
    preamble = preamble.replace(old, "### " + arab_to_deva(n))
  return preamble


def relocate_hindi(all_sets, warnings):
  """Move floated Hindi to its numbered verse.

  Hindi blocks sometimes print after the NEXT verse's avatArikA. A Hindi
  rendering ending with ||n|| belongs to verse n (same set), except
  ||6|| in verse 10's span, which is verse 9's (OCR confusion, matching
  its misprinted mUlam). Unnumbered bhAvArtha paras stay put unless
  they sit pre-mUlam and explicitly hark back ("pUrva gAthA"), in which
  case they join the previous verse. Renderings printed as ||6|| for
  verse 9 stay put (same OCR confusion as the mUlam correction).
  """
  flat = [(s, v) for (s, intro, verses, extras) in all_sets
          for v in verses]
  by_loc = {}
  for idx, (s, v) in enumerate(flat):
    by_loc.setdefault((s, v.local), []).append(idx)

  def trailing_num(p):
    ms = list(VERSE_END_RE.finditer(p.strip()))
    if not ms or ms[-1].end() < len(p.strip()) - 2:
      return None
    return verse_end_num(ms[-1])

  def has_numbered_hindi(v, n):
    for q in v.pre_hindi + v.hindi:
      if trailing_num(q) == n:
        return True
    return False

  moves = []  # (para, from_idx, to_idx, note)
  for idx, (s, v) in enumerate(flat):
    for lstname in ("pre_hindi", "hindi"):
      for p in list(getattr(v, lstname)):
        n = trailing_num(p)
        if n is None:
          continue
        if n == v.local:
          continue
        if n == 6 and v.local == 9:
          continue  # OCR-mislabeled own rendering; keep
        tgt = None
        if n == 6 and v.local == 10:
          tgt = by_loc.get((s, 9), [None])[0]  # like its mUlam
        elif n < v.local:
          tgt = by_loc.get((s, n), [None])[0]  # late float, one back
        else:
          warnings.append("set %s verse %s: Hindi ending ||%s|| kept "
                          "(no forward float)" % (s, v.local, n))
          continue
        if tgt is None:
          warnings.append("set %s verse %s: Hindi ending ||%s|| has no "
                          "target verse" % (s, v.local, n))
          continue
        if has_numbered_hindi(flat[tgt][1], n):
          warnings.append("set %s verse %s: Hindi ||%s|| duplicates "
                          "target's; kept" % (s, v.local, n))
          continue
        moves.append((p, idx, tgt, n))
    # Unnumbered pre-mUlam bhAvArtha harking back joins the prev verse.
    if idx > 0:
      for p in list(v.pre_hindi):
        if trailing_num(p) is not None:
          continue
        if re.search(r"पूर्व\s*गाथा|पूर्वगाथा|प्राग्गाथा", p):
          moves.append((p, idx, idx - 1, "back-ref"))
  for p, frm, to, n in moves:
    for lstname in ("pre_hindi", "hindi"):
      lst = getattr(flat[frm][1], lstname)
      if p in lst:
        lst.remove(p)
    flat[to][1].hindi.append(p)
    warnings.append("relocated Hindi ||%s||: set %s verse %s -> verse %s"
                    % (n, flat[frm][0], flat[frm][1].local,
                       flat[to][1].local))


def structure_file(in_path, out_path):
  warnings = []
  text = Path(in_path).read_text(encoding="utf-8")
  if re.search(r"(?m)^## \S+", text) and "<details" in text:
    raise SystemExit(
      "input looks already structured (has ## sets + <details>); "
      "run only on raw OCR files")
  # Preamble = already-formatted verses 1-9, cut at the dotted separator.
  dot = re.search(r"(?m)^\.+$\n?", text)
  if dot and "<details" in text[:dot.start()]:
    preamble, raw = text[:dot.start()], text[dot.end():]
  else:
    preamble, raw = "", text
  parts = []
  preamble_kept = False
  if preamble:
    lines = preamble.rstrip().split("\n")
    head, body = [], []
    for ln in lines:
      if re.match(r"^###\s+", ln) and not body:
        body.append(ln)
      elif body:
        body.append(ln)
      else:
        head.append(ln)
    preamble = "\n".join(head).rstrip() + "\n\n## १\n\n" + renumber_preamble(
      "\n".join(body).strip()) if body else preamble
    # Repair: hand-done verse 9 nests <details open>मूलम् inside an
    # unclosed अवतारिका block (4 opens, 3 closes). Close it first.
    preamble = preamble.replace(
      "\n\n<details open><summary>मूलम् - ९</summary>",
      "\n\n</details>\n\n<details open><summary>मूलम् - ९</summary>",
      1) if preamble.count("<details") > preamble.count("</details>") \
      else preamble
    parts.append(preamble.rstrip())
    preamble_kept = True
    set_counter = 1
  else:
    set_counter = 0
  # Split the raw remainder into dashaka chunks at dashaka titles.
  chunks = re.split(r"(?m)(?=^[^\n]*दशक\s*-\s*अवतारिका)", raw)
  chunks = [c for c in chunks if c.strip()]
  all_sets = []
  for chunk in chunks:
    paras = assemble_paragraphs(clean_lines(chunk))
    intro, verses, _ = parse_chunk(paras)
    if not verses:
      # Pure extra material (should not normally happen).
      all_sets.append((None, [], [], paras))
      continue
    fill_local_numbers(verses)
    first_local = verses[0].local
    if set_counter == 1 and first_local in (10, 11):
      set_no = 1  # continuation of the preamble set
    elif first_local == 1:
      set_counter += 1
      set_no = set_counter
    elif verses[0].local is not None and set_counter >= 1:
      # Missing ``||1||`` (OCR gap): still a new set when numbers restart.
      set_counter += 1
      set_no = set_counter
      warnings.append("chunk starts with verse %d; assumed new set %d"
                      % (first_local, set_no))
    else:
      set_no = set_counter or 1
    intro, verses, extras = recover_chunk(intro, verses, set_no, warnings)
    all_sets.append((set_no, intro, verses, extras))
    set_counter = set_no
  relocate_hindi(all_sets, warnings)
  for entry in all_sets:
    if entry[0] is None:
      parts.append("\n\n".join(entry[3]).strip())
      continue
    set_no, intro, verses, extras = entry
    if not (preamble_kept and set_no == 1):
      # ## १ already printed at the end of the preamble.
      parts.append("## %s" % arab_to_deva(set_no))
    if intro:
      parts.append(render_with_footnotes(intro, "%d_0" % set_no))
    for verse in verses:
      parts.append(render_verse(verse, set_no, warnings))
    if extras:
      parts.append(render_with_footnotes(extras, "%d_99" % set_no))
    set_counter = set_no
  out = "\n\n".join(p for p in parts if p.strip()) + "\n"
  Path(out_path).write_text(out, encoding="utf-8")
  return warnings


def main(argv=None):
  ap = argparse.ArgumentParser(
    description="Structure raw sa_hi files into ## sets of verse <details>.")
  ap.add_argument("in_path", help="raw sa_hi markdown file")
  ap.add_argument("out_path", help="structured output markdown file")
  args = ap.parse_args(argv)
  warnings = structure_file(args.in_path, args.out_path)
  for w in warnings:
    print("WARNING: " + w, file=sys.stderr)
  print("wrote " + args.out_path)


if __name__ == "__main__":
  main()
