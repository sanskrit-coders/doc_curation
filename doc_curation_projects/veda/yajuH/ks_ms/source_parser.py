"""Source parsers and OCR/orthography repair for Maitrāyaṇī (MS) and Kāṭhaka (KS) Saṁhitās.

- For **MS** (``maitrAyaNIyam/saMhitA/sarva-prastutiH/{1..4}/{01..16}.md``):
  Splits each prapāṭhaka file at ``## १``, ``## २``, ... into per-anuvāka records, keeping
  raw TITUS lines for ``मूलम्`` and cleanly repairing TITUS encoding glitches
  (``ृ᳓̄`` -> ``ॄ᳓``, ``क्ŀ̥`` / ``क्र्ŀ̥`` -> ``कॢ``, ``संप्र्ञ्चाना᳓`` -> ``संपृञ्चाना᳓``,
  stray editorial ``*``) for ``विश्वास-प्रस्तुतिः`` and ``पद-पाठः``.
- For **KS** (``kAThakam/kaTha-kapiShTalAH/saMhitA/mUlam/schroeder/...``):
  Parses Schroeder frontmatter, ``**bold**`` ṛk spans, inline ``[^id]`` footnotes +
  definitions, ``<details><summary>टिप्पणी...</summary>`` blocks, and ``cf. ...`` notes.
  Repairs clear Schroeder OCR typos in ``विश्वास-प्रस्तुतिः`` against clean unaccented
  ``visvara-saMhitA`` / ``ashvamedha-vachanAni`` while preserving syllable-aligned US
  accents and keeping raw Schroeder verbatim in ``मूलम्`` and apparatus in
  ``Schroeder - टिप्पणी``.
"""

from __future__ import annotations

import dataclasses
import difflib
import os
import re
from typing import Sequence

from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import (
  US_SVARITA,
  US_UDATTA,
  apply_marks_to_token,
  has_us_accents,
  syllables_with_marks,
)
from doc_curation.sanskrit.accent.shatapatha_solver import UnifiedVedicLexicon, _deva_to_slp
from doc_curation_projects.veda.yajuH.ks_ms.reference_index import (
  to_ascii_digits,
  to_dev_digits,
)

DEFAULT_KS_VISVARA_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/visvara-saMhitA"
DEFAULT_KS_ASHVAMEDHA_DIR = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/kAThakam/ashvamedha-vachanAni"

_FOOTNOTE_DEF_RE = re.compile(r"(?m)^\[\^([^\]]+)\]:\s*(.*)$")
_FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]]+)\]")
_UNNUM_DETAILS_RE = re.compile(r"<details><summary>(टिप्पणी[^<]*)</summary>(.*?)</details>", re.S)
_CF_TAIL_RE = re.compile(r"(?:\s+(?:cfr?\.|cf\b)[^\n]+)\s*$")
_DEVA_TOKEN_RE = re.compile(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952ऽ]+")
_ALL_ACC_RE = re.compile(r"[\u0951-\u0957\u1cd0-\u1cff]")

# Impossible/corrupt Devanagari OCR combinations in Schroeder (always wrong in Sanskrit)
_IMPOSSIBLE_DEVA_RE = re.compile(
  r"(?:[क-ह]्?[ािीुूृेैोौ][ािीुूृेैोौ]"  # double matra e.g. `व्यृोमा`
  r"|व्यृसि|ध्सृ|द्वप्स्व्र|त्रै᳓व|अग्रिहोत्र|अग्न्या)"
)


@dataclasses.dataclass
class MsAnuvakaSource:
  """One parsed anuvāka from an MS prapāṭhaka markdown file."""

  kanda: str  # "1".."4"
  prapathaka: str  # "01".."16"
  anuvaka_num: int
  title_dev: str  # "०१", "०२", ...
  raw_lines: list[str]
  clean_lines: list[str]


@dataclasses.dataclass
class KsSpanPiece:
  """One contiguous text segment of a KS Schroeder anuvāka (either prose/yajuṣ or ``**bold**`` ṛk)."""

  raw_mula: str  # Schroeder text (without `[^ref]` / `**` / `cf.`), verbatim OCR
  repaired_vp: str  # OCR-repaired text preserving Schroeder's US accents
  is_bold_rk: bool
  footnote_ids: list[str]
  ocr_repairs: list[tuple[str, str]]


