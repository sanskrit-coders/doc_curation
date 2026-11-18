"""Deterministic pre-masking and post-generation verification guards.

Honors the updated ``proofreader-hyphenator`` skill invariants:
1. ``<details><summary>मूलम्...</summary>...</details>`` blocks are masked before
   inference and restored byte-for-byte afterward.
2. **Inline** non-separable dīrgha/guṇa/vṛddhi mergers (e.g. ``धर्मार्थ``, ``महोत्सव``,
   ``सदैव``) are snapped back if split by an inline hyphen ``-``/``–``.
3. **Cross-newline** sandhi reversions (e.g. ``सतीक्षणादयः`` -> ``सति  \\nईक्षणादयः``,
   ``परमात्मेति`` -> ``परमात्मा\\n\\nइति``, ``मृत्युस्तस्यार्थस्य`` -> ``मृत्युः  \\nतस्यार्थस्य``)
   and inserted sentence-ending daṇḍas (``।``) are recognized as valid structural
   formatting — never falsely wrapped in ``[[OLD|NEW]]``.
4. Any genuine inline silent lexical edit is wrapped as ``[[OLD|NEW]]`` (never
   spanning a newline).
"""
from __future__ import annotations

import difflib
import regex
from indic_transliteration.sanscript.schemes.brahmic import accent

_MULAM_DETAILS_RE = regex.compile(
  r"<details(?:\s+open)?\s*>\s*<summary>\s*मूलम्[^<]*</summary>.*?</details>",
  flags=regex.DOTALL,
)
_SUG_OR_TAG_RE = regex.compile(
  r"\[\[[^\]]+\]\]|<<MULAM_\d{4}>>|<!--.*?-->|<[^>]+>"
)
_CODE_FENCE_WRAP_RE = regex.compile(
  r"^\s*```(?:markdown|md)?\s*\n(.*?)\n?\s*```\s*$",
  flags=regex.DOTALL,
)
_THINK_BLOCK_RE = regex.compile(r"^\s*<think>.*?</think>\s*", flags=regex.DOTALL)

_INDEP_VOWEL_TO_MATRA = {
  "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
  "ऋ": "ृ", "ॠ": "ॄ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ",
}
_HALANT_VOWEL_RE = regex.compile(
  r"([\u0915-\u0939])\u094d[\s\-\u2013\u2014]+([\u0905-\u0914])"
)
_VOWEL_SANDHI_MERGER = {
  ("", "अ"): "ा", ("", "आ"): "ा", ("ा", "अ"): "ा", ("ा", "आ"): "ा",
  ("", "इ"): "े", ("", "ई"): "े", ("ा", "इ"): "े", ("ा", "ई"): "े",
  ("", "उ"): "ो", ("", "ऊ"): "ो", ("ा", "उ"): "ो", ("ा", "ऊ"): "ो",
  ("", "ऋ"): "र्", ("ा", "ऋ"): "र्",
  ("", "ए"): "ै", ("", "ऐ"): "ै", ("ा", "ए"): "ै", ("ा", "ऐ"): "ै",
  ("", "ओ"): "ौ", ("", "औ"): "ौ", ("ा", "ओ"): "ौ", ("ा", "औ"): "ौ",
  ("ि", "इ"): "ी", ("ि", "ई"): "ी", ("ी", "इ"): "ी", ("ी", "ई"): "ी",
  ("ु", "उ"): "ू", ("ु", "ऊ"): "ू", ("ू", "उ"): "ू", ("ू", "ऊ"): "ू",
  ("ृ", "ऋ"): "ॄ", ("ृ", "ॠ"): "ॄ",
}
_YAN_SANDHI = {"ि": "्य्", "ी": "्य्", "ु": "्व्", "ू": "्व्", "ृ": "्र्"}
_DEV_WORD_CHUNK_RE = regex.compile(
  r"\[\[([^|\]]+)\|([^\]]+)\]\]|\[\[\?\?\]\]|\[\[P\d+[a-zA-Z]?\]\]|"
  r"<<MULAM_\d{4}>>|<!--.*?-->|"
  r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff]+(?:[-–—]+[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff]+)*"
)


def strip_llm_wrappers(text: str) -> str:
  if not text:
    return ""
  cleaned = _THINK_BLOCK_RE.sub("", text)
  m = _CODE_FENCE_WRAP_RE.match(cleaned)
  return m.group(1) if m else cleaned


def mask_protected_blocks(text: str) -> tuple[str, dict[str, str]]:
  masks: dict[str, str] = {}

  def _repl(m: regex.Match) -> str:
    key = f"<<MULAM_{len(masks):04d}>>"
    masks[key] = m.group(0)
    return key

  return _MULAM_DETAILS_RE.sub(_repl, text), masks


def restore_protected_blocks(text: str, masks: dict[str, str]) -> str:
  out = text
  for key, orig in masks.items():
    out = out.replace(key, orig)
  return out


