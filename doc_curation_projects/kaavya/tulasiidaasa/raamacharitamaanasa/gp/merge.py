"""Merge Marathi translation sections into Hindi Manas files (goraxapura-pATha).

For each Marathi verse unit, finds the Hindi block with matching mula text
(order-preserving alignment across each kanda) and:
  - inserts its translation as <details><summary>अनुवाद (मराठी)</summary>
    below the Hindi translation (भावार्थ),
  - copies explicit nukta/flap markings into the Hindi mula (transfer),
  - records genuinely differing readings in मूल after _________________.

Marathi source files are KEPT (never deleted).

Usage:
  python merge.py [--dry-run] [--kandas 1,2,3,4,5,6,7]
"""
import argparse
import logging
import os
import regex
import sys

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.INFO,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

from tqdm import tqdm

from doc_curation.md.content_processor import commentary_merger as cm
from doc_curation.md.file import MdFile
from doc_curation.md.library import get_md_files_from_path

BASE = "/home/vvasuki/gitland/vishvAsa/rAmAyaNam/content/kAvyam/bhAShAntaram/avadhI/tulasI-dAsaH/rAma-charita-mAnasa/goraxapura-pATha"
KANDA_PAIRS = [
  ("hindy-anuvAda/01_bAlakANDa", ["marAThy-anuvAda/0", "marAThy-anuvAda/1_bAlakANDa"]),
  ("hindy-anuvAda/02_ayodhyAkANDa", ["marAThy-anuvAda/2_ayodhyAkANDa"]),
  ("hindy-anuvAda/03_araNyakANDa", ["marAThy-anuvAda/3_araNyakANDa"]),
  ("hindy-anuvAda/04_kiShkindhAkANDa", ["marAThy-anuvAda/4_kiShkindhAkANDa"]),
  ("hindy-anuvAda/05_sundarakANDa", ["marAThy-anuvAda/5_sundarakANDa"]),
  ("hindy-anuvAda/06_lankAkANDa", ["marAThy-anuvAda/6_lankAkANDa"]),
  ("hindy-anuvAda/07_uttarakANDa", ["marAThy-anuvAda/7_uttarakANDa"]),
]
MARATHI_TRANS_TITLE = "अनुवाद (मराठी)"
SKIP_BASENAMES = ("_index.md", "01_bAlakANDa_temp.md")

_NUMBER_TOKEN_PATTERN = regex.compile(r"[०-९0-9]+(\([^)]*\))?")
_PAREN_LETTER_PATTERN = regex.compile(r"\(\s*[क-हअ-औa-zA-Z]\s*\)")
_DEV_DIGITS = "०१२३४५६७८९"
_DIGIT_MAP = {ch: str(i) for i, ch in enumerate(_DEV_DIGITS)}


def _to_ascii_digits(s):
  return "".join(_DIGIT_MAP.get(ch, ch) for ch in s)


def manas_norm(text):
  """Mula norm for Manas matching: global norm minus number/marker tokens."""
  norm = cm._normalize_mula_for_comparison(text)
  norm = _NUMBER_TOKEN_PATTERN.sub("", norm)
  norm = _PAREN_LETTER_PATTERN.sub("", norm)
  return norm


def _extract_numbers(text):
  return [int(_to_ascii_digits(m.group())) for m in
          regex.finditer(r"[०-९0-9]+", text or "")]


def _clean_mr_title(title):
  return (title or "").replace("\\", "")


def parse_hindi_file(path):
  """Ordered blocks [{kind, mula, vipras, trans_list, details}] per Hindi file."""
  (meta, content) = MdFile(file_path=path).read()
  details = cm._parse_details(content or "")
  blocks = []
  cur = None

  def _close():
    nonlocal cur
    if cur is not None and (cur["mula"] is not None or cur["trans_list"] or cur["vipras"] is not None):
      blocks.append(cur)
    cur = None

  for d in details:
    t = d["title"]
    if t == "विश्वास-प्रस्तुतिः":
      # A new vipras always starts a new block (a populated cur is complete,
      # even mulaless ones like bare vipras+bhavarth sections).
      if cur is not None and (cur["mula"] is not None or cur["trans_list"] or cur["vipras"] is not None):
        _close()
      cur = {"kind": None, "vipras": None, "mula": None, "trans_list": [],
             "file": path, "details": []}
      cur["vipras"] = d
      cur["kind"] = _kind_from_heading(d.get("heading"))
      cur["details"].append(d)
    elif t == "मूल":
      if cur is not None and cur["mula"] is not None:
        _close()
      if cur is None:
        cur = {"kind": None, "vipras": None, "mula": None, "trans_list": [],
               "file": path, "details": []}
      cur["mula"] = d
      if cur["kind"] is None:
        cur["kind"] = _kind_from_heading(d.get("heading"))
      cur["details"].append(d)
    elif t == "भावार्थ":
      if cur is None:
        cur = {"kind": None, "vipras": None, "mula": None, "trans_list": [],
               "file": path, "details": []}
      cur["trans_list"].append(d)
      cur["details"].append(d)
  _close()
  # Anchor = end of last translation, else mula end, else vipras end.
  for b in blocks:
    if b["trans_list"]:
      b["anchor_end"] = max(d["end"] for d in b["trans_list"])
    elif b["mula"] is not None:
      b["anchor_end"] = b["mula"]["end"]
    elif b["vipras"] is not None:
      b["anchor_end"] = b["vipras"]["end"]
    else:
      b["anchor_end"] = None
    mtext = b["mula"]["body"] if b["mula"] is not None else (b["vipras"]["body"] if b["vipras"] is not None else "")
    b["match_text"] = mtext
    b["norm"] = manas_norm(mtext)
    b["numbers"] = _extract_numbers((b["mula"]["body"] if b["mula"] is not None else "") or "")
  return [b for b in blocks if b["anchor_end"] is not None]


def _is_verse_line(ln):
  """A bare line looking like a Manas verse half (short, danda-ended, no prose marks)."""
  s = (ln or "").strip()
  if not s or len(s) > 120:
    return False
  if not (s.endswith("।") or s.endswith("॥")):
    return False
  if regex.search(r"[?!\"“”'()\[\]]", s):
    return False
  if not regex.search(r"[\u0915-\u0939\u0905-\u0914]", s):
    return False
  return True


def _run_has_number(lines):
  return any(regex.search(r"॥\s*[०-९0-9]+\s*॥", l) for l in lines)


def _gap_verse_runs(gap_text):
  """Split gap text into numbered verse pieces.

  Verse-like lines accumulate (blank lines don't break); each line carrying
  a ॥N‖ number closes the current piece. Only pieces with numbers return
  (unnumbered fragments stay put + review downstream if needed).
  """
  pieces = []
  cur = []
  for ln in (gap_text or "").split("\n"):
    s = ln.strip()
    if not s:
      continue  # blank formatting lines neither break nor join
    if not _is_verse_line(s):
      cur = []  # prose/div remnants break the run (stay put); partial run dropped
      continue
    cur.append(s)
    if regex.search(r"॥\s*[०-९0-9]+\s*॥", s):
      pieces.append(cur)
      cur = []
  # Trailing unnumbered tail left in place (not returned).
  return pieces


