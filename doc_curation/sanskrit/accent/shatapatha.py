"""Śatapatha Brāhmaṇa (Mādhyandina) Vedic accent analysis, auditing, and US-notation conversion.

In the Mādhyandina Śatapatha Brāhmaṇa:
- ``᳘`` (U+1CD8) marks a syllable whose *following* syllable undergoes a pitch drop — either
  an udātta before an anudātta (dependent svarita) or pause, or an anudātta/udātta/svarita
  immediately before an independent svarita.
- In ``मूलम् - Weber`` (from TITUS), ``ॗ`` (U+0957) specifically marks the syllable preceding
  an *independent* svarita (jātya, kṣaipra, abhinihita, and ŚB's ``पा॰ ८.२.६`` sandhi svarita
  on udātta + word-initial anudātta vowel mergers), while ``᳘``/``᳟`` mark an udātta before
  an anudātta or pause.
- In ``मूलम् - श्रीधरादि``, ``᳘`` is used for all pitch-drop positions alike (often doubled
  around Mādhyandina *anunāsika*, e.g. ``स᳘ᳫं᳘स्थिते``).
- Consecutive udāttas suppress the mark on all but the last udātta before a pitch drop.

Because the ŚB → US direction is under-determined on its own while the US → ŚB forward
projection is deterministic, this module:
1. Projects a proposed ``पद-पाठः`` (US accents + ŚB ``पा॰ ८.२.४–६`` sandhi) forward into
   expected Weber and Śrīdharādi marks and audits every syllable against both sources.
2. Builds clean, US-accented ``विश्वास-प्रस्तुतिः`` text with inline ``[[OLD|NEW]]``
   suggestions for genuine two-source *vyatyasta* accents and matching summary headers.
"""

from __future__ import annotations

import dataclasses
import difflib
import functools
import os
import re
from pathlib import Path
from typing import Mapping, Sequence

from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.accent.reconciler import (
  DETAILS_RE,
  DEVANAGARI_VOWELS,
  PadapathaItem,
  US_SVARITA,
  US_UDATTA,
  _STOP_NORM,
  _VOWEL_FAMILY,
  _extract_vp_pieces,
  _flatten_pp_syllables,
  _map_pp_to_vp_syllables,
  _merged_valid_marks,
  _no_punct_between,
  _pp_member_starts,
  _skip_elided_avagraha_lead,
  apply_marks_to_token,
  format_padapatha_summary,
  format_suggested_vp_summary,
  has_us_accents,
  parse_padapatha_items,
  reconcile_markdown_blocks,
  syllables_with_marks,
)
from doc_curation.sanskrit.accent.validator import (
  AccentValidationIssue,
  validate_accented_markdown,
)

SCHEME = sanscript.SCHEMES[sanscript.DEVANAGARI]

SB_UDATTA_DROP = "\u1cd8"  # ᳘
SB_END_DROP = "\u1cdf"  # ᳟
WEBER_SVARITA_ANTE = "\u0957"  # ॗ
_YOGAVAAHAS = frozenset("ंःँᳫ᳭ᳮ\ua8f3")
_PAUSES = frozenset("।॥")


@dataclasses.dataclass(frozen=True)
class SbSyllable:
  """One normalized syllable extracted from a Śatapatha Brāhmaṇa ``मूलम्`` block."""

  key: tuple[str, str]  # (normalized_onset, vowel_family)
  mark: str  # 'H' (᳘/᳟), 'G' (ॗ in Weber), or ''
  before_pause: bool
  raw: str


@dataclasses.dataclass(frozen=True)
class SbSylAudit:
  """Per-syllable comparison of predicted ŚB marks against Weber and Śrīdharādi."""

  vp_syl_idx: int
  token: str
  us_mark: str
  exp_weber: str
  exp_shri: str
  act_weber: str | None
  act_shri: str | None
  weber_ok: bool | None
  shri_ok: bool | None
  pada_indices: tuple[int, ...]
  status: str  # 'both_ok', 'weber_ok', 'shri_ok', 'both_disagree', 'unaligned'


@dataclasses.dataclass(frozen=True)
class SbAuditReport:
  """Full two-source ŚB accent audit report for one kaṇḍikā."""

  syllables: list[SbSylAudit]
  disagree_pada_indices: list[int]
  weber_only_pada_indices: list[int]
  shri_only_pada_indices: list[int]
  unmapped_vp_syllables: list[tuple[str, int]]
  unflagged_vyatyasta_padas: list[int]
  possibly_spurious_vyatyasta_padas: list[int]


def strip_weber_footnotes(text: str) -> str:
  """Remove Markdown footnote definitions and inline ``[^wbr_N]`` refs from ``मूलम् - Weber``."""
  s = re.sub(r"(?m)^\[\^[^\]]+\]:.*$", "", text)
  s = re.sub(r"\[\^[^\]]+\]", "", s)
  return s.strip()


def strip_shri_pratika(text: str) -> str:
  """Remove recitation-linkage pratīka parentheticals like ``(न्न᳘)`` or ``(न्ते᳘ ऽथ)`` from Śrīdharādi."""
  s = re.sub(r"(?m)^\[\^[^\]]+\]:.*$", "", text)
  s = re.sub(r"\[\^[^\]]+\]", "", s)
  s = re.sub(r"\[\[!+\]\]", "", s)
  s = re.sub(r"\(\s*[\u0900-\u097f\u1cd0-\u1cff\u0951-\u0957\sऽ]{1,14}\)\s*", "", s)
  return s.strip()


def normalize_kanva_mula_for_sb(text: str) -> str:
  """Normalize Kāṇva ``svarupa.org`` print quirks while preserving ``᳘``/``॑`` accents for ŚB audit."""
  s = text.replace("\u200c", "").replace("\u200d", "").replace("`", "")
  # Rejoin broken line-wrap hyphens (`सौम्यादा᳘ज्य- भागाद्यन्ति` -> `सौम्यादा᳘ज्यभागाद्यन्ति`) while keeping compound `य᳘था-यथा`.
  s = re.sub(r"(?<=[\u0900-\u097f\u1cd0-\u1cff\ua8f3])[-–]\s+", "", s)
  s = re.sub(r"(?<=[\u0900-\u097f\u1cd0-\u1cff\ua8f3]):", "ः", s)
  return s


