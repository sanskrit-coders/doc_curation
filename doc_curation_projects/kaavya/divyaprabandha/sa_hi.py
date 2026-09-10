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
  <details><summary>अवतारिका - <verse></summary> ... </details>
  <details open><summary>मूलम् - <verse></summary> ... </details>
  <details><summary>टीका - <verse></summary> ... </details>
  <details><summary>हिन्दी - <verse></summary> ... </details>

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
import collections
import logging
import re
import sys
from pathlib import Path

from doc_curation.translation.classifier import (
  _HINDI_RE, _SANSKRIT_GLUED_RE, _SANSKRIT_RE, classify_paragraph,
  score_paragraph)

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
# Structural patterns.
# ---------------------------------------------------------------------------

VERSE_END_RE = re.compile(
  r"(?:॥|\|{2}|\.\.|।{2})\s*([०-९0-9ई]*)\s*"
  r"(?:॥|\|{2}|\.\.|।{2}|\|(?![|]))")
# Bare numberless end ("।।" double single-daNDa, digits lost in print).
BARE_DANDA_RE = re.compile(r"(?<![०-९0-9।॥|])।।(?![०-९0-9।॥|])")
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
  r"^(?:\[\[P\d+\]\]\s*)*\*?\*?\s*(?<![\u0900-\u097F])(?:मूलम्|मुलम्|मलम्|मूत्रम्)"
  r"(?:\s*[-–—:]+\s*|\s+)")
# OCR variants: अवतारिका, अवंतारिका, अवतरिका, truncated अवतारिक.
# Dashaka titles likewise vary (05 नवमदर्शक = नवमदशक, OCR श/श).
_AVAT_CORE = r"अवं?त[ा]?रिका?"
_TITLE_CORE = r"(?:\S*दशक|\S*दर्शक)"
AVAT_MARK_RE = re.compile(
  _AVAT_CORE + r"\*?\*?(?:\s+का)?(?:\s*[०-९0-9]+\s*)?\s*[-–—:]+"
  r"|(?:^|\n)\*?\*?" + _AVAT_CORE + r"\*?\*?\s+(?=[\u0900-\u097F])")
# Mid-line mUlam markers start new lines only at a word boundary: this
# blocks ṭīkā pratīka-glosses like "...करः कमलम् - ..." (the मलम् of
# कमलम्!). Mid-line avatArikA markers only split after a daNDa, so
# "X-दशक - अवतारिका-" titles stay intact.
_MIDLINE_MULAM_RE = re.compile(
  r"\s*(?=\*?\*?(?<![\u0900-\u097F])(?:मूलम्|मुलम्|मलम्|मूत्रम्)\s*[-–—:])")
_MIDLINE_AVAT_RE = re.compile(
  r"(?<=[।.!?])\s*(?=\*?\*?अवतारिका\s*[-–—:])")
DASHAKA_TITLE_RE = re.compile(
  r"^[ \t]*\*?[ \t]*(?:\S+[ \t]+)?" + _TITLE_CORE + r"[ \t]*-*[ \t]*" +
  _AVAT_CORE + r"(?![\u0900-\u097F])")
CHUNK_SPLIT_RE = re.compile(
  r"(?m)(?=^[ \t]*\*?[ \t]*(?:\S+[ \t]+)?" + _TITLE_CORE +
  r"[ \t]*-*[ \t]*" + _AVAT_CORE + r"(?![\u0900-\u097F]))")
# Flexible ordinals (long/short/fused): prathamA, tRtIya, prathama-gAthA ...
# OCR drops the anunAsika (paJcama -> paMcama: पञ्चम/पंचम).
_ORD = (r"(?:प्रथम|द्वितीय|तृतीय|चतुर्थ|पञ्चम|पंचम|षष्ठ|सप्तम|अष्टम|नवम|"
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
  r"मूलानुसारी|आकर|इति|श्रूयते|उच्यते|इत्यप्य|व्याख्यान|अर्थ|भावः)")
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
    pn = parse_page_number(s)
    if pn is not None:
      # Page numbers run in both scripts (२१३ and 88): keep them all.
      out.append("[[P%d]]" % pn)
      continue
    if not re.search(r"[\u0900-\u097F]", s) and not re.match(
        r"^\s*(\[\[|\[\^|\+{3}|title)", s):
      # No Devanagari at all (Tibetan debris, stray latin, long digit
      # garbage like 1000068): drop.
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
      # Catches page numbers exposed by bracket/label stripping above.
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
  if re.match(r"^[+↑f†‡]\s+\S", s):
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
      or re.match(r"^[+↑f†‡]\s+\S", p))
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
    self._orphans = []     # anchorless verses split off in parse
    self._stray_defs = []  # footnote-def paras consumed during recovery
    self._mangled = False  # mUlam end mangled (F1:/§/empty): complete text
    self._had_num = False  # anchor carried its own ||n|| number
    self._has_avat = False  # own avatArikA marker found before the anchor
    self._corrected_from = None  # print number replaced by positional fix


