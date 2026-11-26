"""Commentary prose cleanup helpers for VS-K editions."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
import pathlib
import re
import threading
import time
from typing import Callable, Sequence

from doc_curation.md.content_processor.details.common import (
  _SUMMARY_RE,
  parse_top_level_details,
)
from doc_curation.sanskrit import hyphenator
from doc_curation.sanskrit.accent.provenance import normalize_panini_abbreviations
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import (
  VSK_SARVA_PRASTUTI_DIR,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina.samhitaa import bhashya_aligner

CANONICAL_KANVA_SAYANA_SUMMARY = "सायण-टीका (काण्वी)"

_COMM_BLK_RE = re.compile(
  r"(<details><summary>(?:सायण|आनन्दबोध|अनन्ताचार्य)[^<]*</summary>\s*)(.*?)(\s*</details>\n?)",
  flags=re.S,
)
_ORDINALS_DASH_RE = re.compile(
  r"(?:प्रथमा|द्वितीया|तृतीया|चतुर्थी|पञ्चमी|षष्ठी|सप्तमी|अष्टमी|नवमी|दशमी|एकादशी|द्वादशी)-[ \t]*\n"
)
_SA_PREFIX_RE = re.compile(
  r"^(?:[<\"'‘\s]*(?:सा|आ|अ)\s*[-–—:]+\s*)+|^['‘\"\s]*सा\s+(?=अथ|कात्यायन)"
)
_COLOPHON_RE = re.compile(
  r"(?:^|\n)\s*इति\s+[^।॥]{0,80}(?:अध्याय|ऽध्याय|अनुवाक|ऽनुवाक|काण्ड)[^।॥]*(?:।|॥\s*(?:[०-९]+\s*॥)?)\s*$"
)
_TERM_END_RE = re.compile(r"(?:[।॥?!]|(?:[।॥][\"'”’)\s०-९]*))$")
_ITEM_OUT_RE = re.compile(r"<<<ITEM (-?\d+)>>>\s*(.*?)\s*<<<END \1>>>", flags=re.S)
_STAR_SEP_RE = re.compile(r"^(?:\*\s*\*\s*\*|\*\*\*)$")
_UVATA_PAREN_FN_RE = re.compile(
  r"(?<=[\u0900-\u097f])\([०-९]\)(?=[\u0900-\u097f\s।॥,])|(?<=[\u0900-\u097f]\s)\([०-९]\)(?=[\u0900-\u097f])"
)

_KANVI_PROOFREAD_EXTRA = (
  "The input provides `[REF_MANTRA]` ONLY as read-only reference context to clarify garbled OCR words "
  "in `[COMMENTARY]`; output ONLY the proofread commentary body without repeating `[REF_MANTRA]`. "
  "NEVER insert, prepend, or copy new mantra lines/quotes from `[REF_MANTRA]` that were not already in `[COMMENTARY]`. "
  "`[REF_MANTRA]` may come from a related Vedic śākhā (e.g., RV/AV vs VS-K), so NEVER overwrite valid Kāṇva śākhā readings "
  "(such as `सु । आयुः`, `स्वायुः`) to force-match another śākhā. Only fix unmistakable OCR/typo errors inside `[[OLD|NEW]]` "
  "and NEVER make stylistic paraphrases of valid words (e.g. keep `आदाव् उत्पन्नम्`, `अग्नि-प्रणयनम्`, `रुक्म-स्वरूपं` rather than changing stems). "
  "NEVER delete parenthetical words/glosses like `(देव)` (so never emit empty replacements like `[[(देव)|]]`). "
  "A lone Devanāgarī digit `१` between Sanskrit words (e.g., `यूपदेवः १ यष्टृ-देवः`) is an OCR misread of daṇḍa `।` — fix it as `[[१|।]]`, NOT `[[??]]`; reserve `[[??]]` strictly for genuinely illegible gibberish. "
  "For multiple `<<<ITEM id>>>` inputs, return each identically wrapped as `<<<ITEM id>>>\\n<body/>\\n<<<END id>>>`. "
  "Keep compact quoted padapāṭha lines compact (multiple short `।`-ended words per line), and keep trailing verse numbers (`॥ ४६ ॥`) attached to the verse line cleanly. "
  "Group related commentary sentences into continuous multi-sentence paragraphs using ONLY two trailing spaces + single newline (`  \\n`) between consecutive sentences; NEVER put blank lines (`\\n\\n`) between every sentence! Use `\\n\\n` ONLY around `>` blockquotes, `[...]` section headings, colophons, or genuine major topic shifts (after multi-sentence paragraphs). "
  "Strip any leftover leading OCR speaker label `सा -` or standalone prefix `सा ` (e.g., before `अथ` or `कात्यायनः`) cleanly. "
  "Keep standard vedic commentary abbreviations such as `काश्रौ`, `तैसं`, `तैब्रा`, `शत` verbatim unless clearly OCR-garbled (e.g., `काश्रौ १८०४ - १` -> `[[काश्रौ १८०४ - १|काश्रौ १८.४.१]]`). "
  "Always return the COMPLETE commentary block without truncation."
)


def strip_pune_margin_numbers(text: str) -> str:
  """Remove VSM Pune line-margin numbers (`५/१०/१५/२०/२५/३०`) and OCR apparatus/header noise in commentary."""
  t = (
    text.replace("\u200d", "")
    .replace("\\!", "!")
    .replace("\\~", "~")
    .replace("*'*", "'")
    .replace("*\"*", "\"")
  )
  t = re.sub(r"\*([०-९0-9.,;:'\"?!()\[\]]+)\*", r"\1", t)
  t = re.sub(r"\(\s*L\.\s*\d+\s*\)", "", t)
  t = re.sub(
    r"(?m)^\s*(?:<<|>>|°|\*\"\*|\"\*|\(\s*\(\)|"
    r"[-–—.]*\s*[०-९]{1,4}[-–—.,;:•]*|[-–—.]*\s*[0-9]{1,4}\s*[-–—.,;:•)]*|"
    r"[०-९0-9]+\s*[-–]\s*[०-९0-9]+\.?|"
    r"['‘\"“\*]?\s*का[णण्]्?[व्य]?\s*[-–\s]*संहिता(?:\s*(?:भा[ष्यप]संग्रहः?|[।॥०-९\[\]\-]))*|"
    r"का[णण्]्?व[-–\s]*संहिता[-–\s]*भा[ष्यप]संग्रहः?.*|"
    r"कासं[\s.…]*[०-९]+|"
    r"[>\s]*['‘\"\*]?\s*(?:सायणाचार्य|आनन्द-?बोध)[^\n]*(?:[भम]ा[ष्यपध्यन्यव्य]+|[सन]मेता|प्रणीतः).*|"
    r"(?:\[\s*[०-९/]+\s*\]\s*[।॥\s०-९]*)?[^\n\[]*अध्याय[ः:]?\s*\]\s*\.?|"
    r"for\s+['‘\"][^'\n]+;\s*[A-Z]\d.*|"
    r"[क-ह]|"
    r"[^अ-ह॥०-९\n]+)\s*$\n?",
    "",
    t,
  )
  # Strip line-leading left-margin VSM line numbers (e.g. `१० ' इमं मे` or `१५ हविरुद्वपति`)
  t = re.sub(r"(?m)^(?:५|१०|१५|२०|२५|३०)[ \t]+(?=['‘\"“अ-ह])", "", t)
  # Rejoin Devanagari words hyphen-split across a margin line number (`कण्वा- १५ भिमतो`, `सोमक्रयणी - २० मित्य्-अर्थः`)
  t = re.sub(
    r"(?<=[\u0900-\u097f])[ \t]*-[ \t\n]+(?:५|१०|१५|२०|२५|३०)[ \t\n]+(?=[\u0900-\u097f])",
    "",
    t,
  )
  # Drop standalone margin line numbers flanked by spaces/prose (preserving `॥ १५ ॥`, `(५)`, `१.५`)
  t = re.sub(
    r"(?<![॥(\[\d.\-])(?:[ \t]+(?:५|१०|१५|२०|२५|३०))(?=(?:[ \t]+\.(?=\s*\()|[ \t]+(?![॥.)\d])))",
    "",
    t,
  )
  return re.sub(r"\n{3,}", "\n\n", t)


def clean_raw_bhashya_text(text: str, *, hyphenate: bool = True) -> str:
  """Clean OCR/editorial artifacts from extracted commentary prose and optionally hyphenate Sanskrit."""
  t = text.strip()
  if not t:
    return ""
  t = re.sub(r"^(?:[<\"'‘\s]*(?:सा|आ|अ)\s*[-–—:]+\s*)+", "", t)
  t = re.sub(r"\[?\s*[-–—]?\s*अ[०॰]\s*[०-९।|.\-\s]+\]?", " ", t)
  t = re.sub(r"\|\|", "॥", t)
  t = re.sub(r"(?<!\|)\|(?!\|)", "।", t)
  t = re.sub(r"(?<=[\u0900-\u097f])-\s*\n\s*(?=[\u0900-\u097f])", "", t)
  t = strip_pune_margin_numbers(t)
  t = bhashya_aligner.clean_commentary_boilerplate(t)
  if not t:
    return ""
  t = re.sub(r"[ \t]+", " ", t)
  if hyphenate:
    t = hyphenator.hyphene(t, clause_newlines=False)
  return normalize_panini_abbreviations(t)


def _clean_commentary_block(m: re.Match, counters: dict[str, int]) -> str:
  head, body, tail = m.group(1), m.group(2), m.group(3)
  cleaned = strip_pune_margin_numbers(body).strip()
  cleaned = re.sub(r"[ \t]{2,}(?=\S)", " ", cleaned)
  if not cleaned:
    counters["blocks_changed"] += 1
    return ""
  if cleaned != body.strip():
    counters["blocks_changed"] += 1
    if re.search(r"-[ \t\n]+(?:५|१०|१५|२०|२५|३०)[ \t\n]+", body):
      cleaned = "\n".join(
        hyphenator.hyphene(ln, clause_newlines=False) if ln.strip() else ln
        for ln in cleaned.splitlines()
      )
  return f"{head}{cleaned}{tail}"


def clean_vsk_commentary_blocks_in_dir(sarva_dir: pathlib.Path = VSK_SARVA_PRASTUTI_DIR) -> dict[str, int]:
  """Post-clean `सायण`/`आनन्दबोध`/`अनन्ताचार्य` commentary blocks (margin digits & escapes) without touching `मूलम्`/VP."""
  counters = {"files_changed": 0, "blocks_changed": 0}
  for p in sorted(sarva_dir.glob("[0-9][0-9].md")):
    txt = p.read_text(encoding="utf-8")
    new_txt = _COMM_BLK_RE.sub(lambda m: _clean_commentary_block(m, counters), txt)
    new_txt = re.sub(r"<details><summary>सर्वा अवतारिकाः</summary>\s*</details>\n?", "", new_txt)
    if new_txt != txt:
      p.write_text(new_txt, encoding="utf-8")
      counters["files_changed"] += 1
  return counters


def _normalize_inner_lines(chunk: str) -> str:
  """Collapse broken mid-sentence newlines while keeping sentence soft breaks (`  \\n`)."""
  stripped = chunk.lstrip()
  if stripped.startswith(">") or re.match(r"^\[[^\n\]]+\]$", stripped):
    return chunk.strip()
  lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
  out: list[str] = []
  for ln in lines:
    if out and not re.search(r"[।॥?!—:]$", out[-1]):
      out[-1] = f"{out[-1]} {ln}"
    elif out:
      out[-1] = f"{out[-1]}  "
      out.append(ln)
    else:
      out.append(ln)
  return "\n".join(out)


def _collapse_fake_paragraphs(text: str) -> str:
  """Collapse per-sentence `\\n\\n` splits into Markdown soft breaks and compact padapāṭha runs."""
  # Isolate `[ ... ]` section/anuvāka bracket headers so they stay distinct paragraphs.
  isolated = re.sub(r"(?m)^(\[[^\n\]]+\])[ \t]*\n(?=\S)", r"\1\n\n", text)
  chunks = [c.strip() for c in re.split(r"\n\s*\n+", isolated) if c.strip()]
  if not chunks:
    return ""
  chunks = [_normalize_inner_lines(c) for c in chunks]

  is_header = lambda c: bool(re.match(r"^\[[^\n\]]+\]$", c) or _STAR_SEP_RE.match(c))
  is_quote = lambda c: c.lstrip().startswith(">")
  is_colophon = lambda c: bool(_COLOPHON_RE.search(c))
  is_short_pada = lambda c: len(c) <= 28 and "\n" not in c and c.endswith("।")

  grouped: list[tuple[str, str]] = []
  i = 0
  while i < len(chunks):
    if is_short_pada(chunks[i]):
      j = i
      while j < len(chunks) and is_short_pada(chunks[j]):
        j += 1
      if j - i >= 3:
        grouped.append(("PADA", " ".join(chunks[i:j])))
        i = j
        continue
    grouped.append(("NORM", chunks[i]))
    i += 1

  out: list[str] = []
  for idx, (kind, chk) in enumerate(grouped):
    if idx == 0:
      out.append(chk)
      continue
    prev_kind, prev = grouped[idx - 1]
    if is_header(chk) or is_header(prev) or is_quote(chk) or is_quote(prev) or is_colophon(prev):
      out.append(f"\n\n{chk}")
    elif prev_kind == "PADA" or kind == "PADA" or _TERM_END_RE.search(prev):
      out.append(f"  \n{chk}")
    else:
      out.append(f" {chk}")
  return "".join(out)


def clean_prose_block(body: str, *, mode: str = "vsk") -> str:
  """Normalize OCR artifacts, visarga colons, and fake paragraph separations across commentary modes."""
  t = body.replace("\r\n", "\n").replace("\u200d", "").strip()
  if not t:
    return ""
  t = re.sub(r"(?m)^[ \t]*:[ \t]*", "", t)
  t = re.sub(r"(?<=ः)[ \t]*:(?:[ \t]*:)*", "", t)
  t = re.sub(r"(?<=[\u0900-\u097f])[ \t]*:(?:[ \t]*:)*", "ः", t)
  if mode in ("uvata", "mahidhara"):
    # Fix OCR virama+ā-mātrā ligature loss (e.g. `आज्यम्ाज्यशब्देन` -> `आज्यम् । आज्यशब्देन`)
    t = re.sub(r"(?<=[\u0900-\u097f]्)ा", " । आ", t)
    t = re.sub(r"।\s+।", "।", t)
    if mode == "uvata":
      t = _UVATA_PAREN_FN_RE.sub("", t)
      t = re.sub(r"^(?:उ[०॰।.]+\s*)+", "", t.lstrip())
    else:
      t = re.sub(r"^(?:मा?[०॰।.]+\s*)+", "", t.lstrip())
  else:
    t = strip_pune_margin_numbers(t)
    t = _SA_PREFIX_RE.sub("", t.lstrip())
    t = _ORDINALS_DASH_RE.sub(lambda m: m.group(0).replace("-\n", " —\n").replace("- \n", " —\n"), t)
    t = re.sub(r"(?<=[\u0900-\u097f])-[ \t]*\n[ \t]*(?=[\u0900-\u097f])", "-", t)
    t = re.sub(r"(?m)^(?:[<\"'‘\s]*(?:सा|आ|अ)\s*[-–—:]+\s*)+", "", t)
    t = re.sub(r"(?m)^\[(?=\s*इति\s+[^\]\n]+(?:अध्याय|ऽध्याय|अनुवाक))", "", t)
  return normalize_panini_abbreviations(_collapse_fake_paragraphs(t).strip())


def clean_kanva_sayana_block(body: str) -> str:
  """Normalize OCR artifacts, visarga colons, and fake paragraph separations inside Kāṇva Sāyaṇa blocks."""
  return clean_prose_block(body, mode="vsk")


def extract_reference_mantra(content: str, *, max_chars: int = 800) -> str:
  """Extract non-included `मूलम् - काण्वम्` / `विश्वास-प्रस्तुतिः` / `मूलम्` text as read-only context."""
  kanva_parts: list[str] = []
  other_parts: list[str] = []

  def _walk(segment: str) -> None:
    for _, _, title, body in parse_top_level_details(segment, skip_js_includes=True):
      if "काण्व" in title and (title.startswith("मूलम्") or title.startswith("पदपाठः")):
        plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()
        if plain:
          kanva_parts.append(plain)
      elif title.startswith("विश्वास-प्रस्तुतिः") or title.startswith("मूलम्"):
        plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()
        if plain:
          other_parts.append(plain)
      elif "<details" in body:
        _walk(body)

  _walk(content)
  preferred = kanva_parts if kanva_parts else other_parts
  joined = "\n".join(dict.fromkeys(preferred))
  return joined[:max_chars].strip()


def transform_canonical_kanva_sayana_in_text(
  content: str,
  transform_fn: Callable[[str, str], str],
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
) -> tuple[str, int]:
  """Apply ``transform_fn(body, ref_mantra)`` to every non-included canonical ``summary_title`` block."""
  file_ref_mantra = extract_reference_mantra(content)
  changed = 0

  def _walk(segment: str, active_ref: str) -> str:
    nonlocal changed
    spans = parse_top_level_details(segment, skip_js_includes=True)
    if not spans:
      return segment
    pieces: list[str] = []
    cursor = 0
    prev_mantra_blk = ""
    for idx, (start, end, title, body) in enumerate(spans):
      pieces.append(segment[cursor:start])
      blk = segment[start:end]
      m_sum = _SUMMARY_RE.search(blk)
      close_idx = blk.rfind("</details>")
      if m_sum is None or close_idx == -1:
        pieces.append(blk)
      elif title == summary_title:
        new_body = transform_fn(body, active_ref).strip()
        if new_body != body.strip():
          changed += 1
        head = blk[: m_sum.end()]
        pieces.append(f"{head}\n\n{new_body}\n</details>")
      elif summary_title in body:
        # Prefixed `सर्वा अवतारिकाः` blocks precede their mantra; commentary `सर्वाष् टीकाः` follow it.
        next_mantra_blk = ""
        if title == "सर्वा अवतारिकाः" or title.endswith(("विनियोगः", "अवतारिका")):
          for nxt_s, nxt_e, nxt_title, _ in spans[idx + 1 :]:
            if nxt_title.startswith("विश्वास-प्रस्तुतिः") or nxt_title.startswith("मूलम्"):
              next_mantra_blk = segment[nxt_s:nxt_e]
              break
        anchor_blk = next_mantra_blk or prev_mantra_blk
        local_ctx = f"{anchor_blk}\n{blk}" if anchor_blk else blk
        local_ref = extract_reference_mantra(local_ctx) or active_ref
        inner_raw = blk[m_sum.end() : close_idx]
        lead_ws = inner_raw[: len(inner_raw) - len(inner_raw.lstrip())]
        trail_ws = inner_raw[len(inner_raw.rstrip()) :]
        updated_sub = _walk(body, local_ref)
        pieces.append(f"{blk[: m_sum.end()]}{lead_ws}{updated_sub}{trail_ws}</details>")
      else:
        pieces.append(blk)
      if title.startswith("विश्वास-प्रस्तुतिः") or title.startswith("मूलम्"):
        prev_mantra_blk = blk
      cursor = end
    pieces.append(segment[cursor:])
    return "".join(pieces)

  updated = _walk(content, file_ref_mantra)
  assert updated.count("<details") == updated.count("</details>"), "Unbalanced <details> tags after update"
  return updated, changed


def clean_canonical_kanva_sayana_in_roots(
  roots: Sequence[pathlib.Path],
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
  mode: str = "vsk",
) -> dict[str, int]:
  """Deterministically clean fake paragraphs & noise across all non-included ``summary_title`` blocks."""
  counters = {"files_scanned": 0, "files_changed": 0, "blocks_changed": 0, "blocks_seen": 0}

  def _clean(body: str, _ref: str) -> str:
    counters["blocks_seen"] += 1
    return clean_prose_block(body, mode=mode)

  for root in roots:
    root_p = pathlib.Path(root)
    if not root_p.exists():
      continue
    for p in sorted(root_p.rglob("*.md")):
      if not p.is_file():
        continue
      txt = p.read_text(encoding="utf-8")
      if summary_title not in txt:
        continue
      counters["files_scanned"] += 1
      updated, n_changed = transform_canonical_kanva_sayana_in_text(txt, _clean, summary_title=summary_title)
      counters["blocks_changed"] += n_changed
      if updated != txt:
        p.write_text(updated, encoding="utf-8")
        counters["files_changed"] += 1
  return counters


SCOPE_BHASHYA_SUMMARIES = frozenset({
  "सायण-टीका (काण्वी)",
  "सायणः - विनियोगः",
  "सायणः - अवतारिका",
  "आनन्दबोध-टीका",
  "आनन्दबोधः - विनियोगः",
  "आनन्दबोधः - अवतारिका",
  "उवट-टीका",
  "उवटः - विनियोगः",
  "उवटः - अवतारिका",
  "महीधर-टीका",
  "महीधरः - विनियोगः",
  "महीधरः - अवतारिका",
})


def normalize_abbreviations_in_canonical_blocks(
  content: str,
  summary_titles: frozenset[str] | set[str] | Sequence[str] = SCOPE_BHASHYA_SUMMARIES,
) -> tuple[str, int]:
  """Convert Devanagari ``०`` (U+0966) abbreviation signs to ``॰`` (U+0970) inside canonical blocks."""
  target_set = set(summary_titles)
  blocks_changed = 0

  def _walk(segment: str) -> str:
    nonlocal blocks_changed
    spans = parse_top_level_details(segment, skip_js_includes=True)
    if not spans:
      return segment
    pieces: list[str] = []
    cursor = 0
    for start, end, title, body in spans:
      pieces.append(segment[cursor:start])
      blk = segment[start:end]
      m_sum = _SUMMARY_RE.search(blk)
      close_idx = blk.rfind("</details>")
      if m_sum is None or close_idx == -1:
        pieces.append(blk)
      elif title in target_set:
        inner_raw = blk[m_sum.end() : close_idx]
        new_inner = normalize_panini_abbreviations(inner_raw)
        if new_inner != inner_raw:
          blocks_changed += 1
        pieces.append(f"{blk[: m_sum.end()]}{new_inner}</details>")
      elif any(t in body for t in target_set):
        inner_raw = blk[m_sum.end() : close_idx]
        lead_ws = inner_raw[: len(inner_raw) - len(inner_raw.lstrip())]
        trail_ws = inner_raw[len(inner_raw.rstrip()) :]
        updated_sub = _walk(body)
        pieces.append(f"{blk[: m_sum.end()]}{lead_ws}{updated_sub}{trail_ws}</details>")
      else:
        pieces.append(blk)
      cursor = end
    pieces.append(segment[cursor:])
    return "".join(pieces)

  updated = _walk(content)
  assert updated.count("<details") == updated.count("</details>"), "Unbalanced <details> tags after update"
  return updated, blocks_changed


def normalize_abbreviations_in_roots(
  roots: Sequence[pathlib.Path],
  *,
  summary_titles: frozenset[str] | set[str] | Sequence[str] = SCOPE_BHASHYA_SUMMARIES,
  um_dirs: Sequence[pathlib.Path] = (),
  dry_run: bool = False,
) -> dict[str, object]:
  """Normalize ``०`` -> ``॰`` across non-included ``summary_titles`` blocks and ``uvaTa-mahIdharau`` dirs."""
  target_set = set(summary_titles)
  changed_paths: list[str] = []
  blocks_changed = 0
  files_scanned = 0

  for root in roots:
    root_p = pathlib.Path(root)
    if not root_p.exists():
      continue
    for p in sorted(root_p.rglob("*.md")):
      if not p.is_file():
        continue
      txt = p.read_text(encoding="utf-8")
      if "\u0966" not in txt or not any(t in txt for t in target_set):
        continue
      files_scanned += 1
      updated, n_blk = normalize_abbreviations_in_canonical_blocks(txt, target_set)
      blocks_changed += n_blk
      if updated != txt:
        changed_paths.append(str(p))
        if not dry_run:
          p.write_text(updated, encoding="utf-8")

  for um_dir in um_dirs:
    um_p = pathlib.Path(um_dir)
    if not um_p.exists():
      continue
    for p in sorted(um_p.glob("[0-9][0-9].md")):
      if not p.is_file():
        continue
      txt = p.read_text(encoding="utf-8")
      if "\u0966" not in txt:
        continue
      files_scanned += 1
      m_fm = re.match(r"^(\+\+\+\n.*?\n\+\+\+\s*\n+)(.*)$", txt, flags=re.S)
      updated = f"{m_fm.group(1)}{normalize_panini_abbreviations(m_fm.group(2))}" if m_fm else normalize_panini_abbreviations(txt)
      if updated != txt:
        changed_paths.append(str(p))
        if not dry_run:
          p.write_text(updated, encoding="utf-8")

  return {
    "files_scanned": files_scanned,
    "files_changed": len(changed_paths),
    "blocks_changed": blocks_changed,
    "changed_paths": changed_paths,
  }


def _load_working_gemini_clients(
  model_id: str,
  thinking_level: str,
  *,
  key_paths: Sequence[str] | None = None,
) -> list[tuple[str, object]]:
  """Instantiate Gemini GenAI clients without wasting quota on dummy health pings."""
  import tomllib
  from doc_curation.llm.gemini import keys as gkeys

  if key_paths is None:
    data = tomllib.loads(pathlib.Path(gkeys._DEFAULT_TOKENS_PATH).read_text(encoding="utf-8"))
    candidates = [f"gemini.{k}" for k in data.get("gemini", {})] + [
      f"gemini_friends.{k}" for k in data.get("gemini_friends", {})
    ]
  else:
    candidates = list(key_paths)

  clients: list[tuple[str, object]] = []
  for kp in candidates:
    try:
      clients.append((kp, gkeys.get_client(kp)))
    except Exception as exc:
      logging.warning("Skipping key %s during client init: %s", kp, exc)
  return clients


def _collect_kanva_sayana_targets(
  roots: Sequence[pathlib.Path],
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
) -> list[dict]:
  """Collect deterministic target descriptors for all non-included ``summary_title`` blocks."""
  targets: list[dict] = []
  for root in roots:
    for p in sorted(pathlib.Path(root).rglob("*.md")):
      if not p.is_file():
        continue
      txt = p.read_text(encoding="utf-8")
      if summary_title not in txt:
        continue
      idx_in_file = 0

      def _collect(body: str, ref: str) -> str:
        nonlocal idx_in_file
        targets.append(
          {
            "id": len(targets),
            "path": p,
            "idx_in_file": idx_in_file,
            "raw": body,
            "ref_mantra": ref,
          }
        )
        idx_in_file += 1
        return body

      transform_canonical_kanva_sayana_in_text(txt, _collect, summary_title=summary_title)
  return targets


def _load_checkpoint_records(checkpoint_path: pathlib.Path | None) -> dict[int, str]:
  """Read saved `{id, proofread}` JSONL checkpoint entries into a lookup dict."""
  done: dict[int, str] = {}
  if checkpoint_path and checkpoint_path.exists():
    for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
      if not line.strip():
        continue
      rec = json.loads(line)
      done[int(rec["id"])] = rec["proofread"]
  return done


def _collapse_relapsed_single_sentence_breaks(text: str) -> str:
  """Collapse runs of >=2 consecutive 1-sentence prose paragraphs back to soft breaks (`  \\n`)."""
  paras = [p.strip() for p in re.split(r"\n\s*\n+", text.strip()) if p.strip()]
  if len(paras) < 2:
    return text.strip()
  is_prose_line = (
    lambda p: not p.startswith(">")
    and not re.match(r"^\[(?!\[)", p)
    and not re.match(r"^[-*]\s", p)
    and not _COLOPHON_RE.search(p)
    and _TERM_END_RE.search(re.sub(r"\[\[[^|\[\]]*\|([^\[\]]*)\]\]", r"\1", p))
    and len(re.findall(r"[।॥?!]+", re.sub(r"\[\[[^|\[\]]*\|([^\[\]]*)\]\]", r"\1", p))) <= 1
  )
  out: list[str] = []
  i = 0
  while i < len(paras):
    if is_prose_line(paras[i]):
      j = i
      while j < len(paras) and is_prose_line(paras[j]):
        j += 1
      if j - i >= 2:
        out.append("  \n".join(paras[i:j]))
        i = j
        continue
    out.append(paras[i])
    i += 1
  return "\n\n".join(out)


def _postprocess_proofread_output(raw: str, raw_llm: str) -> str:
  """Apply deterministic Sanskrit post-guards and anti-blank-line normalization to LLM output."""
  from doc_curation.llm.proofreader import guards

  cleaned_llm = re.sub(r"^\s*\[(?:COMMENTARY|REF_MANTRA)\]\s*", "", raw_llm).replace("\u200d", "")
  guarded = guards.enforce_post_guards(raw, cleaned_llm, allow_suggestions=True).replace("\u200d", "")
  guarded = re.sub(r"\[\[([^\[\]|]+)\|\[\[([^|\[\]]+)\]\]\]\]", r"[[\1|\2]]", guarded)
  guarded = re.sub(r"\[\[([^\[\]|]+)\|\[\[([^\[\]|]+\|[^\[\]]+)\]\]\]\]", r"[[\2]]", guarded)
  guarded = re.sub(r"\[\[\|([^\[\]]+)\]\]", r"\1", guarded)
  guarded = re.sub(r"\[\[[\'\"‘“\*]+([^|\[\]]+)\|\1\]\]", r"\1", guarded)
  guarded = re.sub(
    r"\[\[[^\n|\]]*(?:आनन्द[- ]?बोध[- ]?भट्टोपाध्याय|का[णण्]्व[- ]?संहिता|कोण्यसंहिता|दनवसंहिता|भा[ष्यप]संग्रह|मा[ष्यध्य]समेता|त्रयस्त्रिशः|ब्रह्मसंबन्धिप्रयोगे)[^\n|\]]*\|\s*\]\]",
    "",
    guarded,
  )
  guarded = re.sub(r"\[\[\s*[०-९A-Za-z0-9\s'\"‘’“”*.,:;\-]+\s*\|\s*\]\]", "", guarded)
  guarded = re.sub(r"\[\[([^|\[\]]*[\u0900-\u097f][^|\[\]]*)\|\s*\]\]", r"\1", guarded)
  guarded = re.sub(
    r"\[\[([^|\[\]]+)\|([^|\[\]]+)\]\]",
    lambda m: m.group(2) if re.sub(r"[\s\-–—]+", "", m.group(1)) == re.sub(r"[\s\-–—]+", "", m.group(2)) else m.group(0),
    guarded,
  )
  sugg_bag: list[str] = []

  def _mask_sugg(m: re.Match[str]) -> str:
    sugg_bag.append(m.group(0))
    return f"\x00SUGG{len(sugg_bag) - 1}\x00"

  guarded_masked = re.sub(r"\[\[[^|\[\]]*\|[^|\[\]]*\]\]", _mask_sugg, guarded)
  guarded_masked = re.sub(r"([।॥])[ \t]*\|", r"\1", guarded_masked)
  guarded_masked = re.sub(r"\|[ \t]*([।॥])", r"\1", guarded_masked)
  guarded = re.sub(r"\x00SUGG(\d+)\x00", lambda m: sugg_bag[int(m.group(1))], guarded_masked)
  guarded = re.sub(r"(?m)^[ \t]*:[ \t]*", "", guarded)
  guarded = re.sub(r"।\s+।", "।", guarded)
  guarded = normalize_panini_abbreviations(_collapse_relapsed_single_sentence_breaks(guarded))
  return guarded.strip() or raw


def _apply_checkpoint_to_roots(
  targets: Sequence[dict],
  done: dict[int, str],
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
) -> tuple[int, int]:
  """Write completed `done` records back into non-included ``summary_title`` blocks."""
  by_file: dict[pathlib.Path, dict[int, str]] = {}
  for t in targets:
    if t["id"] in done:
      by_file.setdefault(t["path"], {})[t["idx_in_file"]] = done[t["id"]]

  files_changed = 0
  blocks_changed = 0
  for p, replacements in sorted(by_file.items()):
    txt = p.read_text(encoding="utf-8")
    cur_idx = 0

    def _apply(body: str, _ref: str) -> str:
      nonlocal cur_idx
      new_b = replacements.get(cur_idx, body)
      cur_idx += 1
      return new_b

    updated, n_changed = transform_canonical_kanva_sayana_in_text(txt, _apply, summary_title=summary_title)
    blocks_changed += n_changed
    if updated != txt:
      p.write_text(updated, encoding="utf-8")
      files_changed += 1
  return files_changed, blocks_changed


def proofread_canonical_kanva_sayana_in_roots(
  roots: Sequence[pathlib.Path],
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
  model_id: str = "gemini-3-flash-preview",
  thinking_level: str = "LOW",
  batch_size: int = 10,
  checkpoint_path: pathlib.Path | None = None,
  max_workers: int = 5,
  min_key_interval_sec: float = 10.0,
  timeout_ms: int = 60000,
) -> dict[str, int]:
  """Proofread & hyphenate non-included ``summary_title`` blocks with mantra context and post-guards."""
  from google.genai import types
  from doc_curation.llm.proofreader import build_system_prompt

  targets = _collect_kanva_sayana_targets(roots, summary_title=summary_title)
  done = _load_checkpoint_records(checkpoint_path)

  pending = [t for t in targets if t["id"] not in done]
  clients = _load_working_gemini_clients(model_id, thinking_level) if pending else []
  if pending and not clients:
    raise RuntimeError(f"No working Gemini API keys available for {model_id}")

  sys_prompt = build_system_prompt(
    clause_newlines=True,
    suggest_corrections=True,
    extra_instructions=_KANVI_PROOFREAD_EXTRA,
  )
  lock = threading.Lock()
  cooldown_until: dict[str, float] = {kp: 0.0 for kp, _ in clients}
  last_used: dict[str, float] = {kp: 0.0 for kp, _ in clients}

  def _next_client() -> tuple[str, object]:
    while True:
      now = time.monotonic()
      with lock:
        ready = [
          (last_used[kp], kp, cl)
          for kp, cl in clients
          if max(cooldown_until[kp], last_used[kp] + min_key_interval_sec) <= now
        ]
        if ready:
          ready.sort(key=lambda x: x[0])
          _, kp, cl = ready[0]
          last_used[kp] = now
          return kp, cl
        wait_until = min(max(cooldown_until[kp], last_used[kp] + min_key_interval_sec) for kp, _ in clients)
      time.sleep(min(5.0, max(0.2, wait_until - time.monotonic())))

  def _is_usable_output(raw: str, parsed_text: str) -> bool:
    if not parsed_text:
      return False
    return len(parsed_text) >= max(15, int(len(raw) * 0.45))

  def _save_records(recs: dict[int, str]) -> None:
    with lock:
      done.update(recs)
      if not checkpoint_path:
        return
      checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
      with checkpoint_path.open("a", encoding="utf-8") as fh:
        for tid, val in recs.items():
          fh.write(json.dumps({"id": tid, "proofread": val}, ensure_ascii=False) + "\n")

  def _run_batch(batch: list[dict]) -> dict[int, str]:
    prompt_parts = [
      "Proofread each delimited `<<<ITEM id>>>` commentary block using its `[REF_MANTRA]` only to clarify OCR corruptions.\n"
    ]
    by_id = {item["id"]: item for item in batch}
    for item in batch:
      prompt_parts.append(
        f"<<<ITEM {item['id']}>>>\n[REF_MANTRA]\n{item['ref_mantra']}\n\n[COMMENTARY]\n{item['raw']}\n<<<END {item['id']}>>>\n"
      )
    user_prompt = "\n".join(prompt_parts)
    max_attempts = max(48, len(clients) * 4)
    for attempt in range(max_attempts):
      kp, client = _next_client()
      try:
        resp = client.models.generate_content(
          model=model_id,
          contents=user_prompt,
          config=types.GenerateContentConfig(
            system_instruction=sys_prompt,
            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
            http_options=types.HttpOptions(timeout=timeout_ms),
          ),
        )
        parsed = {int(k): v.strip() for k, v in _ITEM_OUT_RE.findall(resp.text or "")}
        if all(tid in parsed and _is_usable_output(by_id[tid]["raw"], parsed[tid]) for tid in by_id):
          out = {tid: _postprocess_proofread_output(item["raw"], parsed[tid]) for tid, item in by_id.items()}
          _save_records(out)
          return out
        # Retry individual missing or truncated items if partial batch output occurred
        if len(batch) > 1:
          partial: dict[int, str] = {}
          for tid, item in by_id.items():
            if tid in parsed and _is_usable_output(item["raw"], parsed[tid]):
              partial[tid] = _postprocess_proofread_output(item["raw"], parsed[tid])
            else:
              partial.update(_run_batch([item]))
          _save_records(partial)
          return partial
      except Exception as exc:
        msg = str(exc).lower()
        now_err = time.monotonic()
        with lock:
          if "403" in msg or "permission_denied" in msg:
            cooldown_until[kp] = now_err + 86400.0
          elif "perday" in msg or "requests per day" in msg or "quotavalue': '20'" in msg or '"quotavalue": "20"' in msg:
            cooldown_until[kp] = now_err + 86400.0
          elif "429" in msg or "quota" in msg or "resource_exhausted" in msg:
            cooldown_until[kp] = now_err + 45.0
          else:
            cooldown_until[kp] = now_err + 10.0
          all_long_exhausted = all(cooldown_until[k] > now_err + 3600.0 for k, _ in clients)
        logging.warning("Key %s batch %s attempt %d error: %s", kp, list(by_id), attempt + 1, str(exc)[:140])
        if all_long_exhausted:
          raise RuntimeError("All configured Gemini API keys hit daily/403 quota limits") from exc
    raise RuntimeError(f"Failed proofreading batch {list(by_id)} after retries")

  batches = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
  if batches:
    with ThreadPoolExecutor(max_workers=min(max_workers, len(clients), len(batches))) as pool:
      futs = [pool.submit(_run_batch, b) for b in batches]
      for fut in as_completed(futs):
        fut.result()

  files_changed, blocks_changed = _apply_checkpoint_to_roots(targets, done, summary_title=summary_title)

  return {
    "targets": len(targets),
    "already_done": len(targets) - len(pending),
    "newly_proofread": len(pending),
    "files_changed": files_changed,
    "blocks_changed": blocks_changed,
  }


def export_pending_kanvi_shards(
  roots: Sequence[pathlib.Path],
  checkpoint_path: pathlib.Path | None,
  shard_dir: pathlib.Path,
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
  max_shard_chars: int = 18000,
) -> list[pathlib.Path]:
  """Export unfinished non-included ``summary_title`` blocks into size-bounded `shard_XX.txt` files."""
  targets = _collect_kanva_sayana_targets(roots, summary_title=summary_title)
  done = _load_checkpoint_records(checkpoint_path)
  pending = [t for t in targets if t["id"] not in done]

  shard_dir.mkdir(parents=True, exist_ok=True)
  for old in shard_dir.glob("shard_*.txt"):
    old.unlink()

  shards: list[list[dict]] = []
  cur: list[dict] = []
  cur_chars = 0
  for item in pending:
    item_len = len(item["raw"]) + len(item["ref_mantra"]) + 60
    if cur and cur_chars + item_len > max_shard_chars:
      shards.append(cur)
      cur = []
      cur_chars = 0
    cur.append(item)
    cur_chars += item_len
  if cur:
    shards.append(cur)

  written: list[pathlib.Path] = []
  for idx, chunk in enumerate(shards):
    out_p = shard_dir / f"shard_{idx:02d}.txt"
    parts = [
      f"<<<ITEM {it['id']}>>>\n[REF_MANTRA]\n{it['ref_mantra']}\n\n[COMMENTARY]\n{it['raw']}\n<<<END {it['id']}>>>"
      for it in chunk
    ]
    out_p.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    written.append(out_p)
  return written


def ingest_kanvi_shards_and_apply(
  roots: Sequence[pathlib.Path],
  shard_out_dir: pathlib.Path,
  checkpoint_path: pathlib.Path | None,
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
  apply_to_files: bool = True,
) -> dict[str, int]:
  """Ingest `shard_*.out.txt` responses through post-guards, update checkpoint, and optionally write files."""
  targets = _collect_kanva_sayana_targets(roots, summary_title=summary_title)
  by_id = {t["id"]: t for t in targets}
  done = _load_checkpoint_records(checkpoint_path)

  newly_ingested = 0
  rejected_short = 0
  for out_p in sorted(shard_out_dir.glob("shard_*.out.txt")):
    txt = out_p.read_text(encoding="utf-8")
    for tid_s, body in _ITEM_OUT_RE.findall(txt):
      tid = int(tid_s)
      if tid not in by_id or tid in done:
        continue
      raw = by_id[tid]["raw"]
      cleaned_out = body.strip()
      if (len(raw) >= 30 and len(cleaned_out) < max(12, int(len(raw) * 0.40))) or (raw.strip() and not cleaned_out):
        rejected_short += 1
        continue
      guarded = _postprocess_proofread_output(raw, cleaned_out)
      if tid not in done or done[tid] != guarded:
        done[tid] = guarded
        newly_ingested += 1
        if checkpoint_path:
          checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
          with checkpoint_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": tid, "proofread": guarded}, ensure_ascii=False) + "\n")

  files_changed, blocks_changed = (0, 0)
  if apply_to_files:
    files_changed, blocks_changed = _apply_checkpoint_to_roots(targets, done, summary_title=summary_title)

  missing = len(targets) - len(done)
  return {
    "targets": len(targets),
    "done_total": len(done),
    "missing": missing,
    "newly_ingested": newly_ingested,
    "rejected_short": rejected_short,
    "files_changed": files_changed,
    "blocks_changed": blocks_changed,
  }


def split_text_for_llm(text: str, max_chars: int = 5200) -> list[str]:
  """Split an oversize commentary block cleanly along paragraph/line breaks without mid-sentence tearing."""
  t = text.strip()
  if len(t) <= max_chars:
    return [t] if t else []
  parts: list[str] = []
  cur: list[str] = []
  cur_len = 0
  # Prefer splitting on blank lines first; if a single paragraph exceeds max_chars, split on single newlines.
  units: list[tuple[str, str]] = []
  for para in re.split(r"\n\s*\n+", t):
    p = para.strip()
    if not p:
      continue
    if len(p) <= max_chars:
      units.append(("\n\n", p))
    else:
      for idx, ln in enumerate(ln for ln in p.splitlines() if ln.strip()):
        units.append(("\n\n" if idx == 0 else "\n", ln))
  for sep, u in units:
    if cur and cur_len + len(u) + len(sep) > max_chars:
      parts.append("".join(cur))
      cur = [u]
      cur_len = len(u)
    elif cur:
      cur.append(sep + u)
      cur_len += len(sep) + len(u)
    else:
      cur.append(u)
      cur_len = len(u)
  if cur:
    parts.append("".join(cur))
  return parts


def export_workflow_batches(
  roots: Sequence[pathlib.Path],
  checkpoint_path: pathlib.Path | None,
  batches_path: pathlib.Path,
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
  max_batch_chars: int = 5000,
  max_item_chars: int = 5200,
  split_map_path: pathlib.Path | None = None,
) -> dict[str, int]:
  """Pack pending canonical blocks into size-bounded `wf_proofread_sem.py` JSON batches (auto-splitting long items)."""
  targets = _collect_kanva_sayana_targets(roots, summary_title=summary_title)
  done = _load_checkpoint_records(checkpoint_path)
  pending = [t for t in targets if t["id"] not in done]

  work_units: list[dict] = []
  split_map: dict[str, list[dict]] = {}
  next_neg_id = -1
  for t in pending:
    tid = t["id"]
    chunks = split_text_for_llm(t["raw"], max_chars=max_item_chars)
    if len(chunks) <= 1:
      work_units.append({"id": tid, "ref": t["ref_mantra"], "raw": t["raw"]})
      continue
    parts_meta = []
    for ch_txt in chunks:
      sid = next_neg_id
      next_neg_id -= 1
      work_units.append({"id": sid, "ref": t["ref_mantra"], "raw": ch_txt})
      parts_meta.append({"sid": sid, "raw": ch_txt})
    split_map[str(tid)] = parts_meta

  batches: list[list[dict]] = []
  cur: list[dict] = []
  cur_len = 0
  for u in work_units:
    u_len = len(u["raw"]) + len(u["ref"]) + 80
    if cur and cur_len + u_len > max_batch_chars:
      batches.append(cur)
      cur = []
      cur_len = 0
    cur.append(u)
    cur_len += u_len
  if cur:
    batches.append(cur)

  batches_path.parent.mkdir(parents=True, exist_ok=True)
  batches_path.write_text(json.dumps(batches, ensure_ascii=False), encoding="utf-8")
  if split_map_path is not None:
    split_map_path.parent.mkdir(parents=True, exist_ok=True)
    split_map_path.write_text(json.dumps(split_map, ensure_ascii=False, indent=2), encoding="utf-8")

  return {
    "targets": len(targets),
    "already_done": len(done),
    "pending": len(pending),
    "split_items": len(split_map),
    "work_units": len(work_units),
    "batches": len(batches),
  }


def ingest_workflow_outputs(
  roots: Sequence[pathlib.Path],
  wf_out_dir: pathlib.Path,
  checkpoint_path: pathlib.Path | None,
  *,
  summary_title: str = CANONICAL_KANVA_SAYANA_SUMMARY,
  split_map_path: pathlib.Path | None = None,
  apply_to_files: bool = True,
) -> dict[str, int]:
  """Ingest workflow `shard_*.out.txt` outputs, reassemble split items without ID collision, and apply cleanly."""
  targets = _collect_kanva_sayana_targets(roots, summary_title=summary_title)
  by_id = {t["id"]: t for t in targets}
  done = _load_checkpoint_records(checkpoint_path)

  parsed_units: dict[int, str] = {}
  for out_p in sorted(wf_out_dir.glob("shard_*.out.txt")):
    txt = out_p.read_text(encoding="utf-8")
    for tid_s, body in _ITEM_OUT_RE.findall(txt):
      parsed_units[int(tid_s)] = body.strip()

  split_map: dict[str, list[dict]] = (
    json.loads(split_map_path.read_text(encoding="utf-8"))
    if split_map_path and split_map_path.exists()
    else {}
  )

  newly_ingested = 0
  rejected_short = 0

  def _accept(tid: int, candidate: str) -> None:
    nonlocal newly_ingested, rejected_short
    raw = by_id[tid]["raw"]
    if (len(raw) >= 30 and len(candidate) < max(12, int(len(raw) * 0.40))) or (raw.strip() and not candidate.strip()):
      rejected_short += 1
      return
    guarded = _postprocess_proofread_output(raw, candidate)
    if tid not in done or done[tid] != guarded:
      done[tid] = guarded
      newly_ingested += 1
      if checkpoint_path:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with checkpoint_path.open("a", encoding="utf-8") as fh:
          fh.write(json.dumps({"id": tid, "proofread": guarded}, ensure_ascii=False) + "\n")

  for tid_s, parts_meta in split_map.items():
    tid = int(tid_s)
    if tid not in by_id or tid in done:
      continue
    if all(p["sid"] in parsed_units for p in parts_meta):
      joined = "  \n".join(parsed_units[p["sid"]] for p in parts_meta)
      _accept(tid, joined)

  for uid, body in parsed_units.items():
    if uid < 0 or uid not in by_id or str(uid) in split_map or uid in done:
      continue
    _accept(uid, body)

  files_changed, blocks_changed = (0, 0)
  if apply_to_files:
    files_changed, blocks_changed = _apply_checkpoint_to_roots(targets, done, summary_title=summary_title)

  return {
    "targets": len(targets),
    "done_total": len(done),
    "missing": len(targets) - len(done),
    "newly_ingested": newly_ingested,
    "rejected_short": rejected_short,
    "files_changed": files_changed,
    "blocks_changed": blocks_changed,
  }
