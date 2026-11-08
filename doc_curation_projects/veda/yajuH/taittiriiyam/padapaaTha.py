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
  from doc_curation.md.content_processor import include as include_helper
except Exception:  # pragma: no cover
  include_helper = None

DEFAULT_PADA_BASE = "/home/vvasuki/gitland/sanskrit/raw_etexts_private/vedaH/taittirIyA/padapAThaH/saMhitA"
DEFAULT_HUGO_BASE = "/home/vvasuki/gitland/vishvAsa"

MULA_TITLE_RE = r"^\s*मूलम्.*$"
PADA_TITLE = "पद-पाठः"
PADA_TITLE_RE = r"^\s*पद[\s\-‐‑]*पाठः.*$"
LABEL_END_PENALTY = 0.5
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
  text = regex.sub('[॒॑]ꣳ', 'ं', text)
  has_iti = ("त" in text or "त्य" in text)
  if has_iti:
    text = regex.sub(' इत.*ः', 'ः', text)
    text = regex.sub('॒ इत.*ः([॒॑]?)$', 'ः\\1', text)
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
  text = regex.sub(r'\(३\)', '', text)
  text = regex.sub('ꣳ', 'ँ', text)
  if has_iti:
    # standalone upasarga-pada "निरिति" (= निर्, from निस्) carries no "iti X" gloss
    text = regex.sub('^निरिति([॒॑]?)$', 'निर्\\1', text)
    text = regex.sub('^(अ॒?भ|अ॒?त|अ॒?ध|प॒?र|प्र॒?त|न|व)ीति([॒॑]?)$', '\\1ि\\2', text)
    text = regex.sub('^(उ॒?प|अ॒?प|अ॒?व|प्र|प॒?रा|न|च|व)ेति([॒॑]?)$', '\\1\\2', text)
    text = regex.sub('^एति([॒॑]?)$', 'आ\\1', text)
    text = regex.sub(' इति॑$', '', text)
    # "X इति" without visarga/gloss: the iti is a padapATha marker, X is the word
    # (e.g. मो इति -> मो). Bare इति ("thus") has no space: untouched.
    text = regex.sub('^(.+) इति$', '\\1', text)
    # fused "Xu + iti" without gloss (अन्विति -> अनु, स्विति -> सु);
    # glossed forms (पृत्स्विति पृत्-सु) end otherwise: untouched.
    text = regex.sub('^(\\S+)्विति([॒॑]?)$', '\\1ु\\2', text)
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
  """Drop bracketed/parenthesized/braced chunks, keep within-mantra repetitions.

  Chunks whose content does NOT occur unbracketed elsewhere in the same
  text are elisions, glosses or markers (``[ये देवाः]``, ``[रक्षोहण...]``,
  ``{तेषाँ...}``, ``(+++)``, ``[8]``) and are dropped with content. Chunks whose content
  DOES occur unbracketed (e.g. repeated ``[रक्षोघ्ने स्वाहा]``) are expanded.
  """
  if not any(ch in text for ch in "()[]{}"):
    return text
  for _ in range(2):
    for pat in (r"\([^()]*\)", r"\[[^\[\]]*\]", r"\{[^\{\}]*\}"):
      def _decide(m, _text=text):
        inner = m.group(0)[1:-1]
        inner_norm = normalize_for_match(inner, drop_inserts=False)
        if not inner_norm:
          return ""
        rest = _text[:m.start()] + " " + _text[m.end():]
        rest_bare = regex.sub(r"\{[^\{\}]*\}", "", regex.sub(r"\([^()]*\)", "", regex.sub(r"\[[^\[\]]*\]", "", rest)))
        if inner_norm in normalize_for_match(rest_bare, drop_inserts=False):
          return inner
        return ""
      text, _ = regex.subn(pat, _decide, text)
  text = regex.sub(r"[\[\]\(\)\{\}]", "", text)
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
  if drop_inserts:
    text = drop_elided_inserts(text)
  text = regex.sub(r"[।॥]", "", text)
  # labels like 1A, anuvaka markers [20], punctuation
  text = regex.sub(r"[0-9०-९A-Z]", "", text)
  text = regex.sub(r"[\s\u200b\u200c\u200d\u2026\-\–\—\ऽ\/\.,;:|\"\'“”‘’]+", "", text)
  text = regex.sub(ACCENTS_RE, "", text)
  text = regex.sub(r"[ःᳵᳶ]", "", text)
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


