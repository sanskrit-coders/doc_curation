"""Reconcile US-accented ``विश्वास-प्रस्तुतिः`` inline ``[[OLD|NEW]]`` suggestions against ``पद-पाठः (यान्त्रिकः)``."""

from __future__ import annotations

import dataclasses
import difflib
import functools
import re
from typing import AbstractSet, Sequence

from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

SCHEME = sanscript.SCHEMES[sanscript.DEVANAGARI]

US_UDATTA = "\u1cd3"  # ᳓
US_SVARITA = "\u1cd9"  # ᳙

DEVANAGARI_VOWELS = frozenset("अआइईउऊऋॠऌॡएऐओऔ")
_VOWEL_FAMILY = {
  "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u",
  "ऋ": "r", "ॠ": "r", "ऌ": "l", "ॡ": "l", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}
_STOP_NORM = {
  "ख": "क", "घ": "ग", "छ": "च", "झ": "ज", "ठ": "ट", "ढ": "ड",
  "ण": "न", "ञ": "न", "ङ": "न", "थ": "त", "ध": "द", "फ": "प", "भ": "ब", "श": "स", "ष": "स", "ळ": "ड",
}
_SAME_ONSET_PAIRS = frozenset({
  ("स", "च"), ("च", "स"), ("द", "न"), ("द", "ल"), ("द", "ज"),
  ("त", "च"), ("ग", "क"), ("ह", "ग"), ("ह", "द"), ("ह", "ड"), ("ह", "ब"),
  ("सत", "सट"), ("सट", "सत"), ("त", "सट"), ("सट", "त"), ("त", "सत"), ("सत", "त"),
  ("व", "रव"), ("रव", "व"), ("व", "गव"), ("गव", "व"),
})
_COMPOUND_STOP_VOICE_PAIRS = frozenset({
  ("त", "द"), ("द", "त"), ("प", "ब"), ("ब", "प"), ("ट", "ड"), ("ड", "ट"), ("क", "ग"),
})

DETAILS_RE = re.compile(r"<details(?:\s+open)?><summary>([^<]*)</summary>(.*?)</details>", re.S)
LEAF_DETAILS_RE = re.compile(
  r"<details(?:\s+open)?><summary>([^<]*)</summary>([^<]*(?:<(?!/?details\b)[^<]*)*)</details>",
  re.S | re.I,
)
PP_HEADER_RE = re.compile(r"^पद-पाठः \(यान्त्रिकः(?:\s*-\s*(\d+)/(\d+)\s*व्यत्यस्त-स्वराः)?\)$")
_VP_SUMMARY_TAG_RE = re.compile(
  r"\s*\((?:स्वराः पूर्याः|यन्त्र-स्वरः|स्वराः व्यत्यस्ताः[^)]*|\d+/\d+\s*व्यत्यस्त-स्वराः)\)\s*"
)
_VP_VYAT_SUMMARY_RE = re.compile(r"\((\d+)/(\d+)\s*व्यत्यस्त-स्वराः\)")
_SUG_SPAN_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
_PIECE_PAT = re.compile(
  r"\[\[([^|\]]+)\|([^\]]+)\]\]|[\u0900-\u0963\u0969\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-ऽ]+"
)


@dataclasses.dataclass(frozen=True)
class PadapathaItem:
  """One bullet entry from a ``पद-पाठः (यान्त्रिकः)`` block."""

  ar: str
  ref: str
  prov: str
  vyat: bool
  solid: bool


def has_us_accents(text: str) -> bool:
  """Return True if ``text`` contains Vedic US udātta (᳓) or svarita (᳙) marks."""
  return US_UDATTA in text or US_SVARITA in text


@functools.lru_cache(maxsize=65536)
def sanitize_us_accents(text: str) -> str:
  """Collapse duplicate adjacent Vedic accent marks without removing distinct ones."""
  return re.sub(r"[\u1cd0-\u1cff\u0951\u0952]+", lambda m: "".join(dict.fromkeys(m.group(0))), text)


@functools.lru_cache(maxsize=65536)
def bare_devanagari(text: str) -> str:
  """Strip accents and non-Devanagari characters for strict bare-form equality checks."""
  return re.sub(r"[^\u0900-\u097f]", "", accent.strip_accents(text))


@functools.lru_cache(maxsize=65536)
def _syllables_with_marks_cached(text: str) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
  clean = sanitize_us_accents(text).replace("-", "")
  lets = SCHEME.split_vyanjanas_and_svaras(clean)
  keys: list[tuple[str, str]] = []
  mks: list[str] = []
  onset = ""
  for lt in lets:
    if not lt:
      continue
    if lt[0] in DEVANAGARI_VOWELS:
      v0 = accent.strip_accents(lt)[0]
      vf = _VOWEL_FAMILY.get(v0, "a")
      mk = "S" if US_SVARITA in lt else ("U" if US_UDATTA in lt else "")
      c_norm = "".join(_STOP_NORM.get(c, c) for c in onset)
      c_norm = re.sub(r"(.)\1+", r"\1", c_norm)
      keys.append((c_norm, vf))
      mks.append(mk)
      onset = ""
    else:
      cons = re.sub(r"[^\u0915-\u0939]", "", lt)
      if cons:
        onset += cons
  return tuple(keys), tuple(mks)


def syllables_with_marks(text: str) -> tuple[list[tuple[str, str]], list[str]]:
  """Return normalized ``(onset, vowel_family)`` syllable keys and US accent marks (``'U'``/``'S'``/``''``)."""
  keys, mks = _syllables_with_marks_cached(text)
  return list(keys), list(mks)


def apply_marks_to_token(tok: str, new_marks: Sequence[str]) -> str:
  """Apply per-syllable US marks onto Devanagari ``tok`` preserving consonants/mātrās via ``SCHEME.join_strings``."""
  clean = sanitize_us_accents(tok)
  # Protect virāma + independent-vowel hiatus (e.g. `र्ऋ` in नाभिर्ऋतस्य) from being coalesced into a matra by
  # SCHEME.join_strings, via a ZWNJ sentinel that is stripped again below.
  clean = re.sub(r"्(?=[अआइईउऊऋॠऌॡएऐओऔ])", "्\u200c", clean)
  lets = SCHEME.split_vyanjanas_and_svaras(clean)
  out: list[str] = []
  si = 0
  for lt in lets:
    if not lt:
      continue
    if lt[0] in DEVANAGARI_VOWELS and si < len(new_marks):
      base = re.sub(r"[\u1cd0-\u1cff\u0951\u0952]", "", lt)
      mk = new_marks[si]
      u_char = US_UDATTA if mk == "U" else (US_SVARITA if mk == "S" else "")
      out.append(base + u_char)
      si += 1
    else:
      out.append(lt)
  if si != len(new_marks):
    raise ValueError(f"Syllable count mismatch for {tok!r}: {si} != {len(new_marks)}")
  # Must rejoin separated consonant+vowel elements via SCHEME.join_strings, never "".join(out).
  res = SCHEME.join_strings(out).replace("\u200c", "") if "\u200c" not in tok else SCHEME.join_strings(out)
  if bare_devanagari(res) != bare_devanagari(tok):
    raise ValueError(f"Bare Devanagari drifted for {tok!r} -> {res!r}")
  return res


@functools.lru_cache(maxsize=65536)
def is_solid_provenance(prov: str) -> bool:
  """Return True when a padapāṭha provenance note cites solid Vedic/Pāṇinian authority (not bare ``*MW*``)."""
  # Accept both canonical Devanagari abbreviation sign पा॰ (U+0970) and legacy पा\u0966 (U+0966).
  prov_n = prov.replace("पा\u0966", "पा॰")
  if any(
    c in prov_n
    for c in ("*TS*", "*RV*", "*TB*", "*AV*", "*VS-M*", "*VS-K*", "*VS*", "*KS*", "*MS*", "*ŚB*", "*SB-M*", "*SB-K*", "*TK*", "*Macdonell*", "*Lanman*")
  ):
    return True
  if any(
    r in prov_n
    for r in (
      "पा॰ २.४.",
      "पा॰ ३.१.",
      "पा॰ ३.२.",
      "पा॰ ३.३.",
      "पा॰ ३.४.",
      "पा॰ ४.१.",
      "पा॰ ४.२.",
      "पा॰ ४.३.",
      "पा॰ ४.४.",
      "पा॰ ५.१.",
      "पा॰ ५.२.",
      "पा॰ ५.३.",
      "पा॰ ५.४.",
      "पा॰ ६.१.१६",
      "पा॰ ६.१.१७",
      "पा॰ ६.१.१८",
      "पा॰ ६.१.१९",
      "पा॰ ६.१.२०",
      "पा॰ ६.१.२००",
      "पा॰ ६.१.२१",
      "पा॰ ६.१.२२",
      "पा॰ ६.२.",
      "पा॰ ६.४.",
      "पा॰ ८.१.२८",
      "पा॰ ८.१.१८",
      "पा॰ ८.१.३",
      "पा॰ ८.१.१९",
      "पा॰ ८.१.३०",
      "पा॰ ८.१.५९",
      "पा॰ ८.१.६३",
      "पा॰ ८.१.६५",
      "पा॰ ८.१.७०",
      "पा॰ ८.१.७१",
      "पा॰ ८.१.७२",
    )
  ):
    return True
  if "पा॰ ६.१.१५८" in prov_n and "अनाम्नातम्" not in prov_n:
    return True
  if ("पा॰ ८.१.६६" in prov_n or "पा॰ ८.१.३४" in prov_n) and any(
    x in prov_n for x in ("अनेकोदात्त", "अनुदात्त-दोषः", "यद्वृत्तान्नित्यम्", "हि च", "*TS*", "*RV*", "*TB*", "*TK*", "पा॰ ३.", "पा॰ ६.")
  ):
    return True
  return False


