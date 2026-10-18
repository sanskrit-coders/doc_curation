import regex


# Short bracketed citation opening a sentence, e.g. `(छां.३.१२.१)` /
# `(तै. उ. २। ५। १)`: Devanagari/Latin, digits, ref punctuation, and it
# must contain a digit so ordinary parenthetical asides are left alone.
_leading_bracket_ref = regex.compile(
    r"^\((?=[^()]*[0-9\u0966-\u096F])"
    r"[A-Za-z\u0900-\u097F0-9\s\.\-–—।॥,]{1,60}\)[ \t]*")


def _approx_syllables(line):
  """Approximate svara/syllable count (svara-count clue for verse detection)."""
  try:
    from chandas.syllabize import get_syllables
    return len(get_syllables(line).split())
  except Exception:
    pass
  t = regex.sub(r"[^ऀ-ॣ]", "", line)
  t = regex.sub(r"[।॥]", "", t)
  if not t:
    return 0
  indep = len(regex.findall(r"[अ-औ]", t))
  signs = len(regex.findall(r"[ा-ौ]", t))
  inher = len(regex.findall(r"[क-ह](?![्ा-ौ])", t))
  return indep + signs + inher

def _is_verse_block(para):
  """True if a paragraph is an unquoted verse (do not split internally).

  Clues: ends with ``॥`` (optionally numbered), 2-4 lines each ending
  with ``।``/``॥``, no prose markers (``? ! ; :``), no brackets/refs,
  plus meter check via ``chandas`` when available, else svara-count
  equality.
  """
  lines = [l.strip() for l in para.strip().splitlines() if l.strip()]
  if len(lines) < 2 or len(lines) > 4:
    return False
  if not regex.search(r"॥\s*[०-९0-9\s\.\-–—]*॥?\s*$", lines[-1]):
    return False
  # Quoted verses are already kept intact via quote protection.
  if regex.search(r"[‘’“\"']", para):
    return False
  # Brackets/refs indicate prose with citations, not bare verse.
  if "(" in para or ")" in para or "[" in para:
    return False
  for l in lines:
    if regex.search(r"[?!;:—–]", l):
      return False
    if not regex.search(r"[।॥]\s*[०-९0-9\s\.\-–—]*[।॥]?\s*$", l):
      return False
  # Meter check via chandas when available.
  try:
    from chandas import to_pattern_lines, svat_identifier
    pl = to_pattern_lines(lines)
    res = svat_identifier.IdentifyFromPatternLines(pl)
    if res and res.get("exact"):
      return True
  except Exception:
    pass
  # Fallback: svara-count equality + minimum length.
  try:
    counts = [_approx_syllables(l) for l in lines]
  except Exception:
    return False
  if any(c < 8 for c in counts):
    return False
  if max(counts) / max(1, min(counts)) > 1.6:
    return False
  return True

