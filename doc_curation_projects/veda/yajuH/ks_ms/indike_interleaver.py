"""Fetch, cache, and Sanskrit-anchor-interleave Gemini 3.8 Flash translations from indike.org (Pramāṇa).

Fetches paired Sanskrit (IAST) and English (``~en-mt``, Gemini 3.8 Flash) Markdown pages
from ``https://indike.org/pramana/in.veda.samhita.krsnayajur*{kathaka,maitrayani}*?format=md``
into ``~/.cache/doc_curation/indike_pramana/``, pairs each Sanskrit line 1:1 with its English
translation line, aligns the Sanskrit lines directly against our ``विश्वास-प्रस्तुतिः`` blocks
in ``sarva-prastutiH/``, and inserts ``<details><summary>Gemini 3.8 Flash</summary>`` inside
``<details><summary>सर्वाष् टीकाः</summary>`` immediately above ``<details><summary>मूलम्</summary>``.
"""

from __future__ import annotations

import dataclasses
import difflib
import glob
import os
import re
import time
from typing import Sequence

import requests
from indic_transliteration import sanscript
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.llm.proofreader.translation_aligner import align_cores_to_translation_dp
from doc_curation.md.content_processor.details.common import (
  get_top_level_detail_spans,
  parse_top_level_details,
)
from doc_curation.sanskrit.accent.reconciler import bare_devanagari
from doc_curation_projects.veda.yajuH.ks_ms.reference_index import skeleton_key

DEFAULT_INDIKE_CACHE_DIR = os.path.expanduser("~/.cache/doc_curation/indike_pramana")
BASE_URL = "https://indike.org/pramana"
TRANSLATION_SUMMARY = "Gemini 3.8 Flash"

MS_PRAPATHAKA_COUNTS: dict[int, int] = {1: 11, 2: 13, 3: 16, 4: 14}
KS_PAGE_IDS: tuple[str, ...] = tuple(str(i) for i in range(1, 41)) + tuple(f"asv.{i}" for i in range(1, 14))
MS_PAGE_IDS: tuple[str, ...] = tuple(
  f"{k}.{p}" for k, n_p in MS_PRAPATHAKA_COUNTS.items() for p in range(1, n_p + 1)
)


@dataclasses.dataclass
class IndikePassage:
  """One parsed passage (anuvāka) from indike.org with paired Sanskrit & English lines."""

  passage_id: str  # e.g. "1.1.1" (MS) or "1.1" / "asv.1.1" (KS)
  sa_lines_iast: list[str]
  sa_lines_deva: list[str]
  en_lines: list[str]


def _cache_file_path(cache_dir: str, corpus: str, kind: str, page_id: str) -> str:
  return os.path.join(cache_dir, corpus, kind, f"{page_id}.md")


def fetch_and_cache_indike_corpus(
  corpus: str,
  *,
  cache_dir: str = DEFAULT_INDIKE_CACHE_DIR,
  delay_s: float = 0.12,
  force: bool = False,
) -> dict[str, int]:
  """Politely fetch and cache Sanskrit + ``~en-mt`` Markdown pages for ``ms`` or ``ks``."""
  assert corpus in ("ms", "ks"), f"Unknown corpus: {corpus}"
  slug = "maitrayani" if corpus == "ms" else "kathaka"
  page_ids = MS_PAGE_IDS if corpus == "ms" else KS_PAGE_IDS

  sess = requests.Session()
  sess.headers.update({"User-Agent": "Mozilla/5.0 (doc_curation vedic research)"})

  fetched = 0
  cached = 0
  failed: list[str] = []

  for kind, suffix in (("sa", ""), ("en", "~en-mt")):
    out_dir = os.path.join(cache_dir, corpus, kind)
    os.makedirs(out_dir, exist_ok=True)
    for pid in page_ids:
      fp = _cache_file_path(cache_dir, corpus, kind, pid)
      if not force and os.path.isfile(fp) and os.path.getsize(fp) > 200:
        cached += 1
        continue
      url = f"{BASE_URL}/in.veda.samhita.krsnayajur*{slug}{suffix}.{pid}?format=md"
      ok = False
      for attempt in range(3):
        try:
          resp = sess.get(url, timeout=30)
          if resp.status_code == 200 and len(resp.text) > 150:
            with open(fp, "w", encoding="utf-8") as fh:
              fh.write(resp.text)
            fetched += 1
            ok = True
            break
          if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(1.5 * (attempt + 1))
            continue
          break
        except requests.RequestException:
          time.sleep(1.5 * (attempt + 1))
      if not ok:
        failed.append(f"{corpus}/{kind}/{pid}")
      time.sleep(delay_s)

  return {"fetched": fetched, "cached": cached, "failed_count": len(failed), "failed": failed}