def _relocate_misplaced_marathi(content):
  """Move marathi translations whose markers miss the enclosing block.

  Returns (new_content, n_moved). A translation whose ॥n‖ markers don't
  intersect its enclosing mula block but hit another mula block in the file
  is cut and re-inserted after that home block's translation run. Markerless
  translations and ones with no better home stay put (zero loss risk).
  """
  details = cm._parse_details(content or "")
  mulas = [d for d in details if d["title"] == "मूल"]
  if not mulas:
    return (content, 0)
  # Collect misplaced details (cut later one by one with fresh parses).
  todo = []
  for d in details:
    if d["title"] != MARATHI_TRANS_TITLE or cm._is_samapti_title(d["title"]):
      continue
    spans = set()
    for (_m, verses) in cm._prose_marker_verses(d["body"] or ""):
      spans |= set(verses)
    if not spans:
      continue
    enclosing = None
    for m in mulas:
      if m["end"] <= d["start"]:
        enclosing = m
      else:
        break
    if enclosing is not None and (spans & set(_extract_numbers(enclosing["body"] or ""))):
      continue  # correctly placed
    homes = [m for m in mulas
             if m is not enclosing and (spans & set(_extract_numbers(m["body"] or "")))]
    if homes:
      todo.append(spans)
  # One by one: cut the (first) detail with these markers, re-parse, insert
  # after the home block's translation run. Offsets always fresh: no staleness.
  new_content = content
  n_moved = 0
  for spans in todo:
    details = cm._parse_details(new_content)
    mulas = [d for d in details if d["title"] == "मूल"]
    target = None
    for d in details:
      if d["title"] != MARATHI_TRANS_TITLE:
        continue
      dspans = set()
      for (_m, verses) in cm._prose_marker_verses(d["body"] or ""):
        dspans |= set(verses)
      if dspans == spans:
        # Must ALSO be currently misplaced (enclosing misses).
        enc = None
        for m in mulas:
          if m["end"] <= d["start"]:
            enc = m
          else:
            break
        if enc is not None and (spans & set(_extract_numbers(enc["body"] or ""))):
          continue  # already home
        target = d
        break
    if target is None:
      continue
    home = None
    for m in mulas:
      if spans & set(_extract_numbers(m["body"] or "")):
        home = m
        break
    if home is None:
      continue
    html = new_content[target["start"]:target["end"]]
    new_content = new_content[:target["start"]] + new_content[target["end"]:]
    # Fresh parse for the insert position (cut shifted offsets).
    details = cm._parse_details(new_content)
    home2 = None
    for m in details:
      if m["title"] == "मूल" and (spans & set(_extract_numbers(m["body"] or ""))):
        home2 = m
        break
    if home2 is None:
      # Restore (shouldn't happen): append at end.
      new_content = new_content + "\n\n" + html.strip() + "\n"
      continue
    home_nums = set(_extract_numbers(home2["body"] or ""))
    pos = home2["end"]
    for x in details:
      if x["start"] <= home2["end"]:
        continue
      if x["title"] == "भावार्थ":
        bnums = set(_extract_numbers(x["body"] or ""))
        if bnums and home_nums and not (bnums & home_nums):
          break
        pos = x["end"]
        continue
      if x["title"] == MARATHI_TRANS_TITLE:
        pos = x["end"]
        continue
      break
    new_content = new_content[:pos] + "\n\n" + html.strip() + "\n" + new_content[pos:]
    new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
    n_moved += 1
  return (new_content, n_moved)