def split_mulam_para(p):
  """(head, tail, local_number_or_None, mangled_end_bool).

  head runs up to the first proper ``||n||`` ending (``|| ई ||`` reads
  as 9, empty ``|| ||`` stays numberless), or up to a mangled OCR
  ending (``F1:``, ``§``). tail is the rest (usually TIkA start).
  Leading page markers are preserved at the head.

  Swallow guard: when the head holds a bare numberless ``।।`` before
  its proper ``||n||``, the true end lost its number in print and the
  ``||n||`` belongs to a TIkA restatement -- cut at the bare ``।।``
  (numberless) so TIkA stays out of the mUlam.
  """
  pre = ""
  mpage = re.match(r"^(?:\[\[P\d+\]\]\s*)+", p.strip())
  rest = p.strip()
  if mpage:
    pre = mpage.group(0).strip() + " "
    rest = rest[mpage.end():].strip()
  q = MULAM_START_RE.sub("", rest).strip()
  ms = list(VERSE_END_RE.finditer(q))
  mangled = None
  if ms:
    m = ms[0]
  else:
    m = None
  mm = MANGLED_END_RE.search(q)
  if mm and (not ms or mm.start() < ms[0].start()):
    head = pre + q[:mm.end()].strip()
    tail = re.sub(r"^[|lI1:;.\-–—\s]+", "", q[mm.end():]).strip()
    return head, tail, None, True
  if not ms:
    bm = BARE_DANDA_RE.search(q)
    if bm:
      # Numberless anchor hiding "mUlam ।। TIkA ...": cut at the bare
      # end (genuine numberless ends simply end there instead).
      return (pre + q[:bm.end()].strip(), q[bm.end():].strip(), None,
              False)
    dm = DANGLING_END_RE.search(q)
    if dm:
      return (pre + q[:dm.end()].strip(), q[dm.end():].strip(), None,
              False)
    return pre + q, "", None, False
  m = ms[0]
  num = verse_end_num(m)
  head = pre + q[:m.end()].strip()
  tail = q[m.end():].strip()
  if m.group(1) == "ई":
    head += " " + MUDRITA_I_NOTE
  if num is not None:
    # Swallow guard: a bare ।। strictly BEFORE the end-match means
    # the true end lost its number and the ||n|| closes a TIkA
    # restatement -- cut there (the two ।। of a genuine "।। n ।।"
    # end are its own opener/closer and never count).
    bound = len(pre) + m.start()
    cut = next((bm.end() for bm in BARE_DANDA_RE.finditer(head)
                if bm.end() <= bound), None)
    if cut is not None:
      tail = (head[cut:].strip() + " " + tail).strip()
      head = head[:cut].strip()
      return head, tail, None, False
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
  p = re.sub(r"^\*?\*?" + _AVAT_CORE +
            r"\*?\*?(?:\s+का)?(?:\s*[०-९0-9]+\s*)?\s*[-–—:]+\s*",
            "", p).strip()
  p = re.sub(r"^\*?\*?" + _AVAT_CORE +
            r"\*?\*?\s+(?=[\u0900-\u097F])", "", p).strip()
  return p


def is_hindi_para(q):
  if q.startswith("भावार्थ") or re.match(r"^\*?\*?भावार्थ", q):
    return True
  if re.match(r"^[+↑f†‡]\s+\S", q):
    return True
  return classify_paragraph(q) == "hindi"


# Exegetical markers: a paragraph with these + a verse number is ṭīkā
# anvaya/restatement, never a mUlam (genuine mUlams may quote "iti"
# but never these glossing forms).
EXEGETICAL_RE = re.compile(
  r"इत्यर्थ|इति\s*भाव|इत्याह|इत्युक्त|इत्यादि|तात्पर्य|अन्वय")


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
    elif re.match(r"^[+↑f†‡]\s+\S", q):
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
    elif re.match(r"^[+↑f†‡]\s+\S", q):
      to_hindi.append(q)
    elif classify_paragraph(q) == "hindi":
      to_hindi.append(q)
    else:
      to_avat.append(q)


def _nearest_dashaka_num(lines, idx, guard=200):
  """Numeral of the nearest ``## N`` header (either direction) or None.

  Intro blocks usually follow their ``## N`` header, but sometimes precede
  it; nearest wins, ties go backward. Beyond ``guard`` lines: None.
  """
  best, best_dist, best_back = None, None, True
  dist = 0
  for j in range(idx - 1, -1, -1):
    dist += 1
    if dist > guard:
      break
    m = re.match(r"^##(?!#)\s*(\S+)", lines[j])
    if m:
      best, best_dist, best_back = m.group(1), dist, True
      break
  dist = 0
  for j in range(idx + 1, len(lines)):
    dist += 1
    if dist > guard:
      break
    m = re.match(r"^##(?!#)\s*(\S+)", lines[j])
    if m:
      if best is None or dist < best_dist:
        best, best_dist, best_back = m.group(1), dist, False
      break
  return best


def _label_span(span, prev):
  if re.match(r"^\s*(?:\*\*)?भावार्थ", span):
    return "hi"
  if re.match(r"^[+↑f†‡]\s+\S", span):
    return "hi"
  c = classify_paragraph(span)
  if c == "hindi":
    return "hi"
  if c == "sanskrit":
    return "sa"
  return prev


