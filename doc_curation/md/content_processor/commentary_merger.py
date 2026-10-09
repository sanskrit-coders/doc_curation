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
  """
  text = _to_devanagari(text or "")
  text = _FOOTNOTE_DEF_PATTERN.sub(" ", text)
  text = _FOOTNOTE_REF_PATTERN.sub(" ", text)
  text = _PLUS_ANNOT_PATTERN.sub(" ", text)
  text = text.replace("**", " ")
  # Drop verse-number blocks and daNDas for comparison purposes.
  text = regex.sub(r"॥\s*[०-९0-9೦-೯½\s\-–—,/;]*\s*॥", " ", text)
  text = text.replace("॥", " ").replace("।", " ")
  text = text.replace("ँ", "ं")
  # panchama + halant -> anusvAra (all contexts; comparison only).
  text = regex.sub(r"[ङञणनम]्", "ं", text)
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


def _parse_details(content):
  """Parse top-level details + headings in file order.

  own_nums prefer title + body-daNDa numbers; heading numbers are used only
  as a fallback when title/body yield nothing (e.g. bhAgavata kannaDa mUlas
  whose verse id lives only in the preceding #### heading). This avoids stale
  headings polluting later verses (e.g. rAmAyaNa ## (shloka 35½) headings).
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


def _find_dest_file(alt_path, dest_dir, alt_dir, dest_files_cache=None):
  """Find the dest counterpart for an alt file.

  Strategy: exact relative path → same-dir numeric-prefix match →
  content-overlap search across dest_dir. Returns path or None.
  """
  rel = os.path.relpath(alt_path, alt_dir)
  candidate = os.path.join(dest_dir, rel)
  if os.path.isfile(candidate):
    return candidate
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
    if len(same_num) == 1:
      return same_num[0]
    if len(same_num) > 1:
      # Disambiguate by verse overlap + preference for files lacking Kannada already.
      try:
        (_, alt_content) = MdFile(file_path=alt_path).read()
      except Exception:
        alt_content = ""
      alt_details = _assign_translation_verse_sets(_parse_details(alt_content))
      alt_verse_union = set()
      for d in alt_details:
        if _is_translation_title(d["title"]) or _is_main_mula_title(d["title"]):
          alt_verse_union |= set(d["verse_nums"])
      best = None
      best_score = (-1, 1)
      for cand in same_num:
        try:
          (_, c_content) = MdFile(file_path=cand).read()
        except Exception:
          continue
        c_details = _assign_translation_verse_sets(_parse_details(c_content))
        c_union = set()
        for d in c_details:
          if _is_translation_title(d["title"]) or _is_main_mula_title(d["title"]):
            c_union |= set(d["verse_nums"])
        overlap = len(alt_verse_union & c_union)
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
  # Global content-overlap fallback (needed e.g. MB single-file alt at root).
  try:
    (_, alt_content) = MdFile(file_path=alt_path).read()
  except Exception:
    return None
  alt_details = _assign_translation_verse_sets(_parse_details(alt_content))
  alt_mulas = [d for d in alt_details if _is_main_mula_title(d["title"]) and d["verse_nums"]]
  if not alt_mulas:
    return None
  first_norm = _normalize_mula_for_comparison(alt_mulas[0]["body"])
  if len(first_norm) < 20:
    return None
  probe = first_norm[:60]
  if dest_files_cache is None:
    dest_files_cache = get_md_files_from_path(dir_path=dest_dir)
  best = None
  best_overlap = 0
  alt_union = set()
  for d in alt_details:
    if _is_translation_title(d["title"]) or _is_main_mula_title(d["title"]):
      alt_union |= set(d["verse_nums"])
  for dest_md in dest_files_cache:
    dp = str(dest_md.file_path)
    if os.path.basename(dp) == "_index.md" and os.path.dirname(dp) == dest_dir:
      # Skip top-level index; real content lives deeper (except MB stotra _index).
      # Allow nested _index files (e.g. MB 149 _index.md) - only skip root index.
      continue
    try:
      (_, c_content) = dest_md.read()
    except Exception:
      continue
    if not c_content:
      continue
    c_norm_joined = _normalize_mula_for_comparison(c_content)
    if probe and probe not in c_norm_joined and first_norm not in c_norm_joined:
      continue
    c_details = _assign_translation_verse_sets(_parse_details(c_content))
    c_union = set()
    for d in c_details:
      if _is_translation_title(d["title"]) or _is_main_mula_title(d["title"]):
        c_union |= set(d["verse_nums"])
    overlap = len(alt_union & c_union) if (alt_union and c_union) else 0
    if overlap > best_overlap:
      best_overlap = overlap
      best = dp
    if best is None and (probe in c_norm_joined):
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
    alt_dev = _to_devanagari(alt["body"].strip())
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
    alt_combined_dev = _to_devanagari(alt_combined.strip())
    dest_norm = _normalize_mula_for_comparison(dm["body"])
    alt_norm = _normalize_mula_for_comparison(alt_combined_dev)
    if not dest_norm or not alt_norm:
      continue
    if dest_norm == alt_norm:
      continue
    # Already recorded?
    if alt_norm in dest_norm:
      continue
    variant_map[id(dm)] = alt_combined_dev

  if not insert_map and not variant_map:
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
              alt_dev = _to_devanagari(alt["body"].strip())
              html = f"\n\n<details><summary>{KANNADA_TRANS_TITLE}</summary>\n\n{alt_dev}\n</details>"
              insert_list.append((fresh["end"], html))
    else:
      for orig in dest_hindi:
        if id(orig) in insert_map:
          for alt in insert_map[id(orig)]:
            alt_dev = _to_devanagari(alt["body"].strip())
            html = f"\n\n<details><summary>{KANNADA_TRANS_TITLE}</summary>\n\n{alt_dev}\n</details>"
            insert_list.append((orig["end"], html))
    for pos, html in sorted(insert_list, key=lambda x: x[0], reverse=True):
      new_content = new_content[:pos] + html + new_content[pos:]
  n_trans = len(insert_list)

  if new_content != dest_content:
    if not dry_run:
      dest_md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Merged {dest_path} <- {alt_path}: +{n_trans} kannaDa translations, +{n_variants} variants")
    return (True, n_trans, n_variants)
  return (False, 0, 0)


def merge_translations(dest_dir, alt_dir, dry_run=False):
  """Merge parallel translations: alt_dir -> dest_dir.

  For each md file under alt_dir, finds the corresponding dest file (exact
  relative path, else same-directory numeric-prefix match, else content-overlap
  search), inserts alt translations (transliterated to devanAgarI) below the
  dest Hindi translation as ``अनुवाद (कन्नड)`` details, compares verse mUlas
  ignoring anusvAra/panchama typographic variation and appends significant
  variant readings to the dest mUla detail separated by ``_________________``.

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
