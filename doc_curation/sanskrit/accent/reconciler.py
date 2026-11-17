"""Reconcile US-accented ``विश्वास-प्रस्तुतिः`` inline ``[[OLD|NEW]]`` suggestions against ``पद-पाठः (यान्त्रिकः)``."""

from __future__ import annotations

import dataclasses
import difflib
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
  "ण": "न", "थ": "त", "ध": "द", "फ": "प", "भ": "ब", "श": "स", "ष": "स", "ळ": "ड",
}
_SAME_ONSET_PAIRS = frozenset({
  ("स", "च"), ("च", "स"), ("द", "न"), ("द", "ल"), ("द", "ज"),
  ("त", "च"), ("ग", "क"), ("ह", "ग"), ("ह", "द"),
})

DETAILS_RE = re.compile(r"<details(?:\s+open)?><summary>([^<]*)</summary>(.*?)</details>", re.S)
PP_HEADER_RE = re.compile(r"^पद-पाठः \(यान्त्रिकः(?:\s*-\s*(\d+)/(\d+)\s*व्यत्यस्त-स्वराः)?\)$")
_SUG_SPAN_RE = re.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
_PIECE_PAT = re.compile(
  r"\[\[([^|\]]+)\|([^\]]+)\]\]|[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\u0951\u0952\-ऽ]+"
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


def sanitize_us_accents(text: str) -> str:
  """Collapse duplicate adjacent Vedic accent marks without removing distinct ones."""
  return re.sub(r"[\u1cd0-\u1cff\u0951\u0952]+", lambda m: "".join(dict.fromkeys(m.group(0))), text)


def bare_devanagari(text: str) -> str:
  """Strip accents and non-Devanagari characters for strict bare-form equality checks."""
  return re.sub(r"[^\u0900-\u097f]", "", accent.strip_accents(text))


def syllables_with_marks(text: str) -> tuple[list[tuple[str, str]], list[str]]:
  """Return normalized ``(onset, vowel_family)`` syllable keys and US accent marks (``'U'``/``'S'``/``''``)."""
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
  return keys, mks


def apply_marks_to_token(tok: str, new_marks: Sequence[str]) -> str:
  """Apply per-syllable US marks onto Devanagari ``tok`` preserving consonants/mātrās via ``SCHEME.join_strings``."""
  clean = sanitize_us_accents(tok)
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
  res = SCHEME.join_strings(out)
  if bare_devanagari(res) != bare_devanagari(tok):
    raise ValueError(f"Bare Devanagari drifted for {tok!r} -> {res!r}")
  return res


def is_solid_provenance(prov: str) -> bool:
  """Return True when a padapāṭha provenance note cites solid Vedic/Pāṇinian authority (not bare ``*MW*``)."""
  if any(
    c in prov
    for c in ("*TS*", "*RV*", "*TB*", "*AV*", "*VS*", "*KS*", "*MS*", "*ŚB*", "*TA*", "*TK*", "*Macdonell*", "*Lanman*")
  ):
    return True
  if any(
    r in prov
    for r in (
      "पा० २.४.",
      "पा० ३.१.",
      "पा० ३.२.",
      "पा० ३.३.",
      "पा० ३.४.",
      "पा० ४.१.",
      "पा० ४.२.",
      "पा० ४.३.",
      "पा० ४.४.",
      "पा० ५.१.",
      "पा० ५.२.",
      "पा० ५.३.",
      "पा० ५.४.",
      "पा० ६.१.१६",
      "पा० ६.१.१७",
      "पा० ६.१.१८",
      "पा० ६.१.१९",
      "पा० ६.१.२०",
      "पा० ६.१.२१",
      "पा० ६.१.२२",
      "पा० ६.२.",
      "पा० ६.४.",
      "पा० ८.१.२८",
      "पा० ८.१.१८",
      "पा० ८.१.३",
      "पा० ८.१.१९",
      "पा० ८.१.३०",
      "पा० ८.१.५९",
      "पा० ८.१.६३",
      "पा० ८.१.६५",
      "पा० ८.१.७०",
      "पा० ८.१.७१",
      "पा० ८.१.७२",
    )
  ):
    return True
  if "पा० ६.१.१५८" in prov and "अनाम्नातम्" not in prov:
    return True
  if ("पा० ८.१.६६" in prov or "पा० ८.१.३४" in prov) and any(
    x in prov for x in ("अनेकोदात्त", "अनुदात्त-दोषः", "यद्वृत्तान्नित्यम्", "हि च", "*TS*", "*RV*", "*TB*", "*TK*", "पा० ३.", "पा० ६.")
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


def _same_onset(c1: str, c2: str) -> bool:
  if c1 == c2:
    return True
  if not c1 or not c2:
    return False
  return c1[-1] == c2[-1] or (c1[-1], c2[-1]) in _SAME_ONSET_PAIRS


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
  for m in re.finditer(r"\+\+\+.*?\+\+\+|\[\[\?\?\]\]", vp_work, re.S):
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
      "ends_semi": o.endswith(("य्", "व्य्", "त्य्", "प्य्", "र्य्")),
      "prev_yan_onset": prev_yan_onset,
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
      if (i2 - i1) == (j2 - j1):
        for o in range(i2 - i1):
          p_idx, v_idx = i1 + o, j1 + o
          resyl_ok = (
            pp_keys[p_idx][0] == ""
            and pp_meta[p_idx][1] == 0
            and pp_keys[p_idx][1] == vp_keys[v_idx][1]
            and v_idx > 0
            and vp_meta[v_idx - 1][0] == vp_meta[v_idx][0]
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
        merged_pp_pairs.append((i1 + 1, i1 + 2, j1))
      elif (i2 - i1) == 2 and (j2 - j1) == 1:
        if pp_keys[i1 + 1][0] != "":
          if pp_keys[i1][0] == "" and _same_onset(pp_keys[i1 + 1][0], vp_keys[j1][0]):
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
            and pp_keys[i1][0] in vp_keys[j1][0]
            and any(sv in vp_keys[j1][0] for sv in ("य", "व", "र"))
          )
        ):
          merged_pp_pairs.append((i1, i1 + 1, j1))
      elif (
        (i2 - i1) == 3
        and (j2 - j1) == 2
        and _same_onset(pp_keys[i1][0], vp_keys[j1][0])
        and pp_keys[i1 + 2][0] == ""
        and _same_onset(pp_keys[i1 + 1][0], vp_keys[j1 + 1][0])
      ):
        # e.g. शेषे + आ᳓ + इ(हि) -> शेष ए᳓(हि)
        pp_to_vp[i1] = j1
        merged_pp_pairs.append((i1 + 1, i1 + 2, j1 + 1))
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
  for s1, s2, vs in merged_pp_pairs:
    if 0 <= s1 < len(pp_meta) and 0 <= s2 < len(pp_meta) and 0 <= vs < len(vp_meta):
      pi, vsi = vp_meta[vs]
      merged_at_vs.add(vs)
      pc_syl_sources[pi][vsi].append((s1, s2))
  for pp_si, vs in pp_to_vp.items():
    if vs in merged_at_vs:
      continue
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
      or (vsi == 0 and pc.get("prev_yan_onset") is not None)
    )
  )
  if r1 == "U" and r2 == "" and is_yan_merge:
    return {"S"}, "S"
  if r1 == "U" and r2 == "" and is_abhinihita:
    return {"S", "U"}, "S"
  if "U" in (r1, r2):
    return ({"U", "S"} if (r2 == "" and is_yan_merge) else {"U"}), "U"
  if "S" in (r1, r2):
    return {"S"}, "S"
  return {""}, ""


