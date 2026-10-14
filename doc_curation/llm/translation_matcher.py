"""Sequential core↔translation alignment via batched LLM index mapping.

Provider-agnostic core: no baked-in assumptions about the text (no sūtra
numbers, no Devanagari handling).  All provider calls live in
``doc_curation.llm.opencode.translation_matcher`` and
``doc_curation.llm.gemini.translation_matcher``; this module only needs a
``generate_fn(prompt_text) -> str`` callable, so it also works with any
``LlmBackend.generate_content``.

Token-minimal protocol (single sweep, cursor-based):

1. The translation is split locally into numbered units (sentences);
   footnote definitions (``[^x]:``) stay atomic.
2. Core texts are walked in order in batches sized by character budget.
   Each LLM call sends the next unmapped core batch plus the next
   unmapped translation window starting exactly where the last confirmed
   mapping ended — position is carried by integer cursors, never by
   re-sending settled text.
 3. The model returns *positions only*: ``{"starts": {core_idx: en_idx},
    "skip": [...], "next_en": int}``.  Span ends are implied by the next
    start (the last core of a batch ends at ``next_en``), so output is a
    handful of integers instead of copied text (which also guarantees the
    takes stay verbatim).
 4. Each reply is validated (exact key set, ints in range, non-decreasing,
    first start == window start, every non-skipped core takes >= 1 unit,
    ``next_en`` sane); on failure only that
    batch is retried with the error appended.  After ``max_retries`` it
    raises rather than silently misaligning (cf. detail_chunker).
 5. Cores the model explicitly lists in ``"skip"`` (genuinely no English
    counterpart: colophons, verse fragments already covered by a
    neighbour's span, untranslated passages) get NO Translation block —
    only a ``<!-- TRANSLATION-SKIPPED -->`` marker — so output never
    contains empty Translation blocks; skips are reported in the Appendix.
 6. Scope bounds (``end_file`` / ``end_after``) truncate the stream when
    the md file's scope ends before the translation directory does, so
    the final batch is never forced to swallow foreign tail material.
    Oversized takes and overshooting final batches are logged as
    warnings (free diagnostics, no extra LLM calls).
"""

import json
import logging
import os

import regex

from doc_curation.md.content_processor.details.maker import (
  translation_details)

# Generic English abbreviations (no domain knowledge baked in).
_ABBREVS = (
  "Up", "Br", "Cḥ", "Ch", "Taitt", "Tait", "Bha", "Sū", "Su",
  "Ṛk", "Rk", "Kau", "Kaus", "Mu", "Mun", "Mund", "Śve", "Sve", "Sv",
  "Pra", "Prau", "Ke", "Kena", "Ka", "Kat", "Katha", "Kh", "Brah",
  "Ār", "Ar", "Smṛ", "Smr", "Gītā", "Gita", "Chā", "Cha", "Śat", "Sat",
  "Tai", "Brh", "Samh", "Sam",
  "Mr", "Mrs", "Ms", "Dr", "Prof", "St", "vs", "etc", "viz", "cf",
  "pp", "vol", "trans", "ed", "sec", "fig", "ch", "e", "i",
)


def _split_units_with_spans(body):
  """[(unit_text, start, end)] with raw offsets into ``body`` (LF newlines).

  Unit TEXTS are byte-identical to :func:`_split_translation_units` on
  the same input; spans cover the stripped unit text so tag insertion at
  a span end never touches content.  ``\\r`` input is unsupported here
  (callers fall back); all other logic — footnote defs kept whole,
  dangling line-wrap merge, abbreviation/enumeration/paren guards —
  mirrors the text splitter exactly.
  """
  # Paragraphs with exact spans (blank-line runs are separators) —
  # EXCEPT a blank line inside (...) whose paren closes within LOOKAHEAD
  # chars (refs like "(Br̥. Up.\n\nIII, 7, 22)" wrap across lines; splitting
  # there shreds them into garbage fragments).  An unbalanced paren (e.g.
  # Thibaut's unclosed "(cp.") still breaks normally — swallowing the rest
  # of the file would be far worse.  A stray ")" at depth 0 is ignored.
  LOOKAHEAD = 400
  paras = []  # (text, start, end), text unstripped
  pstart, depth, i, n = 0, 0, 0, len(body)
  while i < n:
    ch = body[i]
    if ch == "(":
      depth += 1
      i += 1
    elif ch == ")":
      depth = max(0, depth - 1)
      i += 1
    elif ch == "\n":
      m = regex.match(r"\n\s*\n", body[i:])
      if not m:
        i += 1
        continue
      split_here = depth == 0
      if not split_here:
        # Inside parens: suppress only if they balance soon.
        d, j, closed = depth, i, False
        lim = min(n, i + LOOKAHEAD)
        while j < lim:
          if body[j] == "(":
            d += 1
          elif body[j] == ")":
            d -= 1
            if d == depth - 1:
              closed = True
              break
          j += 1
        split_here = not closed
      if split_here:
        if body[pstart:i].strip():
          paras.append((body[pstart:i], pstart, i))
        i += len(m.group(0))
        pstart = i
      else:
        i += 1
    else:
      i += 1
  if body[pstart:].strip():
    paras.append((body[pstart:], pstart, n))
  # Normalize to stripped text with trimmed span.
  normed = []
  for part, s, e in paras:
    stripped = part.strip()
    lead = len(part) - len(part.lstrip())
    normed.append((stripped, s + lead, e - (len(part) - len(part.rstrip()))))
  paras = normed

  # Footnote defs stay whole; dangling (unterminated) paras merge forward.
  groups = []  # ("mix", [(text, base)]) or ("def", [(text, base)])
  buf_text, buf_base = [], []
  for text, start, _ in paras:
    if regex.match(r"\[\^[^\]]+\]:", text):
      if buf_text:
        groups.append(("mix", list(zip(buf_text, buf_base))))
        buf_text, buf_base = [], []
      groups.append(("def", [(text, start)]))
      continue
    buf_text.append(text)
    buf_base.append(start)
    if regex.search(r"[.?!;:][\"'’”\)\]]?\s*$", " ".join(buf_text)):
      groups.append(("mix", list(zip(buf_text, buf_base))))
      buf_text, buf_base = [], []
  if buf_text:
    groups.append(("mix", list(zip(buf_text, buf_base))))

  out = []
  for kind, items in groups:
    if kind == "def":
      (text, start), = items
      out.append((regex.sub(r"\s+", " ", text),
                  start, start + len(text)))
      continue
    # Logical stream = stripped components joined by single spaces.
    runs = []  # (logical_start, raw_start, length)
    logical_parts, loff = [], 0
    for text, base in items:
      logical_parts.append(text)
      runs.append((loff, base, len(text)))
      loff += len(text) + 1  # +1 join space
    logical = " ".join(logical_parts)

    def _to_raw(lpos):
      # Map a logical offset to raw; join-spaces map to the left end.
      for ls, rs, ln in runs:
        if lpos < ls + ln:
          return rs + (lpos - ls)
      rs, ln = runs[-1][1], runs[-1][2]
      return rs + ln

    # Protected paren spans (same assumption as before: no nesting).
    prot = []
    for m in regex.finditer(r"\([^()]*\)", logical):
      prot.append(m.span())

    def _in_prot(p):
      return any(s <= p < e for s, e in prot)

    # Candidate terminators with the same guards as the text splitter.
    # As before, a split is suppressed when the starter begins with `(`
    # (a masked paren used to break the starter lookahead there, gluing
    # refs like `(III, 13, 7)` to the preceding sentence).
    cuts = []  # logical offsets just PAST each terminator char
    for m in regex.finditer(r"[.?!;]", logical):
      p = m.start()
      if _in_prot(p):
        continue
      ch = logical[p]
      if ch == ".":
        # Abbreviation guard.
        hit = False
        for ab in _ABBREVS:
          if regex.search(r"\b%s\.$" % regex.escape(ab),
                          logical[max(0, p - 8):p + 1]):
            hit = True
            break
        if hit:
          continue
        # Enumeration guard: start or post-terminator digits.
        pre = logical[max(0, p - 14):p + 1]
        if regex.search(r"(?:^|[.?!]\s+)\d{1,3}\.$", pre):
          continue
      # Starter lookahead (identical to text splitter).
      rest = logical[p + 1:]
      ws = regex.match(r"\s+", rest)
      after = rest[len(ws.group(0)):] if ws else rest
      if not after:
        cuts.append(p + 1)
        continue
      if after.startswith("("):
        continue
      if regex.match(r"[\"'‘“\(\[]?[A-Z0-9\[\(]", after):
        cuts.append(p + 1)
    # Assemble units; text = collapsed raw span (== text-splitter output).
    prev = 0
    for c in cuts:
      seg_raw_s = _to_raw(prev)
      seg_raw_e = _to_raw(c)
      seg_text = regex.sub(r"\s+", " ", logical[prev:c].strip())
      if seg_text:
        # Trim span to non-whitespace (leading/trailing ws collapses away).
        a = prev
        while a < c and logical[a] in " \t\n":
          a += 1
        b = c
        while b > a and logical[b - 1] in " \t\n":
          b -= 1
        out.append((seg_text, _to_raw(a), _to_raw(b)))
      prev = c
    tail_text = regex.sub(r"\s+", " ", logical[prev:].strip())
    if tail_text:
      a = prev
      while a < len(logical) and logical[a] in " \t\n":
        a += 1
      out.append((tail_text, _to_raw(a), _to_raw(len(logical))))
  return out


