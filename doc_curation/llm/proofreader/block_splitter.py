"""Sense-unit block splitter and ``विश्वास-प्रस्तुतिः`` + ``मूलम्`` builder
implementing the ``/text_to_blocks`` skill for BOTH:
1. Local zero-LLM execution (deterministic Pāṇinian Tests 1–5 + distilled SLP1 hyphenator), and
2. ``ProofreaderBackend`` (``Qwen3-14B + LoRA``) for translation-guided / quote-guided splits.

Strict ``/text_to_blocks`` invariants enforced:
- Masks ``+++(...)+++`` editorial glosses during daṇḍa splitting; treats ``+++(supplied_verb)+++``
  as fulfilling finite-verb completeness in Test 5 while stripping ``+++(...)+++`` from ``मूलम्``.
- Keeps reference / pañcāti / anuvāka markers (``१। ५। ११। २॥ ५६``, ``(33)``, ``[41]``) attached.
- Applies Tests 1–5 in order (Same Ṛk/verse, ``yad``/``tad`` conditional-correlative without
  over-merging self-contained ``yad...tad`` sentences, embedded quotes inside conditionals,
  multi-sentence quotations distinguishing genuine ``इति`` from ``√i`` ``एति`` verbs, and
  sequential ``-त्वा``/``-य`` actions + verb-less purpose datives / ``अथ`` items).
- Converts Vedic ``॒``/``॑`` accents to US (``᳓``/``᳙``) in ``विश्वास-प्रस्तुतिः`` while keeping ``मूलम्`` verbatim.
"""
from __future__ import annotations

import json
import regex
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit import split_to_sentences
from doc_curation.sanskrit.hyphenator import hyphene
from .backend import ProofreaderBackend, proofread_text

_ANNO_RE = regex.compile(r"\+\+\+\((.*?)\)\+\+\+", flags=regex.DOTALL)
_PURE_REF_RE = regex.compile(r"^[\s०-९0-9।॥.\-–—()\[\],]+$")
_TRAIL_NUM_REF_RE = regex.compile(r"^[\(\[][०-९0-9.\-\s]+[\)\]]$")
_ENDS_DOUBLE_DANDA_RE = regex.compile(r"॥[\s०-९0-9()\[\].।॥\-–—]*$")
_NUMBERED_DOUBLE_DANDA_RE = regex.compile(r"॥[\s०-९0-9()\[\].।॥\-–—]*[०-९0-9()\[\]][\s०-९0-9()\[\].।॥\-–—]*$")
_HEADING_LINE_RE = regex.compile(
  r"^(?:##\s*)?(?:॥\s*)?(?:अथ(?:\s+|ै)[^\u0951\u0952\u1cd3\u1cd9]*(?:दशकः|अध्यायः|ऽध्यायः)|[^\s\u0951\u0952\u1cd3\u1cd9]*(?:विंशो|त्रिंशो)ऽ?ध्यायः)\s*[।॥०-९0-9()\[\]]*$"
)
_COLOPHON_LINE_RE = regex.compile(
  r"^(?:॥\s*)?इति\s+[^\u0951\u0952\u1cd3\u1cd9]*(?:संहिता|दशकः|अध्यायः|ऽध्यायः|समाप्ता)"
)

# 3rd-sg √i ("eti") verbs explicitly listed in /text_to_blocks/SKILL.md Test 4
_ETI_ROOT_VERBS_SLP = frozenset({
  "eti", "upEti", "paryeti", "aveti", "samaveti", "prEti", "aByeti", "anveti",
  "atyeti", "vyeti", "sameti", "punareti", "antareti", "apeti", "apyeti",
  "udeti", "pratyeti", "aDyeti", "Ayureti",
})

