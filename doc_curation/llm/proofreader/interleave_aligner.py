"""Deterministic + SLP1-stem-aware monotonic DP commentary & translation aligner.

Implements the ``/interleaver`` skill's alignment and multi-role separation rules:
1. Sandhi-aware pratīka extraction (``**bold**``, unquoted ``... इति`` with yaṇ,
   guṇa, savarṇadīrgha, and śākalya-lopa restoration, dash lead-ins, and opening
   headwords), while masking single-quoted ``'...' इति`` sūtra/kalpa citations.
2. Vedic svara, ``+++(...)+++`` gloss, avagraha, nasal, and visarga-sandhi
   normalization plus root/stem & compound-tail overlap scoring.
3. Rule-exact structural role classification (``heading``, ``viniyoga`` + kalpa
   continuations, ``avatarika`` including stuti lead-ins & multi-ṛk chandas notes,
   ``tika`` including single-ṛk chandas notes, ``translation``, ``note``,
   ``viniyoga_sangraha``).
4. Monotonic Viterbi dynamic programming with ``upcoming_cores`` lookahead for
   exact ``unmatched_from`` cutoff, plus post-guard refinement for LLM JSON plans.
"""
from __future__ import annotations

import math
from pathlib import Path
import tomllib
import regex

_RULES_PATH = Path(__file__).resolve().parent / "data" / "interleave_rules.toml"
with _RULES_PATH.open("rb") as _f:
  _RULES = tomllib.load(_f)

_ITI_CONTS = tuple(sorted(_RULES["iti_continuations"], key=len, reverse=True))
_META_VERBS = frozenset(_RULES["meta_verbs"])
_AAHA_FUSED: dict[str, str] = dict(_RULES["aaha_fused"])
_STOPWORDS = frozenset(_RULES["stopwords"])
_VINIYOGA_SKT = tuple(_RULES["viniyoga_sanskrit_cues"])
_VINIYOGA_EN = tuple(_RULES["viniyoga_english_cues"])
_MULTI_RK_AVA = tuple(_RULES["multi_rk_avatarika_cues"])
_STUTI_AVA = tuple(_RULES["stuti_avatarika_cues"])
_EDITORIAL_EN = tuple(_RULES["editorial_english_cues"])
_GRAMMAR_CONT = tuple(_RULES["grammar_continuation_cues"])

_YAN_RESTORE = {"व": "ु", "य": "ि", "र": "ृ", "ल": "ि"}
_ITI_RE = regex.compile(r"([िइेी])त(ि|्य)")
_SVARA_RE = regex.compile(r"[\u0951-\u0954\u1cd0-\u1cf4\u1cf7-\u1cff\u200c\u200d᳓᳙]")
_PLUS_GLOSS_RE = regex.compile(r"\+\+\+.*?\+\+\+", flags=regex.DOTALL)
_BRACKET_NUM_RE = regex.compile(r"\[\^?[0-9०-९P.]+\]")
_SUTRA_QUOTE_RE = regex.compile(
  r"(?:'[^'\n]{2,100}'|‘[^’\n]{2,100}’|\"[^\"]+\"\s*\([^)\n]*[॰.][^)\n]*\))\s*(?:इत[ि्य]\S*)"
)
_COLOPHON_RE = regex.compile(
  r"^\s*इति\s+[^।॥\n]{2,90}(?:अनुवाकः|नुवाकः|प्रपाठकः|अध्यायः|काण्डम्|सूक्तम्|समाप्तम्)\s*॥"
)


