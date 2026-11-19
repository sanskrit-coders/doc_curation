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
  from doc_curation.md.content_processor.details import get_details
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
# Long quotative continuations fused after the marker: इत्युक्तम्/ेत्यादिना/
# ेत्यनेन forms, plus इत्यत्र ("where X [is said]"), इत्याह ("says X") and
# इत्यर्थः ("X means…") — the preceding word is the pratika in each case.
# Any other Devanagari continuation (e.g. the visarga in स्थितिः) means the
# hit is mid-word, not a marker.
_ITI_CONTINUATIONS = (
  "्याद्याः", "्याद्या", "्याद्ये", "्याद्य", "्यादिना", "्यादि",
  "्यनुष्टुप्", "्यनुष्टु", "्युक्तम्", "्युक्त", "्यनेन", "्यर्थम्", "्यर्थः", "्यर्थ",
  "ुक्तम्", "ुक्त", "ादिना", "ाद्याः", "ाद्या", "ाद्ये", "ादि",
  "नेन", "ेव", "ेतत्", "त्र", "ाह", "र्थम्", "र्थः", "र्थ",
  "नुष्टुप्", "नुष्टु", "ीत्वाभावः", "ीत्वा", "ीत्",
)
_ITI_CONTINUATIONS_BY_LEN = tuple(sorted(_ITI_CONTINUATIONS, key=len, reverse=True))
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
# yaṆ-sandhi reversal map (consonant + halant + K -> restored vowel): e.g.
# commentary तत्त्विति = तत्तु + इति, अपि त्विति contains अपि तु.
_YAN_RESTORE = {"व": "ु", "य": "ि", "र": "ृ", "ल": "ि"}


def _split_frontmatter(text):
  m = re.match(r"^(\+\+\+.*?\+\+\+\s*)", text, flags=re.DOTALL)
  if m:
    return m.group(1), text[m.end():]
  return "", text


_SEP_RE = re.compile(r"[\s\-\u2013\u2014\(\)।॥,;:\.\"'“”‘’0-9०-९*+_#]")
_SVARA_STRIP_RE = re.compile(r"[\u0951-\u0954\u1cd0-\u1cf4\u1cf7-\u1cff\u200c\u200d᳓᳙]")
_PLUS_GLOSS_RE = re.compile(r"\+\+\+.*?\+\+\+", flags=re.DOTALL)
_SUTRA_CITATION_RE = re.compile(
  r"(?:'[^'\n]{2,100}'|‘[^’\n]{2,100}’)\s*इत[ि्य]\S*"
)

# A pratika matching more mulas than this cannot locate one (unless long).
_MAX_MULA_HITS = 5
_LONG_PRATIKA_LEN = 8


def _tika_re(tika_title="टीका"):
  return r"<details><summary>%s</summary>(.*?)</details>" % re.escape(tika_title)


def _tika_fmt(tika_title="टीका"):
  return "\n\n<details><summary>%s</summary>\n\n%%s\n</details>" % tika_title


def _norm_parts(s):
  """(normalized, word-start offsets) for sandhi- and svara-tolerant matching.

  Strips Vedic svaras, ``+++(...)+++`` editorial glosses, markdown markers, and
  normalizes anunāsikas, Vedic ``य्ँ``/``व्ँ``/``ल्ँ``, jihvāmūlīya/upadhmānīya,
  avagraha, and geminates; offsets mark mula-word starts in normalized space so
  pratikas must match at a word start and never mid-word.
  """
  s = _PLUS_GLOSS_RE.sub(" ", s or "")
  s = re.sub(r"<!--.*?-->", " ", s, flags=re.DOTALL)
  s = re.sub(r"\[\[([^|\]]+)\|([^]]+)\]\]", r"\1 \2", s)
  s = re.sub(r"\[\^?[0-9०-९P.]+\]", " ", s)
  s = _SVARA_STRIP_RE.sub("", s)
  s = s.replace("ᳵ", "ः").replace("ᳶ", "ः").replace("ळ", "ल")
  s = re.sub(r"[यवल]्ँ", "ं", s)
  s = re.sub(r"[ङञणनम]्", "ं", s)
  s = s.replace("ँ", "ं")
  s = re.sub(r"(^|[\s,।॥\-–—ोे])ऽ", r"\1 अ", s)
  s = s.replace("ऽ", "").replace("त्त्र", "त्र").replace("द्ध्व", "ध्व")
  s = re.sub(r"([अ-हइ-औि-ौ])[शषस]्(?=(?:\s+|[-–—]|$))", r"\1ः ", s)
  s = re.sub(r"([अ-हइ-औि-ौ])स्(?=स्[क-ह])", r"\1ः ", s)
  s = re.sub(r"([अ-हइ-औि-ौ])श्(?=श[क-हअ-औि-ौ])", r"\1ः ", s)
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