def canonical_sandhi_skeleton(text: str) -> str:
  """Collapse inline separable-sandhi splits & separators to a canonical skeleton."""
  s = accent.strip_accents(text)
  prev = None
  while prev != s:
    prev = s
    s = _HALANT_VOWEL_RE.sub(
      lambda m: m.group(1) if m.group(2) == "अ" else m.group(1) + _INDEP_VOWEL_TO_MATRA.get(m.group(2), m.group(2)),
      s,
    )
  s = regex.sub(r"[ङञणनम]\u094d", "ं", s).replace("ँ", "ं")
  return regex.sub(r"[\s\-\u2013\u2014]+", "", s)


def forward_fuse_candidates(left: str, right: str) -> set[str]:
  """Return plausible forward-sandhi merged skeletons of ``(left, right)`` across a newline."""
  l_clean = regex.sub(r"[\s\-\u2013\u2014>]+", "", accent.strip_accents(left))
  r_clean = regex.sub(r"[\s\-\u2013\u2014>]+", "", accent.strip_accents(right))
  if not l_clean or not r_clean:
    return set()
  cands = {canonical_sandhi_skeleton(l_clean + " " + r_clean)}
  r0 = r_clean[0]

  # 1. Vowel sandhi (dīrgha, guṇa, vṛddhi, yaṇ) when right starts with independent vowel
  if r0 in "अआइईउऊऋॠएऐओऔ":
    last = l_clean[-1]
    stem, matra = (l_clean[:-1], last) if "\u093e" <= last <= "\u094c" else (l_clean, "" if "\u0915" <= last <= "\u0939" else None)
    if matra is not None:
      merged_m = _VOWEL_SANDHI_MERGER.get((matra, r0))
      if merged_m is not None:
        cands.add(canonical_sandhi_skeleton(stem + merged_m + r_clean[1:]))
      if matra in _YAN_SANDHI:
        cands.add(canonical_sandhi_skeleton(stem + _YAN_SANDHI[matra] + " " + r_clean))
    # Elided avagraha or पूर्वसवर्ण: e.g. आत्मा + ऽन्तर्यामी / अन्तर्यामी
    if last in ("े", "ो") and r0 == "अ":
      cands.add(canonical_sandhi_skeleton(l_clean + "ऽ" + r_clean[1:]))

  # 2. Visarga sandhi (ः -> स्/श्/ष्/र्/ो/lopa)
  if l_clean.endswith("ः"):
    base = l_clean[:-1]
    if r0 in ("त", "थ", "स"):
      cands.add(canonical_sandhi_skeleton(base + "स्" + r_clean))
    elif r0 in ("च", "छ", "श"):
      cands.add(canonical_sandhi_skeleton(base + "श्" + r_clean))
    elif r0 in ("ट", "ठ", "ष"):
      cands.add(canonical_sandhi_skeleton(base + "ष्" + r_clean))
    if base and ("\u0915" <= base[-1] <= "\u0939"):
      # -aH + a -> -o' ; -aH + voiced/V -> -o or -a (lopa)
      if r0 == "अ":
        cands.add(canonical_sandhi_skeleton(base + "ोऽ" + r_clean[1:]))
      cands.add(canonical_sandhi_skeleton(base + "ो" + r_clean))
      cands.add(canonical_sandhi_skeleton(base + r_clean))
    else:
      cands.add(canonical_sandhi_skeleton(base + "र् " + r_clean))

  # 3. Final त्/द् assimilation across newline (तत् + च -> तच्च, तत् + हि -> तद्धि)
  if l_clean.endswith(("त्", "द्")):
    tbase = l_clean[:-2]
    for rep in ("द्", "त्", "च्", "ज्", "ल्", "न्"):
      cands.add(canonical_sandhi_skeleton(tbase + rep + " " + r_clean))
    if r0 == "ह":
      cands.add(canonical_sandhi_skeleton(tbase + "द्ध" + r_clean[1:]))
    if r0 == "श":
      cands.add(canonical_sandhi_skeleton(tbase + "च्छ" + r_clean[1:]))
  return cands


def rejoin_merger_violations(raw_input: str, output_text: str) -> str:
  """Snap back inline hyphenated dīrgha/guṇa/vṛddhi splits (leaves newlines untouched)."""
  if "-" not in output_text and "–" not in output_text:
    return output_text
  pat = regex.compile(
    r"([\u0905-\u0939][\u0900-\u094c\u094e-\u0963]*)(?<!\u094d)"
    r"[-–—]+([\u0905-\u0914][\u0900-\u0963]*)"
  )
  raw_compact = regex.sub(r"\s+", "", raw_input)

  def _merge_inline(m: regex.Match) -> str:
    left, right, full = m.group(1), m.group(2), m.group(0)
    if (left + right) in raw_compact or full in raw_compact:
      return full
    last = left[-1]
    stem, matra = (left[:-1], last) if "\u093e" <= last <= "\u094c" else (left, "" if "\u0915" <= last <= "\u0939" else None)
    merged_m = None if matra is None else _VOWEL_SANDHI_MERGER.get((matra, right[0]))
    merged = None if merged_m is None else stem + merged_m + right[1:]
    return merged if (merged and merged in raw_compact) else full

  def _fix_chunk(chunk: str) -> str:
    prev = None
    while prev != chunk:
      prev = chunk
      chunk = pat.sub(_merge_inline, chunk)
    return chunk

  parts, last = [], 0
  for sm in _SUG_OR_TAG_RE.finditer(output_text):
    parts.extend((_fix_chunk(output_text[last:sm.start()]), sm.group(0)))
    last = sm.end()
  parts.append(_fix_chunk(output_text[last:]))
  return "".join(parts)