def normalize_sb_orthography(text: str) -> str:
  """Clean Mādhyandina and Kāṇva print quirks from unaccented or ŚB-accented text for ``विश्वास-प्रस्तुतिः``.

  - Strips footnotes, ``[[!!]]`` flags, and recitation-linkage pratīkas like ``(न्न᳘)``.
  - Strips all ŚB/Vedic accent marks so US accents can be filled cleanly from ``पद-पाठः``.
  - Removes Mādhyandina hiatus avagraha before independent vowels (``ऽउ``, ``ऽआ``, ``ऽए``, ``ऽइ``, ``ऽअ``, ``ऽओ``),
    while preserving true *pūrvarūpa* elision avagraha (``सो ऽग्निम्``, ``ते ऽस्य``).
  - Normalizes Kāṇva ``ꣳ`` (``U+A8F3``) / Mādhyandina *anunāsika* ``ᳫँ᳭``/``ᳫं``→``ं``,
    stray backticks, ZWJ/ZWNJ, Devanagari-adjacent ``:``→``ः``, line-wrap ``- ``, and consonant geminations.
  """
  s = normalize_kanva_mula_for_sb(strip_shri_pratika(text))
  s = accent.strip_accents(s)
  s = s.replace("᳟", "").replace("᳭", "").replace("ᳮ", "")
  # Normalize Mādhyandina and Kāṇva anunāsika ligatures.
  s = re.sub(r"ᳫ[ंँ]?", "ं", s)
  s = s.replace("\ua8f3", "ं")
  # Drop hiatus avagraha placed immediately before an independent Devanagari vowel (e.g. `ऽउ`, `ऽआ`, `ऽए`, `ऽअ`).
  s = re.sub(r"ऽ(?=[अआइईउऊऋॠएऐओऔ])", "", s)
  # Collapse Mādhyandina orthographic geminations.
  for src, dst in (
    ("स्स्फ", "स्फ"),
    ("व्व्र", "व्र"),
    ("व्वै", "वै"),
    ("व्वा", "वा"),
    ("व्वे", "वे"),
    ("व्वो", "वो"),
    ("व्वि", "वि"),
    ("व्वी", "वी"),
    ("व्वृ", "वृ"),
    ("व्वद", "वद"),
    ("व्वज्र", "वज्र"),
    ("व्वर्", "वर्"),
    ("र्व्व", "र्व"),
    ("र्द्ध", "र्ध"),
    ("र्म्म", "र्म"),
    ("र्न्न", "र्न"),
    ("र्य्य", "र्य"),
    ("र्त्त", "र्त"),
    ("र्द्दी", "र्दी"),
    ("र्द्द", "र्द"),
    ("क्लृ", "कॢ"),
  ):
    s = s.replace(src, dst)
  s = re.sub(r" {2,}", " ", s)
  return s.strip()


@functools.lru_cache(maxsize=2048)
def _extract_sb_syllables_cached(text: str, source: str = "weber") -> tuple[SbSyllable, ...]:
  clean = strip_weber_footnotes(text) if source == "weber" else normalize_kanva_mula_for_sb(strip_shri_pratika(text))
  # Normalize Devanagari letters while keeping ŚB marks intact.
  lets = SCHEME.split_vyanjanas_and_svaras(clean)
  syls: list[SbSyllable] = []
  onset = ""
  i = 0
  n = len(lets)
  while i < n:
    lt = lets[i]
    if not lt:
      i += 1
      continue
    if lt[0] in DEVANAGARI_VOWELS:
      raw_parts = [lt]
      has_g = WEBER_SVARITA_ANTE in lt
      has_h = (SB_UDATTA_DROP in lt) or (SB_END_DROP in lt)
      j = i + 1
      # Attach any following yogavāhas / Mādhyandina anunāsika (and their doubled marks) to this syllable.
      while j < n and lets[j] and (lets[j][0] in _YOGAVAAHAS or lets[j][0] in (SB_UDATTA_DROP, SB_END_DROP, WEBER_SVARITA_ANTE)):
        raw_parts.append(lets[j])
        if WEBER_SVARITA_ANTE in lets[j]:
          has_g = True
        if SB_UDATTA_DROP in lets[j] or SB_END_DROP in lets[j]:
          has_h = True
        j += 1
      # Check if a danda pause follows before the next vowel (scanning past trailing coda consonants like -म्॥).
      k = j
      before_pause = False
      while k < n and lets[k] and lets[k][0] not in DEVANAGARI_VOWELS:
        if any(p in lets[k] for p in _PAUSES):
          before_pause = True
          break
        k += 1
      v0 = accent.strip_accents(lt)[0]
      vf = _VOWEL_FAMILY.get(v0, "a")
      c_norm = "".join(_STOP_NORM.get(c, c) for c in onset)
      c_norm = re.sub(r"(.)\1+", r"\1", c_norm)
      raw_joined = "".join(raw_parts)
      if SB_END_DROP * 2 in raw_joined:
        # In Weber, double `᳟᳟` before `॥` is the pause-boundary representation of `ॗ` (`G`),
        # signaling an immediately following पा॰ ८.२.६ independent svarita after the pratīka `॥`.
        has_g = True
      if source == "weber":
        mk = "G" if has_g else ("H" if has_h else "")
      else:
        mk = "H" if (has_h or has_g) else ""
      syls.append(SbSyllable(key=(c_norm, vf), mark=mk, before_pause=before_pause, raw=raw_joined))
      onset = ""
      i = j
    else:
      cons = re.sub(r"[^\u0915-\u0939]", "", lt)
      if cons:
        onset += cons
      i += 1
  return tuple(syls)


