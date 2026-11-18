"""Phonemic Extended-SLP1 codec, alignment encoder, and guarded multi-script decoder
for the distilled local Sanskrit neural hyphenator."""
from __future__ import annotations

import random
import regex
from indic_transliteration import sanscript

from doc_curation.llm.proofreader.guards import (
  canonical_sandhi_skeleton,
  mask_protected_blocks,
  rejoin_merger_violations,
  restore_protected_blocks,
)

# Fixed 96-entry SLP1 + punctuation vocabulary (0 = PAD, 1 = UNK)
SLP1_CHARS = (
  "aAiIuUfFxXeEoOMH"
  "kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzshL|"
  "Z'~0123456789"
  " -–।॥,;.?!\"()>"
)
CHAR_TO_ID: dict[str, int] = {ch: idx + 2 for idx, ch in enumerate(SLP1_CHARS)}
VOCAB_SIZE = len(SLP1_CHARS) + 2

_SHORT_VOWELS = frozenset("aiufx")
_MERGED_VOWELS = frozenset("AIUFXeEoO")
_ALL_VOWELS = _SHORT_VOWELS | _MERGED_VOWELS
_SEMIVOWELS = frozenset("yrlvL")
_NASALS = frozenset("NYRnm")
_SIBILANTS = frozenset("Szsh")
_STOPS = frozenset("kKgGcCjJwWqQtTdDpPbB")
_HALANT_CODA_OK = frozenset("myvrsSzdcjgbRntkpl")
_ACCENT_RE = regex.compile(r"[\u0951-\u0954\u1cd0-\u1cff]")
_ANNO_RE = regex.compile(r"\+\+\+\(.*?\)\+\+\+", regex.DOTALL)
_DEV_SPAN_RE = regex.compile(r"[\u0900-\u0963\u0966-\u097f\u1cd0-\u1cff\-–—]+")
_IAST_DIACRITIC_RE = regex.compile(r"[āīūṛṝḷḹṅñṭḍṇśṣṃḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢṂḤ]")
_IAST_WORD_RE = regex.compile(r"[A-Za-zāīūṛṝḷḹṅñṭḍṇśṣṃḥĀĪŪṚṜḶḸṄÑṬḌṆŚṢṂḤ'’\-–]+")

# Head 1: Inline separator after phoneme i
# 0: "", 1: "-", 2: "–", 3: " ", 4: " Z" (lost avagraha)
NUM_SEP_CLASSES = 5
# Head 2: Clause break action at phoneme i (active when clause_newlines=True)
# 0: NO_NL, 1: SOFT_NL ("  \n"), 2: VISARGA_NL (-> "H  \n"),
# 3: DIRGHA_SHORT_NL (A->a\na, I->i\ni, U->u\nu),
# 4: DIRGHA_LONG_NL  (A->a\nA, I->i\nI, U->u\nU),
# 5: GUNA_NL         (e->a\ni, o->a\nu),
# 6: VRDDHI_NL       (E->a\ne, O->a\no)
NUM_CLAUSE_CLASSES = 7

_CLAUSE_SPLIT_MAP: dict[tuple[int, str], tuple[str, str]] = {
  (3, "A"): ("a", "a"), (3, "I"): ("i", "i"), (3, "U"): ("u", "u"),
  (4, "A"): ("a", "A"), (4, "I"): ("i", "I"), (4, "U"): ("u", "U"),
  (5, "e"): ("a", "i"), (5, "o"): ("a", "u"),
  (6, "E"): ("a", "e"), (6, "O"): ("a", "o"),
}


def phon_category(ch: str) -> int:
  if ch in _SHORT_VOWELS:
    return 1
  if ch in _MERGED_VOWELS:
    return 2
  if ch in ("M", "H"):
    return 3
  if ch in _SEMIVOWELS:
    return 4
  if ch in _NASALS:
    return 5
  if ch in _SIBILANTS:
    return 6
  if ch in _STOPS:
    return 7
  if ch in ("Z", "'"):
    return 8
  if ch in " -–।॥,;.?!\"()>":
    return 9
  return 0


def text_to_ids_and_cats(slp_str: str) -> tuple[list[int], list[int]]:
  ids = [CHAR_TO_ID.get(ch, 1) for ch in slp_str]
  cats = [phon_category(ch) for ch in slp_str]
  return ids, cats


