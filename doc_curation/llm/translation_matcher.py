"""Sequential core↔translation alignment via batched LLM index mapping.

Provider-agnostic core: no baked-in assumptions about the text (no sūtra
numbers, no Devanagari handling).  All provider calls live in
``doc_curation.llm.opencode.translation_matcher`` and
``doc_curation.llm.gemini.translation_matcher``; this module only needs a
``generate_fn(prompt_text) -> str`` callable, so it also works with any
``LlmBackend.generate_content``.

Token-minimal protocol (single sweep, cursor-based):

1. The translation is used UNSPLIT, as plain canonical text (dash-glue
   separated, whitespace kept); footnote-definition blocks (``[^x]:``)
   are excised up front and consulted only for Notes.
2. Core texts are walked in order in batches sized by character budget.
   Each LLM call sends the next unmapped core batch plus the next
   unmapped translation window starting exactly where the last confirmed
   mapping ended — position travels by integer word cursors, never by
   re-sending settled text.
 3. The model returns *positions only*: ``{"starts": {core_idx: word_idx},
    "skip": [...], "next_en": int}`` — indices into its own whitespace
    split of the plain window text (verified against the told string
    count), shifted to global by the caller.  Span ends are implied by
    the next start (the last core of a batch ends at ``next_en``), so
    output is a handful of integers instead of copied text (which also
    guarantees the takes stay canonical-text verbatim).  Because spans
    are word ranges, the model splits sentences as it pleases —
    clause-level splits land precisely, with no carry/overlap machinery.
 4. Each reply is validated (exact key set, ints in range, non-decreasing,
    first start == window start, every non-skipped core takes >= 1 word,
    ``next_en`` sane, early stopping always allowed — where the
    translation ends is the model's call, reported, never forced); on
    failure only that
    batch is retried with the error appended.  After ``max_retries`` it
    raises rather than silently misaligning (cf. detail_chunker).
 5. Cores the model explicitly lists in ``"skip"`` (genuinely no English
    words rendering them: colophons, bare interjections, untranslated
    passages) get NO Translation block — only a
    ``<!-- TRANSLATION-SKIPPED -->`` marker — so output never contains
    empty Translation blocks; skips are reported in the Appendix.
 6. Scope bounds (``end_file`` / ``end_after``) truncate the stream when
    the md file's scope ends before the translation directory does, so
    the final batch is never forced to swallow foreign tail material.
    Oversized takes and overshooting final batches are logged as
    warnings (free diagnostics, no extra LLM calls).
"""

import json
import logging
import os
import string

import regex

from doc_curation.md.content_processor.details.maker import (
  translation_details)

def _canon_text(s):
  """Canonical translation text: the text exactly as the model sees it.

  CR/LF become LF, space/tab runs collapse, a space is inserted
  beforehand where dash-glue joins words (``karman.--But,`` gains a
  space beforehand: ``karman. --But,`` — single hyphens in words like
  ``well-known`` are untouched), ends stripped; newlines are KEPT (paragraph structure survives for
  footnote-def detection).  Word indices throughout this module are
  positions in ``text.split()`` — i.e. splitting by regex ``\\s`` —
  and the prompt tells the model exactly this rule, so its counts
  match.  Takes rebuilt with ``" ".join`` are canonical-text verbatim
  (they may show `` -- `` where the source had ``--``).
  """
  t = (s or "").replace("\r\n", "\n").replace("\r", "\n")
  t = regex.sub(r"[ \t]+", " ", t)
  t = regex.sub(r"(\S)(--|—|–)", r"\1 \2", t)
  return t.strip()


#: Position-tag format carrying per-file consumed-word counts (see
#: :func:`_pos_tag`).  Legacy bare tags are stripped by the same regex.
def _pos_tag(n):
  """Position-tag text recording ``n`` consumed words in its file."""
  return f"<!-- TRANSLATION-MATCH-POS words={n} -->"


def _strip_pos_tags(body):
  """Remove position tags (legacy and word-count variants)."""
  return regex.sub(
    r"<!--\s*TRANSLATION-MATCH-POS(?:\s+words=\d+)?\s*-->", "", body)


def _footnote_defs_from_text(body):
  """``{marker: def text}`` for ``[^x]:`` definition blocks in raw body."""
  defs = {}
  for m in regex.finditer(r"\[\^[^\]]+\]:.*?(?=\n\s*\n|\Z)", body,
                          flags=regex.DOTALL):
    text = _canon_text(m.group(0))
    mk = regex.match(r"(\[\^[^\]]+\]):", text).group(1)
    defs.setdefault(mk, text)
  return defs