def _split_translation_units(translation_text):
  """Split translation into numbered sentence units (local, no LLM).

  Footnote definitions stay whole; dangling line-wrap paragraphs (no
  terminal punctuation) are merged with the next paragraph so wraps
  don't become phantom sentences.  Units with no word character at all
  (stray separators like ``…`` or ``--``) are dropped: they carry no
  content and would otherwise become degenerate one-glyph takes.
  """
  text = (translation_text or "").replace("\r\n", "\n")
  return [t for t, _, _ in _split_units_with_spans(text)
          if regex.search(r"\w", t, flags=regex.UNICODE)]


def _one_line(s, limit=None):
  s = regex.sub(r"\s+", " ", (s or "").strip())
  return s if limit is None or len(s) <= limit else s


def _prompt_for_batch(core_batch, c_start, en_window, e_start,
                      total_core, total_en, prev_unit=None):
  core_lines = "\n".join(
    f"core[{c_start + i}]: {s}" for i, s in enumerate(core_batch))
  en_lines = "\n".join(
    f"tr[{e_start + j}]: {s}" for j, s in enumerate(en_window))
  anchor = (f"\nThe previously consumed sentence tr[{e_start - 1}] was: "
            f"{prev_unit}\nYour first span must continue AFTER it.\n"
            if prev_unit else "")
  c_end = c_start + len(core_batch)
  pace = round(c_end * total_en / max(total_core, 1))
  pacing = (f"\nPACING: after this batch {c_end} of {total_core} cores will "
            f"be placed; you should then have consumed roughly {pace} of "
            f"{total_en} translation sentences. If your next_en falls far "
            f"short of that, you are starving later cores — widen spans "
            f"and skip less. (A tight verse cluster may locally consume "
            f"less; do not overcorrect for one.)\n")
  return f"""Align the core texts below, IN ORDER, with the translation sentences below. This continues a longer alignment: core texts 0..{total_core - 1} map into translation sentences 0..{total_en - 1}; everything before core {c_start} / sentence {e_start} is already fixed. Match the translation sentences to the cores in the order they appear: read each core text, find where its English rendering begins, and continue from there.
{anchor}{pacing}
RULES:
- Partition, no gaps, no overlaps: the spans of the taken cores tile translation sentences {e_start}..next_en in order (core i's span runs up to the next core's start; the last taken core's span runs up to next_en). You may stop (next_en) before the window end; leftover sentences carry over to the next batch.
- Every core EITHER takes at least one translation sentence OR is named in "skip". A core with an empty span that is NOT in "skip" is invalid.
- Skip ONLY cores with genuinely no English counterpart here: colophons like 'इति ...', verse fragments whose content a neighbouring core's span already covers, or passages the translation demonstrably does not render. Dumping hard sentences into "skip" to avoid reading them is the failure mode to avoid: place each core deliberately against the window.

CORE TEXTS:
{core_lines}

TRANSLATION SENTENCES:
{en_lines}

Reply with ONLY this JSON (no prose, no fences needed but fences allowed):
{{"starts": {{"{c_start}": {e_start}, ...}}, "skip": [], "next_en": <int>}}
- "starts" must contain exactly the core indices {c_start}..{c_start + len(core_batch) - 1}, each mapping to the FIRST translation sentence of its span (integer in [{e_start}, {e_start + len(en_window)})).
- Starts must be non-decreasing; the first start must equal {e_start}.
- "skip": core indices (subset of the batch) whose span is EMPTY — i.e. their start repeats the next boundary, consuming nothing. Use only for the genuine no-counterpart cases above.
- "next_en" is the first translation index AFTER this batch's last span (integer in [last start, {e_start + len(en_window)}])."""


def _parse_mapping(reply):
  """Extract (starts, skip, next_en) from model output.

  ``skip`` is optional in the reply (defaults to ``[]``): core indices
  with genuinely no counterpart, whose span must be empty.
  """
  text = (reply or "").strip()
  m = regex.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=regex.DOTALL)
  candidate = m.group(1) if m else text
  try:
    data = json.loads(candidate)
  except ValueError:
    # Fall back to the outermost {...} span.
    m = regex.search(r"\{.*\}", text, flags=regex.DOTALL)
    if not m:
      raise ValueError(f"no JSON object found in reply: {text[:200]!r}")
    data = json.loads(m.group(0))
  if not isinstance(data, dict) or not isinstance(data.get("starts"), dict):
    raise ValueError(f"reply lacks 'starts' dict: {text[:200]!r}")
  starts, next_en = data["starts"], data.get("next_en")
  if next_en is None:
    raise ValueError(f"reply lacks 'next_en': {text[:200]!r}")
  raw_skip = data.get("skip", [])
  if raw_skip is None:
    raw_skip = []
  if not isinstance(raw_skip, list):
    raise ValueError(f"'skip' must be a list of core indices: {text[:200]!r}")
  try:
    skip = sorted(set(int(v) for v in raw_skip))
  except (TypeError, ValueError):
    raise ValueError("'skip' entries must be integers")
  return starts, skip, next_en