def _skip_elided_avagraha_lead(pc: dict, it: PadapathaItem, si: int) -> bool:
  if not pc["old"].startswith("ऽ"):
    return False
  ref_syls, _ = syllables_with_marks(it.ref if it.ref != "?" else it.ar)
  return len(ref_syls) != len(pc["keys"]) + 1 or si == 0


def _reconcile_plain_piece(
  pc: dict,
  syl_sources: list[list[tuple[int, ...]]],
  items: Sequence[PadapathaItem],
  pp_keys: list,
  pp_meta: list,
  pp_refs: list[str],
  pp_ars: list[str],
  next_starts_av: bool,
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
      if _skip_elided_avagraha_lead(pc, it, si):
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
    elif len(src) == 2:
      s1, s2 = src
      i1, _ = pp_meta[s1]
      i2, _ = pp_meta[s2]
      it1, it2 = items[i1], items[i2]
      intra_ok = single_item_full and i1 == i2 and it1.solid and pp_refs[s1] == pp_ars[s1] and pp_refs[s2] == pp_ars[s2]
      if not (intra_ok or (it1.vyat and it1.solid) or (it2.vyat and it2.solid)):
        continue
      if not ((it1.solid or not it1.vyat) and (it2.solid or not it2.vyat)):
        continue
      valid_mks, pref_mk = _merged_valid_marks(pp_refs, pp_keys, pc, vsi, s1, s2, next_starts_av)
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
      if it.ref == "?" or _skip_elided_avagraha_lead(pc, it, si) or not it.solid:
        continue
      ref_mk = pp_refs[pp_si]
      valid_mks = {ref_mk} | ({"S"} if ref_mk == "U" else set())
      if nmk not in valid_mks:
        repaired_mks[vsi] = ref_mk
        reasons.append(f"REVAL({it.ar}->{it.ref})")
    elif len(src) == 2:
      s1, s2 = src
      i1, _ = pp_meta[s1]
      i2, _ = pp_meta[s2]
      it1, it2 = items[i1], items[i2]
      if it1.ref == "?" or it2.ref == "?":
        continue
      if not ((it1.solid or not it1.vyat) and (it2.solid or not it2.vyat)):
        continue
      valid_mks, pref_mk = _merged_valid_marks(pp_refs, pp_keys, pc, vsi, s1, s2, next_starts_av)
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
      ed = _reconcile_plain_piece(pc, pc_syl_sources[pi], items, pp_keys, pp_meta, pp_refs, pp_ars, next_starts_av)
    else:
      ed = _validate_existing_sug_piece(pc, pc_syl_sources[pi], items, pp_keys, pp_meta, pp_refs, next_starts_av)
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


def reconcile_markdown_blocks(
  markdown_text: str,
  *,
  extra_invalid_olds: AbstractSet[str] = frozenset(),
  skip_js_includes: bool = True,
) -> tuple[str, list[str]]:
  """Reconcile paired ``विश्वास-प्रस्तुतिः`` and ``पद-पाठः (यान्त्रिकः)`` details blocks inside Markdown text."""
  js_divs = (
    [(m.start(), m.end()) for m in re.finditer(r'<div class="js_include".*?</div>', markdown_text, re.S)]
    if skip_js_includes
    else []
  )
  dmatches = [m for m in DETAILS_RE.finditer(markdown_text) if not any(a <= m.start() < b for a, b in js_divs)]
  replacements: list[tuple[int, int, str]] = []
  all_logs: list[str] = []

  for i, m in enumerate(dmatches):
    if not m.group(1).startswith("पद-पाठः (यान्त्रिकः"):
      continue
    items = parse_padapatha_items(m.group(2).strip())
    for j in range(i - 1, max(-1, i - 5), -1):
      ps = dmatches[j].group(1)
      if ps.startswith("विश्वास-प्रस्तुतिः"):
        if "स्वराः पूर्याः" not in ps and "यन्त्र-स्वरः" not in ps and has_us_accents(dmatches[j].group(2)):
          new_vp, vlogs = reconcile_vp_suggestions(dmatches[j].group(2), items, extra_invalid_olds=extra_invalid_olds)
          if new_vp != dmatches[j].group(2):
            open_attr = " open" if "<details open>" in dmatches[j].group(0)[:20] else ""
            replacements.append((dmatches[j].start(), dmatches[j].end(), f"<details{open_attr}><summary>{ps}</summary>{new_vp}</details>"))
            all_logs.extend(vlogs)
        break

  if not replacements:
    return markdown_text, []

  out = markdown_text
  for s, e, rep in sorted(replacements, key=lambda x: x[0], reverse=True):
    out = out[:s] + rep + out[e:]
  return out, all_logs


def reconcile_vp_and_tk_texts(
  vp_text: str,
  tk_text: str,
  *,
  extra_invalid_olds: AbstractSet[str] = frozenset(),
) -> tuple[str, list[str]]:
  """Reconcile a split ``vishvAsa-prastutiH`` file against its paired ``sarvASh_TIkAH`` file."""
  m_pp = re.search(r"<details[^>]*><summary>(पद-पाठः \(यान्त्रिकः[^<]*\))</summary>(.*?)</details>", tk_text, re.S)
  if not m_pp:
    return vp_text, []
  if vp_text.startswith("+++"):
    parts = vp_text.split("+++", 2)
    if len(parts) == 3:
      lead_nl = "\n" * (len(parts[2]) - len(parts[2].lstrip("\n")))
      vp_hdr = "+++" + parts[1] + "+++" + lead_nl
      vp_body = parts[2].lstrip("\n")
    else:
      vp_hdr, vp_body = "", vp_text
  else:
    vp_hdr, vp_body = "", vp_text
  if not has_us_accents(vp_body):
    return vp_text, []
  items = parse_padapatha_items(m_pp.group(2).strip())
  new_vp, logs = reconcile_vp_suggestions(vp_body, items, extra_invalid_olds=extra_invalid_olds)
  if new_vp == vp_body:
    return vp_text, []
  return vp_hdr + new_vp, logs