def _def_spans(body):
  """Raw ``(start, end)`` spans of ``[^x]:`` definition blocks."""
  return [m.span()
          for m in regex.finditer(r"\[\^[^\]]+\]:.*?(?=\n\s*\n|\Z)", body,
                                  flags=regex.DOTALL)]


def _content_spans(body):
  """Raw ``(start, end)`` spans of content words in canonical ``body``.

  ``body`` must already be canonical (:func:`_canon_text`) with
  position tags stripped; footnote-def ranges are excluded.
  """
  excluded = _def_spans(body)
  return [(w.start(), w.end()) for w in regex.finditer(r"\S+", body)
          if not any(s <= w.start() < e for s, e in excluded)]


def _content_words(body):
  """Content-word list (see :func:`_content_spans`); canonicalizes."""
  t = _canon_text(_strip_pos_tags(body or ""))
  return [t[s:e] for s, e in _content_spans(t)]


def _load_translation_data(translation_paths):
  """``{path: (frontmatter, body, word_spans, defs)}`` fresh from disk.

  ``body`` is the canonical body (:func:`_canon_text`) with position
  tags stripped (footnote defs and paragraph structure intact); ``word_spans`` are raw ``(start, end)`` spans
  of content words (def ranges excluded) so tag moves never touch
  content; ``defs`` maps footnote markers to def text for Notes blocks.
  """
  out = {}
  for path in translation_paths:
    with open(path, encoding="utf-8") as f:
      raw = f.read()
    m = regex.match(r"^(\+\+\+.*?\+\+\+)\n?", raw, flags=regex.DOTALL)
    front = m.group(1) + "\n\n" if m else ""
    body = raw[len(m.group(0)) if m else 0:]
    body = _canon_text(_strip_pos_tags(body))
    defs = _footnote_defs_from_text(body)
    spans = _content_spans(body)
    out[path] = (front, body, spans, defs)
  return out


def _file_words(files_data, path):
  """Content-word list for one loaded file."""
  _, body, spans, _ = files_data[path]
  return [body[s:e] for s, e in spans]


def _load_batch_prompt_template():
  """Read the batch-prompt template from its sibling md file (fresh each call).

  The prose lives in ``translation_matcher_prompt.md`` next to this
  module so it can be edited without code changes; a leading HTML
  comment documents the ``$placeholders`` and is stripped before use.
  """
  path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "translation_matcher_prompt.md")
  with open(path, encoding="utf-8") as f:
    raw = f.read()
  body = regex.sub(r"\A\s*<!--.*?-->\s*", "", raw, flags=regex.DOTALL)
  return string.Template(body.rstrip("\n"))


def _prompt_for_batch(core_batch, c_start, en_window, e_start,
                      total_core, total_en, prev_text=None):
  core_lines = "\n".join(
    f"core[{c_start + i}]: {s}" for i, s in enumerate(core_batch))
  # Plain canonical text, deliberately NOT pre-numbered: the model splits
  # it by regex \s itself and reports positions into its own split
  # (verified against e_window_count), which keeps prompts small.
  en_text = " ".join(en_window)
  anchor = (f"\nThe translation continues from these trailing words "
            f"(already consumed — do NOT take them again): {prev_text}\n"
            f"Your first span must continue AFTER them.\n"
            if prev_text else "")
  c_end = c_start + len(core_batch)
  pace = round(c_end * total_en / max(total_core, 1))
  pacing = (f"\nPACING: after this batch {c_end} of {total_core} cores will "
            f"be placed; you should then have consumed roughly {pace} of "
            f"{total_en} translation words. If your next_en falls far "
            f"short of that, you are starving later cores — widen spans "
            f"and skip less. (A tight verse cluster may locally consume "
            f"less; do not overcorrect for one.)\n")
  return _load_batch_prompt_template().substitute(
    total_core_m1=total_core - 1, total_core=total_core,
    total_en_m1=total_en - 1, total_en=total_en, c_start=c_start,
    c_last=c_end - 1, e_start=e_start, e_window_count=len(en_window),
    anchor=anchor, pacing=pacing, core_lines=core_lines, en_words=en_text)