def pada_coverage(mula_norm, pada_norm):
  """Fraction of ``pada_norm`` covered by ``mula_norm`` (handles galita elisions)."""
  if not mula_norm or not pada_norm:
    return 0.0
  sm = difflib.SequenceMatcher(None, mula_norm, pada_norm)
  cov1 = sum(b.size for b in sm.get_matching_blocks()) / len(pada_norm)
  ms, ps = consonant_skeleton(mula_norm), consonant_skeleton(pada_norm)
  if ms and ps:
    sm2 = difflib.SequenceMatcher(None, ms, ps)
    cov2 = sum(b.size for b in sm2.get_matching_blocks()) / len(ps)
    return max(cov1, cov2)
  return cov1


# ---------------------------------------------------------------------------
# pada file parsing
# ---------------------------------------------------------------------------

@lru_cache(maxsize=64)
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
    # find label blocks: "<num><letters?> ।" or "<letters> ।"
    label_matches = list(regex.finditer(r"(?:^|\s)(\d+[A-Z]*|[A-Z]+)\s*।", body))
    if not label_matches:
      blocks = [(None, body)]
    else:
      blocks = []
      if label_matches[0].start() > 0:
        blocks.append((None, body[:label_matches[0].start()]))
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
        raw = regex.sub(r"^(?:\d+[A-Z]*|[A-Z]+)\s+", "", raw).strip()
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


def _is_non_split_mula_title(title):
  return any(k in title for k in ("संयुक्तम्", "सातवलेकर", "सात्वलेकर"))


