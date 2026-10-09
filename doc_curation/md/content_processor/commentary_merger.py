"""Merge parallel translations (e.g. kannaDa) into a dest corpus (e.g. hindI).

Moved here from :mod:`doc_curation.md.library.combination`; that module
re-exports :func:`merge_translations` for backwards compatibility.
"""
import logging
import os
from collections import defaultdict

import regex
from tqdm import tqdm

from doc_curation.md.file import MdFile
from doc_curation.md.library import get_md_files_from_path
from doc_curation.utils.sanskrit_helper import fix_lazy_anusvaara
from indic_transliteration import sanscript

VARIANT_SEPARATOR = "_________________"
KANNADA_TRANS_TITLE = "अनुवाद (कन्नड)"

_DETAIL_PATTERN = regex.compile(
  r"<details(?P<attrs>[^>]*)><summary>(?P<title>.*?)</summary>(?P<body>.*?)</details>",
  flags=regex.DOTALL)
_HEADING_PATTERN = regex.compile(r"(?m)^#{1,6}\s+(?P<heading>.*)$")
_DANDA_NUM_PATTERN = regex.compile(r"॥([^॥]*?)॥")
_DIGIT_SEQ_PATTERN = regex.compile(r"[0-9०-९೦-೯]+")
_LEADING_NUM_PATTERN = regex.compile(r"^(\d+)")
_FOOTNOTE_DEF_PATTERN = regex.compile(r"(?m)^\[\^[^\]]+\]:[^\n]*")
_FOOTNOTE_REF_PATTERN = regex.compile(r"\[\^[^\]]+\]")
_PLUS_ANNOT_PATTERN = regex.compile(r"\+\+\+.*?\+\+\+", flags=regex.DOTALL)

_DEV_DIGITS = "०१२३४५६७८९"
_KAN_DIGITS = "೦೧೨೩೪೫೬೭೮೯"
_DIGIT_MAP = {}
for _i, _ch in enumerate(_DEV_DIGITS):
  _DIGIT_MAP[_ch] = str(_i)
for _i, _ch in enumerate(_KAN_DIGITS):
  _DIGIT_MAP[_ch] = str(_i)


def _to_ascii_digits(s):
  return "".join(_DIGIT_MAP.get(ch, ch) for ch in s)


_FRACTION_PATTERN = regex.compile(r"[0-9०-९೦-೯]+/[0-9०-९೦-೯]+")


def _extract_ints(text):
  """Extract integer verse numbers from arbitrary text (titles/headings).

  Fractions like १/२ (half-verse marker) are stripped first so that they do
  not contribute spurious verse numbers 1 and 2.
  """
  text = _FRACTION_PATTERN.sub(" ", text or "")
  nums = set()
  for m in _DIGIT_SEQ_PATTERN.finditer(text):
    try:
      nums.add(int(_to_ascii_digits(m.group())))
    except ValueError:
      continue
  return nums


def _extract_danda_nums(body):
  """Extract verse numbers appearing inside ॥…॥ (avoids prose numbers)."""
  nums = set()
  for m in _DANDA_NUM_PATTERN.finditer(body or ""):
    inner = _FRACTION_PATTERN.sub(" ", m.group(1))
    nums |= _extract_ints(inner)
  return nums


def _contains_kannada_script(s):
  return bool(regex.search(r"[\u0C80-\u0CFF]", s or ""))


def _to_devanagari(text):
  if text and _contains_kannada_script(text):
    try:
      return sanscript.transliterate(text, _from=sanscript.KANNADA, _to=sanscript.DEVANAGARI)
    except Exception as e:
      logging.warning(f"Transliteration failed: {e}")
      return text
  return text


def _normalize_mula_for_comparison(text):
  """Normalize mula text so that trivial typographic variation is ignored.

  In particular, anusvAra (ं) vs varga-panchama + halant (ङ्/ञ्/ण्/न्/म्)
  is normalized to anusvAra, footnotes/markup/daNDas/whitespace are stripped.

  NFC-normalized first so that combining-mark orders (e.g. site nukta
  sequences) compare equal to what MdFile.dump_to_file writes (it NFCs).
  """
  import unicodedata
  text = unicodedata.normalize("NFC", _to_devanagari(text or ""))
  text = _FOOTNOTE_DEF_PATTERN.sub(" ", text)
  text = _FOOTNOTE_REF_PATTERN.sub(" ", text)
  text = _PLUS_ANNOT_PATTERN.sub(" ", text)
  text = text.replace("**", " ")
  # Asterisks (md italics from <em>) are never phonemic; strip before ref
  # parsing so refs glued to "*" (e.g. "॥ १-१-३*") still match.
  text = text.replace("*", " ")
  # Drop verse-number refs and daNDas for comparison purposes. Refs may be
  # closed ("॥ २ ॥"), dangling at end ("॥ १-१-२"), mid-text unclosed
  # ("॥ १-१-१८" + newline + more verse), or split across lines ("॥\n१-१-९").
  text = regex.sub(r"॥\s*[०-९0-9೦-೯½\s\-–—,/;]*?\s*(॥|(?=\n|$))", " ", text)
  text = text.replace("॥", " ").replace("।", " ")
  text = text.replace("ँ", "ं")
  # panchama + halant -> anusvAra (all contexts; comparison only).
  text = regex.sub(r"[ङञणनम]्", "ं", text)
  # Hyphens/dashes in mUla text are print artifacts: line-break hyphenation
  # (e.g. "प्रयासै-\nर्बाहौ" vs "प्रयासैर्बाहौ") or readability splits, never
  # phonemic. Ignore them, like spacing variation below.
  text = regex.sub(r"[-‐–—]", "", text)
  # Ignore invisible format chars (ZWJ/ZWNJ/BOM etc.) and spacing/sandhi-join
  # typographic variation (e.g. "तद् वाक्यं" vs "तद्वाक्यं").
  text = regex.sub(r"[\u200b-\u200f\ufeff\u00ad]", "", text)
  # Avagraha omission (ऽ) is typographic, like anusvAra variation - ignore it.
  text = text.replace("ऽ", "").replace("ʼ", "").replace("'", "")
  text = regex.sub(r"\s+", "", text).strip()
  return text


def _denumerified_mula_title(title):
  t = (title or "").strip()
  # Strip trailing verse-number/dash fragments like " - 18½", " - 1", "-32".
  t = regex.sub(r"[\s\-–—:]+[०-९0-9೦-೯½/,\s\-–—:]+$", "", t).strip()
  t = regex.sub(r"[\s\-–—:]+$", "", t).strip()
  return t


def _is_main_mula_title(title):
  """True for verse mUla details (excludes vachana, samApti and Tryambaka variants)."""
  if not _is_mula_title(title):
    return False
  if _is_vachana_title(title):
    return False
  base = _denumerified_mula_title(title)
  return base in ("मूलम्", "ಮೂಲಮ್")


def _is_translation_title(title):
  t = title or ""
  if "समाप्" in t or "ಸಮಾಪ್" in t or "समाप्त" in t or "ಸಮಾಪ್ತ" in t:
    return False
  return ("नुवाद" in t) or ("ನುವಾದ" in t)


def _is_mula_title(title):
  t = title or ""
  if "समाप्" in t or "ಸಮಾಪ್" in t or "समाप्त" in t or "ಸಮಾಪ್ತ" in t:
    return False
  return ("मूलम्" in t) or ("ಮೂಲಮ್" in t)


def _is_vachana_title(title):
  t = title or ""
  return ("वचन" in t) or ("वाचन" in t) or ("ವಚನ" in t) or ("ವಾचನ" in t) or ("ವಾಚನ" in t)


def _is_samapti_title(title):
  t = title or ""
  return ("समाप्" in t) or ("ಸಮಾಪ್" in t) or ("समाप्त" in t) or ("ಸಮಾಪ್ತ" in t)


def _is_samapti_translation_title(title):
  t = title or ""
  return _is_samapti_title(t) and (("नुवाद" in t) or ("ನುವಾದ" in t))


def _alt_to_dev_fixed(text):
  """Transliterate alt (kannaDa-script) text to devanAgarI, fixing lazy anusvAras."""
  return fix_lazy_anusvaara(_to_devanagari(text or ""))


# ---------------------------------------------------------------------------
# Grouping-artifact handling (stray half-verses across verse boundaries).
#
# Editions sometimes attach a half-verse to different verse numbers, e.g.
# Hindi keeps 5a ("लोलिता वसुधा...") inside the verse-4 block while Kannada
# groups {5a, 5b} as verse 5. Number-based alignment then compares mismatched
# spans and fabricates "variants". The helpers below detect such boundary
# disagreements at half-verse resolution and reroute stray units home
# instead of recording fake variants.
# ---------------------------------------------------------------------------

NEAR_RATIO = 0.85
NEAR_MARGIN = 0.75
NEAR_MINLEN = 20

_INDIC_LETTER_PATTERN = regex.compile("[\u0915-\u0939\u0905-\u0914\u0c95-\u0cb9\u0c85-\u0c94]")
_UNIT_STRIP_PATTERN = regex.compile(r"[०-९0-9೦-೯\s\-–—,/;:\*\'\"‘’“”\(\)\[\]½\d\.,;:_+=~।॥]+")
_DANDA_SPLIT_PATTERN = regex.compile(r"[।॥]+")


def _split_half_units(text):
  """Split mula text into half-verse units (on ।/॥), dropping ref-only fragments."""
  text = _FOOTNOTE_DEF_PATTERN.sub(" ", text or "")
  text = _FOOTNOTE_REF_PATTERN.sub(" ", text)
  text = _PLUS_ANNOT_PATTERN.sub(" ", text)
  units = []
  for frag in _DANDA_SPLIT_PATTERN.split(text):
    frag = frag.strip()
    if not frag:
      continue
    probe = _UNIT_STRIP_PATTERN.sub("", frag)
    if not probe:
      continue
    if not _INDIC_LETTER_PATTERN.search(probe):
      continue
    units.append(frag)
  return units


def _unit_norms(units):
  return [_normalize_mula_for_comparison(u) for u in units]


def _join_units_text(units):
  """Rejoin half-verse units for display (dandas were stripped on split)."""
  return "\n".join(u.strip() + " ।" for u in units if (u or "").strip())


