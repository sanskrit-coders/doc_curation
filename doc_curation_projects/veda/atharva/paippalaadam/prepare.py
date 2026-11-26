"""Pre-dedup consolidation, GRETIL VP cleanup, and single-caller inlining for Atharvaveda Paippalāda (`AV-P`)."""
from __future__ import annotations

import os
import pathlib
import re
from collections.abc import Sequence

from doc_curation.md.content_processor import include as include_helper
from indic_transliteration import sanscript

from doc_curation_projects.veda.dedup import mulam_merger, static_fixer
from doc_curation_projects.veda.dedup.block_parser import format_vp_summary_with_kind
from doc_curation_projects.veda.dedup.matcher import classify_unit_kind
from doc_curation_projects.veda.yajuH.vaajasaneyi.dedup.tika_merger import (
  format_details_block,
)

DEFAULT_HUGO_BASE = pathlib.Path("/home/vvasuki/gitland/vishvAsa")
DEFAULT_XML_PATH = pathlib.Path(
  "/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/ambuda-gretil/1_sanskr/tei/sa_paippalAdasaMhitA.xml"
)
DEFAULT_WIKI_DIR = pathlib.Path(
  "/home/vvasuki/gitland/sanskrit/raw_etexts/vedaH/atharva/paippalAda/saMhitA/wiki"
)

_SEE_SPEC_RE = re.compile(
  r"\+\+\+\([^)]*?\bsee\s+(?:stanza\s+)?(?:(\d+)[.,](\d+)[.,])?(\d+)([a-z]+)?(?:\s*[;,)][^)]*)?\)\+\+\+",
  re.IGNORECASE,
)
_XML_SEE_RE = re.compile(r"\bsee\s+(?:stanza\s+)?(?:(\d+)[.,](\d+)[.,])?(\d+)([a-z]+)?", re.IGNORECASE)
_TRIPLE_PLUS_RE = re.compile(r"\+\+\+.*?\+\+\+", re.DOTALL)
_MANAS_DETAILS_RE = re.compile(
  r"<details><summary>मानसतरङ्गिणीकृत्</summary>(.*?)</details>", re.DOTALL
)
_DETAILS_WRAP_RE = re.compile(
  r"<details(?:\s+open)?><summary>([^<]*)</summary>(.*?)</details>", re.DOTALL
)
_FRONTMATTER_RE = re.compile(r"\A((?:\+\+\+.*?\+\+\+|---.*?---)\s*)(.*)\Z", re.DOTALL)
_UNCLOSED_BRACKET_RE = re.compile(r"\s*\[(?:भत्त्|सेए)[^\n]*")
_PRAPATHAKA_TRAIL_RE = re.compile(r"\s*॥\s*प्र[\u1cd3\u1cd9]?पाठक\s*॥\s*$")
_EDITORIAL_PAREN_RE = re.compile(r"\((?:⟨\s*)?([अ-ौक-ह\u0900-\u097f\u1cd0-\u1cff][^()…·]*?)\)")
_SUKTA_INDEX_INC_RE = re.compile(
  r'<div\s+class="js_include"[^>]*\burl="/vedAH/atharva/paippalAdam/saMhitA/sarvASh_TIkAH/[^"]*/_index\.md"[^>]*>.*?</div>\s*',
  re.DOTALL,
)


# Simple phonetic normalizer for prefix overlap matching during refrain expansion.
def _stem_norm(w: str) -> str:
  w = re.sub(r"[।॥,.;?!*+()\[\]\-\u1cd0-\u1cff\u0951-\u0957]", "", w)
  w = re.sub(r"[ंँ](?=$|[क-ह])", "म्", w)
  w = w.replace("ट्वा", "त्वा")
  if w.endswith(("ो", "ः", "स्", "र्")) and len(w) >= 2 or w.endswith(("ा", "ै", "े")) and len(w) >= 3:
    w = w[:-1]
  return w


def split_frontmatter(text: str) -> tuple[str, str]:
  """Return ``(frontmatter_with_trailing_ws, body)`` preserving frontmatter verbatim."""
  m = _FRONTMATTER_RE.match(text)
  if not m:
    return "", text
  return m.group(1), m.group(2)


def _join_slp_vowel_sandhi(w1_deva: str, w2_deva: str) -> str:
  """Contract vowel sandhi across a GRETIL ``w1- \\n -w2`` line-break hyphen."""
  # Fix GRETIL `-र्तस्य` (missing underdot ṛ in `duhānā- / -rtasya`) -> `ऋतस्य`.
  if w2_deva == "र्तस्य" or w2_deva.startswith("र्त"):
    w2_deva = "ऋ" + w2_deva[1:]
  s1 = sanscript.transliterate(w1_deva, sanscript.DEVANAGARI, sanscript.SLP1)
  s2 = sanscript.transliterate(w2_deva, sanscript.DEVANAGARI, sanscript.SLP1)
  if not s1 or not s2:
    return f"{w1_deva} {w2_deva}"
  v1, v2 = s1[-1], s2[0]
  stem = s1[:-1]
  rest = s2[1:]
  mid = None
  if v1 in "aA" and v2 in "aA":
    mid = "A"
  elif v1 in "iI" and v2 in "iI":
    mid = "I"
  elif v1 in "uU" and v2 in "uU":
    mid = "U"
  elif v1 in "fF" and v2 in "fF":
    mid = "F"
  elif v1 in "aA":
    if v2 in "iI":
      mid = "e"
    elif v2 in "uU":
      mid = "o"
    elif v2 in "fF":
      mid = "ar"
    elif v2 in "eE":
      mid = "E"
    elif v2 in "oO":
      mid = "O"
  elif v1 in "iI":
    mid = "y" + v2
  elif v1 in "uU":
    mid = "v" + v2
  elif v1 in "fF":
    mid = "r" + v2
  if mid is None:
    if w1_deva.endswith("्") and v2 in "aAiIuUfFeEoO":
      return sanscript.transliterate(s1 + s2, sanscript.SLP1, sanscript.DEVANAGARI)
    return f"{w1_deva} {w2_deva}"
  return sanscript.transliterate(stem + mid + rest, sanscript.SLP1, sanscript.DEVANAGARI)


def contract_gretil_line_hyphens(body: str) -> str:
  """Join GRETIL across-line ekādeśa breaks ``X-  \\n-Y`` cleanly into Saṁhitā forms."""
  lines = body.replace("\r\n", "\n").splitlines()
  out: list[str] = []
  i = 0
  while i < len(lines):
    cur = lines[i]
    while i + 1 < len(lines) and cur.rstrip().endswith("-") and lines[i + 1].lstrip().startswith("-"):
      l_part = cur.rstrip()[:-1]
      r_part = lines[i + 1].lstrip()[1:]
      # Separate trailing words from whitespace/punctuation cleanly.
      m_l = re.match(r"^(.*?)(\S+)$", l_part, re.DOTALL)
      m_r = re.match(r"^(\S+)(.*)$", r_part, re.DOTALL)
      if m_l and m_r:
        joined_w = _join_slp_vowel_sandhi(m_l.group(2), m_r.group(1))
        cur = m_l.group(1) + joined_w + m_r.group(2)
        i += 1
      else:
        break
    out.append(cur)
    i += 1
  return "\n".join(out)


def load_xml_pada_map(xml_path: pathlib.Path = DEFAULT_XML_PATH) -> tuple[
  dict[tuple[int, int, int], list[tuple[str, str, str]]],
  dict[tuple[int, int, int, str], tuple[str, str]],
]:
  """Load ``(k, s, v) -> [(p_letter, deva_text, note_text)]`` from GRETIL Paippalāda XML."""
  if not xml_path.is_file():
    return {}, {}
  xml_txt = xml_path.read_text(encoding="utf-8")
  by_stanza: dict[tuple[int, int, int], list[tuple[str, str, str]]] = {}
  by_id: dict[tuple[int, int, int, str], tuple[str, str]] = {}
  for m in re.finditer(r'<lg\s+xml:id="(PS_(\d+)\.(\d+)\.(\d+))"[^>]*>(.*?)</lg>', xml_txt, re.DOTALL):
    lg_id, ks, ss, vs, inner_lg = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
    padas: list[tuple[str, str, str]] = []
    for lm in re.finditer(r'<l\s+xml:id="(PS_[^"]+)"[^>]*>(.*?)</l>', inner_lg, re.DOTALL):
      lid, inner = lm.group(1), lm.group(2)
      p_let = lid[len(lg_id):]
      m_n = re.search(r"<note>(.*?)</note>", inner, re.DOTALL)
      note = m_n.group(1).strip() if m_n else ""
      clean_iast = re.sub(r"<note>.*?</note>|<[^>]+>", "", inner, flags=re.DOTALL).strip()
      clean_iast = re.sub(r"\[.*", "", clean_iast).strip()
      deva = sanscript.transliterate(clean_iast, sanscript.IAST, sanscript.DEVANAGARI)
      deva = deva.replace("तिष्ट्ःअतु", "तिष्ठतु")
      padas.append((p_let, deva, note))
      by_id[(ks, ss, vs, p_let)] = (deva, note)
    by_stanza[(ks, ss, vs)] = padas
  return by_stanza, by_id