def extract_sb_syllables(text: str, *, source: str = "weber") -> list[SbSyllable]:
  """Extract normalized syllables and ŚB pitch-drop marks (``'H'``/``'G'``/``''``) from Weber or Śrīdharādi."""
  return list(_extract_sb_syllables_cached(text, source))


def us_marks_to_sb_marks(
  us_marks: Sequence[str],
  *,
  style: str = "weber",
  next_first_mark: str | None = None,
) -> list[str]:
  """Deterministically project US syllable marks (``'U'``/``'S'``/``''``) to ŚB marks.

  Follows the exact 9-cell pitch-drop rule in ``svara-chihnAni.md`` (शतपथब्राह्मणे ऽङ्कनम्):
  - If the next syllable is ``'S'`` (independent svarita): ``'G'`` (``ॗ``) in Weber, ``'H'`` (``᳘``) in Śrīdharādi.
  - Else if the current syllable is ``'U'`` and the next is ``''`` (anudātta) or end-of-utterance: ``'H'`` (``᳘``/``᳟``).
  - Otherwise (including ``U`` followed by ``U``, or ``A``/``S`` followed by ``U``/``A``): ``''``.
  """
  n = len(us_marks)
  out: list[str] = []
  for i, cur in enumerate(us_marks):
    nxt = us_marks[i + 1] if i + 1 < n else next_first_mark
    if nxt == "S":
      out.append("G" if style == "weber" else "H")
    elif cur == "U" and (nxt == "" or nxt is None):
      out.append("H")
    else:
      out.append("")
  return out


def _align_key_sequences(
  src_keys: Sequence[tuple[str, str]],
  dst_keys: Sequence[tuple[str, str]],
) -> dict[int, int]:
  """Align two normalized ``(onset, vowel_family)`` syllable sequences, returning ``src_idx -> dst_idx``."""
  sm = difflib.SequenceMatcher(None, src_keys, dst_keys, autojunk=False)
  mapping: dict[int, int] = {}
  for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
      for o in range(i2 - i1):
        mapping[i1 + o] = j1 + o
    elif tag == "replace" and (i2 - i1) == (j2 - j1):
      for o in range(i2 - i1):
        # Allow minor onset differences (e.g. द/त, क्ष/ष, ब/व) when vowel family matches or aligns 1:1.
        if src_keys[i1 + o][1] == dst_keys[j1 + o][1] or (i2 - i1) <= 2:
          mapping[i1 + o] = j1 + o
  return mapping


def _compute_vp_syllable_marks(
  vp_clean: str,
  items: Sequence[PadapathaItem],
  weber_syls: Sequence[SbSyllable] = (),
  shri_syls: Sequence[SbSyllable] = (),
) -> tuple[
  list[dict],
  list[list[list[tuple[int, ...]]]],
  list[tuple[int, int]],
  list[str],
  list[str],
  list[tuple[int, ...]],
  list[tuple[str, int]],
]:
  """Align ``items`` onto ``vp_clean`` and compute both corrected (``ref``) and source (``ar``) US marks."""
  vp_pieces = _extract_vp_pieces(vp_clean)
  pp_keys, pp_meta, pp_refs, pp_ars = _flatten_pp_syllables(items)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(
    vp_clean, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, _pp_member_starts(items)
  )

  # Map VP syllables to Weber and Śrīdharādi syllables so we can detect ŚB पा॰ ८.२.६ svarita triggers.
  vp_to_weber = _align_key_sequences(vp_keys, [s.key for s in weber_syls]) if weber_syls else {}
  vp_to_shri = _align_key_sequences(vp_keys, [s.key for s in shri_syls]) if shri_syls else {}

  ref_marks: list[str] = []
  ar_marks: list[str] = []
  pada_map: list[tuple[int, ...]] = []
  unmapped: list[tuple[str, int]] = []

  flat_idx = 0
  for pi, pc in enumerate(vp_pieces):
    next_starts_av = (
      pi + 1 < len(vp_pieces)
      and vp_pieces[pi + 1]["old"].startswith("ऽ")
      and _no_punct_between(vp_clean, pc, vp_pieces[pi + 1])
    )
    for vsi, srcs in enumerate(pc_syl_sources[pi]):
      if not srcs:
        unmapped.append((pc["old"], vsi))
        ref_marks.append("")
        ar_marks.append("")
        pada_map.append(())
        flat_idx += 1
        continue
      src = srcs[0]
      if len(src) == 1:
        pp_si = src[0]
        ii, si = pp_meta[pp_si]
        if _skip_elided_avagraha_lead(pc, items[ii], si, vsi):
          ref_marks.append("")
          ar_marks.append("")
          pada_map.append((ii,))
        else:
          ref_marks.append(pp_refs[pp_si])
          ar_marks.append(pp_ars[pp_si] if items[ii].vyat else pp_refs[pp_si])
          pada_map.append((ii,))
      else:
        s1, s2 = src[-2], src[-1]
        i1, _ = pp_meta[s1]
        i2, si2 = pp_meta[s2]
        # Check whether Weber marks ॗ on the preceding syllable (or Shri marks ᳘ on a preceding anudātta)
        # to preserve ŚB's पा॰ ८.२.६ independent svarita on U + A vowel mergers.
        prev_has_svarita_cue = False
        if flat_idx > 0:
          pw = vp_to_weber.get(flat_idx - 1)
          if pw is not None:
            # Weber is aligned: trust it. `ॗ` is the explicit cue; Weber's TITUS text also sometimes prints `᳘`
            # on the anudātta before a पा॰ ८.२.६ svarita. An unmarked Weber syllable overrules a solo Śrīdharādi `᳘`.
            wm = weber_syls[pw].mark
            if wm == "G" or (wm == "H" and not weber_syls[pw].before_pause and ref_marks[flat_idx - 1] in ("", "S")):
              prev_has_svarita_cue = True
          else:
            ps = vp_to_shri.get(flat_idx - 1)
            if ps is not None and shri_syls[ps].mark == "H" and ref_marks[flat_idx - 1] in ("", "S"):
              prev_has_svarita_cue = True
        _, r_mk = _merged_valid_marks(
          pp_refs,
          pp_keys,
          pc,
          vsi,
          s1,
          s2,
          next_starts_av,
          allow_8_2_6_ekadesha_svarita=True,
          prefer_8_2_6_svarita=prev_has_svarita_cue,
          is_pAdAdi_s2=(si2 == 0),
        )
        # Source ('ar') merged mark uses ar accents for vyat items and ref accents for non-vyat items.
        eff_ars = [
          (pp_ars[k] if items[pp_meta[k][0]].vyat else pp_refs[k]) for k in range(len(pp_refs))
        ]
        _, a_mk = _merged_valid_marks(
          eff_ars,
          pp_keys,
          pc,
          vsi,
          s1,
          s2,
          next_starts_av,
          allow_8_2_6_ekadesha_svarita=True,
          prefer_8_2_6_svarita=prev_has_svarita_cue,
          is_pAdAdi_s2=(si2 == 0),
        )
        ref_marks.append(r_mk)
        ar_marks.append(a_mk)
        pada_map.append((i1, i2) if i1 != i2 else (i1,))
      flat_idx += 1

  return vp_pieces, pc_syl_sources, vp_meta, ref_marks, ar_marks, pada_map, unmapped