@dataclasses.dataclass
class KsAnuvakaSource:
  """One parsed KS Schroeder anuvāka with apparatus notes and OCR-repaired VP text."""

  rel_path: str  # e.g. "1_iThimikA/01_puroDAshasthAnakam/01.md"
  part_dir: str  # "1_iThimikA"
  sthanaka_dir: str  # "01_puroDAshasthAnakam"
  sthanaka_num: int
  anuvaka_num: int
  title: str
  pieces: list[KsSpanPiece]
  footnote_defs: dict[str, str]
  unnumbered_notes: list[str]
  cf_notes: list[str]
  has_accents: bool
  accent_coverage: float  # fraction of words with US accents in Schroeder (0.0..1.0)
  visvara_matched: bool


def clean_ms_titus_line(raw_line: str) -> str:
  """Repair MS TITUS encoding quirks while keeping US accents & quote markers clean."""
  s = raw_line.strip()
  # 1. `ृ` + optional US accent + combining macron `\u0304` -> `ॄ` + accent (`पितृ᳓̄न्` -> `पितॄ᳓न्`)
  s = re.sub(r"ृ([\u1cd3\u1cd9]*)\u0304", r"ॄ\1", s)
  # 2. `क्र्ŀ̥` / `क्ŀ̥` -> `कॢ` (`क्र्ŀ̥प्ति` -> `कॢप्ति`)
  s = re.sub(r"क्र्?ŀ\u0325", "कॢ", s)
  # 3. Known TITUS encoding typos (`संप्र्ञ्चाना᳓` -> `संपृञ्चाना᳓`, `धुर्वा᳓` -> `ध्रुवा᳓`)
  s = s.replace("संप्र्ञ्चाना", "संपृञ्चाना")
  s = s.replace("धुर्वा᳓ अस्मि᳓न्", "ध्रुवा᳓ अस्मि᳓न्")
  # 4. Strip TITUS editorial asterisk (` * ॥` -> ` ॥`)
  s = re.sub(r"\s*\*\s*", " ", s)
  # 5. Normalize stray double spaces
  s = re.sub(r"[ \t]+", " ", s).strip()
  return s


def strip_ms_quote_backslashes(text: str) -> str:
  """Clean TITUS Brāhmaṇa ``\\ ... \\`` quote delimiters for ``विश्वास-प्रस्तुतिः`` display.

  TITUS uses ``\\ quote \\ इ᳓ति`` (or a single ``\\`` right before ``इ᳓ति`` to mark quote end).
  """
  if "\\" not in text:
    return text
  parts = text.split("\\")
  if len(parts) >= 3 and len(parts) % 2 == 1:
    out: list[str] = []
    for idx, p in enumerate(parts):
      ps = p.strip()
      if not ps:
        continue
      if idx % 2 == 1:
        out.append(f"‘{ps}’")
      else:
        out.append(ps)
    return re.sub(r"\s+", " ", " ".join(out)).strip()
  # Unpaired `\` right before `इति` -> insert clean pause `, ` so sandhi verifier respects quote hiatus!
  s = re.sub(r"\s*\\\s*(?=इ[\u1cd3\u1cd9]*ति)", ", ", text)
  s = s.replace("\\", " ")
  return re.sub(r"\s+", " ", s).strip()