def parse_padapatha_items(pp_body: str) -> list[PadapathaItem]:
  """Parse bullet lines of a ``पद-पाठः (यान्त्रिकः)`` block into structured items."""
  items: list[PadapathaItem] = []
  for line in pp_body.splitlines():
    if not line.startswith("- "):
      continue
    m_arr = re.match(r"^-\s+(.*?)\s+→\s+\*\*(.*?)\*\*\s+\((.*)\)$", line)
    if m_arr:
      ar, ref, prov = m_arr.group(1).strip(), m_arr.group(2).strip(), m_arr.group(3).strip()
      items.append(PadapathaItem(ar=ar, ref=ref, prov=prov, vyat=True, solid=is_solid_provenance(prov) and ref != "?"))
    else:
      m_pl = re.match(r"^-\s+([^\s(]+)\s+\((.*)\)$", line)
      if m_pl:
        p, prov = m_pl.group(1).strip(), m_pl.group(2).strip()
        items.append(PadapathaItem(ar=p, ref=p, prov=prov, vyat=False, solid=is_solid_provenance(prov)))
      else:
        p = line[2:].split(" (")[0].strip()
        items.append(PadapathaItem(ar=p, ref=p, prov="", vyat=False, solid=False))
  return items


def format_padapatha_summary(n_vyat: int, p_total: int) -> str:
  """Format the canonical ``<summary>`` title for ``पद-पाठः (यान्त्रिकः)``."""
  if n_vyat > 0:
    return f"पद-पाठः (यान्त्रिकः - {n_vyat}/{p_total} व्यत्यस्त-स्वराः)"
  return "पद-पाठः (यान्त्रिकः)"


def format_filled_vp_summary(
  orig_summary: str,
  n_vyat: int,
  p_total: int,
  *,
  mula_has_accents: bool = True,
) -> str:
  """Format the ``<summary>`` title of a ``विश्वास-प्रस्तुतिः`` block after filling US accents from ``पद-पाठः``."""
  base = _VP_SUMMARY_TAG_RE.sub("", orig_summary).strip()
  base = re.sub(r"\s{2,}", " ", base) or "विश्वास-प्रस्तुतिः"
  if not mula_has_accents:
    return f"{base} (यन्त्र-स्वरः)"
  if n_vyat > 0 and p_total > 0:
    return f"{base} ({n_vyat}/{p_total} व्यत्यस्त-स्वराः)"
  return base


def format_suggested_vp_summary(
  orig_summary: str,
  n_vyat: int,
  p_total: int,
) -> str:
  """Format ``विश्वास-प्रस्तुतिः`` summary with the same ``(N/P व्यत्यस्त-स्वराः)`` appendix as ``पद-पाठः``."""
  return format_filled_vp_summary(orig_summary, n_vyat, p_total, mula_has_accents=True)


def _same_onset(c1: str, c2: str) -> bool:
  if c1 == c2:
    return True
  if not c1 or not c2:
    return False
  return c1[-1] == c2[-1] or (c1, c2) in _SAME_ONSET_PAIRS or (c1[-1], c2[-1]) in _SAME_ONSET_PAIRS


def _no_punct_between(vp_work: str, pc_a: dict, pc_b: dict) -> bool:
  """Return True when only spaces/newlines/editorial notes (not clause punctuation) separate two tokens."""
  gap = vp_work[pc_a["end"]:pc_b["start"]]
  gap_clean = re.sub(r"\+\+\+.*?\+\+\+", "", gap, flags=re.S)
  return not re.search(r"[,;।॥?!\|०-९\d]", gap_clean)


def unwrap_stale_suggestions(
  vp_body: str,
  items: Sequence[PadapathaItem],
  *,
  extra_invalid_olds: AbstractSet[str] = frozenset(),
) -> tuple[str, list[str]]:
  """Unwrap known bogus or ambiguous multi-occurrence suggestions before realignment."""
  logs: list[str] = []

  def _repl(m: re.Match[str]) -> str:
    o, n = m.group(1), m.group(2)
    if not has_us_accents(o + n) or bare_devanagari(o) != bare_devanagari(n):
      return m.group(0)
    ob = bare_devanagari(o)
    if o in extra_invalid_olds:
      still_vyat = any(it.vyat and bare_devanagari(it.ar) == ob and it.ref == n for it in items)
      if not still_vyat:
        logs.append(f"REMOVE_BOGUS_SUG: [[{o}|{n}]]")
        return o
    matching = [it for it in items if bare_devanagari(it.ar) == ob]
    if len(matching) > 1 and any(not it.vyat for it in matching):
      logs.append(f"UNWRAP_AMBIG_MULTI_FOR_REALIGN: [[{o}|{n}]]")
      return o
    return m.group(0)

  return _SUG_SPAN_RE.sub(_repl, vp_body), logs


def _extract_vp_pieces(vp_work: str) -> list[dict]:
  chars = list(vp_work)
  for m in re.finditer(r"\+\+\+.*?\+\+\+|\[\[(?:\?+|!+)\]\]", vp_work, re.S):
    for k in range(m.start(), m.end()):
      chars[k] = " "
  masked = "".join(chars)

  bold_spans = [(m.start(1), m.end(1)) for m in re.finditer(r"\*\*([^\*\n]+)\*\*", vp_work)]
  vp_pieces: list[dict] = []
  pending_yan: tuple[int, str] | None = None
  for m in _PIECE_PAT.finditer(masked):
    s, e = m.start(), m.end()
    if m.group(1) is not None:
      o, n, is_sug = m.group(1), m.group(2), True
    else:
      o, n, is_sug = m.group(0), m.group(0), False
    if not re.search(r"[\u0905-\u0939]", o):
      continue
    ks, old_mks = syllables_with_marks(o)
    _, new_mks = syllables_with_marks(n)
    if not ks:
      if not is_sug and o.endswith(("य्", "व्", "र्", "ल्")):
        cons = re.sub(r"[^\u0915-\u0939]", "", o)
        cons_stem = re.sub(r"[यवरल]$", "", cons)
        c_norm = re.sub(r"(.)\1+", r"\1", "".join(_STOP_NORM.get(c, c) for c in cons_stem))
        pending_yan = (e, c_norm)
      else:
        pending_yan = None
      continue
    if len(new_mks) != len(ks):
      pending_yan = None
      continue
    prev_yan_onset: str | None = None
    if (
      pending_yan is not None
      and ks[0][0] == ""
      and _no_punct_between(vp_work, {"end": pending_yan[0]}, {"start": s})
    ):
      prev_yan_onset = pending_yan[1]
    pending_yan = None
    avagraha_after: set[int] = set()
    let_si = 0
    for lt in SCHEME.split_vyanjanas_and_svaras(sanitize_us_accents(o)):
      if not lt:
        continue
      if lt[0] in DEVANAGARI_VOWELS:
        let_si += 1
      elif lt == "ऽ" and let_si > 0:
        avagraha_after.add(let_si - 1)
    prev_ends_semi = bool(
      vp_pieces
      and vp_pieces[-1]["ends_semi"]
      and ks[0][0] == ""
      and _no_punct_between(vp_work, vp_pieces[-1], {"start": s})
    )
    vp_pieces.append({
      "start": s,
      "end": e,
      "old": o,
      "new": n,
      "is_sug": is_sug,
      "bold": any(ba <= s and e <= bb for ba, bb in bold_spans),
      "keys": ks,
      "old_mks": old_mks,
      "new_mks": new_mks,
      "avagraha_after": avagraha_after,
      "ends_semi": o.endswith(("य्", "व्", "र्", "ल्")),
      "prev_yan_onset": prev_yan_onset,
      "prev_ends_semi": prev_ends_semi,
    })
  return vp_pieces


def _flatten_pp_syllables(items: Sequence[PadapathaItem]) -> tuple[list, list, list, list]:
  pp_keys, pp_meta, pp_refs, pp_ars = [], [], [], []
  for ii, it in enumerate(items):
    use_ref = it.ref if it.ref != "?" else it.ar
    ks_r, mks_r = syllables_with_marks(use_ref)
    _, mks_a = syllables_with_marks(it.ar)
    if len(mks_a) != len(ks_r):
      mks_a = [""] * len(ks_r)
    for si, (kv, mkr, mka) in enumerate(zip(ks_r, mks_r, mks_a)):
      pp_keys.append(kv)
      pp_meta.append((ii, si))
      pp_refs.append(mkr)
      pp_ars.append(mka)
  return pp_keys, pp_meta, pp_refs, pp_ars


