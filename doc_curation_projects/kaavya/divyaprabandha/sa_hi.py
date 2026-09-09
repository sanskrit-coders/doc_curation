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

_HINDI_WORDS = (
  "है|हैं|था|थी|थे|होगा|होगी|जायेंगे|में|ने|को|से|द्वारा|लिये|"
  "गया|गयी|गये|हुआ|हुई|हुए|रहा|रही|रहे|किया|किये|कहा|कहते|"
  "बताया|बताते|नहीं|कैसे|क्या|यह|वह|ये|वे|इस|उस|इन|उन|जिन|"
  "अपनी|अपने|हम|तुम|आप|लोग|वाला|वाली|वाले|और|क्योंकि|लेकिन|"
  "यदि|जब|तब|यहाँ|वहाँ|होता|होती|होते|करना|करें|करो|लो|तो|भी|ही"
)
_SANSKRIT_WORDS = (
  "इति|इत्य|चेत्|ननु|अत्र|तत्र|यथा|कथम्|किम्|किमर्थम्|कुतः|तर्हि|"
  "यद्वा|अथवा|एवम्|एव|तद्|एतद्|अस्य|तस्य|एतस्य|भवति|भवेत्|"
  "उच्यते|आह|अवोचत्|अर्थः|इत्यर्थः|खलु|हि|तु|अपि|अस्ति|नास्ति"
)
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
  iti/ity/cet-type words mark Sanskrit. Ties with substance go to
  Hindi (Sanskrit TIkA almost never accumulates Hindi function words,
  while Hindi prose often embeds Sanskrit terms).
  """
  h, s = score_paragraph(text)
  if h >= 2 and h >= s:
    return "hindi"
  if s > h:
    return "sanskrit"
  if h == 1 and s == 0:
    return "hindi"
  if s >= 1:
    return "sanskrit"
  return "unknown"


# ---------------------------------------------------------------------------
# Structural patterns.
# ---------------------------------------------------------------------------

VERSE_END_RE = re.compile(
  r"(?:॥|\|{2}|\.\.|।{2})\s*([०-९0-9]+)\s*(?:॥|\|{2}|\.\.|।{2})")
MULAM_START_RE = re.compile(
  r"^\*?\*?\s*(?:मूलम्|मलम्)(?:\s*[-–—:]+\s*|\s+)")
AVAT_MARK_RE = re.compile(r"अवतारिका\*?\*?\s*[-–—:]+")
# Mid-line mUlam markers must start new lines, but only when the verse
# ending ``||n||`` follows on the same line (bare mentions of the mUlam
# in commentary have no such ending). Mid-line avatArikA markers only
# split after a daNDa (dashaka titles like "X-दशक - अवतारिका-" stay intact).
_MIDLINE_MULAM_RE = re.compile(
  r"\s*(?=\*?\*?(?:मूलम्|मलम्)\s*[-–—:][^\n]*?"
  r"(?:॥|\|{2}|\.\.|।{2})\s*[०-९0-9]+)")
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
  "►", "1", "4", "+", "|", ".", ":", "-", "_", "*", "**", "***", "......",
  "...........................................................",
  "..........................................................",
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
  m = None
  for m in VERSE_END_RE.finditer(s):
    pass
  if m is None:
    return False
  return m.end() >= len(s.strip()) - 2


def assemble_paragraphs(lines):
  """Join OCR lines into paragraphs.

  A new paragraph starts at structural markers and after verse endings;
  ``[[Pnn]]``-only lines terminate the current paragraph (page break at a
  paragraph boundary) while staying inline via the marker text.
  """
  paras = []
  buf = []

  def flush():
    if buf:
      paras.append("\n".join(buf).strip())
      buf.clear()

  for ln in lines:
    s = ln.strip()
    if not s:
      flush()
      continue
    if s.startswith("[[P") and re.fullmatch(r"\[\[P\d+\]\]", s):
      if buf:
        buf[-1] = buf[-1] + " " + s
      else:
        buf.append(s)
      flush()
      continue
    if is_starter_line(s):
      flush()
      buf.append(s)
      if FOOT_DEF_RE.match(s) or ends_with_verse(s):
        flush()
      continue
    buf.append(s)
    if ends_with_verse(s):
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
      expanded.extend(parts)
    else:
      parts2 = re.split(r"(?<=\S)\s+(?=[०-९0-9]+\s*[-–]\s)", ln)
      expanded.extend(parts2 if len(parts2) > 1 else [ln])
  return expanded


def extract_footnote_defs(paras):
  """Pull footnote-definition paragraphs out; return (paras, defs)."""
  defs = {}
  kept = []
  for p in paras:
    lines = split_multi_defs(p.split("\n"))
    if len(lines) == 1:
      m = FOOT_DEF_RE.match(p.strip())
      if m and len(p.strip()) < 300 and (
          FOOT_REF_KEYWORDS_RE.search(m.group(2)) or len(m.group(2)) < 80):
        key = deva_to_arab(m.group(1))
        if key in defs:
          i = 2
          while "%s_%d" % (key, i) in defs:
            i += 1
          key = "%s_%d" % (key, i)
        defs[key] = m.group(2).strip()
        continue
    kept.append(p)
  return kept, defs


def insert_footnote_refs(text, defs, prefix):
  defined = {k for k in defs if k.isdigit() and 1 <= int(k) <= 15}

  def repl(mo):
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
  paras, defs = extract_footnote_defs(paras)
  fid_defs = {"%s_%s" % (prefix, k): v for k, v in defs.items()}
  out = []
  emitted = set()
  for p in paras:
    p = insert_footnote_refs(p, defs, prefix)
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


def split_mulam_para(p):
  """(head_up_to_verse_end, tail, local_number_or_None)."""
  q = MULAM_START_RE.sub("", p).strip()
  ms = list(VERSE_END_RE.finditer(q))
  if not ms:
    return q, "", None
  m = ms[0]
  num = int(deva_to_arab(m.group(1)))
  return q[:m.end()].strip(), q[m.end():].strip(), num


def find_avat_idx(paras, start, end):
  for i in range(start, end):
    if AVAT_MARK_RE.search(paras[i]) \
        and not DASHAKA_TITLE_RE.match(paras[i]):
      return i
  return None


def strip_avat_mark(p):
  p = GATHA_PREFIX_RE.sub("", p).strip()
  p = re.sub(r"^\*?\*?अवतारिका\*?\*?\s*[-–—:]+\s*", "", p).strip()
  return p


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
  """Parse one dashaka chunk -> (intro_paras, [Verse], extras_paras).

  Verse spans are anchored on mUlam markers; each verse's avatArikA is
  searched backwards from its mUlam so consecutive verses never overlap.
  """
  anchors = []
  for i, p in enumerate(paras):
    if MULAM_START_RE.match(p):
      head, tail, num = split_mulam_para(p)
      anchors.append({"idx": i, "head": head, "tail": tail, "num": num})
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
  intro, verses, extras_all = [], [], []
  for v, a in enumerate(anchors):
    verse = Verse()
    verse.mulam = a["head"]
    verse.local = a["num"]
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
    for p in avat_paras:
      q = strip_avat_mark(p)
      if not q or GATHA_LABEL_ONLY_RE.match(q):
        continue
      if q.startswith("भावार्थ") or re.match(r"^\*?\*?भावार्थ", q):
        verse.pre_hindi.append(q)
      elif re.match(r"^[+↑f]\s+\S", q):
        verse.pre_hindi.append(q)
      elif classify_paragraph(q) == "hindi":
        verse.pre_hindi.append(q)
      else:
        verse.avat.append(q)
    comm = ([a["tail"]] if a["tail"] else []) + paras[a["idx"] + 1:comm_end[v]]
    if v == len(anchors) - 1:
      # Trailing dashaka/shataka extras stay out of the TIkA.
      cut = next((j for j, p in enumerate(comm) if is_extra_start(p)), None)
      if cut is not None:
        extras_all = comm[cut:]
        comm = comm[:cut]
    for p in comm:
      q = p.strip()
      if not q or GATHA_LABEL_ONLY_RE.match(q):
        continue
      if q.startswith("भावार्थ") or re.match(r"^\*?\*?भावार्थ", q):
        verse.hindi.append(q)
      elif re.match(r"^[+↑f]\s+\S", q) and ("॥" in q or "।" in q or len(q) > 20):
        verse.hindi.append(q)
      elif classify_paragraph(q) == "hindi":
        verse.hindi.append(q)
      else:
        verse.tika.append(q)
    verses.append(verse)
  return intro, verses, extras_all


def fill_local_numbers(verses, start_hint=None):
  prev = start_hint
  for verse in verses:
    if verse.local is None:
      verse.local = (prev + 1) if prev else 1
    prev = verse.local


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
        rest = []
        for ln in lines:
          m = FOOT_DEF_RE.match(ln.strip())
          if m and is_def(ln):
            add(m, m.group(2).strip())
          elif ln.strip():
            rest.append(ln.strip())
        if rest:
          kept.append("\n".join(rest))
    cleaned.append(kept)
  return cleaned, defs


def render_verse(verse, set_ara, warnings):
  loc = verse.local
  loc_deva = arab_to_deva(loc)
  prefix = "%d_%d" % (set_ara, loc)
  [avat, mulam_l, tika, hindi], raw_defs = collect_verse_defs(
    [verse.avat, [verse.mulam] if verse.mulam else [],
     verse.tika, verse.pre_hindi + verse.hindi])
  fid_defs = {"%s_%s" % (prefix, k): v for k, v in raw_defs.items()}

  def render_list(paras):
    out, emitted = [], set()
    for p in paras:
      p = insert_footnote_refs(p, raw_defs, prefix)
      out.append(p)
      for r in re.findall(r"\[\^([^\]]+)\]", p):
        if r in fid_defs and r not in emitted:
          out.append("[^%s]: %s" % (r, fid_defs[r]))
          emitted.add(r)
    return "\n\n".join(out).strip()

  avat_md = render_list(avat)
  mulam_md = render_list(mulam_l)
  tika_md = render_list(tika)
  hindi_md = render_list(hindi)
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
  out.append("<details><summary>avatArikA - %s</summary>" % loc_deva)
  out.append("")
  out.append(avat_md if avat_md else missing)
  out.append("")
  out.append("</details>")
  out.append("<details open><summary>mUlam - %s</summary>" % loc_deva)
  out.append("")
  out.append(mulam_md if mulam_md else missing)
  out.append("")
  out.append("</details>")
  out.append("<details><summary>TIkA - %s</summary>" % loc_deva)
  out.append("")
  out.append(tika_md if tika_md else missing)
  out.append("")
  out.append("</details>")
  out.append("<details><summary>hindI - %s</summary>" % loc_deva)
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


def structure_file(in_path, out_path):
  warnings = []
  text = Path(in_path).read_text(encoding="utf-8")
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
    parts.append(preamble.rstrip())
    preamble_kept = True
    set_counter = 1
  else:
    set_counter = 0
  # Split the raw remainder into dashaka chunks at dashaka titles.
  chunks = re.split(r"(?m)(?=^[^\n]*दशक\s*-\s*अवतारिका)", raw)
  chunks = [c for c in chunks if c.strip()]
  for chunk in chunks:
    paras = assemble_paragraphs(clean_lines(chunk))
    intro, verses, extras = parse_chunk(paras)
    if not verses:
      # Pure extra material (should not normally happen).
      parts.append("\n\n".join(paras).strip())
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