def _parse_mapping(reply):
  """Extract (starts, skip, next_en) from model output.

  Word indices throughout: ``starts`` maps each core to the FIRST word
  of its span, ``next_en`` is the first word after the batch's last
  span.  ``skip`` is optional (defaults to ``[]``): core indices with
  genuinely no words rendering them, whose span must be empty.
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


def _validate_batch(starts, skip, next_en, c_start, c_end, wlen,
                    remaining):
  """Normalize to ({int: int}, [int], int), or raise ValueError.

  All indices are WINDOW-RELATIVE (0-based positions in the model's
  own whitespace split of the window text); the caller shifts them to
  global.  Spans tile the window head word for word: the first start
  must be 0, starts are non-decreasing, and every non-skipped core
  takes at least one word (lazy empty spans are rejected so the model
  cannot skim hard sentences).  Nothing is dropped or duplicated:
  core ``i``'s take is exactly words ``[start[i], start[i+1])`` (the
  last ends at ``next_en``), so clause-level splits land precisely.
  Stopping early is always allowed — where the translation ends is the
  model's call; the leftover tail is reported, never force-consumed.
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
    if not 0 <= v <= wlen:
      raise ValueError(
        f"core {i} start {v} outside window [0, {wlen}] "
        f"(your split holds {wlen} strings)")
    if prev is not None and v < prev:
      raise ValueError(f"starts not non-decreasing at core {i}")
    prev = v
  if norm[want[0]] != 0:
    raise ValueError(
      f"first start {norm[want[0]]} != window start 0 "
      "(words before it would drop silently)")
  for i in want:
    end_i = norm[i + 1] if i + 1 < c_end else next_en
    width = end_i - norm[i]
    if i in skip_set:
      if width != 0:
        raise ValueError(
          f"core {i} is skipped but takes {width} word(s); "
          "skipped cores must have empty spans")
    elif width < 1:
      raise ValueError(
        f"core {i} has an empty span but is not in 'skip'; either give it "
        "at least one word or name it in 'skip' with genuine cause")
  lo, hi = norm[want[-1]], wlen
  if not lo <= next_en <= hi:
    raise ValueError(f"next_en {next_en} outside [{lo}, {hi}]")
  if remaining > 0 and next_en <= 0 and len(skip_set) < len(want):
    raise ValueError(
      f"batch consumed no translation words (stream has {remaining} "
      "words left here); attach the window head to the batch instead "
      "of stalling")
  return norm, sorted(skip_set), next_en


