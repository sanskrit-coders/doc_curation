"""Interleave commentary below mula blocks as tika.

Simplified engine:

- ``interleave_TIkA_below_mUla`` builds an ordered map of tika-blocks to
  pratikas in commentary-file order, then walks mulas after the last existing
  tika, inserting the next tika-block when its pratika exists in the mula.
  Leftovers are appended under the final mula.
- ``verify_sentence_order`` checks commentary sentence order in dest.
- ``remove_commentary_blocks`` deletes tika blocks from a marker to EOF.
- ``realign_TIkA_below_mUla`` extracts tika blocks into a temp file, strips
  them from dest, then reinserts via ``interleave_TIkA_below_mUla``.
"""
import logging
import re
from collections import deque

try:
  from doc_curation.md.content_processor.details_helper import get_details
  from doc_curation.md.file import MdFile
  _HAS_HELPERS = True
except ImportError:  # pragma: no cover - minimal env without bs4/yamldown.
  get_details = None
  MdFile = None
  _HAS_HELPERS = False

MULA_RE = r"<details><summary>मूलम्</summary>(.*?)</details>"
TIKA_RE = r"<details><summary>टीका</summary>(.*?)</details>"
TIKA_FMT = "\n\n<details><summary>टीका</summary>\n\n%s\n</details>"

# Pratika cue: the iti-marker itself (iti/ity forms). A potential pratika is
# the run of Devanagari words immediately preceding each marker.
ITI_MARKER_RE = r"([िइेी])त(ि|्य)"
# Long quotative continuations fused after the marker (e.g. इत्युक्तम्,
# ेत्यादिना, ेत्यनेन): accepted; any other Devanagari continuation (e.g. the
# visarga in स्थितिः) means the hit is mid-word, not a marker.
_ITI_CONTINUATIONS = ("ुक्तम्", "ुक्त", "ादिना", "ादि", "नेन", "ेव", "ेतत्")
# Quotative-frame verbs: a pratika begins AFTER these (e.g. दर्शयितुं
# सकलेतरप्रमाणविषया इत्युक्तम् quotes सकलेतरप्रमाणविषया, not दर्शयितुं).
# Etc.: extend freely; the full run is still emitted as fallback, so an
# over-eager stop only costs a variant, never recall.
_META_VERBS = frozenset([
  "आह", "दर्शयति", "दर्शयितुं", "दर्शयते",
  "परिहरति", "परिहरते", "आक्षिपति",
  "उपपादयति", "व्याचष्टे", "विवृणोति", "अनुवदति", "प्रतिवक्ति",
  "दूषयति", "निरस्यति", "उपन्यस्यति", "प्रतिपादयति", "विशदयति",
  "सङ्गमयति", "अवतारयति", "समर्थयति", "खण्डयति",
  "ब्रवीति", "वदति", "कथयति", "पठति", "उद्धरति", "निर्दिशति",
])
# fused "...X + आह" frames: deictic/interrogative + āha ("says here...").
# Abutting the marker, the stem IS the pratika (अत्राहेति -> अत्र);
# mid-run, the frame word ends the pratika's left context (stop, exclude).
_AAHA_FUSED = {
  "अत्राह": "अत्र", "तत्राह": "तत्र", "यत्राह": "यत्र", "कुत्राह": "कुत्र",
  "अन्यत्राह": "अन्यत्र", "सर्वत्राह": "सर्वत्र", "एकत्राह": "एकत्र",
  "किमाह": "किम्", "कथमाह": "कथम्",
}


def _split_frontmatter(text):
  m = re.match(r"^(\+\+\+.*?\+\+\+\s*)", text, flags=re.DOTALL)
  if m:
    return m.group(1), text[m.end():]
  return "", text


_SEP_RE = re.compile(r"[\s\-\u2013\u2014\(\)।॥,;:\.\"]")

# A pratika matching more mulas than this cannot locate one (unless long).
_MAX_MULA_HITS = 5
_LONG_PRATIKA_LEN = 8


def _norm_parts(s):
  """(normalized, word-start offsets) for sandhi-tolerant matching.

  Normalization output is identical to :func:`_norm_for_match` (anunāsikas
  to ं, spaces/punctuation stripped); offsets mark mula-word starts in
  normalized space, so pratikas must match at a word start and never mid-word
  (e.g. विशेष must not match inside निर्विशेष).
  """
  s = re.sub(r"[ङञणनम]्", "ं", s)
  s = s.replace("ँ", "ं")
  s = re.sub(r"\[\[([^|\]]+)\|([^]]+)\]\]", r"\1 \2", s)
  out = []
  starts = set()
  at_start = True
  for ch in s:
    if ch == "[" or ch == "]":
      continue
    if _SEP_RE.match(ch):
      at_start = True
      continue
    if at_start:
      starts.add(len(out))
      at_start = False
    out.append(ch)
  return "".join(out), frozenset(starts)


def _norm_for_match(s):
  return _norm_parts(s)[0]


def _split_commentary_sentences(commentary_body):
  t = re.sub(r"^#\d+ lines are missing\.\s*", "", commentary_body, flags=re.MULTILINE)
  joined = re.sub(r"\s+", " ", t).strip()
  parts = re.split(r"(।+|॥+)", joined)
  sents = []
  for i in range(0, len(parts), 2):
    core = parts[i].strip()
    delim = parts[i + 1] if i + 1 < len(parts) else ""
    full = (core + " " + delim).strip()
    full = re.sub(r"\s+", " ", full)
    if full:
      sents.append(full)
  return sents