def _refine_opcodes(ops: list[list], pp_keys: list, pp_meta: list, vp_keys: list) -> list[list]:
  # 1. Prevent deleted onsetless word (e.g. अति, अपि) from stealing identical vowel of next word.
  for idx in range(len(ops) - 2):
    op1, op2, op3 = ops[idx], ops[idx + 1], ops[idx + 2]
    if op1[0] == "equal" and op2[0] == "delete" and op3[0] == "equal":
      i1, i2, j1, j2 = op1[1:]
      d1, d2 = op2[1], op2[2]
      e1, _, ej1, _ = op3[1], op3[2], op3[3], op3[4]
      if i2 > i1 and d2 > d1 and e1 == d2:
        while (
          i2 > i1
          and d2 > d1
          and pp_keys[i2 - 1][0] == ""
          and pp_keys[i2 - 1] == pp_keys[d2 - 1]
          and pp_meta[d2 - 1][0] == pp_meta[d2][0]
        ):
          i2 -= 1
          d2 -= 1
          j2 -= 1
          e1 -= 1
          ej1 -= 1
        op1[2], op1[4] = i2, j2
        op2[1], op2[2], op2[3], op2[4] = i2, d2, j2, j2
        op3[1], op3[3] = e1, ej1

  # 2. Repair yaṇ sandhi emitted as insert(1), equal(k), delete(>=2).
  refined: list[list] = []
  idx = 0
  while idx < len(ops):
    if idx + 2 < len(ops):
      o1, o2, o3 = ops[idx], ops[idx + 1], ops[idx + 2]
      if (
        o1[0] == "insert"
        and o2[0] == "equal"
        and o3[0] == "delete"
        and (o1[4] - o1[3]) == 1
        and (o3[2] - o2[1]) >= (o2[2] - o2[1]) + 2
        and pp_keys[o3[2] - (o2[2] - o2[1]) : o3[2]] == vp_keys[o2[3] : o2[4]]
      ):
        eq_len = o2[2] - o2[1]
        mid_p = o3[2] - eq_len
        refined.append(["replace", o2[1], mid_p, o1[3], o1[4]])
        refined.append(["equal", mid_p, o3[2], o2[3], o2[4]])
        idx += 3
        continue
    refined.append(ops[idx])
    idx += 1

  # 3. Coalesce impossible `pp < vp` ops (`insert` or `replace` with `i2 - i1 < j2 - j1`) caused by
  #    `SequenceMatcher` jumping to a later repeated syllable/word (`लोकम्पृणाम्` #1 -> #2, lone `('व','a')`,
  #    or `ऋतवः + वै -> ऋतवो वा`), absorbing adjacent `equal` + `delete`/`replace` spans until `pp >= vp`.
  #    Prefer rightward merge (`short_pp + equal + delete/replace`) before leftward merge so an `insert + equal + delete`
  #    pair does not steal a preceding already-balanced `2->1` yaṇ merge.
  def _is_short_pp(op: list) -> bool:
    if op[0] == "insert" and ((op[1] == 0 and op[3] == 0) or (op[2] == len(pp_keys) and op[4] == len(vp_keys))):
      return False
    return op[0] in ("insert", "replace") and (op[2] - op[1]) < (op[4] - op[3])

  for allow_leftward in (False, True):
    changed = True
    while changed:
      changed = False
      merged: list[list] = []
      i = 0
      while i < len(refined):
        if (
          i + 2 < len(refined)
          and _is_short_pp(refined[i])
          and refined[i + 1][0] == "equal"
          and refined[i + 2][0] in ("delete", "replace", "insert")
          and (refined[i + 2][2] - refined[i][1]) <= 160
          and (refined[i + 2][4] - refined[i][3]) <= 160
        ):
          merged.append(["replace", refined[i][1], refined[i + 2][2], refined[i][3], refined[i + 2][4]])
          i += 3
          changed = True
        elif (
          allow_leftward
          and i + 2 < len(refined)
          and refined[i][0] in ("delete", "replace")
          and (refined[i][2] - refined[i][1]) > (refined[i][4] - refined[i][3])
          and refined[i + 1][0] == "equal"
          and _is_short_pp(refined[i + 2])
          and (refined[i + 2][2] - refined[i][1]) <= 160
          and (refined[i + 2][4] - refined[i][3]) <= 160
        ):
          merged.append(["replace", refined[i][1], refined[i + 2][2], refined[i][3], refined[i + 2][4]])
          i += 3
          changed = True
        elif i + 1 < len(refined) and _is_short_pp(refined[i]) and refined[i + 1][0] in ("delete", "replace", "insert"):
          merged.append(["replace", refined[i][1], refined[i + 1][2], refined[i][3], refined[i + 1][4]])
          i += 2
          changed = True
        elif allow_leftward and i + 1 < len(refined) and refined[i][0] in ("delete", "replace") and _is_short_pp(refined[i + 1]):
          merged.append(["replace", refined[i][1], refined[i + 1][2], refined[i][3], refined[i + 1][4]])
          i += 2
          changed = True
        elif (
          allow_leftward
          and i + 2 < len(refined)
          and refined[i][0] == "replace"
          and (refined[i][2] - refined[i][1]) >= 2
          and (refined[i][2] - refined[i][1]) == (refined[i][4] - refined[i][3])
          and refined[i + 1][0] == "equal"
          and (refined[i + 1][2] - refined[i + 1][1]) == 1
          and refined[i + 2][0] in ("delete", "replace", "insert")
          and (refined[i + 2][2] - refined[i + 2][1]) != (refined[i + 2][4] - refined[i + 2][3])
          and (refined[i + 2][2] - refined[i][1]) <= 160
          and (refined[i + 2][4] - refined[i][3]) <= 160
          and any(
            not _same_onset(pp_keys[refined[i][1] + o][0], vp_keys[refined[i][3] + o][0])
            for o in range(refined[i][2] - refined[i][1])
          )
        ):
          merged.append(["replace", refined[i][1], refined[i + 2][2], refined[i][3], refined[i + 2][4]])
          i += 3
          changed = True
        elif (
          allow_leftward
          and i + 2 < len(refined)
          and refined[i][0] in ("delete", "replace", "insert")
          and (refined[i][2] - refined[i][1]) != (refined[i][4] - refined[i][3])
          and refined[i + 1][0] == "equal"
          and (refined[i + 1][2] - refined[i + 1][1]) == 1
          and refined[i + 2][0] == "replace"
          and (refined[i + 2][2] - refined[i + 2][1]) == (refined[i + 2][4] - refined[i + 2][3])
          and (refined[i + 2][2] - refined[i][1]) <= 160
          and (refined[i + 2][4] - refined[i][3]) <= 160
          and (
            (
              (refined[i + 2][2] - refined[i + 2][1]) >= 2
              and any(
                not _same_onset(pp_keys[refined[i + 2][1] + o][0], vp_keys[refined[i + 2][3] + o][0])
                for o in range(refined[i + 2][2] - refined[i + 2][1])
              )
            )
            or (
              (refined[i + 2][2] - refined[i + 2][1]) == 1
              and refined[i][0] == "replace"
              and (refined[i][2] - refined[i][1]) == 2
              and (refined[i][4] - refined[i][3]) == 1
              and pp_keys[refined[i][1]][1] in ("ai", "au")
              and pp_keys[refined[i][1] + 1][0] == ""
              and vp_keys[refined[i + 1][3]][0] == ("य" if pp_keys[refined[i][1]][1] == "ai" else "व")
              and pp_keys[refined[i + 2][1]][0] == ""
              and vp_keys[refined[i + 2][3]][0] != ""
            )
          )
        ):
          merged.append(["replace", refined[i][1], refined[i + 2][2], refined[i][3], refined[i + 2][4]])
          i += 3
          changed = True
        else:
          merged.append(refined[i])
          i += 1
      refined = merged
  return refined


def _pp_member_starts(items: Sequence[PadapathaItem]) -> set[int]:
  starts: set[int] = set()
  idx = 0
  for it in items:
    use_ref = it.ref if it.ref != "?" else it.ar
    starts.add(idx)
    if "-" in use_ref:
      offset = 0
      for part in use_ref.split("-"):
        n_part = len(syllables_with_marks(part)[0])
        if n_part:
          starts.add(idx + offset)
          offset += n_part
    idx += len(syllables_with_marks(use_ref)[0])
  return starts