def build_sb_vp_from_padapatha(
  vp_clean_hyphenated: str,
  items: Sequence[PadapathaItem],
  *,
  weber_text: str = "",
  shri_text: str = "",
  orig_summary: str = "विश्वास-प्रस्तुतिः",
) -> tuple[str, str, list[tuple[str, int]]]:
  """Populate US accents and inline ``[[OLD|NEW]]`` suggestions on a clean hyphenated ŚB ``विश्वास-प्रस्तुतिः``.

  Returns ``(new_summary, accented_vp_body, unmapped_syllables)``.
  - Preserves ŚB's ``पा॰ ८.२.६`` independent svarita ``᳙`` where Weber marks ``ॗ`` on the preceding syllable.
  - Emits ``[[OLD|NEW]]`` on tokens containing solid *vyatyasta* padas (``OLD`` = source US accent, ``NEW`` = corrected US accent).
  - Formats ``new_summary`` with the same ``(N/P व्यत्यस्त-स्वराः)`` appendix as ``पद-पाठः`` when ``N > 0``.
  """
  weber_syls = extract_sb_syllables(weber_text, source="weber") if weber_text else []
  shri_syls = extract_sb_syllables(shri_text, source="shri") if shri_text else []

  vp_pieces, pc_syl_sources, _, ref_marks, ar_marks, pada_map, unmapped = _compute_vp_syllable_marks(
    vp_clean_hyphenated, items, weber_syls=weber_syls, shri_syls=shri_syls
  )

  # Compute per-piece offsets in flat syllable arrays.
  piece_offsets: list[int] = []
  cur = 0
  for pc in vp_pieces:
    piece_offsets.append(cur)
    cur += len(pc["keys"])

  out = list(vp_clean_hyphenated)
  for pi in range(len(vp_pieces) - 1, -1, -1):
    pc = vp_pieces[pi]
    if pc["is_sug"]:
      continue
    off = piece_offsets[pi]
    n_syl = len(pc["keys"])
    r_slice = ref_marks[off : off + n_syl]
    a_slice = ar_marks[off : off + n_syl]
    has_solid_vyat = any(
      items[ii].vyat and items[ii].solid
      for si in range(n_syl)
      for ii in pada_map[off + si]
    )
    new_tok = apply_marks_to_token(pc["old"], r_slice)
    if has_solid_vyat and a_slice != r_slice:
      old_tok = apply_marks_to_token(pc["old"], a_slice)
      rep = f"[[{old_tok}|{new_tok}]]"
    else:
      rep = new_tok
    if rep != pc["old"]:
      out[pc["start"] : pc["end"]] = list(rep)

  n_vyat = sum(1 for it in items if it.vyat)
  new_summary = format_suggested_vp_summary(orig_summary, n_vyat, len(items))
  return new_summary, "".join(out), unmapped