def parse_ms_prapathaka(file_path: str) -> list[MsAnuvakaSource]:
  """Parse an MS prapāṭhaka markdown file into ordered ``MsAnuvakaSource`` objects."""
  txt = open(file_path, encoding="utf-8").read()
  body = txt.split("+++", 2)[2] if txt.startswith("+++") and txt.count("+++") >= 2 else txt
  prap = os.path.splitext(os.path.basename(file_path))[0]
  kanda = os.path.basename(os.path.dirname(file_path))

  raw_sections: list[tuple[int, list[str]]] = []
  cur_num: int | None = None
  cur_raw: list[str] = []

  def _flush() -> None:
    if cur_num is None or not cur_raw:
      return
    raw_sections.append((cur_num, list(cur_raw)))

  for ln in body.splitlines():
    s = ln.strip()
    if not s:
      continue
    m_h = re.match(r"^##\s+([०-९0-9]+)\s*$", s)
    if m_h:
      _flush()
      cur_num = int(to_ascii_digits(m_h.group(1)))
      cur_raw = []
      continue
    if cur_num is None:
      cur_num = 1
    cur_raw.append(s)
  _flush()

  # Merge any out-of-order / duplicate TITUS `## N` glitch (e.g. MS 2/01 has `2 -> 3 (2 lines) -> 2 (10 lines) -> 3 (54 lines)`
  # where lines between the first `## 2` and the second `## 3` all belong to anuvāka 2!) without losing a single line!
  merged_sections: list[tuple[int, list[str]]] = []
  idx_s = 0
  while idx_s < len(raw_sections):
    num_s, lines_s = raw_sections[idx_s]
    # Look ahead: does `num_s` recur later in `raw_sections`?
    later_idx = None
    for j in range(idx_s + 1, len(raw_sections)):
      if raw_sections[j][0] == num_s:
        later_idx = j
        break
    if later_idx is not None:
      # Absorb everything from `idx_s` through `later_idx` inclusive into `num_s`!
      comb: list[str] = []
      for j in range(idx_s, later_idx + 1):
        comb.extend(raw_sections[j][1])
      merged_sections.append((num_s, comb))
      idx_s = later_idx + 1
    else:
      merged_sections.append((num_s, lines_s))
      idx_s += 1

  anuvakas: list[MsAnuvakaSource] = []
  for num_s, lines_s in merged_sections:
    title_dev = to_dev_digits(f"{num_s:02d}")
    clean_lines = [clean_ms_titus_line(ln) for ln in lines_s]
    anuvakas.append(
      MsAnuvakaSource(
        kanda=kanda,
        prapathaka=prap,
        anuvaka_num=num_s,
        title_dev=title_dev,
        raw_lines=lines_s,
        clean_lines=clean_lines,
      )
    )
  return anuvakas


# ---------------------------------------------------------------------------
# KS Visvara Loader & Schroeder OCR Repair
# ---------------------------------------------------------------------------

_VISVARA_CACHE: dict[str, dict[int, str]] = {}


def load_ks_visvara_anuvakas(
  part_dir: str,
  sthanaka_num: int,
  *,
  visvara_dir: str = DEFAULT_KS_VISVARA_DIR,
  ashvamedha_dir: str = DEFAULT_KS_ASHVAMEDHA_DIR,
) -> dict[int, str]:
  """Load ``{anuvaka_num: text}`` from ``visvara-saMhitA`` or ``ashvamedha-vachanAni``."""
  key = f"{part_dir}:{sthanaka_num:02d}"
  if key in _VISVARA_CACHE:
    return _VISVARA_CACHE[key]

  base_dir = ashvamedha_dir if part_dir == "5_ashvamedhaH" else visvara_dir
  fp = os.path.join(base_dir, f"{sthanaka_num:02d}.md")
  res: dict[int, str] = {}
  if not os.path.exists(fp):
    _VISVARA_CACHE[key] = res
    return res

  txt = open(fp, encoding="utf-8", errors="ignore").read()
  body = txt.split("+++", 2)[2] if txt.startswith("+++") and txt.count("+++") >= 2 else txt
  # Strip colophon `॥ इति श्रीयजुषि काठके ... ॥`
  body = re.sub(r"॥\s*इति\s+श्रीयजुषि.*", "", body, flags=re.S)

  # Split at anuvāka end markers `॥ १ ॥`, `॥१॥`, `।। ४ ।।`
  parts = re.split(r"(?:॥|।।)\s*([०-९0-9]{1,2})\s*(?:॥|।।)", body)
  for idx in range(0, len(parts) - 1, 2):
    chunk = parts[idx].strip()
    num_s = to_ascii_digits(parts[idx + 1].strip())
    if not num_s.isdigit():
      continue
    n = int(num_s)
    # Remove leading sthānaka title line (`पुरोडाशः।`, `अग्निहोत्र-ब्राह्मणम् ।`) from anuvāka 1
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    if n == 1 and len(lines) >= 2 and len(lines[0]) < 40 and lines[0].endswith(("।", "॥")):
      lines = lines[1:]
    # Rejoin OCR hyphen-breaks inside visvara (`आप्याय - ध्वमघ्न्या` -> `आप्यायध्वमघ्न्या`)
    joined = "\n".join(lines)
    joined = re.sub(r"\s*-\s+", "", joined)
    if n not in res:
      res[n] = joined
  _VISVARA_CACHE[key] = res
  return res


