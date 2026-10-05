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

# Pratika cues: dash-led, long-suffix (etyanena/etyadina/...), verb-led.
DASH_AFTER_RE = r"-\s*([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}?)\s*[िइेी]त(?:ि|्य)"
DASH_BEFORE_RE = r"([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}?)\s*[िइेी]त(?:ि|्य)\s*-\s*"
LONG_SUFFIX = (
  r"(?:ेत्यनेन|ित्यनेन|ीत्यनेन|ेत्यादिना|ित्यादिना|ीत्यादिना|ेत्यादि|ित्यादि"
  r"|ीत्यादि|ेत्युक्तम्|ित्युक्तम्|ीत्युक्तम्|ेत्युक्त|ित्युक्त|ीत्युक्त)"
)
LONG_SPACED_RE = rf"([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,2}}?){LONG_SUFFIX}"
VERB_RE = (
  r"(?:माह|मुदाहरति|उक्तम्|(?:^|\s)आह|[ऀ-ॿ]*ति)\s+"
  r"([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}?)"
  r"\s*(?:इत्युक्तम्|इत्यादिना|इत्यनेन|ीत्युक्तम्|ीत्यादिना|ीत्यनेन"
  r"|[िइेी]त(?:ि|्य))(?=\s|[।॥]|$)"
)


def _split_frontmatter(text):
  m = re.match(r"^(\+\+\+.*?\+\+\+\s*)", text, flags=re.DOTALL)
  if m:
    return m.group(1), text[m.end():]
  return "", text


def _norm_for_match(s):
  t = re.sub(r"\[\[([^|\]]+)\|([^]]+)\]\]", r"\1 \2", s)
  t = re.sub(r"[\[\]]", "", t)
  return re.sub(r"[\s\-\u2013\u2014\(\)।॥,;:\.\"]", "", t)


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


def _extract_pratika(tika_block):
  """Return the pratika string for a tika block (may be '')."""
  b = re.sub(r"^#\d+ lines are missing\.\s*", "", tika_block.strip(), flags=re.MULTILINE)
  if not b:
    return ""
  cands = []
  for pat in (DASH_BEFORE_RE, DASH_AFTER_RE, LONG_SPACED_RE, VERB_RE):
    for m in re.finditer(pat, b):
      base = _clean_base(m.group(1))
      if len(base) >= 2:
        cands.append((m.start(), base))
  if cands:
    cands.sort(key=lambda x: x[0])
    return cands[0][1]
  words = re.findall(r"[ऀ-ॿ]{2,}", b)[:2]
  return _clean_base(" ".join(words))