def _validate_batch(starts, skip, next_en, c_start, c_end, e_start, e_end,
                    is_last, total_en):
  """Normalize to ({int: int}, [int], int), or raise ValueError.

  Every non-skipped core must take a non-empty span; every skipped core
  must take an empty span.  Lazy empty spans (not in ``skip``) are
  rejected so the model cannot skim hard sentences.
  """
  try:
    norm = {int(k): int(v) for k, v in starts.items()}
  except (TypeError, ValueError):
    raise ValueError("starts keys/values must be integers")
  want = list(range(c_start, c_end))
  if sorted(norm) != want:
    raise ValueError(
      f"starts keys {sorted(norm)} != expected core range {want}")
  skip_set = set(skip)
  if not skip_set <= set(want):
    raise ValueError(f"skip {skip} outside batch core range {want}")
  if not isinstance(next_en, int) or isinstance(next_en, bool):
    raise ValueError("next_en must be an integer")
  prev = None
  for i in want:
    v = norm[i]
    if not e_start <= v <= e_end:
      raise ValueError(f"core {i} start {v} outside window [{e_start}, {e_end}]")
    if prev is not None and v < prev:
      raise ValueError(f"starts not non-decreasing at core {i}")
    prev = v
  if norm[want[0]] != e_start:
    raise ValueError(
      f"first start {norm[want[0]]} != window start {e_start} (gap)")
  for i in want:
    end_i = norm[i + 1] if i + 1 < c_end else next_en
    width = end_i - norm[i]
    if i in skip_set:
      if width != 0:
        raise ValueError(
          f"core {i} is skipped but takes {width} sentence(s); "
          "skipped cores must have empty spans")
    elif width < 1:
      raise ValueError(
        f"core {i} has an empty span but is not in 'skip'; either give it "
        "at least one sentence or name it in 'skip' with genuine cause")
  lo, hi = norm[want[-1]], e_end
  if not lo <= next_en <= hi:
    raise ValueError(f"next_en {next_en} outside [{lo}, {hi}]")
  if is_last and next_en != total_en:
    raise ValueError(f"last batch next_en {next_en} != {total_en} (drop)")
  if (not is_last and e_start < total_en and next_en <= e_start
      and len(skip_set) < len(want)):
    raise ValueError(
      f"batch consumed no translation units (next_en {next_en} <= window "
      f"start {e_start} with {total_en - e_start} units left); attach the "
      "window head to the batch instead of stalling")
  return norm, sorted(skip_set), next_en


def seq_match_texts_to_translation(
    texts, translation_text, generate_fn,
    batch_core_chars=800, window_en_chars=8000, max_retries=2):
  """Align core texts to translation spans via batched LLM index mapping.

  :param texts: core sentences in order (any language).
  :param translation_text: full translation text.
  :param generate_fn: ``fn(prompt_text) -> str`` (e.g. wrapping
    ``LlmBackend.generate_content``); called once per batch plus
    retries of failed batches only.
  :param batch_core_chars: soft budget for core text per call.
  :param window_en_chars: cap for the translation window per call.
  :param max_retries: retries of an invalid batch reply (with the
    validation error appended); then RuntimeError.
  :return: list of translation strings, ``len == len(texts)``; each is
    the verbatim window sentences joined with single spaces (``""``
    for empty spans).
  """
  texts = [regex.sub(r"\s+", " ", (t or "").strip()) for t in (texts or [])]
  n = len(texts)
  if n == 0:
    return []
  units = _split_translation_units(translation_text or "")
  # Footnote definitions are metadata, not sequence positions: excluded
  # from the sweep (look them up by marker for Notes blocks instead).
  en = [u for u in units if not regex.match(r"\[\^[^\]]+\]:", u)]
  m = len(en)
  if m == 0:
    return ["" for _ in texts]
  if n == 1:
    return [regex.sub(r"\s+", " ", (translation_text or "").strip())]

  # Precompute char lengths for budgeting.
  core_lens = [len(t) for t in texts]
  en_lens = [len(u) for u in en]
  total_en_chars = sum(en_lens) or 1

  out_takes = {}  # core idx -> (start, end) with end exclusive
  c, e = 0, 0
  while c < n:
    if e >= m:
      # Translation exhausted: remaining cores map to empty spans,
      # no LLM call needed.
      logging.info("matcher tail cores[%d:%d] exhausted "
                   "(en cursor %d >= %d units): %d skipped, no LLM call",
                   c, n, e, m, n - c)
      for i in range(c, n):
        out_takes[i] = (m, m)
      break
    # Core batch within budget (at least one text).
    c_end = c + 1
    while (c_end < n
           and sum(core_lens[c:c_end + 1]) <= batch_core_chars):
      c_end += 1
    e_end = _plan_window(sum(core_lens[c:c_end]), sum(core_lens[c:]),
                         en_lens, e, m, window_en_chars)
    is_last = (c_end == n)
    if is_last:
      e_end = m  # final batch must cover the tail: no drops allowed
    anchor = regex.sub(r"\s+", " ", en[e - 1])[:300] if e > 0 else None
    norm, _skipped, next_en = _map_batch(
      texts[c:c_end], c, en[e:e_end], e, n, m, generate_fn, max_retries,
      prev_unit=anchor)
    for i in range(c, c_end):
      s = norm[i]
      e_next = norm[i + 1] if i + 1 < c_end else next_en
      out_takes[i] = (s, e_next)
    c, e = c_end, next_en

  out = []
  for i in range(n):
    s, e_next = out_takes[i]
    out.append(" ".join(en[s:e_next]))
  return out


def _plan_window(batch_chars, rem_core_chars, en_lens, e, m,
                 window_en_chars):
  """End index (exclusive) of the EN window for a batch.

  Proportional to the batch's share of remaining core text, plus
  headroom, capped; always ≥1 unit.
  """
  rem_core = rem_core_chars or 1
  rem_en = sum(en_lens[e:]) or 1
  want = int(batch_chars * rem_en / rem_core) + 1500
  e_end = e + 1
  while (e_end < m
         and sum(en_lens[e:e_end + 1]) <= min(want, window_en_chars)):
    e_end += 1
  return e_end