def seq_match_texts_to_translation(
    texts, translation_text, generate_fn,
    batch_core_chars=800, window_en_chars=8000, max_retries=2):
  """Align core texts to translation spans via batched LLM word mapping.

  :param texts: core sentences in order (any language).
  :param translation_text: full translation text, UNSPLIT (the model
    splits it as it pleases: takes are word spans, so clause-level
    splits land precisely).
  :param generate_fn: ``fn(prompt_text) -> str`` (e.g. wrapping
    ``LlmBackend.generate_content``); called once per batch plus
    retries of failed batches only.
  :param batch_core_chars: soft budget for core text per call.
  :param window_en_chars: cap for the translation window per call.
  :param max_retries: retries of an invalid batch reply (with the
    validation error appended); then RuntimeError.
  :return: list of translation strings, ``len == len(texts)``; each is
    the verbatim window words joined with single spaces (``""``
    for empty spans).
  """
  texts = [regex.sub(r"\s+", " ", (t or "").strip()) for t in (texts or [])]
  n = len(texts)
  if n == 0:
    return []
  # Footnote definitions are metadata, not sequence positions: excised
  # before word-splitting (look them up by marker for Notes blocks).
  en = _content_words(_strip_pos_tags(translation_text or ""))
  m = len(en)
  if m == 0:
    return ["" for _ in texts]
  if n == 1:
    return [_canon_text(translation_text)]

  # Precompute char lengths for budgeting.
  core_lens = [len(t) for t in texts]
  en_lens = [len(w) + 1 for w in en]

  out_takes = {}  # core idx -> (start, end) with end exclusive
  c, e = 0, 0
  while c < n:
    if e >= m:
      # Translation exhausted: remaining cores map to empty spans,
      # no LLM call needed.
      logging.info("matcher tail cores[%d:%d] exhausted "
                   "(en cursor %d >= %d words): %d skipped, no LLM call",
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
      e_end = m  # final batch sees to the stream end (maximal context;
      # stopping early stays allowed — unmatched tail is reported)
    prev = " ".join(en[max(0, e - 25):e]) if e > 0 else None
    norm, _skipped, next_en = _map_batch(
      texts[c:c_end], c, en[e:e_end], e, n, m, generate_fn, max_retries,
      prev_text=prev)
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
  headroom, capped; always ≥1 word.
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
               prev_text=None):
  """Map one batch; returns (norm {core: word_start}, skipped, next_en).

  Retries narrowly.  ``prev_text`` (trailing already-consumed words
  just before this window, if any) is shown to the model as a
  continuity anchor; those words are never re-taken.
  """
  prompt = _prompt_for_batch(core_batch, c, en_window, e, n, m,
                             prev_text=prev_text)
  reply, err = None, None
  for _ in range(max_retries + 1):
    try:
      reply = generate_fn(prompt if err is None else prompt + (
        f"\n\nYour previous reply was invalid: {err} "
        "Reply again with ONLY the corrected JSON."))
      starts, skip, next_en = _parse_mapping(reply)
      # Validated in the model's window-relative indices, then shifted
      # to global: everything downstream (takes, cursors, markers, tags)
      # is global, while retry errors stay in the model's own language.
      norm, skipped, next_en = _validate_batch(
        starts, skip, next_en, c, c + len(core_batch),
        len(en_window), m - e)
      norm = {k: v + e for k, v in norm.items()}
      next_en += e
      # Free diagnostics (no extra LLM calls): flag pile-ups while the
      # cursors still tell where they happened.
      widths = [((norm[c + k + 1] if k + 1 < len(core_batch) else next_en)
                 - norm[c + k]) for k in range(len(core_batch))]
      widest = max(widths) if widths else 0
      if widest > 200:
        k = widths.index(widest)
        logging.warning(
          "matcher batch core[%d:%d]: core %d takes %d words "
          "(en[%d:%d]) — possible pile-up/overshoot, verify placement",
          c, c + len(core_batch), c + k, widest, norm[c + k],
          norm[c + k] + widest)
      if c + len(core_batch) < n:
        # Starvation check against the paced share: systematic
        # under-consumption piles up into a forced blob at the end
        # (the final batch must consume everything left).  Verse
        # clusters legitimately run lean, so this is only a warning.
        paced = (len(core_batch) / max(n - c, 1)) * (m - e)
        if paced >= 10 and next_en - e < paced / 3:
          logging.warning(
            "matcher batch core[%d:%d] consumes %d of %d remaining "
            "words (paced share ~%d) — later cores may starve, or the "
            "stream overshoots the file's scope (consider "
            "end_file/end_after)", c, c + len(core_batch), next_en - e,
            m - e, round(paced))
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



def _match_end_anchor(words, end_after):
  """Exclusive end word-count of the stream for an ``end_after`` anchor.

  The anchor is a distinctive phrase from the last in-scope stretch
  (any script: verse fragment, section heading, colophon echo),
  matched locally by substring search on the canonical word-joined
  text — no LLM, no domain knowledge in code.  The stream truncates at
  the next word boundary after the anchor.  Zero or multiple matches
  raise ValueError (fail-stop: callers pass a longer anchor).
  """
  anchor = (end_after or "").strip()
  if not anchor:
    raise ValueError("end_after anchor is empty")
  text = " ".join(words)
  hits = [m.start() for m in regex.finditer(regex.escape(anchor), text)]
  if not hits:
    folded, want = text.casefold(), anchor.casefold()
    hits = [m.start() for m in regex.finditer(regex.escape(want), folded)]
    # Casefolding can shift offsets for exotic scripts; the advance to
    # the next whitespace below absorbs small shifts (Latin/Devanagari
    # folds are length-preserving).
  if not hits:
    raise ValueError(
      f"end_after anchor {end_after!r} matches nowhere "
      f"(stream has {len(words)} words)")
  if len(hits) > 1:
    preview = "; ".join(
      f"word~{len(text[:h].split(' '))}: {text[h:h + 60]!r}" for h in hits[:5])
    raise ValueError(
      f"end_after anchor {end_after!r} matches {len(hits)} places "
      f"({preview}); pass a longer, unambiguous anchor")
  h = hits[0] + len(anchor)
  gap = regex.search(r"\s", text[h:])
  cut = len(text) if gap is None else h + gap.start()
  return len(text[:cut].split(" ")) if text[:cut].strip() else 0


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