def strip_accents_tracking(slp_with_accents: str) -> tuple[str, dict[int, str]]:
  """Peel Vedic accent marks off an SLP1 string, attaching each mark to the
  immediately preceding phoneme index for 100% lossless reattachment."""
  clean_chars: list[str] = []
  accents: dict[int, str] = {}
  for ch in slp_with_accents:
    if _ACCENT_RE.fullmatch(ch):
      if clean_chars:
        idx = len(clean_chars) - 1
        accents[idx] = accents.get(idx, "") + ch
    else:
      clean_chars.append(ch)
  return "".join(clean_chars), accents


def encode_curated_sentence(
  curated_text: str,
  rng: random.Random,
  *,
  has_clause_breaks: bool = False,
) -> tuple[str, list[int], list[int]] | None:
  """Convert a curated Devanāgarī sentence/paragraph into ``(raw_slp1, sep_labels, clause_labels)``
  by fusing compound hyphens and realistic sandhi seams."""
  txt = _ANNO_RE.sub("", curated_text)
  txt = regex.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", txt)
  txt = _ACCENT_RE.sub("", txt)
  txt = regex.sub(r"(?<=\S)--(?=\S)", "–", txt)
  if "<" in txt or "[[" in txt or not regex.search(r"[\u0905-\u0939]", txt):
    return None

  slp = sanscript.transliterate(txt.strip(), sanscript.DEVANAGARI, sanscript.SLP1)
  slp = regex.sub(r"[ \t]*\n[ \t]*", "\n", slp)
  slp = regex.sub(r"[ \t]{2,}", " ", slp)

  raw_chars: list[str] = []
  sep_y: list[int] = []
  clause_y: list[int] = []
  n = len(slp)
  i = 0
  while i < n:
    ch = slp[i]
    # Check cross-newline sandhi fusion when building clause-break training data
    if ch == "\n" and raw_chars:
      prev = raw_chars[-1]
      nxt = slp[i + 1] if i + 1 < n else ""
      if has_clause_breaks and nxt and rng.random() < 0.75:
        if prev == "H" and nxt in "tTsScCjJwWqQ":
          sib = "s" if nxt in "tTs" else ("S" if nxt in "cCS" else "z")
          raw_chars[-1] = sib
          clause_y[-1] = 2
          i += 1
          continue
        for cl_id, (l_v, r_v, merged_v) in (
          (3, ("a", "a", "A")), (3, ("i", "i", "I")), (3, ("u", "u", "U")),
          (4, ("a", "A", "A")), (4, ("i", "I", "I")), (4, ("u", "U", "U")),
          (5, ("a", "i", "e")), (5, ("a", "u", "o")),
          (6, ("a", "e", "E")), (6, ("a", "o", "O")),
        ):
          if prev == l_v and nxt == r_v:
            raw_chars[-1] = merged_v
            clause_y[-1] = cl_id
            i += 2
            break
        else:
          pass
        if i <= n and (i >= n or slp[i] != "\n"):
          continue
      # Standard soft newline at space/boundary
      if has_clause_breaks:
        clause_y[-1] = 1
      if prev not in (" ",) and nxt and prev not in _HALANT_CODA_OK:
        raw_chars.append(" ")
        sep_y.append(0)
        clause_y.append(0)
      elif prev in _HALANT_CODA_OK and nxt:
        sep_y[-1] = 3
      i += 1
      continue

    if ch in ("-", "–") and raw_chars:
      sep_y[-1] = 1 if ch == "-" else 2
      i += 1
      continue

    if ch == " " and raw_chars and i + 1 < n:
      prev = raw_chars[-1]
      nxt = slp[i + 1]
      # Lost avagraha corruption: "o Zr" -> "or" (e.g. rAmo 'rTaH -> rAmorTaH)
      if prev in ("o", "e") and slp[i + 1:i + 3] == "Zr" and i + 3 < n and slp[i + 3] not in _ALL_VOWELS:
        if rng.random() < 0.45:
          sep_y[-1] = 4
          i += 2  # skip " Z"
          continue
      # Standard explicit avagraha ("o Zsti" -> "oZsti") or halant sandhi ("ity evam" -> "ityevam")
      if nxt == "Z" or (prev in _HALANT_CODA_OK and (nxt in _ALL_VOWELS or nxt in _STOPS or nxt in _SEMIVOWELS or nxt in _NASALS or nxt in _SIBILANTS)):
        if rng.random() < 0.90:
          sep_y[-1] = 3
          i += 1
          continue
      # Occasional OCR space drop between vowel-final words
      if prev in _ALL_VOWELS and nxt in (_STOPS | _NASALS | _SEMIVOWELS | _SIBILANTS) and rng.random() < 0.06:
        sep_y[-1] = 3
        i += 1
        continue

    raw_chars.append(ch)
    sep_y.append(0)
    clause_y.append(0)
    i += 1

  if len(raw_chars) < 3:
    return None
  return "".join(raw_chars), sep_y, clause_y