def _unit_match_level(u_norm, cand_norms):
  """Best match of a normalized unit against candidates: 'exact', 'near' or None."""
  best = None
  best_ratio = 0.0
  for c in cand_norms:
    if not c:
      continue
    if u_norm == c:
      return ("exact", 1.0)
    if min(len(u_norm), len(c)) < NEAR_MINLEN:
      continue
    import difflib
    r = difflib.SequenceMatcher(None, u_norm, c).ratio()
    if r > best_ratio:
      best_ratio = r
  if best_ratio >= NEAR_RATIO:
    return ("near", best_ratio)
  return (None, best_ratio)


def _mula_original(body):
  """Dest mula text before any recorded _________________ variant."""
  return (body or "").split(VARIANT_SEPARATOR)[0]


def _neighbor_verse_sets(details, d_verses):
  """Verse sets of main-mula blocks adjacent to d_verses (n-1 / n+1)."""
  if not d_verses:
    return []
  lo, hi = min(d_verses), max(d_verses)
  wanted = {lo - 1, hi + 1}
  out = []
  for d in details:
    if not _is_main_mula_title(d["title"]):
      continue
    vs = set(d["verse_nums"])
    if vs and vs != set(d_verses) and (vs & wanted):
      out.append(d)
  return out


def _edge_units(units, which):
  """First (which="opening") or last (which="closing") non-empty unit."""
  units = [u for u in units if (u or "").strip()]
  if not units:
    return []
  return [units[0] if which == "opening" else units[-1]]


def _file_neighbor_scope(details, d_verses):
  """Alt-language EDGE-unit scope from dest-neighbor blocks.

  Returns list of (verse_tuple, unit_norm, unit_raw, edge) with edge in
  ("closing", "opening"): closing units of lower-verse blocks, opening units
  of higher-verse blocks — originals plus recorded units (_________________
  blobs and following VR blocks, positionally attributed). Boundary shifts
  move edge halves, so only edges are admissible as stray evidence; this
  keeps formulaic mid-block repetitions from false-flagging.
  """
  if not d_verses:
    return []
  lo, hi = min(d_verses), max(d_verses)
  scope = []
  for nd in _neighbor_verse_sets(details, d_verses):
    vt = tuple(sorted(nd["verse_nums"]))
    edge = "closing" if max(vt) < lo else "opening"
    for raw in _edge_units(_split_half_units(_mula_original(nd["body"])), edge):
      scope.append((vt, _normalize_mula_for_comparison(raw), raw, edge))
    parts = (nd["body"] or "").split(VARIANT_SEPARATOR)
    for blob in parts[1:]:
      for raw in _edge_units(_split_half_units(blob), edge):
        scope.append((vt, _normalize_mula_for_comparison(raw), raw, edge))
  # VR blocks: attribute to nearest preceding main-mula block.
  last_vt = None
  for d in details:
    if _is_main_mula_title(d["title"]):
      if set(d["verse_nums"]):
        last_vt = tuple(sorted(d["verse_nums"]))
    elif d["title"] == VR_MULA_TITLE and last_vt is not None:
      if set(last_vt) != set(d_verses) and (set(last_vt) & {lo - 1, hi + 1}):
        edge = "closing" if max(last_vt) < lo else "opening"
        for raw in _edge_units(_split_half_units(d["body"]), edge):
          scope.append((last_vt, _normalize_mula_for_comparison(raw), raw, edge))
  return scope


_VR_BARE_REF_PATTERN = regex.compile(r"([०-९0-9]+)\s*[-‐–—]\s*([०-९0-9]+)\s*[-‐–—]\s*([०-९0-9]+)")


def _unit_self_verses(raw_unit):
  """Explicit verse attribution from triple refs (k-s-v, verse-last) in a unit.

  Bare form (no ॥ needed): units never contain daNDas (splitting removed
  them), so refs glued to unit starts like "१-१-९२\\n..." must match too.
  """
  verses = set()
  for m in _VR_BARE_REF_PATTERN.finditer(raw_unit or ""):
    try:
      verses.add(int(_to_ascii_digits(m.groups()[-1])))
    except ValueError:
      continue
  return verses


def plan_variant_units(d_units, v_units, neighbor_scope, d_verses=None):
  """Classify alt-reading units against a dest block + neighbor scope.

  Returns dict(aligned=[...], strays=[(unit, home_verse_tuple)], uniques=[...]):
  - aligned: exact/near match inside the dest block (genuine sameness/difference).
  - strays: no dest match but exact/near match in neighbor scope (boundary
    artifact; home_verse_tuple says where the unit belongs).
  - uniques: match nothing anywhere (genuinely new material).
  """
  d_norms = [d for d in _unit_norms(d_units) if d]
  d_exact = set(d_norms)
  d_verses = set(d_verses or [])
  lo = min(d_verses) if d_verses else None
  hi = max(d_verses) if d_verses else None
  # Only block-EDGE units are stray candidates: leading units may belong to
  # the previous verse, trailing units to the next. Mid units are never
  # rerouted (boundary shifts move edge halves only).
  edge_idx = set()
  if v_units:
    edge_idx.add(0)
    edge_idx.add(len(v_units) - 1)

  def _scope_match(un, want_edge, want_side):
    """Match a unit against scope entries of one edge+side.

    Returns (home_vt, level) or (None, None). want_side is "prev" (lower
    verses, closing edge) or "next" (higher verses, opening edge).
    """
    home = None
    home_level = None
    for (vt, sn, _sraw, edge) in neighbor_scope:
      if not sn:
        continue
      if edge is not None and edge != want_edge:
        continue
      if d_verses and (set(vt) & d_verses):
        continue
      if want_side == "prev" and not (max(vt) < lo):
        continue
      if want_side == "next" and not (min(vt) > hi):
        continue
      if un == sn:
        return (vt, "exact")
      if home_level == "exact":
        continue
      if min(len(un), len(sn)) < NEAR_MINLEN:
        continue
      import difflib
      # Near-strays need clear separation from dest (margin): borderline
      # units stay aligned with their own verse block.
      if difflib.SequenceMatcher(None, un, sn).ratio() >= NEAR_RATIO and _r < NEAR_MARGIN:
        home, home_level = vt, "near"
    return (home, home_level)

  aligned, strays, uniques, protected = [], [], [], []
  for idx, raw in enumerate(v_units):
    un = _normalize_mula_for_comparison(raw)
    if not un:
      continue
    # Explicit triple-ref attribution overrules similarity: a unit carrying
    # refs into d_verses belongs here even if it resembles neighbor text
    # (formulaic repetitions); refs to adjacent verses route it home.
    self_v = _unit_self_verses(raw)
    if self_v:
      if self_v & d_verses:
        protected.append(raw)
        continue
      if d_verses and (max(self_v) == lo - 1 or min(self_v) == hi + 1):
        strays.append((raw, tuple(sorted(self_v)), "ref"))
      else:
        uniques.append(raw)
      continue
    lvl, _r = _unit_match_level(un, d_norms)
    if lvl is not None:
      aligned.append((raw, lvl))
      continue
    if idx not in edge_idx:
      uniques.append(raw)
      continue
    if idx == 0:
      (home, home_level) = _scope_match(un, "closing", "prev")
      # Single-unit blob: try the other direction too.
      if home is None and len(v_units) == 1:
        (home, home_level) = _scope_match(un, "opening", "next")
    else:
      (home, home_level) = _scope_match(un, "opening", "next")
    if home is not None:
      strays.append((raw, home, home_level))
    else:
      uniques.append(raw)
  return {"aligned": aligned, "strays": strays, "uniques": uniques,
          "protected": protected, "d_exact": d_exact}


def decide_variant(d_units, v_units, neighbor_scope, d_verses=None):
  """Decide a variant reading's fate under possible boundary disagreement.

  Returns (action, kept_units, moves) where action is "record_full"
  (no artifact: keep V as-is), "record_partial" (artifact: keep only
  differing units), or "skip" (nothing worth recording); moves is a list of
  (unit_raw, home_verse_tuple) for stray units to reroute home (exact-match
  strays are dropped silently since home already carries that reading).
  """
  if not v_units:
    return ("skip", [], [])
  plan = plan_variant_units(d_units, v_units, neighbor_scope, d_verses=d_verses)
  if not plan["strays"]:
    # No boundary artifact: record V whole unless identical to dest.
    if not plan["uniques"] and not plan["protected"] and all(lvl == "exact" for (_r, lvl) in plan["aligned"]):
      return ("skip", [], [])
    return ("record_full", list(v_units), [])
  moves = [(u, home) for (u, home, lvl) in plan["strays"] if lvl in ("near", "ref")]
  kept = [u for u in plan["uniques"]]
  kept += [r for (r, lvl) in plan["aligned"] if lvl == "near"]
  kept += list(plan["protected"])
  if not kept:
    return ("skip", [], moves)
  return ("record_partial", kept, moves)


def _alt_neighbor_scope(alt_verse_units):
  """Scope entries from live alt data: [(verse_tuple, norm, raw, None)].

  Edge is None (usable for either direction); the vt side check in the
  matcher still applies.
  """
  scope = []
  for (verses, raw_units) in alt_verse_units:
    vt = tuple(sorted(verses))
    for raw in raw_units:
      scope.append((vt, _normalize_mula_for_comparison(raw), raw, None))
  return scope