def _clean_sanskrit_surface(text: str) -> str:
  """Normalize Vedic svaras, editorial glosses, nasals, avagraha, and sandhi geminates."""
  s = _PLUS_GLOSS_RE.sub(" ", text or "")
  s = regex.sub(r"<!--.*?-->", " ", s, flags=regex.DOTALL)
  s = regex.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\1 \2", s)
  s = _BRACKET_NUM_RE.sub(" ", s)
  s = _SVARA_RE.sub("", s)
  s = s.replace("ᳵ", "ः").replace("ᳶ", "ः").replace("ळ", "ल")
  s = regex.sub(r"[यवल]्ँ", "ं", s)
  s = regex.sub(r"[ङञणनम]्", "ं", s)
  s = s.replace("ँ", "ं")
  # Restore initial/post-space/post-o/e avagraha as word-initial `अ`
  s = regex.sub(r"(^|[\s,।॥\-–—ोे])ऽ", r"\1 अ", s)
  s = s.replace("ऽ", "")
  # Normalize Vedic sandhi geminates & word-final sibilant-visarga assimilations
  s = s.replace("त्त्र", "त्र").replace("द्ध्व", "ध्व")
  s = regex.sub(r"([अ-हइ-औि-ौ])[शषस]्(?=(?:\s+|[-–—]|$))", r"\1ः ", s)
  s = regex.sub(r"([अ-हइ-औि-ौ])स्(?=स्[क-ह])", r"\1ः ", s)
  s = regex.sub(r"([अ-हइ-औि-ौ])श्(?=श[क-हअ-औि-ौ])", r"\1ः ", s)
  s = regex.sub(r"थ्(?=\s+स)", "त्", s)
  s = regex.sub(r"[*_+#>]", " ", s)
  return s


def _stem_of(word: str) -> str:
  """Reduce an inflected/derived Sanskrit word to a comparable root/stem prefix."""
  w = word.strip("ःंम्")
  for suf in (
    "यिष्यते", "िष्यते", "ष्यते", "मानाय", "मानाः", "माना", "मानम्",
    "यन्ते", "यते", "न्ते", "न्ति", "ेभ्यः", "ेभ्यस्", "ेभ्य", "ीभ्यः", "ीभ्य", "ोभ्यः", "ोभ्य",
    "ाभ्याम्", "भ्यः", "भ्य", "ायै", "ायाः", "ाय", "स्य", "स्मिन्", "ेषु", "ासु", "ानाम्", "ीनाम्",
    "त्वम्", "त्वात्", "णम्", "नम्", "नः", "नाः", "ेन", "ेण", "ते", "ति",
  ):
    if len(w) >= len(suf) + 3 and w.endswith(suf):
      w = w[:-len(suf)]
      break
  # Canonicalize common vṛddhi/guṇa & grahī->grah alternations (रैभ->रेभ, उद्ग्रही->उद्ग्रह)
  w = w.replace("ग्रही", "ग्रह")
  if len(w) >= 3 and "ै" in w[:3]:
    w = w.replace("ै", "े", 1)
  res = w.rstrip("ःं्ोेािी")
  return res if len(res) >= 2 else word[:3]


def normalize_for_alignment(text: str) -> dict:
  """Build compact normalized string, word-start offsets, words, and stems."""
  s = _clean_sanskrit_surface(text)
  sep_re = regex.compile(r"[\s\-\u2013\u2014\(\)\[\]।॥,;:\.\"'“”‘’0-9०-९/]")
  out_chars: list[str] = []
  starts: set[int] = set()
  at_start = True
  for ch in s:
    if sep_re.match(ch):
      at_start = True
      continue
    if at_start:
      starts.add(len(out_chars))
      at_start = False
    out_chars.append(ch)
  raw_words = [
    w.rstrip("ःस्श्ष्") if len(w) > 3 else w
    for w in regex.findall(r"[ऀ-ॿ]{2,}", s)
    if regex.search(r"[अ-ह]", w)
  ]
  content_words = [w for w in raw_words if w not in _STOPWORDS and len(w) >= 3]
  stems = [_stem_of(w) for w in content_words]
  return {
    "compact": "".join(out_chars),
    "starts": frozenset(starts),
    "words": content_words,
    "stems": stems,
  }


