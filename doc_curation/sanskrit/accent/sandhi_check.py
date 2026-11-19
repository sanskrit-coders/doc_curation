"""Fast Pāṇinian and Vedic forward-sandhi round-trip verifier.

Reconstructs saṁhitā strings from a proposed sequence of padapāṭha (or hyphenated
compound) tokens in SLP1 and checks whether Vedic/Pāṇinian sandhi rules reproduce
the source ``मूलम्`` text. Used to validate padapāṭha word/inflection splits
without loading external lexicons.
"""

from __future__ import annotations

import re
from typing import Sequence

from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

SLP_VOWELS = frozenset("aAiIuUfFxXeEoO")
SLP_VOICED_CONS = frozenset("gGNjJYqQRdDnbBmyrlvh")
SLP_VOICELESS_CONS = frozenset("kKcCwWtTpPSzs")

# Words whose final `:h` derives from etymological `r` (रयम् / ऋत्विग्भ्यो रुत्वम्),
# so rhotacism applies before vowels and voiced consonants regardless of vowel quality.
R_FINAL_SLP = frozenset({
  "punaH", "punar", "antaH", "antar", "svaH", "svar", "suvaH", "suvar",
  "mahaH", "mahar", "prAtaH", "prAtar", "ahaH", "ahar", "kaH", "kar",
  "pitaH", "mAtaH", "BrAtaH", "svasaH", "duhitaH", "savitaH", "hotaH",
  "DAtaH", "tvazwaH", "netaH", "viDAtaH", "bahiH", "bahir",
})

_R_FINAL_SUFFIXES = ("punaH", "antaH", "svaH", "prAtaH", "ahaH", "taH")
_PRONOUN_SU_LOPA = frozenset({"saH", "ezaH", "syaH"})
_SPECIAL_LEFT_WORDS = _PRONOUN_SU_LOPA | R_FINAL_SLP
_LONG_VOWEL = {"a": "A", "i": "I", "u": "U"}
_VOICED_ASP_PAIRS = (
  ("dD", "D"), ("tT", "T"), ("bB", "B"), ("gG", "G"), ("jJ", "J"),
  ("qQ", "Q"), ("kK", "K"), ("pP", "P"), ("wW", "W"),
)
_STOP_TABLE = {
  "k": ("k", "g", "G"),
  "g": ("k", "g", "G"),
  "w": ("w", "q", "Q"),
  "q": ("w", "q", "Q"),
  "p": ("p", "b", None),
  "b": ("p", "b", None),
}
_AVASANA_STOP_SWAP = {"t": "d", "d": "t", "k": "g", "g": "k", "w": "q", "q": "w", "p": "b", "b": "p"}


def clean_deva_for_sandhi(text: str) -> str:
  """Normalize Devanagari saṁhitā or padapāṭha text before SLP1 conversion."""
  s = re.sub(r"(?m)^\[\^[^\]]+\]:.*$", " ", text)
  s = re.sub(r"\[\^[^\]]+\]", " ", s)
  s = re.sub(r"<[^>]+>", " ", s)
  s = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\1", s)
  s = re.sub(r"\[\[.*?\]\]", " ", s, flags=re.S)
  s = re.sub(r"\+\+\+\(.*?\)\+\+\+", " ", s, flags=re.S)
  s = re.sub(r"\[\d+\]|\(\d+\)", " ", s)
  s = accent.strip_accents(s)
  # Drop strikethrough deletions and brief inline textual-variant / ŚB pratīka parentheticals.
  s = re.sub(r"\(?~~.*?~~\)?", "", s)
  s = re.sub(r"\([\u0900-\u097f\u1cd0-\u1cff\sऽ]{1,8}\)", "", s)
  s = s.replace("ॐ", "ओम्").replace("शिश्ञ", "शिश्न")
  # Normalize Taittirīya and Mādhyandina Śatapatha anunāsika marks to anusvāra.
  for src, dst in (
    ("ᳫँ᳭", "ं"), ("ᳫं᳭", "ं"), ("ᳫँ", "ं"), ("ᳫं", "ं"), ("ᳫ", "ं"),
    ("᳭", ""), ("ᳮ", ""), ("᳟", ""),
    ("व्विं", "ंवि"), ("य्यिं", "ंयि"), ("व्वृं", "ंवृ"), ("सव्विं", "संवि"),
    ("व्व्ँ", "ंव"), ("य्य्ँ", "ंय"), ("ल्ल्ँ", "ंल"),
    ("वँय", "ंव्य"), ("वँव", "ंव"),
    ("व्ँ", "ं"), ("य्ँ", "ं"), ("ल्ँ", "ं"), ("ँ", "ं"),
  ):
    s = s.replace(src, dst)
  s = s.replace("ऽ", "").replace("३", "")
  s = re.sub(r"[०-९0-9।॥,;.?!\"'“”‘’—–_()\[\]{}+*/\\|<>=-]", " ", s)
  return s


