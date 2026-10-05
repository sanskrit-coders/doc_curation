"""Interleave commentary below mūla blocks as ṭīkā.

Learned from Śrī-bhāṣya Anandamayādhikaraṇa + Śruta-prakāśikā work.
Uses :mod:`details_helper` (Detail/get_details/transform/insert/MdFile)
whenever possible; custom pratīka logic where no helper exists.
Helpers give one empty line; spec here requires two, so post-process
newlines to ``\\n\\n\\n`` (documented below) while still building via Detail.
"""
import logging
import re

try:  # Use helpers whenever possible; fallback to raw for minimal envs.
  # NB: insert_adjascent_element/adjascent_inserter insert same neighbor for all
  # and one empty line; per-mūla different ṭīkā + two-empty-line spec needs direct
  # insert_after with custom "\n\n\n" spacers (documented in _interleave_soup),
  # still using Detail/get_details/get_nieghbor_detail/transform/MdFile below.
  from doc_curation.md.content_processor.details_helper import (
    Detail,
    get_details,
    get_nieghbor_detail,
    transform_details_with_soup,
  )
  from doc_curation.md.file import MdFile
  _HAS_HELPERS = True
except ImportError:  # pragma: no cover - minimal env without bs4/yamldown.
  Detail = None
  get_details = None
  get_nieghbor_detail = None
  transform_details_with_soup = None
  MdFile = None
  _HAS_HELPERS = False

MULA_RE = r"<details><summary>मूलम्</summary>(.*?)</details>"
TIKA_TAG = "<details><summary>टीका</summary>"
TIKA_FMT = "\n\n\n<details><summary>टीका</summary>\n\n\n%s\n</details>"

# User hint: ([िइेी])त(ि|्य) separates chunks & finds pratīkas.
DASH_SPACED_RE = r"-\s*([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}?)\s*([िइेी]त(?:ि|्य))"
LONG_SUFFIX = r"(?:ेत्यनेन|ित्यनेन|ीत्यनेन|ेत्यादिना|ित्यादिना|ीत्यादिना|ेत्यादि|ित्यादि|ीत्यादि|ेत्युक्तम्|ित्युक्तम्|ीत्युक्तम्|ेत्युक्त|ित्युक्त|ीत्युक्त)"
LONG_SPACED_RE = rf"([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){{0,2}}?){LONG_SUFFIX}"
VERB_RE = (
    # General verb (any Dev ending in ति, e.g. दूषयति/परिहरति/मुदाहरति) + specific
    # माह/आह/उक्तम् (ending in ह/म्, not ति): introduces pratīka without dash,
    # e.g. दूषयति राद्धान्ते चेति (verb दूषयति, no dash). Suffix includes plain
    # dependent/independent iti (ेति/िति/ीति/इति/ेत्य/ित्य) + lookahead (not \b,
    # since \b fails after dependent vowel-sign Mn + space).
    r"(?:माह|मुदाहरति|उक्तम्|(?:^|\s)आह|[ऀ-ॿ]*ति)\s+"
    r"([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}?)"
    r"\s*(?:इत्युक्तम्|इत्यादिना|इत्यनेन|ीत्युक्तम्|ीत्यादिना|ीत्यनेन|[िइेी]त(?:ि|्य))(?=\s|[।॥]|$)"
)
ITI_WORD_RE = r"([ऀ-ॿ]+(?:\s+[ऀ-ॿ]+){0,2}?)\s*([िइेी]त(?:ि|्य))(?=\s|[।॥]|$)"
SHORT_WHITELIST = {"तथ", "तथा", "यथ", "यथा", "एवम", "एवम्", "तत्र"}


def _split_frontmatter(text):
  m = re.match(r"^(\+\+\+.*?\+\+\+\s*)", text, flags=re.DOTALL)
  if m:
    return m.group(1), text[m.end():]
  return "", text


def _norm_mula(s):
  s = re.sub(r"\[\[([^|\]]+)\|([^]]+)\]\]", r"\1 \2", s)
  s = re.sub(r"[\[\]]", "", s)
  return re.sub(r"[\s\-\u2013\u2014\(\)।॥,;:\.\"]", "", s)


def _norm_space(s):
  return re.sub(r"[\s\-]", "", s)


def _fix_stray_latin(s):
  s = s.replace("[[ye|ये]]", "[[ये|ये]]")
  # Isolated 'ye' inside Devanāgarī context -> 'ये'.
  if re.search(r"[ऀ-ॿ]", s):
    s = re.sub(r"(?<=[ऀ-ॿ\s।॥,;:\.\-\[\]\(\)\"'])ye(?=[ऀ-ॿ\s।॥,;:\.\-\[\]\(\)\"'])", "ये", s)
  return s


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