def _quote_safe_danda_spans(text):
  """Yield ``(start, end)`` spans split on ``।``/``॥`` outside quotes, parens, and ``+++...+++``."""
  spans = []
  pos = 0
  paren = 0
  in_dq = False
  in_sq = False
  in_plus = False
  n = len(text)
  i = 0
  while i < n:
    if text[i:i + 3] == "+++":
      in_plus = not in_plus
      i += 3
      continue
    ch = text[i]
    if not in_plus:
      if ch == '"' and (i == 0 or text[i - 1] != "\\"):
        in_dq = not in_dq
      elif not in_dq:
        if ch == "'" and not (i > 0 and text[i - 1].isascii() and text[i - 1].isalpha()):
          if in_sq or ("'" in text[i + 1:i + 140]):
            in_sq = not in_sq
        elif not in_sq:
          if ch in "([“‘":
            paren += 1
          elif ch in ")]”’" and paren > 0:
            paren -= 1
    if not in_plus and not in_dq and not in_sq and paren == 0 and ch in "।॥":
      j = i + 1
      while j < n and text[j] in "।॥":
        j += 1
      if text[pos:i].strip():
        spans.append((pos, j))
      elif spans:
        spans[-1] = (spans[-1][0], j)
      else:
        spans.append((pos, j))
      pos = j
      i = j
      continue
    i += 1
  if text[pos:].strip():
    spans.append((pos, n))
  elif spans and pos < n:
    spans[-1] = (spans[-1][0], n)
  return spans


def _split_commentary_sentences(commentary_body):
  t = re.sub(r"^#\d+ lines are missing\.\s*", "", commentary_body, flags=re.MULTILINE)
  joined = re.sub(r"\s+", " ", t).strip()
  sents = []
  for s, e in _quote_safe_danda_spans(joined):
    full = re.sub(r"\s+", " ", joined[s:e]).strip()
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