def _has_pada_after(tag):
  """True if a pada-pATha detail already accompanies this mUla tag.

  Scans forward siblings until the next split mUla tag or vishvAsa-prastutiH
  tag (or end of parent), and also backward up to the current unit's
  vishvAsa-prastutiH / previous split mUla tag. Any ``pada-pATha`` detail in
  that unit range counts, so re-running :func:`add_pada` never creates a
  duplicate - even if ``pada-pATha`` was placed before ``mUlam`` or after
  ``mUlam (saMyuktam)``.
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
    if title.startswith("विश्वास-प्रस्तुतिः"):
      break
    if regex.fullmatch(MULA_TITLE_RE, title) and not _is_non_split_mula_title(title):
      break  # reached next mUla without seeing a pada-pATha
    if regex.fullmatch(PADA_TITLE_RE, title):
      return True
    sib = sib.next_sibling
  # Also check backward within the same mantra unit (before mUlam)
  sib = tag.previous_sibling
  while sib is not None:
    if isinstance(sib, NavigableString):
      sib = sib.previous_sibling
      continue
    if getattr(sib, "name", None) != "details":
      sib = sib.previous_sibling
      continue
    title = _detail_title(sib)
    if regex.fullmatch(PADA_TITLE_RE, title):
      return True
    if title.startswith("विश्वास-प्रस्तुतिः") or (regex.fullmatch(MULA_TITLE_RE, title) and not _is_non_split_mula_title(title)):
      break
    sib = sib.previous_sibling
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
    if _is_non_split_mula_title(title):
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
    if _is_non_split_mula_title(title):
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
    div_url = div.get("url", "") or ""
    if "/taittirIyam/sArasvata-vibhAgaH/saMhitA/" not in div_url or "/mUlam/" in div_url or "/vishvAsa-prastutiH/" in div_url:
      continue
    if id(div) not in index_by_div:
      index_by_div[id(div)] = len(groups)
      groups.append({"div": div, "url": div_url, "entries": []})
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
    if not url or "/taittirIyam/sArasvata-vibhAgaH/saMhitA/" not in url or "/mUlam/" in url or "/vishvAsa-prastutiH/" in url:
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

def select_pada_window(mula_norms, pada_tokens, max_anuvakas=20, edge_margin=30):
  """Narrow the full pada token list to consecutive anuvakas (panchatis).

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
    logging.warning("No difflib votes; using whole pada file")
    return pada_tokens, 0
  vmax = max(votes.values())
  thresh = max(8, 0.08 * vmax)
  # anuvaka order as they appear in the file (numeric strings, but keep order)
  anu_order = []
  for t in pada_tokens:
    a = t.get("anuvaka", "")
    if a not in anu_order:
      anu_order.append(a)
  # expand contiguously from the top-voted anuvaka, allowing at most a 1-anuvaka
  # gap (e.g. when a middle panchati lives inside a js_include).
  top = max(votes, key=lambda a: votes[a])
  top_idx = anu_order.index(top)
  lo = hi = top_idx
  while lo - 1 >= 0 and (hi - (lo - 1) + 1) <= max_anuvakas:
    if votes.get(anu_order[lo - 1], 0) >= thresh:
      lo -= 1
    elif lo - 2 >= 0 and votes.get(anu_order[lo - 2], 0) >= thresh and (hi - (lo - 2) + 1) <= max_anuvakas:
      lo -= 2
    else:
      break
  while hi + 1 < len(anu_order) and ((hi + 1) - lo + 1) <= max_anuvakas:
    if votes.get(anu_order[hi + 1], 0) >= thresh:
      hi += 1
    elif hi + 2 < len(anu_order) and votes.get(anu_order[hi + 2], 0) >= thresh and ((hi + 2) - lo + 1) <= max_anuvakas:
      hi += 2
    else:
      break
  window_anus = anu_order[lo:hi + 1]
  # token slice, padded so spans may reach into the previous block's tail
  # or the next block's head across anuvaka/block boundaries
  indices = [i for i, t in enumerate(pada_tokens) if t.get("anuvaka", "") in set(window_anus)]
  start, end = min(indices), max(indices) + 1
  logging.info("Selected pada anuvakas %s (votes %s)", window_anus,
               {a: votes[a] for a in window_anus})
  eff_margin = min(edge_margin, 12) if len(mula_norms) <= 2 else edge_margin
  start = max(0, start - eff_margin)
  end = min(len(pada_tokens), end + eff_margin)
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


def _block_continues_flags(window_tokens, source_tokens, window_start):
  """Per-window-token bool: token starts a label block that continues past it.

  A span ending here (with length > 1) has swallowed the next block's head
  token. Single-token blocks (label immediately followed by the next label
  or source end, e.g. mantra-final "1 \u0964 \u0905\u0924\u094d\u092f\u0902\u0939\u093e\u0903")
  yield False: ending there is legitimate.
  """
  flags = []
  for i, t in enumerate(window_tokens):
    if not t.get("label"):
      flags.append(False)
      continue
    prev = source_tokens[window_start + i - 1] if window_start + i - 1 >= 0 else None
    if t.get("label") == "1" and prev is not None and prev.get("anuvaka") != t.get("anuvaka"):
      # Panchati boundary ("1 ।" at start of new panchati line) often falls mid-sentence
      flags.append(False)
      continue
    nxt = source_tokens[window_start + i + 1] if window_start + i + 1 < len(source_tokens) else None
    flags.append(nxt is not None and not nxt.get("label"))
  return flags