def _split_body_sentences(body):
  """Split details body into offset spans for language labeling.

  Footnote-definition lines (``[^id]: ...``) are masked with spaces
  (offset-preserving) so their internal daNDas never split them apart,
  and become their own spans (cut at def boundaries) so neighbours on
  each side score cleanly; scoring uses the original text. Bracketed
  marginal/page refs end spans (the language often switches right after
  them); bare print-marginal digits (में४००, , १-) start spans instead,
  so trailing punctuation travels forward rather than orphaning. Print
  hyphen line-breaks also cut (word halves stay unknown and rejoin via
  continuity, but a switch hiding at the break gets its own span).
  Homogeneous sides always rejoin into one run, so extra cuts only ever
  separate genuinely mixed spans.
  """
  defs = list(re.finditer(r"(?m)^[ \t]*\[\^[^\]]+\]:[^\n]*", body))
  masked = []
  pos = 0
  for m in defs:
    masked.append(body[pos:m.start()])
    masked.append(" " * (m.end() - m.start()))
    pos = m.end()
  masked.append(body[pos:])
  scan = "".join(masked)
  cuts = set()
  for m in _SENT_CUT_RE.finditer(scan):
    cuts.add(m.end())
  for m in defs:
    cuts.add(m.start())
    cuts.add(m.end())
  # Bare marginals cut BEFORE the digit run, so trailing punctuation
  # (३, ...) travels with the following span instead of orphaning.
  for m in _BARE_MARG_RE.finditer(scan):
    cuts.add(m.start())
  spans = []
  pos = 0
  for end in sorted(cuts):
    if end <= pos:
      continue
    if body[pos:end].strip():
      spans.append([pos, end])
    elif spans:
      spans[-1][1] = end
    pos = end
  tail = body[pos:]
  if tail.strip():
    spans.append([pos, len(body)])
  elif spans:
    spans[-1][1] = len(body)
  # No merge step: def-only spans rejoin via label continuity.
  return [(s, e) for s, e in spans]


# Marginal/page references where the language often switches without any
# sentence delimiter (Hindi head + [३२रू + Sanskrit tail): cut after them.
# Homogeneous sides rejoin into one run, so this only ever separates
# genuinely mixed spans. Footnote refs ([^...]) never match (caret/_
# break the numeric core); def lines are masked before scanning anyway.
_MARG_NUM = r"[0-9०-९]+(?:\s*/\s*[0-9०-९]+)?"
_MARG_SFX = r"(?:रू|लू|[रल])?"
# The closing-bracket alternative requires its number NOT to follow a
# word character or caret, so footnote refs ([^7_0_1], [12x]) never cut.
_MARGINAL_RE = (
  r"(?:\[+\s*(?:P\s*[0-9]+|%s)\s*%s\s*\]*|(?<![\u0900-\u097F0-9०-९\w^])%s\s*%s\s*[\]\)]+)"
  % (_MARG_NUM, _MARG_SFX, _MARG_NUM, _MARG_SFX))
# Bare print-marginal digits glued to words (में४०० कृत, कर४५२ तीव)
# or standing as list/marginal markers (, १- भगवान्): cut after them.
# Legitimate words never contain digits, and homogeneous sides rejoin,
# so this only separates artifact-glued mixed spans. The glued-side
# lookbehind admits only Devanagari letters/signs (so verse numbers
# like ८।१२।३ never cut) and never word characters/carets (so footnote
# refs like [^7_0_1] never cut).
_DEV_LETTER = r"\u0905-\u0939\u093E-\u094C\u094D\u0902\u0903"
# A lone ० glued to a letter is an abbreviation (स०/गी०/रा०), never a
# marginal, so glued runs must lead with a nonzero digit.
_BARE_MARG_RE = re.compile(
  r"(?:(?<=[%s])(?:[1-9][0-9]*|[१-९][०-९]*)-?|(?<![\u0900-\u097F0-9०-९\w^])[0-9०-९]+-)"
  % _DEV_LETTER)
_SENT_CUT_RE = re.compile(r"[।॥?!]+|%s|-\s*\n" % _MARGINAL_RE)


# Tolerant bare-marker patterns (cf. DASHAKA_TITLE_RE, plus व/ब and
# शतक variants): `प्रथमदशक-अवतारिका`, `द्वितीयदशक - अवतारिका-`,
# `चतुर्थदशक - अवतारिक` (truncated), `दशमदशक- अबतारिका`, ...
_INTRO_SANSKRIT_RE = re.compile(
  r"^[ \t]*\*?[ \t]*(?:\S+[ \t]+)?\S*(?:दशक|दर्शक|शतक)[ \t]*-*[ \t]*अ[वब]ं?त[ा]?रिका?")
_INTRO_HINDI_RE = re.compile(r"^(.*(?:दशक|शतक) का सार(?:ार्थ)?\s*-+\s*)(.*)$")


def _intro_marker_kind(s):
  """(title, rest) if stripped line s is a bare intro marker, else (None, "").

  Sanskrit markers stand alone (trailing dashes/spaces only); Hindi
  markers keep text following the marker on the same line.
  """
  if s.startswith(("<", "#", "[", ">", "|")):
    return None, ""
  m = _INTRO_SANSKRIT_RE.match(s)
  if m and not s[m.end():].strip(" \t-–—"):
    text = s[:m.end()]
    title = "शतकावतारिका" if ("शतक" in text and "दशक" not in text) else "दशकावतारिका"
    return title, ""
  m = _INTRO_HINDI_RE.match(s)
  if m:
    # preserve any footnote-ref junk preceding the marker core itself
    core = re.search(r"(?:\S+\s+)?(?:दशक|शतक) का सार(?:ार्थ)?\s*-+\s*", s)
    pre = s[:core.start()].strip() if core else ""
    rest = ((pre + " " + m.group(2)).strip() if pre else m.group(2))
    return "हिन्दी", rest
  return None, ""


