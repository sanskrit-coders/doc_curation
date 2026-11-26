"""Bilingual Sanskrit<->English monotonic DP aligner & LLM post-guard for ``translation_matcher``.

Provides:
1. Automatic IAST-to-SLP1 stem matching + discourse-pivot & technical-lexicon
   anchor extraction (``find_core_anchor_hits``).
2. Exact monotonic dynamic programming over candidate English clause/sentence
   boundaries (``align_cores_to_translation_dp``) honoring ``translation_matcher``'s
   ``{"starts": {...}, "skip": [...], "next_en": int}`` schema & invariants.
3. ``local_translation_generate_fn`` (drop-in zero-GPU ``generate_fn`` for
   ``doc_curation.llm.translation_matcher``) and ``refine_translation_mapping``
   (post-guard that snaps noisy LLM word indices onto crisp clause boundaries and
   eliminates schema/validation failures).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import tomllib
from indic_transliteration import sanscript
import regex

from .interleave_aligner import _clean_sanskrit_surface

_RULES_PATH = Path(__file__).resolve().parent / "data" / "translation_rules.toml"
with _RULES_PATH.open("rb") as _f:
  _TR_RULES = tomllib.load(_f)

_SKIP_RES = tuple(regex.compile(p) for p in _TR_RULES["skip_regexes"])
_OPENING_PIVOTS: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
  (skt, tuple(ens)) for skt, ens in _TR_RULES["opening_pivots"]
)
_LEXICON: dict[str, tuple[str, ...]] = {
  k: tuple(v) for k, v in _TR_RULES["lexicon"].items()
}
_EN_COMMON_STOP = frozenset({
  "the", "this", "that", "these", "those", "there", "here", "where", "when",
  "which", "what", "who", "whom", "whose", "from", "with", "into", "unto",
  "have", "has", "had", "been", "being", "were", "will", "shall", "should",
  "would", "could", "also", "only", "other", "such", "some", "many", "more",
  "most", "very", "same", "each", "every", "both", "either", "neither",
})


def is_skippable_core(core_text: str) -> bool:
  """Return True if ``core_text`` is a bare rhetorical question, colophon, or synonym gloss."""
  cleaned = regex.sub(r"^[>\s*]+", "", (core_text or "").strip())
  if any(r.match(cleaned) for r in _SKIP_RES):
    return True
  words = regex.findall(r"[ऀ-ॿ]+", cleaned)
  if len(words) <= 2 and cleaned.endswith("?"):
    return True
  if len(words) <= 8 and "इति यावत्" in cleaned:
    return True
  return False


def candidate_word_starts(en_words: list[str]) -> dict[int, float]:
  """Map valid span-start word indices ``0..len(en_words)`` to boundary bonuses."""
  n = len(en_words)
  cands: dict[int, float] = {0: 3.0, n: 2.5}
  conj_starts = {"or", "and", "nor", "but", "yet", "for", "so", "where", "when", "which", "who", "that", "as"}
  for i in range(1, n):
    prev = en_words[i - 1]
    cur = en_words[i]
    cur_low = cur.lstrip("('\"“‘-–—").lower()
    if cur.startswith(("--", "—", "–")):
      cands[i] = 3.2
    elif prev.endswith((".", "?", "!", ".'", '."', "'.", '".', ").", "?'", '?"', "'?", '"?')):
      cands[i] = 2.6
    elif prev.endswith((";", ":", ";'", ":'", "';", '";', "':", '":')):
      cands[i] = 1.8
    elif prev.lower() in ("&c.", "etc.", "&c.,"):
      cands[i] = 2.0
    elif prev.endswith((",", ",'", ',"', "',", '",', "),")) or cur.startswith(("'", '"', "‘", "“", "(")):
      cands[i] = 0.8
    elif cur_low in conj_starts:
      cands[i] = 0.6
  return cands


def _iast_slp1_tokens(en_words: list[str]) -> list[tuple[int, str]]:
  """Extract potential transliterated Sanskrit stems (IAST -> SLP1) from English words."""
  out: list[tuple[int, str]] = []
  for idx, w in enumerate(en_words):
    clean = w.strip(".,;:!?()[]'\"“”‘’—–-")
    if len(clean) < 4 or clean.lower() in _EN_COMMON_STOP:
      continue
    has_diacritic = any(ord(c) > 127 for c in clean)
    is_mid_cap = idx > 0 and clean[0].isupper() and not en_words[idx - 1].endswith((".", "?", "!", ".'", '."'))
    if has_diacritic or is_mid_cap:
      norm_iast = clean.replace("ḥ", "h").replace("cḥ", "ch").replace("Cḥ", "Ch").lower()
      norm_iast = norm_iast.replace("sh", "ṣ").replace("ch", "c").replace("ṛi", "ṛ")
      slp = sanscript.transliterate(norm_iast, sanscript.IAST, sanscript.SLP1)
      slp = regex.sub(r"[^a-zA-Z]", "", slp)
      if len(slp) >= 4:
        out.append((idx, slp[:6]))
  return out


def find_core_anchor_hits(
  core_text: str,
  en_words: list[str],
  iast_stems: list[tuple[int, str]] | None = None,
) -> dict:
  """Identify opening pivot positions and lexical/IAST word hits for ``core_text``."""
  surf = _clean_sanskrit_surface(core_text)
  head_skt = surf[:45]
  n = len(en_words)
  en_joined_at = [
    " ".join(w.lstrip("('\"“‘").lower() for w in en_words[i:min(n, i + 4)])
    for i in range(n)
  ]

  opening_hits: list[int] = []
  hard_num_hits: list[int] = []
  # Match leading sūtra/mantra numbers (`२९.` or `॥ १-१-२९ ॥`) to `29.` in English
  dev_to_ascii = str.maketrans("०१२३४५६७८९", "0123456789")
  lead_m = regex.match(r"^\s*[>*\s]*([०-९0-9]{1,3})\.", core_text)
  danda_m = regex.search(r"॥\s*(?:[०-९0-9]+[-.]){1,3}([०-९0-9]{1,3})\s*॥", core_text)
  target_nums = {
    m.group(1).translate(dev_to_ascii) for m in (lead_m, danda_m) if m is not None
  }
  if target_nums:
    expanded_nums = set(target_nums)
    for tn in list(target_nums):
      if tn.isdigit() and int(tn) > 1:
        expanded_nums.add(str(int(tn) - 1))  # Cross-recension sūtra offset (e.g. Thibaut 28. = Rāmānuja २९.)
    for i, w in enumerate(en_words):
      w_num = w.strip("()[]").rstrip(".")
      if w.endswith(".") and w_num in expanded_nums and (i == 0 or en_words[i - 1].endswith((".", "?", "!", ".'", '."'))):
        hard_num_hits.append(i)
        opening_hits.append(i)

  for skt_cue, en_prefixes in _OPENING_PIVOTS:
    if skt_cue in head_skt or skt_cue in core_text[:45]:
      for i, phrase in enumerate(en_joined_at):
        raw_i = en_words[i].lower()
        if any(phrase.startswith(ep) or raw_i.startswith(ep) for ep in en_prefixes):
          opening_hits.append(i)

  word_hits: list[tuple[int, str, float]] = []
  seen_pos: set[int] = set()
  for skt_stem, en_terms in _LEXICON.items():
    if skt_stem in surf or skt_stem in core_text:
      for i, phrase in enumerate(en_joined_at):
        if i not in seen_pos and any(phrase.startswith(t) for t in en_terms):
          seen_pos.add(i)
          word_hits.append((i, en_words[i], 2.4 if len(skt_stem) >= 4 else 1.5))

  core_slp = sanscript.transliterate(surf, sanscript.DEVANAGARI, sanscript.SLP1)
  for idx, slp_pref in (iast_stems if iast_stems is not None else _iast_slp1_tokens(en_words)):
    if idx not in seen_pos and slp_pref[:4] in core_slp:
      seen_pos.add(idx)
      word_hits.append((idx, en_words[idx], 3.0))

  is_sruti_citation = bool(regex.search(r"^\s*>|\([^)\n]*[०-९0-9]+\.[०-९0-9]+", core_text))
  has_quote = is_sruti_citation or ("इति" in core_text)
  return {
    "opening_hits": sorted(set(opening_hits)),
    "opening_set": frozenset(opening_hits),
    "hard_num_set": frozenset(hard_num_hits),
    "word_hits": sorted(word_hits, key=lambda x: x[0]),
    "has_quote": has_quote,
    "is_sruti_citation": is_sruti_citation,
    "skt_chars": max(6, len(regex.sub(r"\s+", "", surf))),
    "skippable": is_skippable_core(core_text),
  }


def _score_span_for_core(
  info: dict,
  s: int,
  e: int,
  cand_bonuses: dict[int, float],
  prefix_chars: list[int],
  hit_pref: list[float],
  quote_pref: list[int],
  etc_at: frozenset[int],
) -> float:
  """Score English word span ``[s, e)`` as the rendering of ``info`` in O(1) time."""
  if e == s:
    if info["skippable"]:
      return 3.5
    if info["is_sruti_citation"] and (s in etc_at or (s - 1) in etc_at):
      return 1.8
    return -9.5

  score = cand_bonuses.get(s, -3.5)
  if s in info["hard_num_set"]:
    score += 22.0
  elif s in info["opening_set"] or (s + 1) in info["opening_set"]:
    score += 9.5

  score += min(11.0, hit_pref[e] - hit_pref[s])
  if info["has_quote"] and (quote_pref[e] - quote_pref[s]) > 0:
    score += 1.6

  en_chars = prefix_chars[e] - prefix_chars[s]
  expected = 2.35 * info["skt_chars"] + 14.0
  ratio_pen = 3.1 * abs(math.log((en_chars + 14.0) / expected))
  return score - ratio_pen


def _solve_monotone_span_dp(
  infos: list[dict],
  cand_bonuses: dict[int, float],
  en_words: list[str],
  *,
  n_primary: int | None = None,
  require_full_end: bool = False,
  upcoming_start_idx: int | None = None,
) -> list[int]:
  """Run monotonic Viterbi DP over ``pos_list`` split points, returning ``word_bounds``."""
  wlen = len(en_words)
  pos_list = sorted(cand_bonuses.keys())
  n_pos = len(pos_list)
  prefix_chars = [0] * (wlen + 1)
  quote_pref = [0] * (wlen + 1)
  etc_at = frozenset(k + 1 for k, w in enumerate(en_words) if w.lower().startswith(("&c", "etc")))
  for k, w in enumerate(en_words):
    prefix_chars[k + 1] = prefix_chars[k] + len(w) + 1
    quote_pref[k + 1] = quote_pref[k] + int(w.startswith(("'", '"', "‘", "“")))

  total_k = len(infos)
  up_from = total_k if upcoming_start_idx is None else upcoming_start_idx
  out_k = total_k if n_primary is None else n_primary
  neg_inf = -1e9
  dp = [[neg_inf] * n_pos for _ in range(total_k + 1)]
  back = [[0] * n_pos for _ in range(total_k + 1)]
  dp[0][0] = 0.0

  for k, inf in enumerate(infos):
    is_up = k >= up_from
    max_span_chars = max(900, 12 * inf["skt_chars"]) if require_full_end else None
    hit_pref = [0.0] * (wlen + 1)
    h_map = {pos: wt for pos, _, wt in inf["word_hits"]}
    for idx_w in range(wlen):
      hit_pref[idx_w + 1] = hit_pref[idx_w] + h_map.get(idx_w, 0.0)
    for j_idx in range(n_pos):
      e = pos_list[j_idx]
      best_v, best_i = neg_inf, 0
      i_iter = range(j_idx, -1, -1) if max_span_chars is not None else range(j_idx + 1)
      for i_idx in i_iter:
        s = pos_list[i_idx]
        if max_span_chars is not None and prefix_chars[e] - prefix_chars[s] > max_span_chars and best_v > neg_inf / 2:
          break
        prev_v = dp[k][i_idx]
        if prev_v <= neg_inf / 2:
          continue
        if is_up and e == s:
          sp_score = 1.5 if s == wlen else -0.5
        else:
          sp_score = _score_span_for_core(inf, s, e, cand_bonuses, prefix_chars, hit_pref, quote_pref, etc_at)
        cand_v = prev_v + sp_score
        if cand_v > best_v:
          best_v, best_i = cand_v, i_idx
      dp[k + 1][j_idx] = best_v
      back[k + 1][j_idx] = best_i

  if require_full_end:
    best_end_j = n_pos - 1
  else:
    best_end_j = max(
      range(n_pos),
      key=lambda j: dp[total_k][j] - (0.04 * (wlen - pos_list[j]) if up_from == total_k else 0.0),
    )
  bounds_idx = [0] * (total_k + 1)
  bounds_idx[total_k] = best_end_j
  for k in range(total_k, 0, -1):
    bounds_idx[k - 1] = back[k][bounds_idx[k]]
  bounds = [pos_list[idx] for idx in bounds_idx[: out_k + 1]]
  bounds[0] = 0
  if require_full_end:
    bounds[out_k] = wlen
  return bounds


def tokenize_with_offsets(en_text: str) -> tuple[list[str], list[tuple[int, int]], set[int]]:
  """Return ``(words, char_spans, newline_start_indices)`` preserving source formatting."""
  words: list[str] = []
  spans: list[tuple[int, int]] = []
  nl_starts: set[int] = set()
  prev_end = 0
  for m in regex.finditer(r"\S+", en_text or ""):
    gap = en_text[prev_end:m.start()]
    idx = len(words)
    if idx > 0 and "\n" in gap:
      nl_starts.add(idx)
    words.append(m.group(0))
    spans.append((m.start(), m.end()))
    prev_end = m.end()
  return words, spans, nl_starts


def align_cores_to_formatted_translation(cores: list[str], en_text: str) -> list[str]:
  """Align ordered Sanskrit ``cores`` onto formatted English ``en_text``, preserving source newlines."""
  if not cores:
    return []
  if len(cores) == 1:
    return [(en_text or "").strip()]
  words, spans, nl_starts = tokenize_with_offsets(en_text)
  if not words:
    return ["" for _ in cores]

  cand_bonuses = candidate_word_starts(words)
  for ni in nl_starts:
    cand_bonuses[ni] = max(cand_bonuses.get(ni, 0.0), 4.0)
  if len(cand_bonuses) < len(cores) + 4:
    for wi, w in enumerate(words[:-1]):
      if w.endswith((";", ":")):
        cand_bonuses.setdefault(wi + 1, 1.5)
  if len(cand_bonuses) < len(cores) + 2:
    for wi, w in enumerate(words[:-1]):
      if w.endswith((",", "—", "–", '"', "”", "’")):
        cand_bonuses.setdefault(wi + 1, -0.3)
  if len(cand_bonuses) < len(cores) + 1:
    step = max(1, len(words) // max(1, len(cores) * 2))
    for wi in range(1, len(words), step):
      cand_bonuses.setdefault(wi, -1.8)

  iast_stems = _iast_slp1_tokens(words)
  infos = [find_core_anchor_hits(c, words, iast_stems) for c in cores]
  for inf in infos:
    for oh in inf["opening_hits"]:
      if 0 <= oh <= len(words):
        cand_bonuses.setdefault(oh, 1.5)

  word_bounds = _solve_monotone_span_dp(
    infos, cand_bonuses, words, n_primary=len(cores), require_full_end=True
  )
  results: list[str] = []
  for k in range(len(cores)):
    ws, we = word_bounds[k], word_bounds[k + 1]
    if we <= ws:
      results.append("")
    else:
      results.append(en_text[spans[ws][0] : spans[we - 1][1]].strip())
  return results


def align_cores_to_translation_dp(
  cores: list[str],
  en_words: list[str],
  *,
  c_start: int = 0,
  upcoming_cores: list[str] | None = None,
) -> dict:
  """Align ``cores`` monotonically to ``en_words`` (`{"starts", "skip", "next_en"}`)."""
  n_cores = len(cores)
  wlen = len(en_words)
  if n_cores == 0:
    return {"starts": {}, "skip": [], "next_en": 0}
  if wlen == 0:
    return {
      "starts": {str(c_start + i): 0 for i in range(n_cores)},
      "skip": [c_start + i for i in range(n_cores)],
      "next_en": 0,
    }

  upcoming = list(upcoming_cores or [])[:2]
  all_cores = list(cores) + upcoming
  cand_bonuses = candidate_word_starts(en_words)
  iast_stems = _iast_slp1_tokens(en_words)
  infos = [find_core_anchor_hits(c, en_words, iast_stems) for c in all_cores]
  # Ensure all opening hits are also candidate split positions
  for inf in infos:
    for oh in inf["opening_hits"]:
      if 0 <= oh <= wlen:
        cand_bonuses.setdefault(oh, 1.5)

  word_bounds = _solve_monotone_span_dp(
    infos,
    cand_bonuses,
    en_words,
    n_primary=n_cores,
    require_full_end=False,
    upcoming_start_idx=n_cores,
  )
  starts = {str(c_start + i): word_bounds[i] for i in range(n_cores)}
  next_en = word_bounds[n_cores]
  skips = [c_start + i for i in range(n_cores) if word_bounds[i + 1] == word_bounds[i]]
  # Guard against stalling (`next_en == 0` when `wlen > 0` and not all genuinely skippable)
  if next_en == 0 and wlen > 0 and len(skips) == n_cores:
    skips = [c_start + i for i in range(1, n_cores)]
    for i in range(1, n_cores):
      starts[str(c_start + i)] = wlen
    next_en = wlen
  return {"starts": starts, "skip": skips, "next_en": next_en}


def parse_translation_matcher_prompt(prompt_text: str) -> dict | None:
  """Parse ``(c_start, cores, en_words, upcoming_cores)`` from a matcher prompt."""
  if "CORE TEXTS:\n" not in prompt_text or "TRANSLATION WORDS" not in prompt_text:
    return None
  core_sec = prompt_text.split("CORE TEXTS:\n", 1)[1].split("\n\nTRANSLATION WORDS", 1)[0]
  core_matches = list(regex.finditer(r"(?m)^(?:core\[(\d+)\]:|\[(\d+)\])\s*(?:✓\s*|\{[^}\n]*\}\s*)?(.*)$", core_sec))
  if not core_matches:
    return None
  c_start = int(core_matches[0].group(1) or core_matches[0].group(2))
  cores = [m.group(3).strip() for m in core_matches]

  after_tw = regex.split(r"TRANSLATION WORDS[^\n]*:\n", prompt_text, maxsplit=1)[1]
  tw_body = regex.split(r"\n\n(?:UPCOMING CORES|BILINGUAL|Reply with ONLY)", after_tw, maxsplit=1)[0]
  raw_tokens = tw_body.split()
  # Strip `[0]`, `[1]`, ... index tags if already annotated
  if len(raw_tokens) >= 2 and raw_tokens[0] == "[0]":
    en_words = [tok for tok in raw_tokens if not regex.fullmatch(r"\[\d+\]", tok)]
  else:
    en_words = raw_tokens

  upcoming: list[str] = []
  if "UPCOMING CORES" in after_tw:
    up_sec = after_tw.split("UPCOMING CORES", 1)[1].split("\n\n", 1)[0]
    for um in regex.finditer(r"(?m)^(?:core\[\d+\]:|\[\d+\])\s*(.*)$", up_sec):
      upcoming.append(um.group(1).strip())
  return {"c_start": c_start, "cores": cores, "en_words": en_words, "upcoming_cores": upcoming}


def local_translation_generate_fn(prompt_text: str) -> str:
  """Drop-in zero-GPU ``generate_fn`` for ``doc_curation.llm.translation_matcher``."""
  parsed = parse_translation_matcher_prompt(prompt_text)
  if parsed is None:
    raise ValueError("Prompt is not a recognized translation_matcher batch prompt")
  res = align_cores_to_translation_dp(
    parsed["cores"],
    parsed["en_words"],
    c_start=parsed["c_start"],
    upcoming_cores=parsed["upcoming_cores"],
  )
  return json.dumps(res, ensure_ascii=False)


def refine_translation_mapping(raw_reply: str, prompt_text: str) -> str:
  """Validate & boundary-snap an LLM JSON reply for ``translation_matcher``,
  falling back to ``align_cores_to_translation_dp`` on malformed output."""
  parsed_p = parse_translation_matcher_prompt(prompt_text)
  if parsed_p is None:
    return raw_reply
  c_start = parsed_p["c_start"]
  cores = parsed_p["cores"]
  en_words = parsed_p["en_words"]
  wlen = len(en_words)
  n_cores = len(cores)
  cand_bonuses = candidate_word_starts(en_words)

  try:
    m = regex.search(r"\{.*\}", raw_reply or "", flags=regex.DOTALL)
    data = json.loads(m.group(0) if m else raw_reply)
    raw_starts = {int(k): int(v) for k, v in data["starts"].items()}
    next_en = int(data["next_en"])
  except Exception:
    return local_translation_generate_fn(prompt_text)

  # Detect & repair 2x whitespace-index doubling if model counted `[i]` tags as words
  max_v = max([next_en, *raw_starts.values()], default=0)
  if max_v > wlen and max_v <= 2 * wlen + 2:
    raw_starts = {k: v // 2 for k, v in raw_starts.items()}
    next_en = min(wlen, next_en // 2)

  # Clamp monotonic starts & snap within ±1 word onto strong sentence/dash boundaries
  bounds = [0]
  for k in range(1, n_cores):
    v = min(wlen, max(bounds[-1], raw_starts.get(c_start + k, bounds[-1])))
    if v not in cand_bonuses:
      for delta in (-1, 1):
        if 0 < v + delta <= wlen and (v + delta) >= bounds[-1] and cand_bonuses.get(v + delta, 0.0) >= 2.5:
          v = v + delta
          break
    bounds.append(v)
  next_en = min(wlen, max(bounds[-1], next_en))
  if next_en not in cand_bonuses:
    for delta in (-1, 1):
      if bounds[-1] <= next_en + delta <= wlen and cand_bonuses.get(next_en + delta, 0.0) >= 2.5:
        next_en = next_en + delta
        break
  bounds.append(next_en)

  skips = [c_start + i for i in range(n_cores) if bounds[i + 1] == bounds[i]]
  if next_en == 0 and wlen > 0 and len(skips) == n_cores:
    return local_translation_generate_fn(prompt_text)
  out = {
    "starts": {str(c_start + i): bounds[i] for i in range(n_cores)},
    "skip": skips,
    "next_en": next_en,
  }
  return json.dumps(out, ensure_ascii=False)