_YAD_FORMS_SLP = frozenset({
  "yaH", "yo", "yas", "yaS", "yaz", "yar", "yO", "ye", "yam", "yaM", "yAn",
  "yena", "yAByAm", "yEH", "yasmE", "yeByaH", "yasmAt", "yasmAd", "yasya",
  "yasmin", "yezu", "yat", "yad", "yAni", "yA", "yAm", "yAM", "yayA",
  "yasyE", "yasyAH", "yasyAm", "yatra", "yadA", "yaTA", "yadi", "yAvat", "yAvad",
})
_TAD_CORREL_SLP = frozenset({
  "sa", "saH", "so", "tO", "te", "tam", "taM", "tAn", "tena", "tasmE", "teByaH",
  "tasmAt", "tasmAd", "tasya", "tasmin", "tezu", "tat", "tad", "tAni", "sA",
  "tAm", "tAM", "tayA", "tasyE", "tasyAH", "tasyAm", "tAH", "tatra", "tadA",
  "taTA", "tarhi", "tAvat", "tato", "tataH", "etad", "etat", "eza", "ezaH",
  "ezA", "ete", "etAni", "etam", "etasya", "etasmin",
})
_QUOTE_OPENERS_SLP = (
  "abravIt", "ZbravIt", "bravIt", "uvAca", "Aha", "AhuH", "vadati", "vadanti",
  "brUyAt", "apfcCat", "prcCati",
)
_FINITE_VERB_EXACT_SLP = frozenset({
  "asi", "asmi", "sTa", "sTu", "astu", "santu", "staH", "stha", "smasi", "masi",
  "Bava", "Bavatu", "Bavantu", "pAhi", "muYca", "gacCa", "datta", "yaja",
  "vada", "brUhi", "dehi", "DeHi", "SfRu", "dfha", "jahi", "seDa", "vaha",
  "syAt", "syuH", "AsIt", "aBUt", "acazwa", "ajAnAt", "vyajAnAt", "karat",
  "akarat", "agamat", "stAt", "mOk", "dadAtu", "dadAti", "dadati", "kurute",
  "vidma", "vidmahe", "cakruH", "dadDuH", "viDema", "dASema", "syAma", "Bavema",
  "daDmaH", "smaH", "imaH", "BavAmaH", "yajAmaH",
})
_FINITE_VERB_ENDINGS_SLP = (
  "mi", "si", "ti", "te", "anti", "ante", "mahe", "Dve", "Dvam",
  "ntu", "sva", "Ita", "eta", "uH", "Imahi", "Asam",
  "ntAm", "yatAm", "yAtAm", "DatAm", "etAm", "ItAm", "ema",
)
_PROSE_YAJUS_OPENERS = (
  "उपयामगृहीतोऽसि", "उपयाम-गृहीतोऽसि", "उपया॑मगृहीतो", "उ॒प॒या॒मगृ॑हीतो", "उ॒पया॒मगृ॑हीतो",
)


def _clean_slp_words(seg: str, *, use_local_hyphenator: bool = True) -> list[str]:
  """Convert a Sanskrit segment to clean accent-stripped SLP1 words (using the
  local hyphenator on a scratch copy so sandhi-fused ``यत्पूर्वे`` / ``स्युरिति`` split)."""
  no_anno = _ANNO_RE.sub(" ", seg)
  bare = accent.strip_accents(no_anno).replace("_", " ")
  if use_local_hyphenator:
    try:
      bare = hyphene(bare, clause_newlines=False)
    except Exception:
      pass
  slp = sanscript.transliterate(bare, sanscript.DEVANAGARI, sanscript.SLP1)
  slp = regex.sub(r"[^a-zA-Z'Z\-–\s]", " ", slp)
  return [w.strip("-–'Z") for w in regex.split(r"[\s\-–]+", slp) if w.strip("-–'Z")]


def has_genuine_iti(seg: str, *, use_local_hyphenator: bool = True, precomputed_words: list[str] | None = None) -> bool:
  """Return True iff ``seg`` contains genuine quotative ``इति`` (explicit or sandhi-fused),
  never confusing ``√i`` (``उपैति``, ``पर्येति``, ``समवेति``, etc.) with ``इति``."""
  no_anno = _ANNO_RE.sub(" ", seg)
  bare = accent.strip_accents(no_anno).replace("_", " ")
  raw_slp = sanscript.transliterate(bare, sanscript.DEVANAGARI, sanscript.SLP1)
  raw_tokens = [w.strip("Z'") for w in regex.findall(r"[a-zA-Z'Z]+", raw_slp) if w.strip("Z'")]
  non_eti_tokens = [w for w in raw_tokens if w not in _ETI_ROOT_VERBS_SLP]
  for tok in non_eti_tokens:
    if tok == "iti" or tok.endswith(("Iti", "yiti", "viti", "riti", "diti", "titi", "miti")):
      return True
    if tok.endswith("eti") and len(tok) >= 4:
      return True
  if not non_eti_tokens:
    return False
  if precomputed_words is not None and len(non_eti_tokens) == len(raw_tokens):
    return "iti" in precomputed_words
  hyp_tokens = _clean_slp_words(
    " ".join(sanscript.transliterate(w, sanscript.SLP1, sanscript.DEVANAGARI) for w in non_eti_tokens),
    use_local_hyphenator=use_local_hyphenator,
  )
  return "iti" in hyp_tokens