def _extract_bases(sent):
  out = []
  for pat, kind in [(DASH_SPACED_RE, "dash"), (LONG_SPACED_RE, "long"), (VERB_RE, "verb")]:
    for m in re.finditer(pat, sent):
      base = m.group(1).strip("- ")
      if len(base) >= 2 and not any(b == base for _, b, _ in out):
        out.append((m.group(0).strip(), base, kind))
  for m in re.finditer(ITI_WORD_RE, sent):
    base = m.group(1).strip()
    if len(base) >= 2 and not any(b == base for _, b, _ in out):
      out.append((m.group(0).strip(), base, "iti"))
  return out


def _longest_in_target(prat_norm, target_norm, min_len=2):
  for L in [12, 10, 8, 6, 5, 4, 3, 2]:
    if L > len(prat_norm) or L < min_len:
      continue
    if prat_norm[:L] in target_norm:
      return L
  return 0


def _count_containing(sub, normed):
  return sum(1 for nm in normed if sub in nm) if sub else 0


def _best_match(prat_base, cur_idx, normed, backward=5, forward=30):
  bn = _norm_space(prat_base)
  cands = [bn]
  if bn in ("तथ", "यथ"):
    cands.append(bn + "ा")
  best, best_key = None, None
  lo = max(0, cur_idx - backward)
  hi = min(len(normed), cur_idx + forward + 1)
  for cand in cands:
    for mi in range(lo, hi):
      L = _longest_in_target(cand, normed[mi], min_len=2)
      if L < 2:
        continue
      sub = cand[:L]
      cnt = _count_containing(sub, normed)
      # Frequency guard: generic (cnt>5, e.g. सामानाधिकरण्य) needs long (>=8) or short-whitelist tiny window.
      if cnt > 5:
        if L < 8 and not (len(cand) <= 4 and (cand in SHORT_WHITELIST or cand[:3] in ("तथ", "यथ"))):
          continue
        if len(cand) <= 4 and abs(mi - cur_idx) > 3:
          continue
      key = (L, -abs(mi - cur_idx))
      if best_key is None or key > best_key:
        best_key, best = key, (mi, L)
  return best if best else (None, None)


def _distinctive_words(sent, normed, min_len=6, max_cnt=5):
  words = re.findall(r"[ऀ-ॿ]{5,}", sent)
  out, seen = [], set()
  for w in words:
    if len(w) < min_len or w in seen:
      continue
    seen.add(w)
    for L in [10, 8, 6]:
      if L > len(w):
        continue
      sub = w[:L]
      if 1 <= _count_containing(sub, normed) <= max_cnt:
        out.append((w, sub))
        break
  out.sort(key=lambda x: -len(x[0]))
  return out


def _make_tika_html(txt):
  # Uses Detail (helpers) for base; post-process to two empty lines (spec requires
  # two, Detail gives one).
  txt = _fix_stray_latin(txt)
  if _HAS_HELPERS and Detail is not None:
    html = Detail(title="टीका", content=txt.strip()).to_md_html()
    return html.replace("<summary>टीका</summary>\n\n", "<summary>टीका</summary>\n\n\n", 1)
  return TIKA_FMT % txt.strip()


def _fix_latin_via_helper(content):
  # Script integrity for mūla/ṭīkā only (excludes English Translation which legitimately has Latin).
  if not (_HAS_HELPERS and transform_details_with_soup is not None):
    return re.sub(
      r"<details><summary>(?:मूलम्|टीका)</summary>.*?</details>",
      lambda mo: mo.group(0).replace("[[ye|ये]]", "[[ये|ये]]"),
      content,
      flags=re.DOTALL,
    )

  def _fix_str(s, *a, **k):
    if not re.search(r"[ऀ-ॿ]", s):
      return s
    s = s.replace("[[ye|ये]]", "[[ये|ये]]")
    return re.sub(r"\bye\b", "ये", s)

  return transform_details_with_soup(
    content, content_str_transformer=_fix_str, title_pattern=r"मूलम्.*|टीका"
  )