def _wrap_bare_intro_markers(lines):
  """Wrap bare dashaka/shataka intro marker regions (outside details).

  Returns new line list. Marker regions become plain-titled details
  blocks (numbering/splitting happens downstream); lines already inside
  details blocks are untouched.
  """
  out = []
  i, depth, n = 0, 0, len(lines)
  while i < n:
    line = lines[i]
    s = line.strip()
    kind, rest = _intro_marker_kind(s) if depth <= 0 else (None, "")
    if kind is None:
      out.append(line)
      depth += line.count("<details") - line.count("</details>")
      i += 1
      continue
    j = i + 1
    if not rest:
      while j < n and not lines[j].strip():
        j += 1
    k = j
    while k < n:
      t = lines[k].strip()
      if t.startswith("###") or t.startswith("## ") or t.startswith("<details") \
          or t.startswith("<div") or t.startswith("</div"):
        break
      if _intro_marker_kind(t)[0] is not None:
        break
      k += 1
    body = ([rest] if rest else []) + lines[j:k]
    while body and not body[0].strip():
      body.pop(0)
    while body and not body[-1].strip():
      body.pop()
    if not body:
      logging.warning("Empty intro marker at line %d, leaving it", i + 1)
      out.append(line)
      depth += line.count("<details") - line.count("</details>")
      i += 1
      continue
    out += ["<details><summary>%s</summary>" % kind, ""] + body + ["", "</details>", ""]
    for consumed in lines[i:k]:
      depth += consumed.count("<details") - consumed.count("</details>")
    i = k
  return out


def _join_run_texts(texts):
  """Join same-language run texts from different blocks.

  Paragraph break by default; a run ending in ``-`` continues across a
  print hyphen line-break, so it joins with a plain newline instead.
  """
  if not texts:
    return ""
  cur = texts[0]
  for t in texts[1:]:
    cur += ("\n" if cur.rstrip().endswith("-") else "\n\n") + t
  return cur


def split_mixed_avataarikas_content(content):
  """Split language-mixed dashaka/shataka avatArikA blocks by language.

  All same-language runs in a sequence become ONE details block:
  Sanskrit runs merge into ``दशकावतारिका``/``शतकावतारिका`` (numbered
  ``- N``/``हिन्दी - N`` per nearest ``## N`` header), Hindi runs into
  ``... हिन्दी - N``; blocks emit in first-appearance order. Footnote
  definitions travel with their runs. Single-block sequences keep
  existing titles unless renumbering applies. Byte-identical when
  nothing changes (idempotent). Bare intro markers outside blocks are
  wrapped first (same titling).
  """
  content = "\n".join(_wrap_bare_intro_markers(content.split("\n")))
  lines = content.split("\n")
  pat = re.compile(
    r"<details(?P<attrs>[^>]*)><summary>(?P<title>.*?)</summary>(?P<body>.*?)</details>",
    re.S)
  matches = list(pat.finditer(content))
  # target blocks: avataarika titles or bare हिन्दी
  targets = []
  for m in matches:
    title = m.group("title")
    base, hindi = None, False
    mm = re.fullmatch(r"(दशकावतारिका|शतकावतारिका)( हिन्दी)?( - \S+)?", title)
    if mm:
      base, hindi = mm.group(1), bool(mm.group(2))
    elif title == "हिन्दी":
      base, hindi = None, True
    else:
      continue
    if "<details" in m.group("body"):
      logging.warning("Skipping nested block: %r", title)
      continue
    targets.append({"match": m, "base": base, "hindi": hindi})
  # group targets separated only by blank lines into sequences
  seqs, cur = [], []
  prev_end = None
  for t in targets:
    if cur:
      gap = content[prev_end:t["match"].start()]
      gap_lines = gap.split("\n")
      if any(ln.strip() and not ln.strip().startswith("##") and not ln.strip().startswith("###")
             and not ln.strip().startswith("<") for ln in gap_lines):
        seqs.append(cur)
        cur = []
      elif any(ln.strip().startswith("##") for ln in gap_lines):
        seqs.append(cur)
        cur = []
    cur.append(t)
    prev_end = t["match"].end()
  if cur:
    seqs.append(cur)
  out, pos = [], 0
  for seq in seqs:
    start_line = content.count("\n", 0, seq[0]["match"].start())
    base = next((t["base"] for t in seq if t["base"] is not None), None)
    if base is None:
      logging.warning("Orphan हिन्दी block(s), leaving unnamed")
      continue
    num = _nearest_dashaka_num(lines, start_line)
    if num is None:
      logging.warning("No ## header near line %d, leaving titles", start_line + 1)
      continue
    for t in seq:
      m = t["match"]
      attrs, body = m.group("attrs"), m.group("body")
      spans = _split_body_sentences(body)
      labels, prev = [], "hi" if t["hindi"] else "sa"
      for s, e in spans:
        lab = _label_span(body[s:e], prev)
        labels.append(lab)
        prev = lab
      runs, cur_run = [], []
      for (s, e), lab in zip(spans, labels):
        if cur_run and cur_run[0][1] != lab:
          runs.append(cur_run)
          cur_run = []
        cur_run.append(((s, e), lab))
      if cur_run:
        runs.append(cur_run)
      t["attrs"], t["body"], t["runs"] = attrs, body, runs
    sa_title = "%s - %s" % (base, num)
    hi_title = "%s हिन्दी - %s" % (base, num)
    counts = collections.Counter(
      sa_title if run[0][1] == "sa" else hi_title
      for t in seq for run in t["runs"])
    if all(c <= 1 for c in counts.values()):
      for t in seq:
        m = t["match"]
        out.append(content[pos:m.start()])
        attrs, body, runs = t["attrs"], t["body"], t["runs"]
        if len(runs) <= 1 and m.group("title") in (sa_title, hi_title):
          out.append(m.group(0))
        else:
          parts = []
          for run in runs:
            run_title = sa_title if run[0][1] == "sa" else hi_title
            text = body[run[0][0][0]:run[-1][0][1]].strip()
            parts.append("<details%s><summary>%s</summary>\n\n%s\n</details>" % (
              attrs, run_title, text))
          out.append("\n\n".join(parts))
        pos = m.end()
    else:
      # Same language runs recur across blocks: merge each language
      # into a single block, first-appearance order.
      out.append(content[pos:seq[0]["match"].start()])
      groups, lab_attrs = {}, {}
      for t in seq:
        for run in t["runs"]:
          lab = run[0][1]
          groups.setdefault(lab, []).append(
            t["body"][run[0][0][0]:run[-1][0][1]].strip())
          lab_attrs.setdefault(lab, t["attrs"])
      blocks = []
      for lab, texts in groups.items():
        title = sa_title if lab == "sa" else hi_title
        blocks.append("<details%s><summary>%s</summary>\n\n%s\n</details>" % (
          lab_attrs[lab], title, _join_run_texts(texts)))
      out.append("\n\n".join(blocks))
      pos = seq[-1]["match"].end()
  out.append(content[pos:])
  return "".join(out)