def align_mulas_to_padas(mula_norms, pada_norms, max_span=45,
                         gap_open=0.15, gap_extend=0.001, sequential=None,
                         ends_new_block=None):
  """Align each mUla to a span of pada tokens (similarity + sequence).

  DP with free prefix/suffix and affine-penalized gaps: each mUla consumes
  1..max_span tokens; a skipped stretch (mantras living in ``div.js_include``
  targets, hence absent from this file's mUla list) costs ``gap_open`` once
  plus ``gap_extend`` per token.
  """
  n, m = len(mula_norms), len(pada_norms)
  if n == 0 or m == 0:
    return [], float("inf"), []
  INF = 1e9

  mula_skels = [consonant_skeleton(x) for x in mula_norms]
  pada_skels = [consonant_skeleton(x) for x in pada_norms]
  mula_lens = [len(x) for x in mula_norms]

  p_cum_norm = [""]
  p_cum_skel = [""]
  for pn, ps in zip(pada_norms, pada_skels):
    p_cum_norm.append(p_cum_norm[-1] + pn)
    p_cum_skel.append(p_cum_skel[-1] + ps)

  def _run_dp_row(i, best_prev_val, best_prev_arg, prune=True):
    dp_i = [INF] * (m + 1)
    par_k_i = [None] * (m + 1)
    par_prev_i = [None] * (m + 1)
    mn = mula_norms[i - 1]
    ms = mula_skels[i - 1]
    ml = mula_lens[i - 1]
    min_bpv = min(best_prev_val)
    if min_bpv >= INF:
      return dp_i, par_k_i, par_prev_i
    max_len = int(ml * 1.85) + 8
    for k in range(i - 1, m):
      bpv = best_prev_val[k]
      if bpv >= INF:
        continue
      if prune and bpv > min_bpv + 1.4:
        continue
      bpa = best_prev_arg[k]
      if prune:
        ps_k = pada_skels[k]
        if ms and ps_k:
          head_match = (ms[0] == ps_k[0]) or (len(ms) > 1 and ms[1] == ps_k[0]) or (len(ps_k) > 1 and ms[0] == ps_k[1])
          if not head_match and (i == 1 or bpv > min_bpv + 0.05):
            continue
      base_norm_len = len(p_cum_norm[k])
      eff_max_span = max(max_span, int(ml * 0.65) + 20)
      j_max = min(m, k + eff_max_span)
      for j in range(k + 1, j_max + 1):
        cl = len(p_cum_norm[j]) - base_norm_len
        if prune and cl > max_len and j > k + 1:
          break
        pen = LABEL_END_PENALTY if (ends_new_block is not None and j - 1 > k and ends_new_block[j - 1]) else 0.0
        if bpv + pen >= dp_i[j]:
          continue
        c_norm = p_cum_norm[j][base_norm_len:]
        c_skel = p_cum_skel[j][len(p_cum_skel[k]):]
        r1 = difflib.SequenceMatcher(None, mn, c_norm).ratio()
        r2 = difflib.SequenceMatcher(None, ms, c_skel).ratio() if (ms and c_skel) else 0.0
        cost = 1.0 - max(r1, r2) + pen
        tot = bpv + cost
        if tot < dp_i[j]:
          dp_i[j] = tot
          par_k_i[j] = k
          par_prev_i[j] = bpa
    return dp_i, par_k_i, par_prev_i

  dp = [[INF] * (m + 1) for _ in range(n + 1)]
  par_k = [[None] * (m + 1) for _ in range(n + 1)]
  par_prev = [[None] * (m + 1) for _ in range(n + 1)]
  for j in range(m + 1):
    dp[0][j] = 0.0
  if sequential is None:
    sequential = [False] * n
  for i in range(1, n + 1):
    best_prev_val = [INF] * (m + 1)
    best_prev_arg = [0] * (m + 1)
    if i > 1 and sequential[i - 1]:
      for k in range(m + 1):
        best_prev_val[k] = dp[i - 1][k]
        best_prev_arg[k] = k
    else:
      run_val, run_arg = INF, 0
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
    dp_i, par_k_i, par_prev_i = _run_dp_row(i, best_prev_val, best_prev_arg, prune=True)
    if min(dp_i) >= INF / 2:
      # Fallback: if sequential gapless transition hit a dead-end or pruning was too tight,
      # allow affine gaps and unpruned search on this step.
      if i > 1 and sequential[i - 1]:
        run_val, run_arg = INF, 0
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
      dp_i, par_k_i, par_prev_i = _run_dp_row(i, best_prev_val, best_prev_arg, prune=False)
    dp[i] = dp_i
    par_k[i] = par_k_i
    par_prev[i] = par_prev_i
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