def _iti_candidates_from_match(text: str, m: regex.Match, max_words: int = 3) -> list[str]:
  """Extract sandhi-restored pratīka strings preceding a genuine ``इति`` marker."""
  after = text[m.end():]
  if after.startswith("\u094d"):
    rem = after[1:].lstrip(" -")
    if rem and regex.match(r"[ऀ-ॿ]", rem[0]) and not any(
      rem.startswith(p) for p in ("अनेन", "आह", "अत्र", "अर्थ", "उक्त", "आदि", "एव", "एत")
    ):
      pass  # Still valid spaced `इत्य् <word>`!
  elif after and regex.match(r"[ऀ-ॿ]", after[0]) and not after.startswith(_ITI_CONTS):
    return []

  seg = regex.split(r"(?:\s+[-–—]\s*|[-–—]\s+|[–—।॥:;\n'‘’\"“”()])+", text[:m.start()])[-1]
  # Collapse samāsa hyphens inside compound words (`तत्-स्वरूप-ज्ञान` -> `तत्स्वरूपज्ञान`)
  seg = regex.sub(r"(?<=[ऀ-ॿ])-(?=[ऀ-ॿ])", "", seg)
  words = [w for w in regex.findall(r"[ऀ-ॿ]+", seg) if regex.search(r"[अ-ह]", w)]
  if not words:
    return []
  abut = m.start() > 0 and not text[m.start() - 1].isspace()
  vtag = m.group(1)
  variants: list[list[str]] = [list(words)]
  last = words[-1]
  if abut and last in _AAHA_FUSED:
    variants = [words[:-1] + [_AAHA_FUSED[last]]]
  elif abut and vtag == "े" and last.endswith("त्व"):
    variants.insert(0, words[:-1] + [last[:-2] + "त्वा"])
  elif abut and vtag == "ि" and (ym := regex.search(r"[क-ह]\u094d([यवरल])$", last)):
    variants.insert(0, words[:-1] + [last[:ym.start(1) - 1] + _YAN_RESTORE[ym.group(1)]])
  elif abut and vtag == "ी":
    variants.insert(0, words[:-1] + [last + "ि"])
    variants.append(words[:-1] + [last + "ी"])
  elif abut and vtag == "े":
    variants.append(words[:-1] + [last + "ा"])
  elif not abut and vtag == "इ" and regex.search(r"[क-ह]$", last):
    variants.insert(0, words[:-1] + [last + "े"])

  cands: list[str] = []
  for wl in variants:
    cut = 0
    for k in range(len(wl) - 1):
      if wl[k] in _META_VERBS or wl[k] in _AAHA_FUSED or (wl[k].endswith("माह") and len(wl[k]) > 3):
        cut = k + 1
    for p in (wl[-1], " ".join(wl[cut:][-max_words:]), " ".join(wl[-max_words:])):
      n = normalize_for_alignment(p)["compact"]
      if len(n) >= 2 and p not in _STOPWORDS and n not in cands:
        cands.append(n)
  return cands


def extract_segment_cues(segment: str) -> dict:
  """Extract explicit pratīkas, opening headwords, and structural flags from one segment."""
  raw = (segment or "").strip()
  is_heading_only = bool(regex.match(r"^(?:#{1,6}\s+\S|\*\*[^*\n]+॥\*\*\s*$)", raw))
  explicit: list[str] = []
  bold_count = 0
  if not is_heading_only:
    for bm in regex.finditer(r"\*\*([^*।॥\n]{2,60})\*\*", raw):
      n = normalize_for_alignment(bm.group(1))["compact"]
      if len(n) >= 2 and bm.group(1).strip() not in _STOPWORDS:
        bold_count += 1
        if n not in explicit:
          explicit.append(n)

  masked = _SUTRA_QUOTE_RE.sub(" ", raw)
  # End-pratīka dominance: if a single-sentence segment ends with `... इति ।/॥`
  # (and has no bold word-by-word glosses), that closing pratīka governs alone.
  iti_matches = list(_ITI_RE.finditer(masked))
  end_cands: list[str] = []
  if bold_count == 0 and iti_matches:
    last_im = iti_matches[-1]
    tail_after = masked[last_im.end():]
    if not regex.search(r"[अ-ह]", regex.sub(r"^\u094d", "", tail_after)):
      end_cands = _iti_candidates_from_match(masked, last_im)
  if end_cands:
    explicit.extend(n for n in end_cands if n not in explicit)
  else:
    for im in iti_matches:
      for n in _iti_candidates_from_match(masked, im):
        if n not in explicit:
          explicit.append(n)

  # Double-quoted mula quotes (excluding external `(तै.आन...)` / `(सं॰...)` citations)
  for qm in regex.finditer(r'(?:"([^"\n]{3,80})"|“([^”\n]{3,80})”)(?!\s*\([^)\n]*[॰.])', raw):
    qtxt = qm.group(1) or qm.group(2)
    n = normalize_for_alignment(qtxt)["compact"]
    if len(n) >= 4 and n not in explicit:
      explicit.append(n)

  # Leading source-edition mantra serial number (e.g. `5पञ्चमी -`, `14बार्हस्पत्ये`, `15-17प्रस्तरं`)
  lead_num_m = regex.match(r"^\s*([0-9०-९]{1,3})(?:-[0-9०-९]{1,3})?\s*[ऀ-ॿA-Za-z*]", raw)
  lead_num = int(lead_num_m.group(1).translate(str.maketrans("०१२३४५६७८९", "0123456789"))) if lead_num_m else None
  stripped_head = regex.sub(r"^\s*[0-9०-९]+(?:-[0-9०-९]+)?\s*(?:[ऀ-ॿ]{3,10}\s*[-–—]\s*)?", "", masked)
  head_words = [
    w for w in regex.findall(r"[ऀ-ॿ]{3,}", _clean_sanskrit_surface(stripped_head))[:2]
    if w not in _STOPWORDS
  ]
  has_sutra_quote = bool(_SUTRA_QUOTE_RE.search(raw))
  has_grammar_cue = has_sutra_quote or any(g in raw for g in _GRAMMAR_CONT)
  return {
    "explicit_pratikas": explicit,
    "has_end_pratika": bool(end_cands),
    "bold_count": bold_count,
    "headwords": head_words,
    "lead_num": lead_num,
    "is_heading_only": is_heading_only,
    "is_colophon": bool(_COLOPHON_RE.match(raw)),
    "is_nigada_siddha": ("निगदसिद्ध" in raw or "निगदव्याख्यात" in raw),
    "is_sutra_continuation": (has_grammar_cue and bold_count == 0 and len(explicit) == 0),
  }


