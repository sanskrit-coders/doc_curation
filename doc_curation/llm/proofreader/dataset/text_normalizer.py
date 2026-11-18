"""Text cleanup, forward-sandhi un-splitting, and synthetic OCR corruption helpers."""
from __future__ import annotations

import os
import random
import tomllib
import regex

from doc_curation.llm.proofreader.guards import canonical_sandhi_skeleton

DETAILS_RE = regex.compile(
  r"<details(?:\s+open)?\s*>\s*<summary>([^<]+)</summary>(.*?)</details>",
  flags=regex.DOTALL,
)
ANNO_PLUS_RE = regex.compile(r"\+\+\+\(.*?\)\+\+\+", flags=regex.DOTALL)
SUG_SPAN_RE = regex.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
MANIPRAVALA_RE = regex.compile(r"[\u090e\u0912\u0929\u0931\u0934]")
ANY_ACCENT_RE = regex.compile(r"[\u0951-\u0954\u1cd0-\u1cff]")

_INDEP_TO_MATRA = {
  "अ": "", "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
  "ऋ": "ृ", "ॠ": "ॄ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ",
}
_A_VOWEL_MERGER = {
  "अ": "ा", "आ": "ा", "इ": "े", "ई": "े", "उ": "ो", "ऊ": "ो",
  "ऋ": "र्", "ए": "ै", "ऐ": "ै", "ओ": "ौ", "औ": "ौ",
}

_SYN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "synthetic_cases.toml")
with open(_SYN_PATH, "rb") as _f:
  SYNTHETIC_CFG = tomllib.load(_f)


def msg_record(system: str, user: str, assistant: str, task_type: str) -> dict:
  return {
    "task_type": task_type,
    "messages": [
      {"role": "system", "content": system},
      {"role": "user", "content": user},
      {"role": "assistant", "content": assistant},
    ],
  }


def clean_prastuti_target(text: str) -> str:
  """Strip ``+++(...)+++`` editorial glosses and normalize legacy ``--`` to ``–``."""
  t = ANNO_PLUS_RE.sub("", text)
  t = regex.sub(
    r"([\u0915-\u0939])([\u093e-\u094c])?[-–—]+\s*\+([\u0905-\u0914])",
    lambda m: (
      m.group(1) + _A_VOWEL_MERGER[m.group(3)]
      if (m.group(2) or "") in ("", "ा") and m.group(3) in _A_VOWEL_MERGER
      else m.group(1) + (m.group(2) or "") + m.group(3)
    ),
    t,
  )
  t = regex.sub(r"(?<=\S)[-–—]+\s+[-–—]+(?=\S)", "–", t)
  t = regex.sub(r"(?<=\S)--(?=\S)", "–", t)
  lines = []
  for line in t.splitlines():
    soft = line.endswith("  ")
    cleaned = regex.sub(r"[ \t]{2,}", " ", line.strip())
    lines.append((cleaned + ("  " if soft else "")) if cleaned else "")
  return regex.sub(r"\n{3,}", "\n\n", "\n".join(lines).strip())


def _fuse_across_newline_seam(left_word: str, right_word: str) -> str | None:
  """Deterministically apply external sandhi (dīrgha/guṇa/vṛddhi/yaṇ/visarga)
  across a clause newline when reconstructing raw pre-split source text."""
  if not left_word or not right_word:
    return None
  r0 = right_word[0]
  last = left_word[-1]

  # 1. Visarga sandhi before sibilants / dentals / palatals / cerebrals / अ
  if last == "ः":
    base = left_word[:-1]
    if r0 in ("त", "थ", "स"):
      return base + "स्" + right_word
    if r0 in ("च", "छ", "श"):
      return base + "श्" + right_word
    if r0 in ("ट", "ठ", "ष"):
      return base + "ष्" + right_word
    if base and ("\u0915" <= base[-1] <= "\u0939") and r0 == "अ":
      return base + "ोऽ" + right_word[1:]
    if base and not ("\u0915" <= base[-1] <= "\u0939") and r0 in "अआइईउऊएऐओऔगघजझदधबभमयरलव":
      if r0 in _INDEP_TO_MATRA:
        return base + "र" + _INDEP_TO_MATRA[r0] + right_word[1:]
      return base + "र्" + right_word

  # 2. Vowel sandhi (dīrgha / guṇa / vṛddhi / yaṇ) when right begins with independent vowel
  if r0 in _INDEP_TO_MATRA:
    if last in ("", "ा") or ("\u0915" <= last <= "\u0939"):
      stem = left_word[:-1] if last == "ा" else left_word
      if ("\u0915" <= last <= "\u0939") or last == "ा":
        rep = _A_VOWEL_MERGER.get(r0)
        if rep:
          return stem + rep + right_word[1:]
    if last in ("ि", "ी") and r0 in ("इ", "ई"):
      return left_word[:-1] + "ी" + right_word[1:]
    if last in ("ु", "ू") and r0 in ("उ", "ऊ"):
      return left_word[:-1] + "ू" + right_word[1:]
    if last in ("ि", "ी") and r0 not in ("इ", "ई"):
      return left_word[:-1] + "्य" + _INDEP_TO_MATRA[r0] + right_word[1:]
    if last in ("ु", "ू") and r0 not in ("उ", "ऊ"):
      return left_word[:-1] + "्व" + _INDEP_TO_MATRA[r0] + right_word[1:]
  return None