def split_mixed_avataarikas(dir_path, file_pattern="*.md", dry_run=False):
  """Split language-mixed dashaka/shataka avatArikAs across files.

  Returns {path: changed_bool}. Pure blocks pass through untouched.
  """
  results = {}
  for fp in sorted(Path(dir_path).glob(file_pattern)):
    if not fp.is_file():
      continue
    text = fp.read_text(encoding="utf-8")
    new_text = split_mixed_avataarikas_content(text)
    changed = new_text != text
    results[str(fp)] = changed
    if changed and not dry_run:
      fp.write_text(new_text, encoding="utf-8")
  return results


PRATIKA_RE = re.compile(r"^(.+?)(?:ेत्यादि|ेत्यादि|इत्यादि)(?![\u0900-\u097F])")
# TIkA gloss-dash ("word-word - explanation"): first phrase doubles as
# a pratIka stem when no इत्यादि form exists (03 set 5 verse 1).
GLOSS_DASH_RE = re.compile(r"^(.{6,60}?)\s*[-–—:]\s*\S")


def despace_find(text, start, needle):
  """Original offset of needle in text at/after start, ignoring
  whitespace on both sides; -1 when absent/too short."""
  ns = re.sub(r"\s+", "", needle)
  if len(ns) < 6:
    return -1
  chars, idxs = [], []
  for t, ch in enumerate(text):
    if t < start or re.match(r"\s", ch):
      continue
    chars.append(ch)
    idxs.append(t)
  flat = "".join(chars)
  k = flat.find(ns)
  return idxs[k] if k != -1 else -1


def split_embedded_mulams(paras, warnings):
  """Split avatArikA paras hiding a bare mUlam (no mUlam marker).

  Sometimes the mUlam follows its avatArikA in the same paragraph
  ("...तृडाधिक्यमाह । | यत्किचित्काले ... ॥ ८॥"). The mUlam start is
  located via a following TIkA's pratIka ("यत्किचित्काल इत्यादि").
  Returns (new_paras, pseudo_anchors) with pseudo_anchors as
  {para_index: local_number}; only fires when no anchor already
  carries that number.
  """
  anchored = set()
  for p in paras:
    if MULAM_START_RE.match(p):
      _, _, num, _ = split_mulam_para(p)
      if num is not None:
        anchored.add(num)
  final, pseudo = [], {}
  for i, p in enumerate(paras):
    m_mark = AVAT_MARK_RE.search(p)
    mend = list(VERSE_END_RE.finditer(p))
    if not (m_mark and mend) or DASHAKA_TITLE_RE.match(p):
      final.append(p)
      continue
    n = verse_end_num(mend[-1])
    if n is None or n in anchored:
      final.append(p)
      continue
    stems = []
    for q in paras[i + 1:i + 7]:
      qs = q.strip()
      m = PRATIKA_RE.match(qs)
      if m:
        stem = m.group(1).strip()
        if len(stem) >= 4:
          stems.append(stem)
        continue
      if FOOT_DEF_RE.match(qs) or is_hindi_para(qs) \
          or MULAM_START_RE.match(qs) \
          or (AVAT_MARK_RE.search(qs)
              and not DASHAKA_TITLE_RE.match(qs)):
        continue
      g = GLOSS_DASH_RE.match(qs)
      if g:
        stem = g.group(1).strip()
        if len(re.sub(r"\s+", "", stem)) >= 6:
          stems.append(stem)
    cut = None
    for stem in stems:
      pos = p.find(stem, m_mark.end() + 20)
      if pos == -1:
        pos = despace_find(p, m_mark.end() + 20, stem)
      if pos != -1:
        cut = pos
        break
    if cut is None:
      final.append(p)
      continue
    tail = p[cut:].strip()
    if len(tail) < 100 or AVAT_MARK_RE.search(tail):
      # Too short for a verse (a mere quote) or a second unit.
      final.append(p)
      continue
    final.append(p[:cut].strip())
    final.append(p[cut:].strip())
    pseudo[len(final) - 1] = n
    anchored.add(n)
    warnings.append("split avatArikA-embedded mUlam ||%s|| (pratIka '%s…')"
                    % (n, stems[0][:20] if stems else "?"))
  return final, pseudo