def _load_wiki_stanzas(wiki_dir: pathlib.Path = DEFAULT_WIKI_DIR) -> dict[tuple[int, int, int], str]:
  """Load stanza-numbered Devanagari verses from GRETIL companion ``wiki/`` if available."""
  out: dict[tuple[int, int, int], str] = {}
  if not wiki_dir.is_dir():
    return out
  for fp in sorted(wiki_dir.rglob("*.md")):
    rel_parts = fp.relative_to(wiki_dir).parts
    if len(rel_parts) != 2 or not rel_parts[0].isdigit():
      continue
    m_s = re.match(r"^(\d+)", fp.stem)
    if not m_s:
      continue
    k, s = int(rel_parts[0]), int(m_s.group(1))
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    _, body = split_frontmatter(txt)
    body = body.strip()
    # Split verses delimited by `॥ <num> ॥`
    parts = re.split(r"॥\s*([०-९0-9]+)\s*॥", body)
    for idx in range(0, len(parts) - 1, 2):
      v_raw = parts[idx].strip()
      num_raw = parts[idx + 1].translate(str.maketrans("०१२३४५६७८९", "0123456789"))
      if num_raw.isdigit() and v_raw:
        out[(k, s, int(num_raw))] = v_raw + " ॥"
  return out


def _clean_single_line_for_expansion(ln: str) -> str:
  s = _TRIPLE_PLUS_RE.sub("", ln)
  s = _UNCLOSED_BRACKET_RE.sub("", s)
  s = s.replace("तिष्ट्ःअतु", "तिष्ठतु")
  return re.sub(r"[ \t]+", " ", s).strip()


def _merge_prefix_with_target_lines(prefix: str, suffix: str, target_lines: Sequence[str]) -> str | None:
  """Merge ``prefix`` (before ``(…)``) with target refrain lines avoiding overlap duplication."""
  if not target_lines:
    return None
  clean_targets = [_clean_single_line_for_expansion(t) for t in target_lines]
  clean_targets = [t for t in clean_targets if t]
  if not clean_targets:
    return None
  t0 = clean_targets[0]
  t0_clean_end = re.sub(r"[।॥\s]+$", "", t0)
  pre_s = prefix.strip()
  suff_s = suffix.strip()

  if not pre_s:
    joined = "  \n".join(clean_targets)
    if suff_s in ("॥", "।") and not joined.rstrip().endswith(("॥", "।")):
      joined = joined.rstrip() + " " + suff_s
    elif suff_s and suff_s not in ("॥", "।"):
      suff_clean = re.sub(r"[।॥\s]+$", "", suff_s).strip()
      joined_no_p = re.sub(r"[।॥\s]+$", "", joined).strip()
      if suff_clean and joined_no_p.endswith(suff_clean):
        joined = joined_no_p + (" " + suff_s[-1] if suff_s.endswith(("॥", "।")) else "")
      else:
        j_ws = joined_no_p.split()
        s_ws = suff_s.split()
        ov = 0
        def _yan_stem(w: str) -> str:
          st = _stem_norm(w)
          if st.endswith("्य्") and len(st) >= 4:
            st = st[:-3] + "ि"
          elif st.endswith("्व्") and len(st) >= 4:
            st = st[:-3] + "ु"
          return st
        for k_len in range(min(len(j_ws), len(s_ws)), 0, -1):
          if [_yan_stem(w) for w in j_ws[-k_len:]] == [_yan_stem(w) for w in s_ws[:k_len]]:
            ov = k_len
            break
        joined = " ".join(j_ws[:len(j_ws) - ov] + s_ws)
    return joined

  # Strip trailing punctuation from prefix before aligning with t0.
  # If prefix ends with hyphen (`राज्ञा-`), match compound stem prefix inside t0 (`राज्ञाध्यक्षेण`).
  hyph_pre = pre_s.endswith("-")
  pre_clean_for_match = pre_s[:-1] if hyph_pre else pre_s
  pre_words = pre_clean_for_match.rstrip("।॥ ").split()
  t0_words = t0_clean_end.split()
  if not t0_words:
    return None

  if hyph_pre and pre_words:
    stem_last = pre_words[-1]
    for j, tw in enumerate(t0_words):
      if len(stem_last) >= 3 and tw.startswith(stem_last[:-1]):
        first_line = " ".join(pre_words[:-1] + t0_words[j:])
        if t0.rstrip().endswith("।") and len(clean_targets) > 1:
          first_line += " ।"
        elif t0.rstrip().endswith("॥") and len(clean_targets) == 1:
          first_line += " ॥"
        all_lines = [first_line, *clean_targets[1:]]
        out = "  \n".join(all_lines)
        if suff_s in ("॥", "।"):
          out = re.sub(r"[।॥\s]+$", "", out) + " " + suff_s
        return out

  # Check overlap from the right of `pre_words` matching inside `t0_words`:
  # Case 1: Suffix of pre_words matches a contiguous slice inside t0_words.
  overlap_t_end: int | None = None
  for k_len in range(min(len(pre_words), len(t0_words)), 0, -1):
    sub_pre = [_stem_norm(w) for w in pre_words[-k_len:]]
    for j in range(len(t0_words) - k_len + 1):
      sub_t = [_stem_norm(w) for w in t0_words[j : j + k_len]]
      if sub_pre == sub_t:
        overlap_t_end = j + k_len
        break
    if overlap_t_end is not None:
      break

  # Case 1b: Partial sandhi-boundary stem overlap on last pre word (`दिवोद्` vs `पृथिव्योद्`, `मा` vs `मावत्व्`, `-यामुम्` vs `ऽमुम्`, `इमाम्` vs `प्रेमाम्`).
  if overlap_t_end is None and pre_words:
    pw_last = _stem_norm(pre_words[-1])
    if len(pw_last) >= 2:
      for j, tw in enumerate(t0_words):
        tw_n = _stem_norm(tw)
        if tw_n.startswith(pw_last):
          first_line = " ".join(pre_words[:-1] + t0_words[j:])
          if t0.rstrip().endswith("।") and len(clean_targets) > 1:
            first_line += " ।"
          elif t0.rstrip().endswith("॥") and len(clean_targets) == 1:
            first_line += " ॥"
          all_lines = [first_line, *clean_targets[1:]]
          out = "  \n".join(all_lines)
          if suff_s in ("॥", "।"):
            out = re.sub(r"[।॥\s]+$", "", out) + " " + suff_s
          return out
        if (
          (len(tw_n) >= len(pw_last) and tw_n.endswith(pw_last))
          or (pw_last.endswith("ामुम्") and tw_n == "अमुम्")
          or (pw_last == "इमाम्" and tw_n == "प्रेमाम्")
        ):
          overlap_t_end = j + 1
          break
        if len(pw_last) >= 2 and (
          (pw_last.endswith("ोद्") and tw_n.endswith("ोद्"))
          or (pw_last == "उद्" and tw_n.endswith("ोद्"))
        ):
          overlap_t_end = j + 1
          break

  if overlap_t_end is not None:
    tail_t0 = " ".join(t0_words[overlap_t_end:])
    # Reattach trailing । if t0 had one and tail_t0 is last word before punct or lines follow.
    if not tail_t0 and len(clean_targets) == 1:
      punct = " ॥" if t0.endswith("॥") else (" । " if t0.endswith("।") else "")
      first_line = pre_s + (punct.strip() if suff_s in ("", "॥", "।") else "")
      if suff_s == "॥" and not first_line.endswith("॥"):
        first_line = re.sub(r"[।॥\s]+$", "", first_line) + " ॥"
      elif suff_s == "।" and not first_line.endswith(("।", "॥")):
        first_line = first_line + " ।"
      return first_line
    rest_lines = list(clean_targets[1:])
    if tail_t0:
      if t0.rstrip().endswith("।") and rest_lines:
        tail_t0 += " ।"
      elif t0.rstrip().endswith("॥") and not rest_lines:
        tail_t0 += " ॥"
      first_line = f"{pre_s} {tail_t0}".strip()
    else:
      first_line = pre_s.rstrip()
      if t0.rstrip().endswith("।") and rest_lines and not first_line.endswith(("।", "॥")):
        first_line += " ।"
    all_lines = [first_line, *rest_lines]
  else:
    # No stem match (e.g. `तस्मै` replacing `तस्मा` at position 0? or `इन्द्रो रक्षोहा` when pre had 1-word swap)
    # Wait: if prefix is a single word (`तस्मै`) or ends after `देवता ।`, substitute vs append?
    if pre_s.endswith(("।", "॥")):
      all_lines = [pre_s, *clean_targets] if clean_targets else [pre_s]
    elif len(pre_words) == 1 and len(clean_targets[0].split()) >= 2:
      # e.g. `तस्मै (…) ॥ (see 1def)` where 1d starts `तस्मा उ त्वं ...`: replace word 0!
      replaced_first = " ".join([pre_s] + t0_words[1:])
      if t0.rstrip().endswith("।") and len(clean_targets) > 1:
        replaced_first += " ।"
      elif t0.rstrip().endswith("॥") and len(clean_targets) == 1:
        replaced_first += " ॥"
      all_lines = [replaced_first, *clean_targets[1:]]
    else:
      # Fallback: append t0 after word0 replacement only when ambiguous -> append rest after `t0_words[1:]`? No, safer to avoid guessing if mismatch!
      return None

  out = "  \n".join(all_lines)
  if suff_s in ("॥", "।") or suff_s:
    out = re.sub(r"[।॥\s]+$", "", out) + " " + suff_s
  return out