def _transfer_us_marks_to_repaired_token(old_tok: str, new_bare_tok: str) -> str:
  """Transfer US accent marks from ``old_tok`` onto OCR-repaired ``new_bare_tok``."""
  if not has_us_accents(old_tok):
    return new_bare_tok
  old_keys, old_mks = syllables_with_marks(old_tok)
  new_keys, _ = syllables_with_marks(new_bare_tok)
  if not new_keys or not old_keys:
    return new_bare_tok
  if len(old_keys) == len(new_keys):
    try:
      return apply_marks_to_token(new_bare_tok, old_mks)
    except ValueError:
      return new_bare_tok
  # Align syllables with SequenceMatcher when an OCR drop/insertion changed syllable count by 1
  sm = difflib.SequenceMatcher(a=old_keys, b=new_keys, autojunk=False)
  new_mks = [""] * len(new_keys)
  for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
      for k in range(i2 - i1):
        new_mks[j1 + k] = old_mks[i1 + k]
    elif tag == "replace":
      # Preserve accent from old span onto corresponding new syllable when count matches or is 1
      acc_in_old = [(i - i1, old_mks[i]) for i in range(i1, i2) if old_mks[i]]
      for rel_i, mk in acc_in_old:
        dst = min(j2 - 1, j1 + rel_i)
        if not new_mks[dst]:
          new_mks[dst] = mk
  try:
    return apply_marks_to_token(new_bare_tok, new_mks)
  except ValueError:
    return new_bare_tok


def _is_legitimate_orth_diff(a_bare: str, b_bare: str) -> bool:
  """Return True if ``a_bare`` vs ``b_bare`` is a legitimate Vedic spelling variant (NOT an OCR typo)."""
  def _norm(w: str) -> str:
    w = w.replace("ँ", "ं").replace("च्छ", "छ").replace("सन्न", "संन").replace("सँ", "सं")
    w = re.sub(r"स्स्(?=[थतपफकख])", "स्", w)
    w = re.sub(r"र्([क-ह])्\1", r"र्\1", w)
    w = w.replace("ऽ", "")
    return w
  return _norm(a_bare) == _norm(b_bare)


# High-confidence 1–3 char Schroeder Devanagari OCR confusion pairs `(schroeder_ocr, visvara_clean)`
_SCHROEDER_OCR_PAIRS: frozenset[tuple[str, str]] = frozenset({
  ("", "र्"),          # `त्वोजे` -> `त्वोर्जे`
  ("ग", "घ"),          # `अग्न्या` -> `अघ्न्या`
  ("ृ", ""),           # `पृथिव्यृसि` -> `पृथिव्यसि`, `व्यृोमा` -> `व्योमा`
  ("स्य", "स्प"),      # `वाचस्यतये` -> `वाचस्पतये`
  ("य", "प"),          # `वाचस्यतये` -> `वाचस्पतये` (if aligned as `य`->`प`)
  ("", "्र"),          # `दप्सो` -> `द्रप्सो`, `सुग्भवति` -> `स्रुग्भवति`
  ("द", "द्र"),        # `दप्सो` -> `द्रप्सो`
  ("द्व", "द्र"),      # `द्वप्सो` -> `द्रप्सो`
  ("न", "ग्र"),        # `ताग्ने` -> `ताग्रे`
  ("ने", "ग्रे"),      # `ताग्ने` -> `ताग्रे`
  ("ग्रि", "ग्नि"),    # `अग्रिहोत्र` -> `अग्निहोत्र`
  ("ग्र", "ग्न"),      # `अग्रि` -> `अग्नि`
  ("र", "न"),          # `अग्रि` -> `अग्नि` (aligned as `र`->`न`)
  ("ध्स", "ध्यस"),     # `अध्सृज्यत` -> `अध्यसृज्यत`
  ("", "्य"),          # `अध्सृज्यत` -> `अध्यसृज्यत` (aligned as `""`->`्य`)
  ("स्मा", "स्सा"),    # `विश्वायस्मा` -> `विश्वायस्सा`
  ("म", "स"),          # `विश्वायस्मा` -> `विश्वायस्सा` (aligned as `म`->`स`)
  ("त्र", "ष"),        # `तस्मादेत्रैवम्` -> `तस्मादेषैवम्`
  ("त्रै", "षै"),      # `देत्रैवम्` -> `देषैवम्`
  ("सु", "स्रु"),      # `सुग्भवति` -> `स्रुग्भवति`
  ("व", "ब"),          # common Devanagari OCR swap `व`/`ब` (only when unattested!)
  ("ब", "व"),
  ("ख", "रव"),
  ("भ", "म"),
  ("म", "भ"),
  ("घ", "ध"),
  ("ध", "घ"),
})


