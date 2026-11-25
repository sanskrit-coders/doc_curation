"""Commentary prose cleanup helpers for VS-K editions."""
from __future__ import annotations

import pathlib
import re

from doc_curation.sanskrit import hyphenator
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import (
  VSK_SARVA_PRASTUTI_DIR,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina.samhitaa import bhashya_aligner

_COMM_BLK_RE = re.compile(
  r"(<details><summary>(?:सायण|आनन्दबोध|अनन्ताचार्य)[^<]*</summary>\s*)(.*?)(\s*</details>\n?)",
  flags=re.S,
)


def strip_pune_margin_numbers(text: str) -> str:
  """Remove VSM Pune line-margin numbers (`५/१०/१५/२०/२५/३०`) and OCR apparatus/header noise in commentary."""
  t = text.replace("\\!", "!").replace("\\~", "~").replace("*'*", "'").replace("*\"*", "\"")
  t = re.sub(r"\*([०-९0-9.,;:'\"?!()\[\]]+)\*", r"\1", t)
  t = re.sub(r"\(\s*L\.\s*\d+\s*\)", "", t)
  t = re.sub(
    r"(?m)^\s*(?:<<|>>|°|\*\"\*|\"\*|\(\s*\(\)|"
    r"[-–—.]*\s*[०-९]{1,4}[-–—.,;:•]*|[-–—.]*\s*[0-9]{1,4}\s*[-–—.,;:•)]*|"
    r"[०-९0-9]+\s*[-–]\s*[०-९0-9]+\.?|"
    r"['‘\"“\*]?\s*का[णण्]्?[व्य]?\s*[-–\s]*संहिता(?:\s*[।॥०-९\[\]\-])*|"
    r"कासं[\s.…]*[०-९]+|"
    r"सायणाचार्य.*भाष्य\s*[सन]मेता.*|"
    r"[^\n\[]*अध्यायः\s*\]|"
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
  t = re.sub(r"\[?\s*[-–—]?\s*अ०\s*[०-९।|.\-\s]+\]?", " ", t)
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
  return t


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