def _reroute_strays(content, moves):
  """Append stray units to their home blocks. Pure string transform.

  moves: [(kind, home_verses_tuple, [unit_raw, ...])], kind in ("sep", "vr").
  "sep" strays join the home mula's _________________ record (created if
  needed); "vr" strays join the home's VR block (created if needed).
  Presence-checked: already-recorded readings are not duplicated.
  Returns (new_content, n_moved).
  """
  if not moves:
    return (content, 0)
  details = _assign_translation_verse_sets(_parse_details(content or ""))
  # Pending new bodies keyed by id(detail-dict).
  pending = {}
  n_moved = 0

  def _home_dm(home_verses):
    for d in details:
      if _is_main_mula_title(d["title"]) and (set(d["verse_nums"]) & set(home_verses)):
        return d
    return None

  def _home_recorded_norms(home_dm):
    norms = set()
    body = pending.get(id(home_dm), home_dm["body"])
    for blob in body.split(VARIANT_SEPARATOR)[1:]:
      for u in _split_half_units(blob):
        norms.add(_normalize_mula_for_comparison(u))
    # Following VR blocks of home (positional).
    seen_home = False
    for d in details:
      if d is home_dm:
        seen_home = True
        continue
      if _is_main_mula_title(d["title"]):
        if seen_home:
          break
        continue
      if seen_home and d["title"] == VR_MULA_TITLE:
        body2 = pending.get(id(d), d["body"])
        for u in _split_half_units(body2):
          norms.add(_normalize_mula_for_comparison(u))
    return norms

  new_vr_inserts = []  # (pos, html)
  new_vr_batched = {}  # id(home_dm) -> [pos, home_dm, units]
  for (kind, home_verses, units) in moves:
    home_dm = _home_dm(home_verses)
    if home_dm is None:
      logging.warning(f"No home block for stray {units[0][:40] if units else ''} -> {sorted(home_verses)}")
      continue
    present = _home_recorded_norms(home_dm)
    fresh = [u for u in units
             if _normalize_mula_for_comparison(u) and _normalize_mula_for_comparison(u) not in present]
    if not fresh:
      continue
    if kind == "sep":
      body = pending.get(id(home_dm), home_dm["body"])
      stripped = body.strip()
      add = _join_units_text(fresh)
      if VARIANT_SEPARATOR in stripped:
        new_body = stripped + "\n" + add + "\n"
      else:
        new_body = stripped + f"\n{VARIANT_SEPARATOR}\n" + add + "\n"
      pending[id(home_dm)] = new_body
      n_moved += len(fresh)
    else:
      # VR kind: append to home's existing VR block if present else new block.
      target = None
      seen_home = False
      for d in details:
        if d is home_dm:
          seen_home = True
          continue
        if _is_main_mula_title(d["title"]):
          if seen_home:
            break
          continue
        if seen_home and d["title"] == VR_MULA_TITLE:
          target = d
          break
      add = _join_units_text(fresh)
      if target is not None:
        tbody = pending.get(id(target), target["body"])
        pending[id(target)] = tbody.strip() + "\n" + add + "\n"
      else:
        if id(home_dm) not in new_vr_batched:
          new_vr_batched[id(home_dm)] = [home_dm["end"], home_dm, []]
        new_vr_batched[id(home_dm)][2].extend(fresh)
      n_moved += len(fresh)

  for (_hid, (pos, _hdm, units)) in new_vr_batched.items():
    add = _join_units_text(units)
    new_vr_inserts.append((pos, f"\n\n<details><summary>{VR_MULA_TITLE}</summary>\n\n{add.strip()}\n</details>"))

  if not pending and not new_vr_inserts:
    return (content, 0)
  # Edits keyed by end-pos, descending; at ties inserts apply before the
  # replacement whose range ends there (so inserts land after new blocks).
  edits = []  # (end_pos, kind_flag, start_or_None, html); kind 0 = insert first
  for d in details:
    if id(d) in pending:
      new_body = pending[id(d)]
      new_block = f"<details{d['attrs']}><summary>{d['title']}</summary>\n\n{new_body.strip()}\n</details>"
      edits.append((d["end"], 1, d["start"], new_block))
  for (pos, html) in new_vr_inserts:
    edits.append((pos, 0, None, html))
  new_content = content
  for (e, _k, s, b) in sorted(edits, key=lambda x: (-x[0], x[1])):
    if s is None:
      new_content = new_content[:e] + b + new_content[e:]
    else:
      new_content = new_content[:s] + b + new_content[e:]
  return (new_content, n_moved)


def _parse_details(content):
  """Parse top-level details + headings in file order.

  own_nums prefer title + body-daNDa numbers; heading numbers are used only
  as a fallback when title/body yield nothing (e.g. bhAgavata kannaDa mUlas
  whose verse id lives only in the preceding #### heading). This avoids stale
  headings polluting later verses (e.g. rAmAyaNa ## (shloka 35½) headings).
  samApti (closing) details always get an empty set: colophon numbers
  (e.g. sarga "॥2॥") are not verse ids.
  """
  headings = [(m.start(), m.group("heading") or "") for m in _HEADING_PATTERN.finditer(content or "")]
  details = []
  for m in _DETAIL_PATTERN.finditer(content or ""):
    start = m.start()
    preceding = ""
    for h_start, h_text in headings:
      if h_start < start:
        preceding = h_text
      else:
        break
    title = (m.group("title") or "").strip()
    body = m.group("body") or ""
    if _is_samapti_title(title):
      own = set()
    else:
      primary = _extract_ints(title) | _extract_danda_nums(body)
      if primary:
        own = primary
      else:
        own = _extract_ints(preceding)
    details.append({
      "kind": "detail",
      "full": m.group(),
      "start": m.start(),
      "end": m.end(),
      "attrs": m.group("attrs") or "",
      "title": title,
      "body": body,
      "heading": preceding,
      "own_nums": own,
      "verse_nums": set(own),
    })
  return details


def _assign_translation_verse_sets(details):
  """Fill verse_nums for translation details using preceding mula groups.

  For each translation, verse set = own danda/title/heading numbers ∪ mula
  numbers accumulated since the previous translation. Mula verse sets stay as own.
  """
  acc = set()
  for d in details:
    if _is_main_mula_title(d["title"]):
      # Only verse-mulas contribute to the following translation's group.
      acc |= set(d["own_nums"])
    elif _is_translation_title(d["title"]):
      d["verse_nums"] = set(d["own_nums"]) | set(acc)
      acc = set()
  return details


def _leading_int(basename):
  m = _LEADING_NUM_PATTERN.match(basename or "")
  if not m:
    return None
  try:
    return int(m.group(1).lstrip("0") or "0")
  except ValueError:
    return None


def _alt_probes_and_union(alt_path):
  """Verse probes (first normalized main-mUla readings) + verse union for matching.

  Multiple probes (up to 3 opening verses) so that a single corrupted opening
  verse (e.g. one-akshara typo) cannot sink the match by itself.
  """
  try:
    (_, alt_content) = MdFile(file_path=alt_path).read()
  except Exception:
    return ([], set())
  alt_details = _assign_translation_verse_sets(_parse_details(alt_content))
  probes = []
  for m in [d for d in alt_details if _is_main_mula_title(d["title"]) and d["verse_nums"]][:3]:
    n = _normalize_mula_for_comparison(m["body"])
    if len(n) >= 20:
      probes.append(n[:60])
  union = set()
  for d in alt_details:
    if _is_translation_title(d["title"]) or _is_main_mula_title(d["title"]):
      union |= set(d["verse_nums"])
  return (probes, union)


def _dest_match_data(dest_path):
  try:
    (_, c_content) = MdFile(file_path=dest_path).read()
  except Exception:
    return (None, set())
  if not c_content:
    return (None, set())
  c_details = _assign_translation_verse_sets(_parse_details(c_content))
  union = set()
  for d in c_details:
    if _is_translation_title(d["title"]) or _is_main_mula_title(d["title"]):
      union |= set(d["verse_nums"])
  return (_normalize_mula_for_comparison(c_content), union)


def _is_verified_match(probes, alt_union, dest_norm, dest_union):
  """A path-based candidate counts only if verses corroborate it: some probe
  occurs in dest text AND verse sets overlap (guards shifted numbering)."""
  return bool(probes) and bool(dest_norm) and any(p in dest_norm for p in probes) \
    and bool(alt_union & dest_union)


def _find_dest_file(alt_path, dest_dir, alt_dir, dest_files_cache=None):
  """Find the dest counterpart for an alt file.

  Strategy: exact relative path (content-verified) → same-dir numeric-prefix
  match (content-verified) → content-overlap search across dest_dir
  (multi-probe). Returns path or None.
  """
  probes, alt_union = _alt_probes_and_union(alt_path)
  if not probes:
    return None
  rel = os.path.relpath(alt_path, alt_dir)
  candidate = os.path.join(dest_dir, rel)
  if os.path.isfile(candidate):
    dest_norm, dest_union = _dest_match_data(candidate)
    if _is_verified_match(probes, alt_union, dest_norm, dest_union):
      return candidate
    logging.warning(f"Exact-path candidate content-mismatch, searching instead: {candidate} <- {alt_path}")
  rel_dir = os.path.dirname(rel)
  dest_rel_dir = os.path.join(dest_dir, rel_dir) if rel_dir not in ("", ".") else dest_dir
  alt_num = _leading_int(os.path.basename(rel))
  if alt_num is not None and os.path.isdir(dest_rel_dir):
    try:
      siblings = [f for f in os.listdir(dest_rel_dir)
                  if f.endswith(".md") and os.path.isfile(os.path.join(dest_rel_dir, f))
                  and os.path.basename(f) != "_index.md"]
    except FileNotFoundError:
      siblings = []
    same_num = [os.path.join(dest_rel_dir, f) for f in siblings if _leading_int(f) == alt_num]
    verified = [c for c in same_num
                if _is_verified_match(probes, alt_union, *_dest_match_data(c))]
    if len(verified) == 1:
      return verified[0]
    if len(verified) > 1:
      # Disambiguate by verse overlap + preference for files lacking Kannada already.
      best = None
      best_score = (-1, 1)
      for cand in verified:
        try:
          (_, c_content) = MdFile(file_path=cand).read()
        except Exception:
          continue
        c_details = _assign_translation_verse_sets(_parse_details(c_content))
        c_union = set()
        for d in c_details:
          if _is_translation_title(d["title"]) or _is_main_mula_title(d["title"]):
            c_union |= set(d["verse_nums"])
        overlap = len(alt_union & c_union)
        has_kannada = ("अनुवाद (कन्नड)" in c_content) or ("ಕನ್ನಡ" in c_content)
        score = (overlap, 0 if has_kannada else 1)
        # Prefer larger overlap; on tie prefer file without Kannada yet (needs merging).
        # Actually for BhAgavatam 09.md vs 09_hi.md both overlap fully; prefer the
        # Hindi original (09_hi.md has Hindi translations). Both have Hindi, so fall
        # back to preferring the file whose basename matches alt basename most closely.
        if score > best_score or (score == best_score and os.path.basename(cand) == os.path.basename(rel)):
          best_score = score
          best = cand
      if best is not None:
        # If tie on overlap, prefer exact-basename-like match when possible.
        return best
  # Global content-overlap fallback (needed e.g. MB single-file alt at root,
  # or shifted numbering like kannaDa 12/ = skandha 11).
  if dest_files_cache is None:
    dest_files_cache = get_md_files_from_path(dir_path=dest_dir)
  best = None
  best_overlap = 0
  for dest_md in dest_files_cache:
    dp = str(dest_md.file_path)
    if os.path.basename(dp) == "_index.md" and os.path.dirname(dp) == dest_dir:
      # Skip top-level index; real content lives deeper (except MB stotra _index).
      # Allow nested _index files (e.g. MB 149 _index.md) - only skip root index.
      continue
    dest_norm, dest_union = _dest_match_data(dp)
    if dest_norm is None:
      continue
    if not any(p in dest_norm for p in probes):
      continue
    overlap = len(alt_union & dest_union) if (alt_union and dest_union) else 0
    if overlap > best_overlap:
      best_overlap = overlap
      best = dp
  return best