def _align_replace_span(
  vp_work: str,
  vp_pieces: Sequence[dict],
  pp_keys: list,
  pp_meta: list,
  vp_keys: list,
  vp_meta: list,
  member_starts: AbstractSet[int],
  i1: int,
  i2: int,
  j1: int,
  j2: int,
) -> tuple[dict[int, int], list[tuple[int, int, int]]] | None:
  """Align an arbitrary ``replace`` span ``(i1..i2, j1..j2)`` across chained sandhi/resyllabification."""
  memo: dict[tuple[int, int], tuple[int, list[tuple[str, tuple[int, ...]]]] | None] = {}

  def _solve(p: int, v: int) -> tuple[int, list[tuple[str, tuple[int, ...]]]] | None:
    if p == i2 and v == j2:
      return (0, [])
    state = (p, v)
    if state in memo:
      return memo[state]

    best: tuple[int, list[tuple[str, tuple[int, ...]]]] | None = None

    def _consider(score_delta: int, act: tuple[str, tuple[int, ...]], sub: tuple[int, list[tuple[str, tuple[int, ...]]]] | None) -> None:
      nonlocal best
      if sub is None:
        return
      cand = (score_delta + sub[0], [act] + sub[1])
      if best is None or cand[0] > best[0]:
        best = cand

    # 1. Leading 1->0 left-merge onto j1 - 1 (blocked when i1 - 1 ends in a coda consonant
    #    that resyllabifies onto vowel-initial i1 + i1+1 at j1, e.g. `-म् + आ᳓ + अ-` -> `-मा᳓-`).
    if (
      p == i1
      and v == j1
      and i1 > 0
      and j1 > 0
      and pp_keys[i1][0] == ""
      and (pp_meta[i1][1] == 0 or i1 in member_starts)
      and not ((i2 - i1) == 2 and (j2 - j1) == 1 and pp_keys[i1 + 1][0] == "" and vp_keys[j1][0] != "")
    ):
      ok_gap = True
      if j1 < len(vp_meta):
        pi_prev, pi_cur = vp_meta[j1 - 1][0], vp_meta[j1][0]
        ok_gap = pi_prev == pi_cur or _no_punct_between(vp_work, vp_pieces[pi_prev], vp_pieces[pi_cur])
      if ok_gap:
        _consider(3, ("merge", (i1 - 1, i1, j1 - 1)), _solve(p + 1, v))
        if i1 + 1 < i2 and pp_keys[i1 + 1][0] == "" and (pp_meta[i1 + 1][1] == 0 or (i1 + 1) in member_starts):
          # Leading 2->0 left-merge onto j1 - 1 (e.g. `यज्ञस्य + आ + ऋछेत् -> यज्ञस्यार्छेत्`).
          _consider(3, ("merge", (i1 - 1, i1, i1 + 1, j1 - 1)), _solve(p + 2, v))

    # 2. Trailing 1->0 right-merge of i2 - 1 with i2 onto j2.
    if p == i2 - 1 and v == j2 and j2 < len(vp_meta) and i2 < len(pp_keys):
      next_prev_yan = vp_pieces[vp_meta[j2][0]].get("prev_yan_onset") if vp_meta[j2][1] == 0 else None
      if (
        next_prev_yan is not None
        and pp_keys[p][1] in ("i", "u", "r", "l")
        and pp_keys[i2][0] == ""
        and _same_onset(pp_keys[p][0], next_prev_yan)
      ):
        _consider(3, ("merge", (p, i2, j2)), _solve(i2, j2))
      elif pp_keys[p][0] == "" and pp_keys[i2][0] == "" and _same_onset(pp_keys[p][0], vp_keys[j2][0]):
        _consider(3, ("merge", (p, i2, j2)), _solve(i2, j2))

    # 3. 1->1 syllable correspondence (same onset or consonant-final resyllabification).
    if p < i2 and v < j2:
      same_on = _same_onset(pp_keys[p][0], vp_keys[v][0])
      resyl_ok = (
        v > 0
        and vp_meta[v - 1][0] == vp_meta[v][0]
        and vp_keys[v][0] != ""
        and (
          (
            (pp_meta[p][1] == 0 or p in member_starts)
            and (
              (pp_keys[p][0] == "" and (pp_keys[p][1] == vp_keys[v][1] or (pp_keys[p][1] == "a" and vp_keys[v][1] in ("o", "e"))))
              or (pp_keys[p][0] != "" and vp_keys[v][0].endswith(pp_keys[p][0]) and (pp_keys[p][1] == vp_keys[v][1] or (pp_keys[p][1] == "a" and vp_keys[v][1] in ("o", "e"))))
            )
          )
          or (p > 0 and pp_keys[p - 1][1] == "r" and vp_keys[v][0] == "र" + pp_keys[p][0] and pp_keys[p][1] == vp_keys[v][1])
          or (p in member_starts and (pp_keys[p][0], vp_keys[v][0]) in _COMPOUND_STOP_VOICE_PAIRS and pp_keys[p][1] == vp_keys[v][1])
        )
      )
      if same_on or resyl_ok:
        sc = 4 if pp_keys[p] == vp_keys[v] else (3 if pp_keys[p][1] == vp_keys[v][1] else 2)
        _consider(sc, ("map", (p, v)), _solve(p + 1, v + 1))

    # 4. 2->1 sandhi coalescence (vowel sandhi, abhinihita, yaṇ, ŚB `नु+वै->न्वै/न्वा`, or resyllabified merge).
    if p + 1 < i2 and v < j2 and (
      pp_keys[p + 1][0] == ""
      or (pp_keys[p] == ("न", "u") and pp_keys[p + 1][0] == "व" and vp_keys[v][0] == "नव")
    ):
      nu_vai_merge = pp_keys[p] == ("न", "u") and pp_keys[p + 1][0] == "व" and vp_keys[v][0] == "नव"
      same_on = (_same_onset(pp_keys[p][0], vp_keys[v][0]) and pp_keys[p][1] not in ("ai", "au")) or nu_vai_merge
      yan_ok = (
        pp_keys[p][1] in ("i", "u", "r", "l")
        and (
          pp_keys[p][0] in vp_keys[v][0]
          or _same_onset(pp_keys[p][0], re.sub(r"[यवरल]+$", "", vp_keys[v][0]))
        )
        and any(sv in vp_keys[v][0] for sv in ("य", "व", "र", "ल"))
      )
      resyl_merge = (
        pp_keys[p][0] == ""
        and (pp_meta[p][1] == 0 or p in member_starts)
        and v > 0
        and vp_meta[v - 1][0] == vp_meta[v][0]
        and vp_keys[v][0] != ""
      )
      prev_yan = vp_pieces[vp_meta[v][0]].get("prev_yan_onset") if vp_meta[v][1] == 0 else None
      spaced_yan = (
        prev_yan is not None
        and pp_keys[p][1] in ("i", "u", "r", "l")
        and _same_onset(pp_keys[p][0], prev_yan)
      )
      if same_on or yan_ok or resyl_merge or spaced_yan:
        sc_m = 4 if (same_on or yan_ok or spaced_yan) else 3
        _consider(sc_m, ("merge", (p, p + 1, v)), _solve(p + 2, v + 1))

    # 5. 3->1 double coalescence:
    #    (a) yaṇ (i/u/r/l) + vowel + vowel -> 1 syllable (`अभि + आ + इहि -> अभ्येहि`, `वि + आ + अहरन् -> व्याहरन्`)
    #    (b) vowel + vowel + vowel (e.g. `न + आ + अश्नीयात् -> नाश्नीयात्`)
    if (
      p + 2 < i2
      and v < j2
      and pp_keys[p + 1][0] == ""
      and pp_keys[p + 2][0] == ""
      and (
        (
          pp_keys[p][1] in ("i", "u", "r", "l")
          and (
            pp_keys[p][0] in vp_keys[v][0]
            or _same_onset(pp_keys[p][0], re.sub(r"[यवरल]+$", "", vp_keys[v][0]))
          )
          and any(sv in vp_keys[v][0] for sv in ("य", "व", "र", "ल"))
        )
        or (
          pp_keys[p][1] == "a"
          and _same_onset(pp_keys[p][0], vp_keys[v][0])
          and pp_keys[p + 1][1] == "a"
          and (
            pp_keys[p + 2][1] == "a"
            or (pp_keys[p + 2][1] in ("i", "e", "ai") and vp_keys[v][1] in ("e", "ai"))
            or (pp_keys[p + 2][1] in ("u", "o", "au") and vp_keys[v][1] in ("o", "au"))
            or (pp_keys[p + 2][1] == "r" and vp_keys[v][1] in ("a", "r"))
          )
        )
      )
    ):
      _consider(4, ("merge", (p, p + 1, p + 2, v)), _solve(p + 3, v + 1))

    memo[state] = best
    return best

  ans = _solve(i1, j1)
  if ans is None:
    return None
  local_map: dict[int, int] = {}
  local_merges: list[tuple[int, int, int]] = []
  for kind, payload in ans[1]:
    if kind == "map":
      local_map[payload[0]] = payload[1]
    else:
      local_merges.append(payload)
  return local_map, local_merges