def canonical_geminates(slp: str) -> str:
  """Collapse recensional consonant geminates, epentheses, and orthographic variants."""
  s = slp
  for a, b in _VOICED_ASP_PAIRS:
    s = s.replace(a, b)
  s = s.replace("cC", "C").replace("tS", "C")
  # Taittirīya & Mādhyandina gemination after r and before semivowels y/v/r.
  s = re.sub(r"r([kKgGNcCjJYqQdDnbBmylvh])\1", r"r\1", s)
  s = re.sub(r"([tdnmyvl])\1([yv])", r"\1\2", s)
  # Vedic metrical distraction (-iya- <-> -ya-, suva <-> sva, tanuv- <-> tanv-).
  s = re.sub(r"([kKgGNcCjJYqQRtTdDnpPbBmyrlvSzsh])iy([aAiIuUeEoO])", r"\1y\2", s)
  for sv_a, sv_b in (
    ("suvaH", "svaH"), ("suvar", "svar"), ("suvaS", "svaS"),
    ("suvas", "svas"), ("suva", "sva"),
    ("tanuve", "tanve"), ("tanuvE", "tanvE"), ("tanuvA", "tanvA"),
  ):
    s = s.replace(sv_a, sv_b)
  # Normalize OCR ङ/ड confusion and homorganic nasals to M + consonant.
  s = re.sub(r"q([kKgG])", r"M\1", s)
  s = re.sub(r"[NYRnm]([kKgGcCjJwWqQtTdDpPbBnmlvyrSzsh])", r"M\1", s)
  s = re.sub(r"M{2,}", "M", s)
  s = s.replace("Mts", "Ms").replace("nts", "Ms").replace("MtS", "MS")
  for dbl, single in (("ss", "s"), ("SS", "S"), ("zz", "z"), ("tt", "t"), ("dd", "d"), ("jj", "j"), ("cc", "c"), ("ll", "l"), ("vv", "v"), ("yy", "y")):
    s = s.replace(dbl, single)
  return s


def _to_raw_slp(deva_text: str) -> str:
  s = clean_deva_for_sandhi(deva_text)
  slp = sanscript.transliterate(s, sanscript.DEVANAGARI, sanscript.SLP1)
  slp = re.sub(r"[^a-zA-Z|]", "", slp)
  return slp.replace("L", "q").replace("|", "Q")


def to_norm_slp(deva_text: str) -> str:
  """Convert Devanagari text to canonicalized SLP1 with ``ळ``/``ळ्ह`` normalized."""
  return canonical_geminates(_to_raw_slp(deva_text))