def _group_sandhi_items(out_items: list[regex.Match], output_text: str, r_skel_set: set[str]) -> list[tuple[list[int], str]]:
  """Group output tokens that derive from a single raw sandhi token (inline or cross-newline)."""
  grouped: list[tuple[list[int], str]] = []
  i = 0
  while i < len(out_items):
    grp = [i]
    cur_skel = (
      canonical_sandhi_skeleton(out_items[i].group(1))
      if out_items[i].group(1) is not None
      else canonical_sandhi_skeleton(out_items[i].group(0))
    )
    while i + 1 < len(out_items) and out_items[i].group(1) is None and out_items[i + 1].group(1) is None:
      between = output_text[out_items[i].end():out_items[i + 1].start()]
      # Allow plain spaces inline, or newline + optional blockquote '>' across clause breaks
      if regex.sub(r"[\s>]+", "", between) != "":
        break
      has_nl = "\n" in between
      left_txt = output_text[out_items[grp[0]].start():out_items[i].end()]
      right_txt = out_items[i + 1].group(0)
      matched_skel = None
      if (out_items[i].group(0).endswith(("्", "ो", "े")) or right_txt.startswith("ऽ")):
        cand = canonical_sandhi_skeleton(left_txt + " " + right_txt)
        if cand in r_skel_set:
          matched_skel = cand
      if matched_skel is None and has_nl:
        hits = forward_fuse_candidates(cur_skel, right_txt) & r_skel_set
        if hits:
          matched_skel = next(iter(hits))
      if matched_skel is not None:
        i += 1
        grp.append(i)
        cur_skel = matched_skel
      else:
        break
    grouped.append((grp, cur_skel))
    i += 1
  return grouped


def wrap_silent_mutations(raw_input: str, output_text: str, *, allow_suggestions: bool = True) -> str:
  """Detect genuine inline silent lexical mutations and wrap them in ``[[OLD|NEW]]``."""
  raw_tokens = [m.group(0) for m in regex.finditer(r"[\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff]+", raw_input)]
  out_items = [
    m for m in _DEV_WORD_CHUNK_RE.finditer(output_text)
    if not m.group(0).startswith(("[[P", "<<MULAM", "<!--")) and m.group(0) != "[[??]]"
  ]
  if not raw_tokens or not out_items:
    return output_text

  raw_skels = [canonical_sandhi_skeleton(t) for t in raw_tokens]
  grouped = _group_sandhi_items(out_items, output_text, set(raw_skels))
  grp_skels = [sk for _, sk in grouped]
  if "".join(raw_skels) == "".join(grp_skels):
    return output_text

  sm = difflib.SequenceMatcher(a=raw_skels, b=grp_skels, autojunk=False)
  replacements: list[tuple[int, int, str]] = []
  for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag != "replace" or i1 >= i2 or j1 >= j2:
      continue
    raw_span = " ".join(raw_tokens[i1:i2])
    first_m, last_m = out_items[grouped[j1][0][0]], out_items[grouped[j2 - 1][0][-1]]
    out_span = output_text[first_m.start():last_m.end()]
    # Never emit [[OLD|NEW]] across a newline or around an existing [[...]]
    if "[[" in out_span or "\n" in out_span or canonical_sandhi_skeleton(raw_span) == canonical_sandhi_skeleton(out_span):
      continue
    rep = f"[[{raw_span}|{out_span}]]" if allow_suggestions else raw_span
    replacements.append((first_m.start(), last_m.end(), rep))

  if not replacements:
    return output_text
  rebuilt, cursor = [], 0
  for s_idx, e_idx, rep in replacements:
    rebuilt.extend((output_text[cursor:s_idx], rep))
    cursor = e_idx
  rebuilt.append(output_text[cursor:])
  return "".join(rebuilt)


def enforce_post_guards(raw_input: str, model_output: str, *, allow_suggestions: bool = True) -> str:
  out = strip_llm_wrappers(model_output)
  out = rejoin_merger_violations(raw_input, out)
  return wrap_silent_mutations(raw_input, out, allow_suggestions=allow_suggestions)