def split_into_danda_segments(text: str) -> list[str]:
  """Split Sanskrit text on sentence daṇḍas while masking ``+++(...)+++`` glosses
  and keeping reference markers (``१। ५। ११। २॥ ५६``, ``(33)``) attached."""
  masks: dict[str, str] = {}

  def _m(m):
    k = f"[ANNO_{len(masks)}]"
    masks[k] = m.group(0)
    return k

  masked = _ANNO_RE.sub(_m, text)
  masked = regex.sub(r"(?<=\([०-९0-9]+\)\s*[०-९0-9]+)[ \t]*(?=\n)", " ॥ ", masked)
  raw_segs = [s.strip() for s in split_to_sentences(masked, respect_verse_blocks=False) if s.strip()]
  restored = []
  for s in raw_segs:
    for k, v in masks.items():
      s = s.replace(k, v)
    restored.append(s)

  # Glue pure reference-number segments forward (leading refs) or backward (trailing (33)),
  # and keep trailing post-॥ kaṇḍikā numbers (e.g. `॥१॥ १\n` or `। ॥२॥ ६८\n`) attached backward.
  merged: list[str] = []
  pending_prefix = ""
  for seg in restored:
    if merged and regex.search(r"[\u0905-\u0939]", merged[-1]):
      m_trail = regex.match(r"^([।॥]*\s*[०-९0-9()\[\] \t.।॥\-–—]+)\n+(.+)$", seg, flags=regex.DOTALL)
      if m_trail and (
        _ENDS_DOUBLE_DANDA_RE.search(merged[-1])
        or m_trail.group(1).lstrip().startswith("॥")
      ):
        merged[-1] = f"{merged[-1]} {m_trail.group(1).strip()}"
        seg = m_trail.group(2).strip()
    if _TRAIL_NUM_REF_RE.fullmatch(seg) and merged:
      merged[-1] = f"{merged[-1]} {seg}"
      continue
    if _PURE_REF_RE.fullmatch(seg):
      if merged and regex.search(r"[\u0905-\u0939]", merged[-1]) and not pending_prefix and (
        _ENDS_DOUBLE_DANDA_RE.search(merged[-1]) or seg.lstrip().startswith("॥")
      ):
        merged[-1] = f"{merged[-1]} {seg}"
        continue
      pending_prefix = f"{pending_prefix} {seg}".strip() if pending_prefix else seg
      continue
    if pending_prefix:
      seg = f"{pending_prefix} {seg}"
      pending_prefix = ""
    merged.append(seg)
  if pending_prefix:
    if merged:
      merged[-1] = f"{merged[-1]} {pending_prefix}"
    else:
      merged.append(pending_prefix)
  return merged


def _norm_correl_slp(word: str) -> str:
  if word in _YAD_FORMS_SLP or word in _TAD_CORREL_SLP:
    return word
  if len(word) >= 3 and word[-1] in ("s", "S", "z", "r"):
    return word[:-1] + "H"
  return word


def _is_finite_verb_word(word: str) -> bool:
  w = word[:-1] + "m" if word.endswith("M") else word
  if w in _FINITE_VERB_EXACT_SLP:
    return True
  return len(w) >= 4 and w not in ("kzemA", "kzema", "prema", "nema") and w.endswith(_FINITE_VERB_ENDINGS_SLP)


