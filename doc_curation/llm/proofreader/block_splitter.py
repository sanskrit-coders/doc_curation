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

# 3rd-sg √i ("eti") verbs explicitly listed in /text_to_blocks/SKILL.md Test 4
_ETI_ROOT_VERBS_SLP = frozenset({
  "eti", "upEti", "paryeti", "aveti", "samaveti", "prEti", "aByeti", "anveti",
  "atyeti", "vyeti", "sameti", "punareti", "antareti", "apeti", "apyeti",
  "udeti", "pratyeti", "aDyeti", "Ayureti",
})

_YAD_FORMS_SLP = frozenset({
  "yaH", "yo", "yO", "ye", "yam", "yaM", "yAn", "yena", "yAByAm", "yEH",
  "yasmE", "yasmAt", "yasmAd", "yasya", "yasmin", "yat", "yad", "yAni",
  "yA", "yAm", "yAM", "yayA", "yasyE", "yasyAH", "yasyAm", "yatra", "yadA",
  "yaTA", "yadi", "yAvat", "yAvad",
})
_TAD_CORREL_SLP = frozenset({
  "sa", "saH", "so", "tO", "te", "tam", "taM", "tena", "tasmE", "tasmAt",
  "tasmAd", "tasya", "tasmin", "tat", "tad", "tAni", "sA", "tAm", "tayA",
  "tatra", "tadA", "taTA", "tarhi", "tAvat", "etad", "etat", "eza", "ezaH",
})
_QUOTE_OPENERS_SLP = (
  "abravIt", "ZbravIt", "uvAca", "Aha", "AhuH", "vadati", "vadanti",
  "brUyAt", "apfcCat", "prcCati",
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


def has_genuine_iti(seg: str, *, use_local_hyphenator: bool = True) -> bool:
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
  raw_segs = [s.strip() for s in split_to_sentences(masked) if s.strip()]
  restored = []
  for s in raw_segs:
    for k, v in masks.items():
      s = s.replace(k, v)
    restored.append(s)

  # Glue pure reference-number segments forward (leading refs) or backward (trailing (33))
  merged: list[str] = []
  pending_prefix = ""
  for seg in restored:
    if _TRAIL_NUM_REF_RE.fullmatch(seg) and merged:
      merged[-1] = f"{merged[-1]} {seg}"
      continue
    if _PURE_REF_RE.fullmatch(seg):
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


def _is_self_contained_yad(seg: str, words: list[str]) -> bool:
  """Check Test 2 exception: single-daṇḍa ``yad`` sentence that already contains
  its own ``tad``/``atha saH`` apodosis."""
  if not words or words[0] not in _YAD_FORMS_SLP:
    return False
  if "," in seg or ";" in seg:
    after = seg.split(",", 1)[-1] if "," in seg else seg.split(";", 1)[-1]
    aw = _clean_slp_words(after, use_local_hyphenator=False)
    if any(w in _TAD_CORREL_SLP or w == "aTa" for w in aw[:3]):
      return True
  return any(w in _TAD_CORREL_SLP for w in words[3:])


def _segment_features(seg: str, *, use_local_hyphenator: bool = True) -> dict:
  words = _clean_slp_words(seg, use_local_hyphenator=use_local_hyphenator)
  anno_bodies = [m.group(1) for m in _ANNO_RE.finditer(seg)]
  has_supplied_verb = any(
    w.endswith(("ti", "te", "ta", "t", "uH", "ati", "ate"))
    for body in anno_bodies
    for w in _clean_slp_words(body, use_local_hyphenator=False)
  )
  opens_yad = bool(words and (words[0] in _YAD_FORMS_SLP or (len(words) > 1 and words[0] in ("sa", "so", "aTa", "tad") and words[1] in _YAD_FORMS_SLP)))
  has_yad_any = any(w in _YAD_FORMS_SLP or any(w.startswith(yp) and len(w) > len(yp) + 2 for yp in ("yat", "yad", "yaT", "yadA", "yatr")) for w in words[:2])
  self_yad = _is_self_contained_yad(seg, words)
  opens_tad = bool(words and (words[0] in _TAD_CORREL_SLP or (len(words) > 1 and words[0] == "aTa" and words[1] in _TAD_CORREL_SLP)))
  has_quote_open = any(any(w.endswith(qo) or w == qo for qo in _QUOTE_OPENERS_SLP) for w in words)
  has_iti = has_genuine_iti(seg, use_local_hyphenator=use_local_hyphenator)
  ends_absolutive = bool(words and words[-1].endswith(("tvA", "wA", "QvA")) and not has_supplied_verb)
  has_finite_verb = has_supplied_verb or any(
    w.endswith(("ti", "te", "anti", "ante", "At", "Ita", "eta", "uH", "AsIt", "aBUt", "syAt", "syuH", "acazwa", "ajAnAt", "vyajAnAt"))
    for w in words
  )
  bare_purpose_or_atha = (
    not has_finite_verb
    and "eva" not in words
    and len(words) <= 4
    and bool(words)
    and (words[-1].endswith(("yE", "tyE", "zwye", "zwyE")) or words[0] == "aTa")
  )
  return {
    "words": words,
    "opens_yad": (opens_yad or has_yad_any) and not self_yad,
    "opens_tad": opens_tad,
    "has_quote_open": has_quote_open,
    "has_iti": has_iti,
    "ends_absolutive": ends_absolutive,
    "has_finite_verb": has_finite_verb,
    "bare_purpose_or_atha": bare_purpose_or_atha,
    "ends_double_danda": "॥" in seg[-8:],
    "ends_single_danda": seg.rstrip().endswith("।"),
  }


def group_sense_unit_blocks(
  segments: list[str],
  *,
  use_local_hyphenator: bool = True,
  backend: ProofreaderBackend | None = None,
  translation_hint: str = "",
) -> list[str]:
  """Group consecutive daṇḍa-terminated segments into self-contained sense-unit blocks
  applying Tests 1–5 of ``/text_to_blocks`` (plus optional 14B LLM translation hint)."""
  if len(segments) <= 1:
    return list(segments)

  feats = [_segment_features(s, use_local_hyphenator=use_local_hyphenator) for s in segments]
  n = len(segments)
  merge_after = [False] * (n - 1)

  open_cond = False
  open_quote = False
  for i in range(n - 1):
    cur, nxt = feats[i], feats[i + 1]

    # Test 1: Same Ṛk / verse (2-half verse: single daṇḍa followed by double daṇḍa with similar length)
    if cur["ends_single_danda"] and nxt["ends_double_danda"]:
      lw, rw = len("".join(cur["words"])), len("".join(nxt["words"]))
      if 16 <= lw <= 95 and 0.55 <= (lw / max(1, rw)) <= 1.8 and ("\n" in segments[i] or not cur["has_finite_verb"] or re_is_metrical(segments[i], segments[i + 1])):
        merge_after[i] = True
        continue

    # Update conditional & quotation states
    if cur["opens_yad"]:
      open_cond = True
    if cur["has_quote_open"] and not cur["has_iti"]:
      open_quote = True
    elif cur["has_iti"] and not (cur["opens_yad"] and cur["has_quote_open"]):
      open_quote = False

    # Test 2: Conditional-correlative (2a protasis->apodosis/continuation, 2b main->explanatory yad)
    if open_cond:
      merge_after[i] = True
      if nxt["opens_tad"] and nxt["has_finite_verb"] and not (i + 2 < n and not feats[i + 2]["opens_yad"] and feats[i + 2]["words"][:1] in (["sa"], ["so"], ["prA"], ["pra"])):
        # Keep extending if next-next continues the same Vedic phala-śruti chain
        if not (i + 2 < n and feats[i + 1]["ends_double_danda"] and feats[i + 2]["ends_double_danda"] and not feats[i + 2]["opens_yad"]):
          open_cond = False
      continue
    if nxt["opens_yad"] and (i + 1 == n - 1 or not feats[min(n - 1, i + 2)]["opens_tad"]):
      # (2b) Main statement first, explanatory yad second ("aryamRo vA etannakzatram | yatpUrve PalgunI |")
      merge_after[i] = True
      continue

    # Test 3 & 4: Quotation inside conditional & Same quotation
    if open_quote:
      merge_after[i] = True
      if nxt["has_iti"]:
        open_quote = False
      continue
    if cur["has_iti"] and nxt["has_quote_open"] and nxt["has_iti"] and len(nxt["words"]) <= 5:
      # Embedded Q&A resolution ("kas tAni niramimIteti || prajApatir iti brUyAt ||")
      merge_after[i] = True
      continue

    # Test 5: Sequential action (-tvA/-ya absolutive) or verb-less purpose/atha item
    if cur["ends_absolutive"] or nxt["bare_purpose_or_atha"]:
      merge_after[i] = True
      continue

  if backend is not None and translation_hint.strip():
    merge_after = _refine_merges_with_llm(segments, merge_after, translation_hint, backend)

  blocks: list[str] = []
  buf = [segments[0]]
  for i, m_flag in enumerate(merge_after):
    if m_flag:
      buf.append(segments[i + 1])
    else:
      blocks.append(" ".join(buf))
      buf = [segments[i + 1]]
  blocks.append(" ".join(buf))
  return blocks


def re_is_metrical(seg_a: str, seg_b: str) -> bool:
  """Check approximate akṣara-count parity for 2-half anuṣṭubh/gāyatrī/triṣṭubh verses."""
  va = len(regex.findall(r"[\u0905-\u0914\u093e-\u094c]|(?<=[\u0915-\u0939])(?![\u093e-\u094d])", accent.strip_accents(seg_a)))
  vb = len(regex.findall(r"[\u0905-\u0914\u093e-\u094c]|(?<=[\u0915-\u0939])(?![\u093e-\u094d])", accent.strip_accents(seg_b)))
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
  out_paras: list[str] = []
  for chunk in regex.split(r"(\n\s*\n+)", content):
    if not chunk.strip() or chunk.lstrip().startswith(("#", "<details", "+++", "---")) or not regex.search(r"[\u0905-\u0939]", chunk):
      out_paras.append(chunk)
      continue
    segs = split_into_danda_segments(chunk.strip())
    units = group_sense_unit_blocks(segs, use_local_hyphenator=use_local_hyphenator, backend=backend)
    rendered_groups: list[str] = []
    for unit in units:
      mula_txt = regex.sub(r"[ \t]{2,}", " ", _ANNO_RE.sub("", unit)).strip()
      vp_txt = unit.strip()
      if convert_vedic_to_us and regex.search(r"[\u0951\u0952]", vp_txt):
        vp_txt = accent.to_US_accents(vp_txt, pauses=r"[।॥,;]+")
      if backend is not None:
        vp_txt = proofread_text(vp_txt, backend=backend, clause_newlines=clause_newlines, suggest_corrections=False)
      elif use_local_hyphenator:
        vp_txt = hyphene(vp_txt, clause_newlines=clause_newlines)
      rendered_groups.append(
        f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{vp_txt}\n</details>\n\n"
        f"<details><summary>मूलम्</summary>\n\n{mula_txt}\n</details>"
      )
    out_paras.append("\n\n".join(rendered_groups))
  return "".join(out_paras)