def _update_pos_tags(files_data, used_paths, next_en):
  """Advance position tags to the global ``next_en`` word cursor.

  Returns basenames of files whose tag moved.  Files fully before the
  cursor get the tag at end, the file holding it after its consumed
  words, later files at start (tag at 0 is written explicitly so the
  next input position is unambiguous everywhere).  Only the tag line
  moves — bodies (defs, formatting, bytes) are otherwise preserved.
  Tags are write-only breadcrumbs for humans; the md progress marker
  holds the true cursors.
  """
  bounds, start = {}, 0
  for path in used_paths:
    _, _, spans, _ = files_data[path]
    bounds[path] = (start, start + len(spans))
    start += len(spans)
  changed = []
  for path in used_paths:
    front, body, spans, _ = files_data[path]
    s, e = bounds[path]
    new_pos = min(max(next_en - s, 0), e - s)
    tag = _pos_tag(new_pos)
    if new_pos <= 0:
      new_body = tag + "\n\n" + body.lstrip("\n") if body.strip() else tag + "\n"
    elif new_pos >= len(spans):
      new_body = body.rstrip("\n") + "\n\n" + tag + "\n"
    else:
      off = spans[new_pos - 1][1]
      new_body = (body[:off].rstrip() + "\n\n" + tag + "\n\n"
                  + body[off:].lstrip())
    if new_body != body:
      tmp = path + ".tmp"
      with open(tmp, "w", encoding="utf-8") as f:
        f.write(front + new_body)
      os.replace(tmp, path)
      changed.append(os.path.basename(path))
  return changed


def _appendix_text(total_core, total_paras, used_files, done_text, tagged,
                   scope=None, unmatched=0):
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
  if unmatched:
    text += (f"- {unmatched} trailing translation words unmatched "
             "(beyond file scope, per the model — not an error).\n")
  if empty:
    text += (f"- WARNING: {empty} empty Translation blocks (unexpected; "
             "skips should leave no block behind).\n")
  if tagged:
    text += ("position tags advanced in: " + ", ".join(tagged) + ".\n")
  return text + "</details>\n"


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
  ``<!-- TRANSLATION-MATCH-POS -->`` tag recording consumed words;
  the EN word stream is rebuilt from disk every batch honoring those
  tags, so unmatched tail words of a file automatically continue the
  next call's window; after each mapped batch the tags advance in the
  files themselves (consumed heads are never deleted; footnote defs
  never move).

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
    stretch (any script), matched locally by substring search on the
    word-joined text; the stream truncates at the next word boundary
    after it.  Refines ``end_file`` when the scope ends mid-file.  Zero/multiple matches raise
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
      files_data = _load_translation_data(used_paths)
      _update_pos_tags(files_data, used_paths, 0)
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

    # Translation word stream rebuilt from disk every batch (honors
    # tags and any external edits; unmatched tail words continue into the
    # window).  Footnote defs come from the FULL files (a take may cite
    # a def defined past the scope anchor); mappable words stop at it.
    files_data = _load_translation_data(used_paths)
    words_all = [w for p in used_paths for w in _file_words(files_data, p)]
    footnote_defs = {}
    for p in used_paths:
      footnote_defs.update(files_data[p][3])
    full_m = len(words_all)
    if end_after is not None:
      words_all = words_all[:_match_end_anchor(words_all, end_after)]
    en = words_all
    m = len(en)
    en_lens = [len(w) + 1 for w in en]

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
                   "(en cursor %d >= %d words): %d skipped, no LLM call",
                   g0, g1, e, m, len(batch_texts))
    else:
      e_end = _plan_window(sum(len(t) for t in batch_texts),
                           sum(len(t) for t in todo_texts),
                           en_lens, e, m, window_en_chars)
      if g1 == total_core:
        e_end = m  # final batch sees to the stream end (maximal context;
        # stopping early stays allowed — unmatched tail is reported)
      prev = " ".join(en[max(0, e - 25):e]) if e > 0 else None
      norm, skipped, next_en_new = _map_batch(
        batch_texts, g0, en[e:e_end], e, total_core, m,
        generate_fn, max_retries, prev_text=prev)
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
      for b in _update_pos_tags(files_data, used_paths, next_en_new):
        if b not in tagged:
          tagged.append(b)
    else:
      # No bare sentences left (only Tamil details maybe): finalize now.
      todo_tail = ("\n\n" + todo_new) if todo_new else ""
      scope = None
      if end_after is not None:
        scope = (f"translation stream scoped by end_after {end_after!r} "
                 f"to words [0,{m}) of {full_m}")
      appendix = _appendix_text(
        total_core, total_paras, used_files, done_combined + todo_tail,
        tagged, scope, unmatched=m - next_en_new)
      _atomic_write(md_path, cur_header + done_combined + todo_tail + "\n\n"
                    + appendix + "\n")
      for b in _update_pos_tags(files_data, used_paths, next_en_new):
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
