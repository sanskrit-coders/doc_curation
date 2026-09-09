"""Add Taittiriya pada-pATha details underneath each mUla detail.

Typical usage::

    from doc_curation_projects.veda.yajuH.taittiriiyam.padapaaTha import add_pada
    add_pada("/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH/1/8_rAjasUyAdi/11_abhiShekArthajalagrahaNAdi.md")

    # Batch over a directory (apply_function passes each file path):
    from doc_curation.md import library
    library.apply_function(fn=add_pada, dir_path=".../sarva-prastutiH/1/8_rAjasUyAdi", dry_run=True)

The function:

* infers the pada file ``.../padapAThaH/saMhitA/<kANDa>/<prapAThaka>.md``
  from the ``sarva-prastutiH/<kANDa>/<prapAThaka>_...`` part of ``file_in``,
* extracts top-level ``<details><summary>mUlam</summary>`` blocks
  (blocks inside ``div.js_include`` are *not* edited here - the static
  target they point to is edited instead, recursively),
* extracts in-div ``mUla`` blocks (expanded ``js_include`` prefills) and
  adds the pada-pATha there in place as well,
* aligns each mUla sequence to the pada token sequence using text
  similarity + sequence order (DP, free prefix/suffix, contiguous cover),
* inserts ``<details><summary>pada-pAThaH</summary>`` blocks.

Only standard library + ``regex`` + ``bs4`` + ``doc_curation`` are used.
"""

import difflib
import logging
import os
from functools import lru_cache

import regex
from bs4 import BeautifulSoup, NavigableString
from doc_curation.md import library

from doc_curation.md.file import MdFile

try:
  from doc_curation.md.content_processor import include_helper
except Exception:  # pragma: no cover
  include_helper = None

DEFAULT_PADA_BASE = "/home/vvasuki/gitland/sanskrit/raw_etexts_private/vedaH/taittirIyA/padapAThaH/saMhitA"
DEFAULT_HUGO_BASE = "/home/vvasuki/gitland/vishvAsa"

MULA_TITLE_RE = r"^\s*मूलम्.*$"
PADA_TITLE = "पद-पाठः"
PADA_TITLE_RE = r"^\s*पद[\s\-‐‑]*पाठः.*$"
ACCENTS_RE = r"[॒॑᳓᳙᳚ꣳꣴ]"


# ---------------------------------------------------------------------------
# pada -> saMhita fragment (copied from padapaaTha.get_padasvara + bugfixes)
# ---------------------------------------------------------------------------