def repair_manas_file(path, dry_run=False):
  """Fix Manas Hindi structural gaps in one file.

  - Bare numbered verse runs duplicating adjacent mula/vipras text: deleted.
  - Bare numbered verse runs missing from details: wrapped into
    <details open>विश्वास-प्रस्तुतिः</details> + <details>मूल</details>.
  - मूल without immediately-preceding विश्वास-प्रस्तुतिः sibling: vipras
    duplicate inserted (uniform triplet convention).
  Returns stats dict.
  """
  from doc_curation.md.content_processor import commentary_merger as cm
  stats = {"bare_deleted": 0, "bare_wrapped": 0, "vipras_added": 0, "mula_added": 0, "review": []}
  md = MdFile(file_path=path)
  (meta, content) = md.read()
  if not content:
    return stats
  new_content = content
  # ---- Pass 1: bare verse runs (descending offsets).
  details = cm._parse_details(new_content)
  spans = [(d["start"], d["end"]) for d in details]
  # Section bounds from ## headers (repairs never cross sections).
  section_breaks = [0] + [m.start() for m in regex.finditer(r"(?m)^#{1,6}\s+.*$", new_content)] + [len(new_content)]

  def _section_of(pos):
    for i in range(len(section_breaks) - 1):
      if section_breaks[i] <= pos < section_breaks[i + 1]:
        return i
    return len(section_breaks) - 2

  edits = []  # (start, end, replacement_or_None)
  prev = 0
  detail_list = list(details)
  for idx, d in enumerate(detail_list + [None]):
    start = d["start"] if d is not None else len(new_content)
    gap = new_content[prev:start]
    # Strip frontmatter (first gap), headers, divs.
    if prev == 0:
      gap = regex.sub(r"\A\s*\+{3}.*?\+{3}\s*", "", gap, flags=regex.S)
    gap = regex.sub(r"(?m)^#{1,6}\s+.*$", "", gap)
    gap = regex.sub(r"<div[^>]*>.*?</div>|<div[^>]*>", "", gap, flags=regex.S)
    for run in _gap_verse_runs(gap):
      run_text = "\n".join(run)
      run_norm = manas_norm(run_text)
      if not run_norm:
        continue
      # Neighbor mulas/vipras in the same section.
      sec = _section_of(start)
      neighbors = []
      if idx < len(detail_list) and detail_list[idx]["title"] in ("मूल", "विश्वास-प्रस्तुतिः"):
        # Only the immediately following detail (adjacent duplicate check).
        nd = detail_list[idx]
        if _section_of(nd["start"]) == sec:
          neighbors.append(nd)
      if idx > 0:
        pd = detail_list[idx - 1]
        if pd["title"] in ("मूल", "विश्वास-प्रस्तुतिः") and _section_of(pd["start"]) == sec:
          neighbors.append(pd)
      redundant = False
      for nd in neighbors:
        nnorm = manas_norm(nd["body"] or "")
        if nnorm and (run_norm in nnorm or nnorm in run_norm):
          redundant = True
          break
      # Locate run offsets within the original content for replacement.
      end_at = prev
      ok = True
      for ln in run:
        k = new_content.find(ln, end_at, start)
        if k < 0:
          ok = False
          break
        if end_at == prev:
          at = k
        end_at = k + len(ln)
      # Swallow trailing spaces/tabs on the last line (not newlines).
      if ok:
        m = regex.match(r"[ \t]*", new_content[end_at:start])
        end_at += m.end()
      if not ok:
        stats["review"].append(f"{path}: could not locate bare run: {run[0][:40]}")
        continue
      if redundant:
        edits.append((at, end_at, ""))
        stats["bare_deleted"] += 1
        continue
      else:
        # File-wide duplicate check: same verse text in a non-adjacent mula
        # means the print repeats it (refrain) — wrapping preserves order.
        for od in detail_list:
          if od["title"] not in ("मूल", "विश्वास-प्रस्तुतिः"):
            continue
          onorm = manas_norm(od["body"] or "")
          if onorm and (run_norm in onorm or onorm in run_norm) and od is not None:
            # Adjacent duplicates already handled above; this is distant —
            # still wrap (print order), but note it.
            stats["review"].append(f"{path}: bare verse repeats distant mula "
                                   f"({od['title']}): {run[0][:40]}")
            break
        html = (f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{run_text.strip()}\n</details>\n\n"
                f"<details><summary>मूल</summary>\n\n{run_text.strip()}\n</details>")
        edits.append((at, end_at, html))
        stats["bare_wrapped"] += 1
    prev = d["end"] if d is not None else len(new_content)
  for (s, e, block) in sorted(edits, key=lambda x: -x[0]):
    new_content = new_content[:s] + block + new_content[e:]
  new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
  # ---- Pass 1.5: relocate misplaced Marathi translations (markers miss
  # enclosing block). Runs before vipras insertion so anchors are clean.
  (new_content, n_relocated) = _relocate_misplaced_marathi(new_content)
  stats["relocated"] = n_relocated
  # ---- Pass 2: vipras before every मूल lacking one as previous sibling.
  details = cm._parse_details(new_content)
  inserts = []
  prev_title = None
  for d in details:
    if d["title"] == "मूल":
      if prev_title != "विश्वास-प्रस्तुतिः":
        body = (d["body"] or "").strip()
        if body:
          inserts.append((d["start"],
                          f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{body}\n</details>\n\n"))
          stats["vipras_added"] += 1
        else:
          stats["review"].append(f"{path}: empty मूल, vipras skipped")
      prev_title = "मूल"
    elif d["title"] == "विश्वास-प्रस्तुतिः":
      prev_title = "विश्वास-प्रस्तुतिः"
    else:
      prev_title = d["title"]
  for (pos, html) in sorted(inserts, key=lambda x: -x[0]):
    new_content = new_content[:pos] + html + new_content[pos:]
  new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
  # ---- Pass 2b: मूल after every lone विश्वास-प्रस्तुतिः (verse present only
  # as vipras + bhavarth, e.g. bare dohas). Duplicate vipras body verbatim.
  details = cm._parse_details(new_content)
  inserts = []
  for idx, d in enumerate(details):
    if d["title"] != "विश्वास-प्रस्तुतिः":
      continue
    nxt = details[idx + 1] if idx + 1 < len(details) else None
    if nxt is not None and nxt["title"] == "मूल":
      continue
    body = (d["body"] or "").strip()
    if not body:
      stats["review"].append(f"{path}: empty विश्वास-प्रस्तुतिः, mula skipped")
      continue
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    if not any(ln.endswith(("।", "॥")) for ln in lines):
      stats["review"].append(f"{path}: non-verse vipras, mula skipped: {body[:40]}")
      continue
    inserts.append((d["end"],
                    f"\n\n<details><summary>मूल</summary>\n\n{body}\n</details>"))
    stats["mula_added"] += 1
  for (pos, html) in sorted(inserts, key=lambda x: -x[0]):
    new_content = new_content[:pos] + html + new_content[pos:]
  new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
  if new_content != content and not dry_run:
    md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Repaired {path}: {stats['bare_deleted']} bare-deleted, "
                 f"{stats['bare_wrapped']} bare-wrapped, {stats.get('relocated', 0)} relocated, "
                 f"{stats['vipras_added']} vipras-added")
  return stats


def repair_manas_corpus(hindi_dir, dry_run=False):
  """Run repair_manas_file over one Hindi kanda dir. Returns totals + review."""
  totals = {"files": 0, "bare_deleted": 0, "bare_wrapped": 0, "relocated": 0, "vipras_added": 0, "mula_added": 0}
  review = []
  for md in tqdm(sorted(get_md_files_from_path(dir_path=hindi_dir), key=lambda m: str(m.file_path)),
                 desc=f"Repairing {hindi_dir}"):
    p = str(md.file_path)
    if os.path.basename(p) in SKIP_BASENAMES:
      continue
    try:
      stats = repair_manas_file(p, dry_run=dry_run)
    except Exception as e:
      logging.exception(f"Failed repair {p}: {e}")
      continue
    if stats["bare_deleted"] or stats["bare_wrapped"] or stats.get("relocated", 0) or stats["vipras_added"] or stats["mula_added"]:
      totals["files"] += 1
      totals["bare_deleted"] += stats["bare_deleted"]
      totals["bare_wrapped"] += stats["bare_wrapped"]
      totals["relocated"] += stats.get("relocated", 0)
      totals["vipras_added"] += stats["vipras_added"]
      totals["mula_added"] += stats["mula_added"]
    review.extend(stats["review"])
  logging.info(f"repair_manas_corpus: {totals}")
  return totals, sorted(set(review))


_KHARI_PROSE_PATTERN = None


def _khari_prose_pattern():
  global _KHARI_PROSE_PATTERN
  if _KHARI_PROSE_PATTERN is None:
    d = "[\u0900-\u097F]"
    _KHARI_PROSE_PATTERN = regex.compile(
      r"(?<!" + d + r")(है|हैं|था|थे|थी|गया|गये|गई|किया|किए|किये|होगा|होगी|होगे|रहा|रहे|रही|सकता|सकते|सकती|चाहिए|अपने|उसने|फिर|तथा|क्योंकि|अर्थात्)(?!" + d + r")|,")
  return _KHARI_PROSE_PATTERN


def _verse_numbers_in(text):
  return set(_extract_numbers(text or ""))


def _prev_numbered_block(details, k):
  """Nearest preceding numbered vipras/मूल detail outside detail k's own block.

  Skips k's pair mate (मूल immediately preceded by its vipras belongs with
  it), so a block is never its own 'previous block'.
  """
  j = k - 1
  if j >= 0 and details[k]["title"] == "मूल" and details[j]["title"] == "विश्वास-प्रस्तुतिः":
    j -= 1
  while j >= 0:
    d = details[j]
    if d["title"] in ("मूल", "विश्वास-प्रस्तुतिः") and _verse_numbers_in(d["body"]):
      return d
    j -= 1
  return None


def fix_leaked_prose_file(path, dry_run=False):
  """Move Hindi prose leaked into vipras/मूल verse blocks back to भावार्थ.

  Detects lines carrying a ॥M‖ number that is (a) smaller than the block's
  own max number, (b) present in the nearest preceding numbered verse block,
  and (c) Khari-Boli prose (comma or prose markers with Devanagari word
  boundaries). Such a line is the previous verse-half's translation that
  spilled into the next verse's details: cut it from vipras+मूल and append
  it to the previous block's भावार्थ (created if missing). Returns stats.
  """
  stats = {"lines_moved": 0, "lines_deleted_only": 0, "bhavarth_created": 0, "review": []}
  md = MdFile(file_path=path)
  (meta, content) = md.read()
  if not content:
    return stats
  new_content = content
  # Fixpoint: handle one stray line per fresh parse (max 20 iterations).
  for _round in range(20):
    details = cm._parse_details(new_content)
    found = None  # (line_text, mm, holders, home, target_or_None)
    for k, d in enumerate(details):
      if d["title"] not in ("मूल", "विश्वास-प्रस्तुतिः"):
        continue
      own = set()
      for ln in (d["body"] or "").split("\n"):
        for m in regex.finditer(r"॥\s*([०-९0-9]+)\s*॥", ln):
          own.add(int(m.group(1).translate(str.maketrans("०१२३४५६७८९", "0123456789"))))
      if not own:
        continue
      prev = _prev_numbered_block(details, k)
      if prev is None:
        continue
      prevnums = _verse_numbers_in(prev["body"])
      for ln in (d["body"] or "").split("\n"):
        s = ln.strip()
        if not s:
          continue
        for m in regex.finditer(r"॥\s*([०-९0-9]+)\s*॥", s):
          mm = int(m.group(1).translate(str.maketrans("०१२३४५६७८९", "0123456789")))
          if mm < max(own) and mm in prevnums and _khari_prose_pattern().search(s):
            found = (s, mm)
            break
        if found is not None:
          break
      if found is not None:
        break
    if found is None:
      break
    (s, mm) = found
    # Holders: every vipras/मूल detail currently containing this exact line.
    details = cm._parse_details(new_content)
    holders = [d for d in details if d["title"] in ("मूल", "विश्वास-प्रस्तुतिः")
               and any(ln.strip() == s for ln in (d["body"] or "").split("\n"))]
    if not holders:
      stats["review"].append(f"{path}: stray vanished: {s[:50]}")
      break
    first_holder = min(holders, key=lambda d: d["start"])
    home = _prev_numbered_block(details, details.index(first_holder))
    if home is None or mm not in _verse_numbers_in(home["body"]):
      stats["review"].append(f"{path}: no home block with ॥{mm}‖ for: {s[:50]}")
      break
    home_mula = home
    if home["title"] == "विश्वास-प्रस्तुतिः":
      nxt = details[details.index(home) + 1] if details.index(home) + 1 < len(details) else None
      if nxt is not None and nxt["title"] == "मूल":
        home_mula = nxt
    target = None
    for d in details:
      if home_mula["end"] <= d["start"] < first_holder["start"] and d["title"] == "भावार्थ":
        target = d
        break
    # Delete the line from every holder (descending: earlier offsets stay valid).
    for h in sorted(holders, key=lambda d: -d["start"]):
      lines = (h["body"] or "").split("\n")
      kept = [ln for ln in lines if ln.strip() != s]
      if len(kept) == len(lines):
        continue
      old_block = new_content[h["start"]:h["end"]]
      new_body = "\n".join(kept)
      new_block = regex.sub(r"(<summary>[^<]*</summary>\s*)\n[\s\S]*?(</details>)",
                            lambda m: m.group(1) + "\n" + new_body.strip() + "\n" + m.group(2),
                            old_block, count=1, flags=regex.S)
      if f"<summary>{h['title']}</summary>" not in old_block:
        stats["review"].append(f"{path}: offset drift, skipped holder edit")
        continue
      new_content = new_content[:h["start"]] + new_block + new_content[h["end"]:]
    # Append to target (offsets still valid: every holder deletion happened
    # strictly after target/anchor positions), else create after home mula.
    details = cm._parse_details(new_content)
    holders_now = [d for d in details if d["title"] in ("मूल", "विश्वास-प्रस्तुतिः")
                   and any(ln.strip() == s for ln in (d["body"] or "").split("\n"))]
    assert not holders_now, f"holders remain: {path}"
    if target is not None:
      if manas_norm(s) not in manas_norm(target["body"] or ""):
        tb = (target["body"] or "").rstrip() + "\n" + s.strip() + "\n"
        old_block = new_content[target["start"]:target["end"]]
        new_block = regex.sub(r"(<summary>[^<]*</summary>\s*)\n[\s\S]*?(</details>)",
                              lambda m: m.group(1) + "\n" + tb.strip() + "\n" + m.group(2),
                              old_block, count=1, flags=regex.S)
        new_content = new_content[:target["start"]] + new_block + new_content[target["end"]:]
        stats["lines_moved"] += 1
      else:
        stats["lines_deleted_only"] += 1
    else:
      html = f"\n\n<details><summary>भावार्थ</summary>\n\n{s.strip()}\n</details>"
      new_content = new_content[:home_mula["end"]] + html + new_content[home_mula["end"]:]
      stats["bhavarth_created"] += 1
      stats["lines_moved"] += 1
  new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
  if new_content != content and not dry_run:
    md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Repaired {path}: {stats['bare_deleted']} bare-deleted, "
                 f"{stats['bare_wrapped']} bare-wrapped, {stats.get('relocated', 0)} relocated, "
                 f"{stats['vipras_added']} vipras-added")
  return stats