def join_vowels(v1: str, v2: str) -> list[str]:
  """Return possible SLP1 vowel-sandhi mid segments for ``v1 + v2``."""
  res: set[str] = set()
  if v1 in "aA" and v2 in "aA":
    res.add("A")
  elif v1 in "iI" and v2 in "iI":
    res.add("I")
  elif v1 in "uU" and v2 in "uU":
    res.add("U")
  elif v1 in "fF" and v2 in "fF":
    res.add("F")
  elif v1 in "aA":
    if v2 in "iI":
      res.add("e")
    elif v2 in "uU":
      res.add("o")
    elif v2 in "fF":
      # Include `f` prakṛtibhāva per पा० ६.१.१२८ ऋत्यकः.
      res.update(("ar", "Ar", v1 + v2))
    elif v2 in "eE":
      res.add("E")
      if v1 == "a" and v2 == "e":
        res.add("e")
    elif v2 in "oO":
      res.add("O")
      if v1 == "a" and v2 == "o":
        res.add("o")
  elif v1 in "iI":
    res.add("y" + v2)
  elif v1 in "uU":
    res.update(("v" + v2, "uv" + v2))
  elif v1 in "fF":
    res.add("r" + v2)
  elif v1 == "e":
    if v2 == "a":
      res.update(("e", "ea", "aya", "aa"))
    else:
      res.update(("ay" + v2, "a" + v2))
      res.update(join_vowels("a", v2))
  elif v1 == "E":
    res.update(("Ay" + v2, "A" + v2))
    res.update(join_vowels("A", v2))
  elif v1 == "o":
    if v2 == "a":
      res.update(("o", "oa", "ava", "aa"))
    else:
      res.update(("av" + v2, "a" + v2))
      res.update(join_vowels("a", v2))
  elif v1 == "O":
    res.update(("Av" + v2, "A" + v2))
  return list(res)


def right_variants(r: str, after_retro_trigger: bool, after_r_pra_pari: bool) -> list[str]:
  """Return Vedic ṣatva and ṇatva variants of initial consonant in ``r``."""
  outs = [r]
  if not r:
    return outs
  if after_retro_trigger and r[0] == "s":
    outs.append("z" + r[1:])
    if r.startswith("st"):
      outs.append("zw" + r[2:])
    elif r.startswith("sT"):
      outs.append("zW" + r[2:])
  if after_r_pra_pari and r[0] == "n":
    outs.append("R" + r[1:])
  return outs


def _vowel_sandhi(left: str, right: str, is_compound: bool, left_word_slp: str = "") -> set[str]:
  outs: set[str] = set()
  c_last, r0 = left[-1], right[0]
  if r0 in SLP_VOWELS:
    stem = left[:-1]
    for mid in join_vowels(c_last, r0):
      outs.add(stem + mid + right[1:])
    # Permit hiatus ONLY for pragṛhya (-ī/-ū/-e, monosyllabic nipāta u per पा० १.१.१४) or non-compound -o (पा० ६.१.११५ / ओत्).
    lw = left_word_slp or left
    if c_last in ("I", "U", "e") or (not is_compound and (c_last == "o" or lw == "u")):
      outs.add(left + right)
  else:
    outs.add(left + right)
    if c_last in _LONG_VOWEL:
      outs.add(left[:-1] + _LONG_VOWEL[c_last] + right)
  return outs


def _visarga_voiceless(left: str, stem: str, right: str, *, allow_z: bool, zw_on_t: bool = False) -> set[str]:
  r0 = right[0]
  if r0 in "cC":
    return {stem + "S" + right}
  if r0 in "wW":
    return {stem + "z" + right}
  if r0 in "tT":
    res = {stem + "s" + right}
    if zw_on_t and right.startswith("t"):
      res.add(stem + "zw" + right[1:])
    return res
  if r0 in "Szs":
    return {stem + right, left + right}
  res = {left + right, stem + "s" + right}
  if allow_z:
    res.add(stem + "z" + right)
  return res