def classify_segment_role(
  segment: str,
  *,
  cues: dict | None = None,
  prev_role: str | None = None,
  seen_tika_on_core: bool = False,
) -> str:
  """Classify a segment's ``/interleaver`` role deterministically."""
  raw = (segment or "").strip()
  cues = cues or extract_segment_cues(raw)
  if cues["is_heading_only"]:
    return "heading"
  if "विनियोगसङ्ग्रहः" in raw:
    return "viniyoga_sangraha"
  if regex.match(r"^(?:\[\^?\d+\]:|>\s*\*?Note\b)", raw) and len(raw) >= 120:
    return "note"

  deva_n = len(regex.findall(r"[ऀ-ॿ]", raw))
  latin_n = len(regex.findall(r"[A-Za-z]", raw))
  if latin_n > deva_n * 2 and latin_n >= 4:
    low = raw.lower()
    if any(k in low for k in _EDITORIAL_EN):
      return "avatarika"
    if regex.match(r"^\*\((?:Mantra|Kaṇḍikā|Kandika|Anuvāka)", raw, regex.I) or (
      raw.startswith("*(") and any(k in low for k in _VINIYOGA_EN)
    ):
      return "viniyoga"
    return "translation"

  # Bold word-by-word glosses are always tika
  if cues["bold_count"] >= 1:
    return "tika"
  if any(k in raw for k in _MULTI_RK_AVA):
    return "avatarika"
  if any(k in raw for k in _VINIYOGA_SKT) or regex.search(r"\(सं॰\s*का॰", raw):
    return "viniyoga"
  if prev_role == "viniyoga" and not seen_tika_on_core:
    if regex.search(r"(?:माह\s*[-–—]?\s*$|स्कन्नमाज्य|निगडितः|अवरुद्धः)", raw):
      return "viniyoga"
  if not seen_tika_on_core and any(k in raw for k in _STUTI_AVA) and regex.search(r"[-–—]\s*\S+.*इति\s*॥?\s*$", raw):
    return "avatarika"
  return "tika"