def _flat_bare_with_char_map(text: str) -> tuple[str, list[int]]:
  """Extract accent-stripped, space/punct-stripped Devanagari chars + their indices in ``text``."""
  chars: list[str] = []
  pos_map: list[int] = []
  for idx, ch in enumerate(text):
    if "\u0900" <= ch <= "\u0963" or "\u0971" <= ch <= "\u097f":
      if ch in ("।", "॥", "ऽ"):
        continue
      if "\u0951" <= ch <= "\u0957":
        continue
      chars.append(ch)
      pos_map.append(idx)
  return "".join(chars), pos_map


def repair_ks_text_with_visvara(
  schroeder_text: str,
  visvara_text: str,
  lex: UnifiedVedicLexicon | None = None,
) -> tuple[str, list[tuple[str, str]]]:
  """Repair clear Schroeder OCR typos using ``visvara_text`` while preserving US accents.

  Uses space-agnostic character alignment so fused Schroeder strings (like
  ``प्रजापतिर्वा इदमासीत्तस्मादग्नि᳓र᳓ध्सृज्यत``) align cleanly against spaced
  ``visvara-saMhitA`` without dropping any US accents or overwriting genuine variants.
  """
  work = schroeder_text.replace("\u0952", "").replace("\u1ced", "").replace("\u1cdc", "")
  # 0. Repair unmistakable Schroeder Devanagari OCR artifacts BEFORE visvara diffing:
  # (a) Kaṭha under-hook independent svarita misread as matra `ृ` before another vowel matra (`सरस्यृाय` -> `सरस्या᳙य`,
  #     `यृोऽनग्निः` -> `यो᳙ऽनग्निः`, `वृीहि` -> `वी᳙हि`, `तन्वृो` -> `तन्वो᳙`, `लोकृेऽस्पर्धन्त` -> `लोके᳙ऽस्पर्धन्त`)!
  # (b) Impossible palatal-nasal cluster `ञ्व` -> `ञ्च` (`प्रत्यञ्व` -> `प्रत्यञ्च`, `उदञ्वो` -> `उदञ्चो`, `प्राञ्व` -> `प्राञ्च`).
  pre_repairs: list[tuple[str, str]] = []

  def _fix_katha_svarita_hook(m: re.Match) -> str:
    matra = m.group(1)
    existing_acc = m.group(2)
    pre_repairs.append((m.group(0), f"ृ{matra}→{matra}᳙"))
    return matra + (existing_acc or US_SVARITA)

  work = re.sub(r"ृ([ािीुूेैोौ])([\u1cd3\u1cd9]*)", _fix_katha_svarita_hook, work)
  if "ञ्व" in work:
    pre_repairs.append(("ञ्व", "ञ्व→ञ्च"))
    work = work.replace("ञ्व", "ञ्च")

  if not visvara_text or not work.strip():
    return work, pre_repairs

  s_flat, s_map = _flat_bare_with_char_map(work)
  v_flat, _ = _flat_bare_with_char_map(visvara_text)
  if len(s_flat) < 8 or len(v_flat) < 8:
    return work, pre_repairs

  # When `work` is one piece of a multi-piece anuvāka, locate its matching window inside `v_flat`
  if len(v_flat) > len(s_flat) + 40:
    probe = s_flat[: min(24, len(s_flat))]
    pos = v_flat.find(probe[:12])
    if pos >= 0:
      lo = max(0, pos - 20)
      hi = min(len(v_flat), pos + len(s_flat) + 40)
      v_flat = v_flat[lo:hi]
    else:
      # Fallback: find best matching block via SequenceMatcher on full v_flat
      sm_loc = difflib.SequenceMatcher(None, s_flat, v_flat, autojunk=False)
      blocks = sm_loc.get_matching_blocks()
      best_b = max(blocks, key=lambda b: b.size) if blocks else None
      if best_b and best_b.size >= 8:
        lo = max(0, best_b.b - best_b.a - 25)
        hi = min(len(v_flat), lo + len(s_flat) + 50)
        v_flat = v_flat[lo:hi]

  sm = difflib.SequenceMatcher(None, s_flat, v_flat, autojunk=False)
  if sm.ratio() < 0.70:
    return work, pre_repairs

  opcodes = sm.get_opcodes()
  # Collect safe char-level edits `(orig_start, orig_end, replacement_str, old_snippet, new_snippet)`
  edits: list[tuple[int, int, str, str, str]] = []

  def _extract_word_around(txt: str, pos_lo: int, pos_hi: int) -> str:
    a = pos_lo
    while a > 0 and txt[a - 1] not in " \t\n।॥":
      a -= 1
    b = pos_hi
    while b < len(txt) and txt[b] not in " \t\n।॥":
      b += 1
    return txt[a:b]

  for oi, (tag, i1, i2, j1, j2) in enumerate(opcodes):
    if tag == "equal":
      continue
    a_seg = s_flat[i1:i2]
    b_seg = v_flat[j1:j2]
    if len(a_seg) > 3 or len(b_seg) > 4:
      continue
    # Require strong matching anchors (>= 4 chars equal) immediately on BOTH sides (or >= 5 on one side at edge)
    left_eq = (opcodes[oi - 1][2] - opcodes[oi - 1][1]) if (oi > 0 and opcodes[oi - 1][0] == "equal") else 0
    right_eq = (opcodes[oi + 1][2] - opcodes[oi + 1][1]) if (oi + 1 < len(opcodes) and opcodes[oi + 1][0] == "equal") else 0
    if min(left_eq, right_eq) < 3 or (left_eq + right_eq) < 7:
      continue
    # Ignore legitimate orthography/nasal/geminate variants (`ँ`/`ं`, `छ`/`च्छ`, `स`/`श`/`ष` sandhi, `म`/`न`)
    if _is_legitimate_orth_diff(a_seg, b_seg):
      continue
    if a_seg in ("ँ", "ं", "म्", "न्", "त्", "द्", "स्", "ः", "च्") and b_seg in ("ँ", "ं", "म्", "न्", "त्", "द्", "स्", "ः", "च्", ""):
      continue
    # Never delete/insert a full syllable or grammatical case ending unless it's a verified OCR pair or impossible combo
    ctx_s = s_flat[max(0, i1 - 3) : min(len(s_flat), i2 + 3)]
    ctx_v = v_flat[max(0, j1 - 3) : min(len(v_flat), j2 + 3)]
    if _IMPOSSIBLE_DEVA_RE.search(ctx_v):
      continue

    is_impossible = bool(_IMPOSSIBLE_DEVA_RE.search(ctx_s))
    is_ocr_pair = (a_seg, b_seg) in _SCHROEDER_OCR_PAIRS
    if not is_impossible and not is_ocr_pair:
      continue

    # Map flat indices `[i1, i2)` back to indices in `work`
    if i1 < i2:
      orig_lo = s_map[i1]
      orig_hi = s_map[i2 - 1] + 1
    else:
      # Pure insertion (`"" -> "र्"` or `"" -> "्र"` or `"" -> "्य"`): insert right before `s_map[i1]`
      orig_lo = s_map[i1] if i1 < len(s_map) else len(work)
      orig_hi = orig_lo
      # Special case: `त्वोजे᳓` -> `त्वोर्जे᳓` inserts `र्` BEFORE `ज` (`orig_lo` is `ज`)!
      # Special case: `द᳙प्सो᳙` -> `द्र᳙प्सो᳙` inserts `्र` AFTER `द` and BEFORE any accent `᳙`!
      if b_seg in ("्र", "्य") and i1 > 0:
        prev_c = s_map[i1 - 1]
        orig_lo = prev_c + 1
        orig_hi = orig_lo

    # Do NOT touch `work` if the Schroeder word is ALREADY a valid known Sanskrit word in `lex`
    # (unless impossible Devanagari combo like `पृथिव्यृसि` or `व्यृोमा`!)
    if not is_impossible and lex is not None:
      s_word = _extract_word_around(work, orig_lo, orig_hi)
      s_word_bare = _ALL_ACC_RE.sub("", s_word).replace("ऽ", "")
      slp_s = _deva_to_slp(s_word_bare)
      if slp_s and lex.word_score_slp(slp_s) > 0:
        continue

    # Ensure we don't drop US accent marks sitting between `orig_lo` and `orig_hi`!
    deleted_slice = work[orig_lo:orig_hi]
    preserved_acc = "".join(ch for ch in deleted_slice if ch in (US_UDATTA, US_SVARITA))
    rep_str = b_seg + preserved_acc if (preserved_acc and b_seg) else (b_seg if b_seg else preserved_acc)

    old_w = _extract_word_around(work, orig_lo, orig_hi)
    edits.append((orig_lo, orig_hi, rep_str, old_w, f"{a_seg}→{b_seg}"))

  if not edits:
    return work, pre_repairs

  # Apply non-overlapping edits from right to left
  edits.sort(key=lambda e: (e[0], e[1]))
  filtered: list[tuple[int, int, str, str, str]] = []
  for ed in edits:
    if filtered and ed[0] < filtered[-1][1]:
      continue
    filtered.append(ed)

  out_chars = work
  repairs: list[tuple[str, str]] = []
  for lo, hi, rep, old_w, tag_s in reversed(filtered):
    out_chars = out_chars[:lo] + rep + out_chars[hi:]
    repairs.append((old_w, tag_s))
  repairs.reverse()
  return out_chars, pre_repairs + repairs