def repair_manas_corpus(hindi_dir, dry_run=False):
  """Run repair_manas_file over one Hindi kanda dir. Returns totals + review."""
  totals = {"files": 0, "bare_deleted": 0, "bare_wrapped": 0, "relocated": 0, "vipras_added": 0, "mula_added": 0}
  review = []
  for md in tqdm(sorted(get_md_files_from_path(dir_path=hindi_dir), key=lambda m: str(m.file_path)),
                 desc=f"Repairing {hindi_dir}"):
    p = str(md.file_path)
    if os.path.basename(p) in SKIP_BASENAMES:
      continue
    try:
      stats = repair_manas_file(p, dry_run=dry_run)
    except Exception as e:
      logging.exception(f"Failed repair {p}: {e}")
      continue
    if stats["bare_deleted"] or stats["bare_wrapped"] or stats.get("relocated", 0) or stats["vipras_added"] or stats["mula_added"]:
      totals["files"] += 1
      totals["bare_deleted"] += stats["bare_deleted"]
      totals["bare_wrapped"] += stats["bare_wrapped"]
      totals["relocated"] += stats.get("relocated", 0)
      totals["vipras_added"] += stats["vipras_added"]
      totals["mula_added"] += stats["mula_added"]
    review.extend(stats["review"])
  logging.info(f"repair_manas_corpus: {totals}")
  return totals, sorted(set(review))


def fix_leaked_prose_corpus(hindi_dir, dry_run=False):
  """Run fix_leaked_prose_file over one Hindi kanda dir."""
  totals = {"files": 0, "lines_moved": 0, "lines_deleted_only": 0, "bhavarth_created": 0}
  review = []
  for md in tqdm(sorted(get_md_files_from_path(dir_path=hindi_dir), key=lambda m: str(m.file_path)),
                 desc=f"Fixing leaks in {hindi_dir}"):
    p = str(md.file_path)
    if os.path.basename(p) in SKIP_BASENAMES:
      continue
    try:
      stats = fix_leaked_prose_file(p, dry_run=dry_run)
    except Exception as e:
      logging.exception(f"Failed leak fix {p}: {e}")
      continue
    if stats["lines_moved"] or stats["lines_deleted_only"] or stats["bhavarth_created"]:
      totals["files"] += 1
      totals["lines_moved"] += stats["lines_moved"]
      totals["lines_deleted_only"] += stats["lines_deleted_only"]
      totals["bhavarth_created"] += stats["bhavarth_created"]
    review.extend(stats["review"])
  logging.info(f"fix_leaked_prose_corpus: {totals}")
  return totals, sorted(set(review))