def substantial_content(paras):
  """Does this span hold real verse content (not just footnotes)?"""
  for p in paras:
    q = p.strip()
    if not q or FOOT_DEF_RE.match(q) or q.startswith("[[P"):
      continue
    if is_hindi_para(q):
      return True
    if classify_paragraph(q) == "sanskrit" and len(q) > 60:
      return True
  return False


def split_orphans(avat_paras, warnings):
  """Split extra avatArikA markers into orphan (anchorless) verses.

  Returns (own_avats, [orphan Verse, ...]). A second marker separated
  from the first by substantial content starts an anchorless verse;
  adjacent markers (double avatArikA) stay with one verse.
  """
  marks = [k for k, q in enumerate(avat_paras)
           if AVAT_MARK_RE.search(q) and not DASHAKA_TITLE_RE.match(q)]
  if len(marks) <= 1:
    return avat_paras, []
  bounds = marks + [len(avat_paras)]
  segments = []
  start = bounds[0]
  for m in bounds[1:-1]:
    if substantial_content(avat_paras[start:m]):
      segments.append((start, m))
      start = m
  segments.append((start, bounds[-1]))
  if len(segments) == 1:
    return avat_paras, []
  orphans = []
  for s, e in segments[:-1]:
    o = Verse()
    first = strip_avat_mark(avat_paras[s])
    if first and not GATHA_LABEL_ONLY_RE.match(first):
      o.avat.append(first)
    o._comm_raw = list(avat_paras[s + 1:e])
    orphans.append(o)
    warnings.append("anchorless verse unit split at avatArikA")
  return avat_paras[segments[-1][0]:segments[-1][1]], orphans


def parse_chunk(paras, pseudo=None, warnings=None):
  """Parse one dashaka chunk -> (intro_paras, [Verse], None).

  Verse spans are anchored on mUlam markers (plus pseudo-anchors from
  split_embedded_mulams); each verse's avatArikA is searched backwards
  from its mUlam so consecutive verses never overlap. Commentary stays
  raw here; recover_chunk() classifies it after mUlam completion /
  bare-mUlam promotion.
  """
  anchors = []
  for i, p in enumerate(paras):
    if MULAM_START_RE.match(p):
      head, tail, num, mangled = split_mulam_para(p)
      anchors.append({"idx": i, "head": head, "tail": tail, "num": num,
                      "mangled": mangled, "bare": False})
  if pseudo:
    for idx, num in sorted(pseudo.items()):
      head, tail, _, _ = split_mulam_para(paras[idx])
      anchors.append({"idx": idx, "head": head, "tail": tail, "num": num,
                      "mangled": False, "bare": True})
    anchors.sort(key=lambda a: a["idx"])
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
    verse._had_num = a["num"] is not None
    verse._mangled = a["mangled"]
    verse._anchor_idx = a["idx"]
    verse._has_avat = av_idx[v] is not None
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
    own_avats, orphans = split_orphans(avat_paras, warnings or [])
    sort_avats(own_avats, verse.avat, verse.pre_hindi)
    verse._comm_raw = ([a["tail"]] if a["tail"] else []) + \
      paras[a["idx"] + 1:comm_end[v]]
    verse._orphans = orphans
    for o in verse._orphans:
      verses.append(o)
    verses.append(verse)
    verse._orphans = []
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
  verse._corrected_from = 6
  verse.mulam = (verse.mulam + " " + MUDRITA_NOTE).strip()
  where = ("set %d " % set_no) if set_no else ""
  warnings.append("%sverse 9 printed as ||6||; heading corrected" % where)


def verse_has_hindi_ending(verse, num):
  """Does the verse hold a Hindi para trailing with ||num||?

  Scans classified pre-mUlam Hindi plus Hindi-looking commentary paras
  (completion/diversion has not run yet at correction time).
  """
  for p in verse.pre_hindi:
    ms = list(VERSE_END_RE.finditer(p.strip()))
    if ms and ms[-1].end() >= len(p.strip()) - 2 \
        and verse_end_num(ms[-1]) == num:
      return True
  for p in verse._comm_raw:
    q = p.strip()
    if not is_hindi_para(q):
      continue
    ms = list(VERSE_END_RE.finditer(q))
    if ms and ms[-1].end() >= len(q) - 2 \
        and verse_end_num(ms[-1]) == num:
      return True
  return False