def _is_valid_inline_cut(slp_tok: str, pos: int, sep_cls: int) -> bool:
  """Phonotactic sanity filter on predicted cut after ``slp_tok[pos]``."""
  if pos < 0 or pos >= len(slp_tok) - 1 or sep_cls == 0:
    return False
  left_ch = slp_tok[pos]
  right_ch = slp_tok[pos + 1]
  left_piece = slp_tok[:pos + 1]
  right_piece = slp_tok[pos + 1:]

  # Never leave a vowel-less shard on either side (except avagraha Z+vowel like 'sti)
  if not any(c in _ALL_VOWELS for c in left_piece):
    return False
  if not any(c in _ALL_VOWELS for c in right_piece):
    return False

  if sep_cls == 4:  # SPACE_AVAGRAHA (" Z")
    return left_ch in ("o", "e") and right_ch == "r" and pos + 2 < len(slp_tok) and slp_tok[pos + 2] not in _ALL_VOWELS

  # Never cut between a stop/sibilant/semivowel and its own vowel unless valid halant coda
  if left_ch not in (_ALL_VOWELS | {"M", "H"} | _HALANT_CODA_OK):
    return False
  if left_ch in (_STOPS - _HALANT_CODA_OK) and right_ch in _ALL_VOWELS:
    return False

  # Dictionary-backed merger veto: forbid splitting right after a merged vowel (A/I/U/e/E/o/O)
  # when the junction is a dīrgha/guṇa/vṛddhi merger (e.g. dharmA|rTa, dayA|rdra, maho|tsava, sadE|va)
  if left_ch in _MERGED_VOWELS and sep_cls in (1, 2, 3):
    from .lexicon import is_merger_veto_slp1
    if is_merger_veto_slp1(slp_tok, pos):
      return False
  return True


def reconstruct_token_from_slp1(
  orig_tok: str,
  slp_tok: str,
  accents: dict[int, str],
  sep_preds: list[int],
  clause_preds: list[int] | None,
  scheme: str,
) -> str:
  """Reconstruct a single unhyphenated Sanskrit token in ``scheme`` using predicted
  SLP1 boundary tags, reattaching Vedic accents and enforcing merger-veto guards."""
  pieces_out: list[str] = []
  cur_slp: list[str] = []
  n = len(slp_tok)

  def _flush_piece(piece_str: str) -> str:
    if not piece_str:
      return ""
    return sanscript.transliterate(piece_str, sanscript.SLP1, scheme)

  i = 0
  while i < n:
    ch = slp_tok[i]
    acc = accents.get(i, "")
    cl_act = clause_preds[i] if (clause_preds is not None and i < len(clause_preds)) else 0

    if cl_act == 2 and ch in ("s", "S", "z", "r") and i < n - 1:
      cur_slp.append("H" + acc)
      pieces_out.append(_flush_piece("".join(cur_slp)))
      pieces_out.append("  \n")
      cur_slp = []
      i += 1
      continue

    if (cl_act, ch) in _CLAUSE_SPLIT_MAP and i < n - 1:
      lv, rv = _CLAUSE_SPLIT_MAP[(cl_act, ch)]
      cur_slp.append(lv + acc)
      pieces_out.append(_flush_piece("".join(cur_slp)))
      pieces_out.append("  \n")
      cur_slp = [rv]
      i += 1
      continue

    cur_slp.append(ch + acc)
    sep_cls = sep_preds[i] if i < len(sep_preds) else 0
    if i < n - 1 and sep_cls != 0 and _is_valid_inline_cut(slp_tok, i, sep_cls):
      pieces_out.append(_flush_piece("".join(cur_slp)))
      if cl_act == 1 and sep_cls == 3:
        pieces_out.append("  \n")
      elif sep_cls == 1:
        pieces_out.append("-")
      elif sep_cls == 2:
        pieces_out.append("–")
      elif sep_cls == 3:
        pieces_out.append(" ")
      elif sep_cls == 4:
        pieces_out.append(" ")
        cur_slp = ["Z"]
        i += 1
        continue
      cur_slp = []
    elif i == n - 1 and cl_act == 1:
      pieces_out.append(_flush_piece("".join(cur_slp)))
      pieces_out.append("  \n")
      cur_slp = []
    i += 1

  if cur_slp:
    pieces_out.append(_flush_piece("".join(cur_slp)))

  cand = "".join(pieces_out)
  if scheme == sanscript.DEVANAGARI and "\n" not in cand and "ऽ" not in (set(cand) - set(orig_tok)):
    cand = rejoin_merger_violations(orig_tok, cand)
    if canonical_sandhi_skeleton(cand) != canonical_sandhi_skeleton(orig_tok):
      return orig_tok
  return cand