def _is_self_contained_yad(seg: str, words: list[str]) -> bool:
  """Check Test 2 exception: single-daṇḍa ``yad`` sentence that already contains
  its own ``tad``/``atha saH`` apodosis."""
  yad_idx = next((idx for idx, w in enumerate(words[:2]) if _norm_correl_slp(w) in _YAD_FORMS_SLP), None)
  if yad_idx is None:
    return False
  if "," in seg or ";" in seg:
    after = seg.split(",", 1)[-1] if "," in seg else seg.split(";", 1)[-1]
    aw = _clean_slp_words(after, use_local_hyphenator=False)
    if any(_norm_correl_slp(w) in _TAD_CORREL_SLP or w == "aTa" for w in aw[:3]):
      return True
  return any(
    _norm_correl_slp(w) in _TAD_CORREL_SLP or (len(w) >= 6 and w.startswith(("tamez", "tasmin")))
    for w in words[yad_idx + 3:]
  )


def _segment_features(seg: str, *, use_local_hyphenator: bool = True) -> dict:
  words = _clean_slp_words(seg, use_local_hyphenator=use_local_hyphenator)
  norm_words = [_norm_correl_slp(w) for w in words]
  anno_bodies = [m.group(1) for m in _ANNO_RE.finditer(seg)]
  has_supplied_verb = any(
    w.endswith(("ti", "te", "ta", "t", "uH", "ati", "ate"))
    for body in anno_bodies
    for w in _clean_slp_words(body, use_local_hyphenator=False)
  )
  opens_yad = bool(
    norm_words
    and (
      norm_words[0] in _YAD_FORMS_SLP
      or (len(norm_words) > 1 and norm_words[0] in ("sa", "so", "aTa", "tad") and norm_words[1] in _YAD_FORMS_SLP)
    )
  )
  has_yad_any = any(
    nw in _YAD_FORMS_SLP or any(w.startswith(yp) and len(w) > len(yp) + 2 for yp in ("yat", "yad", "yaT", "yadA", "yatr", "yas"))
    for w, nw in zip(words[:2], norm_words[:2])
  )
  self_yad = _is_self_contained_yad(seg, words)
  opens_tad = bool(norm_words and (norm_words[0] in _TAD_CORREL_SLP or (len(norm_words) > 1 and norm_words[0] == "aTa" and norm_words[1] in _TAD_CORREL_SLP)))
  has_tad_any = any(nw in _TAD_CORREL_SLP for nw in norm_words)
  has_quote_open = any(any(w.endswith(qo) or w == qo for qo in _QUOTE_OPENERS_SLP) for w in words)
  has_iti = has_genuine_iti(seg, use_local_hyphenator=use_local_hyphenator, precomputed_words=words)
  ends_absolutive = bool(
    words
    and len(words[-1]) >= 5
    and words[-1] != "tvA"
    and words[-1].endswith(("tvA", "wA", "QvA"))
    and not has_supplied_verb
  )
  has_finite_verb = has_supplied_verb or any(
    _is_finite_verb_word(w)
    or (w.endswith(("At", "Ad", "It", "Id")) and w not in ("tasmAt", "yasmAt", "asmAt", "kasmAt", "sAkzAt", "paScAt"))
    for w in words
  )
  bare_purpose_or_atha = (
    not has_finite_verb
    and "eva" not in words
    and len(words) <= 4
    and bool(words)
    and (words[-1].endswith(("yE", "tyE", "zwye", "zwyE")) or words[0] == "aTa")
  )
  seg_s = seg.rstrip()
  return {
    "words": words,
    "norm_words": norm_words,
    "opens_yad": (opens_yad or has_yad_any) and not self_yad,
    "opens_tad": opens_tad,
    "has_tad_any": has_tad_any,
    "has_quote_open": has_quote_open,
    "has_iti": has_iti,
    "ends_absolutive": ends_absolutive,
    "has_finite_verb": has_finite_verb,
    "bare_purpose_or_atha": bare_purpose_or_atha,
    "ends_double_danda": bool(_ENDS_DOUBLE_DANDA_RE.search(seg_s)),
    "ends_numbered_double_danda": bool(_NUMBERED_DOUBLE_DANDA_RE.search(seg_s)),
    "ends_single_danda": seg_s.endswith("।"),
  }