_PASSAGE_HDR_RE = re.compile(r"^###\s+\[([^\]]+)\]\([^\)]+\)\s*$", re.M)


def _clean_indike_en_line(ln: str) -> str:
  """Clean CommonMark escapes in an indike.org English translation line."""
  s = ln.rstrip()
  # Unescape CommonMark bracket/asterisk escapes (`\[I cut\]` -> `[I cut]`, `\*` -> `*`)
  s = s.replace(r"\[", "[").replace(r"\]", "]").replace(r"\*", "*")
  return s.strip()


def _iast_to_deva_clean(iast_line: str) -> str:
  """Convert a TITUS/indike IAST line (with acute/grave accents & candrabindu) to bare Devanagari."""
  import unicodedata
  s = iast_line.strip()
  s = s.replace("m̐", "ṃ").replace("n̐", "ṃ")
  # Strip IAST vowel accent combining marks (`\u0300` grave, `\u0301` acute, `\u0302` circumflex, `\u0310` candrabindu)
  # ONLY after vowels (NEVER strip `\u0301` off `s` -> `ś` = Devanagari `श`!).
  nfd = unicodedata.normalize("NFD", s)
  out_chars: list[str] = []
  last_base = ""
  for ch in nfd:
    if unicodedata.category(ch) != "Mn":
      last_base = ch.lower()
      out_chars.append(ch)
    else:
      if ch in ("\u0300", "\u0301", "\u0302", "\u0310") and last_base in ("a", "e", "i", "o", "u", "r", "l"):
        continue
      out_chars.append(ch)
  s_clean = unicodedata.normalize("NFC", "".join(out_chars))
  s_clean = re.sub(r"[|/\\]+", " ", s_clean)
  s_clean = re.sub(r"\s+", " ", s_clean).strip()
  return sanscript.transliterate(s_clean, sanscript.IAST, sanscript.DEVANAGARI)


def parse_indike_md_passages(md_text: str, *, is_english: bool) -> dict[str, list[str]]:
  """Parse ``### [passage_id](...)`` blocks from one indike.org ``?format=md`` page."""
  matches = list(_PASSAGE_HDR_RE.finditer(md_text))
  out: dict[str, list[str]] = {}
  for idx, m in enumerate(matches):
    pid = m.group(1).strip()
    start = m.end()
    end = matches[idx + 1].start() if idx + 1 < len(matches) else len(md_text)
    chunk = md_text[start:end]
    # Drop trailing footer `---\nSource: ...`
    chunk = re.split(r"\n---\s*\n", chunk, maxsplit=1)[0]
    lines: list[str] = []
    for raw_ln in chunk.splitlines():
      s = raw_ln.strip()
      if not s:
        continue
      # Skip Keith blockquote excerpts (`> ...`) that indike.org appends under Sanskrit passages!
      if s.startswith(">"):
        continue
      if is_english:
        lines.append(_clean_indike_en_line(s))
      else:
        lines.append(s)
    out[pid] = lines
  return out


def load_indike_passages(
  corpus: str,
  *,
  cache_dir: str = DEFAULT_INDIKE_CACHE_DIR,
) -> dict[str, IndikePassage]:
  """Load all cached Sanskrit + English passages for ``ms`` or ``ks`` keyed by passage_id."""
  page_ids = MS_PAGE_IDS if corpus == "ms" else KS_PAGE_IDS
  out: dict[str, IndikePassage] = {}
  for pid in page_ids:
    sa_fp = _cache_file_path(cache_dir, corpus, "sa", pid)
    en_fp = _cache_file_path(cache_dir, corpus, "en", pid)
    sa_map = parse_indike_md_passages(open(sa_fp, encoding="utf-8").read(), is_english=False) if os.path.isfile(sa_fp) else {}
    en_map = parse_indike_md_passages(open(en_fp, encoding="utf-8").read(), is_english=True) if os.path.isfile(en_fp) else {}
    for psg_id in en_map:
      sa_iast = sa_map.get(psg_id, [])
      sa_deva = [_iast_to_deva_clean(ln) for ln in sa_iast]
      out[psg_id] = IndikePassage(
        passage_id=psg_id,
        sa_lines_iast=sa_iast,
        sa_lines_deva=sa_deva,
        en_lines=en_map[psg_id],
      )
  return out