def dedup_bhavarth_lines_file(path, dry_run=False):
  """Drop exact-duplicate prose lines repeated across भावार्थ blocks.

  A line carrying ॥M‖ is kept only in भावार्थ details enclosed by a verse
  block containing M; other copies are deleted. Lines with no keeper, or
  multiple keepers, are left untouched + review-listed. Returns stats.
  """
  stats = {"removed": 0, "review": []}
  md = MdFile(file_path=path)
  (meta, content) = md.read()
  if not content:
    return stats
  from collections import defaultdict
  new_content = content
  # Fixpoint: one duplicated line per fresh parse (offsets shift on edit).
  for _round in range(20):
    details = cm._parse_details(new_content)
    bhavarths = [d for d in details if d["title"] == "भावार्थ"]
    # line -> bhavarths containing it (exact stripped match, with ॥N‖).
    holders = defaultdict(list)
    for d in bhavarths:
      for ln in (d["body"] or "").split("\n"):
        s = ln.strip()
        if s and regex.search(r"॥\s*[०-९0-9]+\s*॥", s):
          holders[s].append(d)
    target = None
    for s, ds_ in holders.items():
      if len(ds_) < 2:
        continue
      keepers = []
      for d in ds_:
        enc = None
        for m in details:
          if m["title"] in ("मूल", "विश्वास-प्रस्तुतिः") and m["end"] <= d["start"]:
            enc = m
          elif m["start"] > d["start"]:
            break
        if enc is not None and (set(_extract_numbers(s)) & set(_verse_numbers_in(enc["body"] or ""))):
          keepers.append(d)
      if len(keepers) == 1:
        target = (s, keepers[0], [d for d in ds_ if d is not keepers[0]])
        break
      stats["review"].append(
        f"{path}: ambiguous duplicate kept as-is: {s[:50]} in {len(ds_)} bhavarths")
    if target is None:
      break
    (s, keeper, drops) = target
    for d in sorted(drops, key=lambda x: -x["start"]):
      lines = (d["body"] or "").split("\n")
      kept = [ln for ln in lines if ln.strip() != s]
      if len(kept) == len(lines):
        continue
      old_block = new_content[d["start"]:d["end"]]
      new_body = "\n".join(kept)
      new_block = regex.sub(r"(<summary>[^<]*</summary>\s*)\n[\s\S]*?(</details>)",
                            lambda m: m.group(1) + "\n" + new_body.strip() + "\n" + m.group(2),
                            old_block, count=1, flags=regex.S)
      if f"<summary>{d['title']}</summary>" not in old_block:
        stats["review"].append(f"{path}: offset drift, skipped holder edit")
        continue
      new_content = new_content[:d["start"]] + new_block + new_content[d["end"]:]
      stats["removed"] += 1
  new_content = regex.sub(r"\n{3,}", "\n\n", new_content)
  if new_content != content and not dry_run:
    md.replace_content_metadata(new_content=new_content, dry_run=False)
    logging.info(f"Deduped bhavarth lines in {path}: removed={stats['removed']}")
  return stats


def dedup_bhavarth_lines(hindi_dir, dry_run=False):
  """Run dedup_bhavarth_lines_file over one Hindi kanda dir."""
  totals = {"files": 0, "removed": 0}
  review = []
  for md in tqdm(sorted(get_md_files_from_path(dir_path=hindi_dir), key=lambda m: str(m.file_path)),
                 desc=f"Deduping bhavarth in {hindi_dir}"):
    p = str(md.file_path)
    if os.path.basename(p) in SKIP_BASENAMES:
      continue
    try:
      stats = dedup_bhavarth_lines_file(p, dry_run=dry_run)
    except Exception as e:
      logging.exception(f"Failed bhavarth dedup {p}: {e}")
      continue
    if stats["removed"]:
      totals["files"] += 1
      totals["removed"] += stats["removed"]
    review.extend(stats["review"])
  logging.info(f"dedup_bhavarth_lines: {totals}")
  return totals, sorted(set(review))


def _kind_from_heading(heading):
  if not heading:
    return None
  for kind in ("दोहा", "चौपाई", "छन्द", "छंद", "सोरठा", "श्लोक", "हरिगीतिका"):
    if kind in heading:
      return kind
  return None


def parse_marathi_file(path):
  """Ordered units [{kind, mula, trans}] — strict (mula, translation) pairs."""
  (meta, content) = MdFile(file_path=path).read()
  details = cm._parse_details(content or "")
  units = []
  i = 0
  while i < len(details):
    d = details[i]
    t = _clean_mr_title(d["title"])
    if t.startswith("मूल ("):
      kind = t[len("मूल ("):].rstrip(")")
      trans = None
      if i + 1 < len(details) and "मराठी" in _clean_mr_title(details[i + 1]["title"]):
        trans = details[i + 1]
        i += 2
      else:
        i += 1
      mula_text = d["body"] or ""
      units.append({"kind": kind, "mula": d, "trans": trans,
                    "file": path, "norm": manas_norm(mula_text),
                    "numbers": _extract_numbers(mula_text)})
    else:
      i += 1
  return units


def collect_hindi_blocks(kanda_dir):
  blocks = []
  for md in sorted(get_md_files_from_path(dir_path=kanda_dir), key=lambda m: str(m.file_path)):
    p = str(md.file_path)
    if os.path.basename(p) in SKIP_BASENAMES:
      continue
    blocks.extend(parse_hindi_file(p))
  return blocks


def collect_marathi_units(kanda_dirs):
  if isinstance(kanda_dirs, str):
    kanda_dirs = [kanda_dirs]
  units = []
  for kanda_dir in kanda_dirs:
    for md in sorted(get_md_files_from_path(dir_path=kanda_dir), key=lambda m: str(m.file_path)):
      p = str(md.file_path)
      if os.path.basename(p) in SKIP_BASENAMES:
        continue
      units.extend(parse_marathi_file(p))
  return units