def _map_pp_to_vp_syllables(
  vp_work: str,
  vp_pieces: Sequence[dict],
  pp_keys: list,
  pp_meta: list,
  vp_keys: list,
  vp_meta: list,
  member_starts: AbstractSet[int] = frozenset(),
) -> list[list[tuple[int, ...]]]:
  sm = difflib.SequenceMatcher(None, pp_keys, vp_keys, autojunk=False)
  ops = _refine_opcodes([list(op) for op in sm.get_opcodes()], pp_keys, pp_meta, vp_keys)

  pp_to_vp: dict[int, int] = {}
  merged_pp_pairs: list[tuple[int, int, int]] = []
  for tag, i1, i2, j1, j2 in ops:
    if tag == "equal":
      for o in range(i2 - i1):
        pp_to_vp[i1 + o] = j1 + o
    elif tag == "replace":
      before_cnt = len(pp_to_vp) + len(merged_pp_pairs)
      if (i2 - i1) == (j2 - j1):
        for o in range(i2 - i1):
          p_idx, v_idx = i1 + o, j1 + o
          resyl_ok = (
            pp_keys[p_idx][1] == vp_keys[v_idx][1]
            and v_idx > 0
            and vp_meta[v_idx - 1][0] == vp_meta[v_idx][0]
            and vp_keys[v_idx][0] != ""
            and (
              ((pp_meta[p_idx][1] == 0 or p_idx in member_starts) and (pp_keys[p_idx][0] == "" or vp_keys[v_idx][0].endswith(pp_keys[p_idx][0])))
              or (p_idx > 0 and pp_keys[p_idx - 1][1] == "r" and vp_keys[v_idx][0] == "र" + pp_keys[p_idx][0])
              or (p_idx in member_starts and (pp_keys[p_idx][0], vp_keys[v_idx][0]) in _COMPOUND_STOP_VOICE_PAIRS)
            )
          )
          if _same_onset(pp_keys[p_idx][0], vp_keys[v_idx][0]) or resyl_ok:
            pp_to_vp[p_idx] = v_idx
      elif (
        (i2 - i1) == 3
        and (j2 - j1) == 1
        and i1 > 0
        and j1 > 0
        and pp_keys[i1][0] == ""
        and (pp_meta[i1][1] == 0 or i1 in member_starts)
        and pp_keys[i1 + 2][0] == ""
        and _same_onset(pp_keys[i1 + 1][0], vp_keys[j1][0])
      ):
        merged_pp_pairs.append((i1 - 1, i1, j1 - 1))
        if (
          pp_keys[i1 + 1][1] in ("e", "o")
          and vp_keys[j1][1] == "a"
          and j1 + 1 < len(vp_keys)
          and vp_keys[j1 + 1][0] == ""
          and i1 + 3 < len(pp_keys)
          and pp_keys[i1 + 3][0] == ""
        ):
          pp_to_vp[i1 + 1] = j1
          merged_pp_pairs.append((i1 + 2, i1 + 3, j1 + 1))
        else:
          merged_pp_pairs.append((i1 + 1, i1 + 2, j1))
      elif (i2 - i1) == 2 and (j2 - j1) == 1:
        next_prev_yan = (
          vp_pieces[vp_meta[j1 + 1][0]].get("prev_yan_onset")
          if j1 + 1 < len(vp_meta) and vp_meta[j1 + 1][1] == 0
          else None
        )
        if (
          next_prev_yan is not None
          and i1 + 2 < len(pp_keys)
          and _same_onset(pp_keys[i1][0], vp_keys[j1][0])
          and pp_keys[i1 + 1][1] in ("i", "u", "r", "l")
          and pp_keys[i1 + 2][0] == ""
          and _same_onset(pp_keys[i1 + 1][0], next_prev_yan)
        ):
          # e.g. ब्राह्मणेभ्यो + ह्य् अनुज्ञानम् where भ्यः->भ्यो + हि got grouped as 2->1
          pp_to_vp[i1] = j1
          merged_pp_pairs.append((i1 + 1, i1 + 2, j1 + 1))
        elif pp_keys[i1 + 1][0] != "":
          if pp_keys[i1] == ("न", "u") and pp_keys[i1 + 1][0] == "व" and vp_keys[j1][0] == "नव":
            merged_pp_pairs.append((i1, i1 + 1, j1))
          elif pp_keys[i1][0] == "" and _same_onset(pp_keys[i1 + 1][0], vp_keys[j1][0]):
            pp_to_vp[i1 + 1] = j1
            if i1 > 0 and j1 > 0 and (pp_meta[i1][1] == 0 or i1 in member_starts):
              pi_prev, pi_cur = vp_meta[j1 - 1][0], vp_meta[j1][0]
              if pi_prev == pi_cur or _no_punct_between(vp_work, vp_pieces[pi_prev], vp_pieces[pi_cur]):
                merged_pp_pairs.append((i1 - 1, i1, j1 - 1))
          elif _same_onset(pp_keys[i1][0], vp_keys[j1][0]):
            pp_to_vp[i1] = j1
        elif (
          pp_keys[i1][1] in ("e", "o")
          and vp_keys[j1][1] == "a"
          and _same_onset(pp_keys[i1][0], vp_keys[j1][0])
          and j1 + 1 < len(vp_keys)
          and vp_keys[j1 + 1][0] == ""
        ):
          pp_to_vp[i1] = j1
          if i1 + 2 < len(pp_keys) and pp_keys[i1 + 2][0] == "":
            merged_pp_pairs.append((i1 + 1, i1 + 2, j1 + 1))
        elif pp_keys[i1 + 1][0] == "" and (
          _same_onset(pp_keys[i1][0], vp_keys[j1][0])
          or (
            pp_keys[i1][1] in ("i", "u", "r")
            and (
              pp_keys[i1][0] in vp_keys[j1][0]
              or _same_onset(pp_keys[i1][0], re.sub(r"[यवरल]+$", "", vp_keys[j1][0]))
            )
            and any(sv in vp_keys[j1][0] for sv in ("य", "व", "र"))
          )
        ):
          merged_pp_pairs.append((i1, i1 + 1, j1))
      elif (i2 - i1) == 3 and (j2 - j1) == 2:
        if (
          _same_onset(pp_keys[i1][0], vp_keys[j1][0])
          and pp_keys[i1 + 2][0] == ""
          and _same_onset(pp_keys[i1 + 1][0], vp_keys[j1 + 1][0])
        ):
          # e.g. शेषे + आ᳓ + इ(हि) -> शेष ए᳓(हि)
          pp_to_vp[i1] = j1
          merged_pp_pairs.append((i1 + 1, i1 + 2, j1 + 1))
        elif (
          pp_keys[i1 + 1][0] == ""
          and _same_onset(pp_keys[i1][0], vp_keys[j1][0])
          and _same_onset(pp_keys[i1 + 2][0], vp_keys[j1 + 1][0])
        ):
          # e.g. प्र᳓-उक्तः -> प्रो᳓क्तो
          merged_pp_pairs.append((i1, i1 + 1, j1))
          pp_to_vp[i1 + 2] = j1 + 1
      if len(pp_to_vp) + len(merged_pp_pairs) == before_cnt:
        aligned = _align_replace_span(
          vp_work, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, member_starts, i1, i2, j1, j2
        )
        if aligned is not None:
          pp_to_vp.update(aligned[0])
          merged_pp_pairs.extend(aligned[1])
    elif tag == "delete":
      if (i2 - i1) == 1:
        next_is_av = j1 < len(vp_meta) and vp_pieces[vp_meta[j1][0]]["old"].startswith("ऽ")
        prev_yan = (
          vp_pieces[vp_meta[j1][0]].get("prev_yan_onset")
          if j1 < len(vp_meta) and vp_meta[j1][1] == 0
          else None
        )
        can_spaced_yan = (
          prev_yan is not None
          and i1 + 1 < len(pp_keys)
          and pp_keys[i1][1] in ("i", "u", "r", "l")
          and pp_keys[i1 + 1][0] == ""
          and _same_onset(pp_keys[i1][0], prev_yan)
        )
        can_ends_semi_yan = (
          j1 > 0
          and j1 < len(vp_meta)
          and vp_meta[j1][1] == 0
          and vp_pieces[vp_meta[j1 - 1][0]]["ends_semi"]
          and _no_punct_between(vp_work, vp_pieces[vp_meta[j1 - 1][0]], vp_pieces[vp_meta[j1][0]])
          and i1 + 1 < len(pp_keys)
          and pp_keys[i1][1] in ("i", "u", "r", "l")
          and pp_keys[i1 + 1][0] == ""
          and vp_keys[j1][0] == ""
        )
        can_right = (
          j1 < len(vp_keys)
          and i1 + 1 < len(pp_keys)
          and pp_keys[i1][0] == ""
          and pp_keys[i1 + 1][0] == ""
          and _same_onset(pp_keys[i1][0], vp_keys[j1][0])
        )
        can_left = j1 > 0 and (pp_meta[i1][1] == 0 or i1 in member_starts) and pp_keys[i1][0] == ""
        if can_left and j1 < len(vp_meta):
          pi_l, pi_r = vp_meta[j1 - 1][0], vp_meta[j1][0]
          if pi_l != pi_r and not _no_punct_between(vp_work, vp_pieces[pi_l], vp_pieces[pi_r]):
            can_left = False
        across_vp_space = j1 > 0 and j1 < len(vp_meta) and vp_meta[j1 - 1][0] != vp_meta[j1][0]
        if can_spaced_yan or can_ends_semi_yan:
          merged_pp_pairs.append((i1, i1 + 1, j1))
        elif next_is_av and can_left:
          merged_pp_pairs.append((i1 - 1, i1, j1 - 1))
        elif can_right and (across_vp_space or not can_left):
          merged_pp_pairs.append((i1, i1 + 1, j1))
        elif can_left:
          merged_pp_pairs.append((i1 - 1, i1, j1 - 1))
        elif can_right:
          merged_pp_pairs.append((i1, i1 + 1, j1))
      elif (i2 - i1) >= 2:
        if pp_keys[i1][0] == "" and (pp_meta[i1][1] == 0 or i1 in member_starts) and i1 > 0 and j1 > 0:
          if vp_pieces[vp_meta[j1 - 1][0]]["ends_semi"]:
            merged_pp_pairs.append((i1 - 1, i1, j1 - 1))
        if (
          j1 < len(vp_keys)
          and i2 < len(pp_keys)
          and pp_keys[i2 - 1][0] == ""
          and pp_keys[i2][0] == ""
          and _same_onset(pp_keys[i2 - 1][0], vp_keys[j1][0])
        ):
          merged_pp_pairs.append((i2 - 1, i2, j1))

  pc_syl_sources = [[[] for _ in pc["keys"]] for pc in vp_pieces]
  merged_at_vs: set[int] = set()
  for tup in merged_pp_pairs:
    *srcs_p, vs = tup
    if all(0 <= s < len(pp_meta) for s in srcs_p) and 0 <= vs < len(vp_meta):
      pi, vsi = vp_meta[vs]
      merged_at_vs.add(vs)
      pc_syl_sources[pi][vsi].append(tuple(srcs_p))
  for pp_si, vs in pp_to_vp.items():
    if vs in merged_at_vs:
      continue
    pi, vsi = vp_meta[vs]
    pc_syl_sources[pi][vsi].append((pp_si,))

  if (
    any(not srcs for pc_s in pc_syl_sources for srcs in pc_s)
    and len(pp_keys) <= 250
    and len(vp_keys) <= 250
  ):
    full_aligned = _align_replace_span(
      vp_work, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, member_starts, 0, len(pp_keys), 0, len(vp_keys)
    )
    if full_aligned is not None:
      pc_syl_sources = [[[] for _ in pc["keys"]] for pc in vp_pieces]
      merged_at_vs = set()
      for tup in full_aligned[1]:
        *srcs_p, vs = tup
        pi, vsi = vp_meta[vs]
        merged_at_vs.add(vs)
        pc_syl_sources[pi][vsi].append(tuple(srcs_p))
      for pp_si, vs in full_aligned[0].items():
        if vs not in merged_at_vs:
          pi, vsi = vp_meta[vs]
          pc_syl_sources[pi][vsi].append((pp_si,))
  return pc_syl_sources


def _merged_valid_marks(
  pp_refs: list[str],
  pp_keys: list[tuple[str, str]],
  pc: dict,
  vsi: int,
  s1: int,
  s2: int,
  next_starts_av: bool,
  *,
  allow_8_2_6_ekadesha_svarita: bool = False,
  prefer_8_2_6_svarita: bool = False,
  is_pAdAdi_s2: bool = True,
) -> tuple[set[str], str]:
  """Compute valid Pāṇini 8.2.4-8.2.6 sandhi accents ``(valid_marks, preferred_mark)`` for ``s1 + s2``."""
  r1, r2 = pp_refs[s1], pp_refs[s2]
  is_av_b = (vsi in pc["avagraha_after"]) or (vsi == len(pc["keys"]) - 1 and next_starts_av)
  is_abhinihita = (
    is_av_b
    and pc["keys"][vsi][1] in ("e", "o")
    and pp_keys[s2][0] == ""
    and pp_keys[s2][1] == "a"
  )
  is_yan_merge = (
    pp_keys[s1][1] in ("i", "u", "r", "l")
    and pp_keys[s2][0] == ""
    and (
      (
        len(pc["keys"][vsi][0]) > len(pp_keys[s1][0])
        and any(sv in pc["keys"][vsi][0] for sv in ("य", "व", "र", "ल"))
      )
      or (vsi == 0 and (pc.get("prev_yan_onset") is not None or pc.get("prev_ends_semi", False)))
    )
  )
  if r1 == "U" and r2 == "" and is_yan_merge:
    return {"S"}, "S"
  if r1 == "U" and r2 == "" and is_abhinihita:
    return {"S", "U"}, "S"
  if allow_8_2_6_ekadesha_svarita and r1 == "U" and r2 == "" and is_pAdAdi_s2 and pp_keys[s2][0] == "":
    return {"S", "U"}, ("S" if prefer_8_2_6_svarita else "U")
  if allow_8_2_6_ekadesha_svarita and is_abhinihita and r1 == "" and r2 == "U":
    return {"S", "U"}, ("S" if prefer_8_2_6_svarita else "U")
  if "U" in (r1, r2):
    return ({"U", "S"} if (r2 == "" and is_yan_merge) else {"U"}), "U"
  if "S" in (r1, r2):
    return {"S"}, "S"
  return {""}, ""