def _map_batch(core_batch, c, en_window, e, n, m, generate_fn, max_retries,
               prev_unit=None):
  """Map one batch; returns (norm {core: en_start}, skipped [core], next_en).

  Retries narrowly. ``prev_unit`` (the already-consumed sentence just
  before this window, if any) is shown to the model as a continuity
  anchor; it is never re-sent as mappable text.
  """
  prompt = _prompt_for_batch(core_batch, c, en_window, e, n, m,
                             prev_unit=prev_unit)
  reply, err = None, None
  for _ in range(max_retries + 1):
    try:
      reply = generate_fn(prompt if err is None else prompt + (
        f"\n\nYour previous reply was invalid: {err} "
        "Reply again with ONLY the corrected JSON."))
      starts, skip, next_en = _parse_mapping(reply)
      norm, skipped, next_en = _validate_batch(
        starts, skip, next_en, c, c + len(core_batch), e, e + len(en_window),
        c + len(core_batch) == n, m)
      # Free diagnostics (no extra LLM calls): flag pile-ups while the
      # cursors still tell where they happened.
      widths = [((norm[c + k + 1] if k + 1 < len(core_batch) else next_en)
                 - norm[c + k]) for k in range(len(core_batch))]
      widest = max(widths) if widths else 0
      if widest > 10:
        k = widths.index(widest)
        logging.warning(
          "matcher batch core[%d:%d]: core %d takes %d units "
          "(en[%d:%d]) — possible pile-up/overshoot, verify placement",
          c, c + len(core_batch), c + k, widest, norm[c + k],
          norm[c + k] + widest)
      if c + len(core_batch) == n and next_en - e > max(10, m // 2):
        logging.warning(
          "matcher batch core[%d:%d]: final batch consumes %d of %d "
          "units — the stream likely overshoots the file's scope "
          "(consider end_file/end_after)", c, c + len(core_batch),
          next_en - e, m)
      logging.info("matcher batch core[%d:%d] -> en[%d:%d] (%d skipped)",
                   c, c + len(core_batch), e, next_en, len(skipped))
      return norm, skipped, next_en
    except ValueError as ex:
      err = str(ex)
      logging.warning("matcher batch [%d,%d) invalid (%s), retrying",
                      c, c + len(core_batch), err)
  raise RuntimeError(
    f"matcher batch core[{c}:{c + len(core_batch)}] failed validation "
    f"{max_retries + 1}x; last error: {err}")



def _normalize_anchor(s):
  """Collapse whitespace + casefold for anchor matching."""
  return regex.sub(r"\s+", " ", s or "").strip().casefold()


def _match_end_anchor(en, end_after):
  """Exclusive end index (count) of the stream for an ``end_after`` anchor.

  The anchor is a distinctive phrase from the last in-scope translation
  unit (any script: verse fragment, section heading, colophon echo).  It
  is matched locally by substring search — no LLM, no domain knowledge
  in code.  Returns ``match_idx + 1`` so the stream truncates right
  after the anchor unit.  Zero or multiple matches raise ValueError
  (fail-stop: callers pass a longer anchor).
  """
  want = _normalize_anchor(end_after)
  if not want:
    raise ValueError("end_after anchor is empty")
  hits = [i for i, u in enumerate(en) if want in _normalize_anchor(u)]
  if not hits:
    raise ValueError(
      f"end_after anchor {end_after!r} matches no translation unit "
      f"(stream has {len(en)} units)")
  if len(hits) > 1:
    preview = "; ".join(
      f"{i}: {en[i][:60]!r}" for i in hits[:5])
    raise ValueError(
      f"end_after anchor {end_after!r} matches {len(hits)} units "
      f"({preview}); pass a longer, unambiguous anchor")
  return hits[0] + 1


def _translation_files_sorted(translation_path, start_file=None,
                              end_file=None):
  """Ordered translation file paths from a dir or a single file.

  :param translation_path: directory of translation ``*.md`` files, or a
    single ``*.md`` file path.
  :param start_file: basename to start from (e.g. ``"12.md"``); ``None``
    starts with the first file.  Uses
    :func:`doc_curation.md.library.get_md_files_from_path` (skips
    dotfiles and ``_``-prefixed files).
  :param end_file: basename to stop at (inclusive); ``None`` runs to the
    last file.  Bounds the translation stream when the md file's scope
    ends before the directory does (e.g. an adhikaraṇa file ending at
    sūtra 22 while the directory runs on to later sūtras) — without it
    the final batch would be forced to swallow foreign tail material.
  :return: list of absolute file paths, this file and later siblings.
  """
  from doc_curation.md.library import get_md_files_from_path

  if os.path.isfile(translation_path):
    paths = [os.path.abspath(translation_path)]
  else:
    md_files = get_md_files_from_path(
      dir_path=translation_path,
      file_name_filter=lambda x: not os.path.basename(str(x)).startswith((".", "_")))
    paths = sorted(
      {os.path.abspath(str(mf.file_path)) for mf in md_files},
      key=lambda s: [int(p) if p.isdigit() else p
                     for p in regex.split(r"(\d+)", s)])
  if start_file is not None:
    names = [os.path.basename(p) for p in paths]
    if start_file not in names:
      raise ValueError(
        f"start_file {start_file!r} not found in {translation_path}; "
        f"available: {names}")
    paths = paths[names.index(start_file):]
  if end_file is not None:
    names = [os.path.basename(p) for p in paths]
    if end_file not in names:
      raise ValueError(
        f"end_file {end_file!r} not found in {translation_path}; "
        f"available: {names}")
    paths = paths[:names.index(end_file) + 1]
  return paths


def _continue_marker(done_core, total_core, next_en, total_en,
                     total_paras, files):
  return ("<!-- TRANSLATION-MATCH-CONTINUE "
          f"done_core={done_core} total_core={total_core} "
          f"next_en={next_en} total_en={total_en} "
          f"total_paras={total_paras} files={','.join(files)} -->")


def _parse_continue_marker(text):
  """(done_core, next_en, total_core, total_en, total_paras, files) or None."""
  m = regex.search(
    r"<!--\s*TRANSLATION-MATCH-CONTINUE\s+done_core=(\d+)\s+"
    r"total_core=(\d+)\s+next_en=(\d+)\s+total_en=(\d+)"
    r"(?:\s+total_paras=(\d+))?(?:\s+files=([^>]*?))?\s*-->",
    text)
  if not m:
    return None
  files = [f for f in (m.group(6) or "").split(",") if f]
  paras = int(m.group(5)) if m.group(5) is not None else None
  return (int(m.group(1)), int(m.group(3)), int(m.group(2)),
          int(m.group(4)), paras, files)


def _todo_tokens(cur_todo):
  """[(kind, text)] with kind in details/sep/bare, details never chopped."""
  out = []
  for seg in regex.split(r"(<details\b.*?</details>)", cur_todo,
                         flags=regex.DOTALL):
    if not seg:
      continue
    if seg.strip().startswith("<details"):
      out.append(("details", seg))
      continue
    for tok in regex.split(r"(\n\s*\n)", seg):
      if not tok:
        continue
      if regex.fullmatch(r"\n\s*\n", tok):
        out.append(("sep", tok))
      elif not tok.strip():
        out.append(("sep", tok))
      else:
        out.append(("bare", tok))
  return out


def _split_header_rest(text):
  """(header, rest): header runs through the last वैैयासिक line..."""
  idxs = [m.start() for m in regex.finditer("वैयासिकन्यायमाला", text)]
  if idxs:
    line_end = text.find("\n", idxs[-1])
    cut = len(text) if line_end == -1 else line_end + 1
    return text[:cut], text[cut:]
  m = regex.match(r"^\+\+\+.*?\+\+\+\n?", text, flags=regex.DOTALL)
  header = m.group(0) if m else ""
  return header, text[len(header):]


def _bare_paras(rest):
  """[(seg_index, para_text)] bare paragraphs outside <details> blocks."""
  segments = regex.split(r"(<details\b.*?</details>)", rest, flags=regex.DOTALL)
  paras = []
  for si, seg in enumerate(segments):
    if seg.startswith("<details"):
      continue
    for para in regex.split(r"\n\s*\n", seg):
      if para.strip():
        paras.append((si, para.strip()))
  return segments, paras


def _has_bare_devanagari(rest):
  bare = regex.sub(r"<details\b.*?</details>", "", rest, flags=regex.DOTALL)
  # Skip markdown headings and `--` attribution lines: like
  # generic_sanskrit_vipra_mUla, those are never sentences to wrap.
  bare = regex.sub(r"(?m)^\s*(#{1,6}\s.*|--.*)$", "", bare)
  return bool(regex.search(r"[\u0900-\u097F]{2,}", bare))


def _load_translation_units(translation_paths):
  """{path: (frontmatter, [body units])} reread fresh from disk every call.

  Any position-tag line is stripped (it is metadata, not content).
  """
  out = {}
  for path in translation_paths:
    with open(path, encoding="utf-8") as f:
      raw = f.read()
    m = regex.match(r"^(\+\+\+.*?\+\+\+)\n?", raw, flags=regex.DOTALL)
    front = m.group(1) + "\n\n" if m else ""
    body = raw[len(m.group(0)) if m else 0:]
    # Strip the position tag BEFORE splitting: otherwise a dangling junk
    # para (e.g. "…") merges forward with the tag line, smuggles \w into
    # the unit past the junk filter, and survives _strip_pos_tag as a
    # contentless husk (a future degenerate take).
    body = body.replace(TRANSLATION_POS_TAG, "")
    out[path] = (front, _strip_pos_tag(_split_translation_units(body)))
  return out


def _flatten_units(files_units, used_paths):
  """(en_stream (non-def units), positions [(path, unit_idx)])."""
  en, pos = [], []
  for path in used_paths:
    _, units = files_units[path]
    for ui, u in enumerate(units):
      if regex.match(r"\[\^[^\]]+\]:", u):
        continue
      en.append(u)
      pos.append((path, ui))
  return en, pos


def _footnote_defs_from_units(all_units):
  defs = {}
  for u in all_units:
    m = regex.match(r"(\[\^[^\]]+\]):", u)
    if m:
      defs.setdefault(m.group(1), u)
  return defs


def _has_unmapped_mula(text):
  """True if some मूलम् block lacks a Translation block directly above."""
  return any(not mapped for _, _, mapped in _mula_entries(text))


def _split_leading_mapped(text):
  """(done_head, todo_tail): cut after the leading run of mapped मूलम् blocks.

  Checkpoints move mapped blocks before the progress marker so the todo
  region always starts at the first unmapped sentence; resume counting
  then needs no skip logic in the steady state.
  """
  entries = _mula_entries(text)
  run = 0
  while run < len(entries) and entries[run][2]:
    run += 1
  if run == 0:
    return "", text
  seen = 0
  for m in regex.finditer(r"<details\b.*?</details>", text,
                          flags=regex.DOTALL):
    title = regex.search(r"<summary>(.*?)</summary>", m.group(0),
                         flags=regex.DOTALL)
    if title and title.group(1).strip() == "मूलम्":
      seen += 1
      if seen == run:
        return text[:m.end()], text[m.end():]
  return text, ""  # unreachable when entries are consistent


#: Position tag written into translation files: everything before it is
#: consumed; the next LLM input starts right after it.  Always kept on
#: blank-line boundaries so sentence splitting is unaffected.  Consumed
#: heads and footnote defs are never deleted or reordered — the tag is
#: purely inserted (or moved).
TRANSLATION_POS_TAG = "<!-- TRANSLATION-MATCH-POS -->"


def _strip_pos_tag(units):
  """Drop the position tag from split units (whole or glued-in)."""
  out = []
  for u in units:
    if u.strip() == TRANSLATION_POS_TAG:
      continue
    if TRANSLATION_POS_TAG in u:
      u = u.replace(TRANSLATION_POS_TAG, "").strip()
      if not u:
        continue
    out.append(u)
  return out


def _update_pos_tags(files_units, used_paths, next_en):
  """Advance position tags to the global ``next_en`` cursor.

  Returns basenames of files whose tag moved.  Files fully before the
  cursor get the tag at end, the file holding it after its consumed
  units, later files keep/omit theirs (tag at 0 is written explicitly
  so the next input position is unambiguous everywhere).
  """
  bounds, start = {}, 0
  for path in used_paths:
    _, units = files_units[path]
    cnt = sum(1 for u in units if not regex.match(r"\[\^[^\]]+\]:", u))
    bounds[path] = (start, start + cnt)
    start += cnt
  changed = []
  for path in used_paths:
    s, e = bounds[path]
    new_pos = min(max(next_en - s, 0), e - s)
    _, units = files_units[path]
    out, seen, placed = [], 0, new_pos <= 0
    if placed:
      out.append(TRANSLATION_POS_TAG)
    for u in units:
      out.append(u)
      if not placed and not regex.match(r"\[\^[^\]]+\]:", u):
        seen += 1
        if seen >= new_pos:
          out.append(TRANSLATION_POS_TAG)
          placed = True
    if not placed:
      out.append(TRANSLATION_POS_TAG)
    old = "\n\n".join(units)
    new = "\n\n".join(out)
    if old != new:
      front, _ = files_units[path]
      _write_translation_file(path, front, out)
      changed.append(os.path.basename(path))
  return changed


def _appendix_text(total_core, total_paras, used_files, done_text, tagged,
                   scope=None):
  """Appendix block; counts Notes/skipped blocks in done_text."""
  notes = len(regex.findall(r"<summary>Translation - Notes</summary>",
                            done_text))
  skipped = done_text.count(TRANSLATION_SKIPPED_TAG)
  empty = len(regex.findall(
    r"<summary>Translation</summary>\n\n\s*</details>", done_text))
  paras = total_paras if total_paras is not None else "?"
  text = (
    "<details><summary>Appendix</summary>\n\n"
    f"- {total_core} sentences from {paras} paragraphs interleaved "
    f"with translations from [{', '.join(used_files)}].\n"
    f"- {notes} Translation - Notes blocks; {skipped} skipped "
    "(no counterpart found).\n")
  if scope:
    text += f"- Scope: {scope}.\n"
  if empty:
    text += (f"- WARNING: {empty} empty Translation blocks (unexpected; "
             "skips should leave no block behind).\n")
  if tagged:
    text += ("position tags advanced in: " + ", ".join(tagged) + ".\n")
  return text + "</details>\n"


def _write_translation_file(path, frontmatter, units):
  """Rewrite one translation file (frontmatter + blank-joined units)."""
  body = "\n\n".join(units).strip() + "\n" if units else ""
  tmp = path + ".tmp"
  with open(tmp, "w", encoding="utf-8") as f:
    f.write(frontmatter + body)
  os.replace(tmp, path)


def _atomic_write(path, content):
  tmp = path + ".tmp"
  with open(tmp, "w", encoding="utf-8") as f:
    f.write(content)
  os.replace(tmp, path)


def _mula_blocks(rest):
  """[(block_text, sentence)] for each <details>..मूलम्..</details>, in order."""
  return [(tag, s) for tag, s, _ in _mula_entries(rest)]


#: Skip marker written directly above a मूलम् block whose core the model
#: explicitly skipped (genuinely no English counterpart).  Skipped blocks
#: count as done (never get Translation blocks, never re-enter the todo),
#: and are reported in the Appendix.  ASCII-only, so bare-Sanskrit guards
#: ignore it.
TRANSLATION_SKIPPED_TAG = "<!-- TRANSLATION-SKIPPED -->"


def _mula_entries(text):
  """[(block_text, sentence, mapped)] for each मूलम् block, in order.

  ``mapped`` is True when a Translation [/ Notes] block sits directly
  above (blank-line separated), or when a ``TRANSLATION-SKIPPED`` marker
  does (skipped cores are done: no Translation block is ever inserted
  for them).  Mapped blocks may linger in the todo
  region (checkpoints never move them); callers skip the leading mapped
  run so batches always start at the first unmapped sentence.
  """
  all_blocks = list(regex.finditer(r"<details\b.*?</details>", text,
                                   flags=regex.DOTALL))
  out = []
  for i, m in enumerate(all_blocks):
    tag = m.group(0)
    title = regex.search(r"<summary>(.*?)</summary>", tag, flags=regex.DOTALL)
    if not (title and title.group(1).strip() == "मूलम्"):
      continue
    body = regex.sub(r"^.*?</summary>", "", tag, flags=regex.DOTALL)
    body = regex.sub(r"</details>\s*$", "", body, flags=regex.DOTALL)
    prev = all_blocks[i - 1] if i > 0 else None
    pre = text[prev.end() if prev is not None else 0:m.start()]
    skipped_here = TRANSLATION_SKIPPED_TAG in pre
    pre_wo = pre.replace(TRANSLATION_SKIPPED_TAG, "")
    mapped = False
    if regex.fullmatch(r"\s*", pre_wo or ""):
      if prev is not None:
        ptitle = regex.search(r"<summary>(.*?)</summary>", prev.group(0),
                              flags=regex.DOTALL)
        mapped = (ptitle is not None
                  and ptitle.group(1).strip() in (
                    "Translation", "Translation - Notes"))
      mapped = mapped or skipped_here
    out.append((tag, body.strip(), mapped))
  return out


def _finalize_appendix(md_path, total_core, total_paras, used_files,
                       tagged):
  """Strip any marker, verify fully mapped, append Appendix. Returns summary."""
  with open(md_path, encoding="utf-8") as f:
    cur_text = f.read()
  cur_header, cur_rest = _split_header_rest(cur_text)
  cur_rest_nomarker = regex.sub(
    r"<!--\s*TRANSLATION-MATCH-CONTINUE.*?-->", "", cur_rest,
    flags=regex.DOTALL)
  if _has_unmapped_mula(cur_rest_nomarker):
    raise RuntimeError(f"{md_path}: unmapped मूलम् remains at finalize.")
  body_nodetails = regex.sub(r"<details\b.*?</details>", "",
                             cur_rest_nomarker, flags=regex.DOTALL)
  if regex.search(r"[\u0900-\u097F]{2,}", body_nodetails):
    raise RuntimeError(f"{md_path}: bare Sanskrit remains at finalize.")
  notes = len(regex.findall(r"<summary>Translation - Notes</summary>",
                            cur_rest_nomarker))
  skipped = cur_rest_nomarker.count(TRANSLATION_SKIPPED_TAG)
  empty = len(regex.findall(
    r"<summary>Translation</summary>\n\n\s*</details>", cur_rest_nomarker))
  paras_txt = total_paras if total_paras is not None else "?"
  appendix = (
    "<details><summary>Appendix</summary>\n\n"
    f"- {total_core} sentences from {paras_txt} paragraphs interleaved "
    f"with translations from [{', '.join(used_files)}].\n"
    f"- {notes} Translation - Notes blocks; {skipped} skipped "
    "(no counterpart found).\n"
    + (f"- WARNING: {empty} empty Translation blocks (unexpected).\n"
       if empty else "")
    + ("position tags advanced in: " + ", ".join(tagged) + ".\n"
       if tagged else "") +
    "</details>\n")
  _atomic_write(md_path, cur_header + cur_rest_nomarker.rstrip()
                + "\n\n" + appendix)
  return {"status": "done", "sentences": total_core,
          "paragraphs": total_paras, "notes": notes, "empty": empty,
          "skipped": skipped, "files": used_files, "tagged": tagged}


def insert_translation_details(md_path, translation_dir_path, start_file=None,
                               end_file=None, end_after=None, generate_fn=None,
                               batch_core_chars=800, window_en_chars=8000,
                               max_retries=2, dry_run=False):
  """Map translations onto pre-made मूलम् sentences and insert them.

  Assumes :func:`doc_curation.md.content_processor.details.maker.generic_sanskrit_vipra_mUla`
  has already run: every sentence to translate already sits in its own
  ``मूलम्`` block (with a विश्वास-प्रस्तुतिः twin).  This function gathers
  those मूलम् sentences into an array, maps them with the batched index
  protocol of :func:`seq_match_texts_to_translation`, and inserts just
  the Translation [/ Translation - Notes] details directly above each
  corresponding मूलम् block.  Cores the model explicitly skips (no
  English counterpart) get no Translation block at all — only a
  ``<!-- TRANSLATION-SKIPPED -->`` marker — and are listed in the
  Appendix; output never contains empty Translation blocks.

  After EVERY validated LLM response the md file is reread from disk
  and rewritten (mapped blocks + progress marker + remaining bare मूलम्
  blocks) before the next call, so concurrent edits survive and reruns
  resume after the marker.  On full success the marker is replaced by an
  Appendix block.  Bare Sanskrit outside details (i.e. the maker step
  was skipped) raises RuntimeError; reruns on finished files are no-ops.

  Translation-file carryover: every translation file carries a
  ``<!-- TRANSLATION-MATCH-POS -->`` tag marking where the next LLM
  input starts (units before it are consumed).  The EN stream is rebuilt
  from disk every batch honoring those tags, so unmatched tail
  sentences of a file automatically continue the next call's window;
  after each mapped batch the tags advance in the files themselves
  (consumed heads are never deleted; footnote defs never move).

  :param md_path: md file rewritten in place.
  :param translation_dir_path: directory of translation ``*.md`` files,
    or a single translation ``*.md`` file path.
  :param start_file: basename to start from (e.g. ``"12.md"``); ``None``
    starts with the first file.
  :param end_file: basename to stop at (inclusive); ``None`` runs to the
    last file.  Use when the md file's scope ends before the directory
    does, so the final batch is not forced to swallow foreign tail
    material (e.g. later sūtras for a later adhikaraṇa file).
  :param end_after: distinctive phrase from the last in-scope
    translation unit (any script), matched locally by substring search;
    the stream truncates right after its unit.  Refines ``end_file``
    when the scope ends mid-file.  Zero/multiple matches raise
    ValueError (fail-stop); ``None`` consumes to the end of ``end_file``.
  :param generate_fn: ``fn(prompt_text) -> str``.
  :param dry_run: map everything but write nothing (no md, tag, or
    Appendix writes).
  :return: dict summary.
  """
  used_paths = _translation_files_sorted(translation_dir_path, start_file,
                                           end_file)
  used_files = [os.path.basename(p) for p in used_paths]

  with open(md_path, encoding="utf-8") as f:
    text = f.read()
  header, rest = _split_header_rest(text)
  marker = _parse_continue_marker(rest)

  if marker is None:
    if _has_bare_devanagari(rest):
      raise RuntimeError(
        f"{md_path} still has bare Sanskrit outside details; run "
        "generic_sanskrit_vipra_mUla first, then insert translations.")
    blocks = _mula_blocks(rest)
    if not blocks:
      if "<summary>Appendix</summary>" in rest:
        return {"status": "already-done", "sentences": 0,
                "paragraphs": 0, "notes": 0, "empty": 0,
                "files": used_files}
      app = ("<details><summary>Appendix</summary>\n\n"
             "No mismatches or anomalies detected.\n</details>\n")
      if not dry_run:
        _atomic_write(md_path, text if text.endswith("\n") else text + "\n"
                      + ("" if rest.endswith("\n\n") else "\n") + app)
      return {"status": "appendix-only", "sentences": 0,
              "paragraphs": 0, "notes": 0, "empty": 0,
              "files": used_files}
    total_core = len(blocks)
    total_paras = total_core  # 1:1 sentences↔blocks from here on
    if not _has_unmapped_mula(rest):
      # Fully mapped (e.g. rerun after success, or Appendix deleted):
      # never duplicate translations; just ensure the Appendix exists.
      if "<summary>Appendix</summary>" in rest:
        return {"status": "already-done",
                "sentences": total_core, "paragraphs": total_paras,
                "notes": 0, "empty": 0, "files": used_files}
      if dry_run:
        return {"status": "done", "sentences": total_core,
                "paragraphs": total_paras, "notes": 0, "empty": 0,
                "files": used_files, "tagged": []}
      return _finalize_appendix(md_path, total_core, total_paras,
                                used_files, [])
    done_core, next_en = 0, 0
    if not dry_run:
      # Fresh md run: stale position tags would mislead the next input,
      # so reset them to 0 before mapping anything.
      files_units = _load_translation_units(used_paths)
      for path in used_paths:
        front, units = files_units[path]
        _write_translation_file(
          path, front, [TRANSLATION_POS_TAG] + units)
  else:
    (done_core, next_en, total_core, _total_en_marked, _paras_marked,
     marked_files) = marker
    if marked_files and marked_files != used_files:
      logging.warning("translation file set changed since marker %s; "
                      "resuming by cursors anyway", marked_files)
    total_paras = _paras_marked

  # ---- checkpointed batch loop ----
  # Invariants: sentences [0, done_core) already carry Translation blocks
  # in the file's done region; the todo region holds the remaining bare
  # मूलम् blocks; next_en indexes the freshly rebuilt EN stream, whose
  # per-file position tags mirror it on disk.
  tagged = []
  finalized = False
  final_notes = final_empty = 0
  mem_todo = None  # dry-run only: remaining todo text carried in memory
  while True:
    if dry_run and mem_todo is not None:
      cur_todo = mem_todo
      cur_done_core, cur_next_en = done_core, next_en
    else:
      # Reread everything before each call (concurrent-edit safe).
      with open(md_path, encoding="utf-8") as f:
        cur_text = f.read()
      cur_header, cur_rest = _split_header_rest(cur_text)
      cur_marker = _parse_continue_marker(cur_rest)
      if cur_marker is None:
        if done_core or next_en:
          raise RuntimeError(
            f"{md_path}: progress marker vanished; refusing to continue.")
        cur_todo = cur_rest
        cur_done_core, cur_next_en = 0, 0
      else:
        if (cur_marker[0], cur_marker[1]) != (done_core, next_en):
          # Another process advanced the file; adopt the file's cursors.
          done_core, next_en = cur_marker[0], cur_marker[1]
          logging.info("adopting on-disk cursors done_core=%d next_en=%d",
                       done_core, next_en)
        pieces = regex.split(r"<!--\s*TRANSLATION-MATCH-CONTINUE.*?-->",
                             cur_rest, maxsplit=1, flags=regex.DOTALL)
        cur_todo = pieces[1] if len(pieces) > 1 else ""
        cur_done_core, cur_next_en = done_core, next_en
        if cur_marker[2] != total_core:
          raise RuntimeError(
            f"{md_path}: marker total_core changed; refusing to continue.")
      if dry_run:
        mem_todo = cur_todo

    # Translation stream rebuilt from disk every batch (honors tags and
    # any external edits; unmatched tails carry over into the window).
    # Footnote defs come from the FULL stream (a take may cite a def
    # defined past the scope anchor); mappable units stop at the anchor.
    files_units = _load_translation_units(used_paths)
    en, _ = _flatten_units(files_units, used_paths)
    all_units = [u for path in used_paths for u in files_units[path][1]]
    footnote_defs = _footnote_defs_from_units(all_units)
    full_m = len(en)
    if end_after is not None:
      en = en[:_match_end_anchor(en, end_after)]
    m = len(en)
    en_lens = [len(u) for u in en]

    # Todo मूलम् sentences from the todo text (source of truth).
    # A leading run of already-mapped blocks may linger here (older
    # checkpoints left them in place); skip it so the batch always
    # starts at the first unmapped sentence.  Those skipped sentences
    # are already counted in done_core, so g0 stays cur_done_core.
    # A mapped block after an unmapped one means corruption → raise.
    todo_entries = _mula_entries(cur_todo)
    skipped = 0
    while skipped < len(todo_entries) and todo_entries[skipped][2]:
      skipped += 1
    if any(mapped for _, _, mapped in todo_entries[skipped:]):
      raise RuntimeError(
        f"{md_path}: mapped मूलम् block after unmapped ones; "
        "file changed incompatibly.")
    todo_texts = [s for _, s, _ in todo_entries[skipped:]]
    if cur_done_core + len(todo_texts) != total_core:
      raise RuntimeError(
        f"{md_path}: expected {total_core - cur_done_core} remaining "
        f"मूलम् sentences, todo has {len(todo_texts)}; "
        "file changed incompatibly.")

    if not todo_texts:
      break  # done: finalize below

    # Batch = leading todo sentences within budget (≥1).
    n_sent = 1
    while (n_sent < len(todo_texts)
           and sum(len(t) for t in todo_texts[:n_sent + 1]) <= batch_core_chars):
      n_sent += 1
    batch_texts = todo_texts[:n_sent]
    g0, g1 = cur_done_core, cur_done_core + n_sent

    e = cur_next_en
    if e >= m:
      translations = [""] * len(batch_texts)  # exhausted: no LLM call
      skipped_flags = [True] * len(batch_texts)
      next_en_new = m
      logging.info("matcher tail cores[%d:%d] exhausted "
                   "(en cursor %d >= %d units): %d skipped, no LLM call",
                   g0, g1, e, m, len(batch_texts))
    else:
      e_end = _plan_window(sum(len(t) for t in batch_texts),
                           sum(len(t) for t in todo_texts),
                           en_lens, e, m, window_en_chars)
      if g1 == total_core:
        e_end = m  # final batch covers the tail: no drops allowed
      anchor = regex.sub(r"\s+", " ", en[e - 1])[:300] if e > 0 else None
      norm, skipped, next_en_new = _map_batch(
        batch_texts, g0, en[e:e_end], e, total_core, m,
        generate_fn, max_retries, prev_unit=anchor)
      skip_set = set(skipped)
      skipped_flags = [(g0 + k) in skip_set for k in range(len(batch_texts))]
      translations = []
      for k in range(len(batch_texts)):
        s = norm[g0 + k]
        e_next = norm[g0 + k + 1] if k + 1 < len(batch_texts) else next_en_new
        translations.append("" if skipped_flags[k]
                            else " ".join(en[s:e_next]))

    if dry_run:
      # Memory-only: mapping already validated above; carry remainder.
      # Drop the mapped मूलम् blocks' sentences from memory todo by
      # cutting after the batch's last block tag.
      tags = [b for b, _, _ in todo_entries[skipped:skipped + n_sent]]
      tail = mem_todo
      for tag in tags:
        idx = tail.find(tag)
        assert idx != -1, "mapped block missing from memory todo"
        tail = tail[idx + len(tag):]
      mem_todo = tail
      done_core, next_en = g1, next_en_new
      continue

    # Surgery (fresh read below does the real splice): IDs only here.
    # NOTE: translations list above aligns 1:1 with batch_texts.
    done_core, next_en = g1, next_en_new

    # Checkpoint: reread done region (concurrent-edit safe), then write
    # the md checkpoint FIRST, then advance the translation-file tags
    # (a crash between them resumes from the md marker; stale tags are
    # recomputed from it on the next batch).
    with open(md_path, encoding="utf-8") as f:
      check_text = f.read()
    _, check_rest = _split_header_rest(check_text)
    check_marker = _parse_continue_marker(check_rest)
    if check_marker is None:
      # First batch: nothing done yet on disk.
      done_body_prev = ""
    else:
      done_body_prev = regex.split(
        r"<!--\s*TRANSLATION-MATCH-CONTINUE.*?-->", check_rest, maxsplit=1,
        flags=regex.DOTALL)[0]
    # Re-derive the just-mapped region from the fresh read and splice
    # the new Translation blocks in (never trust stale in-memory text).
    _, fresh_todo_parsed = _split_header_rest(check_text)
    if check_marker is not None:
      fresh_todo_parsed = regex.split(
        r"<!--\s*TRANSLATION-MATCH-CONTINUE.*?-->", fresh_todo_parsed,
        maxsplit=1, flags=regex.DOTALL)[1]
    fresh_entries = _mula_entries(fresh_todo_parsed)
    fresh_skip = 0
    while (fresh_skip < len(fresh_entries) and fresh_entries[fresh_skip][2]):
      fresh_skip += 1
    fresh_texts = [s for _, s, _ in fresh_entries[fresh_skip:]]
    if fresh_texts[:len(batch_texts)] != batch_texts:
      raise RuntimeError(
        f"{md_path}: todo changed incompatibly before checkpoint.")
    new_todo2 = fresh_todo_parsed
    for (tag, _, _), tr, was_skipped in zip(
        fresh_entries[fresh_skip:fresh_skip + len(batch_texts)],
        translations, skipped_flags):
      if was_skipped:
        # No counterpart: leave the mūlam bare, marked done via comment.
        new_todo2 = new_todo2.replace(
          tag, TRANSLATION_SKIPPED_TAG + "\n\n" + tag, 1)
        continue
      markers = [mk for mk in dict.fromkeys(
        regex.findall(r"\[\^[^\]]+\]", tr or ""))
        if mk in footnote_defs]
      notes = "\n".join(footnote_defs[mk] for mk in markers) or None
      new_todo2 = new_todo2.replace(
        tag, translation_details(tr, notes) + "\n\n" + tag, 1)
    new_done_core = cur_done_core + len(batch_texts)
    # Move the mapped leading run before the marker: the todo region
    # then always starts at the first unmapped sentence.
    done_add, todo_new_raw = _split_leading_mapped(new_todo2)
    parts = [p for p in (done_body_prev.strip(), done_add.strip()) if p]
    done_combined = "\n\n".join(parts)
    todo_new = todo_new_raw.strip()
    if _has_unmapped_mula(todo_new):
      marker_txt = _continue_marker(
        new_done_core, total_core, next_en_new, m, total_paras, used_files)
      _atomic_write(md_path, cur_header + done_combined
                    + "\n\n" + marker_txt + "\n\n" + todo_new + "\n")
      for b in _update_pos_tags(files_units, used_paths, next_en_new):
        if b not in tagged:
          tagged.append(b)
    else:
      # No bare sentences left (only Tamil details maybe): finalize now.
      todo_tail = ("\n\n" + todo_new) if todo_new else ""
      scope = None
      if end_after is not None:
        scope = (f"translation stream scoped by end_after {end_after!r} "
                 f"to units [0,{m}) of {full_m}")
      appendix = _appendix_text(
        total_core, total_paras, used_files, done_combined + todo_tail,
        tagged, scope)
      _atomic_write(md_path, cur_header + done_combined + todo_tail + "\n\n"
                    + appendix + "\n")
      for b in _update_pos_tags(files_units, used_paths, next_en_new):
        if b not in tagged:
          tagged.append(b)
      done_core, next_en = new_done_core, next_en_new
      finalized = True
      final_notes = len(regex.findall(
        r"<summary>Translation - Notes</summary>",
        done_combined + todo_tail))
      final_empty = len(regex.findall(
        r"<summary>Translation</summary>\n\n\s*</details>",
        done_combined + todo_tail))
      final_skipped = (done_combined + todo_tail).count(
        TRANSLATION_SKIPPED_TAG)
      break

  # ---- finalize: drop marker, append appendix ----
  if dry_run:
    return {"status": "done", "sentences": total_core,
            "paragraphs": total_paras, "notes": 0, "empty": 0,
            "files": used_files, "tagged": tagged}
  if finalized:
    return {"status": "done", "sentences": total_core,
            "paragraphs": total_paras, "notes": final_notes,
            "empty": final_empty, "skipped": final_skipped,
            "files": used_files, "tagged": tagged}
  return _finalize_appendix(md_path, total_core, total_paras, used_files,
                            tagged)