def _merge_single_file(dest_path, alt_path, dry_run=False):
  """Merge one alt file into its dest counterpart.

  - Inserts alt translations (transliterated to devanAgarI) as
    <details><summary>अनुवाद (कन्नड)</summary> below dest Hindi translations.
  - Compares verse mUlas (ignoring anusvAra/panchama variation); on significant
    variation appends the alt reading to the dest mUla detail after
    VARIANT_SEPARATOR.
  Returns (merged_bool, n_trans_inserted, n_variants_added).
  """
  dest_md = MdFile(file_path=dest_path)
  alt_md = MdFile(file_path=alt_path)
  (dest_meta, dest_content) = dest_md.read()
  (alt_meta, alt_content) = alt_md.read()
  if not dest_content or not dest_content.strip():
    logging.warning(f"Empty dest, skipping: {dest_path}")
    return (False, 0, 0)
  dest_details = _assign_translation_verse_sets(_parse_details(dest_content))
  alt_details = _assign_translation_verse_sets(_parse_details(alt_content))

  dest_hindi = [d for d in dest_details
                if _is_translation_title(d["title"]) and "कन्नड" not in (d["title"] or "")]
  # Exclude Kannada-script titles already in dest (previous partial merges use devanAgarI
  # "अनुवाद (कन्नड)", so the above filter suffices; keep it simple).
  alt_trans = [d for d in alt_details if _is_translation_title(d["title"])]
  if not alt_trans:
    logging.info(f"No translations in alt, skipping: {alt_path}")
    return (False, 0, 0)
  if not dest_hindi:
    logging.warning(f"No Hindi translations in dest, skipping: {dest_path} <- {alt_path}")
    return (False, 0, 0)

  dest_kannada = [d for d in dest_details
                  if _is_translation_title(d["title"]) and "कन्नड" in (d["title"] or "")]
  dest_kannada_norms = [_normalize_mula_for_comparison(d["body"]) for d in dest_kannada]
  dest_whole_norm = _normalize_mula_for_comparison(dest_content)

  # Map dest hindi position -> list of alt_trans to insert after it.
  insert_map = defaultdict(list)
  unhandled = []
  for alt in alt_trans:
    a_verses = set(alt["verse_nums"])
    if not a_verses:
      unhandled.append(alt)
      continue
    overlapping = [d for d in dest_hindi if set(d["verse_nums"]) & a_verses]
    if not overlapping:
      unhandled.append(alt)
      continue
    # Already present? (idempotency for full or partial merges)
    alt_dev = _alt_to_dev_fixed(alt["body"].strip())
    alt_norm = _normalize_mula_for_comparison(alt_dev)
    already = False
    for kd, kn in zip(dest_kannada, dest_kannada_norms):
      if set(kd["verse_nums"]) & a_verses and (kn == alt_norm or (alt_norm and alt_norm in kn)):
        already = True
        break
    if not already and alt_norm and alt_norm in dest_whole_norm:
      # Same translation text already somewhere in dest (different grouping) - treat as present.
      already = True
    if already:
      continue
    last = max(overlapping, key=lambda x: x["end"])
    insert_map[id(last)].append(alt)

  # Mula variant detection: only when alt subset-covers dest (avoids split-vs-grouped false positives).
  dest_mulas = [d for d in dest_details if _is_main_mula_title(d["title"])]
  alt_mulas = [d for d in alt_details if _is_main_mula_title(d["title"])]
  variant_map = {}  # id(dest_mula) -> combined alt variant dev text
  pending_moves = []  # (kind, home_verses, [units]) for grouping strays
  for dm in dest_mulas:
    d_verses = set(dm["verse_nums"])
    if not d_verses:
      continue
    if VARIANT_SEPARATOR in (dm["body"] or ""):
      continue  # Already has a recorded variant; keep idempotent.
    covering = [a for a in alt_mulas if set(a["verse_nums"]) and set(a["verse_nums"]) <= d_verses]
    if not covering:
      continue
    union = set()
    for a in covering:
      union |= set(a["verse_nums"])
    if union != d_verses:
      continue  # Grouping mismatch - cannot reliably compare.
    covering_sorted = sorted(covering, key=lambda x: x["start"])
    alt_combined = "\n".join(a["body"].strip() for a in covering_sorted if a["body"].strip())
    if not alt_combined.strip():
      continue
    alt_combined_dev = _alt_to_dev_fixed(alt_combined.strip())
    dest_norm = _normalize_mula_for_comparison(_mula_original(dm["body"]))
    alt_norm = _normalize_mula_for_comparison(alt_combined_dev)
    if not dest_norm or not alt_norm:
      continue
    if dest_norm == alt_norm:
      continue
    # Already recorded?
    if alt_norm in dest_norm:
      continue
    # Grouping-artifact guard: stray halves reroute home instead of
    # fabricating variants; partial readings record only differing units.
    lo, hi = min(d_verses), max(d_verses)
    alt_scope = _alt_neighbor_scope(
      [(set(a["verse_nums"]), _split_half_units(_alt_to_dev_fixed(a["body"])))
       for a in alt_mulas if set(a["verse_nums"]) & {lo - 1, hi + 1}])
    scope = _file_neighbor_scope(dest_details, d_verses) + alt_scope
    (action, kept, mv) = decide_variant(
      _split_half_units(_mula_original(dm["body"])), _split_half_units(alt_combined_dev),
      scope, d_verses=d_verses)
    if mv:
      pending_moves.extend([("sep", home, [u]) for (u, home) in mv])
    if action == "skip":
      continue
    if action == "record_partial":
      variant_map[id(dm)] = _join_units_text(kept)
      continue
    variant_map[id(dm)] = alt_combined_dev

  # SamApti (closing) translations: unmatched by verse (colophon numbers are
  # sarga numbers, not verse ids). Transliterate the title and add (कन्नड).
  samapti_htmls = []
  for alt in alt_details:
    if not _is_samapti_translation_title(alt["title"]):
      continue
    body = (alt["body"] or "").strip()
    if not body:
      continue
    alt_fixed = _alt_to_dev_fixed(body)
    alt_norm = _normalize_mula_for_comparison(alt_fixed)
    if not alt_norm or (alt_norm in dest_whole_norm):
      continue  # already present
    title_dev = _to_devanagari(alt["title"].strip())
    samapti_htmls.append(
      f"\n\n<details><summary>{title_dev} (कन्नड)</summary>\n\n{alt_fixed}\n</details>")

  if not insert_map and not variant_map and not samapti_htmls and not pending_moves:
    # Nothing new, but check whether everything is already merged (for deletion).
    all_handled = not unhandled
    if all_handled:
      # All alt translations either inserted previously or overlapping dest kannada.
      # Verify: every alt_trans is either skipped as already-present or would be inserted.
      # Since insert_map is empty, they must all be already-present.
      return (True, 0, 0)
    logging.info(f"No new content to merge for {dest_path} <- {alt_path}; unhandled={len(unhandled)}")
    return (False, 0, 0)

  # Apply edits from the end of the file backwards.
  new_content = dest_content
  # 1) Mula variant replacements (replace whole detail block).
  mula_replacements = []
  for dm in dest_mulas:
    if id(dm) in variant_map:
      new_body = dm["body"].strip() + f"\n{VARIANT_SEPARATOR}\n" + variant_map[id(dm)].strip() + "\n"
      new_block = f"<details{dm['attrs']}><summary>{dm['title']}</summary>\n\n{new_body}</details>"
      mula_replacements.append((dm["start"], dm["end"], new_block))
  for s, e, block in sorted(mula_replacements, key=lambda x: x[0], reverse=True):
    new_content = new_content[:s] + block + new_content[e:]
    # Shift stored positions for subsequent insertions? Insertions use original positions,
    # so recompute: easier to apply insertions first by position in the ORIGINAL string,
    # but replacements change offsets. To keep it simple, re-parse after replacements
    # if both kinds exist. Here we apply mula first then re-derive insertion anchors
    # by searching for the hindi blocks in the updated content.
  n_variants = len(mula_replacements)

  # Re-parse to get fresh offsets if we changed mula blocks and also need insertions.
  insert_list = []  # (anchor_end, html)
  if insert_map:
    if mula_replacements:
      reparsed = _assign_translation_verse_sets(_parse_details(new_content))
      # Rebuild dest_hindi anchors by matching (title, verse_nums) - titles may repeat,
      # so match in order.
      # Build a queue per (title) in order.
      from collections import deque
      key_to_queue = defaultdict(deque)
      for d in reparsed:
        if _is_translation_title(d["title"]) and "कन्नड" not in (d["title"] or ""):
          key_to_queue[(d["title"], tuple(sorted(d["verse_nums"])))].append(d)
      # Original dest_hindi in file order:
      orig_hindi_sorted = sorted(dest_hindi, key=lambda x: x["start"])
      for orig in orig_hindi_sorted:
        if id(orig) in insert_map:
          key = (orig["title"], tuple(sorted(orig["verse_nums"])))
          if key_to_queue[key]:
            fresh = key_to_queue[key].popleft()
            for alt in insert_map[id(orig)]:
              alt_dev = _alt_to_dev_fixed(alt["body"].strip())
              html = f"\n\n<details><summary>{KANNADA_TRANS_TITLE}</summary>\n\n{alt_dev}\n</details>"
              insert_list.append((fresh["end"], html))
    else:
      for orig in dest_hindi:
        if id(orig) in insert_map:
          for alt in insert_map[id(orig)]:
            alt_dev = _alt_to_dev_fixed(alt["body"].strip())
            html = f"\n\n<details><summary>{KANNADA_TRANS_TITLE}</summary>\n\n{alt_dev}\n</details>"
            insert_list.append((orig["end"], html))
    for pos, html in sorted(insert_list, key=lambda x: x[0], reverse=True):
      new_content = new_content[:pos] + html + new_content[pos:]
  n_trans = len(insert_list)

  if samapti_htmls:
    # Anchor after the last dest samApti block (e.g. समाप्तिः); else append at EOF.
    # Fresh parse: mula replacements above may have shifted offsets.
    reparsed_s = _parse_details(new_content)
    anchors = [d for d in reparsed_s
               if _is_samapti_title(d["title"]) and "(कन्नड)" not in (d["title"] or "")]
    if anchors:
      apos = max(anchors, key=lambda x: x["end"])["end"]
      new_content = new_content[:apos] + "".join(samapti_htmls) + new_content[apos:]
    else:
      new_content = new_content.rstrip() + "".join(samapti_htmls) + "\n"
    n_trans += len(samapti_htmls)

  n_moved = 0
  if pending_moves:
    # Reroute grouping strays home (fresh offsets; presence-checked inside).
    (new_content, n_moved) = _reroute_strays(new_content, pending_moves)

  if new_content != dest_content:
    if not dry_run:
      dest_md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Merged {dest_path} <- {alt_path}: +{n_trans} kannaDa translations, +{n_variants} variants, +{n_moved} moved")
    return (True, n_trans, n_variants)
  return (False, 0, 0)