def _skip_elided_avagraha_lead(pc: dict, it: PadapathaItem, si: int, vsi: int = 0) -> bool:
  old = pc["old"]
  if not (vsi == 0 and old.startswith("ऽ") and si == 0):
    return False
  # `ऽ` before an independent vowel (`ऽआसीत्`, `ऽअतः`, `ऽउग्रः`) is a hiatus marker, NOT an elided `अ`.
  if len(old) > 1 and old[1] in DEVANAGARI_VOWELS:
    return False
  return True


def _reconcile_plain_piece(
  pc: dict,
  syl_sources: list[list[tuple[int, ...]]],
  items: Sequence[PadapathaItem],
  pp_keys: list,
  pp_meta: list,
  pp_refs: list[str],
  pp_ars: list[str],
  next_starts_av: bool,
  *,
  allow_8_2_6_ekadesha_svarita: bool = False,
  prefer_8_2_6_svarita: bool = False,
) -> tuple[int, int, str, str, bool, str, str] | None:
  cur_mks = pc["old_mks"]
  target_mks = list(cur_mks)
  reasons: list[str] = []

  mapped_items = {pp_meta[psi][0] for srcs in syl_sources if srcs for psi in srcs[0]}
  single_item_full = False
  if len(mapped_items) == 1 and all(srcs for srcs in syl_sources):
    only_ii = next(iter(mapped_items))
    expected_n = len(syllables_with_marks(items[only_ii].ref)[0])
    if sum(len(srcs[0]) for srcs in syl_sources) == expected_n:
      single_item_full = True

  for vsi, srcs in enumerate(syl_sources):
    if not srcs:
      continue
    vp_mk = cur_mks[vsi]
    src = srcs[0]
    if len(src) == 1:
      pp_si = src[0]
      ii, si = pp_meta[pp_si]
      it = items[ii]
      if _skip_elided_avagraha_lead(pc, it, si, vsi):
        continue
      if not (it.solid and (it.vyat or single_item_full or len(syl_sources) == len(syllables_with_marks(it.ref)[0]))):
        continue
      ref_mk, ar_mk = pp_refs[pp_si], pp_ars[pp_si]
      if vp_mk == ref_mk or (vp_mk == "S" and ref_mk == "U"):
        continue
      if not it.vyat:
        if ar_mk != ref_mk or (not pc["old"].startswith("ऽ") and not single_item_full and len(pc["keys"]) != len(syllables_with_marks(it.ref)[0])):
          continue
      target_mks[vsi] = ref_mk
      reasons.append(f"{it.ar}->{it.ref} ({it.prov})")
    elif len(src) >= 2:
      s1, s2 = src[-2], src[-1]
      i1, _ = pp_meta[s1]
      i2, si2 = pp_meta[s2]
      it1, it2 = items[i1], items[i2]
      intra_ok = single_item_full and i1 == i2 and it1.solid and pp_refs[s1] == pp_ars[s1] and pp_refs[s2] == pp_ars[s2]
      if not (intra_ok or (it1.vyat and it1.solid) or (it2.vyat and it2.solid)):
        continue
      if not ((it1.solid or not it1.vyat) and (it2.solid or not it2.vyat)):
        continue
      valid_mks, pref_mk = _merged_valid_marks(
        pp_refs,
        pp_keys,
        pc,
        vsi,
        s1,
        s2,
        next_starts_av,
        allow_8_2_6_ekadesha_svarita=allow_8_2_6_ekadesha_svarita,
        prefer_8_2_6_svarita=prefer_8_2_6_svarita,
        is_pAdAdi_s2=(si2 == 0),
      )
      if vp_mk not in valid_mks:
        target_mks[vsi] = pref_mk
        r_desc = f"{it1.ar}->{it1.ref}" if it1.vyat else f"{it2.ar}->{it2.ref}"
        reasons.append(f"MERGE({r_desc})")

  if target_mks != cur_mks:
    new_tok = apply_marks_to_token(pc["old"], target_mks)
    if new_tok != pc["old"]:
      return (pc["start"], pc["end"], pc["old"], f"[[{pc['old']}|{new_tok}]]", pc["bold"], "ADD", "; ".join(dict.fromkeys(reasons)))
  return None


def _validate_existing_sug_piece(
  pc: dict,
  syl_sources: list[list[tuple[int, ...]]],
  items: Sequence[PadapathaItem],
  pp_keys: list,
  pp_meta: list,
  pp_refs: list[str],
  next_starts_av: bool,
  *,
  allow_8_2_6_ekadesha_svarita: bool = False,
  prefer_8_2_6_svarita: bool = False,
) -> tuple[int, int, str, str, bool, str, str] | None:
  new_mks = pc["new_mks"]
  repaired_mks = list(new_mks)
  reasons: list[str] = []

  for vsi, srcs in enumerate(syl_sources):
    if not srcs:
      continue
    nmk = new_mks[vsi]
    src = srcs[0]
    if len(src) == 1:
      pp_si = src[0]
      ii, si = pp_meta[pp_si]
      it = items[ii]
      if it.ref == "?" or _skip_elided_avagraha_lead(pc, it, si, vsi) or not it.solid:
        continue
      ref_mk = pp_refs[pp_si]
      valid_mks = {ref_mk} | ({"S"} if ref_mk == "U" else set())
      if nmk not in valid_mks:
        repaired_mks[vsi] = ref_mk
        reasons.append(f"REVAL({it.ar}->{it.ref})")
    elif len(src) >= 2:
      s1, s2 = src[-2], src[-1]
      i1, _ = pp_meta[s1]
      i2, si2 = pp_meta[s2]
      it1, it2 = items[i1], items[i2]
      if it1.ref == "?" or it2.ref == "?":
        continue
      if not ((it1.solid or not it1.vyat) and (it2.solid or not it2.vyat)):
        continue
      valid_mks, pref_mk = _merged_valid_marks(
        pp_refs,
        pp_keys,
        pc,
        vsi,
        s1,
        s2,
        next_starts_av,
        allow_8_2_6_ekadesha_svarita=allow_8_2_6_ekadesha_svarita,
        prefer_8_2_6_svarita=prefer_8_2_6_svarita,
        is_pAdAdi_s2=(si2 == 0),
      )
      if nmk not in valid_mks:
        repaired_mks[vsi] = pref_mk
        reasons.append(f"REVAL_MERGE({it1.ar}->{it1.ref}+{it2.ar}->{it2.ref})")

  if repaired_mks != new_mks:
    fixed_new = apply_marks_to_token(pc["old"], repaired_mks)
    old_span = f"[[{pc['old']}|{pc['new']}]]"
    rsn = "; ".join(dict.fromkeys(reasons))
    if fixed_new == pc["old"]:
      return (pc["start"], pc["end"], old_span, pc["old"], pc["bold"], "UNWRAP", rsn)
    return (pc["start"], pc["end"], old_span, f"[[{pc['old']}|{fixed_new}]]", pc["bold"], "UPDATE", rsn)
  return None