def _visarga_sandhi(left: str, right: str, left_word_slp: str) -> set[str]:
  outs: set[str] = {left + right}
  c_last = left[-1]
  stem = left[:-1]
  vp = stem[-1] if stem else ""
  r0 = right[0]

  if left_word_slp in _PRONOUN_SU_LOPA:
    outs.add(stem + right)
    if r0 in SLP_VOWELS:
      for mid in join_vowels("a", r0):
        outs.add(stem[:-1] + mid + right[1:])
  if left_word_slp in R_FINAL_SLP or any(left_word_slp.endswith(sfx) for sfx in _R_FINAL_SUFFIXES):
    if r0 == "r" and vp in _LONG_VOWEL:
      outs.add(stem[:-1] + _LONG_VOWEL[vp] + right)
    elif r0 in SLP_VOWELS or r0 in SLP_VOICED_CONS:
      outs.add(stem + "r" + right)

  if c_last == "r":
    if r0 == "r" and vp in _LONG_VOWEL:
      outs.add(stem[:-1] + _LONG_VOWEL[vp] + right)
    if r0 in SLP_VOICELESS_CONS:
      outs.update((stem + "H" + right, stem + right))
    return outs

  if vp == "a":
    if r0 in SLP_VOWELS:
      if r0 == "a":
        outs.update((stem[:-1] + "o" + right[1:], stem[:-1] + "o" + right, stem + right))
      else:
        outs.add(stem + right)
        for dv in join_vowels("a", r0):
          outs.add(stem[:-1] + dv + right[1:])
    elif r0 in SLP_VOICED_CONS:
      outs.add(stem[:-1] + "o" + right)
      if r0 == "r":
        outs.add(stem[:-1] + "A" + right)
    else:
      outs.update(_visarga_voiceless(left, stem, right, allow_z=True))
  elif vp == "A":
    if r0 in SLP_VOWELS or r0 in SLP_VOICED_CONS:
      outs.add(stem + right)
      if r0 in SLP_VOWELS:
        for dv in join_vowels("A", r0):
          outs.add(stem[:-1] + dv + right[1:])
    else:
      outs.update(_visarga_voiceless(left, stem, right, allow_z=False))
  else:
    if r0 == "r" and vp in _LONG_VOWEL:
      outs.add(stem[:-1] + _LONG_VOWEL[vp] + right)
    elif r0 in SLP_VOWELS or r0 in SLP_VOICED_CONS:
      outs.add(stem + "r" + right)
    else:
      outs.update(_visarga_voiceless(left, stem, right, allow_z=True, zw_on_t=True))
  return outs


def _nasal_sandhi(left: str, right: str, is_compound: bool) -> set[str]:
  c_last, r0 = left[-1], right[0]
  stem = left[:-1]
  if c_last in ("m", "M"):
    outs = {stem + "m" + right, stem + "M" + right}
    if r0 not in SLP_VOWELS and r0 in "nl":
      outs.add(stem + r0 + right)
    return outs

  vp = stem[-1] if stem else ""
  if r0 in SLP_VOWELS:
    outs = {stem + "n" + right}
    if vp in "aiuf":
      outs.add(stem + "Mn" + right)
    if vp in "AIUF":
      outs.update((stem + "M" + right, stem + "Mr" + right))
    return outs
  if r0 in "cC":
    return {stem + "MS" + right, stem + "M" + right}
  if r0 in "wW":
    return {stem + "Mz" + right, stem + "M" + right}
  if r0 in "tT":
    return {stem + "Ms" + right, stem + "M" + right, left + right}
  if r0 == "S":
    return {stem + "MC" + right[1:], stem + "M" + right, left + right}
  outs = {left + right, stem + "M" + right}
  if is_compound:
    outs.add(stem + right)
  return outs


def _dental_stop_sandhi(left: str, right: str) -> set[str]:
  stem, r0 = left[:-1], right[0]
  outs = {stem + "t" + right}
  if r0 in SLP_VOWELS or r0 in "gGdDbByrv":
    outs.add(stem + "d" + right)
  elif r0 == "h":
    outs.update((stem + "D" + right[1:], stem + "dh" + right[1:]))
  elif r0 in "nm":
    outs.update((stem + "M" + right, stem + "d" + right))
  elif r0 in "cC":
    outs.add(stem + "C" + right[1:] if r0 == "C" else stem + "c" + right)
  elif r0 in "jJ":
    outs.add(stem + "j" + right)
  elif r0 in "wW":
    outs.add(stem + "w" + right)
  elif r0 in "qQ":
    outs.add(stem + "q" + right)
  elif r0 == "l":
    outs.update((stem + "Ml" + right, stem + "l" + right))
  elif r0 == "S":
    outs.add(stem + "C" + right[1:])
  elif right.startswith(("sT", "st")) and left.endswith(("ut", "ud")):
    outs.add(stem + right[1:])
  return outs