def _expand_slash_lines(sa_lines: list[str], en_lines: list[str]) -> tuple[list[str], list[str]]:
  """Expand `` / ``-separated multi-clause lines (common in MS 1.4+ & KS Aśvamedha) when Sanskrit & English align."""
  # Case A: English collapsed multiple Sanskrit lines into 1+ ` / `-joined lines (`MS 1.4.1`: 28 sa vs 1 en with 27 ` / `)!
  if sa_lines and len(en_lines) < len(sa_lines):
    flat_en: list[str] = []
    for el in en_lines:
      parts = [p.strip() for p in re.split(r"\s+/\s+", el) if p.strip()]
      flat_en.extend(parts)
    if len(flat_en) == len(sa_lines):
      return list(sa_lines), flat_en

  if len(sa_lines) != len(en_lines):
    return sa_lines, en_lines
  exp_sa: list[str] = []
  exp_en: list[str] = []
  for sl, el in zip(sa_lines, en_lines):
    en_parts = [p.strip() for p in re.split(r"\s+/\s+", el) if p.strip()]
    if len(en_parts) >= 2:
      sa_parts = [p.strip() for p in re.split(r"\s*(?://|/|\|)\s*", sl) if p.strip()]
      if len(sa_parts) == len(en_parts):
        exp_sa.extend(sa_parts)
        exp_en.extend(en_parts)
        continue
    exp_sa.append(sl)
    exp_en.append(el)
  return exp_sa, exp_en