def reconcile_vp_suggestions(
  vp_body: str,
  items: Sequence[PadapathaItem],
  *,
  extra_invalid_olds: AbstractSet[str] = frozenset(),
  allow_8_2_6_ekadesha_svarita: bool = False,
  prefer_8_2_6_svarita: bool = False,
) -> tuple[str, list[str]]:
  """Align ``विश्वास-प्रस्तुतिः`` against ``पद-पाठः (यान्त्रिकः)`` and add, unwrap, or update ``[[OLD|NEW]]`` spans."""
  logs: list[str] = []
  vp_work, unwrap_logs = unwrap_stale_suggestions(vp_body, items, extra_invalid_olds=extra_invalid_olds)
  logs.extend(unwrap_logs)

  vp_pieces = _extract_vp_pieces(vp_work)
  if not vp_pieces or not items:
    return vp_work, logs

  pp_keys, pp_meta, pp_refs, pp_ars = _flatten_pp_syllables(items)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(vp_work, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, _pp_member_starts(items))

  edits = []
  for pi, pc in enumerate(vp_pieces):
    next_starts_av = (
      pi + 1 < len(vp_pieces)
      and vp_pieces[pi + 1]["old"].startswith("ऽ")
      and _no_punct_between(vp_work, pc, vp_pieces[pi + 1])
    )
    if not pc["is_sug"]:
      mapped_ids = {pp_meta[psi][0] for srcs in pc_syl_sources[pi] if srcs for psi in srcs[0]}
      if len(mapped_ids) == 1 and not pc["old"].startswith("ऽ"):
        ii_only = next(iter(mapped_ids))
        ref_only = items[ii_only].ref if items[ii_only].ref != "?" else items[ii_only].ar
        exp_n = len(syllables_with_marks(ref_only)[0])
        cov_n = sum(len(srcs[0]) for srcs in pc_syl_sources[pi] if srcs)
        if cov_n < exp_n:
          adj_prev = (
            pi > 0
            and _no_punct_between(vp_work, vp_pieces[pi - 1], pc)
            and any(pp_meta[psi][0] == ii_only for srcs in pc_syl_sources[pi - 1] if srcs for psi in srcs[0])
          )
          adj_next = (
            pi + 1 < len(vp_pieces)
            and _no_punct_between(vp_work, pc, vp_pieces[pi + 1])
            and any(pp_meta[psi][0] == ii_only for srcs in pc_syl_sources[pi + 1] if srcs for psi in srcs[0])
          )
          if not (adj_prev or adj_next):
            continue
      ed = _reconcile_plain_piece(
        pc,
        pc_syl_sources[pi],
        items,
        pp_keys,
        pp_meta,
        pp_refs,
        pp_ars,
        next_starts_av,
        allow_8_2_6_ekadesha_svarita=allow_8_2_6_ekadesha_svarita,
        prefer_8_2_6_svarita=prefer_8_2_6_svarita,
      )
    else:
      ed = _validate_existing_sug_piece(
        pc,
        pc_syl_sources[pi],
        items,
        pp_keys,
        pp_meta,
        pp_refs,
        next_starts_av,
        allow_8_2_6_ekadesha_svarita=allow_8_2_6_ekadesha_svarita,
        prefer_8_2_6_svarita=prefer_8_2_6_svarita,
      )
    if ed is not None:
      edits.append(ed)

  if not edits:
    return vp_work, logs

  out = list(vp_work)
  for s, e, old_span, rep, is_b, kind, rsn in reversed(edits):
    out[s:e] = list(rep)
    btag = "BOLD " if is_b else ""
    logs.append(f"{kind}_{btag}SUG: {old_span} -> {rep}  <-- {rsn}")
  return "".join(out), logs


def fill_vp_accents_from_padapatha(
  vp_body: str,
  items: Sequence[PadapathaItem],
  *,
  allow_8_2_6_ekadesha_svarita: bool = False,
  prefer_8_2_6_svarita: bool = False,
) -> tuple[str, list[tuple[str, int]]]:
  """Directly populate US accents (``᳓``/``᳙``) onto an unaccented ``विश्वास-प्रस्तुतिः`` body from ``items``.

  Preserves markdown bolding, ``+++(...)+++`` notes, hyphens, spaces, and exact bare Devanagari,
  applying Pāṇini ``8.2.4–8.2.6`` cross-pada sandhi rules. Returns ``(filled_vp_body, unmapped_syllables)``.
  """
  vp_pieces = _extract_vp_pieces(vp_body)
  if not vp_pieces or not items:
    return vp_body, []

  pp_keys, pp_meta, pp_refs, _ = _flatten_pp_syllables(items)
  vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
  vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
  pc_syl_sources = _map_pp_to_vp_syllables(vp_body, vp_pieces, pp_keys, pp_meta, vp_keys, vp_meta, _pp_member_starts(items))

  unmapped: list[tuple[str, int]] = []
  out = list(vp_body)
  for pi, pc in reversed(list(enumerate(vp_pieces))):
    if pc["is_sug"]:
      continue
    next_starts_av = (
      pi + 1 < len(vp_pieces)
      and vp_pieces[pi + 1]["old"].startswith("ऽ")
      and _no_punct_between(vp_body, pc, vp_pieces[pi + 1])
    )
    target_mks = list(pc["old_mks"])
    for vsi, srcs in enumerate(pc_syl_sources[pi]):
      if not srcs:
        unmapped.append((pc["old"], vsi))
        continue
      src = srcs[0]
      if len(src) == 1:
        pp_si = src[0]
        ii, si = pp_meta[pp_si]
        if not _skip_elided_avagraha_lead(pc, items[ii], si, vsi):
          target_mks[vsi] = pp_refs[pp_si]
      elif len(src) >= 2:
        _, si2 = pp_meta[src[-1]]
        _, pref_mk = _merged_valid_marks(
          pp_refs,
          pp_keys,
          pc,
          vsi,
          src[-2],
          src[-1],
          next_starts_av,
          allow_8_2_6_ekadesha_svarita=allow_8_2_6_ekadesha_svarita,
          prefer_8_2_6_svarita=prefer_8_2_6_svarita,
          is_pAdAdi_s2=(si2 == 0),
        )
        target_mks[vsi] = pref_mk
    if target_mks != pc["old_mks"]:
      new_tok = apply_marks_to_token(pc["old"], target_mks)
      out[pc["start"]:pc["end"]] = list(new_tok)
  return "".join(out), list(reversed(unmapped))


def find_js_include_spans(markdown_text: str) -> list[tuple[int, int]]:
  """Return balanced ``(start, end)`` spans of top-level ``<div class="js_include">...</div>`` elements."""
  spans: list[tuple[int, int]] = []
  tag_re = re.compile(r"<div\b[^>]*>|</div>", re.I)
  js_depth = 0
  inner_depth = 0
  start_pos = 0
  for m in tag_re.finditer(markdown_text):
    tok = m.group(0)
    if tok.lower().startswith("<div"):
      if js_depth == 0:
        if "js_include" in tok:
          js_depth = 1
          start_pos = m.start()
      else:
        inner_depth += 1
    elif js_depth > 0:
      if inner_depth > 0:
        inner_depth -= 1
      else:
        spans.append((start_pos, m.end()))
        js_depth = 0
  return spans


def _is_direct_fill_vp_block(ps_stripped: str, vp_body: str, *, is_sb_cluster: bool) -> bool:
  """Return True when ``विश्वास-प्रस्तुतिः`` uses direct US accent fill rather than ``[[OLD|NEW]]`` suggestions."""
  if "[[" in vp_body:
    return False
  if "स्वराः व्यत्यस्ताः" in ps_stripped or "यन्त्र-स्वरः" in ps_stripped:
    return True
  return (not is_sb_cluster) and bool(_VP_VYAT_SUMMARY_RE.search(ps_stripped))


def _reconcile_markdown_blocks_once(
  markdown_text: str,
  *,
  extra_invalid_olds: AbstractSet[str] = frozenset(),
  skip_js_includes: bool = True,
  allow_8_2_6_ekadesha_svarita: bool | None = None,
  refill_direct_vp: bool = True,
  refresh_pp_summaries: bool = True,
  sync_vp_summaries: bool = False,
) -> tuple[str, list[str]]:
  """Execute one pass of :func:`reconcile_markdown_blocks`."""
  js_divs = find_js_include_spans(markdown_text) if skip_js_includes else []
  dmatches = [m for m in LEAF_DETAILS_RE.finditer(markdown_text) if not any(a <= m.start() < b for a, b in js_divs)]
  replacements: list[tuple[int, int, str]] = []
  all_logs: list[str] = []

  has_kanva_sb_doc = "\u1cd8" in markdown_text or "<summary>C R Swaminathan</summary>" in markdown_text
  for i, m in enumerate(dmatches):
    pp_hdr = m.group(1).strip()
    if not pp_hdr.startswith("पद-पाठः (यान्त्रिकः"):
      continue
    items = parse_padapatha_items(m.group(2).strip())
    n_vyat = sum(1 for it in items if it.vyat)
    p_total = len(items)
    if refresh_pp_summaries and p_total > 0:
      expected_pp_hdr = format_padapatha_summary(n_vyat, p_total)
      if expected_pp_hdr != pp_hdr:
        pp_open = " open" if "<details open>" in m.group(0)[:20] else ""
        replacements.append((m.start(), m.end(), f"<details{pp_open}><summary>{expected_pp_hdr}</summary>{m.group(2)}</details>"))
        all_logs.append(f"PP_HDR: {pp_hdr} -> {expected_pp_hdr}")

    is_sb_cluster = False
    for j in range(i - 1, max(-1, i - 12), -1):
      ps = dmatches[j].group(1)
      if ps.startswith("पद-पाठः (यान्त्रिकः"):
        break
      if "\n##" in markdown_text[dmatches[j].end() : m.start()]:
        break
      if ps in ("मूलम् - Weber", "मूलम् - श्रीधरादि") or (
        ps == "मूलम्" and ("\u1cd8" in dmatches[j].group(2) or has_kanva_sb_doc)
      ):
        is_sb_cluster = True
      if ps.startswith("विश्वास-प्रस्तुतिः"):
        vp_m = dmatches[j]
        ps_stripped = ps.strip()
        vp_body = vp_m.group(2)
        allow_826 = is_sb_cluster if allow_8_2_6_ekadesha_svarita is None else allow_8_2_6_ekadesha_svarita
        if "स्वराः पूर्याः" in ps_stripped:
          break
        open_attr = " open" if "<details open>" in vp_m.group(0)[:20] else ""
        is_direct_vp = _is_direct_fill_vp_block(ps_stripped, vp_body, is_sb_cluster=is_sb_cluster)
        if not is_direct_vp and has_us_accents(vp_body):
          new_vp, vlogs = reconcile_vp_suggestions(
            vp_body,
            items,
            extra_invalid_olds=extra_invalid_olds,
            allow_8_2_6_ekadesha_svarita=allow_826,
          )
          new_ps = ps_stripped
          has_vyat_suffix = bool(_VP_VYAT_SUMMARY_RE.search(ps_stripped)) or "स्वराः व्यत्यस्ताः" in ps_stripped
          if (
            sync_vp_summaries
            and p_total > 0
            and "यन्त्र-स्वरः" not in ps_stripped
            and (is_sb_cluster or has_vyat_suffix or "[[" in new_vp)
          ):
            new_ps = format_suggested_vp_summary(ps_stripped, n_vyat, p_total)
          if new_vp != vp_body or new_ps != ps_stripped:
            hdr_out = new_ps if new_ps != ps_stripped else ps
            replacements.append((vp_m.start(), vp_m.end(), f"<details{open_attr}><summary>{hdr_out}</summary>{new_vp}</details>"))
            all_logs.extend(vlogs)
            if new_ps != ps_stripped:
              all_logs.append(f"VP_HDR: {ps_stripped} -> {new_ps}")
        elif refill_direct_vp and is_direct_vp:
          new_vp, unmapped = fill_vp_accents_from_padapatha(
            vp_body,
            items,
            allow_8_2_6_ekadesha_svarita=allow_826,
          )
          new_ps = format_filled_vp_summary(
            ps_stripped,
            n_vyat,
            p_total,
            mula_has_accents=("यन्त्र-स्वरः" not in ps_stripped),
          )
          if not unmapped and (new_vp != vp_body or new_ps != ps_stripped):
            replacements.append((vp_m.start(), vp_m.end(), f"<details{open_attr}><summary>{new_ps}</summary>{new_vp}</details>"))
            all_logs.append(f"REFILLED_VP: {ps_stripped} -> {new_ps}")
        break

  if not replacements:
    return markdown_text, []

  out = markdown_text
  for s, e, rep in sorted(replacements, key=lambda x: x[0], reverse=True):
    out = out[:s] + rep + out[e:]
  return out, all_logs