def _remove_spurious_variants_single_file(dest_path, dry_run=False):
  """Drop recorded mUla variants that are insignificant under current normalization.

  Splits each mUla detail body at VARIANT_SEPARATOR; if the recorded variant
  normalizes equal to the original reading (e.g. only line-break hyphenation
  differed), restores the original body. Returns number of variants removed.
  """
  dest_md = MdFile(file_path=dest_path)
  (dest_meta, dest_content) = dest_md.read()
  if VARIANT_SEPARATOR not in (dest_content or ""):
    return 0
  details = _parse_details(dest_content)
  replacements = []
  for d in details:
    if not _is_main_mula_title(d["title"]):
      continue
    if VARIANT_SEPARATOR not in (d["body"] or ""):
      continue
    original, _, recorded = d["body"].partition(VARIANT_SEPARATOR)
    if not original.strip() or not recorded.strip():
      continue
    if _normalize_mula_for_comparison(original) == _normalize_mula_for_comparison(recorded):
      new_body = original.strip() + "\n"
      new_block = f"<details{d['attrs']}><summary>{d['title']}</summary>\n\n{new_body}</details>"
      replacements.append((d["start"], d["end"], new_block))
  if not replacements:
    return 0
  new_content = dest_content
  for s, e, block in sorted(replacements, key=lambda x: x[0], reverse=True):
    new_content = new_content[:s] + block + new_content[e:]
  if new_content != dest_content:
    if not dry_run:
      dest_md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Removed {len(replacements)} spurious variants in {dest_path}")
    return len(replacements)
  return 0


def remove_spurious_mula_variants(dest_dir, dry_run=False):
  """Remove insignificant recorded mUla variants under dest_dir.

  Keeps variants that remain significantly different after normalization;
  only drops ones equal to the original (e.g. hyphenation-only differences).
  """
  md_files = get_md_files_from_path(dir_path=dest_dir)
  n_files = 0
  n_removed = 0
  for md_file in tqdm(sorted(md_files, key=lambda m: str(m.file_path)), desc=f"Cleaning variants in {dest_dir}"):
    try:
      n = _remove_spurious_variants_single_file(str(md_file.file_path), dry_run=dry_run)
    except Exception as e:
      logging.exception(f"Failed cleaning {md_file.file_path}: {e}")
      continue
    if n:
      n_files += 1
      n_removed += n
  logging.info(f"remove_spurious_mula_variants {dest_dir}: files={n_files} removed={n_removed}")
  return {"files": n_files, "removed": n_removed}


def prune_index_only_dirs(root_dir, dry_run=False):
  """Delete directories under root_dir left with just _index.md (bottom-up).

  After merging, alt dirs whose content files were all merged+deleted contain
  only their _index.md stub. Removes such dirs (never root_dir itself);
  parents that thereby become index-only are pruned too. Returns removed dirs.
  """
  import shutil
  removed = []
  for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
    if os.path.abspath(dirpath) == os.path.abspath(root_dir):
      continue
    try:
      entries = os.listdir(dirpath)
    except FileNotFoundError:
      continue  # already pruned via a parent
    if len(entries) == 1 and entries[0] == "_index.md" \
        and os.path.isfile(os.path.join(dirpath, "_index.md")):
      if not dry_run:
        shutil.rmtree(dirpath)
      logging.info(f"{'Would remove' if dry_run else 'Removed'} index-only dir: {dirpath}")
      removed.append(dirpath)
  logging.info(f"prune_index_only_dirs {root_dir}: removed={len(removed)}")
  return {"removed": removed}


def merge_translations(dest_dir, alt_dir, dry_run=False):
  """Merge parallel translations: alt_dir -> dest_dir.

  For each md file under alt_dir, finds the corresponding dest file (exact
  relative path, else same-directory numeric-prefix match, else content-overlap
  search), inserts alt translations (transliterated to devanAgarI with lazy
  anusvAras fixed) below the dest Hindi translation as ``अनुवाद (कन्नड)``
  details, compares verse mUlas ignoring anusvAra/panchama typographic
  variation and appends significant variant readings to the dest mUla detail
  separated by ``_________________``. Unmatched closing (samApti) translations
  are appended after the dest samApti block with a ``(कन्नड)``-suffixed title.

  Every alt file thus merged is deleted (unless dry_run).
  """
  alt_files = [m for m in get_md_files_from_path(dir_path=alt_dir)
               if os.path.basename(str(m.file_path)) != "_index.md"]
  dest_cache = get_md_files_from_path(dir_path=dest_dir)
  n_merged = 0
  n_trans_total = 0
  n_var_total = 0
  n_skipped = 0
  for alt_md in tqdm(sorted(alt_files, key=lambda m: str(m.file_path)), desc=f"Merging {alt_dir} -> {dest_dir}"):
    alt_path = str(alt_md.file_path)
    dest_path = _find_dest_file(alt_path, dest_dir, alt_dir, dest_files_cache=dest_cache)
    if dest_path is None:
      logging.warning(f"No dest counterpart, skipping alt: {alt_path}")
      n_skipped += 1
      continue
    try:
      (merged, n_t, n_v) = _merge_single_file(dest_path, alt_path, dry_run=dry_run)
    except Exception as e:
      logging.exception(f"Failed merging {dest_path} <- {alt_path}: {e}")
      n_skipped += 1
      continue
    n_trans_total += n_t
    n_var_total += n_v
    if merged:
      n_merged += 1
      if not dry_run:
        try:
          os.remove(alt_path)
          logging.info(f"Removed merged alt file: {alt_path}")
        except FileNotFoundError:
          pass
    else:
      n_skipped += 1
  logging.info(f"merge_translations {alt_dir} -> {dest_dir}: merged={n_merged} skipped={n_skipped} "
               f"translations_added={n_trans_total} variants_added={n_var_total}")
  return {"merged": n_merged, "skipped": n_skipped,
          "translations_added": n_trans_total, "variants_added": n_var_total}


# ---------------------------------------------------------------------------
# valmikiramayan.net (VR) commentary merger
#
# Merges English word-meanings/translation/notes from
# https://www.valmikiramayan.net into per-verse details named after the
# commentator, plus shloka variants into "मूलम् - VR" details.
# ---------------------------------------------------------------------------

VR_KANDA_URL_IDS = {
  1: ("baala", "bala"),
  2: ("ayodhya", "ayodhya"),
  3: ("aranya", "aranya"),
  4: ("kish", "kishkindha"),
  5: ("sundara", "sundara"),
  6: ("yuddha", "yuddha"),
}

VR_AUTHOR_BY_KANDA = {
  1: "Desiraju Hanumanta Rao",
  2: "Murali Krishnamurthy Kopalle Murthy",
  3: "Desiraju Hanumanta Rao",
  4: "Desiraju Hanumanta Rao",
  5: "Murali Krishnamurthy Kopalle Murthy",
  6: "Murali Krishnamurthy Kopalle Murthy",
}

VR_DEST_SUBDIR_BY_KANDA = {
  1: "1_bAlakANDam",
  2: "2_ayodhyAkANDam",
  3: "3_araNyakANDam",
  4: "4_kiShkindhAkANDam",
  5: "5_sundarakANDam",
  6: "6_yuddhakANDam",
}

VR_MULA_TITLE = "मूलम् - VR"

_VR_REF_PATTERN = regex.compile(r"॥\s*([०-९0-9]+)\s*[-‐–—]\s*([०-९0-9]+)\s*[-‐–—]\s*([०-९0-9]+)")
_VR_ANCHOR_PATTERN = regex.compile(r"^Verse(\d+)$")
_VR_STOP_PREFIXES = ("Thus completes", "इति वाल्मीकि", "इति श्रीमद्रामायणे",
                     "Verse Locator for Book", "Top of Page", "- - -")


def vr_sarga_url(kanda, sarga):
  (id1, id2) = VR_KANDA_URL_IDS[kanda]
  return f"https://www.valmikiramayan.net/utf8/{id1}/sarga{sarga}/{id2}sans{sarga}.htm"


def _vr_rich_text(el):
  """Serialize an lxml element to markdown-ish text (*em*, newlines for br)."""
  chunks = []
  def rec(node):
    if node.tag == "br":
      chunks.append("\n")
      return
    if node.text:
      chunks.append(node.text)
    for ch in node:
      if ch.tag == "em":
        chunks.append("*")
        rec(ch)
        chunks.append("*")
      else:
        rec(ch)
      if ch.tail:
        chunks.append(ch.tail)
  rec(el)
  text = "".join(chunks)
  text = regex.sub(r"[ \t\xa0]+", " ", text)
  lines = [ln.rstrip() for ln in text.split("\n")]
  text = "\n".join(lines)
  text = regex.sub(r"\n{3,}", "\n\n", text)
  return text.strip()


def _vr_clean_sanskrit(text):
  text = text.replace("||", "॥").replace("|", "।")
  lines = [regex.sub(r"\s+", " ", ln).strip() for ln in text.split("\n")]
  lines = [ln for ln in lines if ln]
  return "\n".join(lines)