def _map_to_commentary(dest_norms, comm_norms, fuzzy_threshold=0.85):
  """Map dest sentence norms to commentary indexes (ordering aid for verify).

  Exact normalized matches consume duplicate commentary indexes in dest order;
  leftovers fall back to difflib fuzzy match (>= threshold, best ratio wins).
  Returns a list of (cpos|None, fuzzy_flag) parallel to dest_norms.
  """
  import difflib
  from collections import defaultdict, deque as _deque
  index = defaultdict(_deque)
  buckets = defaultdict(list)
  for i, n in enumerate(comm_norms):
    if len(n) < 2:
      continue
    index[n].append(i)
    buckets[len(n) // 10].append((i, n))
  out = []
  for n in dest_norms:
    if len(n) >= 2 and n in index and index[n]:
      out.append((index[n].popleft(), False))
      continue
    best = None
    if len(n) >= 2:
      cands = []
      b = len(n) // 10
      for bb in (b - 1, b, b + 1):
        cands.extend(buckets.get(bb, ()))
      for i, cn in cands:
        if abs(len(cn) - len(n)) > max(12, int(0.4 * len(n))):
          continue
        r = difflib.SequenceMatcher(None, n, cn, autojunk=False).ratio()
        if r >= fuzzy_threshold and (best is None or r > best[0]):
          best = (r, i)
    out.append((best[1], True) if best is not None else (None, False))
  return out


def _attribute_tikas(dest_body):
  """Parse dest body; return (mula_texts, tika_entries, mula_spans).

  tika_entries: list of dicts {span, mula_j, body} in document order, each tika
  attributed to its preceding mula (spec inserts directly below).
  """
  mula_pat = re.compile(MULA_RE, re.DOTALL)
  all_pat = re.compile(r"<details><summary>(मूलम्|टीका)</summary>(.*?)</details>", re.DOTALL)
  items = list(all_pat.finditer(dest_body))
  mula_texts, owner, cur = [], {}, None
  for ii, m in enumerate(items):
    if m.group(1) == "मूलम्":
      owner[ii] = len(mula_texts)
      mula_texts.append(m.group(2))
      cur = len(mula_texts) - 1
    else:
      owner[ii] = cur
  entries = [
    {"span": (m.start(), m.end()), "mula_j": owner[ii], "body": m.group(2)}
    for ii, m in enumerate(items) if m.group(1) == "टीका"
  ]
  spans = [(m.start(), m.end()) for m in mula_pat.finditer(dest_body)]
  return mula_texts, entries, spans


def _clean_base(b):
  return b.strip("- ").split("।")[0].split("॥")[0].strip()


def _short_mula(mula_text, limit=80):
  """One-line snippet of a mula for logs."""
  return re.sub(r"\s+", " ", mula_text).strip()[:limit]


def _marker_candidates(b, m, max_words=3):
  """Pratika candidates for one iti-marker match, in order: single word,
  post-frame run, full run.

  ``b`` is the searched text, ``m`` an :data:`ITI_MARKER_RE` match. Returns
  None when the hit is unusable (a mid-word continuation like स्थितिः, or no
  preceding words). Emitted variants are the bare last word (the fused stem),
  the run after the nearest quotative frame, and the full run. Frames ending
  the run early are dash/danda stops, standalone :data:`_META_VERBS`
  (pratika begins after दर्शयति/परिहरति/आह…), and fused “…X + आह” words
  (pratika begins after them); an abutting deictic “…Xत्राह” contributes its
  stem instead (अत्राहेति -> अत्र).
  """
  after = b[m.end():]
  if after and re.match(r"[ऀ-ॿ]", after[0]) and not after.startswith(_ITI_CONTINUATIONS):
    return None
  seg = re.split(r"[-–—।॥:;\n]+", b[:m.start()])[-1]
  words = [w for w in re.findall(r"[ऀ-ॿ]+", seg) if re.search(r"[अ-ह]", w)]
  if not words:
    return None
  words = list(words)
  if not b[m.start() - 1].isspace() and words[-1] in _AAHA_FUSED:
    words[-1] = _AAHA_FUSED[words[-1]]

  def _is_frame(w):
    return (w in _META_VERBS or w in _AAHA_FUSED
            or (w.endswith("माह") and len(w) > 3))

  cut = 0
  for k in range(len(words) - 1):
    if _is_frame(words[k]):
      cut = k + 1
  postmeta = words[cut:][-max_words:]
  full = words[-max_words:]
  cands = []
  for p in (words[-1], " ".join(postmeta) if len(postmeta) > 1 else None,
            " ".join(full) if len(full) > 1 else None):
    if p is None:
      continue
    p = _clean_base(p)
    if len(_norm_for_match(p)) >= 2 and p not in cands:
      cands.append(p)
  return cands or None


def _extract_pratikas(tika_block, max_words=3):
  """All potential pratikas in a tika block, in order of appearance.

  A potential pratika is the run of up to ``max_words`` Devanagari words
  immediately preceding an iti-marker ``([िइेी])त(ि|्य)`` — e.g. तथ in तथेति,
  शास्त्रैक in शास्त्रैकेति, तत्सम्बन्धितया प्रकरणान्तरेष्वप in
  ...प्रकरणान्तरेष्वपीति, सकलेतरप्रमाणविषया in ...विषया इत्युक्तम्, एवम् in
  एवमिति, ...प्रकृत in ...प्रकृतेत्यनेन. The run never crosses a dash or
  sentence stop, and the marker must end the word or continue into a
  recognized long suffix (see ``_ITI_CONTINUATIONS``), so mid-word hits like
  स्थितिः are ignored. Both the bare last word and the full run are emitted,
  so single-word pratikas match even inside longer runs. Falls back to the
  block's first two Devanagari words when no marker is found, so every
  non-empty block still yields a candidate.
  """
  b = re.sub(r"^#\d+ lines are missing\.\s*", "", tika_block.strip(), flags=re.MULTILINE)
  if not b:
    return []
  cands = []
  for m in re.finditer(ITI_MARKER_RE, b):
    for p in _marker_candidates(b, m, max_words) or ():
      if p not in cands:
        cands.append(p)
  if not cands:
    words = re.findall(r"[ऀ-ॿ]{2,}", b)[:2]
    p = _clean_base(" ".join(words))
    if len(_norm_for_match(p)) >= 2 and p not in cands:
      cands.append(p)
  return cands


def _sentence_spans(text):
  """(start, end) spans of danda-terminated sentences in raw-text order.

  Mirrors :func:`_split_commentary_sentences` boundaries (split on ।/॥ runs,
  each run closing the preceding sentence; trailing undelimited text forms a
  final sentence) but keeps raw-text offsets, so chunks sliced on these spans
  stay sentence-atomic for :func:`verify_sentence_order`. Spans tile the text
  contiguously.
  """
  spans = []
  pos = 0
  for m in re.finditer(r"[।॥]+", text):
    if text[pos:m.start()].strip():
      spans.append((pos, m.end()))
    elif spans:
      s, _ = spans[-1]
      spans[-1] = (s, m.end())
    else:
      spans.append((pos, m.end()))
    pos = m.end()
  if text[pos:].strip():
    spans.append((pos, len(text)))
  elif spans and pos < len(text):
    spans[-1] = (spans[-1][0], len(text))
  return spans


def _split_block_at_pratikas(block, max_words=3):
  """Split a tika block into pratika-headed chunks, in order.

  Each accepted iti-marker starts a new chunk at its sentence: a chunk holds
  whole sentences from its opening marker's sentence up to the next chunk's
  start (so no sentence ever spans two chunks), with preamble sentences
  before the first marker joining the first chunk. Chunk pratikas are the
  union of their opening sentence's marker candidates. A block with no
  accepted marker stays whole (fallback pratikas, as before).
  Returns ``[(chunk_text, pratikas)]``.
  """
  from bisect import bisect_right
  b = block.strip()
  if not b:
    return []
  marks = []
  for m in re.finditer(ITI_MARKER_RE, b):
    mc = _marker_candidates(b, m, max_words)
    if mc:
      marks.append((m.start(), mc))
  if not marks:
    return [(b, _extract_pratikas(b, max_words))]
  spans = _sentence_spans(b)
  starts = [s for s, _ in spans]
  sent_of = [max(bisect_right(starts, s) - 1, 0) for s, _ in marks]
  bounds = sorted(set(sent_of))
  chunks = []
  for ci, s0 in enumerate(bounds):
    s_end = (bounds[ci + 1] - 1) if ci + 1 < len(bounds) else (len(spans) - 1)
    # First chunk starts at the block start so preamble sentences before the
    # first marker join it (never drop them); later chunks tile contiguously.
    seg_start = spans[0][0] if ci == 0 else spans[s0][0]
    text = b[seg_start:spans[s_end][1]].strip()
    prs = []
    for (_, mc), si in zip(marks, sent_of):
      if si == s0:
        for p in mc:
          if p not in prs:
            prs.append(p)
    if text:
      chunks.append((text, prs))
  return chunks


def _build_TIkA_pratika_map(blocks):
  """Ordered map of pratika-headed chunks to pratika lists, in order.

  Each block from ``blocks`` is split via :func:`_split_block_at_pratikas`;
  returns a deque of ``(chunk, pratikas)`` tuples in commentary order.
  """
  ordered = deque()
  _i = 0
  for b in blocks:
    for chunk, pratikas in _split_block_at_pratikas(b):
      ordered.append((chunk, pratikas))
      logging.info("pratika map %d: %r (block head: %r).", _i, pratikas, chunk[:80])
      _i += 1
  return ordered


def _segmented_total(cand, fixed, n_blocks, n_mulas, start_idx):
  """Longest total with ``fixed`` ({block_idx: mula_idx}) forced.

  Fixed anchors pin disjoint ranges; each segment between them is optimized
  independently, so the sum (+ anchors) is the longest count honoring them.
  """
  anchors = [(bi, mj) for bi, mj in sorted(fixed.items())]
  bounds = [(-1, start_idx - 1)] + anchors + [(n_blocks, n_mulas)]
  total = len(fixed)
  for (bi0, m0), (bi1, m1) in zip(bounds, bounds[1:]):
    seg = list(range(bi0 + 1, bi1))
    if not seg:
      continue
    sub = [[j for j in cand[i] if m0 < j < m1] for i in seg]
    total += len(_longest_match_sequence(sub))
  return total


def _compat_fixed(cand_fixed, cand, n_blocks, n_mulas, start_idx):
  """Fixed placements kept only when compatible with the longest count.

  Greedily keeps anchors in commentary order: an anchor stays iff forcing it
  (with anchors kept so far) still reaches the unconstrained longest total.
  Incompatible anchors rejoin the normal pool (attach/place by DP) instead of
  costing placements.
  """
  free_total = _segmented_total(cand, {}, n_blocks, n_mulas, start_idx)
  kept = {}
  for bi in sorted(cand_fixed):
    trial = dict(kept)
    trial[bi] = cand_fixed[bi]
    if _segmented_total(cand, trial, n_blocks, n_mulas, start_idx) == free_total:
      kept = trial
    else:
      logging.info("interleave: fixed block %d -> mula %d dropped (costs count).",
                   bi, cand_fixed[bi])
  if len(kept) < len(cand_fixed):
    logging.info("interleave: kept %d of %d fixed anchors at longest total %d.",
                 len(kept), len(cand_fixed), free_total)
  return kept


def _exact_pairs(all_pratikas, norm_prats, norm_mulas, start_idx):
  """All (block_idx, mula_idx) unique-exact pairs, in block order, plus hits.

  A pair qualifies when some pratika of the block occurs EXACTLY (full
  length, word start) in exactly one mula in range: such a pratika
  unambiguously locates its mula, whatever its length. A block may contribute
  several pairs; conflicting ones are resolved downstream, never reordered.
  Returns ``(pairs, hit_of)`` with ``hit_of[(bi, mj)]`` the raw pratika.
  """
  m = len(norm_mulas)
  sole = {}
  for nprs in norm_prats:
    for npr in nprs:
      if npr not in sole:
        hits = [j for j in range(start_idx, m)
                if any(norm_mulas[j][0].startswith(npr, o) for o in norm_mulas[j][1])]
        sole[npr] = hits[0] if len(hits) == 1 else None
  pairs = []
  hit_of = {}
  for bi, (plist, nprs) in enumerate(zip(all_pratikas, norm_prats)):
    seen_m = set()
    for p, npr in zip(plist, nprs):
      mj = sole[npr]
      if mj is not None and mj not in seen_m:
        seen_m.add(mj)
        pairs.append((bi, mj))
        hit_of.setdefault((bi, mj), p)
  return pairs, hit_of


def _lis_select(pairs):
  """Longest strictly-increasing subsequence of block-ordered pairs.

  ``pairs`` ascending by block idx. Returns the chosen ``[(bi, mj)]``; ties
  prefer smallest end-mula (leaves most room downstream), then smallest
  end-block. Deterministic.
  """
  n = len(pairs)
  if not pairs:
    return []
  dp = [1] * n
  par = [-1] * n
  for i in range(n):
    bi, mi = pairs[i]
    for k in range(i):
      bk, mk = pairs[k]
      if bk < bi and mk < mi and dp[k] + 1 > dp[i]:
        dp[i] = dp[k] + 1
        par[i] = k
  best = max(dp)
  end = min([i for i in range(n) if dp[i] == best],
            key=lambda i: (pairs[i][1], pairs[i][0]))
  out = []
  while end != -1:
    out.append(pairs[end])
    end = par[end]
  return out[::-1]


def _select_anchors(all_pratikas, norm_prats, norm_mulas, cand, n_blocks, n_mulas,
                    start_idx):
  """Fixed anchors ``{block_idx: (mula_idx, raw_hit)}``, longest-compatible.

  Unique-exact pairs (:func:`_exact_pairs`) feed a longest increasing subset
  (:func:`_lis_select`, smallest-end-mula ties, so e.g. ``473@254`` beats
  ``447@265``); survivors keeping the longest count stay fixed
  (:func:`_compat_fixed`), and dropped pairs must not suppress alternatives,
  so selection repeats without them until stable (excluded set grows
  monotonically: terminates).
  """
  pairs, hit_of = _exact_pairs(all_pratikas, norm_prats, norm_mulas, start_idx)
  excl = set()
  kept = {}
  for _round in range(25):
    pool = [p for p in pairs if p not in excl]
    sel = _lis_select(pool)
    trial = _compat_fixed({bi: mj for bi, mj in sel}, cand, n_blocks, n_mulas,
                          start_idx)
    dropped = [(bi, mj) for (bi, mj) in sel if bi not in trial]
    kept = {bi: (mj, hit_of[(bi, mj)]) for bi, mj in trial.items()}
    if not dropped:
      break
    excl.update(dropped)
    logging.info("interleave: re-selecting anchors without %d costly pairs.", len(dropped))
  else:
    logging.warning("interleave: anchor fixpoint did not converge; using last kept set.")
  return kept


def _match_candidates(blocks_pratikas, mula_texts, start_idx):
  """Candidate mula lists per block under anchored, gated matching.

  A block may sit under mula ``j`` (>= ``start_idx``) if any of its pratikas
  matches there by :func:`_pratika_in_norm_mula`, except pratikas matching
  more than :data:`_MAX_MULA_HITS` mulas (too promiscuous to locate one,
  unless at least :data:`_LONG_PRATIKA_LEN` chars long). Returns
  ``(cand, usable, norm_prats, norm_mulas)``: ``cand[i]`` is the sorted mula
  list for block ``i``; ``usable`` maps normalized pratika to its gate
  verdict; the ``norm_*`` parallels feed hit logging without recomputation.
  """
  norm_mulas = [_norm_parts(t) for t in mula_texts]
  norm_prats = [[_norm_for_match(p) for p in plist] for plist in blocks_pratikas]
  m = len(mula_texts)
  occ = {}
  for nprs in norm_prats:
    for npr in nprs:
      if npr not in occ:
        occ[npr] = sum(1 for j in range(start_idx, m)
                       if _pratika_in_norm_mula(npr, *norm_mulas[j]))
  usable = {npr: (c <= _MAX_MULA_HITS or len(npr) >= _LONG_PRATIKA_LEN)
            for npr, c in occ.items()}
  gated = sorted(npr for npr, ok in usable.items() if not ok)
  if gated:
    logging.info("interleave: %d promiscuous pratikas gated out (e.g. %r).",
                 len(gated), gated[:8])
  cand = []
  for nprs in norm_prats:
    js = []
    for j in range(start_idx, m):
      nm, starts = norm_mulas[j]
      if any(usable[npr] and _pratika_in_norm_mula(npr, nm, starts) for npr in nprs):
        js.append(j)
    cand.append(js)
  return cand, usable, norm_prats, norm_mulas


def _longest_match_sequence(cand):
  """Longest increasing (block, mula) index sequence, earliest placements.

  ``cand[i]`` is the sorted candidate mula list for block ``i``. Returns
  ``[(block_idx, mula_idx)]`` with both strictly increasing and of maximum
  possible length; among all longest sequences the lexicographically smallest
  placement is applied.
  """
  from functools import lru_cache
  n = len(cand)

  @lru_cache(maxsize=None)
  def suf(i, lo):
    # Max further placements using blocks[i:] with mulas >= lo.
    if i >= n:
      return 0
    best = suf(i + 1, lo)
    for j in cand[i]:
      if j < lo:
        continue
      v = 1 + suf(i + 1, j + 1)
      if v > best:
        best = v
    return best

  need = suf(0, -1)
  seq, lo = [], -1
  for i in range(n):
    for j in cand[i]:
      if j < lo:
        continue
      if len(seq) + 1 + suf(i + 1, j + 1) == need:
        seq.append((i, j))
        lo = j + 1
        break
  return seq


# Coverage: fraction of a (long) pratika that must match at a mula word start.
_COVERAGE_NUM = 4
_COVERAGE_DEN = 5
_COVERAGE_CAP = 12
# Edit path (longer pratikas only): prefix of at least max(_EDIT_MIN_LEN,
# len - _EDIT_TAIL_PAD) chars must align within _EDIT_CUTOFF (typos and
# adjacent transpositions mid-string, which cost 1 under OSA; tails stay
# free).
_EDIT_MIN_LEN = 10
_EDIT_TAIL_PAD = 6
_EDIT_CUTOFF = 3


def _anchored_edit_distance(npr, nm, o, max_dist, i_min=0):
  """Min edit distance over pratika prefixes, anchored at mula offset ``o``.

  Aligns ``npr`` starting exactly at ``o`` (no skipping on either side up
  front); the end is free on both sides, but only prefixes of length at least
  ``i_min`` count. Adjacent transpositions cost 1 (OSA). Banded to
  ``max_dist`` with early exit; returns a value > ``max_dist`` when the
  cutoff is exceeded.
  """
  m = len(npr)
  if i_min > m:
    return max_dist + 1
  n = min(len(nm) - o, m + max_dist)
  if n < 0:
    return max_dist + 1
  INF = max_dist + 1
  best = INF
  prevprev = [INF] * (n + 1)
  prev = [INF] * (n + 1)
  prev[0] = 0
  for i in range(1, m + 1):
    cur = [INF] * (n + 1)
    lo = max(1, i - max_dist)
    hi = min(n, i + max_dist)
    ch = npr[i - 1]
    rowmin = INF
    for j in range(lo, hi + 1):
      cost = 0 if ch == nm[o + j - 1] else 1
      v = prev[j] + 1
      ins = cur[j - 1] + 1
      if ins < v:
        v = ins
      sub = prev[j - 1] + cost
      if sub < v:
        v = sub
      if (i > 1 and j > 1 and ch == nm[o + j - 2]
          and npr[i - 2] == nm[o + j - 1]):
        tr = prevprev[j - 2] + 1
        if tr < v:
          v = tr
      cur[j] = v
      if v < rowmin:
        rowmin = v
    if i >= i_min and rowmin < best:
      best = rowmin
    if rowmin > max_dist:
      return INF if best > max_dist else best
    prevprev, prev = prev, cur
  return best


def _pratika_in_norm_mula(npr, nm, starts):
  """Anchored match on pre-normalized strings: coverage or bounded edit.

  Most pratika characters must match (barring whitespace, punctuation and
  anunāsika normalization, all already stripped): short pratikas (< 5 chars)
  must match fully, longer ones need ``_COVERAGE_NUM/_COVERAGE_DEN`` of their
  characters, capped at ``_COVERAGE_CAP``. Longer pratikas (≥
  ``_EDIT_MIN_LEN``) additionally match on bounded edit distance (typos and
  adjacent transpositions mid-string, e.g. commentary भेदव्यपेदशाच्च vs sūtra
  भेदव्यपदेशाच्च). Every hit must begin at a mula word start from ``starts``.
  """
  if len(npr) < 2 or len(nm) < 2:
    return False
  if len(npr) < 5:
    need = len(npr)
  else:
    need = min(((_COVERAGE_NUM * len(npr)) + (_COVERAGE_DEN - 1)) // _COVERAGE_DEN,
               _COVERAGE_CAP)
  needle = npr[:need]
  for o in starts:
    if nm.startswith(needle, o):
      return True
  if len(npr) >= _EDIT_MIN_LEN:
    i_min = max(_EDIT_MIN_LEN, len(npr) - _EDIT_TAIL_PAD)
    for o in starts:
      if _anchored_edit_distance(npr, nm, o, _EDIT_CUTOFF, i_min) <= _EDIT_CUTOFF:
        return True
  return False


def _pratika_in_mula(pratika, mula_text):
  """Sandhi-tolerant existence check: anchored coverage on raw strings.

  Same rule as :func:`_pratika_in_norm_mula` (finds e.g. त्वंपदञ्च in त्वं पदं
  च). Corpus-frequency gating (promiscuous pratikas cannot locate a mula)
  lives in :func:`_match_candidates`, which sees all mulas at once.
  """
  npr = _norm_for_match(pratika)
  nm, starts = _norm_parts(mula_text)
  return _pratika_in_norm_mula(npr, nm, starts)


def _get_ordered_tika_blocks(commentary_file):
  """Return tika-block texts in commentary-file order.

  If the file holds ``<details><summary>टीका</summary>`` blocks (e.g. a temp
  file from :func:`realign_TIkA_below_mUla`), those bodies define the blocks.
  Otherwise the plain body (frontmatter + missing-lines markers stripped) is
  split into paragraphs on blank lines, then fragment paras not ending in
  ``।``/``॥`` are merged with the next para so no sentence spans two blocks
  (otherwise :func:`verify_sentence_order` would report phantom missing).
  """
  with open(commentary_file, encoding="utf-8") as f:
    comm_raw = f.read()
  comm_body = _split_frontmatter(comm_raw)[1]
  tika_bodies = [
    m.group(1) for m in re.finditer(TIKA_RE, comm_body, flags=re.DOTALL)
  ]
  if tika_bodies:
    return [b.strip() for b in tika_bodies if b.strip()]
  comm_body = re.sub(r"^#\d+ lines are missing\.\s*", "", comm_body, flags=re.MULTILINE)
  paras = [p.strip() for p in re.split(r"\n\s*\n", comm_body)]
  paras = [p for p in paras if p]
  blocks, buf = [], ""
  for para in paras:
    buf = (buf + " " + para).strip() if buf else para
    if re.search(r"[।॥]\s*[\"'”’\]\)»]*\s*$", buf):
      blocks.append(buf)
      buf = ""
  if buf:
    blocks.append(buf)
  return blocks


def interleave_TIkA_below_mUla(dest_file, commentary_file):
  """Insert commentary as tika below each mulam block.

  - Builds an ordered map of pratika-headed chunks to pratika lists via
    :func:`_build_TIkA_pratika_map` (blocks from ``commentary_file``, see
    :func:`_get_ordered_tika_blocks`, each split at its iti-markers via
    :func:`_split_block_at_pratikas`); chunk order is identical to
    commentary order.
  - Finds the last existing tika block in ``dest_file``; only mulas after it
    are considered (earlier gaps are left untouched).
  - High-confidence pratika matches are fixed first (:func:`_select_anchors`):
    unique-exact pairs feed a longest increasing subset, kept only when the
    longest count survives (:func:`_compat_fixed`, re-selected without costly
    pairs until stable); incompatible ones rejoin the pool. The longest
    increasing sequence is then computed per segment between fixed anchors
    (:func:`_longest_match_sequence`): each placed block sits under a mula
    where any of its pratikas holds (anchored word-start coverage per
    :func:`_pratika_in_norm_mula` — most pratika characters must match,
    barring normalized spaces/punctuation/anunāsikas; longer pratikas also get
    a bounded edit path; promiscuous pratikas gated out per
    :func:`_match_candidates`), mulas increase with commentary order, and no
    longer placeable subset exists within any segment. An unmatched block is
    consumed, not stalling later blocks: if a previous block already matched,
    it is appended to that previous matched block's tika; leading unmatched
    blocks (before any match) are prepended to the first matched block's tika.
  - If nothing ever matches, all blocks go into a single tika under the final
    mula (at EOF, so sentence order is preserved).
  """
  with open(dest_file, encoding="utf-8") as f:
    dest_raw = f.read()
  dest_head, dest_body = _split_frontmatter(dest_raw)
  mula_pat = re.compile(MULA_RE, re.DOTALL)
  mula_matches = list(mula_pat.finditer(dest_body))
  if not mula_matches:
    logging.warning("No mūlam blocks in %s", dest_file)
    return
  mula_texts = [m.group(1) for m in mula_matches]
  _, tika_entries, _ = _attribute_tikas(dest_body)
  owned = [e["mula_j"] for e in tika_entries if e["mula_j"] is not None]
  last_tika_mula = max(owned) if owned else None
  start_idx = (last_tika_mula + 1) if last_tika_mula is not None else 0
  if start_idx >= len(mula_matches):
    logging.info("All mulas already have tikas in %s; nothing to fill.", dest_file)
    # Still allow leftover-append below if commentary has blocks? No mulas to
    # walk, so everything would be leftovers; that path is handled by realign
    # (which strips first). Here there is nothing to do.
    return
  blocks = _get_ordered_tika_blocks(commentary_file)
  if not blocks:
    logging.warning("No tika blocks in %s", commentary_file)
    return
  # Ordered map of tika-blocks to pratika lists, in commentary-file order.
  ordered = _build_TIkA_pratika_map(blocks)
  logging.info("interleave: %d tika blocks, %d mulas, starting at mula %d (last tika at %s).",
               len(ordered), len(mula_matches), start_idx, last_tika_mula)
  all_pratikas = [pratikas for _, pratikas in ordered]
  cand, usable, norm_prats, norm_mulas = _match_candidates(all_pratikas, mula_texts, start_idx)
  n_blocks, n_mulas = len(ordered), len(mula_matches)
  fixed = _select_anchors(all_pratikas, norm_prats, norm_mulas, cand,
                          n_blocks, n_mulas, start_idx)
  # Longest sequence per segment between fixed anchors (fixed endpoints pin
  # the ranges, so segments are independent).
  anchors = [(bi, mj) for bi, (mj, _) in sorted(fixed.items())]
  bounds = [(-1, start_idx - 1)] + anchors + [(n_blocks, n_mulas)]
  placed, hit_for = {}, {}
  for bi, (mj, hit) in fixed.items():
    placed[bi] = mj
    hit_for[bi] = hit
  for (bi0, m0), (bi1, m1) in zip(bounds, bounds[1:]):
    seg = list(range(bi0 + 1, bi1))
    if not seg:
      continue
    sub = [[j for j in cand[i] if m0 < j < m1] for i in seg]
    for li, mj in _longest_match_sequence(sub):
      placed[seg[li]] = mj
  logging.info("interleave: %d fixed + longest sequence: %d of %d blocks placed.",
               len(fixed), len(placed), len(ordered))
  to_insert = {}  # mula_idx -> list of block texts, in commentary order.
  matched = []  # (hit pratika, mula_idx).
  attached = []  # (block pratikas, mula_idx) appended to a previous matched tika.
  pending_leading = []  # (block, pratikas) unmatched before any match.
  last_placed = None
  for bi, (block, pratikas) in enumerate(ordered):
    if bi in placed:
      mj = placed[bi]
      hit = hit_for.get(bi)
      if hit is None:
        nm, starts = norm_mulas[mj]
        for p, npr in zip(pratikas, norm_prats[bi]):
          if usable[npr] and _pratika_in_norm_mula(npr, nm, starts):
            hit = p
            break
      texts = [b for b, _ in pending_leading] + [block]
      if pending_leading:
        logging.info("interleave: prepending %d leading unmatched blocks to mula %r.",
                     len(pending_leading), _short_mula(mula_texts[mj]))
        pending_leading = []
      to_insert[mj] = texts
      matched.append((hit, mj))
      logging.info("interleave: mula %r <- pratika %r.",
                   _short_mula(mula_texts[mj]), (hit or "")[:60])
      last_placed = mj
    elif last_placed is not None:
      to_insert[last_placed].append(block)
      attached.append((pratikas, last_placed))
      logging.info("interleave: appended unmatched block (pratikas %r) to previous matched mula %r.",
                   pratikas, _short_mula(mula_texts[last_placed]))
    else:
      pending_leading.append((block, pratikas))
      logging.info("interleave: no match yet; holding block (pratikas %r) as leading.", pratikas)
  parts, prev = [], 0
  for idx, m in enumerate(mula_matches):
    s, e = m.span()
    nxt_start = mula_matches[idx + 1].start() if idx + 1 < len(mula_matches) else len(dest_body)
    between = dest_body[e:nxt_start]
    parts.append(dest_body[prev:e])
    if idx in to_insert:
      parts.append(TIKA_FMT % "\n\n".join(t.strip() for t in to_insert[idx]))
      parts.append(between)
      prev = nxt_start
    else:
      parts.append(between)
      prev = nxt_start
  new_body = "".join(parts)
  leftovers = []
  if pending_leading and last_placed is None:
    # Nothing ever matched: keep all blocks together under the final mula.
    leftovers = [b for b, _ in pending_leading]
    new_body = new_body.rstrip() + "\n" + (TIKA_FMT % "\n\n".join(t.strip() for t in leftovers)) + "\n"
    logging.info("interleave: appended %d unmatched blocks under final mula.", len(leftovers))
  for _pr, _mi in matched:
    logging.info("interleave matched: pratika %r -> mula %r.",
                 _pr, _short_mula(mula_texts[_mi]))
  for _prs, _mi in attached:
    logging.info("interleave attached: pratikas %r appended to mula %r.",
                 _prs, _short_mula(mula_texts[_mi]))
  with open(dest_file, "w", encoding="utf-8") as f:
    f.write(dest_head + new_body)
  logging.info("Inserted %d ṭīkās into %s (mūlas=%d, matched=%d, attached=%d, leftovers=%d).",
               len(to_insert), dest_file, len(mula_matches), len(matched),
               len(attached), len(leftovers))
  return {"inserted": len(to_insert), "matched": matched, "attached": attached,
          "leftovers": leftovers, "pratikas": all_pratikas}


def verify_sentence_order(dest_file, commentary_file, start_string=None):
  """Verify tika sentence order strictly follows commentary order.

  - Reads tika blocks in document order via details_helper.get_details
    (regex fallback when helpers are unavailable) and splits them with the
    shared splitter; reads commentary sentences the same way.
  - If ``start_string`` is given, scope starts at the first commentary
    sentence whose normalized form contains it (else the whole file is
    checked from the beginning when ``start_string`` is None): only dest
    sentences mapped at/after the scope start are checked, in dest order.
  - Mapping is verbatim normalized (_norm_for_match) with difflib fuzzy
    fallback (>= 0.85, e.g. typo-fixed variants); shared _map_to_commentary.
  - FAILS on order decreases (dest has B right after A with cpos(B) <= cpos(A))
    and on missing sentences (commentary cpos strictly inside the scope range
    with zero dest mappings anywhere). Unmapped dest sentences and fuzzy
    mappings are reported (not failures). Returns a report dict; logs
    human-readable appendix lines.
  """
  if _HAS_HELPERS:
    from doc_curation.md.content_processor.details_helper import get_details as _get_details
    from doc_curation.md.file import MdFile as _MdFile
    dest_md = _MdFile(file_path=dest_file)
    metadata, dest_content = dest_md.read()
    tika_items = _get_details(dest_content, title="टीका", metadata=metadata)
    tika_bodies = [det.content for _, det in tika_items]
  else:
    with open(dest_file, encoding="utf-8") as f:
      dest_raw = f.read()
    _, dest_content = _split_frontmatter(dest_raw)
    tika_bodies = [
      m.group(1) for m in
      re.finditer(r"<details><summary>टीका</summary>(.*?)</details>", dest_content, flags=re.DOTALL)
    ]
  dest_sents, dest_norms = [], []
  for body in tika_bodies:
    for s in _split_commentary_sentences(body):
      t = s.strip()
      if not t:
        continue
      n = _norm_for_match(t)
      if len(n) < 2:
        continue
      dest_sents.append(t)
      dest_norms.append(n)
  with open(commentary_file, encoding="utf-8") as f:
    comm_raw = f.read()
  comm_body = _split_frontmatter(comm_raw)[1]
  comm_sents = _split_commentary_sentences(comm_body)
  comm_norms = [_norm_for_match(s) for s in comm_sents]
  if start_string is None:
    marker_cpos = 0
  else:
    marker_cpos = None
    marker_norm = _norm_for_match(start_string)
    for i, n in enumerate(comm_norms):
      if n == marker_norm:
        marker_cpos = i
        break
    if marker_cpos is None:
      for i, n in enumerate(comm_norms):
        if marker_norm and marker_norm in n:
          marker_cpos = i
          break
    if marker_cpos is None:
      logging.warning("verify: start string not found; checking whole file.")
      marker_cpos = 0
  mapped = _map_to_commentary(dest_norms, comm_norms)
  scope = [(k, c, dest_sents[k]) for k, (c, _fz) in enumerate(mapped) if c is not None and c >= marker_cpos]
  violations, duplicates = [], []
  for a_i in range(len(scope) - 1):
    _ka, ca, ta = scope[a_i]
    _kb, cb, tb = scope[a_i + 1]
    if cb < ca:
      exp = comm_sents[ca + 1] if ca + 1 < len(comm_sents) else ""
      violations.append({
        "seq": a_i, "prev_cpos": ca, "prev_tail": ta[-60:],
        "curr_cpos": cb, "curr_head": tb[:80], "expected_cpos": ca + 1, "expected_head": exp[:80],
      })
    elif cb == ca:
      duplicates.append({"seq": a_i, "cpos": ca, "head": tb[:80]})
  covered = set(c for _, c, _ in scope)
  covered.update(c for c, _fz in mapped if c is not None)
  missing = []
  if scope:
    lo = min(c for _, c, _ in scope)
    hi = max(c for _, c, _ in scope)
    for c in range(lo + 1, hi):
      if len(comm_norms[c]) < 2:
        continue  # lone-danda splitter artifacts are not sentences
      if c not in covered:
        missing.append({"cpos": c, "head": comm_sents[c][:80] if c < len(comm_sents) else ""})
  unmapped = [(k, dest_sents[k][:80]) for k, (c, _fz) in enumerate(mapped) if c is None]
  fuzzy_n = sum(1 for _c, fz in mapped if fz)
  ok = not violations and not missing
  logging.info("verify_sentence_order: %s (%d tikas, %d sents, %d checked from cpos %d; violations=%d duplicates=%d missing=%d unmapped=%d fuzzy=%d)",
               "OK" if ok else "FAILED", len(tika_bodies), len(dest_sents), len(scope),
               marker_cpos, len(violations), len(duplicates), len(missing), len(unmapped), fuzzy_n)
  for v in violations:
    logging.info("  order violation: after cpos %d %r dest has cpos %d %r; commentary has cpos %d %r",
                 v["prev_cpos"], v["prev_tail"], v["curr_cpos"], v["curr_head"],
                 v["expected_cpos"], v["expected_head"])
  for m in missing:
    logging.info("  missing: commentary cpos %d %r absent from all tikas", m["cpos"], m["head"])
  for d in duplicates[:5]:
    logging.info("  duplicate (info): cpos %d repeated in dest order: %r", d["cpos"], d["head"])
  return {"ok": ok, "marker_cpos": marker_cpos, "n_tikas": len(tika_bodies),
          "n_sents": len(dest_sents), "n_checked": len(scope),
          "violations": violations, "missing": missing, "duplicates": duplicates,
          "unmapped_count": len(unmapped), "unmapped_samples": unmapped[:5],
          "fuzzy_mapped": fuzzy_n}


def remove_commentary_blocks(dest_file, start_string):
  """Remove tika blocks from the one containing start_string to end of file.

  - Locates the FIRST ``<details><summary>टीका</summary>`` block (document
    order) whose normalized content contains the normalized ``start_string``
    (verbatim _norm_for_match containment).
  - Deletes that block and every LATER tika block. Mula blocks and other
    detail types (Translation etc.) are kept intact. Leftover blank spacers
    collapse; tags/spacing/svara elsewhere preserved byte-identically.
  - Returns a report dict; logs removed counts + affected mula range.
  """
  with open(dest_file, encoding="utf-8") as f:
    dest_raw = f.read()
  dest_head, dest_body = _split_frontmatter(dest_raw)
  tika_pat = re.compile(r"<details><summary>टीका</summary>(.*?)</details>", re.DOTALL)
  matches = list(tika_pat.finditer(dest_body))
  if not matches:
    logging.info("remove_commentary_blocks: no tika blocks in %s; nothing to do.", dest_file)
    return {"ok": True, "changed": False, "removed": 0}
  marker = _norm_for_match(start_string)
  cut = None
  for idx, m in enumerate(matches):
    if marker and marker in _norm_for_match(m.group(1)):
      cut = idx
      break
  if cut is None:
    logging.warning("remove_commentary_blocks: start string not found in any tika: %r",
                    start_string[:60])
    return {"ok": False, "changed": False, "removed": 0}
  # Mula owner of first removed tika (appendix; parsing only).
  _mt, _entries, _sp = _attribute_tikas(dest_body)
  _from_mula, _last_mula = None, None
  if len(_entries) == len(matches):
    _owner_by_span = {e["span"]: e["mula_j"] for e in _entries}
    _first = matches[cut]
    _from_mula = _owner_by_span.get((_first.start(), _first.end()))
    _owned = [e["mula_j"] for e in _entries if e["mula_j"] is not None]
    _last_mula = max(_owned) if _owned else None
  else:
    logging.warning("remove_commentary_blocks: parse counts differ; mula range unknown.")
  new_body = dest_body
  for m in reversed(matches[cut:]):
    s, e = m.span()
    ps = s
    if new_body[max(0, s - 3):s] == "\n\n\n":
      ps = s - 3
    elif new_body[max(0, s - 2):s] == "\n\n":
      ps = s - 2
    new_body = new_body[:ps] + new_body[e:]
  with open(dest_file, "w", encoding="utf-8") as f:
    f.write(dest_head + new_body)
  left = len(tika_pat.findall(new_body))
  logging.info("remove_commentary_blocks: removed %d tika blocks (%d left) from mula %s to %s in %s (start: %r).",
               len(matches) - cut, left, _from_mula, _last_mula, dest_file, start_string[:60])
  return {"ok": True, "changed": True, "removed": len(matches) - cut, "left": left,
          "from_tika_index": cut, "from_mula": _from_mula, "to_mula": _last_mula}


def realign_TIkA_below_mUla(dest_file, start_string, commentary_file=None):
  """Realign misplaced tikas by reinserting them in pratika order.

  - Extracts existing tika-block bodies from ``dest_file``, starting at the
    first tika containing ``start_string``, into a temp file (details blocks,
    commentary order preserved).
  - Strips those blocks from ``dest_file`` via :func:`remove_commentary_blocks`.
  - Reinserts via :func:`interleave_TIkA_below_mUla` using ``commentary_file``
    when given (and existing), else the temp file holding the extracted blocks.
  """
  import os
  import tempfile
  with open(dest_file, encoding="utf-8") as f:
    dest_raw = f.read()
  _, dest_body = _split_frontmatter(dest_raw)
  tika_pat = re.compile(TIKA_RE, re.DOTALL)
  matches = list(tika_pat.finditer(dest_body))
  if not matches:
    logging.info("realign: no tika blocks in %s; nothing to do.", dest_file)
    return {"ok": True, "changed": False, "removed": 0}
  marker = _norm_for_match(start_string)
  cut = None
  for idx, m in enumerate(matches):
    if marker and marker in _norm_for_match(m.group(1)):
      cut = idx
      break
  if cut is None:
    logging.warning("realign: start string not found in any tika: %r", start_string[:60])
    return {"ok": False, "changed": False, "removed": 0}
  extracted = [m.group(1).strip() for m in matches[cut:] if m.group(1).strip()]
  tmpdir = "/tmp/opencode"
  try:
    os.makedirs(tmpdir, exist_ok=True)
  except OSError:
    tmpdir = tempfile.gettempdir()
  fd, temp_path = tempfile.mkstemp(prefix="tika_collated_", suffix=".md", dir=tmpdir, text=True)
  with os.fdopen(fd, "w", encoding="utf-8") as f:
    for body in extracted:
      f.write("<details><summary>टीका</summary>\n\n%s\n</details>\n\n" % body)
  logging.info("realign: extracted %d tika blocks to %s.", len(extracted), temp_path)
  remove_commentary_blocks(dest_file, start_string)
  if commentary_file is not None and os.path.exists(commentary_file):
    source = commentary_file
  else:
    source = temp_path
  logging.info("realign: reinserting into %s from %s.", dest_file, source)
  interleave_TIkA_below_mUla(dest_file, source)
  try:
    os.remove(temp_path)
  except OSError:
    pass
  return {"ok": True, "changed": True, "removed": len(extracted), "source": source}


if __name__ == '__main__':
  pass
  remove_commentary_blocks(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md", start_string="उपरितनवाक्यापर्यालोचनां दर्शयति")
  interleave_TIkA_below_mUla(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md", commentary_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sudarshana-sUriH/shruta-prakAshikA/mUlam_rA/1/1/06_AnandamayAdhikaraNam.md")
  verify_sentence_order(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md", commentary_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sudarshana-sUriH/shruta-prakAshikA/mUlam_rA/1/1/06_AnandamayAdhikaraNam.md", start_string="उपरितनवाक्यापर्यालोचनां दर्शयति")
  # realign_TIkA_below_mUla(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md")