def score_segment_against_cores(
  cues: dict,
  seg_norm: dict,
  core_norms: list[dict],
  stem_idf: dict[str, float],
) -> tuple[list[float], dict[int, str]]:
  """Score a segment against every core (target + lookahead) with matched witness."""
  def _anchored_match(needle: str, cm: str, st: frozenset[int]) -> bool:
    if len(needle) < 2 or len(cm) < 2:
      return False
    need = len(needle) if len(needle) < 5 else min((4 * len(needle) + 4) // 5, 12)
    sub = needle[:need]
    if any(cm.startswith(sub, o) for o in st):
      return True
    return len(needle) >= 5 and any(
      len(cm[o:o + need]) == need and sum(a != b for a, b in zip(sub, cm[o:o + need])) <= 1 for o in st
    )

  n_cores = len(core_norms)
  scores = [0.0] * n_cores
  witness: dict[int, str] = {}

  # Tier 1: Explicit pratīkas (`**bold**`, unquoted `... इति`, `"..."`)
  max_t1_hits = max(4, n_cores // 5)
  for pr in cues["explicit_pratikas"]:
    hits = [j for j in range(n_cores) if _anchored_match(pr, core_norms[j]["compact"], core_norms[j]["starts"])]
    if hits and (len(hits) <= max_t1_hits or len(pr) >= 7):
      bonus = 18.0 if len(hits) == 1 else (8.5 / math.sqrt(len(hits)))
      if len(pr) >= 5:
        bonus += 2.5
      for j in hits:
        cm, st = core_norms[j]["compact"], core_norms[j]["starts"]
        extra = 2.5 if any(cm.startswith(pr, o) for o in st) else 0.0
        if 0 in st and _anchored_match(pr, cm, frozenset({0})):
          extra += (4.5 if cues.get("has_end_pratika") else 2.0)
        scores[j] += bonus + extra
        witness.setdefault(j, pr)

  if cues.get("has_end_pratika") and sum(1 for v in scores if v >= 15.0) == 1:
    return scores, witness

  # Tier 2: Opening headword / root-derivative word-start match (`मेघायते`, `अभिवर्षणं` -> `अभिवर्षते`)
  max_t2_hits = max(3, n_cores // 6)
  for idx_h, hw in enumerate(cues["headwords"][:2]):
    hw_norm = normalize_for_alignment(hw)["compact"]
    hw_stem = _stem_of(hw)
    weight = 1.0 if idx_h == 0 else 0.55
    hits = []
    for j in range(n_cores):
      cm, st = core_norms[j]["compact"], core_norms[j]["starts"]
      if _anchored_match(hw_norm, cm, st) or (
        len(hw_stem) >= 3 and any(cm.startswith(hw_stem, o) for o in st)
      ):
        hits.append(j)
    if hits and len(hits) <= max_t2_hits:
      bonus = (12.0 if len(hits) == 1 else 5.0) * weight
      for j in hits:
        scores[j] += bonus
        witness.setdefault(j, hw)

  # Tier 3: IDF-weighted content-stem & compound-tail overlap (solves anvaya glosses)
  seg_compact = seg_norm["compact"]
  seg_stems = set(seg_norm["stems"])
  for j in range(n_cores):
    ov = 0.0
    for w, st in zip(core_norms[j]["words"], core_norms[j]["stems"]):
      idf = stem_idf.get(st, 1.0)
      if st in seg_stems or (len(w) >= 4 and w in seg_compact):
        ov += 2.2 * idf
        witness.setdefault(j, w)
    scores[j] += min(ov, 9.0)
  return scores, witness


def _viterbi_best_path(
  score_mat: list[list[float]],
  seg_cues: list[dict],
  prelim_roles: list[str],
  num_cores: int,
  total_c: int,
) -> list[int]:
  """Solve monotonic Viterbi path ``c_0 <= c_1 <= ...`` across ``total_c`` cores."""
  num_segs = len(score_mat)
  neg_inf = -1e9
  dp = [[neg_inf] * total_c for _ in range(num_segs)]
  back = [[0] * total_c for _ in range(num_segs)]
  for c in range(total_c):
    dp[0][c] = score_mat[0][c] - 1.6 * c

  last_seen_num = seg_cues[0]["lead_num"]
  for i in range(1, num_segs):
    cues_i = seg_cues[i]
    role_i = prelim_roles[i]
    max_sig = max(score_mat[i]) if score_mat[i] else 0.0
    prev_nigada = seg_cues[i - 1]["is_nigada_siddha"]
    cur_num = cues_i["lead_num"]
    new_mantra_num = cur_num is not None and (last_seen_num is None or cur_num > last_seen_num)
    if cur_num is not None:
      last_seen_num = cur_num
    for c in range(total_c):
      emit = score_mat[i][c] + (6.0 if cues_i["is_colophon"] and c == num_cores - 1 else 0.0)
      best_prev, best_p = neg_inf, 0
      for p in range(c + 1):
        trans = 0.0
        if p == c:
          if new_mantra_num:
            trans -= 7.0
          elif cues_i["is_sutra_continuation"] or max_sig < 3.0:
            trans += 2.2
          if prelim_roles[i - 1] in ("viniyoga", "avatarika", "heading") and role_i == "tika" and not prev_nigada and not new_mantra_num:
            trans += 4.0
          if role_i in ("viniyoga", "avatarika", "heading") and prelim_roles[i - 1] == "tika":
            trans -= 4.5
          if prev_nigada and role_i == "tika":
            trans -= 3.5
        else:
          jump = c - p
          trans -= (1.25 * jump if jump <= 2 else 2.5 + 3.2 * (jump - 2))
          if p < num_cores and c >= num_cores:
            best_active = max(score_mat[i][:num_cores]) if num_cores else 0.0
            strong_upcoming = emit >= 9.0 and (emit - best_active) >= 2.5
            if not (strong_upcoming or new_mantra_num or (role_i in ("viniyoga", "avatarika", "heading") and prelim_roles[i - 1] == "tika")):
              trans -= 12.0
          if new_mantra_num and jump == 1:
            trans += 5.5
          elif cues_i["is_sutra_continuation"]:
            trans -= 6.0
          elif max_sig < 2.8 and role_i == "tika" and not cues_i["is_colophon"] and not prev_nigada and not new_mantra_num:
            trans -= 2.4
          if role_i in ("viniyoga", "avatarika", "heading") and prelim_roles[i - 1] == "tika" and jump == 1:
            trans += 3.5
        cand_v = dp[i - 1][p] + trans + emit
        if cand_v > best_prev:
          best_prev, best_p = cand_v, p
      dp[i][c] = best_prev
      back[i][c] = best_p

  best_end = max(range(total_c), key=lambda c: dp[num_segs - 1][c])
  path = [0] * num_segs
  path[num_segs - 1] = best_end
  for i in range(num_segs - 1, 0, -1):
    path[i - 1] = back[i][path[i]]
  return path


def align_commentary_segments(
  cores: list[str],
  segments: list[str],
  *,
  upcoming_cores: list[str] | None = None,
  is_sarvash_tikah: bool = False,
) -> dict:
  """Align segments monotonically to ``cores`` (+ ``upcoming_cores``) via Viterbi DP."""
  num_cores = len(cores)
  num_segs = len(segments)
  if num_cores == 0 or num_segs == 0:
    return {"assignments": [], "unmatched_from": 0, "hints": []}

  all_cores = list(cores) + list(upcoming_cores or [])
  total_c = len(all_cores)
  core_norms = [normalize_for_alignment(c) for c in all_cores]
  seg_norms = [normalize_for_alignment(_SUTRA_QUOTE_RE.sub(" ", s)) for s in segments]
  seg_cues = [extract_segment_cues(s) for s in segments]

  df: dict[str, int] = {}
  for cn in core_norms:
    for st in set(cn["stems"]):
      df[st] = df.get(st, 0) + 1
  stem_idf = {st: math.log((total_c + 1.0) / (cnt + 0.5)) + 0.5 for st, cnt in df.items()}

  score_mat, wit_mat, prelim_roles = [], [], []
  prev_r: str | None = None
  seen_tika = False
  for s_idx, seg in enumerate(segments):
    sc, wit = score_segment_against_cores(seg_cues[s_idx], seg_norms[s_idx], core_norms, stem_idf)
    score_mat.append(sc)
    wit_mat.append(wit)
    best_s = max(sc) if sc else 0.0
    role = classify_segment_role(seg, cues=seg_cues[s_idx], prev_role=prev_r, seen_tika_on_core=(seen_tika and best_s < 6.0))
    prelim_roles.append(role)
    seen_tika = True if role == "tika" else (False if role in ("viniyoga", "avatarika", "heading") else seen_tika)
    prev_r = role

  path = _viterbi_best_path(score_mat, seg_cues, prelim_roles, num_cores, total_c)

  # Finalize unmatched_from (first segment assigned to upcoming core >= num_cores)
  unmatched_from = next((i for i, c in enumerate(path) if c >= num_cores), num_segs)
  assignments = []
  prev_role_on_core: dict[int, str] = {}
  seen_tika_core: set[int] = set()
  for i in range(unmatched_from):
    c = path[i]
    role = classify_segment_role(
      segments[i],
      cues=seg_cues[i],
      prev_role=prev_role_on_core.get(c),
      seen_tika_on_core=(c in seen_tika_core),
    )
    if role == "tika":
      seen_tika_core.add(c)
    prev_role_on_core[c] = role
    assignments.append({"seg": i, "core": c, "role": role})

  # Intra-core ordering invariant: segments on core c preceding its last viniyoga
  # (without bold word-by-word glosses) belong to that core's leading viniyoga block.
  last_vin_by_core: dict[int, int] = {}
  for a in assignments:
    if a["role"] == "viniyoga":
      last_vin_by_core[a["core"]] = a["seg"]
  for a in assignments:
    last_v = last_vin_by_core.get(a["core"], -1)
    if a["seg"] < last_v and a["role"] == "tika" and seg_cues[a["seg"]]["bold_count"] == 0:
      a["role"] = "viniyoga"

  hints = []
  for i in range(num_segs):
    sc = score_mat[i]
    best_c = max(range(total_c), key=lambda c: sc[c])
    second_s = max([sc[c] for c in range(total_c) if c != best_c], default=0.0)
    lbl = f"CORE {best_c}" if best_c < num_cores else f"UPCOMING {best_c - num_cores}"
    hit = wit_mat[i].get(best_c, "")
    conf = "strong" if (sc[best_c] >= 9.0 and sc[best_c] - second_s >= 4.0) else ("weak" if sc[best_c] >= 3.0 else "cont")
    hints.append({
      "seg": i,
      "best_target": lbl,
      "best_idx": best_c,
      "score": round(sc[best_c], 2),
      "margin": round(sc[best_c] - second_s, 2),
      "confidence": conf,
      "witness": hit,
      "role_hint": prelim_roles[i],
    })
  return {"assignments": assignments, "unmatched_from": unmatched_from, "hints": hints}


def refine_interleave_plan(
  plan: dict,
  cores: list[str],
  segments: list[str],
  *,
  upcoming_cores: list[str] | None = None,
  is_sarvash_tikah: bool = False,
) -> dict:
  """Post-guard an LLM JSON plan with strong unique-pratīka anchors & monotonicity."""
  dp_plan = align_commentary_segments(
    cores, segments, upcoming_cores=upcoming_cores, is_sarvash_tikah=is_sarvash_tikah
  )
  hints = dp_plan["hints"]
  num_cores = len(cores)
  unmatched = int(plan.get("unmatched_from", dp_plan["unmatched_from"]))
  # If a segment has a strong unique match to an upcoming core, cap unmatched_from
  for h in hints:
    if h["confidence"] == "strong" and h["best_idx"] >= num_cores:
      unmatched = min(unmatched, h["seg"])
      break

  by_seg = {int(a["seg"]): dict(a) for a in plan.get("assignments", []) if int(a["seg"]) < unmatched}
  dp_by_seg = {a["seg"]: a for a in dp_plan["assignments"]}
  repaired: list[dict] = []
  floor_core = 0
  for i in range(unmatched):
    item = by_seg.get(i) or dict(dp_by_seg.get(i, {"seg": i, "core": floor_core, "role": hints[i]["role_hint"]}))
    h = hints[i]
    c = int(item["core"])
    if h["confidence"] == "strong" and h["best_idx"] < num_cores and h["best_idx"] >= floor_core:
      c = h["best_idx"]
    c = min(num_cores - 1, max(floor_core, c))
    floor_core = c
    # Override multi-rk vs single-rk chandas & bold-gloss role mistakes deterministically
    role = item["role"]
    if any(k in segments[i] for k in _MULTI_RK_AVA):
      role = "avatarika"
    elif extract_segment_cues(segments[i])["bold_count"] >= 1 and role in ("avatarika", "viniyoga"):
      role = "tika"
    repaired.append({"seg": i, "core": c, "role": role})
  return {"assignments": repaired, "unmatched_from": unmatched}