def _is_prose_formula_seg(seg: str) -> bool:
  s = accent.strip_accents(seg.lstrip())
  return any(s.startswith(op) for op in ("उपयामगृहीतो", "उपयाम-गृहीतो", "अथ ", "स्वाहा", "नमोऽस्तु रुद्रेभ्यो", "नमो ऽस्तु रुद्रेभ्यो", "तेभ्यो नमो"))


def _is_prose_yajus_pair(seg_a: str, seg_b: str) -> bool:
  if _is_prose_formula_seg(seg_a) or _is_prose_formula_seg(seg_b):
    return True
  va, vb = _akshara_count(seg_a), _akshara_count(seg_b)
  if 21 <= va <= 26 and 21 <= vb <= 26 and abs(va - vb) <= 2:
    return False
  sa = accent.strip_accents(seg_a.strip())
  sb = accent.strip_accents(seg_b.strip())
  wa = sa.split()[:2]
  wb = sb.split()[:2]
  if wa and wa == wb and len("".join(wa)) >= 5:
    return True
  return False


def _is_metrical_pair(seg_a: str, seg_b: str) -> bool:
  """Return True if ``(seg_a, seg_b)`` look like two halves of one metrical Ṛk/verse."""
  if _is_prose_yajus_pair(seg_a, seg_b):
    return False
  va = _akshara_count(seg_a)
  vb = _akshara_count(seg_b)
  if 14 <= va <= 27 and 14 <= vb <= 27 and abs(va - vb) <= 4:
    return True
  # Asymmetric Vedic stanzas: Gayatri (14-17+8 / 8+14-17), Usnih (14-17+12), Brhati/Pankti (13-17+18-25)
  if (14 <= va <= 17 and 7 <= vb <= 9) or (7 <= va <= 9 and 14 <= vb <= 17):
    return True
  if (14 <= va <= 17 and 10 <= vb <= 13) or (10 <= va <= 13 and 14 <= vb <= 17):
    return True
  if (13 <= va <= 17 and 18 <= vb <= 25) or (18 <= va <= 25 and 13 <= vb <= 17):
    return True
  if 10 <= va <= 28 and 10 <= vb <= 28 and abs(va - vb) <= 6:
    try:
      from chandas import svat_identifier, to_pattern_lines
      pl = to_pattern_lines([accent.strip_accents(seg_a), accent.strip_accents(seg_b)])
      res = svat_identifier.IdentifyFromPatternLines(pl)
      if res and res.get("exact"):
        return True
    except Exception:
      pass
  return False


def _verse_chain_length(segments: list[str], start: int) -> int:
  """Return number of segments (>= 3) forming a pāda-by-pāda metrical Ṛk chain from ``start``,
  or 0 if ``segments[start:]`` is not a metrical pāda chain."""
  n = len(segments)
  if start >= n - 2:
    return 0
  counts: list[int] = []
  j = start
  while j < n and (j - start) < 4:
    seg = segments[j].strip()
    if _is_prose_formula_seg(seg) or (j > start and _is_prose_yajus_pair(segments[j - 1], seg)):
      return 0
    c = _akshara_count(seg)
    if not (6 <= c <= 13):
      return 0
    counts.append(c)
    if _ENDS_DOUBLE_DANDA_RE.search(seg) or (j + 1 < n and _is_prose_formula_seg(segments[j + 1])):
      if len(counts) >= 3 and 20 <= sum(counts) <= 56 and (max(counts) / max(1, min(counts))) <= 1.7:
        return len(counts)
      return 0
    if not seg.endswith("।"):
      return 0
    j += 1
  return 0


def _closes_cond_apodosis(feats: list[dict], i: int, segments: list[str]) -> bool:
  n = len(feats)
  cur, nxt = feats[i], feats[i + 1]
  if cur["has_finite_verb"] and not cur["opens_yad"] and nxt["opens_yad"]:
    return True
  if cur["has_finite_verb"] and not nxt["opens_tad"] and i > 0 and _is_metrical_pair(segments[i - 1], segments[i]):
    return True
  if not ((nxt["opens_tad"] or nxt["has_tad_any"]) and nxt["has_finite_verb"] and not nxt["opens_yad"]):
    return False
  if i + 2 < n and not feats[i + 2]["opens_yad"] and feats[i + 2]["words"][:1] in (["sa"], ["so"], ["prA"], ["pra"]) and not nxt["ends_numbered_double_danda"]:
    return False
  if i + 2 < n and nxt["ends_double_danda"] and not nxt["ends_numbered_double_danda"] and feats[i + 2]["ends_double_danda"] and not feats[i + 2]["opens_yad"]:
    return False
  return True