def split_to_sentences(text):
  """Split Sanskrit prose (e.g. bhāṣya) into sentences.

  - Splits on ``।``, ``॥`` (with optional verse numbers like ``॥ १३ ॥``),
    ``?``, ``!`` and ``;`` occurring *outside* protected spans.
  - Does NOT split inside round/square brackets ``(...)``/``[...]``
    (reference numbers like ``(तै. उ. २। ५। १)`` contain ``।``),
    nor inside short quotations
    ``‘...’``/``'...'``/``“...”``/``"..."``
    (verses and śruti quotes like ``‘यदा ... विन्दते। ... भवति’``
    stay intact).
  - Does NOT split unquoted verse blocks (e.g. Gītā śloka on two
    lines ending in ``॥``): detected via ``॥``, svara-count equality
    and ``chandas`` meter identification when available.
  - Closing markdown emphasis markers (``**`` / ``__``) sitting right
    after a terminator stay glued to the sentence they close (e.g.
    ``**इति ... ॥१०॥**`` is not split into a sentence plus a stray
    ``**``).
  - A short bracketed citation opening a sentence (e.g.
    ``(छां.३.१२.१)``, ``(तै. उ. २। ५। १)``) is appended to the previous
    sentence, since it cites that sentence rather than starting a new one.
  - Returns list of stripped non-empty sentences, preserving original
    characters. Trailing fragment without terminator (e.g. lead-in
    ending in ``—``) is returned as-is so nothing is lost.

  :param text: Sanskrit text (possibly multi-paragraph).
  :return: list of sentences.
  """
  if not text:
    return []
  text = text.replace("\r\n", "\n").strip()
  if not text:
    return []

  # Respect paragraph breaks: split first on blank lines so lead-in
  # fragments ending in — / : and standalone verses stay separate,
  # then split each paragraph on terminators and flatten.
  paragraphs = [p for p in regex.split(r"\n\s*\n", text) if p.strip()]
  if len(paragraphs) > 1:
    out = []
    for p in paragraphs:
      out.extend(split_to_sentences(p))
    return out

  # Unquoted verse block: keep whole paragraph together.
  if _is_verse_block(text):
    return [text.strip()]

  # --- protected spans: (...) [...] and '...' "..." ‘...’ “...” ---
  spans = []

  def _add_spans(pattern, flags=0):
    try:
      for m in regex.finditer(pattern, text, flags=flags):
        if m.end() > m.start():
          spans.append((m.start(), m.end()))
    except Exception:
      pass

  # Balanced round brackets (refs); regex module supports recursion.
  try:
    _add_spans(r"\((?:[^()]|(?R))*\)", flags=regex.DOTALL)
  except Exception:
    _add_spans(r"\([^()]*\)", flags=regex.DOTALL)
  _add_spans(r"\[[^\[\]]*\]", flags=regex.DOTALL)
  # Curly/straight quotes (non-greedy, must close on same paragraph).
  _add_spans(r"‘[^’]*’", flags=regex.DOTALL)
  _add_spans(r"“[^”]*”", flags=regex.DOTALL)
  _add_spans(r"'[^'\n]*'", flags=0)
  _add_spans(r'"[^"\n]*"', flags=0)

  spans.sort()
  # Merge overlaps.
  merged = []
  for s, e in spans:
    if merged and s <= merged[-1][1]:
      merged[-1] = (merged[-1][0], max(merged[-1][1], e))
    else:
      merged.append((s, e))

  def _protected(pos):
    for s, e in merged:
      if s <= pos < e:
        return True
      if pos < s:
        return False
    return False

  # --- terminators outside protected spans ---
  # Double daṇḍa with optional number/range: ॥ १३ ॥, ॥१२ – १९ ॥, ॥.
  double_pat = regex.compile(r"॥\s*[०-९0-9\s\.\-–—]*॥|॥")
  single_pat = regex.compile(r"(?<!।)।(?!।)")
  punct_pat = regex.compile(r"[?!;]")

  bounds = []  # end offsets (exclusive of trailing spaces, inclusive of terminator)
  for m in double_pat.finditer(text):
    if not _protected(m.start()):
      bounds.append(("d", m.start(), m.end()))
  for m in single_pat.finditer(text):
    if not _protected(m.start()):
      # Skip if part of an already-recorded double-daṇḍa bound.
      skip = False
      for _, ds, de in bounds:
        if ds <= m.start() < de:
          skip = True
          break
      if not skip:
        bounds.append(("s", m.start(), m.end()))
  for m in punct_pat.finditer(text):
    if not _protected(m.start()):
      bounds.append(("p", m.start(), m.end()))
  bounds.sort(key=lambda x: x[1])

  close_emphasis = regex.compile(r"(?:\*\*|__)+")

  sentences = []
  start = 0
  for _, bs, be in bounds:
    # Include immediately following closing quotes/brackets if any
    # (e.g. `...?’, ...।’` is rare; terminator is usually outside).
    # Also absorb closing markdown emphasis markers (`**`, `__`) that
    # hug the terminator, so `...॥१०॥**` stays one sentence instead of
    # leaving a stray `**`.
    end = be
    m = close_emphasis.match(text, end)
    if m:
      end = m.end()
    # Do not consume the whitespace; slicing + strip handles it.
    sent = text[start:end].strip()
    # Attach leading whitespace-separated? No, keep as-is.
    if sent:
      sentences.append(sent)
    start = end
  tail = text[start:].strip()
  if tail:
    sentences.append(tail)

  # A short parenthesized reference opening a sentence (e.g.
  # `(छां.३.१२.१)`) cites the preceding sentence; glue it back there
  # instead of letting it start a new sentence.
  out = []
  for s in [x for x in sentences if x]:
    while out:
      m = _leading_bracket_ref.match(s)
      if not m:
        break
      out[-1] = out[-1] + " " + s[:m.end()].strip()
      s = s[m.end():].strip()
    if s:
      out.append(s)
  return out