def _other_stop_sandhi(left: str, right: str) -> set[str]:
  c_last, r0 = left[-1], right[0]
  stem = left[:-1]
  vl, vd, h_sub = _STOP_TABLE[c_last]
  outs = {stem + vl + right}
  if r0 in SLP_VOWELS or r0 in SLP_VOICED_CONS:
    outs.add(stem + vd + right)
    if r0 in "nm":
      outs.add(stem + "M" + right)
    if r0 == "h" and h_sub:
      outs.add(stem + h_sub + right[1:])
  elif c_last in ("k", "g") and r0 == "S":
    outs.update((stem + "kC" + right[1:], stem + "kS" + right[1:]))
  elif c_last in ("w", "q"):
    if r0 == "s":
      outs.add(stem + "wts" + right[1:])
    elif r0 in "tT":
      outs.add(stem + "w" + right if r0 == "t" else stem + "W" + right[1:])
  return outs


def sandhi_step(left: str, right_raw: str, is_compound: bool = False, left_word_slp: str = "") -> set[str]:
  """Compute candidate canonicalized SLP1 strings from joining ``left + right_raw``."""
  if not left:
    return {canonical_geminates(right_raw)}
  if not right_raw:
    return {canonical_geminates(left)}

  c_last = left[-1]
  v_prev = left[-2] if len(left) >= 2 else ""
  retro_trig = c_last in "iIuUfFeEoOrk" or (c_last == "H" and v_prev in "iIuUfFeEoO")
  natva_trig = (
    left.endswith(("pra", "pari", "nir", "niH", "antar", "aBIzu", "mozu", "Uzu"))
    or "r" in left[-3:]
    or "f" in left[-3:]
  )

  outs: set[str] = set()
  for right in right_variants(right_raw, retro_trig, natva_trig):
    if c_last in SLP_VOWELS:
      outs.update(_vowel_sandhi(left, right, is_compound, left_word_slp))
    elif c_last in ("H", "s", "r"):
      outs.update(_visarga_sandhi(left, right, left_word_slp))
    elif c_last in ("m", "M", "n"):
      outs.update(_nasal_sandhi(left, right, is_compound))
    elif c_last in ("t", "d"):
      outs.update(_dental_stop_sandhi(left, right))
    elif c_last in _STOP_TABLE:
      outs.update(_other_stop_sandhi(left, right))
    else:
      outs.add(left + right)
  return {canonical_geminates(o) for o in outs}


def word_to_slp_options(pada_deva: str) -> set[str]:
  """Convert a padapāṭha token (allowing ``-`` samāsa splits) to candidate SLP1 forms."""
  parts = [p for p in pada_deva.split("-") if p.strip()]
  if not parts:
    return {""}
  cur = {to_norm_slp(parts[0])}
  for pt in parts[1:]:
    r_slp = to_norm_slp(pt)
    nxt: set[str] = set()
    for c in cur:
      nxt.update(sandhi_step(c, r_slp, is_compound=True, left_word_slp=c))
    cur = nxt
  res: set[str] = set()
  for c in cur:
    res.add(c)
    if c.endswith("s"):
      res.add(c[:-1] + "H")
  return res


def _matches_avasana_end(st: str, target: str) -> bool:
  if st == target:
    return True
  # पा० ८.४.५६ वाऽवसाने: optional devoicing/voicing of final stops at pause.
  if st and st[-1] in _AVASANA_STOP_SWAP and st[:-1] + _AVASANA_STOP_SWAP[st[-1]] == target:
    return True
  if (st.endswith("m") and st[:-1] + "M" == target) or st + "M" == target or st + "n" == target or st == target + "H":
    return True
  if st.endswith("aH") and (st[:-2] + "o" == target or st[:-1] == target or st[:-1] + "s" == target or st[:-1] + "r" == target):
    return True
  if st.endswith("AH") and (st[:-1] == target or st[:-1] + "s" == target):
    return True
  if st.endswith("H") and (st[:-1] + "r" == target or st[:-1] + "s" == target):
    return True
  if st.endswith("O") and st[:-1] + "Av" == target:
    return True
  if st.endswith("E") and st[:-1] + "Ay" == target:
    return True
  return False