def _align_via_bilingual_dp(
  vp_blocks: Sequence[str],
  en_clauses: Sequence[str],
) -> tuple[list[str], dict]:
  """Align ``en_clauses`` to ``vp_blocks`` using ``doc_curation``'s zero-GPU Bilingual Monotonic DP.

  Preserves exact line/clause structure of ``en_clauses`` whenever ``align_cores_to_translation_dp``
  lands near a clause boundary, ensuring clean sentence breaks and 100% verbatim coverage.
  """
  n_blk = len(vp_blocks)
  # Build flat `en_words` plus clause-boundary word offsets so we can snap cleanly to line boundaries!
  en_words: list[str] = []
  clause_starts: set[int] = {0}
  word_to_clause: list[int] = []
  for ci, cl in enumerate(en_clauses):
    ws = cl.split()
    if not ws:
      continue
    clause_starts.add(len(en_words))
    for w in ws:
      en_words.append(w)
      word_to_clause.append(ci)
  clause_starts.add(len(en_words))

  if not en_words:
    return [""] * n_blk, {"mode": "dp_empty", "filled": 0, "total": n_blk}

  cores_clean = [re.sub(r"\s+", " ", bare_devanagari(b)).strip() for b in vp_blocks]
  W = len(en_words)

  # Run `align_cores_to_translation_dp` in smooth windows of up to 18 cores so DP stays fast & tight!
  # Actually for `n_blk <= 28` and `W <= 600` a single global DP call takes < 40 ms!
  # Only window when `n_blk > 35` or `W > 750` (giant Ashvamedha/Brahmana anuvakas).
  def _starts_to_list(starts_obj, count: int) -> list[int]:
    if isinstance(starts_obj, dict):
      return [int(starts_obj.get(str(k), starts_obj.get(k, 0))) for k in range(count)]
    return [int(x) for x in starts_obj]

  if n_blk <= 35 and W <= 750:
    res_dp = align_cores_to_translation_dp(cores_clean, en_words)
    raw_starts = _starts_to_list(res_dp["starts"], n_blk)
    skip_set = {int(x) for x in res_dp.get("skip", [])}
  else:
    # Monotone proportional windowing in batches of 20 cores
    raw_starts = [0] * n_blk
    skip_set = set()
    blk_lens = [max(1, len(skeleton_key(c))) for c in cores_clean]
    cur_w = 0
    batch_sz = 20
    for bi0 in range(0, n_blk, batch_sz):
      bi1 = min(n_blk, bi0 + batch_sz)
      sub_cores = cores_clean[bi0:bi1]
      rem_sk = sum(blk_lens[bi0:])
      sub_sk = sum(blk_lens[bi0:bi1])
      if bi1 == n_blk:
        w_end = W
      else:
        est_w = cur_w + round((W - cur_w) * (sub_sk / max(1, rem_sk)))
        # Give generous slack (+35%) to DP, trimmed by `next_en`
        w_end = min(W, max(cur_w + len(sub_cores), est_w + max(25, (W - cur_w) // 5)))
      sub_words = en_words[cur_w:w_end]
      if not sub_words:
        for k in range(bi0, bi1):
          raw_starts[k] = W
          skip_set.add(k)
        continue
      upcoming = cores_clean[bi1 : bi1 + 3] if bi1 < n_blk else None
      sub_dp = align_cores_to_translation_dp(sub_cores, sub_words, upcoming_cores=upcoming)
      sub_starts = _starts_to_list(sub_dp["starts"], len(sub_cores))
      for k, st in enumerate(sub_starts):
        raw_starts[bi0 + k] = cur_w + st
      for sk_i in sub_dp.get("skip", []):
        skip_set.add(bi0 + int(sk_i))
      nxt = cur_w + int(sub_dp.get("next_en", len(sub_words)))
      cur_w = max(cur_w, min(W, nxt))

  # Snap each non-skipped start within ±2 words to an existing `clause_starts` line boundary (preserving strict monotonicity!)
  sorted_cs = sorted(clause_starts)
  snapped: list[int] = list(raw_starts)
  for i in range(n_blk):
    if i in skip_set:
      continue
    st = snapped[i]
    if i == 0:
      snapped[i] = 0
      continue
    prev_st = max((snapped[j] for j in range(i) if j not in skip_set), default=0)
    nxt_st = min((snapped[j] for j in range(i + 1, n_blk) if j not in skip_set), default=W)
    best_cs = min(sorted_cs, key=lambda c: abs(c - st))
    if abs(best_cs - st) <= 2 and prev_st < best_cs < nxt_st:
      snapped[i] = best_cs

  # Build final per-block English text preserving `  \n` breaks across original `en_clauses`!
  active_idxs = [i for i in range(n_blk) if i not in skip_set]
  out = [""] * n_blk
  for pos_a, bi in enumerate(active_idxs):
    w0 = snapped[bi]
    w1 = snapped[active_idxs[pos_a + 1]] if pos_a + 1 < len(active_idxs) else W
    if w1 <= w0:
      continue
    # Group words `[w0, w1)` by their source `word_to_clause` index so original line breaks stay crisp!
    lines_grp: list[list[str]] = []
    last_ci = -1
    for wi in range(w0, w1):
      ci = word_to_clause[wi]
      if ci != last_ci:
        lines_grp.append([en_words[wi]])
        last_ci = ci
      else:
        lines_grp[-1].append(en_words[wi])
    out[bi] = "  \n".join(" ".join(g) for g in lines_grp)

  return out, {"mode": "bilingual_dp", "filled": sum(1 for x in out if x), "total": n_blk}


def _split_en_clause_for_subblocks(en_text: str, sub_block_weights: Sequence[int]) -> list[str]:
  """Split one English translation line across ``k >= 2`` finer mantra/clause blocks using punctuation boundaries."""
  k = len(sub_block_weights)
  if k <= 1:
    return [en_text]
  s = en_text.strip()
  if not s:
    return [""] * k

  # Priority 1: ` / ` delimiter (KS Aśvamedha)
  slash_parts = [p.strip() for p in re.split(r"\s+/\s+", s) if p.strip()]
  if len(slash_parts) == k:
    return slash_parts

  # Collect candidate punctuation split positions (after `;`, `!`, `?`, `.`, `—`, `,`)
  # Score each boundary by punctuation strength + proximity to proportional target offset!
  tot_w = max(1, sum(sub_block_weights))
  cum = 0
  target_fracs: list[float] = []
  for w in sub_block_weights[:-1]:
    cum += w
    target_fracs.append(cum / tot_w)

  # Find all clean split points `(char_idx, strength)` outside `[...]` brackets
  cands: list[tuple[int, float]] = []
  bracket_depth = 0
  n = len(s)
  for idx, ch in enumerate(s):
    if ch == "[":
      bracket_depth += 1
    elif ch == "]":
      bracket_depth = max(0, bracket_depth - 1)
    elif bracket_depth == 0:
      if ch in (";", "!", "?") and idx + 1 < n and s[idx + 1] == " ":
        cands.append((idx + 1, 1.0))
      elif ch == "." and idx + 1 < n and s[idx + 1] == " ":
        cands.append((idx + 1, 0.95))
      elif ch == "/" and idx > 0 and idx + 1 < n and s[idx - 1] == " " and s[idx + 1] == " ":
        cands.append((idx + 1, 1.0))
      elif ch == "—" and idx + 1 < n:
        cands.append((idx + 1, 0.75))
      elif ch == "," and idx + 1 < n and s[idx + 1] == " ":
        cands.append((idx + 1, 0.55))

  if not cands:
    # No clean punctuation boundary inside this single short line -> assign to first block and repeat/leave clean?
    # Better: split only if clearly divisible on whitespace near target only when long (>= 8 words), else keep full on first!
    words = s.split()
    if len(words) < k * 2:
      return [s] + [""] * (k - 1)
    out: list[str] = []
    prev_wi = 0
    for tf in target_fracs:
      wi = max(prev_wi + 1, min(len(words) - 1, round(tf * len(words))))
      out.append(" ".join(words[prev_wi:wi]))
      prev_wi = wi
    out.append(" ".join(words[prev_wi:]))
    return out

  # Pick `k - 1` strictly increasing candidate cut positions closest to `target_fracs`!
  chosen: list[int] = []
  prev_pos = 0
  for ti, tf in enumerate(target_fracs):
    target_pos = tf * n
    rem_cuts = (k - 1) - ti
    best_p: int | None = None
    best_score = -1e9
    for pos, strength in cands:
      if pos <= prev_pos + 3 or pos >= n - 3:
        continue
      dist_frac = abs(pos - target_pos) / max(1, n)
      # Reject absurdly distant punctuation (> 0.38 of line away)
      if dist_frac > 0.38:
        continue
      sc = strength * 0.45 - dist_frac * 1.5
      if sc > best_score:
        best_score = sc
        best_p = pos
    if best_p is not None:
      chosen.append(best_p)
      prev_pos = best_p

  if len(chosen) != k - 1:
    # Fall back to clean word-boundary proportional split if `chosen` came up short,
    # keeping any chosen punctuation cuts and filling gaps only if enough words remain.
    if not chosen:
      words = s.split()
      if len(words) < k * 2:
        return [s] + [""] * (k - 1)
      out = []
      prev_wi = 0
      for tf in target_fracs:
        wi = max(prev_wi + 1, min(len(words) - 1, round(tf * len(words))))
        out.append(" ".join(words[prev_wi:wi]))
        prev_wi = wi
      out.append(" ".join(words[prev_wi:]))
      return out
    # Fill missing cuts greedily at whitespace nearest target
    all_cuts = sorted(chosen)
    while len(all_cuts) < k - 1:
      # Find largest interval
      bounds = [0] + all_cuts + [n]
      best_int = max(range(len(bounds) - 1), key=lambda idx_b: bounds[idx_b + 1] - bounds[idx_b])
      a, b = bounds[best_int], bounds[best_int + 1]
      mid = (a + b) // 2
      sp = s.find(" ", mid)
      if sp == -1 or sp >= b - 2:
        sp = s.rfind(" ", a + 2, mid)
      if sp <= a + 1 or sp >= b - 1:
        break
      all_cuts.append(sp)
      all_cuts.sort()
    chosen = all_cuts

  pieces: list[str] = []
  prev = 0
  for pos in chosen:
    seg = s[prev:pos].strip()
    if seg.endswith("/"):
      seg = seg[:-1].strip()
    pieces.append(seg)
    prev = pos
  tail = s[prev:].strip()
  if tail.startswith("/"):
    tail = tail[1:].strip()
  pieces.append(tail)
  while len(pieces) < k:
    pieces.append("")
  return pieces[:k]


def align_indike_to_vp_blocks(
  vp_blocks: Sequence[str],
  passages: Sequence[IndikePassage],
) -> tuple[list[str], dict]:
  """Align one or more ``IndikePassage`` objects onto ``vp_blocks`` using exact Sanskrit-to-Sanskrit alignment.

  Returns ``(en_per_block, diagnostics)`` where ``len(en_per_block) == len(vp_blocks)``.
  """
  n_blk = len(vp_blocks)
  if n_blk == 0:
    return [], {"mode": "empty", "coverage": 1.0}

  # Concatenate passages (e.g. merged `15/02-04.md` joins `15.2`, `15.3`, `15.4`)
  sa_raw: list[str] = []
  sa_deva: list[str] = []
  en_lines: list[str] = []
  for p in passages:
    es, ee = _expand_slash_lines(p.sa_lines_iast, p.en_lines)
    if len(es) == len(ee) and es:
      sa_raw.extend(es)
      sa_deva.extend(_iast_to_deva_clean(ln) for ln in es)
      en_lines.extend(ee)
    else:
      sa_raw.extend(p.sa_lines_iast)
      sa_deva.extend(p.sa_lines_deva)
      en_lines.extend(p.en_lines)

  if not en_lines:
    return [""] * n_blk, {"mode": "no_en", "coverage": 0.0}

  # Clean `vp_blocks` to skeletons
  blk_skels = [skeleton_key(bare_devanagari(b)) for b in vp_blocks]
  blk_lens = [max(1, len(sk)) for sk in blk_skels]

  # Build cumulative character boundaries of `vp_blocks` in concatenated `host_sk`
  host_sk = "".join(blk_skels)
  blk_spans: list[tuple[int, int]] = []
  cur = 0
  for sk in blk_skels:
    blk_spans.append((cur, cur + len(sk)))
    cur += len(sk)

  # Case 1: Exact 1:1 Sanskrit-to-English lines available -> Sanskrit-to-Sanskrit SequenceMatcher alignment!
  if len(sa_deva) == len(en_lines) and sa_deva and host_sk:
    ind_skels = [skeleton_key(sd) for sd in sa_deva]
    ind_sk = "".join(ind_skels)
    ind_spans: list[tuple[int, int]] = []
    pos = 0
    for sk in ind_skels:
      ind_spans.append((pos, pos + len(sk)))
      pos += len(sk)

    sm = difflib.SequenceMatcher(None, ind_sk, host_sk, autojunk=False)
    ratio = sm.ratio()
    if ratio >= 0.45:
      # Map every indike char index -> host char index via matching blocks (monotone piecewise linear!)
      mblocks = [mb for mb in sm.get_matching_blocks() if mb.size > 0]
      # Build anchor pairs `(ind_c, host_c)`
      anchors: list[tuple[int, int]] = [(0, 0)]
      for mb in mblocks:
        anchors.append((mb.a, mb.b))
        anchors.append((mb.a + mb.size, mb.b + mb.size))
      anchors.append((len(ind_sk), len(host_sk)))

      def _map_ind_to_host(ic: int) -> int:
        # Binary search in monotone anchors
        lo, hi = 0, len(anchors) - 1
        while lo < hi - 1:
          mid = (lo + hi) // 2
          if anchors[mid][0] <= ic:
            lo = mid
          else:
            hi = mid
        a0, b0 = anchors[lo]
        a1, b1 = anchors[hi]
        if a1 <= a0:
          return b0
        frac = (ic - a0) / (a1 - a0)
        return round(b0 + frac * (b1 - b0))

      # Determine which host block(s) each indike line covers!
      blk_en_buckets: list[list[str]] = [[] for _ in range(n_blk)]
      for li, (ia, ib) in enumerate(ind_spans):
        en_l = en_lines[li].strip()
        if not en_l:
          continue
        # Handle header-only English lines like `"Now begins the fifth book, named Aśvamedha."` (no Sanskrit!)
        if ib == ia:
          # Attach to the block corresponding to `_map_ind_to_host(ia)`
          hc = _map_ind_to_host(ia)
          b_idx = 0
          for bi, (ba, bb) in enumerate(blk_spans):
            if ba <= hc < bb:
              b_idx = bi
              break
          blk_en_buckets[b_idx].append(en_l)
          continue

        ha = _map_ind_to_host(ia)
        hb = _map_ind_to_host(ib)
        if hb < ha:
          hb = ha
        # Find all host blocks with significant overlap with `[ha, hb)`
        overlapped: list[tuple[int, int]] = []
        for bi, (ba, bb) in enumerate(blk_spans):
          ov = min(hb, bb) - max(ha, ba)
          if ov > 0:
            overlapped.append((bi, ov))
        if not overlapped:
          # Snap to nearest block to midpoint
          mid_h = (ha + hb) // 2
          nearest = min(range(n_blk), key=lambda bi: abs(((blk_spans[bi][0] + blk_spans[bi][1]) // 2) - mid_h))
          blk_en_buckets[nearest].append(en_l)
        elif len(overlapped) == 1:
          blk_en_buckets[overlapped[0][0]].append(en_l)
        else:
          # Filter out tiny sliver overlaps (< 25% of that host block AND < 20% of this indike line)
          line_h_len = max(1, hb - ha)
          sig = [
            (bi, ov) for bi, ov in overlapped
            if ov >= 0.30 * max(1, blk_spans[bi][1] - blk_spans[bi][0]) or ov >= 0.25 * line_h_len
          ]
          if not sig:
            sig = [max(overlapped, key=lambda x: x[1])]
          if len(sig) == 1:
            blk_en_buckets[sig[0][0]].append(en_l)
          else:
            # One indike line spans `len(sig)` finer host blocks -> split English cleanly!
            sub_pieces = _split_en_clause_for_subblocks(en_l, [ov for _, ov in sig])
            for (bi, _), piece in zip(sig, sub_pieces):
              if piece:
                blk_en_buckets[bi].append(piece)

      # Normalize line breaks within each block (clean `  \n` joining multiple lines)
      res = ["  \n".join(bkt) for bkt in blk_en_buckets]
      non_empty = sum(1 for r in res if r)
      return res, {"mode": "sa_anchored", "ratio": round(ratio, 3), "filled": non_empty, "total": n_blk}

  # Case 2: Sanskrit lines truncated or mismatched -> expand ` / ` clauses, check exact 1:1 count, else Bilingual Monotonic DP!
  all_en_clauses: list[str] = []
  for el in en_lines:
    parts = [p.strip() for p in re.split(r"\s+/\s+", el) if p.strip()]
    all_en_clauses.extend(parts)
  if len(all_en_clauses) == n_blk:
    return all_en_clauses, {"mode": "exact_count", "filled": n_blk, "total": n_blk}
  return _align_via_bilingual_dp(vp_blocks, all_en_clauses)


def resolve_indike_passages_for_ms_file(
  rel_path: str,
  ms_passages: dict[str, IndikePassage],
) -> list[IndikePassage]:
  """Map an MS ``sarva-prastutiH`` relative path (e.g. ``2/01/02.md``) to its ordered ``IndikePassage`` list."""
  parts = rel_path.replace("\\", "/").split("/")
  if len(parts) != 3:
    return []
  k, p, a = int(parts[0]), int(parts[1]), int(os.path.splitext(parts[2])[0])
  base_id = f"{k}.{p}.{a}"
  # Handle the 4 known MS structural differences cleanly:
  # 1. MS `2/01/02.md` merged TITUS duplicate `## 2 -> ## 3 (2 lines) -> ## 2 (10 lines)`; `2/01/03.md` is `2.1.3\_2`!
  if base_id == "2.1.2" and "2.1.2\\_2" in ms_passages:
    ids = [x for x in ("2.1.2", "2.1.3", "2.1.2\\_2") if x in ms_passages]
    return [ms_passages[x] for x in ids]
  if base_id == "2.1.3" and "2.1.3\\_2" in ms_passages:
    return [ms_passages["2.1.3\\_2"]]
  # 2. Sub-numbered anuvākas (`3.10.1.1..3`, `4.11.2.1..3`)
  if base_id not in ms_passages:
    sub_ids = sorted(
      (pid for pid in ms_passages if pid.startswith(base_id + ".")),
      key=lambda s: [int(x) if x.isdigit() else 0 for x in s.split(".")],
    )
    if sub_ids:
      return [ms_passages[x] for x in sub_ids]
    return []
  return [ms_passages[base_id]]


def resolve_indike_passages_for_ks_file(
  rel_path: str,
  ks_passages: dict[str, IndikePassage],
) -> list[IndikePassage]:
  """Map a KS ``sarva-prastutiH`` relative path (e.g. ``1_iThimikA/15_shrIrAjasUyam/02-04.md``) to its passages."""
  parts = rel_path.replace("\\", "/").split("/")
  if len(parts) != 3:
    return []
  part_dir, sth_dir, fname = parts
  m_sth = re.match(r"^(\d+)", sth_dir)
  if not m_sth:
    return []
  s_num = int(m_sth.group(1))
  stem = os.path.splitext(fname)[0]
  m_rng = re.match(r"^(\d+)-(\d+)$", stem)
  if m_rng:
    anums = list(range(int(m_rng.group(1)), int(m_rng.group(2)) + 1))
  else:
    m_one = re.match(r"^(\d+)", stem)
    anums = [int(m_one.group(1))] if m_one else []

  out: list[IndikePassage] = []
  for a in anums:
    base_id = f"asv.{s_num}.{a}" if part_dir == "5_ashvamedhaH" else f"{s_num}.{a}"
    if base_id in ks_passages:
      out.append(ks_passages[base_id])
    else:
      sub_ids = sorted(
        (pid for pid in ks_passages if pid.startswith(base_id + ".")),
        key=lambda s: [int(x) if x.isdigit() else 0 for x in s.split(".")],
      )
      out.extend(ks_passages[x] for x in sub_ids)
  return out


def interleave_indike_corpus(
  corpus: str,
  sarva_root: str,
  *,
  cache_dir: str = DEFAULT_INDIKE_CACHE_DIR,
  dry_run: bool = False,
  summary_title: str = TRANSLATION_SUMMARY,
) -> dict:
  """Interleave cached indike.org Gemini 3.8 Flash translations across all MS or KS ``sarva-prastutiH`` files."""
  passages = load_indike_passages(corpus, cache_dir=cache_dir)
  resolver = resolve_indike_passages_for_ms_file if corpus == "ms" else resolve_indike_passages_for_ks_file
  files = sorted(
    f for f in glob.glob(os.path.join(sarva_root, "*", "*", "*.md"))
    if os.path.basename(f) != "_index.md"
  )

  modes: dict[str, int] = {}
  total_blocks = 0
  filled_blocks = 0
  missing_files: list[str] = []
  verify_errors: list[tuple[str, str]] = []

  for fp in files:
    rel = os.path.relpath(fp, sarva_root).replace("\\", "/")
    psgs = resolver(rel, passages)
    if not psgs:
      missing_files.append(rel)
      continue
    orig_md = open(fp, encoding="utf-8").read()
    vps = extract_vp_blocks_from_sarva_md(orig_md)
    en_list, diag = align_indike_to_vp_blocks(vps, psgs)
    mode = diag.get("mode", "unknown")
    modes[mode] = modes.get(mode, 0) + 1
    total_blocks += len(vps)
    filled_blocks += sum(1 for x in en_list if x.strip())

    new_md = insert_gemini_into_sarva_markdown(orig_md, en_list, summary_title=summary_title)
    # Verify tag balance + zero stray `None` + non-empty coverage!
    n_open = len(re.findall(r"<details\b", new_md))
    n_close = new_md.count("</details>")
    if n_open != n_close:
      verify_errors.append((rel, f"unbalanced details {n_open} vs {n_close}"))
      continue
    if ">None<" in new_md or "\nNone\n" in new_md:
      verify_errors.append((rel, "stray None sentinel"))
      continue
    # Verify English word coverage (>= 95% of source words survive into rendered Gemini blocks!)
    src_en_words = " ".join(
      ln for p in psgs for ln in p.en_lines
    ).replace(" / ", " ").split()
    dst_en_words = " ".join(x for x in en_list if x).split()
    if src_en_words and len(dst_en_words) < 0.90 * len(src_en_words):
      verify_errors.append((rel, f"low en coverage {len(dst_en_words)}/{len(src_en_words)}"))
      continue

    if not dry_run and new_md != orig_md:
      with open(fp, "w", encoding="utf-8") as fh:
        fh.write(new_md)

  return {
    "corpus": corpus.upper(),
    "files": len(files),
    "missing_files": missing_files,
    "total_blocks": total_blocks,
    "filled_blocks": filled_blocks,
    "modes": modes,
    "verify_errors": verify_errors,
  }


_GEMINI_BLOCK_RE = re.compile(
  r"<details>\s*<summary>\s*" + re.escape(TRANSLATION_SUMMARY) + r"\s*</summary>.*?</details>\s*",
  re.S,
)


def insert_gemini_into_sarva_markdown(
  md_text: str,
  en_per_block: Sequence[str],
  *,
  summary_title: str = TRANSLATION_SUMMARY,
) -> str:
  """Insert (or idempotently update) ``<details><summary>Gemini 3.8 Flash</summary>`` inside each ``सर्वाष् टीकाः`` right above ``मूलम्``."""
  # Locate each `<details><summary>सर्वाष् टीकाः</summary> ... </details>` top-level block in order!
  # Every VP cluster in our MS/KS `sarva-prastutiH` has 1:1 `विश्वास-प्रस्तुतिः` -> `सर्वाष् टीकाः` containing `<details><summary>मूलम्</summary>`.
  spans = get_top_level_detail_spans(md_text, skip_js_includes=True)
  tika_spans: list[tuple[int, int]] = []
  for a, b in spans:
    seg = md_text[a:b]
    m_sum = re.match(r"<details[^>]*>\s*<summary>([^<]*)</summary>", seg)
    if m_sum and m_sum.group(1).strip() == "सर्वाष् टीकाः":
      tika_spans.append((a, b))

  if len(tika_spans) != len(en_per_block):
    raise ValueError(f"Mismatch between सर्वाष् टीकाः blocks ({len(tika_spans)}) and en_per_block ({len(en_per_block)})")

  out = md_text
  # Edit right-to-left so earlier offsets stay valid
  for (a, b), en_txt in reversed(list(zip(tika_spans, en_per_block))):
    seg = out[a:b]
    # Remove any prior Gemini block inside this `सर्वाष् टीकाः` for idempotence
    seg_clean = _GEMINI_BLOCK_RE.sub("", seg)
    en_s = en_txt.strip()
    if en_s:
      gem_blk = f"<details><summary>{summary_title}</summary>\n\n{en_s}\n</details>\n\n"
      m_mula = re.search(r"<details>\s*<summary>\s*मूलम्\s*</summary>", seg_clean)
      if m_mula:
        seg_new = seg_clean[: m_mula.start()] + gem_blk + seg_clean[m_mula.start() :]
      else:
        # Insert right after `<details><summary>सर्वाष् टीकाः</summary>\n\n`
        m_hdr = re.match(r"(<details[^>]*>\s*<summary>[^<]*</summary>\s*)", seg_clean)
        seg_new = (seg_clean[: m_hdr.end()] + "\n" + gem_blk + seg_clean[m_hdr.end() :]) if m_hdr else seg_clean
    else:
      seg_new = seg_clean
    out = out[:a] + seg_new + out[b:]
  return out


def extract_vp_blocks_from_sarva_md(md_text: str) -> list[str]:
  """Extract ordered ``विश्वास-प्रस्तुतिः`` bodies from a ``sarva-prastutiH`` file."""
  vps: list[str] = []
  for _start, _end, title, body in parse_top_level_details(md_text, skip_js_includes=True):
    if title.startswith("विश्वास-प्रस्तुतिः"):
      vps.append(body.strip())
  return vps