def _apply_test1_metrical(segments: list[str], feats: list[dict], merge_after: list[bool], verse_merge: list[bool], i: int) -> int | None:
  n = len(segments)
  cur, nxt = feats[i], feats[i + 1]
  chain_len = _verse_chain_length(segments, i) if nxt["ends_single_danda"] else 0
  if chain_len >= 3:
    for k in range(i, i + chain_len - 1):
      merge_after[k] = True
      verse_merge[k] = True
    return i + chain_len - 1
  if not _is_metrical_pair(segments[i], segments[i + 1]):
    return None
  pair_end = (
    nxt["ends_double_danda"]
    or (
      nxt["ends_single_danda"]
      and (i + 2 >= n or _is_prose_formula_seg(segments[i + 2]) or not _is_metrical_pair(segments[i + 1], segments[i + 2]))
    )
  )
  if not pair_end and nxt["ends_single_danda"]:
    j = i + 1
    while j + 1 < n and feats[j]["ends_single_danda"] and not _is_prose_formula_seg(segments[j + 1]) and _is_metrical_pair(segments[j], segments[j + 1]):
      j += 1
      if j - i > 24:
        break
    if (feats[j]["ends_double_danda"] or (j + 1 < n and _is_prose_formula_seg(segments[j + 1]))) and (j - i + 1) % 2 == 0:
      pair_end = True
  if pair_end:
    merge_after[i] = True
    verse_merge[i] = True
    return i + 1
  return None


def _group_units_with_flags(
  segments: list[str],
  *,
  use_local_hyphenator: bool = True,
  backend: ProofreaderBackend | None = None,
  translation_hint: str = "",
) -> list[tuple[str, bool]]:
  if len(segments) <= 1:
    return [(segments[0], False)] if segments else []

  feats = [_segment_features(s, use_local_hyphenator=use_local_hyphenator) for s in segments]
  n = len(segments)
  merge_after = [False] * (n - 1)
  verse_merge = [False] * (n - 1)

  open_cond = False
  open_quote = False
  i = 0
  while i < n - 1:
    cur, nxt = feats[i], feats[i + 1]
    if cur["ends_numbered_double_danda"]:
      open_cond = False
      open_quote = False
      i += 1
      continue

    if cur["ends_single_danda"] and not open_cond and not open_quote:
      next_i = _apply_test1_metrical(segments, feats, merge_after, verse_merge, i)
      if next_i is not None:
        if cur["opens_yad"] or nxt["opens_yad"]:
          if not nxt["has_finite_verb"]:
            open_cond = True
        i = next_i
        continue

    if cur["opens_yad"]:
      open_cond = True
    if cur["has_quote_open"] and not cur["has_iti"]:
      open_quote = True
    elif cur["has_iti"] and not (cur["opens_yad"] and cur["has_quote_open"]):
      open_quote = False

    closed_cond_here = False
    if open_cond:
      if cur["has_finite_verb"] and not cur["opens_yad"] and nxt["opens_yad"]:
        open_cond = False
        closed_cond_here = True
      elif cur["has_finite_verb"] and not nxt["opens_tad"] and i > 0 and merge_after[i - 1] and _is_metrical_pair(segments[i - 1], segments[i]):
        verse_merge[i - 1] = True
        open_cond = False
        closed_cond_here = True
      else:
        merge_after[i] = True
        if _closes_cond_apodosis(feats, i, segments):
          open_cond = False
        i += 1
        continue

    already_yad_block = i > 0 and merge_after[i - 1] and feats[i - 1]["opens_yad"]
    if not closed_cond_here and not already_yad_block and cur["words"][-1:] != ["svAhA"] and nxt["opens_yad"] and (not nxt["has_finite_verb"] or cur["has_tad_any"]) and (i + 1 == n - 1 or not feats[min(n - 1, i + 2)]["opens_tad"]):
      if not (cur["ends_single_danda"] and nxt["ends_single_danda"] and _is_metrical_pair(segments[i], segments[i + 1]) and nxt["has_finite_verb"]):
        merge_after[i] = True
        i += 1
        continue

    if open_quote:
      merge_after[i] = True
      if nxt["has_iti"]:
        open_quote = False
      i += 1
      continue
    if cur["has_iti"] and nxt["has_quote_open"] and nxt["has_iti"] and len(nxt["words"]) <= 5:
      merge_after[i] = True
      i += 1
      continue
    if cur["ends_absolutive"] or nxt["bare_purpose_or_atha"]:
      merge_after[i] = True
    i += 1

  if backend is not None and translation_hint.strip():
    merge_after = _refine_merges_with_llm(segments, merge_after, translation_hint, backend)

  blocks: list[tuple[str, bool]] = []
  buf = [segments[0]]
  is_verse_buf = False
  for idx_m, m_flag in enumerate(merge_after):
    if m_flag:
      buf.append(segments[idx_m + 1])
      if verse_merge[idx_m]:
        is_verse_buf = True
    else:
      blocks.append((("  \n" if is_verse_buf else " ").join(buf), is_verse_buf))
      buf = [segments[idx_m + 1]]
      is_verse_buf = False
  blocks.append((("  \n" if is_verse_buf else " ").join(buf), is_verse_buf))
  return blocks