def _pratika_in_mula(pratika, mula_text, prefix_len=5):
  """Sandhi-tolerant existence check: normalized containment.

  Exact normalized containment wins; otherwise the first ``prefix_len``
  normalized chars must occur in the mula (suffix sandhi like म्/ं, ञ्च/ंच
  often differs while the stem matches).
  """
  npr = _norm_for_match(pratika)
  nm = _norm_for_match(mula_text)
  if len(npr) < 2 or len(nm) < 2:
    return False
  if npr in nm:
    return True
  if len(npr) > prefix_len and npr[:prefix_len] in nm:
    return True
  return False


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

  - Builds an ordered map of tika-blocks to pratikas; tika-block order is
    identical to that in ``commentary_file`` (see :func:`_get_ordered_tika_blocks`).
  - Finds the last existing tika block in ``dest_file``; only mulas after it
    are considered (earlier gaps are left untouched).
  - For each such mula in document order, peeks at the next pratika: if
    :func:`_pratika_in_mula` holds, inserts the corresponding tika block
    directly below the mula and pops it out of the ordered map; otherwise the
    mula is left empty and the same pratika is tried against the next mula.
  - Repeats till mulas are exhausted or the ordered map is empty.
  - Appends any remaining tika-blocks (joined in order) as a single tika
    block under the final mula in the dest file (at EOF, so sentence order is
    preserved).
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
  # Ordered map: deque of (block, pratika) in commentary order.
  ordered = deque((b, _extract_pratika(b)) for b in blocks)
  logging.info("interleave: %d tika blocks, %d mulas, starting at mula %d (last tika at %s).",
               len(ordered), len(mula_matches), start_idx, last_tika_mula)
  for _i, (_b, _pr) in enumerate(ordered):
    logging.info("interleave pratika %d: %r (block head: %r).", _i, _pr, _b[:80])
  all_pratikas = [pr for _, pr in ordered]
  to_insert = {}
  matched = []
  for mula_idx in range(start_idx, len(mula_matches)):
    if not ordered:
      break
    block, pratika = ordered[0]
    if _pratika_in_mula(pratika, mula_texts[mula_idx]):
      to_insert[mula_idx] = block.strip()
      ordered.popleft()
      matched.append((pratika, mula_idx))
      logging.info("interleave: mula %d <- pratika %r.", mula_idx, pratika[:60])
  parts, prev = [], 0
  for idx, m in enumerate(mula_matches):
    s, e = m.span()
    nxt_start = mula_matches[idx + 1].start() if idx + 1 < len(mula_matches) else len(dest_body)
    between = dest_body[e:nxt_start]
    parts.append(dest_body[prev:e])
    if idx in to_insert:
      parts.append(TIKA_FMT % to_insert[idx])
      parts.append(between)
      prev = nxt_start
    else:
      parts.append(between)
      prev = nxt_start
  new_body = "".join(parts)
  unmatched = list(ordered)
  if ordered:
    remaining = "\n\n".join(b.strip() for b, _ in ordered)
    new_body = new_body.rstrip() + "\n" + (TIKA_FMT % remaining) + "\n"
    logging.info("interleave: appended %d remaining blocks under final mula.", len(ordered))
  for _pr, _mi in matched:
    logging.info("interleave matched: pratika %r -> mula %d.", _pr, _mi)
  for _b, _pr in unmatched:
    logging.info("interleave unmatched (leftover): pratika %r (block head: %r).", _pr, _b[:80])
  with open(dest_file, "w", encoding="utf-8") as f:
    f.write(dest_head + new_body)
  logging.info("Inserted %d ṭīkās into %s (mūlas=%d, leftovers=%d).",
               len(to_insert), dest_file, len(mula_matches), len(unmatched))
  return {"inserted": len(to_insert), "matched": matched,
          "unmatched": [(b, pr) for b, pr in unmatched],
          "pratikas": [pr for _, pr in list(to_insert.items())] if False else None}


def verify_sentence_order(dest_file, commentary_file, start_marker=DEFAULT_ORDER_MARKER):
  """Verify tika sentence order strictly follows commentary order.

  - Reads tika blocks in document order via details_helper.get_details
    (regex fallback when helpers are unavailable) and splits them with the
    shared splitter; reads commentary sentences the same way.
  - Scope starts at ``start_marker`` (a commentary sentence; default covers
    everything from Shrutyantara-paryalocana onward, skipping head-extra
    intro material): only dest sentences mapped at/after the marker are
    checked, in dest order.
  - Mapping is verbatim normalized (_norm_for_match) with difflib fuzzy
    fallback (>= 0.85, e.g. typo-fixed variants); shared _map_to_commentary.
  - FAILS on order decreases (dest has B right after A with cpos(B) <= cpos(A),
    e.g. cpos 321 followed by 314) and on missing sentences (commentary cpos
    strictly inside the scope range with zero dest mappings anywhere, e.g.
    cpos 320-321 absent between 319 and 322, or 322-326 absent between 321
    and 327). Unmapped dest sentences and fuzzy mappings are reported (not
    failures). Returns a report dict; logs human-readable appendix lines.
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
  marker_cpos = None
  marker_norm = _norm_for_match(start_marker)
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
    logging.warning("verify: start marker not found; checking whole file.")
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
  verify_sentence_order(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md", commentary_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sudarshana-sUriH/shruta-prakAshikA/mUlam_rA/1/1/06_AnandamayAdhikaraNam.md", start_marker="उपरितनवाक्यापर्यालोचनां दर्शयति")
  # realign_TIkA_below_mUla(dest_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/tattvam/rAmAnujaH/shrI-bhAShyam/sarva-prastutiH/1_samanvayaH/1_ayoga-vyavachChedaH/06_AnandamayAdhikaraNam.md") 