def _match_single_head(head_norm, span_first_norm):
  if not head_norm:
    return True
  hs, ss = consonant_skeleton(head_norm), consonant_skeleton(span_first_norm)
  if hs and ss:
    if hs.startswith(ss) or ss.startswith(hs):
      return True
    if len(ss) >= 2 and ss.endswith("त") and hs.startswith(ss[:-1]):
      return True
    if hs[0] == ss[0] and (len(ss) == 1 or len(hs) == 1 or similarity(hs[:len(ss) + 1], ss) >= 0.5):
      return True
  head_pref = head_norm[:max(len(span_first_norm) + 2, 3)]
  return similarity(head_pref, span_first_norm) >= 0.5


def span_head_ok(entry_text, span_first_norm, carried_over=False):
  """Check the span starts with the mUla's head word (or a subsequent clause head
  when the leading clause is elided/galita in the padapATha)."""
  if carried_over:
    return True
  head_norm = normalize_for_match(mula_head_token(entry_text))
  if _match_single_head(head_norm, span_first_norm):
    return True
  # Check subsequent clauses (separated by danda, newline, or quotes) in case
  # the leading clause of the mUla was elided (galita) in the padapATha.
  for clause in regex.split(r"[।॥\n\"“”‘’]+", entry_text):
    ch = normalize_for_match(mula_head_token(clause))
    if ch and _match_single_head(ch, span_first_norm):
      return True
  return False


def build_pada_text(span_tokens):
  """Build ``... । ... ।`` display string for a span (without clause index labels)."""
  if not span_tokens:
    return ""
  return " ".join(f"{t['raw']} {t['delim']}" for t in span_tokens).strip()


# ---------------------------------------------------------------------------
# file processing
# ---------------------------------------------------------------------------

def mula_head_token(text):
  """First whitespace-separated token of markup-cleaned mUla text."""
  text = regex.sub(r"\+\+\+.*?\+\+\+", "", text)
  text = drop_elided_inserts(text)
  text = regex.sub(r"[।॥]", " ", text)
  text = regex.sub(r"[0-9०-९A-Z]", "", text)
  text = regex.sub(r"[\u200b\u200c\u200d\u2026\-\u2013\u2014\/\.,;:|\+\"\'“”‘’]+", " ", text)
  parts = text.split()
  return parts[0] if parts else ""


def leading_carryover(entry_text, span_concat_norm):
  """Return "आ । " prefix if the mUla starts with particle आ missing
  from the span head (padapATha source has no token for it, e.g. leading
  \u0906 in "\u0906 \u0928 \u090f\u0924\u0941"), else ''. Conservative: only fires for
  head token 'आ' whose norm is not already the span start.
  """
  if not span_concat_norm:
    return ""
  head = mula_head_token(entry_text)
  head_norm = normalize_for_match(head)
  if head_norm != "आ":
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


def _span_acceptable(entry, span_concat_norm, s):
  if "अनुवाकः" in entry["text"] or "प्रपाठकः" in entry["text"]:
    return False
  if s >= 0.5:
    return True
  # Galita (elided repeated clauses in padapATha): span is shorter than mUla,
  # but >=85% of the span's characters match inside the mUla.
  if len(span_concat_norm) >= 3 and pada_coverage(entry["norm"], span_concat_norm) >= 0.85:
    return True
  return False