def _attribute_tikas(dest_body, tika_title="टीका"):
  """Parse dest body; return (mula_texts, tika_entries, mula_spans).

  tika_entries: list of dicts {span, mula_j, body} in document order, each tika
  attributed to its preceding mula (spec inserts directly below).
  """
  mula_pat = re.compile(MULA_RE, re.DOTALL)
  esc_t = re.escape(tika_title)
  all_pat = re.compile(r"<details><summary>(मूलम्|%s)</summary>(.*?)</details>" % esc_t, re.DOTALL)
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
    for ii, m in enumerate(items) if m.group(1) == tika_title
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
  the run after the nearest quotative frame, and the full run, with yaṇ twins
  first where applicable: a fused “…C + halant + K + dependent-ि marker”
  (e.g. तत्त्विति = तत्तु + इति, अपि त्विति containing अपि तु) also emits the
  vowel-restored twin list (:data:`_YAN_RESTORE`), since juxtaposed originals
  (सत्त्व + इति) share the shape and gating/matching sort them out. Frames
  ending the run early are dash/danda stops, standalone :data:`_META_VERBS`
  (pratika begins after दर्शयति/परिहरति/आह…), and fused “…X + आह” words
  (pratika begins after them); an abutting deictic “…Xत्राह” contributes its
  stem instead (अत्राहेति -> अत्र).
  """
  after = b[m.end():]
  if after.startswith("\u094d"):
    pass  # Spaced hyphenated `इत्य् अनेन` / `इत्य् आह` / `इत्य् अर्थः`
  elif after and re.match(r"[ऀ-ॿ]", after[0]) and not after.startswith(_ITI_CONTINUATIONS):
    return None
  seg = re.split(r"(?:\s+[-–—]\s*|[-–—]\s+|[–—।॥:;\n'‘’\"“”()])+", b[:m.start()])[-1]
  seg = re.sub(r"(?<=[ऀ-ॿ])-(?=[ऀ-ॿ])", "", seg)
  words = [w for w in re.findall(r"[ऀ-ॿ]+", seg) if re.search(r"[अ-ह]", w)]
  if not words:
    return None
  words = list(words)
  abut = m.start() > 0 and not b[m.start() - 1].isspace()
  vtag = m.group(1)
  if abut and words[-1] in _AAHA_FUSED:
    words[-1] = _AAHA_FUSED[words[-1]]
    yan_lists = [words]
  elif abut and vtag == "े" and words[-1].endswith("त्व"):
    yan_lists = [words[:-1] + [words[-1][:-2] + "त्वा"], words]
  elif (abut and vtag == "ि"
        and (ym := re.search("[क-ह]\u094d([यवरल])$", words[-1]))):
    stem = words[-1][:ym.start(1) - 1] + _YAN_RESTORE[ym.group(1)]
    yan_lists = [words[:-1] + [stem], words]
  elif abut and vtag == "ी":
    yan_lists = [words[:-1] + [words[-1] + "ि"], words[:-1] + [words[-1] + "ी"], words]
  elif abut and vtag == "े":
    yan_lists = [words, words[:-1] + [words[-1] + "ा"]]
  elif not abut and vtag == "इ" and re.search(r"[क-ह]$", words[-1]):
    yan_lists = [words[:-1] + [words[-1] + "े"], words]
  else:
    yan_lists = [words]

  def _is_frame(w):
    return (w in _META_VERBS or w in _AAHA_FUSED
            or (w.endswith("माह") and len(w) > 3))

  cands = []
  for wl in yan_lists:
    cut = 0
    for k in range(len(wl) - 1):
      if _is_frame(wl[k]):
        cut = k + 1
    postmeta = wl[cut:][-max_words:]
    full = wl[-max_words:]
    for p in (wl[-1], " ".join(postmeta) if len(postmeta) > 1 else None,
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
  # Bolded pratīkas (`**शवसः**`, `**आदित्**`)
  for bm in re.finditer(r"\*\*([^*।॥\n]{2,60})\*\*", b):
    p = _clean_base(bm.group(1))
    if len(_norm_for_match(p)) >= 2 and p not in cands:
      cands.append(p)
  masked = _SUTRA_CITATION_RE.sub(lambda m: " " * (m.end() - m.start()), b)
  for m in re.finditer(ITI_MARKER_RE, masked):
    for p in _marker_candidates(masked, m, max_words) or ():
      if p not in cands:
        cands.append(p)
  for qm in re.finditer(r'(?:"([^"\n]{3,80})"|“([^”\n]{3,80})”)(?!\s*\([^)\n]*[॰.])', b):
    p = _clean_base(qm.group(1) or qm.group(2))
    if len(_norm_for_match(p)) >= 3 and p not in cands:
      cands.append(p)
  if not cands:
    words = re.findall(r"[ऀ-ॿ]{2,}", _PLUS_GLOSS_RE.sub(" ", masked))[:2]
    p = _clean_base(" ".join(words))
    if len(_norm_for_match(p)) >= 2 and p not in cands:
      cands.append(p)
  return cands


def _sentence_spans(text):
  """(start, end) spans of quote-safe danda-terminated sentences in raw-text order."""
  return _quote_safe_danda_spans(text)


def _marker_end(b, m_end):
  """End offset of an iti-marker including virāma or a fused long continuation, if any."""
  if b.startswith("\u094d", m_end):
    return m_end + 1
  for cont in _ITI_CONTINUATIONS_BY_LEN:
    if b.startswith(cont, m_end):
      return m_end + len(cont)
  return m_end


def _split_block_at_pratikas(block, max_words=3):
  """Split a tika block into pratika-headed chunks, in order."""
  from bisect import bisect_right
  b = block.strip()
  if not b:
    return []
  masked = _SUTRA_CITATION_RE.sub(lambda m: " " * (m.end() - m.start()), b)
  marks = []
  for m in re.finditer(ITI_MARKER_RE, masked):
    mc = _marker_candidates(masked, m, max_words)
    if mc:
      marks.append((m.start(), m.end(), mc))
  if not marks:
    return [(b, _extract_pratikas(b, max_words))]
  spans = _sentence_spans(b)
  starts = [s for s, _ in spans]
  sent_of = [max(bisect_right(starts, s) - 1, 0) for s, _, _ in marks]
  end_marker_of = {}
  for idx, ((s, e, mc), si) in enumerate(zip(marks, sent_of)):
    if not re.search(r"[अ-ह]", masked[_marker_end(masked, e):spans[si][1]]):
      end_marker_of[si] = idx
  bounds = sorted(set(sent_of))
  chunks = []
  for ci, s0 in enumerate(bounds):
    s_end = (bounds[ci + 1] - 1) if ci + 1 < len(bounds) else (len(spans) - 1)
    # First chunk starts at the block start so preamble sentences before the
    # first marker join it (never drop them); later chunks tile contiguously.
    seg_start = spans[0][0] if ci == 0 else spans[s0][0]
    text = b[seg_start:spans[s_end][1]].strip()
    prs = []
    for idx, ((_, _, mc), si) in enumerate(zip(marks, sent_of)):
      if si != s0:
        continue
      if s0 in end_marker_of and idx != end_marker_of[s0]:
        continue
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


def _usable_in_range(seg, norm_prats, norm_mulas, m0, m1):
  """Gate verdicts counted within mula range ``(m0, m1)``.

  Same rule as the global gate (:func:`_match_candidates`): usable iff the
  pratika pair-matches at most :data:`_MAX_MULA_HITS` mulas in range (or is
  long). A globally promiscuous pratika (e.g. अत, तथ) revives where sentence
  order narrows it to few candidates, so short pratikas match their
  appropriate nearby mula instead of never matching at all.
  """
  seen = set()
  usable = {}
  for i in seg:
    for npr in norm_prats[i]:
      if npr in seen:
        continue
      seen.add(npr)
      c = sum(1 for j in range(m0 + 1, m1)
              if _pratika_in_norm_mula(npr, *norm_mulas[j]))
      usable[npr] = (c <= _MAX_MULA_HITS or len(npr) >= _LONG_PRATIKA_LEN)
  return usable


def _longest_match_sequence(cand):
  """Longest increasing (block, mula) index sequence, earliest placements.

  ``cand[i]`` is the sorted candidate mula list for block ``i``. Returns
  ``[(block_idx, mula_idx)]`` with both strictly increasing and of maximum
  possible length; among all longest sequences the lexicographically smallest
  placement is applied. Iterative DP (no recursion: hundreds of blocks would
  overflow the stack).
  """
  n = len(cand)
  if n == 0:
    return []
  lo_vals = {-1}
  for js in cand:
    for j in js:
      lo_vals.add(j + 1)
  lo_sorted = sorted(lo_vals)
  # suf_rows[i][lo] = max further placements using blocks[i:] with mulas >= lo.
  suf_rows = [None] * (n + 1)
  suf_rows[n] = {lo: 0 for lo in lo_sorted}
  for i in range(n - 1, -1, -1):
    cur = {}
    for lo in lo_sorted:
      best = suf_rows[i + 1][lo]
      for j in cand[i]:
        if j < lo:
          continue
        v = 1 + suf_rows[i + 1][j + 1]
        if v > best:
          best = v
      cur[lo] = best
    suf_rows[i] = cur
  need = suf_rows[0][-1]
  seq, lo = [], -1
  for i in range(n):
    for j in cand[i]:
      if j < lo:
        continue
      if len(seq) + 1 + suf_rows[i + 1][j + 1] == need:
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


def _get_ordered_tika_blocks(commentary_file, tika_title="टीका"):
  """Return tika-block texts in commentary-file order."""
  with open(commentary_file, encoding="utf-8") as f:
    comm_raw = f.read()
  comm_body = _split_frontmatter(comm_raw)[1]
  tika_bodies = [
    m.group(1) for m in re.finditer(_tika_re(tika_title), comm_body, flags=re.DOTALL)
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


def interleave_TIkA_below_mUla(dest_file, commentary_file, tika_title="टीका"):
  """Insert commentary as ``tika_title`` (default ``टीका``) below each mulam block."""
  with open(dest_file, encoding="utf-8") as f:
    dest_raw = f.read()
  dest_head, dest_body = _split_frontmatter(dest_raw)
  mula_pat = re.compile(MULA_RE, re.DOTALL)
  mula_matches = list(mula_pat.finditer(dest_body))
  if not mula_matches:
    logging.warning("No mūlam blocks in %s", dest_file)
    return
  mula_texts = [m.group(1) for m in mula_matches]
  _, tika_entries, _ = _attribute_tikas(dest_body, tika_title=tika_title)
  owned = [e["mula_j"] for e in tika_entries if e["mula_j"] is not None]
  last_tika_mula = max(owned) if owned else None
  start_idx = (last_tika_mula + 1) if last_tika_mula is not None else 0
  if start_idx >= len(mula_matches):
    logging.info("All mulas already have tikas in %s; nothing to fill.", dest_file)
    return
  blocks = _get_ordered_tika_blocks(commentary_file, tika_title=tika_title)
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
  usable_by_block = {}
  for (bi0, m0), (bi1, m1) in zip(bounds, bounds[1:]):
    seg = list(range(bi0 + 1, bi1))
    if not seg:
      continue
    seg_usable = _usable_in_range(seg, norm_prats, norm_mulas, m0, m1)
    for bi in seg:
      usable_by_block[bi] = seg_usable
    sub = []
    for i in seg:
      js = []
      for j in range(m0 + 1, m1):
        nm, starts = norm_mulas[j]
        if any(seg_usable[npr] and _pratika_in_norm_mula(npr, nm, starts)
               for npr in norm_prats[i]):
          js.append(j)
      sub.append(js)
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
        use = usable_by_block.get(bi, usable)
        nm, starts = norm_mulas[mj]
        for p, npr in zip(pratikas, norm_prats[bi]):
          if use.get(npr, False) and _pratika_in_norm_mula(npr, nm, starts):
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
  tika_fmt = _tika_fmt(tika_title)
  parts, prev = [], 0
  for idx, m in enumerate(mula_matches):
    s, e = m.span()
    nxt_start = mula_matches[idx + 1].start() if idx + 1 < len(mula_matches) else len(dest_body)
    between = dest_body[e:nxt_start]
    parts.append(dest_body[prev:e])
    if idx in to_insert:
      parts.append(tika_fmt % "\n\n".join(t.strip() for t in to_insert[idx]))
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
    new_body = new_body.rstrip() + "\n" + (tika_fmt % "\n\n".join(t.strip() for t in leftovers)) + "\n"
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


def verify_sentence_order(dest_file, commentary_file, start_string=None, tika_title="टीका"):
  """Verify ``tika_title`` sentence order strictly follows commentary order."""
  if _HAS_HELPERS:
    from doc_curation.md.content_processor.details import get_details as _get_details
    from doc_curation.md.file import MdFile as _MdFile
    dest_md = _MdFile(file_path=dest_file)
    metadata, dest_content = dest_md.read()
    tika_items = _get_details(dest_content, title=tika_title, metadata=metadata)
    tika_bodies = [det.content for _, det in tika_items]
  else:
    with open(dest_file, encoding="utf-8") as f:
      dest_raw = f.read()
    _, dest_content = _split_frontmatter(dest_raw)
    tika_bodies = [
      m.group(1) for m in
      re.finditer(_tika_re(tika_title), dest_content, flags=re.DOTALL)
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


def remove_commentary_blocks(dest_file, start_string, tika_title="टीका"):
  """Remove ``tika_title`` blocks from the one containing ``start_string`` to EOF."""
  with open(dest_file, encoding="utf-8") as f:
    dest_raw = f.read()
  dest_head, dest_body = _split_frontmatter(dest_raw)
  tika_pat = re.compile(_tika_re(tika_title), re.DOTALL)
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
  _mt, _entries, _sp = _attribute_tikas(dest_body, tika_title=tika_title)
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


def realign_TIkA_below_mUla(dest_file, start_string, commentary_file=None, tika_title="टीका"):
  """Realign misplaced ``tika_title`` blocks by reinserting them in pratika order."""
  import os
  import tempfile
  with open(dest_file, encoding="utf-8") as f:
    dest_raw = f.read()
  _, dest_body = _split_frontmatter(dest_raw)
  tika_pat = re.compile(_tika_re(tika_title), re.DOTALL)
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
      f.write("<details><summary>%s</summary>\n\n%s\n</details>\n\n" % (tika_title, body))
  logging.info("realign: extracted %d tika blocks to %s.", len(extracted), temp_path)
  remove_commentary_blocks(dest_file, start_string, tika_title=tika_title)
  if commentary_file is not None and os.path.exists(commentary_file):
    source = commentary_file
  else:
    source = temp_path
  logging.info("realign: reinserting into %s from %s.", dest_file, source)
  interleave_TIkA_below_mUla(dest_file, source, tika_title=tika_title)
  try:
    os.remove(temp_path)
  except OSError:
    pass
  return {"ok": True, "changed": True, "removed": len(extracted), "source": source}


if __name__ == '__main__':
  pass
  # remove_commentary_blocks(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md", start_string="उपरितनवाक्यापर्यालोचनां दर्शयति")
  interleave_TIkA_below_mUla(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/08_AkAshAdhikaraNam.md", commentary_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sudarshana-sUriH/shruta-prakAshikA/mUlam_rA/1/1/08_AkAshAdhikaraNam.md")
  # verify_sentence_order(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md", commentary_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sudarshana-sUriH/shruta-prakAshikA/mUlam_rA/1/1/06_AnandamayAdhikaraNam.md", start_string="उपरितनवाक्यापर्यालोचनां दर्शयति")
  # realign_TIkA_below_mUla(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md")