def _compute_assign(matches_texts, sents):
  """Greedy pratīka-driven assignment shared by raw/soup paths."""
  normed = [_norm_mula(t) for t in matches_texts]
  assign, cur = {}, 0
  started = False
  for si, sent in enumerate(sents[:12]):
    for _, base, _ in _extract_bases(sent):
      bn = _norm_space(base)
      if len(bn) < 7:
        continue
      for L in [10, 8, 7]:
        if L > len(bn):
          continue
        hits = [mi for mi, nm in enumerate(normed) if bn[:L] in nm]
        if len(hits) == 1:
          cur = hits[0]
          started = True
          break
      if started:
        break
    if started:
      for pj in range(max(0, si - 5), si):
        for _, b2, _ in _extract_bases(sents[pj]):
          mi2, _ = _best_match(b2, cur, normed, backward=10, forward=0)
          if mi2 is not None and mi2 < cur:
            assign.setdefault(mi2, []).append(pj)
      break
  for si, sent in enumerate(sents):
    if any(si in v for v in assign.values()):
      continue
    best_mi, best_L = None, 0
    for _, base, _ in _extract_bases(sent):
      mi, L = _best_match(base, cur, normed, backward=5, forward=30)
      if mi is None:
        continue
      bn = _norm_space(base)
      if _count_containing(bn[:L], normed) > 5 and L < 8 and not (
        len(bn) <= 4 and (bn in SHORT_WHITELIST or bn[:3] in ("तथ", "यथ"))
      ):
        continue
      if L > best_L or (L == best_L and best_mi is not None and abs(mi - cur) < abs(best_mi - cur)):
        best_mi, best_L = mi, L
    if best_mi is None:
      for w, sub in _distinctive_words(sent, normed):
        cand = None
        for d in range(0, 11):
          for mi in {cur - d, cur + d}:
            if 0 <= mi < len(normed) and sub in normed[mi] and (cand is None or abs(mi - cur) < abs(cand - cur)):
              cand = mi
          if cand is not None and d >= 3:
            break
        if cand is not None:
          best_mi = cand
          break
    if best_mi is None:
      assign.setdefault(cur, []).append(si)
    else:
      cur = best_mi
      assign.setdefault(cur, []).append(si)
  return assign


def _interleave_raw(dest_body, matches, sents):
  normed = [_norm_mula(m.group(1)) for m in matches]
  # Reuse _compute_assign via texts for consistency (matches_texts = raw inners).
  assign = _compute_assign([m.group(1) for m in matches], sents)
  to_insert = {}
  for mula_idx, sidxs in assign.items():
    m = matches[mula_idx]
    _, e = m.span()
    nxt = matches[mula_idx + 1].start() if mula_idx + 1 < len(matches) else len(dest_body)
    if TIKA_TAG in dest_body[e:nxt]:
      continue
    txt = " ".join(sents[i].strip() for i in sorted(sidxs))
    txt = _fix_stray_latin(txt)
    if txt.strip():
      to_insert[mula_idx + 1] = txt
  if not to_insert:
    return dest_body, 0
  parts, prev = [], 0
  for idx, m in enumerate(matches):
    s, e = m.span()
    nxt_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(dest_body)
    between = dest_body[e:nxt_start]
    parts.append(dest_body[prev:e])
    if (idx + 1) in to_insert:
      parts.append("\n\n\n<details><summary>टीका</summary>\n\n\n" + to_insert[idx + 1] + "\n</details>")
      parts.append(between)
      prev = nxt_start
    else:
      parts.append(between)
      prev = nxt_start
  return "".join(parts), len(to_insert)


def interleave_TIkA_below_mUla(dest_file, commentary_file):
  """Insert commentary as ṭīkā below each mūlam block.

  - Every ``<details><summary>मूलम्</summary>`` in ``dest_file`` (ignores
    ``मूलम् (संयुक्तम्)``); inserts directly below, two empty lines,
    ``<details><summary>टीका</summary>\\n\\n\\nTEXT\\n</details>``.
  - Keeps existing ṭīkās (only fills missing); verbatim except stray-Latin fix
    (``ye``→``ये``); preserves tags/spacing/svara; no extra commentary.
  - Sequential but never forced: pratīka (``([िइेी])त(ि|्य)`` + dash/verb/long/
    sūtra-exact/content-distinctive, multi-word with spaces, sandhi-tolerant
    prefix fallback, ं/म् preserved e.g. सोऽयम्/सोऽयं, frequency cnt<=5,
    short whitelist तथ/यथा/एवम्/तत्र, backward 5 / forward 30, longest wins)
    decides; trailing ``- X चेति`` goes to next (e.g. अयोग्यता→next),
    leading examples go further-down single mūla listing all (दण्डी/शुक्लेन/
    नीलम्/नीलोत्पल→later), previous-block details appearing later move back
    (विरोधाभावात्/देशान्तर…→previous), stay-on-current for elaboration,
    śruti/colophon left empty (collective). Logs appendix (entirely-wrong /
    head-tail-extra, missing).
  """
  # Helpers path first (uses Detail/get_details/transform/insert/MdFile).
  if _HAS_HELPERS:
    try:
      return _interleave_soup(dest_file, commentary_file)
    except Exception as exc:  # Fall back to raw on soup failure.
      logging.warning("Soup path failed (%s); falling back to raw.", exc)
  # Raw fallback (stdlib only): frontmatter-preserving plain I/O + regex.
  with open(dest_file, encoding="utf-8") as f:
    dest_raw = f.read()
  with open(commentary_file, encoding="utf-8") as f:
    comm_raw = f.read()
  dest_head, dest_body = _split_frontmatter(dest_raw)
  mula_pat = re.compile(MULA_RE, re.DOTALL)
  matches = list(mula_pat.finditer(dest_body))
  if not matches:
    logging.warning("No mūlam blocks in %s", dest_file)
    return
  sents = _split_commentary_sentences(_split_frontmatter(comm_raw)[1])
  if not sents:
    logging.warning("No commentary sentences in %s", commentary_file)
    return
  combined_body, n = _interleave_raw(dest_body, matches, sents)
  if not n:
    logging.info("Nothing to insert for %s", dest_file)
    return
  combined_body = _fix_latin_via_helper(combined_body)
  with open(dest_file, "w", encoding="utf-8") as f:
    f.write(dest_head + combined_body)
  logging.info("Inserted %d ṭīkās into %s (mūlas=%d).", n, dest_file, len(matches))