def expand_paippalada_ellipses(
  raw_stanzas: dict[tuple[int, int, int], str],
  xml_by_stanza: dict[tuple[int, int, int], list[tuple[str, str, str]]],
  xml_by_id: dict[tuple[int, int, int, str], tuple[str, str]],
  wiki_stanzas: dict[tuple[int, int, int], str] | None = None,
) -> tuple[dict[tuple[int, int, int], str], dict[str, int], list[tuple[int, int, int, str]]]:
  """Expand GRETIL ``(…)`` refrains across all Paippalāda stanzas without mutating source dictionaries."""
  expanded: dict[tuple[int, int, int], str] = dict(raw_stanzas)
  stats = {"xml_see": 0, "same_sukta": 0, "wiki": 0, "unresolved": 0}
  unresolved_list: list[tuple[int, int, int, str]] = []

  def _resolve_xml_pada(rk: int, rs: int, rv: int, rp: str, depth: int = 0) -> list[str] | None:
    if depth > 5:
      return None
    out_lines: list[str] = []
    for ch in rp:
      item = xml_by_id.get((rk, rs, rv, ch))
      if item is None:
        return None
      deva, note = item
      deva_c = _clean_single_line_for_expansion(deva)
      if "(…)" not in deva_c and "…" not in deva_c:
        out_lines.append(deva_c)
        continue
      m_s = _XML_SEE_RE.search(note)
      if not m_s:
        return None
      nk = int(m_s.group(1)) if m_s.group(1) else rk
      ns = int(m_s.group(2)) if m_s.group(2) else rs
      nv = int(m_s.group(3))
      np = m_s.group(4) or ""
      if not np:
        p_rows = xml_by_stanza.get((nk, ns, nv), [])
        sub = [_clean_single_line_for_expansion(d) for _, d, _ in p_rows]
      else:
        sub = _resolve_xml_pada(nk, ns, nv, np, depth + 1)
      if not sub:
        return None
      pre, _, suff = deva_c.partition("(…)")
      merged = _merge_prefix_with_target_lines(pre, suff, sub)
      if not merged:
        return None
      out_lines.extend(merged.splitlines())
    return out_lines

  # Multi-pass so intra-sūkta chaining (`v2 -> v1`, etc.) resolves cleanly.
  for _pass in range(3):
    changed_pass = False
    for key in sorted(expanded.keys()):
      k, s, v = key
      body = expanded[key]
      if "(…)" not in re.sub(_TRIPLE_PLUS_RE, "", body):
        continue
      lines = body.splitlines()
      new_lines: list[str] = []
      changed_stanza = False
      for li, ln in enumerate(lines):
        ln_code = re.sub(_TRIPLE_PLUS_RE, "", ln)
        m_ell = re.search(r"\(+[^)]*…\)", ln_code)
        if not m_ell:
          new_lines.append(ln)
          continue
        ell_tok = m_ell.group(0)
        # Normalizing `((…)` or `(नु …)` -> `(…)` or `नु (…)` cleanly.
        ln_clean = _clean_single_line_for_expansion(ln)
        if ell_tok != "(…)":
          partial = ell_tok.lstrip("(").rstrip(")").replace("…", "").strip()
          ln_clean = ln_clean.replace(ell_tok, f"{partial} (…)" if partial else "(…)", 1)
        # 1. Explicit `+++(see X.Y.Zab)+++`
        m_see = _SEE_SPEC_RE.search(ln)
        if m_see:
          rk = int(m_see.group(1)) if m_see.group(1) else k
          rs = int(m_see.group(2)) if m_see.group(2) else s
          rv = int(m_see.group(3))
          rp = m_see.group(4) or ""
          target_lines: list[str] | None = None
          if rp:
            target_lines = _resolve_xml_pada(rk, rs, rv, rp)
          if target_lines is None and (rk, rs, rv) in expanded:
            src_lines = [_clean_single_line_for_expansion(x) for x in expanded[(rk, rs, rv)].splitlines() if _clean_single_line_for_expansion(x)]
            if src_lines and not any("…" in x for x in src_lines):
              if rp:
                idxs = [ord(c) - ord("a") for c in rp]
                if all(0 <= ix < len(src_lines) for ix in idxs):
                  target_lines = [src_lines[ix] for ix in idxs]
              elif len(src_lines) > li:
                target_lines = src_lines[li:]
              elif src_lines:
                target_lines = src_lines
          if target_lines:
            pre, _, suff = ln_clean.partition("(…)")
            rep = _merge_prefix_with_target_lines(pre, suff, target_lines)
            if rep:
              new_lines.append(rep)
              stats["xml_see"] += 1
              changed_stanza = True
              continue

        # 2. Implicit same-sūkta refrain match (walk backwards `v-1 .. 1`)
        resolved_local = False
        pre, _, suff = ln_clean.partition("(…)")
        if "(…)" not in suff:
          for ref_v in range(v - 1, 0, -1):
            if (k, s, ref_v) not in expanded:
              continue
            cand_lines = [_clean_single_line_for_expansion(x) for x in expanded[(k, s, ref_v)].splitlines() if _clean_single_line_for_expansion(x)]
            if not cand_lines or any("(…)" in x for x in cand_lines):
              continue
            if not pre.strip():
              if len(cand_lines) > li:
                rep = _merge_prefix_with_target_lines("", suff, cand_lines[li:])
                if rep:
                  new_lines.append(rep)
                  stats["same_sukta"] += 1
                  changed_stanza = True
                  resolved_local = True
                  break
            else:
              pre_ws = pre.strip().rstrip("।॥ ").split()
              for ti, t_ln in enumerate(cand_lines):
                rep = _merge_prefix_with_target_lines(pre, suff, cand_lines[ti:])
                if rep:
                  t_stems = {_stem_norm(w) for w in t_ln.split()}
                  if (
                    pre.strip().endswith(("।", "॥"))
                    and "देवता" in pre
                    and "देवता" in t_ln
                  ) or (pre_ws and _stem_norm(pre_ws[-1]) in t_stems):
                    new_lines.append(rep)
                    stats["same_sukta"] += 1
                    changed_stanza = True
                    resolved_local = True
                    break
              if resolved_local:
                break
        if resolved_local:
          continue

        # 3. Companion `wiki/` alignment for residual lines (normalized `ं -> म्`, `ट्वा -> त्वा`)
        if wiki_stanzas and (k, s, v) in wiki_stanzas:
          w_body = wiki_stanzas[(k, s, v)]
          if "(…)" not in w_body and "…" not in w_body:
            def _norm_wiki_str(s_val: str) -> tuple[str, list[int]]:
              chars_out: list[str] = []
              idx_out: list[int] = []
              for idx_c, ch in enumerate(s_val):
                if ch in " \t\n।॥,.;?!-ऽ\u1cd0-\u1cff\u0951-\u0957":
                  continue
                c_norm = "म्" if ch in ("ं", "ँ") else ch
                for sub_c in c_norm:
                  chars_out.append(sub_c)
                  idx_out.append(idx_c)
              return "".join(chars_out), idx_out

            prefix_ctx = _clean_single_line_for_expansion(" ".join(new_lines) + " " + pre.rstrip("-")).strip()
            ctx_no_sp, _ = _norm_wiki_str(prefix_ctx)
            w_s, w_chars = _norm_wiki_str(w_body)
            if "(…)" in ln_clean and pre.strip() and "(…)" not in suff and ctx_no_sp and len(ctx_no_sp) >= 4:
              anchor_sub = ctx_no_sp[-min(len(ctx_no_sp), 14):]
              hit_pos = w_s.find(anchor_sub)
              if hit_pos == -1 and len(anchor_sub) > 5:
                anchor_sub = anchor_sub[:-1]
                hit_pos = w_s.find(anchor_sub)
              if hit_pos == -1 and len(ctx_no_sp) >= 8:
                anchor_sub = ctx_no_sp[-8:]
                hit_pos = w_s.find(anchor_sub)
              match_end = (hit_pos + len(anchor_sub)) if hit_pos != -1 else -1
              if hit_pos != -1 and match_end < len(w_chars):
                char_idx = w_chars[match_end]
                tail_w = w_body[char_idx:].strip()
                if tail_w:
                  if char_idx > 0 and w_body[char_idx - 1] not in " \t\n" and pre.strip():
                    m_prev_sp = w_body.rfind(" ", 0, char_idx)
                    full_tail = w_body[m_prev_sp + 1 :].strip()
                    pre_ws_split = pre.rstrip("- ").rsplit(None, 1)
                    pre_head = pre_ws_split[0] if len(pre_ws_split) == 2 else ""
                    rep = f"{pre_head} {full_tail}".strip()
                  else:
                    rep = f"{pre.rstrip('- ')} {tail_w}".strip()
                  if suff.strip() in ("॥", "।") and not rep.rstrip().endswith(("॥", "।")):
                    rep = rep.rstrip() + " " + suff.strip()
                  new_lines.append(rep)
                  stats["wiki"] += 1
                  changed_stanza = True
                  continue
            if not pre.strip() and "(…)" in suff and len(w_body) >= 12:
              mid_txt = re.sub(r"[।॥]+", "", suff.replace("(…)", "")).strip()
              mid_no_sp, _ = _norm_wiki_str(mid_txt)
              mid_fused = mid_no_sp.replace("्", "")
              w_fused = w_s.replace("्", "")
              if mid_no_sp and len(mid_no_sp) >= 6 and (
                mid_no_sp in w_s
                or mid_no_sp[: min(len(mid_no_sp), 10)] in w_s
                or mid_fused[: min(len(mid_fused), 10)] in w_fused
              ):
                new_lines.append(w_body.strip())
                stats["wiki"] += 1
                changed_stanza = True
                continue

        # 4. Repeating final refrain pāda/clause across sibling stanzas (only when not an explicit `see` ref!)
        if not m_see and pre.strip() and "(…)" not in suff and v >= 2:
          ref_candidates: dict[str, int] = {}
          for ref_v in range(1, v):
            c_body = expanded.get((k, s, ref_v), "")
            if not c_body or "(…)" in _clean_single_line_for_expansion(c_body):
              continue
            c_lns = [_clean_single_line_for_expansion(x) for x in c_body.splitlines() if _clean_single_line_for_expansion(x)]
            if len(c_lns) >= 2:
              # Check both exact last line AND normalized tail after first `।` if single-verse multiline differs
              last_ln = c_lns[-1]
              ref_candidates[last_ln] = ref_candidates.get(last_ln, 0) + 1
          rep_tail = None
          if len(ref_candidates) == 1:
            rep_tail = next(iter(ref_candidates.keys()))
          else:
            common = [ln_c for ln_c, cnt in ref_candidates.items() if cnt >= 2]
            if len(common) == 1:
              rep_tail = common[0]
            else:
              # Fallback: check repeated last clause across all siblings (`… तासां श्वन्वतीनाम् ...` or `वातापे पीव इद् भव ॥`)
              clauses: dict[str, int] = {}
              for ref_v in range(1, v):
                c_body = _clean_single_line_for_expansion(expanded.get((k, s, ref_v), ""))
                if not c_body or "(…)" in c_body:
                  continue
                c_parts = [p.strip() for p in re.split(r"।", c_body) if p.strip()]
                if len(c_parts) >= 2:
                  tail_c = c_parts[-1]
                  if len(tail_c.split()) >= 3:
                    clauses[tail_c] = clauses.get(tail_c, 0) + 1
              common_cl = [c for c, cnt in clauses.items() if cnt >= 2]
              if len(common_cl) == 1:
                rep_tail = common_cl[0]
              elif (k, s, v - 1) in expanded:
                # Single previous stanza sharing clear suffix refrain after 1+ clauses (`06/016`, `16/043`)
                prev_b = _clean_single_line_for_expansion(expanded[(k, s, v - 1)])
                if prev_b and "(…)" not in prev_b:
                  p_parts = [p.strip() for p in re.split(r"।", prev_b) if p.strip()]
                  if len(p_parts) >= 2 and 3 <= len(p_parts[-1].split()) <= 8:
                    rep_tail = p_parts[-1]
          if rep_tail:
            new_lines.append(f"{pre.strip()}  \n{rep_tail}")
            stats["same_sukta"] += 1
            changed_stanza = True
            continue
        new_lines.append(ln)

      if changed_stanza:
        expanded[key] = "\n".join(new_lines)
        changed_pass = True
    if not changed_pass:
      break

  for key, body in sorted(expanded.items()):
    clean_b = re.sub(_TRIPLE_PLUS_RE, "", body)
    if "(…)" in clean_b or "…" in clean_b:
      stats["unresolved"] += 1
      unresolved_list.append((*key, body))
  return expanded, stats, unresolved_list


