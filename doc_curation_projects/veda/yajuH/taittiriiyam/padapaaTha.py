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
* aligns the mUla sequence to the pada token sequence using text
  similarity + sequence order (DP, free prefix/suffix, contiguous cover),
* inserts ``<details><summary>pada-pAThaH</summary>`` blocks.

Only standard library + ``regex`` + ``bs4`` + ``doc_curation`` are used.
"""

import difflib
import logging
import os

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
  text = regex.sub('ं॒ ‌', 'ं', text)
  text = regex.sub(' इति॑$', '', text)
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


def normalize_for_match(text, is_pada=False):
  """Light normalization for fuzzy matching.

  * pada tokens first go through :func:`strip_iti`,
  * markup / glosses / punctuation / labels are removed,
  * accents + visarga are removed (visarga assimilates to s/r in saMhita,
    so dropping it makes ``पतिः + असि`` comparable to ``पतिरसि``).
  """
  if is_pada:
    text = strip_iti(text)
  text = regex.sub(r"\*\*", "", text)
  text = regex.sub(r"\+\+\+.*?\+\+\+", "", text)
  text = regex.sub(r"[\[\]\(\)]", "", text)
  text = regex.sub(r"[।॥]", "", text)
  # labels like 1A, anuvaka markers [20], punctuation
  text = regex.sub(r"[0-9०-९A-Z]", "", text)
  text = regex.sub(r"[\s\u200b\-\–\—\ऽ\/\.,;:|]+", "", text)
  text = regex.sub(ACCENTS_RE, "", text)
  text = text.replace("ः", "")
  return text


def similarity(a, b):
  if not a or not b:
    return 0.0
  return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# pada file parsing
# ---------------------------------------------------------------------------

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
    # text = visible text without summary
    texts = []
    for child in list(tag.children)[1:]:
      if isinstance(child, NavigableString):
        texts.append(str(child))
      else:
        texts.append(child.get_text(separator=" "))
    text = " ".join(texts).strip()
    entries.append({
      "tag": tag,
      "text": text,
      "norm": normalize_for_match(text, is_pada=False),
      "already_has_pada": _has_pada_after(tag),
    })
  return soup, metadata, content, entries


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

def select_pada_window(mula_norms, pada_tokens, max_anuvakas=4):
  """Narrow the full pada token list to consecutive anuvakas.

  Order-aware prefilter: concatenate normalized mUlas (M) and normalized
  pada tokens (P), find longest common substrings via difflib (fast, C-ish
  for short M), and vote for anuvakas by matched character count.
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
  # token slice
  indices = [i for i, t in enumerate(pada_tokens) if t.get("anuvaka", "") in set(window_anus)]
  start, end = min(indices), max(indices) + 1
  logging.info("Selected pada anuvakas %s (votes %s)", window_anus,
               {a: votes[a] for a in window_anus})
  return pada_tokens[start:end], start


def align_mulas_to_padas(mula_norms, pada_norms, max_span=30, gap_penalty=0.02):
  """Align each mUla to a span of pada tokens (similarity + sequence).

  DP with free prefix/suffix and penalized gaps (for mantras that live in
  ``div.js_include`` targets and are therefore absent from this file's
  top-level mUla list): each mUla consumes 1..max_span tokens,
  skipped pada tokens cost ``gap_penalty`` each. Cost = 1 - similarity.

  Returns (spans, total_cost, gaps) where spans[i] = (start, end) and
  gaps[i] = number of skipped pada tokens just before spans[i].
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
  for i in range(1, n + 1):
    # best_prev[k] = min_{k'<=k} dp[i-1][k'] + gap*(k-k')
    best_prev_val = [INF] * (m + 1)
    best_prev_arg = [0] * (m + 1)
    running_val, running_arg = INF, 0
    for k in range(m + 1):
      cand = dp[i - 1][k]
      if cand < running_val + gap_penalty:
        running_val, running_arg = cand, k
      else:
        running_val = running_val + gap_penalty
      best_prev_val[k] = running_val
      best_prev_arg[k] = running_arg
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

def process_single_file(md_path, pada_tokens, dry_run=False, max_span=30,
                        min_avg_sim=0.55):
  """Add pada details to top-level mUlas of one file. Returns num inserted."""
  soup, metadata, content, mulas = get_top_mulas(md_path)
  if not mulas:
    logging.info("No top-level mUlam in %s", md_path)
    return 0
  mula_norms = [x["norm"] for x in mulas]
  # Two-stage: cheap bigram window selection, then exact DP inside window.
  window_tokens, window_start = select_pada_window(mula_norms, pada_tokens)
  if not window_tokens:
    logging.warning("Empty pada window for %s", md_path)
    return 0
  window_norms = [t["norm"] for t in window_tokens]
  spans, total_cost, gaps = align_mulas_to_padas(mula_norms, window_norms, max_span=max_span)
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
    if s < 0.5 or gaps[idx] > 0:
      logging.warning("  low match [%d] sim=%.3f%s mUla=%r pada=%r", idx, s, extra,
                      mulas[idx]["text"][:60],
                      " + ".join(t["raw"][:30] for t in window_tokens[spans[idx][0]:spans[idx][1]])[:120])
  if avg_sim < min_avg_sim:
    logging.warning("Skipping %s: avg similarity %.3f < %.2f", md_path, avg_sim, min_avg_sim)
    return 0
  inserted = 0
  for entry, (a, b) in zip(mulas, spans):
    # Re-check right before inserting: get_top_mulas() ran before alignment,
    # so re-verify on the live soup to guarantee no duplicate is created.
    if entry["already_has_pada"] or _has_pada_after(entry["tag"]):
      if not entry["already_has_pada"]:
        logging.info("Skipping %r: pada-pATha already present", entry["text"][:40])
      continue
    span_tokens = window_tokens[a:b]
    pada_text = build_pada_text(span_tokens)
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
             _visited=None):
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
                                           max_span=max_span)
  for target in collect_include_targets(file_in, hugo_base=hugo_base):
    # recurse with the same pada tokens (same kANDa/prapAThaka window search
    # is redone per file via free prefix/suffix DP, so Rk/yajuH statics work).
    if target in _visited:
      continue
    _visited.add(target)
    try:
      processed[target] = process_single_file(target, pada_tokens,
                                              dry_run=dry_run, max_span=max_span)
    except Exception as e:  # pragma: no cover
      logging.warning("Failed %s: %s", target, e)
      processed[target] = 0
    # one more level for nested includes (e.g. yajuH static -> Rk static)
    try:
      for nested in collect_include_targets(target, hugo_base=hugo_base):
        if nested in _visited:
          continue
        _visited.add(nested)
        try:
          processed[nested] = process_single_file(nested, pada_tokens,
                                                  dry_run=dry_run, max_span=max_span)
        except Exception as e:  # pragma: no cover
          logging.warning("Failed %s: %s", nested, e)
    except Exception:  # pragma: no cover
      pass
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