def audit_padapatha_against_sb(
  vp_clean_hyphenated: str,
  items: Sequence[PadapathaItem],
  weber_text: str,
  shri_text: str,
  *,
  next_first_mark: str | None = None,
) -> SbAuditReport:
  """Audit every syllable of a proposed ``पद-पाठः`` against both ``मूलम् - Weber`` and ``मूलम् - श्रीधरादि``.

  Projects the US saṁhitā marks derived from ``items`` forward into expected Weber (``H``/``G``/``''``)
  and Śrīdharādi (``H``/``''``) marks, and checks every syllable against both editions.
  A pada is a true *vyatyasta* candidate when **both** Weber and Śrīdharādi disagree with the
  predicted ŚB mark on one of its syllables (or on the syllable preceding an independent svarita).
  """
  weber_syls = extract_sb_syllables(weber_text, source="weber") if weber_text else []
  shri_syls = extract_sb_syllables(shri_text, source="shri") if shri_text else []

  vp_pieces, _, _, ref_marks, ar_marks, pada_map, unmapped = _compute_vp_syllable_marks(
    vp_clean_hyphenated, items, weber_syls=weber_syls, shri_syls=shri_syls
  )
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_tokens = [pc["old"] for pc in vp_pieces for _ in pc["keys"]]

  exp_weber = us_marks_to_sb_marks(ref_marks, style="weber", next_first_mark=next_first_mark)
  exp_shri = us_marks_to_sb_marks(ref_marks, style="shri", next_first_mark=next_first_mark)

  vp_to_weber = _align_key_sequences(vp_keys, [s.key for s in weber_syls]) if weber_syls else {}
  vp_to_shri = _align_key_sequences(vp_keys, [s.key for s in shri_syls]) if shri_syls else {}

  audits: list[SbSylAudit] = []
  disagree_padas: set[int] = set()
  disagree_syl_targets: list[tuple[int, ...]] = []
  weber_only_padas: set[int] = set()
  shri_only_padas: set[int] = set()
  n = len(ref_marks)

  for idx in range(n):
    ew = exp_weber[idx]
    es = exp_shri[idx]
    wi = vp_to_weber.get(idx)
    si = vp_to_shri.get(idx)
    aw = weber_syls[wi].mark if wi is not None else None
    as_ = shri_syls[si].mark if si is not None else None

    # Before a `॥` pause (mid-kaṇḍikā or end-of-kaṇḍikā), or across a word boundary between two udāttas
    # (`U` + `U` where the next word's initial `U` is also confirmed in the edition, e.g. `लोकाः᳘ प्र᳘तिष्ठिता`),
    # ŚB marks final udātta as `᳟`/`᳘` (`H`) even when the following syllable is `U`.
    wi_next = vp_to_weber.get(idx + 1) if idx + 1 < n else None
    si_next = vp_to_shri.get(idx + 1) if idx + 1 < n else None
    cross_word_uu = (
      idx + 1 < n
      and ref_marks[idx] == "U"
      and ref_marks[idx + 1] == "U"
      and pada_map[idx] != pada_map[idx + 1]
    )
    w_pause_u = (
      wi is not None
      and ref_marks[idx] == "U"
      and (
        weber_syls[wi].before_pause
        or (
          cross_word_uu
          and wi_next is not None
          and exp_weber[idx + 1] == "H"
          and weber_syls[wi_next].mark == "H"
        )
      )
    )
    s_pause_u = (
      si is not None
      and ref_marks[idx] == "U"
      and (
        shri_syls[si].before_pause
        or (
          cross_word_uu
          and si_next is not None
          and exp_shri[idx + 1] == "H"
          and shri_syls[si_next].mark == "H"
        )
      )
    )

    # At the very last syllable of a kaṇḍikā when next_first_mark is unknown (or Weber drops cross-kaṇḍikā ॗ),
    # allow boundary flexibility.
    if idx == n - 1 and next_first_mark is None:
      w_ok = None if aw is None else (
        aw == ew
        or (ref_marks[idx] == "U" and aw in ("H", "", "G"))
        or (ref_marks[idx] in ("", "S") and aw in ("", "G"))
      )
      s_ok = None if as_ is None else (
        as_ == es
        or (ref_marks[idx] == "U" and as_ in ("H", ""))
        or (ref_marks[idx] in ("", "S") and as_ in ("", "H"))
      )
    elif idx == n - 1 and next_first_mark == "S":
      # Weber frequently omits cross-kaṇḍikā ॗ before ॥ (or retains ᳘ on final udātta before pause).
      w_ok = None if aw is None else (aw in ("G", "") or (ref_marks[idx] == "U" and aw == "H"))
      s_ok = None if as_ is None else (as_ == es or (s_pause_u and as_ == "H"))
    else:
      # In Weber, `H` (᳘) occasionally substitutes for `G` (ॗ) before jātya/kṣaipra/8.2.6, and vice versa only if flagged.
      # When an independent svarita `S` immediately precedes an udātta `U` (`S + U` kampa, e.g. `अन्तर्याम्य᳙मृ᳓तः`,
      # `श᳓रीरं यो᳙ ऽग्नि᳓म्`), ŚB frequently omits pre-svarita `ॗ`/`᳘` on `idx` and marks `᳘` or `""` on `S` itself.
      pre_su_kampa = (
        idx + 2 < n
        and ref_marks[idx + 1] == "S"
        and len(pada_map[idx + 1]) >= 2
        and ref_marks[idx + 2] == "U"
      )
      at_su_kampa = (
        ref_marks[idx] == "S"
        and len(pada_map[idx]) >= 2
        and idx + 1 < n
        and ref_marks[idx + 1] == "U"
      )
      w_ok = None if aw is None else (
        aw == ew
        or (w_pause_u and aw == "H")
        or (pre_su_kampa and aw in ("G", ""))
        or (at_su_kampa and aw in ("", "H"))
      )
      s_ok = None if as_ is None else (
        as_ == es
        or (s_pause_u and as_ == "H")
        or (pre_su_kampa and as_ in ("H", ""))
        or (at_su_kampa and as_ in ("", "H"))
      )

    if w_ok is None and s_ok is None:
      status = "unaligned"
    elif (w_ok is True) and (s_ok is True or s_ok is None):
      status = "both_ok" if s_ok is True else "weber_ok"
    elif w_ok is True and s_ok is False:
      status = "weber_ok"
    elif s_ok is True and (w_ok is False or w_ok is None):
      status = "shri_ok"
    else:
      status = "both_disagree"

    # Attribute a mismatch on syllable `idx` to its own pada(s) — or to `pada_map[idx + 1]` when
    # the mismatch is caused by an independent svarita on `idx + 1` or a cross-pada ripple from a
    # `vyat` flip on `idx + 1`'s leading syllable.
    p_idxs = pada_map[idx]
    if status == "both_disagree":
      target_padas = p_idxs
      if idx + 1 < n and pada_map[idx + 1]:
        if ew == "G" or aw == "G":
          target_padas = pada_map[idx + 1]
        elif ar_marks[idx] == ref_marks[idx] and ar_marks[idx + 1] != ref_marks[idx + 1]:
          alt_ew = us_marks_to_sb_marks([ref_marks[idx]], style="weber", next_first_mark=ar_marks[idx + 1])[0]
          alt_es = us_marks_to_sb_marks([ref_marks[idx]], style="shri", next_first_mark=ar_marks[idx + 1])[0]
          if (aw is not None and aw == alt_ew) or (as_ is not None and as_ == alt_es):
            target_padas = pada_map[idx + 1]
      disagree_padas.update(target_padas)
      disagree_syl_targets.append(target_padas)
    elif status == "weber_ok" and s_ok is False:
      weber_only_padas.update(p_idxs)
    elif status == "shri_ok" and w_ok is False:
      shri_only_padas.update(p_idxs)

    audits.append(
      SbSylAudit(
        vp_syl_idx=idx,
        token=vp_tokens[idx],
        us_mark=ref_marks[idx],
        exp_weber=ew,
        exp_shri=es,
        act_weber=aw,
        act_shri=as_,
        weber_ok=w_ok,
        shri_ok=s_ok,
        pada_indices=p_idxs,
        status=status,
      )
    )

  flagged_vyat = {i for i, it in enumerate(items) if it.vyat}
  unflagged_set: set[int] = set()
  for tp in disagree_syl_targets:
    if not any(p in flagged_vyat for p in tp):
      unflagged_set.update(tp)
  unflagged = sorted(unflagged_set)
  spurious = sorted(flagged_vyat - disagree_padas)

  return SbAuditReport(
    syllables=audits,
    disagree_pada_indices=sorted(disagree_padas),
    weber_only_pada_indices=sorted(weber_only_padas),
    shri_only_pada_indices=sorted(shri_only_padas),
    unmapped_vp_syllables=unmapped,
    unflagged_vyatyasta_padas=unflagged,
    possibly_spurious_vyatyasta_padas=spurious,
  )