def clean_gretil_vp_text(vp_text: str, *, expand_body: str | None = None) -> str:
  """Normalize non-manual Paippalāda VP text (preserve manual edits externally by caller check)."""
  s = expand_body if expand_body is not None else vp_text
  s = _TRIPLE_PLUS_RE.sub("", s)
  s = _UNCLOSED_BRACKET_RE.sub("", s)
  s = s.replace("तिष्ट्ःअतु", "तिष्ठतु")
  s = _PRAPATHAKA_TRAIL_RE.sub(" ॥", s)
  # Strip GRETIL editorial signs outside `+++...+++` (`+ऽ`, `*ऽ`, `?word?`) and editorial Devanagari parens.
  s = re.sub(r"[+*](?=ऽ)", "", s)
  s = re.sub(r"[?*+]", "", s)
  s = _EDITORIAL_PAREN_RE.sub(lambda m: m.group(1).strip(), s)
  # Clean double spacing before line endings & rejoin cross-line vowel sandhi.
  lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.replace("\r\n", "\n").splitlines()]
  lines = [ln for ln in lines if ln]
  joined = contract_gretil_line_hyphens("\n".join(lines))
  # Preserve trailing double-space markdown linebreaks.
  out_lines = [ln.strip() for ln in joined.splitlines() if ln.strip()]
  return "  \n".join(out_lines) + "\n"


def _normalize_content_vp_residual_gretil(vp_body: str, *, is_manual: bool, mula_ctx: str = "") -> str:
  """Clean residual GRETIL editorial artifacts in an already-inlined ``AV-P`` VP block."""
  s = _PRAPATHAKA_TRAIL_RE.sub(" ॥", vp_body)
  if is_manual:
    return s
  # Strip GRETIL editorial parens `(च्)`, `(त्)`, `(या᳓)`, `(⟨ मल्वं᳓)` while keeping `(…)` and `(· ·)`
  s = _EDITORIAL_PAREN_RE.sub(lambda m: m.group(1).strip(), s)
  # Contract broken GRETIL `C्- +++(word)+++ \n -V` leftovers (`स्थ् आग्नयश्`, `म् आश्विना`, `च् आन्तस्`, `च् ओभाभ्याम्`)
  for pat, rep in (
    (r"परिचि([\u1cd3\u1cd9]*)त\s+स्थ्\s+आ([\u1cd3\u1cd9]*)ग्नय", r"परिचि\1त स्था\2ग्नय"),
    (r"वर्धय\s+म्\s+आश्विना", r"वर्धय माश्विना"),
    (r"पृथिवीं([\u1cd3\u1cd9]*)\s+च्\s+आ([\u1cd3\u1cd9]*)न्तस्", r"पृथिवीं\1 चा\2न्तस्"),
    (r"शर्वा([\u1cd3\u1cd9]*)य\s+च्\s+ओभा([\u1cd3\u1cd9]*)भ्याम्", r"शर्वा\1य चोभा\2भ्याम्"),
  ):
    s = re.sub(pat, rep, s)
  # Also contract any still-uncontracted `C्- ... -V` if directly copied into VP/GR
  if "-\n-" in s or "-\r\n-" in s or re.search(r"्-\s*(?:\+\+\+[^+]+\+\+\+)?\s*\n\s*-", s):
    s = clean_gretil_vp_text(s).strip()
  return s