def group_sense_unit_blocks(
  segments: list[str],
  *,
  use_local_hyphenator: bool = True,
  backend: ProofreaderBackend | None = None,
  translation_hint: str = "",
) -> list[str]:
  """Group consecutive daṇḍa-terminated segments into self-contained sense-unit blocks
  applying Tests 1–5 of ``/text_to_blocks`` (plus optional 14B LLM translation hint)."""
  return [
    txt for txt, _ in _group_units_with_flags(
      segments,
      use_local_hyphenator=use_local_hyphenator,
      backend=backend,
      translation_hint=translation_hint,
    )
  ]


def _akshara_count(text: str) -> int:
  return len(regex.findall(r"[\u0905-\u0914\u093e-\u094c]|(?<=[\u0915-\u0939])(?![\u093e-\u094d])", accent.strip_accents(text)))


def re_is_metrical(seg_a: str, seg_b: str) -> bool:
  """Check approximate akṣara-count parity for 2-half anuṣṭubh/gāyatrī/triṣṭubh verses."""
  va = _akshara_count(seg_a)
  vb = _akshara_count(seg_b)
  return (14 <= va <= 26) and abs(va - vb) <= 3


def _refine_merges_with_llm(
  segments: list[str],
  base_merges: list[bool],
  translation_hint: str,
  backend: ProofreaderBackend,
) -> list[bool]:
  """Zero-retyping index-only JSON refinement using ``ProofreaderBackend``."""
  seg_lines = "\n".join(f"[SEG {idx}] {s}" for idx, s in enumerate(segments))
  prompt = (
    "You are splitting Sanskrit segments into minimal self-contained sense-unit blocks.\n"
    "Never retype text. Inspect the numbered Sanskrit segments and translation below, and reply ONLY with JSON:\n"
    '{"merge_after": [<0-based indices i where SEG i and SEG i+1 belong in the SAME sense-unit block>]}\n\n'
    f"SEGMENTS:\n{seg_lines}\n\nTRANSLATION:\n{translation_hint.strip()}"
  )
  try:
    reply, _ = backend.generate_content(prompt)
    cleaned = regex.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", reply.strip())
    idxs = {int(x) for x in json.loads(cleaned).get("merge_after", [])}
    return [base_merges[i] or (i in idxs) for i in range(len(base_merges))]
  except Exception:
    return base_merges


def _split_structural_lines(chunk: str) -> list[tuple[str, str]]:
  """Separate unaccented chapter headings & colophons from prose/mantra spans."""
  out: list[tuple[str, str]] = []
  buf: list[str] = []

  def _flush():
    if buf:
      out.append(("text", "\n".join(buf)))
      buf.clear()

  for raw_ln in chunk.splitlines():
    s = raw_ln.strip()
    if s and _HEADING_LINE_RE.fullmatch(s):
      _flush()
      h_txt = s.lstrip("#").strip()
      out.append(("heading", f"## {h_txt}"))
    elif s and _COLOPHON_LINE_RE.match(s):
      _flush()
      out.append(("colophon", s))
    else:
      buf.append(raw_ln)
  _flush()
  return out