def collapse_prose_soft_breaks(text: str, *, fuse_newline_sandhi_prob: float = 0.0, rng: random.Random | None = None) -> str:
  def _join_lines(p: str) -> str:
    if p.lstrip().startswith(">") and fuse_newline_sandhi_prob <= 0.0:
      return p.strip()
    lines = [regex.sub(r"^>\s*", "", l).strip() for l in p.splitlines() if l.strip()]
    if len(lines) <= 1:
      return p.strip()
    acc = lines[0]
    for nxt in lines[1:]:
      if rng is not None and rng.random() < fuse_newline_sandhi_prob and not acc.endswith(("।", "॥", ",", ";", "-", "–")):
        l_parts = acc.rsplit(" ", 1)
        r_parts = nxt.split(" ", 1)
        fused = _fuse_across_newline_seam(l_parts[-1], r_parts[0])
        if fused:
          prefix = (l_parts[0] + " ") if len(l_parts) > 1 else ""
          suffix = (" " + r_parts[1]) if len(r_parts) > 1 else ""
          acc = prefix + fused + suffix
          continue
      acc = acc + " " + nxt
    return acc.strip()

  paras = regex.split(r"\n\s*\n", text)
  return "\n\n".join(_join_lines(p) for p in paras if p.strip())


def is_verse_block(text: str) -> bool:
  lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
  return 2 <= len(lines) <= 6 and "॥" in lines[-1] and any(l.endswith("।") for l in lines[:-1])


def has_meaningful_prose_clause_breaks(text: str) -> bool:
  if is_verse_block(text):
    return False
  lines = [l.strip() for l in text.strip().splitlines() if l.strip() and not l.strip().startswith(">")]
  return len(lines) >= 2 and any(not l.endswith(("।", "॥", ":", "-")) for l in lines[:-1])


def skeleton_old_side(text: str) -> str:
  old_only = SUG_SPAN_RE.sub(lambda m: m.group(1), text)
  old_only = regex.sub(r"\[\[(?:P\d+[a-zA-Z]?|\?\?)\]\]", "", old_only)
  return canonical_sandhi_skeleton(old_only)