def cleanup_avp_content_residual_ellipses_and_gretil(
  sarva_dir: pathlib.Path = DEFAULT_HUGO_BASE / "vedAH" / "content" / "atharva" / "paippalAdam" / "saMhitA" / "sarva-prastutiH",
  *,
  xml_path: pathlib.Path = DEFAULT_XML_PATH,
  wiki_dir: pathlib.Path = DEFAULT_WIKI_DIR,
  dry_run: bool = True,
) -> dict[str, object]:
  """Clean residual ``॥ प्रपाठक ॥``, editorial parens, GRETIL ``C् V`` breaks, and ``(…)`` refrains in ``sarva-prastutiH/``."""
  xml_by_stanza, xml_by_id = load_xml_pada_map(xml_path)
  wiki_stanzas = _load_wiki_stanzas(wiki_dir)

  md_files = sorted(
    fp for fp in sarva_dir.rglob("*.md")
    if fp.is_file() and re.match(r"^\d\d/\d\d\d\.md$", str(fp.relative_to(sarva_dir)))
  )

  # Build raw stanza lookup across sarva-prastutiH (`मूलम् - पैप्पलादम् (GR)` or `VP` bare, including `js_include` prefills)
  # AND enrich xml_by_stanza with normalized devanagari where XML had missing `see` details.
  stanza_bare: dict[tuple[int, int, int], str] = {}
  file_texts: dict[pathlib.Path, str] = {}
  for fp in md_files:
    rel = str(fp.relative_to(sarva_dir))
    k, s = int(rel[:2]), int(rel[3:6])
    txt = fp.read_text(encoding="utf-8")
    file_texts[fp] = txt
    for m in re.finditer(r"## ([^\n]+)\n(.*?)(?=\n## |\Z)", txt, re.DOTALL):
      v_raw = m.group(1).split()[0].translate(str.maketrans("०१२३४५६७८९", "0123456789"))
      if not v_raw.isdigit():
        continue
      v = int(v_raw)
      blk = m.group(2)
      mu_m = re.search(r"<details[^>]*><summary>मूलम् - पैप्पलादम् \(GR\)</summary>(.*?)</details>", blk, re.DOTALL)
      vp_m = re.search(r"<details[^>]*><summary>विश्वास-प्रस्तुतिः[^<]*</summary>(.*?)</details>", blk, re.DOTALL)
      src = mu_m.group(1).strip() if mu_m else (vp_m.group(1).strip() if vp_m else "")
      if src:
        stanza_bare[(k, s, v)] = re.sub(r"[\u1cd0-\u1cff\u0951\u0952]", "", src)

  expanded_all, _, _ = expand_paippalada_ellipses(stanza_bare, xml_by_stanza, xml_by_id, wiki_stanzas=wiki_stanzas)

  # Re-apply any clean `wiki/` completion specifically for remaining `06/012`, `06/013`, `19/055`, etc. using `v-1` siblings
  # and wiki fallback cleanly for each unresolved stanza
  stats = {"files_changed": 0, "vp_ell_expanded": 0, "gr_ell_expanded": 0, "gretil_fixed": 0, "vp_unaccented_reset": []}
  vp_diffs: list[tuple[str, str, str]] = []
  gr_diffs: list[tuple[str, str, str]] = []

  def _resolve_block_text(k: int, s: int, v: int, raw_block: str) -> str | None:
    bare_blk = re.sub(r"[\u1cd0-\u1cff\u0951\u0952]", "", raw_block).strip()
    # 1. Exact pattern-preserving expansions for residual partial/double `(…)` refrains
    # so existing clean AV-P prefixes/variants are NEVER overwritten by noisy `wiki/` text.
    if (k, s) in ((6, 12), (6, 13)):
      m_dir = re.search(r"अस्मान्\s+([^\s]+)\s+दिशः", bare_blk)
      if m_dir:
        return (
          f"यो ऽस्मान् {m_dir.group(1)} दिशो ऽघायुर् अभिदासात् ।  \n"
          "एतत् स ऋच्छाद् अश्मवर्म नो ऽस्तु ॥"
        )
    if (k, s) == (6, 16) and "परिंशम् आरिशामहे" in bare_blk:
      return re.sub(
        r"\s*\(…\)\s*॥\s*$",
        " ।  \nवातापे पीव इद् भव ॥",
        clean_gretil_vp_text(bare_blk).strip(),
      )
    if (k, s) == (7, 13) and bare_blk.rstrip().endswith("(…) ॥"):
      return re.sub(
        r"\s*\(…\)\s*॥\s*$",
        "  \nतासां श्वन्वतीनाम्  \nइन्द्रो अपि कृतच् छिरः ॥",
        clean_gretil_vp_text(bare_blk).strip(),
      )
    if (k, s, v) == (16, 43, 1) and "(…) ॥" in bare_blk:
      return re.sub(
        r"\(…\)\s*॥",
        "भूयो भूयः श्वः श्वस् तेन त्वं द्विषतो जहि ॥",
        clean_gretil_vp_text(bare_blk).strip(),
      )
    if (k, s, v) == (16, 47, 1) and "प्रयच्छच् च" in bare_blk:
      return (
        "पृश्निश् चासि पृषती चासि  \n"
        "तस्यास् ते यच्छच् च प्रयच्छच् चैति मुखे ।  \n"
        "ताभ्यां ते विधेयं ताभ्यां ते नमस् ताभ्यां नो मृड ताभ्यां नो ऽधि ब्रूहि ताभ्यां नो ऽभि जिघ्र ।  \n"
        "मातेव पुत्रं पितेव सूनुम् अयं ते अस्मि तन्वं मुमुग्धि ग्राह्या बन्धेभ्यो विमदं न एनम् ॥"
      )
    if (k, s) == (16, 95) and v in (1, 2):
      first_w = "वीरुद्भ्यस्" if v == 1 else "ओषधीभ्यस्"
      return (
        f"{first_w} त्वा निर्वपामि शतधारम् अपक्षुधम् ।  \n"
        "स पक्तारं वह सुकृतां यत्र लोको यत्र ऋषयः प्रथमजाः पुराणाः ॥"
      )
    if (k, s) == (16, 129) and 2 <= v <= 8:
      mid = re.sub(r"^\(…\)\s*|\s*\(…\)\s*॥\s*$", "", clean_gretil_vp_text(bare_blk).strip()).strip()
      if mid.startswith("अपाम् "):
        mid_body = mid[len("अपाम् "):]
        lead = "यो व आपो ऽपाम्"
      elif mid.startswith("अपां "):
        mid_body = mid[len("अपां "):]
        lead = "यो व आपो ऽपां"
      else:
        mid_body = mid
        lead = "यो व आपो"
      tail_part = (
        "देवयजनः ।  \n"
        "इदं तम् अति सृजामि तं माभ्य् अव निक्षि ।  \n"
        "तेन तम् अभ्य् अति सृजामि यो ऽस्मान् द्वेष्टि यं वयं द्विष्मः ।  \n"
        "तं वधेयं तं स्तृषीयानेन ब्रह्मणानेन कर्मणानया मेन्या ॥"
      )
      if "यजुष्य" in mid_body:
        mid_body = mid_body.replace("यजुष्यः", "यजुष्यो")
        return f"{lead} {mid_body} {tail_part}"
      if mid_body.endswith("बिन्दुः"):
        mid_body = re.sub(r"बिन्दुः$", "बिन्दुर् अप्स्व्", mid_body)
      else:
        mid_body = re.sub(r"ः$", "ो ऽप्स्व्", mid_body)
      return f"{lead} {mid_body} अन्तर् यजुष्यो {tail_part}"
    if (k, s) == (16, 131) and 4 <= v <= 10:
      raw_no_notes = _TRIPLE_PLUS_RE.sub("", raw_block).strip()
      raw_no_notes = re.sub(r"हा-\s*\n\s*-आ", "हा", raw_no_notes)
      raw_no_notes = re.sub(r"हा-\s*\n\s*-अ", "हा", raw_no_notes)
      raw_no_notes = re.sub(r"हा-\s*\n\s*-ओ", "हौ", raw_no_notes)
      c_blk = clean_gretil_vp_text(raw_no_notes).strip()
      c_blk = re.sub(r"^\(…\)\s*सपत्नहा(?=\s|$)", "विष्णोः क्रमो ऽसि सपत्नहा  \n", c_blk)
      c_blk = re.sub(r"^\(…\)\s*सपत्नह", "विष्णोः क्रमो ऽसि सपत्नह", c_blk)
      c_blk = re.sub(r"\s*\n+\s*", "  \n", c_blk)
      m_line = re.search(r"^(.*?)\s*\(…\)\s*॥\s*$", c_blk, re.DOTALL)
      if m_line:
        pre_l = re.sub(r"तम्$", "तं", m_line.group(1).strip())
        return (
          f"{pre_l} निर् भजामो  \n"
          "यो ऽस्मान् द्वेष्टि यं वयं द्विष्मः ।  \n"
          "पूर्वजान् सपत्नान् अवैनान् बाधे अत्य् एनान् क्रमाम्य्  \n"
          "अपाङ् अपनुत्तः सपत्नः ॥"
        )
    if (k, s) == (17, 21) and v in (6, 8):
      return re.sub(
        r"\s*\(…\)\s*॥\s*$",
        " आमुष्यायणम् अमुष्याः पुत्रम् आ वृश्चामि ॥",
        clean_gretil_vp_text(bare_blk).strip(),
      )
    if (k, s) == (18, 30) and 2 <= v <= 5:
      res_b = re.sub(r"\(नु[\u1cd3\u1cd9]*\s*…\)", "नु तिष्ठतो य एवं वेद", raw_block.strip())
      return _normalize_content_vp_residual_gretil(res_b, is_manual=False)
    if (k, s) == (18, 32) and 5 <= v <= 9:
      res_b = raw_block.strip()
      for pat, rep in (
        (r"\(धा([\u1cd3\u1cd9]*)म\s*…\)", r"धा\1म भवति य एवं वेद"),
        (r"\(प्रियं([\u1cd3\u1cd9]*)\s*…\)", r"प्रियं\1 धाम भवति य एवं वेद"),
        (r"\(एवं([\u1cd3\u1cd9]*)\s*…\)", r"एवं\1 वेद"),
        (r"\(?वृश्च([\u1cd3\u1cd9]*)ते\s*…\)", r"वृश्च\1ते य एवं विद्वांसं व्रात्यम् उपवदति"),
        (r"\(?य([\u1cd3\u1cd9]*)\s*…\)", r"य\1 एवं विद्वांसं व्रात्यम् उपवदति"),
        (r"\(\s*…\s*\)", "प्रियं धाम भवति य एवं वेद ।  \nताभ्यश् चा वृश्चते य एवं विद्वांसं व्रात्यम् उपवदति"),
      ):
        res_b = re.sub(pat, rep, res_b)
      if "…" not in res_b:
        return _normalize_content_vp_residual_gretil(res_b, is_manual=False)
    if (k, s, v) == (19, 55, 17):
      v16 = stanza_bare.get((19, 55, 16), "")
      if "साहस्री पुष्टिः" in v16:
        return (
          "बृहस्पतेर् आकूतिर् असि साहस्री पुष्टिः ।  \n"
          "बृहस्पतेर् आकूत्याहं साहस्र्या पुष्ट्या  \n"
          "साहस्रान् पशून् पुषेयम् ॥"
        )

    cand = expanded_all.get((k, s, v), "")
    if cand and "…" not in _TRIPLE_PLUS_RE.sub("", cand):
      return clean_gretil_vp_text(cand).strip()
    if (k, s, v) in xml_by_stanza:
      xml_rows = xml_by_stanza[(k, s, v)]
      has_note = any(nt for _, _, nt in xml_rows)
      if has_note:
        ann_lines = [f"{d} +++({nt})+++" if nt else d for _, d, nt in xml_rows]
        sub_map = dict(stanza_bare)
        sub_map[(k, s, v)] = "\n".join(ann_lines)
        sub_exp, _, _ = expand_paippalada_ellipses(sub_map, xml_by_stanza, xml_by_id, wiki_stanzas=wiki_stanzas)
        c2 = sub_exp.get((k, s, v), "")
        if c2 and "…" not in _TRIPLE_PLUS_RE.sub("", c2):
          return clean_gretil_vp_text(c2).strip()
    w = wiki_stanzas.get((k, s, v), "")
    if w and "…" not in w:
      w_clean = re.sub(r"\s*॥\s*॥\s*$", " ॥", w.strip())
      w_clean = re.sub(r"\s*:\s*॥", " ॥", w_clean)
      return "  \n".join(ln.strip() for ln in w_clean.splitlines() if ln.strip())
    return None

  for fp, orig in file_texts.items():
    rel = str(fp.relative_to(sarva_dir))
    k, s = int(rel[:2]), int(rel[3:6])
    parts = re.split(r"(^## [^\n]+\n)", orig, flags=re.MULTILINE)
    if len(parts) < 3:
      continue
    out_parts = [parts[0]]
    changed_file = False
    for idx in range(1, len(parts), 2):
      hdr = parts[idx]
      blk = parts[idx + 1]
      v_raw = hdr[3:].split()[0].translate(str.maketrans("०१२३४५६७८९", "0123456789"))
      v = int(v_raw) if v_raw.isdigit() else 0

      def _tx_details(m_d: re.Match[str]) -> str:
        nonlocal changed_file
        full_open = m_d.group(0)
        d_hdr = m_d.group(1)
        d_body = m_d.group(2)
        if not (d_hdr.startswith("विश्वास-प्रस्तुतिः") or d_hdr in ("मूलम् (GR)", "मूलम् - पैप्पलादम् (GR)")):
          return full_open
        is_vp = d_hdr.startswith("विश्वास-प्रस्तुतिः")
        is_manual = is_vp and "(यन्त्र-स्वरः)" not in d_hdr
        new_body = _normalize_content_vp_residual_gretil(d_body.strip(), is_manual=is_manual)
        if "…" in _TRIPLE_PLUS_RE.sub("", new_body) and (not is_vp or not is_manual) and v > 0:
          resolved = _resolve_block_text(k, s, v, new_body)
          if resolved and "…" not in resolved:
            new_body = resolved
            if is_vp:
              stats["vp_ell_expanded"] = int(stats["vp_ell_expanded"]) + 1
              vp_diffs.append((rel, d_body.strip().replace("\n", " / "), new_body.replace("\n", " / ")))
              stats["vp_unaccented_reset"].append((rel, v))
            else:
              stats["gr_ell_expanded"] = int(stats["gr_ell_expanded"]) + 1
              gr_diffs.append((rel, d_body.strip().replace("\n", " / "), new_body.replace("\n", " / ")))
        if new_body != d_body.strip():
          if "प्रपाठक" in d_body or "(" in d_body or "स्थ्" in d_body or "च् " in d_body or "म् " in d_body:
            stats["gretil_fixed"] = int(stats["gretil_fixed"]) + 1
          changed_file = True
          open_tag = m_d.group(0).split("</summary>", 1)[0] + "</summary>"
          return f"{open_tag}\n\n{new_body}\n</details>"
        return full_open

      # Skip blocks inside `<div class="js_include"`
      segs = re.split(r'(<div\s+class="js_include"[^>]*>.*?</div>(?:\s*</div>)*)', blk, flags=re.DOTALL)
      new_segs = []
      for seg in segs:
        if seg.startswith('<div'):
          new_segs.append(seg)
        else:
          new_segs.append(re.sub(r"<details(?:\s+open)?><summary>([^<]*)</summary>((?:(?!</?details\b).)*)</details>", _tx_details, seg, flags=re.DOTALL))
      out_parts.append(hdr + "".join(new_segs))

    new_txt = "".join(out_parts)
    if new_txt != orig:
      stats["files_changed"] = int(stats["files_changed"]) + 1
      if not dry_run:
        fp.write_text(new_txt, encoding="utf-8")

  stats["vp_diffs"] = vp_diffs
  stats["gr_diffs"] = gr_diffs
  return stats