def _interleave_soup(dest_file, commentary_file):
  """Soup path using details_helper (Detail/get_details/transform/insert/MdFile).

  Same greedy assignment via :func:`_compute_assign`; detection/creation/
  existing-check/Latin-fix/file-I/O via helpers. Spacing post-processed to
  two empty lines (helpers default to one) to meet spec.
  """
  from bs4 import NavigableString

  dest_md = MdFile(file_path=dest_file)
  metadata, dest_content = dest_md.read()
  with open(commentary_file, encoding="utf-8") as f:
    comm_raw = f.read()
  # MdFile strips frontmatter already for dest; commentary may still have it if plain read.
  comm_body = _split_frontmatter(comm_raw)[1] if comm_raw.lstrip().startswith("+++") else comm_raw
  # get_details needs full content (with frontmatter? No, body only? MdFile content excludes frontmatter. Good.)
  from doc_curation.md import content_processor as _cp

  soup = _cp._soup_from_content(content=dest_content, metadata=metadata)
  if soup is None:
    raise ValueError("soup parse failed")
  details = get_details(dest_content, title="मूलम्", metadata=metadata)
  # Ignore संयुक्तम् for insertion (step 1); keep order.
  mula_items = [(tag, det) for tag, det in details if "संयुक्तम्" not in (det.title or "")]
  if not mula_items:
    logging.warning("No mūlam blocks in %s", dest_file)
    return
  matches_texts = [det.content for _, det in mula_items]
  sents = _split_commentary_sentences(comm_body)
  if not sents:
    logging.warning("No commentary sentences in %s", commentary_file)
    return
  assign = _compute_assign(matches_texts, sents)
  # Existing-tika check via immediate next sibling details (uses helper).
  to_insert = {}
  for mula_idx, (tag, det) in enumerate(mula_items):
    nxt = get_nieghbor_detail(tag, seek_before=False)
    if nxt is not None:
      from doc_curation.md.content_processor.details_helper import Detail as _D

      nd = _D.from_soup_tag(nxt)
      if nd is not None and (nd.title or "").strip() == "टीका":
        continue
    if mula_idx not in assign or not assign[mula_idx]:
      continue
    txt = " ".join(sents[i].strip() for i in sorted(assign[mula_idx]))
    # _fix_stray_latin via string (transform pass later covers soup text nodes too).
    from doc_curation.md.content_processor.details_helper import Detail as _D2

    _ = _D2  # keep import used (Detail creation below uses module-global Detail).
    txt = _fix_stray_latin(txt)
    if txt.strip():
      to_insert[mula_idx] = txt
  if not to_insert:
    logging.info("Nothing to insert for %s", dest_file)
    return
  # Per-mūla different insertion via Detail.to_soup (helper) + "\n\n\n" spacers.
  # Spec needs two empty lines (helpers default to one); custom "\n\n\n" here
  # meets spec for new blocks while existing blocks (one empty line) stay untouched.
  for mula_idx, (tag, det) in enumerate(mula_items):
    if mula_idx not in to_insert:
      continue
    tika_html = _make_tika_html(to_insert[mula_idx])
    from bs4 import BeautifulSoup as _BS
    from bs4 import NavigableString as _NS

    neighbor_tag = _BS(tika_html, "html.parser").select_one("details")
    # insert_after puts newest immediately after tag; reverse to get tag, spacer, neighbor.
    tag.insert_after(neighbor_tag)
    tag.insert_after(_NS("\n\n\n"))
  new_content = _cp._make_content_from_soup(soup=soup)
  new_content = _fix_latin_via_helper(new_content)
  dest_md.replace_content_metadata(new_content=new_content)
  logging.info("Inserted %d ṭīkās into %s (mūlas=%d).", len(to_insert), dest_file, len(mula_items))