def strip_iti(text):
  """Strip ``iti ...`` glosses from a single padapATha token."""
  text = regex.sub('ख्ष', 'क्ष', text)
  text = regex.sub('थ्स', 'त्स', text)
  text = regex.sub('ऱ्', 'र्', text)
  text = regex.sub('ꣴ', 'ं', text)
  text = regex.sub(' इत.*ः', 'ः', text)
  text = regex.sub('॒ इत.*ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]ꣳ', 'ं', text)
  text = regex.sub('ेति[॒॑] .+ा([॒॑]?)$', 'ा\\1', text)
  text = regex.sub('ेति[॒॑] .+([॒॑]?)$', '\\1', text)
  text = regex.sub('ेत्य[॒॑]?.+?([॒॑]?)$', '\\1', text)
  text = regex.sub('ेती[॒॑]?.+?([॒॑]?)$', '\\1', text)
  text = regex.sub('ीति[॒॑] .+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('ीत्य[॒॑]?.+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('ीति[॒॑] .+ि([॒॑]?)$', 'ि\\1', text)
  text = regex.sub('ीत्य[॒॑]?.+ि([॒॑]?)$', 'ि\\1', text)
  text = regex.sub('ा[॒॑]? इत.+ै([॒॑]?)$', 'ै\\1', text)
  text = regex.sub('ी[॒॑]? इत.+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('[॒॑]?दिति[॒॑] .+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?दि[॒॑]?त्य[॒॑]?.+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?दि[॒॑]?ती[॒॑]?.+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?मिति[॒॑] .+?([॑]?)म्$', '\\1म्', text)
  text = regex.sub('[॒॑]?मिति[॒॑] .+?([॑])म्$', '\\1म्', text)
  text = regex.sub('[॒॑]?रिति[॒॑] .+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]?रि[॒॑]?त्य[॒॑]?.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]?रि[॒॑]?ती[॒॑]?.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]? इ[॒॑]?त.+े([॒॑]?)$', 'े\\1', text)
  text = regex.sub('[॒॑]? इत.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub(' इ॑त.*ः([॒॑]?)', 'ः\\1', text)
  text = regex.sub('्([॒॑])', '्', text)
  text = regex.sub('न्न्([॒॑]?)', 'न्', text)
  # standalone upasarga-pada "निरिति" (= निर्, from निस्) carries no "iti X" gloss
  text = regex.sub('^निरिति([॒॑]?)$', 'निर्\\1', text)
  text = regex.sub('ं॒ ‌', 'ं', text)
  text = regex.sub(' इति॑$', '', text)
  # "X इति" without visarga/gloss: the iti is a padapATha marker, X is the word
  # (e.g. मो इति -> मो). Bare इति ("thus") has no space: untouched.
  text = regex.sub('^(.+) इति$', '\\1', text)
  # fused "Xu + iti" without gloss (अन्विति -> अनु, स्विति -> सु);
  # glossed forms (पृत्स्विति पृत्-सु) end otherwise: untouched.
  text = regex.sub('^(\\S+)्विति([॒॑]?)$', '\\1ु\\2', text)
  text = regex.sub(r'\(३\)', '', text)
  text = regex.sub('ꣳ', 'ँ', text)
  text = regex.sub('([॒॑]?)न्निति[॒॑] .+([॒॑]?)न्', '\\1न्', text)
  text = regex.sub('नि[॒॑]?ति[॒॑]? .*([॒॑]?)न्', 'न्', text)
  text = regex.sub('नि[॒॑]?ती[॒॑]? .*([॒॑]?)न्', 'न्', text)
  text = regex.sub('नि[॒॑]?त्य[॒॒]?.*([॒॑]?)न्', 'न्', text)
  text = regex.sub('मि[॒॑]?ति[॒॑]? .*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('मि[॒॑]?त्य[॒॑]?.*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('मि[॒॑]?ती[॒॑]?.*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('ङि[॒॑]?ति[॒॑]? .*?([॒॑]?)ङ्$', '\\1ङ्', text)
  text = regex.sub('्विति[॒॑] .*ु([॒॑]?)$', 'ु\\1', text)
  text = regex.sub('्वि[॒॑]?त्य[॒॑]?.*ु([॒॑]?)$', 'ु\\1', text)
  text = regex.sub('॒विति॑ .*ो([॒॑]?)$', 'ो\\1', text)
  text = regex.sub('ा[॒॑]?विति[॒॑] .+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?वित्य[॒॑]?.+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?वि[॒॑]?ती[॒॑]?.+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?यिति[॒॑] .+ै([॒॑]?)$', 'ै\\1', text)
  text = regex.sub('[॒॑]?गिति[॒॑] .*?([॒॑]?)क्$', '\\1क्', text)
  text = regex.sub('[॒॑]?डिति[॒॑] .*?([॒॑]?)ट्$', '\\1ट्', text)
  text = regex.sub('ू[॒॑]? इत.*ू([॒॑]?)$', 'ू\\1', text)
  text = regex.sub('ो[॒॑]? इ[॒॑]?त.*ो([॒॒]?)$', 'ो\\1', text)
  return text


def drop_elided_inserts(text):
  """Drop bracketed/parenthesized chunks, keep within-mantra repetitions.

  Chunks whose content does NOT occur unbracketed elsewhere in the same
  text are elisions, glosses or markers (``[ये देवाः]``, ``[रक्षोहण...]``,
  ``(+++)``, ``[8]``) and are dropped with content. Chunks whose content
  DOES occur unbracketed (e.g. repeated ``[रक्षोघ्ने स्वाहा]``) are expanded.
  """
  for _ in range(2):
    for pat in (r"\([^()]*\)", r"\[[^\[\]]*\]"):
      def _decide(m, _text=text):
        inner = m.group(0)[1:-1]
        inner_norm = normalize_for_match(inner, drop_inserts=False)
        if not inner_norm:
          return ""
        rest = _text[:m.start()] + " " + _text[m.end():]
        rest_bare = regex.sub(r"\([^()]*\)", "", regex.sub(r"\[[^\[\]]*\]", "", rest))
        if inner_norm in normalize_for_match(rest_bare, drop_inserts=False):
          return inner
        return ""
      text, _ = regex.subn(pat, _decide, text)
  text = regex.sub(r"[\[\]\(\)]", "", text)
  return text


def normalize_for_match(text, is_pada=False, drop_inserts=True):
  """Light normalization for fuzzy matching.

  * pada tokens first go through :func:`strip_iti`,
  * markup / glosses / punctuation / labels are removed, bracketed and
    parenthesized inserts via :func:`drop_elided_inserts`,
  * accents + visarga are removed (visarga assimilates to s/r in saMhita,
    so dropping it makes ``पतिः + असि`` comparable to ``पतिरसि``).
  """
  if is_pada:
    text = strip_iti(text)
  text = regex.sub(r"\*\*", "", text)
  text = regex.sub(r"\+\+\+.*?\+\+\+", "", text)
  # stray "+" is markup cruft (e.g. "[8] +न"); "व्ँ" is this corpus's
  # anusvara glyph (सव्ँवत्सर = संवत्सर)
  text = regex.sub(r"\+", "", text)
  text = regex.sub("\u0935\u094d([ँं])", r"\1", text)
  text = drop_elided_inserts(text)
  text = regex.sub(r"[।॥]", "", text)
  # labels like 1A, anuvaka markers [20], punctuation
  text = regex.sub(r"[0-9०-९A-Z]", "", text)
  text = regex.sub(r"[\s\u200b\-\–\—\ऽ\/\.,;:|]+", "", text)
  text = regex.sub(ACCENTS_RE, "", text)
  text = text.replace("ः", "")
  return text


def _skeleton_class():
  mapping = {}
  # Same place of articulation; voicing/aspiration/nasal-place/sibilant-place
  # are what external sandhi alters (t<->d, m<->n, s<->sh, ...). Vowels,
  # visarga-reflexes (र्/स्/ो/∅) and lengths are abstracted away here;
  # the full-string score below keeps lexical precision.
  for group, rep in [('कखगघ', 'क'), ('चछजझ', 'च'),
                     ('टठडढ', 'ट'), ('तथदध', 'त'),
                     ('पफबभ', 'प'),
                     ('ङञणनमंँᳶ', 'न'),
                     ('शषस', 'स')]:
    for ch in group:
      mapping[ch] = rep
  return mapping

_SKELETON_MAP = _skeleton_class()


@lru_cache(maxsize=65536)
def consonant_skeleton(s):
  """Consonant place-skeleton of a normalized string (vowels dropped)."""
  out = []
  for ch in s:
    mapped = _SKELETON_MAP.get(ch)
    if mapped is not None:
      out.append(mapped)
    elif 'क' <= ch <= 'ह':
      out.append(ch)
  return ''.join(out)


def similarity(a, b):
  if not a or not b:
    return 0.0
  full = difflib.SequenceMatcher(None, a, b).ratio()
  sk = difflib.SequenceMatcher(
      None, consonant_skeleton(a), consonant_skeleton(b)).ratio()
  return max(full, sk)


# ---------------------------------------------------------------------------
# pada file parsing
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def parse_pada_file(pada_path):
  """Parse a padapATha saMhitA file into ordered tokens.

  Each token is a dict with ``raw`` (original, with accents),
  ``delim`` (``।`` or ``॥``), ``label`` (e.g. ``1A`` or ``None``,
  only set on the first token of a label block), ``anuvaka``
  (e.g. ``20``) and ``norm`` (normalized, iti-stripped).
  """
  with open(pada_path, encoding="utf-8") as f:
    lines = [x.strip() for x in f.read().splitlines() if x.strip()]
  tokens = []
  for line in lines:
    anuvaka = ""
    m = regex.search(r"\[(\d+)\]\s*$", line)
    if m:
      anuvaka = m.group(1)
      body = regex.sub(r"\[\d+\]\s*$", "", line).strip()
    else:
      body = line
    # find label blocks: "<num><letters?> ।"
    label_matches = list(regex.finditer(r"(?:^|\s)(\d+[A-Z]*)\s*।", body))
    if not label_matches:
      blocks = [(None, body)]
    else:
      blocks = []
      for idx, lm in enumerate(label_matches):
        label = lm.group(1)
        start = lm.end()
        end = label_matches[idx + 1].start() if idx + 1 < len(label_matches) else len(body)
        blocks.append((label, body[start:end]))
    for label, block in blocks:
      # token + delimiter pairs
      first = True
      for tm in regex.finditer(r"([^।॥]+)([।॥]+)", block):
        raw = tm.group(1).strip()
        delim_raw = tm.group(2).strip()
        delim = "॥" if "॥" in delim_raw else "।"
        if not raw:
          continue
        tokens.append({
          "raw": raw,
          "delim": delim,
          "label": label if first else None,
          "anuvaka": anuvaka,
          "norm": normalize_for_match(raw, is_pada=True),
        })
        first = False
  return tokens


def infer_pada_file(file_in, pada_base=DEFAULT_PADA_BASE):
  """Infer ``.../saMhitA/<kANDa>/<prapAThaka>.md`` from a sarva-prastuti path."""
  m = regex.search(r"sarva-prastutiH/(\d+)/(\d+)[^/]*", str(file_in))
  if m is None:
    # static mantra files mirror the same <kANDa>/<prapAThaka>_* layout
    m = regex.search(r"saMhitA/(?:yajuH|Rk)/[^/]+/(\d+)/(\d+)", str(file_in))
  if not m:
    raise ValueError(f"Cannot infer kANDa/prapAThaka from {file_in}")
  kanda, prapathaka = m.group(1), m.group(2)
  # prapathaka may have leading zero - pada files use plain ints ("8.md")
  pada_path = os.path.join(pada_base, kanda, f"{int(prapathaka)}.md")
  if not os.path.exists(pada_path):
    raise FileNotFoundError(f"pada file not found: {pada_path}")
  return pada_path


# ---------------------------------------------------------------------------
# mUla extraction
# ---------------------------------------------------------------------------

def _is_inside_include(tag):
  for parent in tag.parents:
    if getattr(parent, "get", None) is None:
      continue
    classes = parent.get("class", []) or []
    if "js_include" in classes:
      return True
  return False


def _nearest_include_url(tag):
  for parent in tag.parents:
    if getattr(parent, "get", None) is None:
      continue
    classes = parent.get("class", []) or []
    if "js_include" in classes and parent.get("url"):
      return parent.get("url")
  return None


def _detail_title(tag):
  summary = tag.find("summary")
  if summary is None:
    return ""
  return summary.get_text().strip()


def _has_pada_after(tag):
  """True if a pada-pATha detail already follows this mUla tag.

  Scans forward siblings until the next mUla tag (or end of parent).
  Any ``pada-pATha`` detail in that range counts, so re-running
  :func:`add_pada` never creates a duplicate - even if other details
  (Keith, TIkA, ...) were inserted between the mUla and its pada-pATha,
  or the title has variant spacing/hyphens.
  """
  sib = tag.next_sibling
  while sib is not None:
    if isinstance(sib, NavigableString):
      sib = sib.next_sibling
      continue
    if getattr(sib, "name", None) != "details":
      sib = sib.next_sibling
      continue
    title = _detail_title(sib)
    if regex.fullmatch(MULA_TITLE_RE, title):
      return False  # reached next mUla without seeing a pada-pATha
    if regex.fullmatch(PADA_TITLE_RE, title):
      return True
    sib = sib.next_sibling
  return False


def _mula_entry_from_tag(tag):
  """Build a mula entry dict from a ``<details><summary>mUlam`` tag."""
  texts = []
  for child in list(tag.children)[1:]:
    if isinstance(child, NavigableString):
      texts.append(str(child))
    else:
      texts.append(child.get_text(separator=" "))
  text = " ".join(texts).strip()
  return {
    "tag": tag,
    "text": text,
    "norm": normalize_for_match(text, is_pada=False),
    "already_has_pada": _has_pada_after(tag),
  }


def get_top_mulas(md_path):
  """Return (soup, metadata, content, mula_entries) for top-level mUlas.

  mula_entries: list of dicts ``tag``, ``text``, ``norm``,
  ``already_has_pada`` in document order. Entries inside
  ``div.js_include`` are excluded, as are ``मूलम् (संयुक्तम्)`` blocks
  (combined text - no pada-pATha is added there). Plain ``मूलम्`` and
  variants like ``मूलम् - ऋक्`` / ``मूलम् - यजुः`` /
  ``मूलम् - ब्राह्मणम्`` are processed.
  """
  md_file = MdFile(file_path=str(md_path))
  metadata, content = md_file.read()
  from doc_curation.md import content_processor
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:  # pragma: no cover
    soup = BeautifulSoup(f"<body>{content}</body>", "html.parser")
  entries = []
  for tag in soup.select("details"):
    summary = tag.find("summary")
    if summary is None:
      continue
    title = summary.get_text().strip()
    if not regex.fullmatch(MULA_TITLE_RE, title):
      continue
    if "संयुक्तम्" in title:
      continue
    if _is_inside_include(tag):
      continue
    entries.append(_mula_entry_from_tag(tag))
  return soup, metadata, content, entries


def get_div_mula_groups(soup):
  """Group in-div mUla entries by nearest enclosing ``div.js_include``.

  These are the expanded include prefills. Each group is a dict with
  ``div`` (the tag), ``url`` and ``entries`` (mula entry dicts as in
  :func:`get_top_mulas`, in document order). ``मूलम् (संयुक्तम्)`` blocks
  are excluded, like in :func:`get_top_mulas`.
  """
  groups = []
  index_by_div = {}
  for tag in soup.select("details"):
    summary = tag.find("summary")
    if summary is None:
      continue
    title = summary.get_text().strip()
    if not regex.fullmatch(MULA_TITLE_RE, title):
      continue
    if "संयुक्तम्" in title:
      continue
    div = None
    for parent in tag.parents:
      if getattr(parent, "get", None) is None:
        continue
      if "js_include" in (parent.get("class", []) or []):
        div = parent
        break
    if div is None:
      continue
    if id(div) not in index_by_div:
      index_by_div[id(div)] = len(groups)
      groups.append({"div": div, "url": div.get("url", ""), "entries": []})
    groups[index_by_div[id(div)]]["entries"].append(_mula_entry_from_tag(tag))
  return groups


def collect_include_targets(md_path, hugo_base=DEFAULT_HUGO_BASE):
  """Resolve ``div.js_include`` urls to local static .md files."""
  md_file = MdFile(file_path=str(md_path))
  metadata, content = md_file.read()
  from doc_curation.md import content_processor
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:  # pragma: no cover
    return []
  targets = []
  for div in soup.select("div.js_include"):
    url = div.get("url", "")
    if not url:
      continue
    if include_helper is None:
      continue
    try:
      path = include_helper.file_path_from_url(
        url=url, hugo_base_dir=hugo_base, current_file_path=str(md_path))
    except Exception as e:  # pragma: no cover
      logging.warning("Could not resolve %s: %s", url, e)
      continue
    if path is not None and os.path.exists(path) and path.endswith(".md"):
      if path not in targets:
        targets.append(path)
  return targets


# ---------------------------------------------------------------------------
# alignment (similarity + sequence)
# ---------------------------------------------------------------------------

def select_pada_window(mula_norms, pada_tokens, max_anuvakas=4, edge_margin=30):
  """Narrow the full pada token list to consecutive anuvakas.

  Order-aware prefilter: concatenate normalized mUlas (M) and normalized
  pada tokens (P), find longest common substrings via difflib (fast, C-ish
  for short M), and vote for anuvakas by matched character count.
  The returned window is padded by ``edge_margin`` tokens on each side:
  a mantra's span may start with the previous block's tail or end with the
  next block's head (e.g. anuvaka breaks mid-mantra).
  Returns (window_tokens, window_start_index).
  """
  import bisect
  from collections import Counter
  if not pada_tokens:
    return [], 0
  pada_norms = [t["norm"] for t in pada_tokens]
  # char offsets -> token index
  offsets = []
  pieces = []
  total = 0
  for n in pada_norms:
    offsets.append(total)
    pieces.append(n)
    total += len(n)
  p_concat = "".join(pieces)
  m_concat = "".join(mula_norms)
  if not m_concat or not p_concat:
    return pada_tokens, 0
  sm = difflib.SequenceMatcher(None, m_concat, p_concat, autojunk=False)
  votes = Counter()
  for a, b, size in sm.get_matching_blocks():
    if size < 3:
      continue
    # middle char of the block -> token -> anuvaka
    pos = b + size // 2
    ti = bisect.bisect_right(offsets, pos) - 1
    ti = max(0, min(ti, len(pada_tokens) - 1))
    votes[pada_tokens[ti].get("anuvaka", "")] += size
  if not votes:
    # fallback: whole file (DP has free prefix/suffix but would be slow;
    # cap to first max_anuvakas anuvakas to stay safe)
    logging.warning("No difflib votes; using whole pada file")
    return pada_tokens, 0
  vmax = max(votes.values())
  thresh = max(10, 0.15 * vmax)
  # anuvaka order as they appear in the file (numeric strings, but keep order)
  anu_order = []
  for t in pada_tokens:
    a = t.get("anuvaka", "")
    if a not in anu_order:
      anu_order.append(a)
  # expand contiguously from the top-voted anuvaka (avoids far noise votes
  # forcing a huge min-max span).
  top = max(votes, key=lambda a: votes[a])
  top_idx = anu_order.index(top)
  lo = hi = top_idx
  while lo - 1 >= 0 and votes.get(anu_order[lo - 1], 0) >= thresh \
      and (hi - (lo - 1) + 1) <= max_anuvakas:
    lo -= 1
  while hi + 1 < len(anu_order) and votes.get(anu_order[hi + 1], 0) >= thresh \
      and ((hi + 1) - lo + 1) <= max_anuvakas:
    hi += 1
  window_anus = anu_order[lo:hi + 1]
  # token slice, padded so spans may reach into the previous block's tail
  # or the next block's head across anuvaka/block boundaries
  indices = [i for i, t in enumerate(pada_tokens) if t.get("anuvaka", "") in set(window_anus)]
  start, end = min(indices), max(indices) + 1
  logging.info("Selected pada anuvakas %s (votes %s)", window_anus,
               {a: votes[a] for a in window_anus})
  start = max(0, start - edge_margin)
  end = min(len(pada_tokens), end + edge_margin)
  return pada_tokens[start:end], start


def _no_div_between(a, b):
  """True if sibling tag b is reachable from a with no div.js_include between.

  Contiguous mUla blocks outside includes are sequential in padapATha
  order, so their spans must be gapless. Unreachable pairs (different
  parents) return False: gaps stay allowed (status quo ante).
  """
  sib = a.next_sibling
  while sib is not None and sib is not b:
    if getattr(sib, "name", None) is not None:
      if "js_include" in (sib.get("class", []) or []):
        return False
      try:
        nested = sib.find("div", class_="js_include")
      except Exception:
        nested = None
      if nested is not None:
        return False
    sib = sib.next_sibling
  return sib is b


def align_mulas_to_padas(mula_norms, pada_norms, max_span=30,
                         gap_open=0.15, gap_extend=0.001, sequential=None):
  """Align each mUla to a span of pada tokens (similarity + sequence).

  DP with free prefix/suffix and affine-penalized gaps: each mUla consumes
  1..max_span tokens; a skipped stretch (mantras living in ``div.js_include``
  targets, hence absent from this file's mUla list) costs ``gap_open`` once
  plus ``gap_extend`` per token. The affine form matters: one long skipped
  div-region must stay cheaper than one garbage mismatch (cost up to 1.0),
  while a zero-length gap costs nothing, so genuinely contiguous sequences
  are unaffected. Cost = 1 - similarity.

  Returns (spans, total_cost, gaps) where spans[i] = (start, end) and
  gaps[i] = number of skipped pada tokens just before spans[i].

  ``sequential[j]`` (j >= 1) forces a gapless transition from mula j-1 to
  mula j (contiguous blocks with no div between); None means gaps allowed
  everywhere (affine-penalized).
  """
  n, m = len(mula_norms), len(pada_norms)
  if n == 0 or m == 0:
    return [], float("inf"), []
  INF = 1e9
  from functools import lru_cache

  @lru_cache(maxsize=None)
  def span_cost(i, k, j):
    concat = "".join(pada_norms[k:j])
    return 1.0 - similarity(mula_norms[i], concat)

  dp = [[INF] * (m + 1) for _ in range(n + 1)]
  par_k = [[None] * (m + 1) for _ in range(n + 1)]  # start of span
  par_prev = [[None] * (m + 1) for _ in range(n + 1)]  # end of prev span
  for j in range(m + 1):
    dp[0][j] = 0.0  # free prefix
  if sequential is None:
    sequential = [False] * n
  for i in range(1, n + 1):
    # best_prev[k] = min(dp[i-1][k], min_{k'<k} dp[i-1][k'] + open + extend*(k-k'))
    best_prev_val = [INF] * (m + 1)
    best_prev_arg = [0] * (m + 1)
    if i > 1 and sequential[i - 1]:
      # contiguous blocks with no div between: hard gapless transition
      for k in range(m + 1):
        best_prev_val[k] = dp[i - 1][k]
        best_prev_arg[k] = k
    else:
      run_val, run_arg = INF, 0  # running min of (dp[i-1][k'] - extend*k')
      for k in range(m + 1):
        best_v, best_a = dp[i - 1][k], k
        if run_val < INF:
          cand = gap_open + gap_extend * k + run_val
          if cand < best_v:
            best_v, best_a = cand, run_arg
        best_prev_val[k] = best_v
        best_prev_arg[k] = best_a
        v = dp[i - 1][k] - gap_extend * k
        if v < run_val:
          run_val, run_arg = v, k
    for j in range(1, m + 1):
      best, bk, bp = INF, None, None
      for k in range(max(0, j - max_span), j):
        if best_prev_val[k] >= INF:
          continue
        if k < (i - 1) * 1:
          continue
        c = span_cost(i - 1, k, j)
        tot = best_prev_val[k] + c
        if tot < best:
          best, bk, bp = tot, k, best_prev_arg[k]
      dp[i][j] = best
      par_k[i][j] = bk
      par_prev[i][j] = bp
  best_end = min(range(n, m + 1), key=lambda j: dp[n][j])
  spans, gaps = [], []
  j = best_end
  for i in range(n, 0, -1):
    k = par_k[i][j]
    prev = par_prev[i][j]
    if k is None:  # pragma: no cover
      raise RuntimeError("No feasible pada alignment (try larger max_span)")
    spans.append((k, j))
    gaps.append(k - (prev if prev is not None else k))
    j = prev
  spans = list(reversed(spans))
  gaps = list(reversed(gaps))
  return spans, dp[n][best_end], gaps


def build_pada_text(span_tokens):
  """Build ``1A । ... । ... ।`` display string for a span."""
  if not span_tokens:
    return ""
  parts = []
  first = span_tokens[0]
  if first.get("label"):
    parts.append(f"{first['label']} ।")
  for t in span_tokens:
    # inner label boundaries inside a span should not normally happen
    # (spans respect contiguity, may cross labels for multi-anuvaka files);
    # surface them if they occur mid-span.
    if t is not first and t.get("label"):
      parts.append(f"{t['label']} ।")
    parts.append(f"{t['raw']} {t['delim']}")
  return " ".join(parts).strip()


# ---------------------------------------------------------------------------
# file processing
# ---------------------------------------------------------------------------

def mula_head_token(text):
  """First whitespace-separated token of markup-cleaned mUla text."""
  text = regex.sub(r"\+\+\+.*?\+\+\+", "", text)
  text = drop_elided_inserts(text)
  text = regex.sub(r"[।॥]", " ", text)
  text = regex.sub(r"[0-9०-९A-Z]", "", text)
  text = regex.sub(r"[\u200b\-\u2013\u2014\/\.,;:|\+]+", " ", text)
  parts = text.split()
  return parts[0] if parts else ""


def leading_carryover(entry_text, span_concat_norm):
  """Return "X । " prefix if the mUla starts with a short particle missing
  from the span head (padapATha source has no token for it, e.g. leading
  \u0906 in "\u0906 \u0928 \u090f\u0924\u0941"), else ''. Conservative: only fires for
  head tokens of ≤2 chars whose norm is not already the span start.
  """
  if not span_concat_norm:
    return ""
  head = mula_head_token(entry_text)
  head_norm = normalize_for_match(head)
  if not head_norm or len(head_norm) > 2:
    return ""
  if span_concat_norm.startswith(head_norm):
    return ""
  logging.warning("  carrying over leading particle %r absent from pada span", head)
  return "%s । " % head


def _group_pada_tokens(group, md_path, fallback_tokens, hugo_base):
  """Pada tokens for a div group: inferred from the div's target file.

  An include block mirrors its target static file, so its mantras are
  matched against the target's own kANDa/prapAThaka pada source (the
  corresponding pada-pATha), not the container's. Falls back to the
  container tokens when the target is unresolvable or out of scope.
  """
  url = (group.get("url") or "").strip()
  if url and include_helper is not None:
    try:
      target = include_helper.file_path_from_url(
          url=url, hugo_base_dir=hugo_base, current_file_path=str(md_path))
      pada_file = infer_pada_file(target) if target else None
    except (ValueError, FileNotFoundError) as e:
      logging.info("Div %s: using container pada (%s)", url, e)
      pada_file = None
    except Exception as e:  # pragma: no cover
      logging.warning("Div %s: include resolution failed: %s", url, e)
      pada_file = None
    if pada_file is not None:
      logging.info("Div %s: matching against %s", url, pada_file)
      return parse_pada_file(pada_file)
  return fallback_tokens


def process_single_file(md_path, pada_tokens, dry_run=False, max_span=30,
                        min_avg_sim=0.55, hugo_base=DEFAULT_HUGO_BASE):
  """Add pada details to mUlas of one file (top-level + in-div). Returns num inserted."""
  soup, metadata, content, mulas = get_top_mulas(md_path)
  div_groups = get_div_mula_groups(soup)
  if not mulas and not div_groups:
    logging.info("No mUlam in %s", md_path)
    return 0
  empties = [m for m in mulas if not m["norm"]]
  for m in empties:
    logging.warning("Skipping mUla with empty text after cleanup: %r", m["text"][:60])
  mulas = [m for m in mulas if m["norm"]]
  inserted = 0
  if mulas:
    mula_norms = [x["norm"] for x in mulas]
    # Contiguous blocks (no div between) must map to gapless spans.
    sequential = [False] + [_no_div_between(mulas[i - 1]["tag"], mulas[i]["tag"])
                            for i in range(1, len(mulas))]
    # Two-stage: cheap bigram window selection, then exact DP inside window.
    window_tokens, window_start = select_pada_window(mula_norms, pada_tokens,
                                                       edge_margin=max_span)
    if not window_tokens:
      logging.warning("Empty pada window for %s", md_path)
      return 0
    window_norms = [t["norm"] for t in window_tokens]
    spans, total_cost, gaps = align_mulas_to_padas(mula_norms, window_norms, max_span=max_span,
                                                   sequential=sequential)
    sims = []
    for idx, (a, b) in enumerate(spans):
      concat = "".join(window_norms[a:b])
      sims.append(similarity(mula_norms[idx], concat))
    avg_sim = sum(sims) / len(sims) if sims else 0.0
    n_gaps = sum(1 for g in gaps if g > 0)
    logging.info("Aligned %d mUlas in %s (window %d tokens @%d, avg_sim=%.3f, gaps=%d)",
                 len(mulas), md_path, len(window_tokens), window_start, avg_sim, n_gaps)
    for idx, s in enumerate(sims):
      extra = f" (+{gaps[idx]} skipped before)" if gaps[idx] else ""
      if s < 0.5:
        logging.warning("  low match [%d] sim=%.3f%s mUla=%r pada=%r", idx, s, extra,
                        mulas[idx]["text"][:60],
                        " + ".join(t["raw"][:30] for t in window_tokens[spans[idx][0]:spans[idx][1]])[:120])
      elif gaps[idx] > 0:
        logging.info("  match [%d] sim=%.3f%s mUla=%r", idx, s, extra,
                     mulas[idx]["text"][:60])
    if avg_sim < min_avg_sim:
      logging.warning("Skipping %s: avg similarity %.3f < %.2f", md_path, avg_sim, min_avg_sim)
      return 0
    for entry, (a, b), s in zip(mulas, spans, sims):
      # Re-check right before inserting: get_top_mulas() ran before alignment,
      # so re-verify on the live soup to guarantee no duplicate is created.
      if entry["already_has_pada"] or _has_pada_after(entry["tag"]):
        if not entry["already_has_pada"]:
          logging.info("Skipping %r: pada-pATha already present", entry["text"][:40])
        continue
      if s < 0.5:
        # Safety net: a low-similarity match is never written, even if the
        # file-level average looked fine (one garbage span can hide in it).
        logging.warning("  skipping low match sim=%.3f mUla=%r pada=%r", s,
                        entry["text"][:60],
                        " + ".join(t["raw"][:30] for t in window_tokens[a:b])[:120])
        continue
      span_tokens = window_tokens[a:b]
      pada_text = leading_carryover(entry["text"], "".join(window_norms[a:b])) + build_pada_text(span_tokens)
      if not pada_text:
        continue
      new_html = f"<details><summary>{PADA_TITLE}</summary>\n\n{pada_text}\n</details>"
      new_detail = BeautifulSoup(new_html, "html.parser").find("details")
      entry["tag"].insert_after(NavigableString("\n\n"))
      entry["tag"].insert_after(new_detail)
      entry["tag"].insert_after(NavigableString("\n\n"))
      inserted += 1
  # In-div mUlas (expanded js_include prefills): add pada-pATha in place too,
  # besides the included static file (handled by add_pada recursion).
  # Each enclosing div is aligned independently - a div prefill mirrors one
  # static file (usually 1-2 contiguous mantras).
  for group in div_groups:
    for e in group["entries"]:
      if not e["norm"]:
        logging.warning("Skipping in-div mUla with empty text after cleanup: %r", e["text"][:60])
    g_all = [e for e in group["entries"] if e["norm"]]
    if not g_all:
      continue
    # Same nearest-div group = contiguous blocks (nested divs hold other
    # streams and do not break contiguity): hard gapless throughout.
    # Already-done entries still participate as tiling anchors.
    g_norms = [e["norm"] for e in g_all]
    g_seq = [False] * len(g_all)
    g_tokens = _group_pada_tokens(group, md_path, pada_tokens, hugo_base)
    g_window, _ = select_pada_window(g_norms, g_tokens, edge_margin=max_span)
    if not g_window:
      continue
    g_wnorms = [t["norm"] for t in g_window]
    try:
      g_spans, _, _ = align_mulas_to_padas(g_norms, g_wnorms, max_span=max_span,
                                           sequential=g_seq)
    except RuntimeError as e:
      logging.warning("Skipping in-div mUlas in %s (%s): %s", md_path, group["url"], e)
      continue
    for entry, (a, b) in zip(g_all, g_spans):
      if entry["already_has_pada"] or _has_pada_after(entry["tag"]):
        continue
      s = similarity(entry["norm"], "".join(g_wnorms[a:b]))
      if s < 0.5:
        logging.warning("  in-div low match sim=%.3f mUla=%r pada=%r (in %s)",
                        s, entry["text"][:60],
                        " + ".join(t["raw"][:30] for t in g_window[a:b])[:120],
                        group["url"])
        continue
      pada_text = leading_carryover(entry["text"], "".join(g_wnorms[a:b])) + build_pada_text(g_window[a:b])
      if not pada_text:
        continue
      new_html = f"<details><summary>{PADA_TITLE}</summary>\n\n{pada_text}\n</details>"
      new_detail = BeautifulSoup(new_html, "html.parser").find("details")
      entry["tag"].insert_after(NavigableString("\n\n"))
      entry["tag"].insert_after(new_detail)
      entry["tag"].insert_after(NavigableString("\n\n"))
      inserted += 1
  if inserted and not dry_run:
    from doc_curation.md import content_processor
    new_content = content_processor._make_content_from_soup(soup=soup)
    new_content = new_content.replace("<div", "\n<div")
    MdFile(file_path=str(md_path)).replace_content_metadata(
      new_metadata=metadata, new_content=new_content)
  logging.info("Inserted %d pada details in %s", inserted, md_path)
  return inserted


def add_pada(file_in, pada_file=None, pada_base=DEFAULT_PADA_BASE,
             hugo_base=DEFAULT_HUGO_BASE, dry_run=False, max_span=30,
             _visited=None, _depth=0):
  """Add pada-pATha details for ``file_in`` + its static includes.

  :param file_in: content file path (str/Path) or MdFile, e.g.
    ``.../sarva-prastutiH/1/8_rAjasUyAdi/11_...md``. Accepts MdFile as well,
    so it can be used with ``library.apply_function(fn=add_pada, ...)``.
  :param pada_file: explicit pada source; inferred from ``file_in`` if None.
  :param dry_run: if True, only log matches, change nothing.
  :returns: dict with ``pada_file``, ``processed`` (per-file insert counts).
  """
  if _visited is None:
    _visited = set()
  if hasattr(file_in, "file_path"):
    file_in = file_in.file_path
  file_in = str(file_in)
  if file_in in _visited:
    return {"pada_file": pada_file, "processed": {}}
  _visited.add(file_in)
  if pada_file is None:
    pada_file = infer_pada_file(file_in, pada_base=pada_base)
  logging.info("pada source for %s: %s", file_in, pada_file)
  pada_tokens = parse_pada_file(pada_file)
  logging.info("Loaded %d pada tokens from %s", len(pada_tokens), pada_file)
  processed = {}
  processed[file_in] = process_single_file(file_in, pada_tokens, dry_run=dry_run,
                                           max_span=max_span, hugo_base=hugo_base)
  if _depth >= 2:
    return {"pada_file": pada_file, "processed": processed}
  for target in collect_include_targets(file_in, hugo_base=hugo_base):
    # Each static target resolves its OWN pada file (it may live in another
    # prapAThaka - e.g. 1/7 statics referenced from 1/8 files). Targets
    # outside Taittiriya-saMhita pada scope (Rk-shAkala, atharva, sUtra)
    # are skipped: their padas live elsewhere.
    if target in _visited:
      continue
    # NOTE: do NOT pre-mark _visited here - the recursive call marks
    # file_in itself; pre-marking would trip its already-visited guard
    # and silently skip the target.
    try:
      sub = add_pada(target, pada_base=pada_base, hugo_base=hugo_base,
                     dry_run=dry_run, max_span=max_span,
                     _visited=_visited, _depth=_depth + 1)
      processed.update(sub["processed"])
    except (ValueError, FileNotFoundError) as e:
      logging.info("Skipping %s: %s", target, e)
    except Exception as e:  # pragma: no cover
      logging.warning("Failed %s: %s", target, e)
      processed[target] = 0
  return {"pada_file": pada_file, "processed": processed}


def get_padasvara(text):
  text = regex.sub('ख्ष', 'क्ष', text)
  text = regex.sub('थ्स', 'त्स', text)
  text = regex.sub('ऱ्', 'र्', text)
  text = regex.sub('ꣴ', 'ं', text)
  text = regex.sub(' इत.*ः', 'ः', text)
  text = regex.sub('॒ इत.*ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]ꣳ', 'ं', text)
  text = regex.sub('ेति[॒॑] .+ा([॒॑]?)$', 'ा\\1', text)
  text = regex.sub('ेति[॒॑] .+([॒॑]?)$', '\\1', text)
  text = regex.sub('ेत्य[॒॑]?.+?([॒॑]?)$', '\\1', text)
  text = regex.sub('ेती[॒॑]?.+?([॒॑]?)$', '\\1', text)
  text = regex.sub('ीति[॒॑] .+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('ीत्य[॒॑]?.+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('ीति[॒॑] .+ि([॒॑]?)$', 'ि\\1', text)
  text = regex.sub('ीत्य[॒॑]?.+ि([॒॑]?)$', 'ि\\1', text)
  text = regex.sub('ा[॒॑]? इत.+ै([॒॑]?)$', 'ै\\1', text)
  text = regex.sub('ी[॒॑]? इत.+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('[॒॑]?दिति[॒॑] .+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?दि[॒॑]?त्य[॒॑]?.+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?दि[॒॑]?ती[॒॑]?.+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?मिति[॒॑] .+?([॑]?)म्$', '\\1म्', text)
  text = regex.sub('[॒॑]?मिति[॒॑] .+?([॑])म्$', '\\1म्', text)
  text = regex.sub('[॒॑]?रिति[॒॑] .+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]?रि[॒॑]?त्य[॒॑]?.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]?रि[॒॑]?ती[॒॑]?.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]? इ[॒॑]?त.+े([॒॑]?)$', 'े\\1', text)
  text = regex.sub('[॒॑]? इत.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub(' इ॑त.*ः([॒॑]?)', 'ः\\1', text)
  text = regex.sub('्([॒॑])', '्', text)
  text = regex.sub('न्न्([॒॑]?)', 'न्', text)
  text = regex.sub('ं॒ ‌', 'ं', text)
  text = regex.sub(' इति॑$', '<empty-string>', text)
  text = regex.sub(r'\(३\)', '<empty-string>', text)
  text = regex.sub('ꣳ', 'ँ', text)
  text = regex.sub('([॒॑]?)न्निति[॒॑] .+([॒॑]?)न्', '\\1न्', text)
  text = regex.sub('नि[॒॑]?ति[॒॑]? .*([॒॑]?)न्', 'न्', text)
  text = regex.sub('नि[॒॑]?ती[॒॑]? .*([॒॑]?)न्', 'न्', text)
  text = regex.sub('नि[॒॑]?त्य[॒॑]?.*([॒॑]?)न्', 'न्', text)
  text = regex.sub('मि[॒॑]?ति[॒॑]? .*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('मि[॒॑]?त्य[॒॑]?.*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('मि[॒॑]?ती[॒॑]?.*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('ङि[॒॑]?ति[॒॑]? .*?([॒॑]?)ङ्$', '\\1ङ्', text)
  text = regex.sub('्विति[॒॑] .*ु([॒॑]?)$', 'ु\\1', text)
  text = regex.sub('्वि[॒॑]?त्य[॒॑]?.*ु([॒॑]?)$', 'ु\\1', text)
  text = regex.sub('॒विति॑ .*ो([॒॑]?)$', 'ो\\1', text)
  text = regex.sub('ा[॒॑]?विति[॒॑] .+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?वित्य[॒॑]?.+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?वि[॒॑]?ती[॒॑]?.+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?यिति[॒॑] .+ै([॒॑]?)$', 'ै\\1', text)
  text = regex.sub('[॒॑]?गिति[॒॑] .*?([॒॑]?)क्$', '\\1क्', text)
  text = regex.sub('[॒॑]?गि[॒॑]?त्य[॒॑]?.*?([॒॑]?)क्$', '\\1क्', text)
  text = regex.sub('[॒॑]?डिति[॒॑] .*?([॒॑]?)ट्$', '\\1ट्', text)
  text = regex.sub('ू[॒॑]? इत.*ू([॒॑]?)$', 'ू\\1', text)
  text = regex.sub('ो[॒॑]? इ[॒॑]?त.*ो([॒॑]?)$', 'ो\\1', text)
  return text


if __name__ == '__main__':
  pass
  # add_pada(file_in="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH/1/8_rAjasUyAdi/11_abhiShekArthajalagrahaNAdi.md")
  library.apply_function(fn=add_pada, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sArasvata-vibhAgaH/saMhitA/sarva-prastutiH/1/8_rAjasUyAdi")