def correct_print_number(verse, printed, expected, warnings, set_no=None):
  """Renumber an avatArikA-backed verse by position (backward print only).

  Fires only when the printed number is BACKWARD (printed < expected):
  the earlier slot is taken, so this unit must be the positional verse
  (e.g. 04 set 4: avatArikA-backed units printing ||4||/||6|| at slots
  8/9, with solid true-4/true-6 units earlier). Forward jumps
  (printed > expected) mean genuinely missing verses: warn only.
  """
  verse.local = expected
  verse._corrected_from = printed
  note = "<!-- mudrite ||%s|| -->" % arab_to_deva(printed)
  verse.mulam = (verse.mulam + " " + note).strip()
  where = ("set %s " % set_no) if set_no else ""
  warnings.append("%sverse %d printed as ||%s||; heading corrected by "
                  "position (verify content)" % (
                    where, expected, arab_to_deva(printed)))


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
  if re.search(r"।।\s*$", verse.mulam):
    # True end lost its number in print (bare-।। cut or numberless
    # anchor): nothing numbered may be glued on; take as-is.
    warnings.append("set %s verse %s: mUlam ends with numberless ।।; "
                    "taken as-is" % (set_no, expected))
    return
  pages, hindi_tmp, stray_tmp = [], [], []
  kept = []  # exegetical TIkA skipped over: preserved for commentary
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
    if EXEGETICAL_RE.search(q):
      # TIkA anvaya/restatement, never a mUlam ending: keep for comm.
      kept.append(p)
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
      if num is not None and num > 11:
        # Saṅgati/ratnAvalI śloka (e.g. "मुनिराह षष्ठे ॥ ४६ ॥"):
        # never our verse end; keep for commentary, keep scanning.
        kept.append(p)
        consumed += 1
        continue
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
  verse._comm_raw = kept + verse._comm_raw[consumed:]


def bare_mulam_match(q, expected):
  """Bare (marker-less) mUlam line ending with the expected number?"""
  q = re.sub(r"\s*(?:" + _ORD + r"(?:\s+या\s+" + _ORD + r")?\s+गा(?:था|या)"
             r"[\s:;.\-–—]*)$", "", q).strip()
  if not q or len(q) > 300:
    return False
  if MULAM_START_RE.match(q) or FOOT_DEF_RE.match(q):
    return False
  if EXEGETICAL_RE.search(q):
    return False  # TIkA anvaya/restatement, never a bare mUlam
  if q.startswith("भावार्थ") or re.match(r"^[+↑f†‡]\s+\S", q):
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


def split_restart_subchunks(paras, warnings):
  """Split a titled chunk further at verse-number restarts.

  Some dashakas lack their title line; their verses then merge into the
  previous chunk (..., 10, 11, 1, 2, ...). A restart to 1 (or 2, when
  ||1|| itself is lost) after 9+ starts a new sub-chunk at the
  restarted verse's avatArikA (or mUlam when unmarked).
  """
  anchors = []
  for i, p in enumerate(paras):
    if MULAM_START_RE.match(p):
      _, _, num, _ = split_mulam_para(p)
      anchors.append((i, num))
  if not anchors:
    return [(paras, None)]
  filled = []
  prev = None
  for _, num in anchors:
    if num is None:
      num = (prev + 1) if prev else 1
    filled.append(num)
    prev = num
  # Scan sequence with the systematic ९->६ confusion normalized (a 6
  # right after an 8 reads as 9): the tail-run check below then sees
  # through mislabeled verse-9s (08 सप्तम-chunk tail [5..8,6,10,11]).
  seq = list(filled)
  for k in range(1, len(seq)):
    if seq[k] == 6 and seq[k - 1] == 8:
      seq[k] = 9
  cuts = [0]
  for j in range(1, len(anchors)):
    if seq[j - 1] is not None and seq[j - 1] >= 9 \
        and seq[j] in (1, 2):
      cuts.append(j)
      warnings.append("number-restart split: new set at verse %d "
                      "(after ||%s||)" % (seq[j], seq[j - 1]))
      continue
    if seq[j - 1] is not None and seq[j - 1] >= 9 \
        and seq[j] is not None and 3 <= seq[j] < seq[j - 1]:
      # Lost title + lost opening verses (08 सप्तम-chunk tail
      # [5..11] with phala-verse end): split only when the restarted
      # run continues sequentially to 11.
      k = j
      while k + 1 < len(anchors) and seq[k + 1] == seq[k] + 1:
        k += 1
      if seq[k] == 11:
        cuts.append(j)
        warnings.append("tail split: verses %d..11 after ||%s|| "
                        "(missing title?)" % (seq[j], seq[j - 1]))
  if len(cuts) == 1:
    return [(paras, None)]
  sublists = []
  for g, c in enumerate(cuts):
    a0 = anchors[c][0]
    av = find_avat_idx(paras, (anchors[c - 1][0] + 1) if c > 0 else 0, a0)
    if g == 0:
      start = 0  # keep title + intro of the first group
    else:
      start = av if av is not None else a0
    if g + 1 < len(cuts):
      b0 = anchors[cuts[g + 1]][0]
      avb = find_avat_idx(paras, anchors[cuts[g + 1] - 1][0] + 1, b0)
      end = avb if avb is not None else b0
    else:
      end = len(paras)
    sub = paras[start:end]
    sublists.append((sub, None))
  return sublists