def _collect_all_vishvasa_scan_roots(
  hugo_base_dir: pathlib.Path = DEFAULT_HUGO_BASE,
  *,
  include_all_repos: bool = False,
) -> list[pathlib.Path]:
  """Collect exact subdirectories citing ``paippalAdam`` plus the Paippalāda trees."""
  import shutil
  import subprocess

  if include_all_repos:
    return static_fixer._collect_vishvasa_scan_roots(hugo_base_dir, [])
  base_roots: list[str] = []
  for rname in ("vedAH", "vedAH_Rk", "vedAH_yajuH", "vedAH_sAma", "devaH"):
    for sub in ("content", "static"):
      cand = hugo_base_dir / rname / sub
      if cand.is_dir():
        base_roots.append(str(cand.resolve()))
  roots: set[pathlib.Path] = {
    (hugo_base_dir / "vedAH" / "content" / "atharva" / "paippalAdam").resolve(),
    (hugo_base_dir / "vedAH" / "static" / "atharva" / "paippalAdam").resolve(),
  }
  rg_bin = shutil.which("rg")
  if rg_bin and base_roots:
    proc = subprocess.run(
      [rg_bin, "-l", "/paippalAdam/", "-g", "*.md", *base_roots],
      capture_output=True, text=True, check=False,
    )
    if proc.returncode in (0, 1):
      for line in proc.stdout.splitlines():
        if line.strip():
          p = pathlib.Path(line).resolve().parent
          # Keep top-level Paippalāda root concise; collect exact external dirs outside Paippalāda.
          if not any(root == p or root in p.parents for root in roots):
            roots.add(p)
  else:
    return sorted(pathlib.Path(r) for r in base_roots)
  return sorted(r for r in roots if r.is_dir())