def _prepare_target_and_pauses(mula_text: str, pauses: str | None) -> tuple[str, set[int]]:
  cleaned = re.sub(r"<[^>]+>", " ", mula_text)
  target = to_norm_slp(cleaned)
  if not pauses:
    return target, set()
  # Only explicit pause punctuation (not `\n` wraps without daṇḍa) creates pause offsets.
  split_re = f"(?:{pauses}|\\+\\+\\+[^+]*\\+\\+\\+|[0-9\u0966-\u096f]+\\s*[।॥]+)"
  raw_clauses = [_to_raw_slp(c) for c in re.split(split_re, cleaned)]
  raw_clauses = [rc for rc in raw_clauses if rc]
  if len(raw_clauses) <= 1:
    return target, set()
  # Canonicalize the full joined target once (preserving cross-danda consonant rules),
  # and record cumulative character offsets of pause boundaries.
  canon_full = canonical_geminates("".join(raw_clauses))
  if canon_full == target:
    pause_offsets = {len(canonical_geminates("".join(raw_clauses[:k]))) for k in range(1, len(raw_clauses))}
  else:
    pause_offsets = set()
    cum = ""
    for rc in raw_clauses[:-1]:
      cum += canonical_geminates(rc)
      pause_offsets.add(len(cum))
  return target, pause_offsets


def verify_mantra_sandhi(
  padas_strs: Sequence[str],
  mula_text: str,
  *,
  pauses: str | None = r"[।॥;]+",
) -> tuple[bool, int, str, str]:
  """Verify whether ``padas_strs`` reconstruct ``mula_text`` under forward sandhi.

  By default, explicit pause punctuation (``pauses=r"[।॥;]+"``) allows avasāna
  hiatus at those clause boundaries, while daṇḍa-less line breaks (``\\n``)
  still require external sandhi.

  Returns:
    ``(ok, fail_pada_idx, target_window, matched_prefix)``.
  """
  target, pause_offsets = _prepare_target_and_pauses(mula_text, pauses)
  if not target:
    return True, -1, "", ""

  state_map: dict[str, str] = {"": ""}
  best_prefix = ""
  for pi, pd in enumerate(padas_strs):
    w_opts = word_to_slp_options(pd)
    next_map: dict[str, str] = {}
    for st, last_wo in state_map.items():
      for wo in w_opts:
        cands = sandhi_step(st, wo, is_compound=False, left_word_slp=last_wo)
        if pause_offsets:
          if len(st) in pause_offsets:
            cands.add(st + wo)
            if st.endswith("m"):
              cands.add(st[:-1] + "M" + wo)
          if st.endswith("s") and (len(st) - 1) in pause_offsets:
            cands.update((st[:-1] + "H" + wo, st[:-1] + wo))
        for cand in cands:
          chk = cand[:-2] if len(cand) > 2 else ""
          if target.startswith(chk) and len(cand) <= len(target) + 3:
            if cand not in next_map or wo in _SPECIAL_LEFT_WORDS:
              next_map[cand] = wo
            if len(cand) > len(best_prefix) and target.startswith(cand[:-1] if len(cand) > 1 else ""):
              best_prefix = cand
    if not next_map:
      rem_target = target[max(0, len(best_prefix) - 4) : len(best_prefix) + 18]
      return False, pi, rem_target, best_prefix[-12:]
    state_map = next_map

  if target in state_map or any(_matches_avasana_end(st, target) for st in state_map):
    return True, -1, "", target

  rem_target = target[max(0, len(best_prefix) - 4) : len(best_prefix) + 18]
  return False, len(padas_strs) - 1, rem_target, best_prefix[-12:]