def _vr_ref_verses(text):
  """Verse numbers from ॥ k-s-v ॥ triple refs (last component is the verse;
  some pages reverse the order to s-k-v, still verse-last)."""
  verses = set()
  for m in _VR_REF_PATTERN.finditer(text or ""):
    try:
      verses.add(int(_to_ascii_digits(m.groups()[-1])))
    except ValueError:
      continue
  return verses


def _vr_is_stop_el(el):
  text = "".join(el.itertext()).strip()
  if not text:
    return False
  if "©" in text and len(text) < 120:
    return True
  return text.startswith(_VR_STOP_PREFIXES)


def fetch_vr_sarga(kanda, sarga, cache_dir=None, session=None, timeout=30):
  """Fetch + parse one VR sarga page. Returns dict or None on failure.

  Dict: {"url", "heading", "intro_paras", "verses": [{"verses", "sanskrit",
  "pratipada", "tat", "comments"}]}. Raw HTML cached under cache_dir.
  """
  import time
  url = vr_sarga_url(kanda, sarga)
  cache_path = None
  if cache_dir is not None:
    os.makedirs(cache_dir, exist_ok=True)
    (id1, _id2) = VR_KANDA_URL_IDS[kanda]
    cache_path = os.path.join(cache_dir, f"{id1}_sarga{sarga}.html")
  html_bytes = None
  if cache_path is not None and os.path.isfile(cache_path):
    with open(cache_path, "rb") as f:
      html_bytes = f.read()
  else:
    if session is None:
      import requests
      session = requests.Session()
      session.headers.update({"User-Agent": "doc_curation/1.0 (research)"})
    last_err = None
    for attempt in range(3):
      try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 404:
          logging.warning(f"VR page not found (404): {url}")
          return None
        resp.raise_for_status()
        html_bytes = resp.content
        break
      except Exception as e:
        last_err = e
        logging.warning(f"VR fetch attempt {attempt + 1}/3 failed for {url}: {e}")
        time.sleep(2 * (attempt + 1))
    if html_bytes is None:
      logging.error(f"VR fetch failed for {url}: {last_err}")
      return None
    if cache_path is not None:
      with open(cache_path, "wb") as f:
        f.write(html_bytes)
  from lxml import html as lh
  tree = lh.fromstring(html_bytes)
  h3_els = tree.xpath("//h3")
  heading = _vr_rich_text(h3_els[0]) if h3_els else ""
  heading = "\n".join(ln for ln in heading.split("\n")
                      if ln.strip() and "Verses converted to UTF-8" not in ln
                      and ln.strip() != "Introduction").strip()
  # Intro: tat/txt paras after h3, before first verloc (class varies by kanda).
  intro_paras = []
  if h3_els:
    node = h3_els[0].getnext()
    while node is not None:
      if not isinstance(node.tag, str):
        node = node.getnext()
        continue
      cls = (node.get("class") or "")
      if "verloc" in cls:
        break
      if node.tag == "p" and ("tat" in cls or "txt" in cls):
        t = _vr_rich_text(node)
        if t:
          intro_paras.append(t)
      node = node.getnext()
  verses = []
  verlocs = [el for el in tree.xpath("//p[@class='verloc']")]
  for vl in verlocs:
    anchors = set()
    for name in vl.xpath(".//a/@name"):
      m = _VR_ANCHOR_PATTERN.match((name or "").strip())
      if m:
        anchors.add(int(m.group(1)))
    sanskrits, pratipada, tats, comments = [], "", [], []
    node = vl.getnext()
    while node is not None:
      if not isinstance(node.tag, str):
        node = node.getnext()
        continue
      cls = (node.get("class") or "")
      if "verloc" in cls or _vr_is_stop_el(node):
        break
      if node.tag == "p" and "SanSloka" in cls:
        # Skip audio-only blocks (no Devanagari text).
        raw = "".join(node.itertext())
        if regex.search(r"[\u0900-\u097F]", raw):
          t = _vr_clean_sanskrit(_vr_rich_text(node))
          if t:
            sanskrits.append(t)
      elif node.tag == "p" and "pratipada" in cls:
        t = _vr_rich_text(node)
        if t:
          pratipada = (pratipada + "\n" + t).strip() if pratipada else t
      elif node.tag == "p" and "tat" in cls:
        t = _vr_rich_text(node)
        if t:
          tats.append(t)
      elif node.tag == "p" and "comment" in cls:
        t = _vr_rich_text(node)
        if t:
          comments.append(t)
      node = node.getnext()
    sanskrit = "\n".join(sanskrits).strip()
    # Leading ॐ is the site's page-mangala, not part of the shloka.
    sanskrit = regex.sub(r"^ॐ\s*", "", sanskrit)
    verse_set = set(anchors) | _vr_ref_verses(sanskrit)
    if not verse_set:
      continue  # locator-only paragraph (or footer), not a verse block
    if not sanskrit and not pratipada and not tats and not comments:
      continue
    verses.append({"verses": verse_set, "sanskrit": sanskrit,
                   "pratipada": pratipada, "tat": "\n\n".join(tats).strip(),
                   "comments": comments})
  if not verses and not intro_paras:
    logging.warning(f"VR page parsed empty: {url}")
    return None
  return {"url": url, "heading": heading, "intro_paras": intro_paras, "verses": verses}


def _dest_sarga_map(kanda_dir):
  """Map sarga number -> dest md path (prefers 056_x over 056a_x)."""
  mapping = {}
  for md in get_md_files_from_path(dir_path=kanda_dir):
    path = str(md.file_path)
    base = os.path.basename(path)
    if base == "_index.md":
      continue
    m = regex.match(r"^(\d+)", base)
    if not m:
      continue
    num = int(m.group(1))
    after = base[m.end():m.end() + 1]
    exact = after in ("_", ".", "-")
    if num not in mapping or (exact and not mapping[num][1]):
      mapping[num] = (path, exact)
  for num, (path, exact) in sorted(mapping.items()):
    if not exact:
      logging.warning(f"Sarga {num} in {kanda_dir} maps only to non-exact file: {path}")
  return {num: path for num, (path, _exact) in mapping.items()}


def merge_vr_sarga_into_file(dest_path, sarga_data, author, dry_run=False):
  """Merge one VR sarga (commentary + intro + mula variants) into a dest file.

  Returns (n_commentaries, n_variants).
  """
  dest_md = MdFile(file_path=dest_path)
  (_meta, dest_content) = dest_md.read()
  if dest_content is None:
    dest_content = ""
  details = _assign_translation_verse_sets(_parse_details(dest_content))
  dest_whole_norm = _normalize_mula_for_comparison(dest_content)
  url = sarga_data.get("url", "")
  source_line = f"\n\nस्रोतः: [valmikiramayan.net]({url})" if url else ""
  inserts = []
  n_com = 0
  n_var = 0

  def _commentary_body(v):
    sections = []
    if v["pratipada"].strip():
      sections.append("**पदच्छेदः**\n\n" + v["pratipada"].strip())
    if v["tat"].strip():
      sections.append("**अनुवादः**\n\n" + v["tat"].strip())
    for c in v["comments"]:
      if c.strip():
        sections.append("**टिप्पनी**\n\n" + c.strip())
    if not sections:
      return ""
    return "\n\n".join(sections) + source_line

  # Intro block at top of content.
  intro_title = f"{author} - Intro"
  if sarga_data.get("intro_paras") and not any(d["title"] == intro_title for d in details):
    intro_body = ""
    if sarga_data.get("heading"):
      intro_body += "**" + sarga_data["heading"].strip() + "**\n\n"
    intro_body += "\n\n".join(sarga_data["intro_paras"]) + source_line
    inserts.append((0, f"<details><summary>{intro_title}</summary>\n\n{intro_body.strip()}\n</details>\n\n"))
    n_com += 1

  dest_trans = [d for d in details
                if _is_translation_title(d["title"]) and not _is_samapti_title(d["title"])]
  dest_mulas = [d for d in details if _is_main_mula_title(d["title"])]

  for v in sarga_data.get("verses", []):
    verses = set(v["verses"])
    if not verses:
      continue
    body = _commentary_body(v)
    if body:
      key_text = (v["tat"] or v["pratipada"] or (v["comments"][0] if v["comments"] else ""))[:100]
      key_norm = _normalize_mula_for_comparison(key_text)
      if not (key_norm and key_norm in dest_whole_norm):
        overlapping = [d for d in dest_trans if set(d["verse_nums"]) & verses]
        if not overlapping:
          overlapping = [d for d in dest_mulas if set(d["verse_nums"]) & verses]
        if overlapping:
          anchor = max(overlapping, key=lambda x: x["end"])
          inserts.append((anchor["end"],
                          f"\n\n<details><summary>{author}</summary>\n\n{body}\n</details>"))
          n_com += 1
        else:
          logging.warning(f"No dest anchor for VR verses {sorted(verses)} in {dest_path}")
    # Mula variant: staged per verse-group; compared jointly below so that
    # split-vs-grouped verse divisions still align (subset-cover rule).
    sanskrit = (v["sanskrit"] or "").strip()
    if sanskrit:
      vr_norm = _normalize_mula_for_comparison(sanskrit)
      if vr_norm and vr_norm not in dest_whole_norm:
        v["_vr_norm"] = vr_norm
        v["_verses"] = verses
      else:
        v["_vr_norm"] = None

  # Mula variants: only when VR blocks subset-cover a dest mula exactly
  # (avoids split-vs-grouped false positives). Grouping-artifact guard:
  # stray halves reroute home instead of fabricating variants.
  vr_blocks = [v for v in sarga_data.get("verses", []) if v.get("_vr_norm")]
  vr_scope_all = _alt_neighbor_scope(
    [(set(v["verses"]), _split_half_units(v["sanskrit"]))
     for v in sarga_data.get("verses", []) if set(v["verses"])])
  inserted_norms = set()
  pending_moves = []
  for dm in dest_mulas:
    d_verses = set(dm["verse_nums"])
    if not d_verses:
      continue
    covering = [v for v in vr_blocks if v["_verses"] and v["_verses"] <= d_verses]
    if not covering:
      continue
    union = set()
    for v in covering:
      union |= v["_verses"]
    if union != d_verses:
      continue
    combined = "\n".join(v["sanskrit"].strip() for v in sorted(covering, key=lambda x: min(x["_verses"])))
    combined_norm = _normalize_mula_for_comparison(combined)
    dest_norm = _normalize_mula_for_comparison(dm["body"].split(VARIANT_SEPARATOR)[0])
    if not dest_norm or not combined_norm or dest_norm == combined_norm:
      continue
    if combined_norm in dest_whole_norm or combined_norm in inserted_norms:
      continue  # already recorded (previous run or earlier mula in this run)
    lo, hi = min(d_verses), max(d_verses)
    scope = _file_neighbor_scope(details, d_verses) + [
      e for e in vr_scope_all if set(e[0]) & {lo - 1, hi + 1}]
    (action, kept, mv) = decide_variant(
      _split_half_units(dm["body"].split(VARIANT_SEPARATOR)[0]), _split_half_units(combined),
      scope, d_verses=d_verses)
    if mv:
      pending_moves.extend([("vr", home, [u]) for (u, home) in mv])
    if action == "skip":
      continue
    if action == "record_partial":
      combined = _join_units_text(kept)
      combined_norm = _normalize_mula_for_comparison(combined)
      if combined_norm in dest_whole_norm or combined_norm in inserted_norms:
        continue
    inserted_norms.add(combined_norm)
    inserts.append((dm["end"],
                    f"\n\n<details><summary>{VR_MULA_TITLE}</summary>\n\n{combined.strip()}\n</details>"))
    n_var += 1

  if not inserts and not pending_moves:
    return (0, 0)
  new_content = dest_content
  for pos, html in sorted(inserts, key=lambda x: x[0], reverse=True):
    new_content = new_content[:pos] + html + new_content[pos:]
  n_moved = 0
  if pending_moves:
    (new_content, n_moved) = _reroute_strays(new_content, pending_moves)
  if new_content != dest_content:
    if not dry_run:
      dest_md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Merged VR into {dest_path}: +{n_com} commentaries, +{n_var} variants, +{n_moved} moved")
    return (n_com, n_var)
  return (0, 0)