def recover_chunk(intro, verses, set_no, warnings):
  """Fill numbers, fix OCR ९->६, complete split mUlams, promote bare ones.

  Numbering is single-pass left-to-right so a corrected verse feeds the
  next verse's expectation (a filled number never poisons followers).
  """
  # 0. Demote false anchors: ṭīkā śloka-quotes introduced by "मूलम् -".
  # Genuine mUlams never start with "(". A marker with nothing but a
  # gAthA label ("मूलम् - पंचमी गाथा", mUlam text lost; the label line
  # itself is dropped in cleanup, leaving a marker-only empty head) is
  # likewise hollow: the bare mUlam nearby (pseudo-anchor) is the real
  # verse. Anchors whose number already occurred AND which lack their
  # own avatArikA are likewise demoted
  # (duplicate/false prints); the first occurrence always stays.
  seen_numbers = set()
  i = 0
  while i < len(verses):
    v = verses[i]
    hollow = GATHA_LABEL_ONLY_RE.match(v.mulam.strip()) \
      or (v._anchor_idx >= 0 and not v.mulam.strip())
    if (v.mulam.startswith("(") or hollow) and i > 0:
      prev = verses[i - 1]
      prev._comm_raw.extend(v.avat + ([v.mulam] if v.mulam else [])
                            + v._comm_raw)
      prev.hindi.extend(v.pre_hindi)
      prev._stray_defs.extend(v._stray_defs)
      why = "hollow gAthA-label mUlam" if hollow else "quoted sloka"
      warnings.append("set %s verse %s: %s as mUlam; demoted "
                      "to commentary" % (set_no, v.local, why))
      del verses[i]
      continue
    i += 1
  # 1. Fill + sequential 6 -> 9 correction in one pass. Filled numbers
  # from any earlier pass are reset first so corrected values feed on.
  # AvatArikA-backed verses printing a BACKWARD number take their
  # positional slot (forward jumps = genuinely missing verses: warn).
  printed = {v.local for v in verses if v._had_num}
  prev = None
  for verse in verses:
    if not verse._had_num:
      verse.local = None
    if verse.local is None:
      verse.local = (prev + 1) if prev else 1
    exp = (prev + 1) if prev is not None else verse.local
    if verse.local == 6 and exp == 9:
      correct_six_to_nine(verse, warnings, set_no)
    elif prev is not None and verse.local != exp and verse.local < exp \
        and verse._has_avat and exp <= 11 and exp not in printed:
      correct_print_number(verse, verse.local, exp, warnings, set_no)
    elif prev is not None and verse.local != exp and verse.local > exp \
        and verse._has_avat and exp <= 11 and exp not in printed \
        and verse_has_hindi_ending(verse, exp):
      # Forward print (02 -> 04) corroborated by the verse's own Hindi
      # ending with the positional number: same mislabel, correct it
      # (05 set 7: units printing ||4||/||5|| holding Hindi ||2||/||3||).
      correct_print_number(verse, verse.local, exp, warnings, set_no)
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
      # No avatArikA evidence (likely a TIkA anvaya restatement):
      # leave the candidate in commentary instead of promoting.
      warnings.append("set %s: possible bare mUlam ||%s|| without "
                      "avatArikA; left in TIkA" % (set_no, exp_next))
      i += 1
      continue
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
    if not m or not m.group(2).strip():
      return False
    return bool(len(s) < 300
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
  out.append("<details open><summary>मूलम् - %s</summary>" % loc_deva)
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
        if v._corrected_from is not None and n == v._corrected_from:
          continue  # same print mislabel as the corrected mUlam; keep
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
  # Frontmatter always stays on top verbatim.
  fm = re.match(r"\+\+\+\n.*?\n\+\+\+\n?", text, re.S)
  frontmatter = fm.group(0) if fm else ""
  text = text[len(frontmatter):]
  # Preamble = already-formatted verses 1-9, cut at the dotted separator.
  dot = re.search(r"(?m)^\.+$\n?", text)
  if dot and "<details" in text[:dot.start()]:
    preamble, raw = text[:dot.start()], text[dot.end():]
  else:
    preamble, raw = "", text
  parts = [frontmatter.rstrip()] if frontmatter.strip() else []
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
  chunks = re.split(CHUNK_SPLIT_RE, raw)
  chunks = [c for c in chunks if c.strip()]
  all_sets = []
  for chunk in chunks:
    paras = assemble_paragraphs(clean_lines(chunk))
    for sub, _sub_pseudo in split_restart_subchunks(paras, warnings):
      sub, pseudo = split_embedded_mulams(sub, warnings)
      intro, verses, _ = parse_chunk(sub, pseudo, warnings)
      if not verses:
        # Pure extra material (verseless header chunk): keep as plain.
        all_sets.append((None, [], [], sub))
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