def _is_manual_vp(vp_body: str, mula_core: str) -> bool:
  """Return True if a VP file has manual edits (accents, bolding, glosses, or curated differences)."""
  if re.search(r"[\u1cd0-\u1cff\u0951\u0952]", vp_body) or "**" in vp_body:
    return True
  return vp_body.strip() != mula_core.strip()


def prepare_paippalada_corpus(
  *,
  hugo_base_dir: pathlib.Path = DEFAULT_HUGO_BASE,
  xml_path: pathlib.Path = DEFAULT_XML_PATH,
  wiki_dir: pathlib.Path = DEFAULT_WIKI_DIR,
  scan_roots: Sequence[pathlib.Path] | None = None,
  dry_run: bool = False,
) -> dict:
  """Consolidate 3-part Paippalāda `mUlam/`, clean GRETIL VP, and inline single-caller files.

  External multi-caller static files (referenced outside `sarva-prastutiH/`) are migrated
  to `static/atharva/paippalAdam/saMhitA/{Rk,yajuH}/` cleanly with all caller URLs updated.
  """
  saMhitA_static = hugo_base_dir / "vedAH" / "static" / "atharva" / "paippalAdam" / "saMhitA"
  content_dir = hugo_base_dir / "vedAH" / "content" / "atharva" / "paippalAdam" / "saMhitA" / "sarva-prastutiH"
  mula_dir = saMhitA_static / "mUlam"
  vp_dir = saMhitA_static / "vishvAsa-prastutiH"
  sarva_dir = saMhitA_static / "sarvASh_TIkAH"

  scan_roots = list(scan_roots) if scan_roots is not None else _collect_all_vishvasa_scan_roots(hugo_base_dir)
  stats: dict = {
    "manas_mula_renamed": 0,
    "mulam_consolidation": {},
    "empty_index_includes_removed": 0,
    "vp_cleaned": 0,
    "manual_vp_preserved": 0,
    "ellipsis_stats": {},
    "inlined_mantras": 0,
    "moved_multi_caller": 0,
  }

  # Snapshot manual vs untouched VP BEFORE deleting mUlam/, plus build stanza dict for ellipsis expansion.
  raw_stanzas: dict[tuple[int, int, int], str] = {}
  rel_to_coords: dict[str, tuple[int, int, int]] = {}
  manual_rels: set[str] = set()
  for vp_fp in sorted(vp_dir.rglob("*.md")):
    if vp_fp.name in ("_index.md", "file_list.md"):
      continue
    rel = vp_fp.relative_to(vp_dir).as_posix()
    k_s, s_s, fn = rel.split("/")
    v_num = int(re.match(r"^(\d+)", fn).group(1))
    coords = (int(k_s), int(s_s), v_num)
    rel_to_coords[rel] = coords
    _, vp_body = split_frontmatter(vp_fp.read_text(encoding="utf-8"))
    mu_fp = mula_dir / rel
    if mu_fp.is_file():
      _, mu_raw = split_frontmatter(mu_fp.read_text(encoding="utf-8"))
      # Fix colliding `मानसतरङ्गिणीकृत्` block name inside `mUlam/` before consolidation.
      if "<summary>मानसतरङ्गिणीकृत्</summary>" in mu_raw:
        new_mu = (mu_fp.read_text(encoding="utf-8")).replace(
          "<summary>मानसतरङ्गिणीकृत्</summary>",
          "<summary>मूलम् - मानसतरङ्गिणीकृत्</summary>",
        )
        stats["manas_mula_renamed"] += 1
        if not dry_run:
          mu_fp.write_text(new_mu, encoding="utf-8")
      mu_core = _MANAS_DETAILS_RE.sub("", mu_raw)
      mu_core = re.sub(r"</?details[^>]*>|<summary>.*?</summary>", "", mu_core, flags=re.DOTALL).strip()
      raw_stanzas[coords] = mu_core
      if _is_manual_vp(vp_body, mu_core):
        manual_rels.add(rel)
    else:
      raw_stanzas[coords] = vp_body.strip()

  stats["manual_vp_preserved"] = len(manual_rels)

  # 1. Consolidate mUlam/ -> sarvASh_TIkAH/ across all callers (vedAH, vedAH_yajuH, devaH...).
  if mula_dir.is_dir():
    avp_mula_spec = mulam_merger.CorpusMulamSpec(
      name="AV-P",
      shAkha_label="पैप्पलादम्",
      mula_dir=mula_dir,
      sarva_dir=sarva_dir,
      mula_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/mUlam/",
      vp_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/vishvAsa-prastutiH/",
      sarva_url_prefix="/vedAH/atharva/paippalAdam/saMhitA/sarvASh_TIkAH/",
      pada_summary="पद-पाठः (यान्त्रिकः)",
    )
    stats["mulam_consolidation"] = mulam_merger.consolidate_corpus_mula(
      avp_mula_spec,
      caller_roots=scan_roots,
      hugo_base_dir=str(hugo_base_dir),
      dry_run=dry_run,
      delete_mula_dir=not dry_run,
    )

  # 2. Expand ellipses and clean GRETIL markup in non-manual vishvAsa-prastutiH/ files.
  xml_by_stanza, xml_by_id = load_xml_pada_map(xml_path)
  wiki_stanzas = _load_wiki_stanzas(wiki_dir)
  expanded_map, ell_stats, unresolved = expand_paippalada_ellipses(
    raw_stanzas, xml_by_stanza, xml_by_id, wiki_stanzas=wiki_stanzas
  )
  stats["ellipsis_stats"] = ell_stats
  stats["ellipsis_unresolved_samples"] = [(k, s, v) for k, s, v, _ in unresolved[:20]]

  for rel, coords in sorted(rel_to_coords.items()):
    if rel in manual_rels:
      continue
    vp_fp = vp_dir / rel
    if not vp_fp.is_file():
      continue
    old_txt = vp_fp.read_text(encoding="utf-8")
    fm, old_body = split_frontmatter(old_txt)
    cleaned_body = clean_gretil_vp_text(old_body, expand_body=expanded_map.get(coords, old_body))
    if cleaned_body != old_body:
      stats["vp_cleaned"] += 1
      if not dry_run:
        vp_fp.write_text(fm + cleaned_body, encoding="utf-8")

  # 3. Remove empty sūkta `_index.md` includes from sarva-prastutiH/.
  for c_fp in sorted(content_dir.rglob("*.md")):
    if c_fp.name in ("_index.md", "file_list.md"):
      continue
    c_txt = c_fp.read_text(encoding="utf-8")
    new_c, n_sub = _SUKTA_INDEX_INC_RE.subn("", c_txt)
    if n_sub:
      stats["empty_index_includes_removed"] += n_sub
      if not dry_run:
        c_fp.write_text(new_c, encoding="utf-8")

  # 4. Scan references across all vishvAsa/ to split multi-caller (move -> Rk/ or yajuH/) vs 1-caller (inline).
  vp_targets = {
    fp.resolve(): f"/vedAH/atharva/paippalAdam/saMhitA/{fp.relative_to(saMhitA_static).as_posix()}"
    for fp in sorted(vp_dir.rglob("*.md"))
    if fp.is_file() and fp.name not in ("_index.md", "file_list.md")
  }
  url_to_fp = {u: fp for fp, u in vp_targets.items()}
  sarva_targets = {
    fp.resolve(): f"/vedAH/atharva/paippalAdam/saMhitA/{fp.relative_to(saMhitA_static).as_posix()}"
    for fp in sorted(sarva_dir.rglob("*.md"))
    if fp.is_file() and fp.name not in ("_index.md", "file_list.md")
  }
  url_to_fp.update({u: fp for fp, u in sarva_targets.items()})
  all_targets = set(vp_targets.keys()) | set(sarva_targets.keys())
  inc_refs, link_refs = static_fixer._scan_static_references(
    scan_roots, all_targets, str(hugo_base_dir), ["vedAH"], url_to_target=url_to_fp
  )

  # Separate single-caller rels vs multi-caller rels cleanly.
  single_rels: set[str] = set()
  multi_rels: set[str] = set()
  for vp_fp in sorted(vp_targets.keys()):
    rel = vp_fp.relative_to(vp_dir).as_posix()
    sv_fp = (sarva_dir / rel).resolve()
    n_vp_refs = len(inc_refs.get(vp_fp, []))
    n_sv_refs = len(inc_refs.get(sv_fp, [])) if sv_fp.is_file() else 0
    has_link = bool(link_refs.get(vp_fp)) or bool(link_refs.get(sv_fp))
    if not has_link and n_vp_refs <= 1 and n_sv_refs <= 1:
      single_rels.add(rel)
    else:
      multi_rels.add(rel)

  # Migrate multi-caller files from flat `{vishvAsa-prastutiH,sarvASh_TIkAH}/` into `{Rk,yajuH}/...`.
  url_rewrites: dict[str, str] = {}
  multi_callers_touched: set[pathlib.Path] = set()
  multi_targets_moved: set[pathlib.Path] = set()
  for rel in sorted(multi_rels):
    vp_fp = vp_dir / rel
    sv_fp = sarva_dir / rel
    _, vp_body = split_frontmatter(vp_fp.read_text(encoding="utf-8"))
    unit_dir = "Rk" if classify_unit_kind(vp_body, default_brahmana=False) == "rk" else "yajuH"
    new_vp_fp = saMhitA_static / unit_dir / "vishvAsa-prastutiH" / rel
    new_sv_fp = saMhitA_static / unit_dir / "sarvASh_TIkAH" / rel
    old_vp_url = f"/vedAH/atharva/paippalAdam/saMhitA/vishvAsa-prastutiH/{rel}"
    new_vp_url = f"/vedAH/atharva/paippalAdam/saMhitA/{unit_dir}/vishvAsa-prastutiH/{rel}"
    old_sv_url = f"/vedAH/atharva/paippalAdam/saMhitA/sarvASh_TIkAH/{rel}"
    new_sv_url = f"/vedAH/atharva/paippalAdam/saMhitA/{unit_dir}/sarvASh_TIkAH/{rel}"
    url_rewrites[old_vp_url] = new_vp_url
    url_rewrites[old_sv_url] = new_sv_url
    for ref_fp, _, _ in inc_refs.get(vp_fp.resolve(), []) + inc_refs.get(sv_fp.resolve(), []):
      multi_callers_touched.add(ref_fp)
    stats["moved_multi_caller"] += 1
    if not dry_run:
      new_vp_fp.parent.mkdir(parents=True, exist_ok=True)
      new_sv_fp.parent.mkdir(parents=True, exist_ok=True)
      vp_fp.rename(new_vp_fp)
      multi_targets_moved.add(new_vp_fp)
      if sv_fp.is_file():
        sv_fp.rename(new_sv_fp)
        multi_targets_moved.add(new_sv_fp)

  if not dry_run and url_rewrites:
    for c_fp in sorted(multi_callers_touched):
      if not c_fp.is_file():
        continue
      txt = c_fp.read_text(encoding="utf-8")
      new_t = txt
      for old_u, new_u in url_rewrites.items():
        if old_u in new_t:
          new_t = new_t.replace(old_u, new_u)
      if new_t != txt:
        c_fp.write_text(new_t, encoding="utf-8")

  # Inline single-caller mantra pairs in sarva-prastutiH/ content files & unlink 1-caller static files.
  single_vp_urls = {f"/vedAH/atharva/paippalAdam/saMhitA/vishvAsa-prastutiH/{r}": r for r in single_rels}
  single_sv_urls = {f"/vedAH/atharva/paippalAdam/saMhitA/sarvASh_TIkAH/{r}": r for r in single_rels}
  div_url_re = re.compile(r'\burl=(["\'])([^"\']+)\1')
  updated_content_files: list[str] = []

  for c_fp in sorted(content_dir.rglob("*.md")):
    if c_fp.name in ("_index.md", "file_list.md"):
      continue
    c_txt = c_fp.read_text(encoding="utf-8")
    divs = include_helper.find_js_include_divs(c_txt)
    edits: list[tuple[int, int, str]] = []
    files_to_delete: list[pathlib.Path] = []
    for s_open, _, _, _, e_close, open_tag in divs:
      m_u = div_url_re.search(open_tag)
      if not m_u:
        continue
      url = m_u.group(2)
      if url in single_vp_urls:
        rel = single_vp_urls[url]
        vp_fp = vp_dir / rel
        if not vp_fp.is_file():
          continue
        _, vp_body = split_frontmatter(vp_fp.read_text(encoding="utf-8"))
        vp_clean = vp_body.strip()
        kind = "rk" if classify_unit_kind(vp_clean, default_brahmana=False) == "rk" else "yajuh"
        sum_lbl = format_vp_summary_with_kind("विश्वास-प्रस्तुतिः", kind)
        edits.append((s_open, e_close, format_details_block(sum_lbl, vp_clean, is_open=True)))
        files_to_delete.append(vp_fp)
      elif url in single_sv_urls:
        rel = single_sv_urls[url]
        sv_fp = sarva_dir / rel
        if not sv_fp.is_file():
          continue
        _, sv_body = split_frontmatter(sv_fp.read_text(encoding="utf-8"))
        sv_clean = sv_body.strip()
        edits.append((s_open, e_close, format_details_block("सर्वाष् टीकाः", sv_clean, is_open=False)))
        files_to_delete.append(sv_fp)
    if edits:
      edits.sort(key=lambda x: x[0], reverse=True)
      out_txt = c_txt
      for s_o, e_c, rep in edits:
        pre = out_txt[:s_o].rstrip("\n")
        post = out_txt[e_c:].lstrip("\n")
        if pre and post:
          out_txt = pre + "\n\n" + rep + "\n\n" + post
        elif pre:
          out_txt = pre + "\n\n" + rep + "\n"
        elif post:
          out_txt = rep + "\n\n" + post
        else:
          out_txt = rep + "\n"
      out_txt = re.sub(r"\n{3,}", "\n\n", out_txt)
      if not static_fixer._balanced_tags(out_txt):
        raise ValueError(f"Unbalanced tags after inlining single-caller Paippalada blocks in {c_fp}")
      stats["inlined_mantras"] += sum(1 for _, _, r in edits if "<summary>विश्वास-प्रस्तुतिः" in r)
      updated_content_files.append(str(c_fp))
      if not dry_run:
        c_fp.write_text(out_txt, encoding="utf-8")
        for fdel in files_to_delete:
          if fdel.is_file():
            fdel.unlink()

  # Clean residual empty legacy static dirs (`vishvAsa-prastutiH/`, `sarvASh_TIkAH/` directly under `saMhitA/`).
  if not dry_run:
    for root_old in (vp_dir, sarva_dir):
      if not root_old.is_dir():
        continue
      for idx_fp in list(root_old.rglob("_index.md")):
        if not split_frontmatter(idx_fp.read_text(encoding="utf-8"))[1].strip():
          idx_fp.unlink()
      for dirpath, dirnames, filenames in os.walk(root_old, topdown=False):
        if not dirnames and not filenames:
          try:
            pathlib.Path(dirpath).rmdir()
          except OSError:
            pass
    if multi_targets_moved:
      include_helper.surgical_prefill_transitive(
        scan_roots,
        [str(p) for p in sorted(multi_targets_moved)],
        hugo_base_dir=str(hugo_base_dir),
        skip_sources_with_empty_includes=False,
        only_if_prefilled=False,
        dry_run=False,
      )

  return stats


def main(argv: Sequence[str] | None = None) -> int:
  import argparse
  import json

  parser = argparse.ArgumentParser(description="Prepare Atharvaveda Paippalāda Saṁhitā corpus for dedup.")
  parser.add_argument("--dry-run", action="store_true")
  args = parser.parse_args(argv)
  res = prepare_paippalada_corpus(dry_run=args.dry_run)
  print(json.dumps(res, ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