def process_single_file(md_path, pada_tokens, dry_run=False, max_span=45,
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
  if mulas and not all(e["already_has_pada"] for e in mulas):
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
    ends_block = _block_continues_flags(window_tokens, pada_tokens, window_start)
    spans, total_cost, gaps = align_mulas_to_padas(mula_norms, window_norms, max_span=max_span,
                                                   sequential=sequential, ends_new_block=ends_block)
    sims = []
    for idx, (a, b) in enumerate(spans):
      concat = "".join(window_norms[a:b])
      sims.append(similarity(mula_norms[idx], concat))
    avg_sim = sum(sims) / len(sims) if sims else 0.0
    n_gaps = sum(1 for g in gaps if g > 0)
    logging.info("Aligned %d mUlas in %s (window %d tokens @%d, avg_sim=%.3f, gaps=%d)",
                 len(mulas), md_path, len(window_tokens), window_start, avg_sim, n_gaps)
    if avg_sim < min_avg_sim:
      logging.warning("Skipping %s: avg similarity %.3f < %.2f", md_path, avg_sim, min_avg_sim)
      return 0
    for entry, (a, b), s in zip(mulas, spans, sims):
      if entry["already_has_pada"] or _has_pada_after(entry["tag"]):
        continue
      span_concat_norm = "".join(window_norms[a:b])
      if not _span_acceptable(entry, span_concat_norm, s):
        logging.warning("  skipping low match sim=%.3f mUla=%r pada=%r", s,
                        entry["text"][:60],
                        " + ".join(t["raw"][:30] for t in window_tokens[a:b])[:120])
        continue
      span_tokens = window_tokens[a:b]
      carried = leading_carryover(entry["text"], span_concat_norm)
      if not span_head_ok(entry["text"], window_norms[a], carried_over=bool(carried)):
        if pada_coverage(entry["norm"], span_concat_norm) < 0.90:
          logging.warning("  skipping bad head mUla=%r pada-head=%r", entry["text"][:60],
                          span_tokens[0]["raw"][:40])
          continue
      pada_text = carried + build_pada_text(span_tokens)
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
  for group in div_groups:
    g_all = [e for e in group["entries"] if e["norm"]]
    if not g_all or all(e["already_has_pada"] for e in g_all):
      continue
    g_norms = [e["norm"] for e in g_all]
    g_seq = [False] * len(g_all)
    g_tokens = _group_pada_tokens(group, md_path, pada_tokens, hugo_base)
    g_window, g_start = select_pada_window(g_norms, g_tokens, edge_margin=max_span)
    if not g_window:
      continue
    g_wnorms = [t["norm"] for t in g_window]
    try:
      g_spans, _, _ = align_mulas_to_padas(g_norms, g_wnorms, max_span=max_span,
                                           sequential=g_seq,
                                           ends_new_block=_block_continues_flags(g_window, g_tokens, g_start))
    except RuntimeError as e:
      logging.warning("Skipping in-div mUlas in %s (%s): %s", md_path, group["url"], e)
      continue
    for entry, (a, b) in zip(g_all, g_spans):
      if entry["already_has_pada"] or _has_pada_after(entry["tag"]):
        continue
      span_concat_norm = "".join(g_wnorms[a:b])
      s = similarity(entry["norm"], span_concat_norm)
      if not _span_acceptable(entry, span_concat_norm, s):
        logging.warning("  in-div low match sim=%.3f mUla=%r pada=%r (in %s)",
                        s, entry["text"][:60],
                        " + ".join(t["raw"][:30] for t in g_window[a:b])[:120],
                        group["url"])
        continue
      span_toks = g_window[a:b]
      carried = leading_carryover(entry["text"], span_concat_norm)
      if not span_head_ok(entry["text"], g_wnorms[a], carried_over=bool(carried)):
        if pada_coverage(entry["norm"], span_concat_norm) < 0.90:
          logging.warning("  skipping bad head mUla=%r pada-head=%r (in %s)", entry["text"][:60],
                          span_toks[0]["raw"][:40])
          continue
      pada_text = carried + build_pada_text(span_toks)
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
    new_content = regex.sub(r"([^\n])[ \t]*(</details>)", r"\1\n\2", new_content)
    new_content = regex.sub(r"([^\n])\n(<div\b)", r"\1\n\n\2", new_content)
    new_content = regex.sub(r"([^\n])\n(<details\b)", r"\1\n\n\2", new_content)
    new_content = regex.sub(r"(</details>)\n([^\n])", r"\1\n\n\2", new_content)
    new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
    MdFile(file_path=str(md_path)).replace_content_metadata(
      new_metadata=metadata, new_content=new_content)
  logging.info("Inserted %d pada details in %s", inserted, md_path)
  return inserted


def add_pada(file_in, pada_file=None, pada_base=DEFAULT_PADA_BASE,
             hugo_base=DEFAULT_HUGO_BASE, dry_run=False, max_span=45,
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