def merge_kanda(hindi_dir, marathi_dir, dry_run=False):
  """Align + merge one kanda. Returns stats dict + review list."""
  stats = {"pairs": 0, "translations": 0, "variants": 0, "nukta_transfers": 0,
           "unmatched_marathi": 0, "unmatched_hindi": 0}
  review = []
  if isinstance(marathi_dir, str):
    marathi_dir = [marathi_dir]
  plan = plan_kanda(hindi_dir, marathi_dir)
  hindi_blocks = plan["hindi_blocks"]
  marathi_units = plan["marathi_units"]
  grouped = plan["grouped"]
  unmatched = plan["unmatched"]
  logging.info(f"Hindi blocks: {len(hindi_blocks)}, Marathi units: {len(marathi_units)}, "
               f"groups: {len(grouped)}, unmatched marathi: {len(unmatched)}, "
               f"nonmonotonic: {len(plan['align_notes'])}")
  stats["unmatched_marathi"] = len(unmatched)
  for (mj, hi, kind) in plan["align_notes"]:
    u = marathi_units[mj]
    review.append(f"{kind} pairing: marathi {u['file'].split('/')[-1]} kind={u['kind']} -> hindi {hindi_blocks[hi]['file'].split('/')[-1]}")
  still_unmatched_hindi = plan["unmatched_hindi"]
  stats["unmatched_hindi"] = len(still_unmatched_hindi)
  for hi in still_unmatched_hindi:
    hb = hindi_blocks[hi]
    review.append(f"UNMATCHED hindi {hb['file'].split('/')[-1]} kind={hb['kind']}: {(hb['match_text'] or '')[:60].replace(chr(10), ' ')}")
  # Per-group actions, keyed by Hindi block identity (post-transfer norm).
  # actions_by_file[path] = list of dicts in file order. Anchor block (for
  # translations + variant record) = LAST Hindi block of the span.
  actions_by_file = {}
  for g in grouped:
    his = sorted(g["his"])
    mjs = sorted(g["mjs"])
    hb = hindi_blocks[his[-1]]
    combined_mr = "\n".join(marathi_units[mj]["mula"]["body"].strip()
                            for mj in mjs if (marathi_units[mj]["mula"]["body"] or "").strip())
    if not combined_mr:
      continue
    combined_hi = "\n".join((hindi_blocks[i]["mula"]["body"] if hindi_blocks[i]["mula"] is not None else hindi_blocks[i]["match_text"] or "") for i in his)
    base_text = (hb["mula"]["body"] if hb["mula"] is not None else hb["match_text"]) or ""
    actions = []
    # 1) Nukta transfer into each covered Hindi mula (+vipras if identical).
    #    Operates span-vs-span so grouped blocks transfer correctly.
    new_span = cm.transfer_nukta_marks(combined_hi, combined_mr)
    span_idents = {}
    if new_span is not None:
      # Split transferred span back across Hindi blocks by unit alignment?
      # Conservative: apply transfer per Hindi block against combined Marathi.
      for i in his:
        btext = (hindi_blocks[i]["mula"]["body"] if hindi_blocks[i]["mula"] is not None else hindi_blocks[i]["match_text"]) or ""
        nb = cm.transfer_nukta_marks(btext, combined_mr)
        if nb is not None:
          ident = cm._normalize_mula_for_comparison(nb)
          span_idents[i] = ident
          actions.append({"kind": "transfer", "ident": ident, "new_body": nb,
                          "hi": i, "sync_vipras": True})
    # Anchor identity (post-transfer norm of anchor block).
    anchor_base = (hindi_blocks[his[-1]]["mula"]["body"] if hindi_blocks[his[-1]]["mula"] is not None else hindi_blocks[his[-1]]["match_text"]) or ""
    anchor_ident = span_idents.get(his[-1], cm._normalize_mula_for_comparison(anchor_base))
    # 2) Variant compare (span-level, post-transfer).
    hindi_span = new_span if new_span is not None else combined_hi
    if cm._normalize_mula_for_comparison(hindi_span) != cm._normalize_mula_for_comparison(combined_mr):
      actions.append({"kind": "variant", "ident": anchor_ident, "reading": combined_mr})
    # 3) Translation inserts (one per marathi unit, in order).
    for mj in mjs:
      u = marathi_units[mj]
      if u["trans"] is None:
        review.append(f"{u['file']} unit {u['kind']}/{u['numbers']}: no marathi translation")
        continue
      tbody = (u["trans"]["body"] or "").strip()
      if not tbody:
        continue
      actions.append({"kind": "trans", "ident": anchor_ident, "tbody": tbody,
                      "mj": mj})
    if actions:
      actions_by_file.setdefault(hb["file"], []).extend(actions)
    stats["pairs"] += 1
  for mj in unmatched:
    u = marathi_units[mj]
    review.append(f"UNMATCHED marathi {u['file'].split('/')[-1]} kind={u['kind']} nums={u['numbers']}: {(u['mula']['body'] or '')[:60].replace(chr(10), ' ')}")
  for path, actions in tqdm(sorted(actions_by_file.items()), desc="Writing merged files"):
    _apply_file_edits(path, actions, dry_run=dry_run, stats=stats)
  return stats, sorted(set(review))


def plan_kanda(hindi_dir, marathi_dirs):
  """Shared alignment plan: ordered blocks/units, groups, unmatched lists."""
  if isinstance(marathi_dirs, str):
    marathi_dirs = [marathi_dirs]
  hindi_blocks = collect_hindi_blocks(hindi_dir)
  marathi_units = collect_marathi_units(marathi_dirs)
  hnorms = [b["norm"] for b in hindi_blocks]
  mnorms = [u["norm"] for u in marathi_units]
  groups, unmatched, align_notes = cm.align_parallel_units(hnorms, mnorms)
  grouped = [{"his": [hi], "mjs": list(mjs)} for (hi, mjs) in groups]
  marathi_to_group = {}
  for g in grouped:
    for mj in g["mjs"]:
      marathi_to_group[mj] = g
  used_hindi = {hi for g in grouped for hi in g["his"]}
  for hi in sorted(set(range(len(hindi_blocks))) - used_hindi):
    h = hnorms[hi]
    if not h or len(h) < 20:
      continue
    for mj in sorted(marathi_to_group):
      if h in mnorms[mj]:
        marathi_to_group[mj]["his"].append(hi)
        used_hindi.add(hi)
        break
  grouped = [g for g in grouped if g["his"]]
  grouped.sort(key=lambda g: max(g["his"]))
  still_unmatched_hindi = sorted(set(range(len(hindi_blocks))) - used_hindi)
  return {"hindi_blocks": hindi_blocks, "marathi_units": marathi_units,
          "hnorms": hnorms, "mnorms": mnorms, "grouped": grouped,
          "unmatched": unmatched, "align_notes": align_notes,
          "unmatched_hindi": still_unmatched_hindi}


def verify_marathi_merged(plan, hindi_dir):
  """Verify each Marathi unit is fully merged. Errs toward keeping.

  A unit counts as merged only if aligned AND its translation (if any) is
  present in the anchor Hindi file AND its differing readings are recorded
  (or identical). Returns (merged_units, gaps).
  """
  hindi_blocks = plan["hindi_blocks"]
  marathi_units = plan["marathi_units"]
  # Hindi file norms for presence checks.
  file_norms = {}
  for md in sorted(get_md_files_from_path(dir_path=hindi_dir), key=lambda m: str(m.file_path)):
    p = str(md.file_path)
    if os.path.basename(p) in SKIP_BASENAMES:
      continue
    try:
      (_m, c) = MdFile(p).read()
    except Exception:
      continue
    file_norms[p] = cm._normalize_mula_for_comparison(c or "")
  # Marathi unit -> group anchor Hindi block.
  unit_anchor = {}
  for g in plan["grouped"]:
    his = sorted(g["his"])
    for mj in g["mjs"]:
      unit_anchor[mj] = hindi_blocks[his[-1]]
  merged, gaps = [], []
  for mj, u in enumerate(marathi_units):
    if mj in plan["unmatched"]:
      gaps.append({"file": u["file"], "kind": u["kind"], "numbers": u["numbers"],
                   "issues": ["unaligned"],
                   "head": ((u["mula"]["body"] or "")[:70]).replace(chr(10), " ")})
      continue
    hb = unit_anchor.get(mj)
    if hb is None:
      gaps.append({"file": u["file"], "kind": u["kind"], "numbers": u["numbers"],
                   "issues": ["no-anchor"],
                   "head": ((u["mula"]["body"] or "")[:70]).replace(chr(10), " ")})
      continue
    issues = []
    fnorm = file_norms.get(hb["file"], "")
    if u["trans"] is not None:
      tbody = (u["trans"]["body"] or "").strip()
      tnorm = cm._normalize_mula_for_comparison(tbody)
      if tnorm and tnorm not in fnorm:
        issues.append("translation-missing")
    # Variant side: differing reading must be recorded in the anchor file
    # (or identical to Hindi, modulo nukta transfer already applied).
    mtext = (u["mula"]["body"] or "").strip()
    if mtext:
      # Hindi counterpart span = anchor block's mula text.
      htext = (hb["mula"]["body"] if hb["mula"] is not None else hb["match_text"]) or ""
      if cm._normalize_mula_for_comparison(htext) != cm._normalize_mula_for_comparison(mtext):
        if cm._normalize_mula_for_comparison(mtext) not in fnorm:
          issues.append("reading-unrecorded")
    if issues:
      gaps.append({"file": u["file"], "kind": u["kind"], "numbers": u["numbers"],
                   "issues": issues,
                   "head": (mtext[:70]).replace(chr(10), " ")})
    else:
      merged.append(u)
  return (merged, gaps)