def parse_ks_anuvaka(
  file_path: str,
  schroeder_root: str,
  *,
  lex: UnifiedVedicLexicon | None = None,
  visvara_dir: str = DEFAULT_KS_VISVARA_DIR,
  ashvamedha_dir: str = DEFAULT_KS_ASHVAMEDHA_DIR,
) -> KsAnuvakaSource:
  """Parse a single KS Schroeder anuvāka file and repair OCR typos against ``visvara-saMhitA``."""
  rel_path = os.path.relpath(file_path, schroeder_root).replace("\\", "/")
  parts = rel_path.split("/")
  part_dir = parts[0] if len(parts) >= 3 else ""
  sthanaka_dir = parts[1] if len(parts) >= 3 else ""
  sth_m = re.match(r"^(\d+)", sthanaka_dir)
  sthanaka_num = int(sth_m.group(1)) if sth_m else 0
  anu_base = os.path.splitext(parts[-1])[0]
  anu_m = re.match(r"^(\d+)", anu_base)
  anuvaka_num = int(anu_m.group(1)) if anu_m else 0

  txt = open(file_path, encoding="utf-8").read()
  title = to_dev_digits(f"{anuvaka_num:02d}")
  m_title = re.search(r'(?m)^title\s*=\s*"([^"]+)"', txt)
  if m_title:
    title = m_title.group(1).strip()

  body = txt.split("+++", 2)[2] if txt.startswith("+++") and txt.count("+++") >= 2 else txt

  # 1. Extract `<details><summary>टिप्पणी...</summary>...</details>` blocks
  unnumbered_notes: list[str] = []
  def _grab_tippani(m: re.Match) -> str:
    hdr = m.group(1).strip()
    inner = m.group(2).strip()
    if inner:
      unnumbered_notes.append(f"**{hdr}**\n\n{inner}")
    return ""
  body = _UNNUM_DETAILS_RE.sub(_grab_tippani, body)

  # 2. Extract markdown footnote definitions `[^id]: ...`
  footnote_defs: dict[str, str] = {}
  def _grab_fn_def(m: re.Match) -> str:
    footnote_defs[m.group(1).strip()] = m.group(2).strip()
    return ""
  body = _FOOTNOTE_DEF_RE.sub(_grab_fn_def, body)

  # 3. Extract trailing `cf. Mâitr. S. ...; Kap. S. ...` cross-reference lines
  cf_notes: list[str] = []
  cleaned_lines: list[str] = []
  for ln in body.splitlines():
    m_cf = _CF_TAIL_RE.search(ln)
    if m_cf:
      cf_notes.append(m_cf.group(0).strip())
      ln = ln[: m_cf.start()].rstrip()
    # Also catch standalone `cf. ...` lines
    if re.match(r"^\s*(?:cfr?\.|cf\b)\s+", ln):
      cf_notes.append(ln.strip())
      continue
    cleaned_lines.append(ln)
  main_body = "\n".join(cleaned_lines).strip()

  # 4. Split main_body into alternating non-bold and `**bold**` pieces!
  # Collapse inline empty bold toggles (`** **`, horizontal spaces ONLY — never across `\n` between separate bold ṛks!)
  main_body = re.sub(r"\*\*[ \t]+\*\*", " ", main_body)
  # Handle multi-line `**...**` spans cleanly.
  raw_segments: list[tuple[str, bool]] = []
  bold_re = re.compile(r"\*\*(.+?)\*\*", re.S)
  pos = 0
  for m_b in bold_re.finditer(main_body):
    pre = main_body[pos : m_b.start()].strip()
    if pre:
      raw_segments.append((pre, False))
    b_txt = m_b.group(1).strip()
    if b_txt:
      raw_segments.append((b_txt, True))
    pos = m_b.end()
  tail = main_body[pos:].strip()
  if tail:
    raw_segments.append((tail, False))

  # 5. Load matching visvara anuvāka text for OCR repair
  vis_map = load_ks_visvara_anuvakas(
    part_dir, sthanaka_num, visvara_dir=visvara_dir, ashvamedha_dir=ashvamedha_dir
  )
  vis_text = vis_map.get(anuvaka_num, "")
  # If exact number didn't match well, probe adjacent anuvāka ±1 by character overlap
  full_bare = re.sub(r"[^\u0900-\u0963\u0971-\u097f]", "", _ALL_ACC_RE.sub("", main_body))
  visvara_matched = False
  if full_bare and vis_map:
    best_v = ""
    best_r = 0.0
    probe_nums = [anuvaka_num] + [
      anuvaka_num + d for d in (-1, 1, -2, 2) if (anuvaka_num + d) in vis_map
    ]
    for pn in probe_nums:
      vt = vis_map.get(pn, "")
      if not vt:
        continue
      vb = re.sub(r"[^\u0900-\u0963\u0971-\u097f]", "", vt)
      r = difflib.SequenceMatcher(None, full_bare[:400], vb[:400]).ratio()
      if r > best_r:
        best_r = r
        best_v = vt
    if best_r >= 0.55:
      vis_text = best_v
      visvara_matched = True
    else:
      vis_text = ""

  # 6. Build KsSpanPiece list, stripping `[^id]` from text while recording their IDs
  pieces: list[KsSpanPiece] = []
  total_words = 0
  accented_words = 0
  for seg_txt, is_bold in raw_segments:
    fn_ids = _FOOTNOTE_REF_RE.findall(seg_txt)
    mula_clean = _FOOTNOTE_REF_RE.sub("", seg_txt)
    # Strip trailing anuvāka number `॥१॥` / `॥ ॥१॥` cleanly for splitting
    mula_clean = re.sub(r"[ \t]+", " ", mula_clean).strip()
    if not mula_clean:
      continue
    repaired, repairs = repair_ks_text_with_visvara(
      mula_clean, vis_text if visvara_matched else "", lex=lex
    )
    toks = _DEVA_TOKEN_RE.findall(mula_clean)
    total_words += len(toks)
    accented_words += sum(1 for t in toks if has_us_accents(t))
    pieces.append(
      KsSpanPiece(
        raw_mula=mula_clean,
        repaired_vp=repaired,
        is_bold_rk=is_bold,
        footnote_ids=fn_ids,
        ocr_repairs=repairs,
      )
    )

  cov = (accented_words / total_words) if total_words > 0 else 0.0
  return KsAnuvakaSource(
    rel_path=rel_path,
    part_dir=part_dir,
    sthanaka_dir=sthanaka_dir,
    sthanaka_num=sthanaka_num,
    anuvaka_num=anuvaka_num,
    title=title,
    pieces=pieces,
    footnote_defs=footnote_defs,
    unnumbered_notes=unnumbered_notes,
    cf_notes=cf_notes,
    has_accents=(accented_words > 0),
    accent_coverage=cov,
    visvara_matched=visvara_matched,
  )