def unsplit_sanskrit_to_raw(
  curated_text: str,
  rng: random.Random,
  *,
  revert_suggestions_to_old: bool = True,
  collapse_clause_newlines: bool = True,
  hard_wrap_prob: float = 0.25,
) -> str:
  """Reconstruct realistic raw un-hyphenated / OCR text from a curated passage."""
  t = SUG_SPAN_RE.sub(lambda m: m.group(1), curated_text) if revert_suggestions_to_old else curated_text
  if collapse_clause_newlines:
    t = collapse_prose_soft_breaks(t, fuse_newline_sandhi_prob=0.75, rng=rng)

  prev = None
  while prev != t:
    prev = t
    t = regex.sub(
      r"([\u0915-\u0939])\u094d(?:[-–—]+|[ \t]+)(?=[\u0905-\u0914])([\u0905-\u0914])",
      lambda m: m.group(1) + _INDEP_TO_MATRA.get(m.group(2), m.group(2)),
      t,
    )
  t = regex.sub(r"([ेो])\s+ऽ", r"\1ऽ", t)
  t = regex.sub(r"([सशषरदजचटडलबग]\u094d)[ \t]+(?=[\u0915-\u0939])", r"\1", t)
  t = regex.sub(
    r"(?<=[\u0900-\u097fA-Za-z\u0100-\u017f\u1e00-\u1eff])[-–](?=[\u0900-\u097fA-Za-z\u0100-\u017f\u1e00-\u1eff])",
    "",
    t,
  )
  if rng.random() < 0.35:
    t = regex.sub(r"म्(?=\s+[\u0915-\u0939])", "ं", t)

  if rng.random() < hard_wrap_prob and "\n\n" not in t and len(t) > 110:
    limit = rng.randint(58, 78)
    lines, cur, cur_len = [], [], 0
    for w in t.split(" "):
      if cur and cur_len + 1 + len(w) > limit:
        lines.append(" ".join(cur))
        cur, cur_len = [w], len(w)
      else:
        cur.append(w)
        cur_len += len(w) + 1
    if cur:
      lines.append(" ".join(cur))
    t = "\n".join(lines)
  return t.strip()


def _corrupt_single_word(unsplit_core: str, rng: random.Random) -> str | None:
  m_repha = regex.search(r"र्([\u0915-\u0939])([\u093e-\u094c])", unsplit_core)
  if m_repha and rng.random() < 0.30:
    s, e = m_repha.span()
    return unsplit_core[:s] + m_repha.group(1) + "र्" + m_repha.group(2) + unsplit_core[e:]
  rules = list(SYNTHETIC_CFG["devanagari_ocr_confusions"])
  rng.shuffle(rules)
  for src_sub, dst_sub in rules:
    pos = unsplit_core.find(src_sub, 0 if len(src_sub) >= 2 else 1)
    if pos != -1:
      cand = unsplit_core[:pos] + dst_sub + unsplit_core[pos + len(src_sub):]
      if cand != unsplit_core and canonical_sandhi_skeleton(cand) != canonical_sandhi_skeleton(unsplit_core):
        return cand
  return None


def inject_realistic_ocr_typo(curated_para: str, rng: random.Random, *, max_typos: int = 2) -> tuple[str, str] | None:
  """Inject 1–2 authentic Devanāgarī OCR corruptions into a curated paragraph
  (preserving multi-line ``  \\n`` clause breaks in ``target_out`` while un-splitting
  and collapsing ``raw_in``)."""
  if "[[" in curated_para or "<" in curated_para:
    return None
  # Tokenize preserving exact whitespace separators (including "  \n")
  pieces = regex.split(r"(\s+)", curated_para)
  cand_indices = [
    i for i in range(0, len(pieces), 2)
    if len(pieces[i]) >= 6 and not pieces[i].startswith(">")
    and regex.fullmatch(r"[\u0900-\u0963\u0971-\u097f\-–]+[।॥,;]*", pieces[i])
  ]
  if not cand_indices:
    return None
  rng.shuffle(cand_indices)
  n_want = min(len(cand_indices), 2 if (len(cand_indices) >= 5 and rng.random() < 0.45) else 1, max_typos)

  pieces_sug = list(pieces)
  pieces_raw = list(pieces)
  sentinels: list[tuple[str, str]] = []
  for idx in sorted(cand_indices[:n_want]):
    m_punc = regex.match(r"^(.*?)([।॥,;]*)$", pieces[idx])
    core_hyp, trail_punc = m_punc.group(1), m_punc.group(2)
    unsplit_core = unsplit_sanskrit_to_raw(core_hyp, rng, hard_wrap_prob=0.0)
    if len(unsplit_core) < 5:
      continue
    corrupted = _corrupt_single_word(unsplit_core, rng)
    if not corrupted:
      continue
    tag = f"§§TYPO{len(sentinels)}§§"
    sentinels.append((tag, corrupted))
    pieces_sug[idx] = f"[[{corrupted}|{core_hyp}]]{trail_punc}"
    pieces_raw[idx] = f"{tag}{trail_punc}"

  if not sentinels:
    return None
  raw_in = unsplit_sanskrit_to_raw("".join(pieces_raw), rng, collapse_clause_newlines=True)
  for tag, corrupted in sentinels:
    raw_in = raw_in.replace(tag, corrupted)
  return raw_in, "".join(pieces_sug)