def format_padapatha_block(items: Sequence[PadapathaItem]) -> str:
  """Render a list of ``PadapathaItem`` objects into a ``<details><summary>पद-पाठः ...</summary>`` block."""
  n_vyat = sum(1 for it in items if it.vyat)
  hdr = format_padapatha_summary(n_vyat, len(items))
  lines: list[str] = []
  for it in items:
    if it.vyat:
      lines.append(f"- {it.ar} → **{it.ref}** ({it.prov})")
    else:
      lines.append(f"- {it.ref} ({it.prov})")
  body = "\n".join(lines)
  return f"<details><summary>{hdr}</summary>\n\n{body}\n</details>"


@dataclasses.dataclass(frozen=True)
class SbFileUpdateReport:
  """Result returned by :func:`apply_sb_kandika_updates`."""

  md_path: str
  updated_keys: list[str]
  preserved_us_keys: list[str]
  validation_issues: list[AccentValidationIssue]
  reconcile_logs: list[str]
  preserved_reconcile_logs: list[str]
  wrote: bool


@dataclasses.dataclass(frozen=True)
class _VpCluster:
  subidx: int
  vp_match: re.Match[str] | None
  weber_text: str
  shri_text: str
  insert_pos: int
  existing_pp_match: re.Match[str] | None
  mula_match: re.Match[str] | None = None
  mula_header: str = "मूलम् - श्रीधरादि"


def _extract_vp_clusters(part: str) -> list[_VpCluster]:
  dmatches = list(DETAILS_RE.finditer(part))
  clusters: list[_VpCluster] = []
  subidx = 0
  for i, m in enumerate(dmatches):
    if not m.group(1).strip().startswith("विश्वास-प्रस्तुतिः"):
      continue
    weber_text = ""
    shri_text = ""
    mula_hdr = "मूलम् - श्रीधरादि"
    insert_pos = m.end()
    k = i + 1
    while k < len(dmatches) and dmatches[k].group(1).strip().startswith("विश्वास-टिप्पनी"):
      insert_pos = dmatches[k].end()
      k += 1
    while k < len(dmatches):
      sum_k = dmatches[k].group(1).strip()
      if sum_k.startswith("मूलम्") and "Makoto" not in sum_k:
        if "Weber" in sum_k and not weber_text:
          weber_text = dmatches[k].group(2).strip()
        elif "श्रीधरादि" in sum_k and not shri_text:
          shri_text = dmatches[k].group(2).strip()
          mula_hdr = sum_k
        elif sum_k == "मूलम्" and not shri_text:
          shri_text = dmatches[k].group(2).strip()
          mula_hdr = sum_k
        insert_pos = dmatches[k].end()
        k += 1
      else:
        break
    existing_pp = None
    if k < len(dmatches) and dmatches[k].group(1).strip().startswith("पद-पाठः (यान्त्रिकः"):
      existing_pp = dmatches[k]
    clusters.append(
      _VpCluster(
        subidx=subidx,
        vp_match=m,
        weber_text=weber_text,
        shri_text=shri_text,
        insert_pos=insert_pos,
        existing_pp_match=existing_pp,
        mula_match=None,
        mula_header=mula_hdr,
      )
    )
    subidx += 1

  if not clusters:
    for i, m in enumerate(dmatches):
      if m.group(1).strip() == "मूलम्":
        existing_pp = None
        if i + 1 < len(dmatches) and dmatches[i + 1].group(1).strip().startswith("पद-पाठः (यान्त्रिकः"):
          existing_pp = dmatches[i + 1]
        clusters.append(
          _VpCluster(
            subidx=0,
            vp_match=None,
            weber_text="",
            shri_text=m.group(2).strip(),
            insert_pos=m.end(),
            existing_pp_match=existing_pp,
            mula_match=m,
            mula_header="मूलम्",
          )
        )
        break
  return clusters


def _coerce_padapatha_items(
  pp_spec: str | Sequence[str] | Sequence[PadapathaItem],
) -> list[PadapathaItem]:
  if isinstance(pp_spec, str):
    return parse_padapatha_items(pp_spec)
  seq = list(pp_spec)
  if not seq:
    return []
  if isinstance(seq[0], PadapathaItem):
    return [it for it in seq if isinstance(it, PadapathaItem)]
  return parse_padapatha_items("\n".join(str(ln) for ln in seq))