_FRONTMATTER_RE = regex.compile(r"\A(?:\+\+\+.*?\n\+\+\+|---.*?\n---)[ \t]*\n?", flags=regex.DOTALL)


def text_to_vipra_mula_blocks(
  content: str,
  *,
  use_local_hyphenator: bool = True,
  backend: ProofreaderBackend | None = None,
  clause_newlines: bool = True,
  convert_vedic_to_us: bool = True,
) -> str:
  """Convert bare Sanskrit Markdown paragraphs into sense-unit ``विश्वास-प्रस्तुतिः`` +
  ``मूलम्`` blocks per ``/text_to_blocks`` (preserving ``+++(...)+++`` & US accents in
  ``विश्वास-प्रस्तुतिः`` while keeping ``मूलम्`` clean and verbatim)."""
  fm_match = _FRONTMATTER_RE.match(content)
  prefix = fm_match.group(0) if fm_match else ""
  body_content = content[len(prefix):] if fm_match else content

  def _is_verse_like_block(unit_text: str) -> bool:
    unit_segs = split_into_danda_segments(unit_text)
    if len(unit_segs) >= 2 and any(s.strip().endswith("।") for s in unit_segs[:-1]) and _ENDS_DOUBLE_DANDA_RE.search(unit_segs[-1].strip()):
      return _is_metrical_pair(unit_segs[0], unit_segs[1]) if len(unit_segs) == 2 else _verse_chain_length(unit_segs, 0) == len(unit_segs)
    return False

  def _append_orphan_ref_to_last_block(ref_txt: str) -> bool:
    for idx in range(len(out_paras) - 1, -1, -1):
      if "<summary>मूलम्</summary>" in out_paras[idx]:
        out_paras[idx] = regex.sub(r"(\n</details>)", rf" {ref_txt}\1", out_paras[idx])
        return True
    return False

  out_paras: list[str] = []
  for chunk in regex.split(r"(\n\s*\n+)", body_content):
    cs = chunk.strip()
    if not cs or chunk.lstrip().startswith(("#", "<details", "+++", "---")):
      out_paras.append(chunk)
      continue
    if _PURE_REF_RE.fullmatch(cs) and _append_orphan_ref_to_last_block(cs):
      if out_paras and not out_paras[-1].strip():
        out_paras.pop()
      continue
    if not regex.search(r"[\u0905-\u0939]", chunk):
      out_paras.append(chunk)
      continue
    rendered_parts: list[str] = []
    for kind, body in _split_structural_lines(chunk):
      if kind in ("heading", "colophon"):
        rendered_parts.append(body)
        continue
      if not body.strip():
        continue
      segs = split_into_danda_segments(body.strip())
      units = _group_units_with_flags(segs, use_local_hyphenator=use_local_hyphenator, backend=backend)
      for unit, verse_flag in units:
        if not regex.search(r"[\u0905-\u0939]", unit):
          if unit.strip():
            rendered_parts.append(unit.strip())
          continue
        mula_txt = regex.sub(r"[ \t]{2,}", " ", _ANNO_RE.sub("", unit)).strip()
        vp_txt = unit.strip()
        is_verse = verse_flag or _is_verse_like_block(unit)
        if convert_vedic_to_us and regex.search(r"[\u0951\u0952]", vp_txt):
          vp_txt = accent.to_US_accents(vp_txt, pauses=r"[।॥,;]+")
        if backend is not None:
          vp_txt = proofread_text(vp_txt, backend=backend, clause_newlines=(clause_newlines and not is_verse), suggest_corrections=False)
        elif use_local_hyphenator:
          vp_txt = hyphene(vp_txt, clause_newlines=(clause_newlines and not is_verse))
        rendered_parts.append(
          f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{vp_txt}\n</details>\n\n"
          f"<details><summary>मूलम्</summary>\n\n{mula_txt}\n</details>"
        )
    out_paras.append("\n\n".join(rendered_parts))
  return prefix + "".join(out_paras)