def _dedupe_identical_details_single_file(dest_path, titles, dry_run=False):
  """Drop byte-identical duplicate detail blocks (same title + same body).

  Keeps the first occurrence. Distinct bodies (e.g. the site's own
  misnumbered pratipada openings) are never touched.
  """
  import unicodedata
  dest_md = MdFile(file_path=dest_path)
  (_meta, dest_content) = dest_md.read()
  if not dest_content:
    return 0
  details = _parse_details(dest_content)
  seen = set()
  removals = []
  for d in details:
    if d["title"] not in titles:
      continue
    key = (d["title"], unicodedata.normalize("NFC", (d["body"] or "").strip()))
    if key in seen:
      removals.append((d["start"], d["end"]))
    else:
      seen.add(key)
  if not removals:
    return 0
  new_content = dest_content
  for s, e in sorted(removals, key=lambda x: x[0], reverse=True):
    new_content = new_content[:s] + new_content[e:]
  new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
  if new_content != dest_content:
    if not dry_run:
      dest_md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Deduped {len(removals)} identical {titles} blocks in {dest_path}")
    return len(removals)
  return 0


def dedupe_vr_blocks(dest_base_dir, dry_run=False):
  """Remove identical-duplicate VR detail blocks under the dest tree."""
  md_files = get_md_files_from_path(dir_path=dest_base_dir)
  n_files = 0
  n_removed = 0
  authors = set(VR_AUTHOR_BY_KANDA.values())
  titles = {VR_MULA_TITLE} | authors | {f"{a} - Intro" for a in authors}
  for md_file in tqdm(sorted(md_files, key=lambda m: str(m.file_path)), desc="Deduping VR blocks"):
    try:
      n = _dedupe_identical_details_single_file(str(md_file.file_path), titles, dry_run=dry_run)
    except Exception as e:
      logging.exception(f"Failed dedup {md_file.file_path}: {e}")
      continue
    if n:
      n_files += 1
      n_removed += n
  logging.info(f"dedupe_vr_blocks {dest_base_dir}: files={n_files} removed={n_removed}")
  return {"files": n_files, "removed": n_removed}


def merge_valmiki_net(dest_base_dir, cache_dir=None, kandas=(1, 2, 3, 4, 5, 6), dry_run=False, sleep_s=0.5):
  """Merge VR commentaries for kandas into the gorakhpur dest tree."""
  import time
  import requests
  session = requests.Session()
  session.headers.update({"User-Agent": "doc_curation/1.0 (research)"})
  totals = {"sargas": 0, "commentaries": 0, "variants": 0, "skipped": 0}
  for kanda in kandas:
    author = VR_AUTHOR_BY_KANDA[kanda]
    kanda_dir = os.path.join(dest_base_dir, VR_DEST_SUBDIR_BY_KANDA[kanda])
    if not os.path.isdir(kanda_dir):
      logging.warning(f"Dest kanda dir missing, skipping: {kanda_dir}")
      continue
    smap = _dest_sarga_map(kanda_dir)
    logging.info(f"Kanda {kanda} ({author}): {len(smap)} dest sargas")
    for sarga in tqdm(sorted(smap), desc=f"VR kanda {kanda}"):
      data = fetch_vr_sarga(kanda, sarga, cache_dir=cache_dir, session=session)
      if data is None:
        totals["skipped"] += 1
        continue
      try:
        (nc, nv) = merge_vr_sarga_into_file(smap[sarga], data, author, dry_run=dry_run)
      except Exception as e:
        logging.exception(f"Failed VR merge {smap[sarga]}: {e}")
        totals["skipped"] += 1
        continue
      totals["sargas"] += 1
      totals["commentaries"] += nc
      totals["variants"] += nv
      if sleep_s:
        time.sleep(sleep_s)
  logging.info(f"merge_valmiki_net: {totals}")
  return totals


# ---------------------------------------------------------------------------
# Grouping-artifact cleanup + scan + prose re-splitting.
# ---------------------------------------------------------------------------

def _evaluate_recorded_blob(d_orig_units, blob_units, neighbor_scope, d_verses):
  """Thin wrapper returning decide_variant() for a recorded blob."""
  if not blob_units:
    return ("skip", [], [])
  return decide_variant(d_orig_units, blob_units, neighbor_scope, d_verses=d_verses)


def cleanup_grouping_artifacts_file(dest_path, dry_run=False):
  """Fix grouping-artifact variants in one file.

  For each recorded variant blob (_________________ sections and VR blocks):
  drop fully-explained (fake) blobs, prune stray units out of mixed blobs
  (recording only differing units), and reroute near-match strays to their
  home verse blocks. Returns dict with counts + review notes.
  """
  dest_md = MdFile(file_path=dest_path)
  (_meta, dest_content) = dest_md.read()
  stats = {"blobs_dropped": 0, "blobs_pruned": 0, "units_moved": 0, "review": []}
  if not dest_content:
    return stats
  details = _assign_translation_verse_sets(_parse_details(dest_content))
  # (start, end, new_block_or_None) replacements; None removes the detail.
  replacements = []
  moves = []  # (kind, home_verses, [units])
  for dm in [d for d in details if _is_main_mula_title(d["title"])]:
    d_verses = set(dm["verse_nums"])
    if not d_verses:
      continue
    d_units = _split_half_units(_mula_original(dm["body"]))
    scope = _file_neighbor_scope(details, d_verses)
    parts = (dm["body"] or "").split(VARIANT_SEPARATOR)
    if len(parts) > 1:
      # Evaluate recorded blobs after the first (original) part, jointly:
      # multiple separators accumulate only via moves; treat as one blob.
      recorded_raw = ("\n".join(p for p in parts[1:])).strip()
      blob_units = _split_half_units(recorded_raw)
      (action, kept, mv) = _evaluate_recorded_blob(d_units, blob_units, scope, d_verses)
      moves.extend([("sep", home, [u]) for (u, home) in mv])
      if action == "skip" and not kept:
        # Fully explained: drop the whole recorded section.
        new_body = parts[0].strip() + "\n"
        replacements.append((dm["start"], dm["end"],
                             f"<details{dm['attrs']}><summary>{dm['title']}</summary>\n\n{new_body}</details>"))
        stats["blobs_dropped"] += 1
      elif action == "record_partial":
        new_body = parts[0].strip() + f"\n{VARIANT_SEPARATOR}\n" + _join_units_text(kept).strip() + "\n"
        replacements.append((dm["start"], dm["end"],
                             f"<details{dm['attrs']}><summary>{dm['title']}</summary>\n\n{new_body}</details>"))
        stats["blobs_pruned"] += 1
      elif mv:
        stats["review"].append(f"{dest_path} sep-blob verses {sorted(d_verses)}: kept with moves?")
  # VR blocks, attributed to nearest preceding main-mula.
  last_dm = None
  for d in details:
    if _is_main_mula_title(d["title"]):
      if set(d["verse_nums"]):
        last_dm = d
      continue
    if d["title"] != VR_MULA_TITLE or last_dm is None:
      continue
    d_verses = set(last_dm["verse_nums"])
    if not d_verses:
      continue
    d_units = _split_half_units(_mula_original(last_dm["body"]))
    scope = _file_neighbor_scope(details, d_verses)
    (action, kept, mv) = _evaluate_recorded_blob(d_units, _split_half_units(d["body"]), scope, d_verses)
    moves.extend([("vr", home, [u]) for (u, home) in mv])
    if action == "skip" and not kept:
      replacements.append((d["start"], d["end"], None))
      stats["blobs_dropped"] += 1
    elif action == "record_partial":
      replacements.append((d["start"], d["end"],
                           f"<details{d['attrs']}><summary>{d['title']}</summary>\n\n" + _join_units_text(kept).strip() + "\n</details>"))
      stats["blobs_pruned"] += 1
  new_content = dest_content
  for (s, e, block) in sorted(replacements, key=lambda x: -x[0]):
    new_content = new_content[:s] + (block if block is not None else "") + new_content[e:]
  new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
  if moves:
    (new_content, n_moved) = _reroute_strays(new_content, moves)
    stats["units_moved"] += n_moved
  if new_content != dest_content:
    if not dry_run:
      dest_md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Grouping cleanup {dest_path}: {stats}")
  return stats


_PROSE_MARKER_PATTERN = regex.compile(r"॥\s*([०-९0-9]+)(?:\s*[-–—]\s*([०-९0-9]+))?\s*॥")


def _prose_marker_verses(body):
  """All (match, verse_set) markers in a translation body, in order."""
  out = []
  for m in _PROSE_MARKER_PATTERN.finditer(body or ""):
    try:
      a = int(_to_ascii_digits(m.group(1)))
      b = int(_to_ascii_digits(m.group(2))) if m.group(2) else a
    except ValueError:
      continue
    if b < a or b - a > 60:
      continue
    out.append((m, set(range(a, b + 1))))
  return out