def _extract_non_managed_blocks(text: str) -> list[tuple[str, str]]:
  out: list[tuple[str, str]] = []
  for m in DETAILS_RE.finditer(text):
    hdr = m.group(1).strip()
    if hdr.startswith(("विश्वास-प्रस्तुतिः", "पद-पाठः (यान्त्रिकः")):
      continue
    raw = m.group(0)
    if hdr == "मूलम्" and raw.startswith("<details open>"):
      raw = "<details>" + raw[len("<details open>"):]
    out.append((hdr, raw))
  return out


def _apply_span_edits(text: str, edits: Sequence[tuple[int, int, str]]) -> str:
  out = text
  for s, e, rep in sorted(edits, key=lambda x: (x[0], x[1]), reverse=True):
    out = out[:s] + rep + out[e:]
  return out


def apply_sb_kandika_updates(
  md_path: str | os.PathLike[str],
  kandika_map: Mapping[
    str | tuple[str, int],
    tuple[str | None, str | Sequence[str] | Sequence[PadapathaItem]],
  ],
  *,
  preserve_existing_us: bool = True,
  dry_run: bool = False,
  strict: bool = True,
) -> SbFileUpdateReport:
  """Update Śatapatha Brāhmaṇa kaṇḍikā blocks in ``md_path`` cleanly with full validation.

  Parameters:
  - ``md_path``: path to a ``sarva-prastutiH`` ŚB Markdown file.
  - ``kandika_map``: maps each section heading (e.g. ``"०१"`` or ``"०१ अर्कस्यार्कत्वम्"``) —
    or ``(heading, vp_subidx)`` for multi-VP sections such as ``02/04/1.md`` — to
    ``(vp_clean_hyphenated, padapatha_spec)``, where ``padapatha_spec`` is a Markdown bullet
    string, sequence of ``- ...`` lines, or sequence of :class:`PadapathaItem` objects.
  - ``preserve_existing_us``: when ``True`` (default), any ``विश्वास-प्रस्तुतिः`` block that
    already contains US accents (``᳓``/``᳙``) is preserved byte-for-byte verbatim, and only its
    ``पद-पाठः`` block is inserted/updated right after its contiguous ``मूलम् - *`` run.
  - ``dry_run``: compute, validate, and reconcile without writing to disk.
  - ``strict``: when ``True`` (default), raise :class:`ValueError` before writing if any
    validation issue or non-preserved reconciler diff is found.

  Guarantees:
  - Inserts/replaces ``पद-पाठः`` immediately after the contiguous ``मूलम् - *`` run following each
    ``विश्वास-प्रस्तुतिः`` (ignoring trailing ``मूलम् - Makoto`` blocks in Kāṇḍa 12 and preserving
    section-level ``मूलम् - *``, ``सायणः``, ``हरिस्वामी``, ``Eggeling``, and pre-``##`` intro blocks
    verbatim).
  - Runs :func:`validate_accented_markdown` (which auto-enforces separated upasarga+tiṅanta rules on
    ŚB clusters) and :func:`reconcile_markdown_blocks` before writing.
  """
  path = Path(md_path)
  orig_txt = path.read_text(encoding="utf-8")
  if not kandika_map:
    return SbFileUpdateReport(
      md_path=str(path),
      updated_keys=[],
      preserved_us_keys=[],
      validation_issues=[],
      reconcile_logs=[],
      preserved_reconcile_logs=[],
      wrote=False,
    )

  parts = re.split(r"(?m)(?=^##\s+)", orig_txt)
  # Count leading numeral prefixes across sections so titled headers like `## ०१ अर्कस्यार्कत्वम्`
  # can also be addressed by `"०१"` when unambiguous.
  lead_counts: dict[str, int] = {}
  for part in parts:
    m_hdr = re.match(r"^##\s+([^\n]+)", part)
    if m_hdr:
      norm_hdr = re.sub(r"\s+", " ", m_hdr.group(1).strip())
      lead = norm_hdr.split()[0]
      lead_counts[lead] = lead_counts.get(lead, 0) + 1

  matched_map_keys: set[str | tuple[str, int]] = set()
  updated_keys: list[str] = []
  preserved_us_keys: list[str] = []
  preserved_vp_literals: list[str] = []
  out_parts: list[str] = []
  check_parts: list[str] = []

  for part in parts:
    m_hdr = re.match(r"^##\s+([^\n]+)", part)
    if not m_hdr:
      out_parts.append(part)
      check_parts.append(part)
      continue

    norm_hdr = re.sub(r"\s+", " ", m_hdr.group(1).strip())
    lead = norm_hdr.split()[0]
    lead_unique = lead != norm_hdr and lead_counts.get(lead, 0) == 1
    clusters = _extract_vp_clusters(part)
    if len(clusters) > 1 and (norm_hdr in kandika_map or (lead_unique and lead in kandika_map)):
      ambig = norm_hdr if norm_hdr in kandika_map else lead
      raise ValueError(
        f"Ambiguous section key {ambig!r} in {path}: section has {len(clusters)} VP blocks; "
        f"pass ({ambig!r}, subidx) tuple keys"
      )

    edits: list[tuple[int, int, str]] = []
    check_edits: list[tuple[int, int, str]] = []
    for cl in clusters:
      map_key: str | tuple[str, int] | None = None
      if (norm_hdr, cl.subidx) in kandika_map:
        map_key = (norm_hdr, cl.subidx)
      elif lead_unique and (lead, cl.subidx) in kandika_map:
        map_key = (lead, cl.subidx)
      elif len(clusters) == 1 and norm_hdr in kandika_map:
        map_key = norm_hdr
      elif len(clusters) == 1 and lead_unique and lead in kandika_map:
        map_key = lead

      if map_key is None:
        if cl.existing_pp_match is not None and cl.vp_match is not None and has_us_accents(cl.vp_match.group(2)):
          vp_m = cl.vp_match
          open_attr = " open" if "<details open>" in vp_m.group(0)[:20] else ""
          masked_vp = f"<details{open_attr}><summary>विश्वास-प्रस्तुतिः (स्वराः पूर्याः)</summary>{vp_m.group(2)}</details>"
          check_edits.append((vp_m.start(), vp_m.end(), masked_vp))
        continue

      matched_map_keys.add(map_key)
      key_label = f"{norm_hdr}[{cl.subidx}]" if len(clusters) > 1 else norm_hdr
      vp_clean, pp_spec = kandika_map[map_key]
      items = _coerce_padapatha_items(pp_spec)
      if not items:
        raise ValueError(f"Empty padapāṭha specification for {key_label!r} in {path}")
      pp_block = format_padapatha_block(items)

      vp_m = cl.vp_match
      existing_vp_has_us = (vp_m is not None) and has_us_accents(vp_m.group(2))
      if vp_m is not None and (preserve_existing_us or vp_clean is None) and existing_vp_has_us:
        preserved_us_keys.append(key_label)
        preserved_vp_literals.append(vp_m.group(0))
        # In the reconciliation-check copy, mark preserved hand-edited VP so non-preserved blocks are still strictly checked.
        open_attr = " open" if "<details open>" in vp_m.group(0)[:20] else ""
        masked_vp = f"<details{open_attr}><summary>विश्वास-प्रस्तुतिः (स्वराः पूर्याः)</summary>{vp_m.group(2)}</details>"
        check_edits.append((vp_m.start(), vp_m.end(), masked_vp))
      else:
        if vp_clean is None:
          raise ValueError(f"vp_clean_hyphenated is required for non-US section {key_label!r} in {path}")
        orig_summary = vp_m.group(1).strip() if vp_m is not None else "विश्वास-प्रस्तुतिः"
        vp_sum, vp_acc, unmapped = build_sb_vp_from_padapatha(
          vp_clean,
          items,
          weber_text=cl.weber_text,
          shri_text=cl.shri_text,
          orig_summary=orig_summary,
        )
        if unmapped:
          raise ValueError(f"Unmapped syllables in {key_label!r} ({path}): {unmapped}")
        # If the source `मूलम्` block was completely unaccented (no `᳘` or `॑`), tag `विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)`.
        mula_has_accents = bool(
          "\u1cd8" in (cl.weber_text + cl.shri_text)
          or "\u0951" in (cl.weber_text + cl.shri_text)
          or "\u0957" in cl.weber_text
        )
        if not mula_has_accents:
          vp_sum = "विश्वास-प्रस्तुतिः (यन्त्र-स्वरः)"
        if vp_m is not None:
          open_attr = " open" if "<details open>" in vp_m.group(0)[:20] else ""
          new_vp_block = f"<details{open_attr}><summary>{vp_sum}</summary>\n\n{vp_acc}\n</details>"
          edits.append((vp_m.start(), vp_m.end(), new_vp_block))
          check_edits.append((vp_m.start(), vp_m.end(), new_vp_block))
        else:
          assert cl.mula_match is not None
          mula_m = cl.mula_match
          new_vp_prefix = f"<details open><summary>{vp_sum}</summary>\n\n{vp_acc}\n</details>\n\n"
          collapsed_mula = f"<details><summary>{mula_m.group(1).strip()}</summary>{mula_m.group(2)}</details>"
          rep_span = new_vp_prefix + collapsed_mula
          edits.append((mula_m.start(), mula_m.end(), rep_span))
          check_edits.append((mula_m.start(), mula_m.end(), rep_span))

      if cl.existing_pp_match is not None:
        pp_edit = (cl.existing_pp_match.start(), cl.existing_pp_match.end(), pp_block)
      else:
        pp_edit = (cl.insert_pos, cl.insert_pos, "\n\n" + pp_block)
      edits.append(pp_edit)
      check_edits.append(pp_edit)
      updated_keys.append(key_label)

    out_parts.append(_apply_span_edits(part, edits) if edits else part)
    check_parts.append(_apply_span_edits(part, check_edits) if check_edits else part)

  unmatched = [k for k in kandika_map if k not in matched_map_keys]
  if unmatched:
    raise KeyError(f"Unmatched kandika_map keys in {path}: {unmatched}")

  new_txt = "".join(out_parts)
  check_txt = "".join(check_parts)

  # Verify all non-managed blocks (मूलम्-*, सायणः, हरिस्वामी, Eggeling, etc.) and preserved US VP blocks are verbatim.
  if _extract_non_managed_blocks(orig_txt) != _extract_non_managed_blocks(new_txt):
    raise AssertionError(f"Non-managed details blocks were modified while updating {path}")
  for lit in preserved_vp_literals:
    if lit not in new_txt:
      raise AssertionError(f"Preserved US-accented विश्वास-प्रस्तुतिः block was modified in {path}")

  issues = validate_accented_markdown(new_txt)
  rec_txt, rec_logs = reconcile_markdown_blocks(check_txt)
  if rec_txt != check_txt and not rec_logs:
    rec_logs = ["reconciler modified text without log entries"]

  preserved_rec_logs: list[str] = []
  if preserved_us_keys:
    _, full_rec_logs = reconcile_markdown_blocks(new_txt)
    preserved_rec_logs = [lg for lg in full_rec_logs if lg not in rec_logs]

  if strict and (issues or rec_logs):
    details_parts: list[str] = []
    if issues:
      details_parts.append(f"{len(issues)} validation issue(s): {issues[:5]}")
    if rec_logs:
      details_parts.append(f"{len(rec_logs)} reconciler diff(s): {rec_logs[:5]}")
    raise ValueError(f"Refusing to write {path}: " + "; ".join(details_parts))

  wrote = False
  if not dry_run:
    path.write_text(new_txt, encoding="utf-8")
    wrote = True

  return SbFileUpdateReport(
    md_path=str(path),
    updated_keys=updated_keys,
    preserved_us_keys=preserved_us_keys,
    validation_issues=issues,
    reconcile_logs=rec_logs,
    preserved_reconcile_logs=preserved_rec_logs,
    wrote=wrote,
  )