def mark_unmatched_marathi(base_dir, dry_run=False):
  """Mark unmatched Marathi mula details with unmatched="true" (and unmark matched ones).

  Operates per kanda via the shared alignment plan: marathi units with no
  Hindi counterpart get the marker on their मूल detail tag (attributes
  otherwise preserved); stale markers on now-matched units are removed.
  Returns stats.
  """
  stats = {"files": 0, "marked": 0, "unmarked": 0}
  hindi_to_marathi = {}
  for (hsub, msubs) in KANDA_PAIRS:
    if isinstance(msubs, str):
      msubs = [msubs]
    hindi_to_marathi.setdefault(hsub, []).extend(msubs)
  for hsub, msubs in hindi_to_marathi.items():
    plan = plan_kanda(os.path.join(base_dir, hsub),
                      [os.path.join(base_dir, m) for m in msubs])
    unmatched_idx = set(plan["unmatched"])
    # Group unit indices per file.
    by_file = {}
    for mj, u in enumerate(plan["marathi_units"]):
      by_file.setdefault(u["file"], []).append(mj)
    for path, mjs in sorted(by_file.items()):
      md = MdFile(file_path=path)
      (_meta, content) = md.read()
      if not content:
        continue
      details = cm._parse_details(content)
      # Map marathi unit index -> its mula detail (units built in file order).
      mula_details = [d for d in details if _clean_mr_title(d["title"]).startswith("मूल (")]
      edits = []  # (tag_start, tag_end, new_tag)
      changed_marks = changed_unmarks = 0
      for k, mj in enumerate(sorted(mjs)):
        if k >= len(mula_details):
          continue
        d = mula_details[k]
        tag_end = content.find(">", d["start"])
        if tag_end < 0 or tag_end > d["start"] + 200:
          continue
        tag = content[d["start"]:tag_end + 1]
        has_mark = "unmatched=" in tag
        if mj in unmatched_idx:
          if not has_mark:
            new_tag = tag[:-1].rstrip() + ' unmatched="true">'
            edits.append((d["start"], tag_end + 1, new_tag))
            changed_marks += 1
        else:
          if has_mark:
            new_tag = regex.sub(r"\s*unmatched=\"true\"", "", tag)
            edits.append((d["start"], tag_end + 1, new_tag))
            changed_unmarks += 1
      if edits:
        new_content = content
        for (s, e, block) in sorted(edits, key=lambda x: -x[0]):
          new_content = new_content[:s] + block + new_content[e:]
        if new_content != content:
          if not dry_run:
            md.replace_content_metadata(new_content=new_content, dry_run=False)
          stats["files"] += 1
          stats["marked"] += changed_marks
          stats["unmarked"] += changed_unmarks
  logging.info(f"mark_unmatched_marathi: {stats}")
  return stats


def prune_merged_marathi(base_dir, dry_run=False):
  """Delete Marathi files whose every unit verifies as fully merged.

  A unit counts as merged only if aligned AND its translation (if any) is
  present in the anchor Hindi file AND its differing readings are recorded
  (or identical). _index.md files are never deleted. Errs toward keeping.
  Returns stats + per-file decisions.
  """
  stats = {"files_checked": 0, "files_deleted": 0, "files_kept": 0}
  decisions = []
  hindi_to_marathi = {}
  for (hsub, msubs) in KANDA_PAIRS:
    if isinstance(msubs, str):
      msubs = [msubs]
    hindi_to_marathi.setdefault(hsub, []).extend(msubs)
  for hsub, msubs in hindi_to_marathi.items():
    hindi_dir = os.path.join(base_dir, hsub)
    plan = plan_kanda(hindi_dir, [os.path.join(base_dir, m) for m in msubs])
    (merged, gaps) = verify_marathi_merged(plan, hindi_dir)
    merged_files = {u["file"] for u in merged}
    gap_files = {g["file"] for g in gaps}
    units_by_file = {}
    for u in plan["marathi_units"]:
      units_by_file.setdefault(u["file"], []).append(u)
    # All marathi md files (including ones with zero verse units, e.g.
    # front-matter prose that was never verse-mergeable).
    all_paths = set()
    for msub in msubs:
      for md in get_md_files_from_path(dir_path=os.path.join(base_dir, msub)):
        p = str(md.file_path)
        if os.path.basename(p) in SKIP_BASENAMES:
          continue
        all_paths.add(p)
    for path in sorted(all_paths):
      stats["files_checked"] += 1
      if os.path.basename(path) == "_index.md":
        stats["files_kept"] += 1
        decisions.append((path, "kept-index"))
        continue
      if not units_by_file.get(path):
        # No verse units at all (front-matter prose etc.): nothing
        # verse-anchored was merged from here; keep.
        stats["files_kept"] += 1
        decisions.append((path, "kept-no-units"))
        continue
      if path in merged_files and path not in gap_files:
        decisions.append((path, "deleted"))
        stats["files_deleted"] += 1
        if not dry_run:
          os.remove(path)
          logging.info(f"Removed fully-merged marathi file: {path}")
      else:
        stats["files_kept"] += 1
        decisions.append((path, "kept-gaps"))
  logging.info(f"prune_merged_marathi: {stats}")
  return stats, decisions