def apply_slp1_predictions_to_paragraph(
  para: str,
  predict_fn,
  *,
  clause_newlines: bool = False,
) -> str:
  """Run sentence-level SLP1 tagging across a paragraph while preserving existing
  compounds, punctuation, Markdown, and non-Sanskrit words verbatim."""
  anno_masks: dict[str, str] = {}

  def _mask_anno(m):
    k = f"§§ANNO{len(anno_masks)}§§"
    anno_masks[k] = m.group(0)
    return k

  work = _ANNO_RE.sub(_mask_anno, para)

  # Collect Devanāgarī or diacritic-IAST token spans in order
  spans: list[tuple[int, int, str, str, bool]] = []
  for m in _DEV_SPAN_RE.finditer(work):
    tok = m.group(0)
    if not regex.search(r"[\u0905-\u0939]", tok):
      continue
    already = any(s in tok for s in ("-", "–", "—"))
    spans.append((m.start(), m.end(), tok, sanscript.DEVANAGARI, already))

  if not spans and _IAST_DIACRITIC_RE.search(work):
    for m in _IAST_WORD_RE.finditer(work):
      tok = m.group(0)
      if not _IAST_DIACRITIC_RE.search(tok):
        continue
      already = any(s in tok for s in ("-", "–"))
      spans.append((m.start(), m.end(), tok, sanscript.IAST, already))

  if not spans:
    return para

  slp_Stream_parts: list[str] = []
  tok_meta: list[tuple[int, int, str, dict[int, str], str, bool]] = []
  cursor_slp = 0
  for idx, (_, _, tok, scheme, already) in enumerate(spans):
    if idx > 0:
      slp_Stream_parts.append(" ")
      cursor_slp += 1
    slp_raw = sanscript.transliterate(tok, scheme, sanscript.SLP1)
    slp_clean, acc_map = strip_accents_tracking(slp_raw)
    slp_Stream_parts.append(slp_clean)
    tok_meta.append((cursor_slp, cursor_slp + len(slp_clean), slp_clean, acc_map, scheme, already))
    cursor_slp += len(slp_clean)

  full_slp = "".join(slp_Stream_parts)
  sep_all, clause_all = predict_fn(full_slp)

  out_buf: list[str] = []
  last_end = 0
  for i_sp, (st_char, en_char, orig_tok, _, _) in enumerate(spans):
    gap = work[last_end:st_char]
    if i_sp > 0 and clause_newlines and "\n" not in gap:
      prev_slp_end = tok_meta[i_sp - 1][1] - 1
      if 0 <= prev_slp_end < len(clause_all) and clause_all[prev_slp_end] == 1:
        gap = regex.sub(r"[ \t]+$", "", gap) + "  \n"
      elif "।" in gap or "॥" in gap:
        gap = regex.sub(r"([।॥]+)[ \t]+", r"\1  \n", gap)
    out_buf.append(gap)

    s_idx, e_idx, slp_clean, acc_map, scheme, already = tok_meta[i_sp]
    if already or len(slp_clean) < 3:
      out_buf.append(orig_tok)
    else:
      t_sep = sep_all[s_idx:e_idx]
      t_cl = clause_all[s_idx:e_idx] if clause_newlines else None
      # Word-final clause break is handled on `gap` above so punctuation stays attached!
      if t_cl is not None and len(t_cl) > 0:
        t_cl = list(t_cl)
        t_cl[-1] = 0
      out_buf.append(reconstruct_token_from_slp1(orig_tok, slp_clean, acc_map, t_sep, t_cl, scheme))
    last_end = en_char

  out_buf.append(work[last_end:])
  res = "".join(out_buf)
  for k, v in anno_masks.items():
    res = res.replace(k, v)
  return res


def apply_slp1_predictions_to_text(
  text: str,
  predict_fn,
  *,
  clause_newlines: bool = False,
) -> str:
  """Top-level Markdown-safe text wrapper protecting ``मूलम्`` blocks."""
  if not text:
    return text
  masked, masks = mask_protected_blocks(text)
  sep_re = r"(\n\s*\n+)" if clause_newlines else r"(\n)"
  parts = regex.split(sep_re, masked)
  out_parts = [
    apply_slp1_predictions_to_paragraph(p, predict_fn, clause_newlines=clause_newlines)
    if idx % 2 == 0 and p.strip()
    else p
    for idx, p in enumerate(parts)
  ]
  return restore_protected_blocks("".join(out_parts), masks)