def reconcile_markdown_blocks(
  markdown_text: str,
  *,
  extra_invalid_olds: AbstractSet[str] = frozenset(),
  skip_js_includes: bool = True,
  allow_8_2_6_ekadesha_svarita: bool | None = None,
  refill_direct_vp: bool = True,
  refresh_pp_summaries: bool = True,
  sync_vp_summaries: bool = False,
  fixed_point: bool = False,
  max_passes: int = 5,
) -> tuple[str, list[str]]:
  """Reconcile paired ``विश्वास-प्रस्तुतिः`` and ``पद-पाठः (यान्त्रिकः)`` details blocks inside Markdown text.

  When ``sync_vp_summaries=True``, suggestion-mode ``विश्वास-प्रस्तुतिः`` headers in ŚB clusters,
  clusters with inline ``[[OLD|NEW]]`` spans, or headers already bearing a *vyatyasta* count suffix
  are also kept in sync via :func:`format_suggested_vp_summary`.
  When ``fixed_point=True``, iterates up to ``max_passes`` passes until a pass leaves the text unchanged.
  """
  if max_passes < 1:
    raise ValueError(f"max_passes must be >= 1, got {max_passes}")
  passes = max_passes if fixed_point else 1
  cur = markdown_text
  combined_logs: list[str] = []
  for _ in range(passes):
    nxt, logs = _reconcile_markdown_blocks_once(
      cur,
      extra_invalid_olds=extra_invalid_olds,
      skip_js_includes=skip_js_includes,
      allow_8_2_6_ekadesha_svarita=allow_8_2_6_ekadesha_svarita,
      refill_direct_vp=refill_direct_vp,
      refresh_pp_summaries=refresh_pp_summaries,
      sync_vp_summaries=sync_vp_summaries,
    )
    combined_logs.extend(logs)
    if nxt == cur:
      break
    cur = nxt
  return cur, combined_logs


def reconcile_and_sync_markdown_blocks(
  markdown_text: str,
  *,
  extra_invalid_olds: AbstractSet[str] = frozenset(),
  skip_js_includes: bool = True,
  allow_8_2_6_ekadesha_svarita: bool | None = None,
  refill_direct_vp: bool = True,
  max_passes: int = 5,
) -> tuple[str, list[str]]:
  """Run :func:`reconcile_markdown_blocks` to fixed point with ``पद-पाठः`` and ``विश्वास-प्रस्तुतिः`` summary sync."""
  return reconcile_markdown_blocks(
    markdown_text,
    extra_invalid_olds=extra_invalid_olds,
    skip_js_includes=skip_js_includes,
    allow_8_2_6_ekadesha_svarita=allow_8_2_6_ekadesha_svarita,
    refill_direct_vp=refill_direct_vp,
    refresh_pp_summaries=True,
    sync_vp_summaries=True,
    fixed_point=True,
    max_passes=max_passes,
  )


_NON_MULA_STAGE_RE = re.compile(
  r"\((?:उत्तरस्याम्|दक्षिणस्याम्|मध्ये|दश देवसेनाभ्यः)[^)]*\)|(?<!\[)\[[^\[\]]+\](?!\])"
)


def _split_toml_frontmatter(text: str) -> tuple[str, str]:
  if text.startswith("+++"):
    parts = text.split("+++", 2)
    if len(parts) == 3:
      lead_nl = "\n" * (len(parts[2]) - len(parts[2].lstrip("\n")))
      return "+++" + parts[1] + "+++" + lead_nl, parts[2].lstrip("\n")
  return "", text


def _mask_non_mula_spans(
  vp_body: str,
  mula_body: str = "",
  *,
  mask_stage_brackets: bool = True,
) -> tuple[str, list[tuple[str, str]]]:
  """Mask ``<div class="js_include">...</div>`` and non-``मूलम्`` stage-direction/anuṣaṅga brackets."""
  masks: list[tuple[str, str]] = []
  out = vp_body
  for s, e in reversed(find_js_include_spans(out)):
    tok = f"\x01JSMASK{len(masks)}\x02"
    masks.append((tok, out[s:e]))
    out = out[:s] + tok + out[e:]

  if mask_stage_brackets:
    mula_bare = bare_devanagari(mula_body) if mula_body else ""

    def _repl(m: re.Match) -> str:
      frag = m.group(0)
      frag_bare = bare_devanagari(frag)
      if frag_bare and mula_bare and frag_bare in mula_bare:
        return frag
      tok = f"\x01STMASK{len(masks)}\x02"
      masks.append((tok, frag))
      return tok

    out = _NON_MULA_STAGE_RE.sub(_repl, out)
  return out, masks


def _unmask_spans(text: str, masks: Sequence[tuple[str, str]]) -> str:
  out = text
  for tok, orig in reversed(masks):
    out = out.replace(tok, orig)
  return out


def _slice_items_for_partial_vp(items: Sequence[PadapathaItem], vp_masked: str) -> Sequence[PadapathaItem]:
  """Slice ``items`` to the prefix matching ``vp_masked`` when ``VP`` is an abbreviated pratīka (e.g. ``…``)."""
  vp_clean = re.sub(r"\+\+\+.*?\+\+\+", "", vp_masked, flags=re.S)
  vp_clean = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\1", vp_clean)
  vp_n = len(syllables_with_marks(vp_clean)[0])
  if vp_n == 0:
    return []
  pp_total = sum(len(syllables_with_marks(it.ref if it.ref != "?" else it.ar)[0]) for it in items)
  if pp_total - vp_n <= 3:
    return items
  cum = 0
  best_k = len(items)
  best_diff = abs(pp_total - vp_n)
  for k, it in enumerate(items, 1):
    cum += len(syllables_with_marks(it.ref if it.ref != "?" else it.ar)[0])
    diff = abs(cum - vp_n)
    if diff < best_diff:
      best_diff = diff
      best_k = k
  return items[:best_k]


def reconcile_vprastuti_and_tiikaa_texts(
  vprastuti_text: str,
  tiikaa_text: str,
  *,
  extra_invalid_olds: AbstractSet[str] = frozenset(),
  mask_stage_brackets: bool = True,
) -> tuple[str, list[str]]:
  """Reconcile a split ``vishvAsa-prastutiH`` file against its companion ``sarvASh_TIkAH`` (ṭīkā) file.

  In split Hugo corpus layouts:
  - ``vprastuti_text`` (``vishvAsa-prastutiH/<mantra>.md``) holds the reader-facing US-accented presentation text
    (optionally followed or wrapped by ``<div class="js_include">`` blocks, stage directions, or ``…`` pratīka abbreviations).
  - ``tiikaa_text`` (``sarvASh_TIkAH/<mantra>.md``, i.e. the ``टीका`` + ``मूलम्`` + ``पद-पाठः`` companion file)
    holds ``<details><summary>मूलम्</summary>``, ``<details><summary>पद-पाठः (यान्त्रिकः...)</summary>``, and commentaries.

  Only outer blocks outside ``<div class="js_include">...</div>`` are read from ``tiikaa_text`` and modified in ``vprastuti_text``.
  Stage-direction parentheses and single-bracketed anuṣaṅga supplements absent from ``मूलम्`` are masked during alignment,
  and abbreviated ``vprastuti_text`` prefixes are aligned against the matching prefix of ``पद-पाठः`` items.
  """
  js_tk = find_js_include_spans(tiikaa_text)
  tk_blocks = [m for m in LEAF_DETAILS_RE.finditer(tiikaa_text) if not any(a <= m.start() < b for a, b in js_tk)]
  m_pp = next((m for m in tk_blocks if m.group(1).strip().startswith("पद-पाठः (यान्त्रिकः")), None)
  if m_pp is None:
    return vprastuti_text, []
  m_mula = next((m for m in tk_blocks if m.group(1).strip().startswith("मूलम्")), None)
  mula_body = m_mula.group(2) if m_mula is not None else ""

  vp_hdr, vp_body = _split_toml_frontmatter(vprastuti_text)
  vp_masked, masks = _mask_non_mula_spans(vp_body, mula_body, mask_stage_brackets=mask_stage_brackets)
  if not has_us_accents(vp_masked):
    return vprastuti_text, []

  items = parse_padapatha_items(m_pp.group(2).strip())
  sub_items = _slice_items_for_partial_vp(items, vp_masked)
  if not sub_items:
    return vprastuti_text, []

  new_masked, logs = reconcile_vp_suggestions(vp_masked, sub_items, extra_invalid_olds=extra_invalid_olds)
  new_vp_body = _unmask_spans(new_masked, masks)
  if new_vp_body == vp_body:
    return vprastuti_text, []
  return vp_hdr + new_vp_body, logs