def _apply_file_edits(path, actions, dry_run=False, stats=None):
  """Apply a file's group actions in phases with re-parses; identity = mula norm."""
  from collections import deque
  md = MdFile(file_path=path)
  (meta, content) = md.read()
  orig_content = content
  n_trans = n_var = n_tr = 0
  # Phase 1: nukta transfers. Identity: post-transfer norm with nukta
  # stripped == pre-transfer nukta-stripped norm; FIFO queues for duplicates.
  transfers = [a for a in actions if a["kind"] == "transfer"]
  if transfers:
    from collections import defaultdict, deque
    details = cm._parse_details(content or "")
    q = defaultdict(deque)
    for d in details:
      if d["title"] == "मूल":
        q[cm._strip_nukta(cm._normalize_mula_for_comparison(d["body"]))].append(d)
    new_content = content
    replacements = []
    for a in transfers:
      want_stripped = cm._strip_nukta(a["ident"])
      if not q.get(want_stripped):
        continue
      best = q[want_stripped].popleft()
      # Sync vipras if identical to mula pre-transfer.
      pre_norm = cm._normalize_mula_for_comparison(best["body"])
      replacements.append((best["start"], best["end"],
                           f"<details{best['attrs']}><summary>{best['title']}</summary>\n\n{a['new_body'].strip()}\n</details>"))
      if a.get("sync_vipras"):
        for d2 in cm._parse_details(new_content):
          if d2["title"] == "विश्वास-प्रस्तुतिः" and cm._normalize_mula_for_comparison(d2["body"]) == pre_norm:
            replacements.append((d2["start"], d2["end"],
                                 f"<details{d2['attrs']}><summary>{d2['title']}</summary>\n\n{a['new_body'].strip()}\n</details>"))
            break
      n_tr += 1
    for (s, e, block) in sorted(replacements, key=lambda x: -x[0]):
      new_content = new_content[:s] + block + new_content[e:]
    content = new_content
  # Phase 2: translation inserts (match mula by ident; anchor after last
  # भावार्थ else mula). Runs BEFORE variant appends so anchors match.
  trans = [a for a in actions if a["kind"] == "trans"]
  if trans:
    details = cm._parse_details(content)
    from collections import defaultdict
    q = defaultdict(deque)
    for d in details:
      if d["title"] == "मूल":
        q[cm._normalize_mula_for_comparison(d["body"])].append(d)
    whole_norm = cm._normalize_mula_for_comparison(content)
    inserts = []
    # End position of each mula's translation run (following भावार्थ details).
    for a in trans:
      tnorm = cm._normalize_mula_for_comparison(a["tbody"])
      if tnorm and tnorm in whole_norm:
        continue  # already present
      if not q.get(a["ident"]):
        continue
      anchor_mula = q[a["ident"]].popleft()
      # Find following भावार्थ run end. The run continues only through
      # भावार्थ details whose verse numbers agree with the anchor block
      # (orphan translations of other verses must not extend it).
      anchor_nums = set(_extract_numbers(anchor_mula["body"] or ""))
      pos = anchor_mula["end"]
      for d in details:
        if d["start"] <= anchor_mula["end"]:
          continue
        if d["title"] == "भावार्थ":
          # Must precede the next मूल.
          intervening = [x for x in details if anchor_mula["end"] < x["start"] < d["start"] and x["title"] == "मूल"]
          if intervening:
            break
          bnums = set(_extract_numbers(d["body"] or ""))
          if bnums and anchor_nums and not (bnums & anchor_nums):
            break
          pos = d["end"]
          continue
        if d["title"] in ("मूल", "विश्वास-प्रस्तुतिः"):
          break
        # Other titles (incl. existing Marathi translations): skipped over,
        # anchor stays (multi-unit groups keep Marathi order via batching below).
        continue
      inserts.append((pos, f"\n\n<details><summary>{MARATHI_TRANS_TITLE}</summary>\n\n{a['tbody'].strip()}\n</details>"))
      whole_norm += tnorm
      n_trans += 1
    # Batch same-position inserts preserving action order.
    by_pos = {}
    for (pos, html) in inserts:
      by_pos.setdefault(pos, []).append(html)
    for (pos, htmls) in sorted(by_pos.items(), key=lambda x: -x[0]):
      content = content[:pos] + "".join(htmls) + content[pos:]
  # Phase 3: variant records (match mula by post-transfer ident norm).
  variants = [a for a in actions if a["kind"] == "variant"]
  if variants:
    details = cm._parse_details(content)
    from collections import defaultdict
    q = defaultdict(deque)
    for d in details:
      if d["title"] == "मूल":
        q[cm._normalize_mula_for_comparison(d["body"])].append(d)
    whole_norm = cm._normalize_mula_for_comparison(content)
    replacements = []
    for a in variants:
      reading_norm = cm._normalize_mula_for_comparison(a["reading"])
      if not reading_norm or reading_norm in whole_norm:
        continue  # already recorded
      if not q.get(a["ident"]):
        continue
      anchor = q[a["ident"]].popleft()
      new_body = anchor["body"].strip() + f"\n{cm.VARIANT_SEPARATOR}\n" + a["reading"].strip() + "\n"
      replacements.append((anchor["start"], anchor["end"],
                           f"<details{anchor['attrs']}><summary>{anchor['title']}</summary>\n\n{new_body}</details>"))
      whole_norm += reading_norm
      n_var += 1
    for (s, e, block) in sorted(replacements, key=lambda x: -x[0]):
      content = content[:s] + block + content[e:]
  if stats is not None:
    stats["translations"] += n_trans
    stats["variants"] += n_var
    stats["nukta_transfers"] += n_tr
  if content != orig_content and not dry_run:
    md.replace_content_metadata(new_content=content, dry_run=False)
  return (n_trans, n_var)


def main(argv=None):
  ap = argparse.ArgumentParser(description=__doc__)
  ap.add_argument("--dry-run", action="store_true")
  ap.add_argument("--kandas", default="1,2,3,4,5,6,7")
  ap.add_argument("--base", default=BASE)
  ap.add_argument("--prune", action="store_true",
                  help="after merging, delete marathi files verifying as fully merged")
  ap.add_argument("--repair", action="store_true",
                  help="repair Hindi structural gaps (bare verses, missing vipras) only")
  ap.add_argument("--mark-unmatched", action="store_true",
                  help="mark unmatched Marathi mula details with unmatched=\"true\"")
  ap.add_argument("--fix-leaks", action="store_true",
                  help="move Hindi prose leaked into vipras/मूल back to भावार्थ")
  args = ap.parse_args(argv)
  wanted = {int(x) for x in args.kandas.split(",") if x.strip()}
  if args.repair:
    totals = {"files": 0, "bare_deleted": 0, "bare_wrapped": 0, "relocated": 0, "vipras_added": 0, "mula_added": 0}
    review = []
    for idx, (hsub, _msubs) in enumerate(KANDA_PAIRS, start=1):
      if idx not in wanted:
        continue
      t, r = repair_manas_corpus(os.path.join(args.base, hsub.rstrip("/")), dry_run=args.dry_run)
      for k in totals:
        totals[k] += t.get(k, 0)
      review.extend(r)
    print(f"REPAIR RESULT: {totals} review={len(review)}")
    for x in sorted(set(review))[:30]:
      print("  REVIEW:", x)
    return 0
  if args.mark_unmatched:
    stats = mark_unmatched_marathi(args.base, dry_run=args.dry_run)
    print(f"MARK RESULT: {stats}")
    return 0
  if args.fix_leaks:
    totals = {"files": 0, "lines_moved": 0, "lines_deleted_only": 0, "bhavarth_created": 0}
    review = []
    for idx, (hsub, _msubs) in enumerate(KANDA_PAIRS, start=1):
      if idx not in wanted:
        continue
      t, r = fix_leaked_prose_corpus(os.path.join(args.base, hsub.rstrip("/")), dry_run=args.dry_run)
      for k in totals:
        totals[k] += t.get(k, 0)
      review.extend(r)
    print(f"LEAKFIX RESULT: {totals} review={len(review)}")
    for x in sorted(set(review))[:30]:
      print("  REVIEW:", x)
    return 0
  if args.prune:
    stats, decisions = prune_merged_marathi(args.base, dry_run=args.dry_run)
    print(f"PRUNE RESULT: {stats}")
    kept = [d for d in decisions if d[1] != "deleted"]
    print(f"kept files: {len(kept)} (showing up to 20)")
    for path, why in kept[:20]:
      print(f"  KEPT ({why}): {path.replace(args.base, '')}")
    return 0
  for idx, (hsub, msubs) in enumerate(KANDA_PAIRS, start=1):
    if idx not in wanted:
      continue
    print(f"=== kanda {idx}: {hsub} <- {msubs} ===", flush=True)
    stats, review = merge_kanda(os.path.join(args.base, hsub),
                                [os.path.join(args.base, m) for m in msubs],
                                dry_run=args.dry_run)
    print(f"KANDA {idx} RESULT: {stats} review={len(review)}", flush=True)
    # Marathi-side lines are few and actionable: always show all of them.
    # UNMATCHED-hindi lines are expected-by-design flood in this corpus: cap them.
    mr_lines = [r for r in review if "UNMATCHED hindi" not in r]
    hi_lines = [r for r in review if "UNMATCHED hindi" in r]
    for r in mr_lines:
      print("  REVIEW:", r, flush=True)
    for r in hi_lines[:15]:
      print("  REVIEW:", r, flush=True)
    if len(hi_lines) > 15:
      print(f"  ... +{len(hi_lines) - 15} further UNMATCHED hindi lines omitted", flush=True)
  return 0


if __name__ == "__main__":
  sys.exit(main())