def split_grouped_translations_file(dest_path, dry_run=False):
  """Split kannaDa translations spanning dest verse blocks (marker-gated).

  Only splits when the body carries explicit ॥n‖/॥n-m‖ markers whose
  segments map cleanly to distinct dest verse blocks. Anything else spanning
  multiple blocks goes to the review list untouched. Returns stats + review.
  """
  stats = {"splits": 0, "review": []}
  dest_md = MdFile(file_path=dest_path)
  (_meta, dest_content) = dest_md.read()
  if not dest_content or KANNADA_TRANS_TITLE not in dest_content:
    return stats
  details = _assign_translation_verse_sets(_parse_details(dest_content))
  mulas = [d for d in details if _is_main_mula_title(d["title"]) and set(d["verse_nums"])]

  def _anchor_of(verses):
    cands = [d for d in mulas if set(d["verse_nums"]) & set(verses)]
    if len(cands) == 1:
      return cands[0]
    return None

  edits = []  # (start, end, [(anchor_end, html)])
  for d in details:
    if d["title"] != KANNADA_TRANS_TITLE or _is_samapti_title(d["title"]):
      continue
    body = d["body"] or ""
    markers = _prose_marker_verses(body)
    if len(markers) < 2:
      continue
    if body[:markers[0][0].start()].strip():
      continue  # leading text before first marker: not splittable
    block_span = set(d["verse_nums"]) | {min(d["verse_nums"], default=0) - 1,
                                         max(d["verse_nums"], default=0) + 1}
    segments = []
    ok = True
    for i, (m, verses) in enumerate(markers):
      if not (set(verses) & block_span):
        ok = False  # marker far outside this block (e.g. colophon): abort
        break
      seg_start = m.end()
      seg_end = markers[i + 1][0].start() if i + 1 < len(markers) else len(body)
      seg_text = body[seg_start:seg_end].strip()
      if not seg_text:
        continue
      anchor = _anchor_of(verses)
      if anchor is None:
        ok = False
        break
      segments.append((anchor, seg_text, verses))
    if not ok or len({id(a) for (a, _t, _v) in segments}) < 2:
      continue
    # All segments map cleanly to 2+ distinct dest blocks: split.
    edits.append((d["start"], d["end"], [(seg_text, verses) for (_a, seg_text, verses) in segments]))
  if edits and not dry_run:
    # Remove originals (descending), then re-parse and place parts at fresh
    # anchors (positions shift after removals).
    new_content = dest_content
    for (s, e, _parts) in sorted(edits, key=lambda x: -x[0]):
      new_content = new_content[:s] + new_content[e:]
    new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
    reparsed = _assign_translation_verse_sets(_parse_details(new_content))
    remulas = [d for d in reparsed if _is_main_mula_title(d["title"]) and set(d["verse_nums"])]

    def _fresh_anchor(verses):
      cands = [d for d in remulas if set(d["verse_nums"]) & set(verses)]
      if len(cands) == 1:
        # Insert after this block's translation run: last translation detail
        # overlapping its verses, else the mula end.
        followers = [d for d in _assign_translation_verse_sets(_parse_details(new_content))
                     if _is_translation_title(d["title"]) and set(d.get("verse_nums", set())) & set(cands[0]["verse_nums"])]
        if followers:
          return max(followers, key=lambda x: x["end"])["end"]
        return cands[0]["end"]
      return None

    ok_all = True
    to_insert = []
    for (_s, _e, parts) in edits:
      for (seg_text, verses) in parts:
        pos = _fresh_anchor(verses)
        if pos is None:
          ok_all = False
          break
        marker_txt = "॥%s॥" % ("-".join(str(v) for v in sorted(verses)) if len(verses) > 1 else str(sorted(verses)[0]))
        to_insert.append((pos, f"\n\n<details><summary>{KANNADA_TRANS_TITLE}</summary>\n\n{seg_text} {marker_txt}\n</details>"))
      if not ok_all:
        break
    if ok_all and to_insert:
      for (pos, html) in sorted(to_insert, key=lambda x: -x[0]):
        new_content = new_content[:pos] + html + new_content[pos:]
      dest_md.replace_content_metadata(new_content=new_content, dry_run=False)
      stats["splits"] += len(edits)
      logging.info(f"Split {len(edits)} grouped translations in {dest_path}")
    else:
      # Anchors dissolved after removal (shouldn't happen): restore + review.
      new_content = dest_content
      for (_s, _e, parts) in edits:
        stats["review"].append(
          f"{dest_path} kannaDa split aborted post-removal; spans {[sorted(v) for (_t, v) in parts]}")
  # Review: translations whose span covers an earliest dest block carrying
  # MORE than 2 halves per verse — the signature of a shifted grouping
  # (stray half glued to the previous verse). Plain grouped translations over
  # standard 2-half blocks, legit ardha-verse extras (2n+1 with the extra
  # matching nothing elsewhere), and gadya prose blocks (long units) are
  # conventional placement, not flagged.
  for d in details:
    if d["title"] != KANNADA_TRANS_TITLE or _is_samapti_title(d["title"]):
      continue
    body = d["body"] or ""
    markers = _prose_marker_verses(body)
    spans = set()
    for (_m, verses) in markers:
      spans |= set(verses)
    if not spans:
      spans = set(d["verse_nums"])
    covered = sorted([a for a in mulas if set(a["verse_nums"]) & spans],
                     key=lambda x: x["start"])
    if len(covered) < 2:
      continue
    first = covered[0]
    first_units = _split_half_units(_mula_original(first["body"]))
    if len(first_units) <= 2 * len(first["verse_nums"]):
      continue
    if any(len(_normalize_mula_for_comparison(u)) >= 100 for u in first_units):
      continue  # gadya prose block, not sloka grouping
    stats["review"].append(
      f"{dest_path} kannaDa translation spans verses {sorted(spans)}; "
      f"earliest block verses {sorted(first['verse_nums'])} has {len(first_units)} half-units")
  stats["review"] = sorted(set(stats["review"]))
  return stats


def split_grouped_translations(dest_dir, dry_run=False):
  """Marker-gated splitting of grouped kannaDa translations + review list."""
  review = []
  n_splits = 0
  for md_file in tqdm(sorted(get_md_files_from_path(dir_path=dest_dir), key=lambda m: str(m.file_path)),
                      desc="Splitting grouped translations"):
    try:
      stats = split_grouped_translations_file(str(md_file.file_path), dry_run=dry_run)
    except Exception as e:
      logging.exception(f"Failed prose split {md_file.file_path}: {e}")
      continue
    n_splits += stats["splits"]
    review.extend(stats["review"])
  logging.info(f"split_grouped_translations {dest_dir}: splits={n_splits} review={len(set(review))}")
  return {"splits": n_splits, "review": sorted(set(review))}


def cleanup_grouping_artifacts(dest_dir, dry_run=False, max_passes=3):
  """Fixpoint cleanup of grouping-artifact variants under dest_dir."""
  totals = {"files": 0, "blobs_dropped": 0, "blobs_pruned": 0, "units_moved": 0}
  review = []
  for _pass in range(max_passes):
    changed = False
    for md_file in tqdm(sorted(get_md_files_from_path(dir_path=dest_dir), key=lambda m: str(m.file_path)),
                        desc=f"Grouping cleanup pass {_pass + 1}"):
      try:
        stats = cleanup_grouping_artifacts_file(str(md_file.file_path), dry_run=dry_run)
      except Exception as e:
        logging.exception(f"Failed grouping cleanup {md_file.file_path}: {e}")
        continue
      if stats["blobs_dropped"] or stats["blobs_pruned"] or stats["units_moved"]:
        changed = True
        totals["files"] += 1
        totals["blobs_dropped"] += stats["blobs_dropped"]
        totals["blobs_pruned"] += stats["blobs_pruned"]
        totals["units_moved"] += stats["units_moved"]
      review.extend(stats["review"])
    if not changed:
      break
  logging.info(f"cleanup_grouping_artifacts {dest_dir}: {totals}")
  return {**totals, "review": review}


def scan_grouping_artifacts(dest_dir):
  """Detection-only report of grouping-artifact variant blobs."""
  report = []
  for md_file in tqdm(sorted(get_md_files_from_path(dir_path=dest_dir), key=lambda m: str(m.file_path)),
                      desc=f"Scanning grouping artifacts"):
    try:
      (meta, content) = MdFile(file_path=str(md_file.file_path)).read()
    except Exception:
      continue
    if not content or (VARIANT_SEPARATOR not in content and VR_MULA_TITLE not in content):
      continue
    details = _assign_translation_verse_sets(_parse_details(content))
    for dm in [d for d in details if _is_main_mula_title(d["title"])]:
      d_verses = set(dm["verse_nums"])
      if not d_verses:
        continue
      d_units = _split_half_units(_mula_original(dm["body"]))
      scope = _file_neighbor_scope(details, d_verses)
      blobs = []
      parts = (dm["body"] or "").split(VARIANT_SEPARATOR)
      if len(parts) > 1:
        blobs.append(("sep", "\n".join(parts[1:])))
      if blobs:
        for (kind, blob_text) in blobs:
          (action, kept, mv) = _evaluate_recorded_blob(d_units, _split_half_units(blob_text), scope, d_verses)
          if action != "record_full":
            report.append({"file": str(md_file.file_path), "verses": sorted(d_verses), "kind": kind,
                           "action": action, "kept": len(kept), "moves": [(u[:30], sorted(h)) for (u, h) in mv]})
    last_dm = None
    for d in details:
      if _is_main_mula_title(d["title"]):
        if set(d["verse_nums"]):
          last_dm = d
        continue
      if d["title"] != VR_MULA_TITLE or last_dm is None:
        continue
      d_verses = set(last_dm["verse_nums"])
      if not d_verses:
        continue
      (action, kept, mv) = _evaluate_recorded_blob(
        _split_half_units(_mula_original(last_dm["body"])), _split_half_units(d["body"]),
        _file_neighbor_scope(details, d_verses), d_verses)
      if action != "record_full":
        report.append({"file": str(md_file.file_path), "verses": sorted(d_verses), "kind": "vr",
                       "action": action, "kept": len(kept), "moves": [(u[:30], sorted(h)) for (u, h) in mv]})
  return report
