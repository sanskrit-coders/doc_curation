"""Backend scanner, alignment, feedback-comment insertion, and scoped git commit helpers for reviewing Vedic accent suggestions."""

from __future__ import annotations

import dataclasses
import functools
import glob
import hashlib
import json
import os
import pathlib
import re
import subprocess
from typing import Any, Iterable, Sequence

from doc_curation.md.content_processor.include import seeker as include_seeker
from doc_curation.md.content_processor.include import transformer as include_transformer
from doc_curation.sanskrit.accent import reconciler

_DEV_SUG_RE = re.compile(r"\[\[([^|\]]*[\u0900-\u097f\u1cd0-\u1cff][^|\]]*)\|([^\]]+)\]\]")
_DIV_TOKEN_RE = re.compile(r"<div\b[^>]*>|</div>", re.I)
_JS_URL_RE = re.compile(r"""\burl=(["'])(?P<url>[^"']+)\1""", re.I)
_FRONTMATTER_TOML_RE = re.compile(r"\A(\+\+\+.*?\n\+\+\+[ \t]*\n?)", re.S)
_FRONTMATTER_YAML_RE = re.compile(r"\A(---.*?\n---[ \t]*\n?)", re.S)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
_INLINE_FEEDBACK_AT_RE = re.compile(r"\+\+\+([^\n+]*?!![^\n+]*?)\+\+\+")

DEFAULT_REVIEW_CACHE_DIR = os.path.expanduser("~/.cache/doc_curation/accent_review")
_VALID_DECISIONS = frozenset({"pending", "accept", "reject", "hold"})
_ACCENT_STRIP_RE = re.compile(r"[\u0951-\u0954\u1cd0-\u1cff\u0300-\u036f]")
_SARVANAMA_PRIORITY = frozenset({"अदस्", "इदम्", "तद्", "यद्", "किम्", "एतद्", "अस्मद्", "युष्मद्"})


def _join_hyphenated_deva(tok: str) -> str:
  """Join hyphenated padapāṭha compounds with basic internal vowel/consonant sandhi."""
  clean = _ACCENT_STRIP_RE.sub("", tok).replace("ऽ", "").strip()
  clean = re.sub(r"[३3]", "", clean)
  parts = [p for p in clean.split("-") if p]
  if not parts:
    return ""
  if len(parts) == 1:
    return re.sub(r"([वयलर])्ँ", r"\1ं", parts[0]).replace("\ua8f3", "ं").replace("ँ", "ं")

  from indic_transliteration import sanscript

  def _join_slp_pair(a: str, b: str) -> str:
    # Basic internal vowel savarṇa/guṇa/vṛddhi/yaṇ sandhi + visarga/halanta helpers
    if a.endswith(("a", "A")):
      if b.startswith(("a", "A")):
        return a[:-1] + "A" + b[1:]
      if b.startswith(("i", "I")):
        return a[:-1] + "e" + b[1:]
      if b.startswith(("u", "U")):
        return a[:-1] + "o" + b[1:]
      if b.startswith("f"):
        return a[:-1] + "ar" + b[1:]
      if b.startswith(("e", "E")):
        return a[:-1] + "E" + b[1:]
      if b.startswith(("o", "O")):
        return a[:-1] + "O" + b[1:]
    elif a.endswith(("i", "I")):
      if b.startswith(("i", "I")):
        return a[:-1] + "I" + b[1:]
      if b and b[0] in "aAuUfFeEoO":
        return a[:-1] + "y" + b
    elif a.endswith(("u", "U")):
      if b.startswith(("u", "U")):
        return a[:-1] + "U" + b[1:]
      if b and b[0] in "aAiIfFeEoO":
        return a[:-1] + "v" + b
    joined_d = sanscript.transliterate(a + b, sanscript.SLP1, sanscript.DEVANAGARI)
    return sanscript.transliterate(joined_d, sanscript.DEVANAGARI, sanscript.SLP1)

  from doc_curation.sanskrit.accent import provenance as _prov

  joined_slp = sanscript.transliterate(
    re.sub(r"([वयलर])्ँ", r"\1ं", parts[0]).replace("ँ", "ं"),
    sanscript.DEVANAGARI,
    sanscript.SLP1,
  )
  for nxt in parts[1:]:
    nxt_clean = re.sub(r"([वयलर])्ँ", r"\1ं", nxt).replace("ँ", "ं")
    # Try consonant/visarga internal sandhi first in Devanagari, else vowel sandhi in SLP1
    cur_deva = sanscript.transliterate(joined_slp, sanscript.SLP1, sanscript.DEVANAGARI)
    merged_deva = cur_deva + nxt_clean
    replaced_cons = False
    for pat, rep in _prov._PADAPATHA_INTERNAL_SANDHI_PAIRS:
      m2 = pat.sub(rep, merged_deva)
      if m2 != merged_deva:
        joined_slp = sanscript.transliterate(m2, sanscript.DEVANAGARI, sanscript.SLP1)
        replaced_cons = True
        break
    if not replaced_cons:
      nxt_slp = sanscript.transliterate(nxt_clean, sanscript.DEVANAGARI, sanscript.SLP1)
      joined_slp = _join_slp_pair(joined_slp, nxt_slp)
  return sanscript.transliterate(joined_slp, sanscript.SLP1, sanscript.DEVANAGARI).replace("ँ", "ं")


def _extract_tokens_from_pp_line(pp_line: str, fallback_tok: str = "") -> list[str]:
  s = (pp_line or "").strip()
  if s.startswith("- "):
    s = s[2:].strip()
  head = s.split(" (", 1)[0].split(" +++", 1)[0].strip()
  out: list[str] = []
  if "→" in head:
    left, right = head.split("→", 1)
    for part in (right, left):
      tok = part.replace("*", "").strip().split()[0] if part.replace("*", "").strip() else ""
      if tok and tok not in out:
        out.append(tok)
  elif head:
    tok = head.replace("*", "").strip().split()[0]
    if tok:
      out.append(tok)
  if fallback_tok:
    fb = fallback_tok.strip()
    if fb.startswith("[[") and "|" in fb and fb.endswith("]]"):
      bar = fb.index("|")
      out.extend([fb[bar + 1 : -2].strip(), fb[2:bar].strip()])
    elif fb:
      out.append(fb.replace("*", "").strip())
  return [t for t in dict.fromkeys(out) if t]


@functools.lru_cache(maxsize=8192)
def resolve_goldendict_lookup(pp_line: str, fallback_tok: str = "") -> dict[str, Any]:
  """Resolve unaccented lookup word and Vidyut prātipadika/dhātu targets for GoldenDict."""
  raw_tokens = _extract_tokens_from_pp_line(pp_line, fallback_tok=fallback_tok)
  if not raw_tokens:
    return {"word": "", "pratipadika": "", "primary": "", "alternatives": []}

  joined_forms = [j for j in (_join_hyphenated_deva(t) for t in raw_tokens) if j]
  surface_word = joined_forms[0] if joined_forms else _ACCENT_STRIP_RE.sub("", raw_tokens[0]).strip()
  if not surface_word:
    return {"word": "", "pratipadika": "", "primary": "", "alternatives": []}

  basics: list[str] = []
  krts_derived: list[str] = []
  dhatus: list[str] = []
  avyayas: list[str] = []

  try:
    from indic_transliteration import sanscript
    from vidyut.kosha import PadaEntry, PratipadikaEntry
    from doc_curation.sanskrit.accent import shatapatha_solver as ss

    if ss.get_vidyut_kosha() is not None:
      for jf in joined_forms:
        slp = ss._deva_to_slp(jf)
        ents = ss._kosha_get_slp(slp)
        for e in ents:
          if isinstance(e, PadaEntry.Subanta):
            if getattr(e, "is_avyaya", False) and getattr(e, "lemma", None):
              av = sanscript.transliterate(e.lemma, sanscript.SLP1, sanscript.DEVANAGARI)
              if av not in avyayas:
                avyayas.append(av)
            pe = e.pratipadika_entry
            if isinstance(pe, PratipadikaEntry.Basic):
              p_deva = sanscript.transliterate(pe.pratipadika.text, sanscript.SLP1, sanscript.DEVANAGARI)
              if p_deva and p_deva not in basics:
                basics.append(p_deva)
            elif isinstance(pe, PratipadikaEntry.Krdanta):
              krt_name = str(pe.krt)
              root_deva = sanscript.transliterate(pe.dhatu_entry.clean_text, sanscript.SLP1, sanscript.DEVANAGARI)
              if root_deva and root_deva not in dhatus:
                dhatus.append(root_deva)
              if krt_name == "kta":
                for suf in ("तानाम्", "तात्", "तस्य", "ताय", "तेन", "तेषु", "तैः", "तः", "तम्", "ता", "ते"):
                  if jf.endswith(suf) and len(jf) > len(suf):
                    st = jf[: -len(suf)] + "त"
                    if st not in krts_derived:
                      krts_derived.append(st)
                    break
              elif krt_name == "Satf~":
                for suf in ("द्भ्यः", "द्भिः", "न्तः", "न्तम्", "न्ति", "ताम्", "त्सु", "तः", "ते", "ता", "तम्", "त्", "न्"):
                  if jf.endswith(suf) and len(jf) > len(suf) + 1:
                    st = jf[: -len(suf)] + "त्"
                    if st not in krts_derived:
                      krts_derived.append(st)
                    break
          elif isinstance(e, PadaEntry.Tinanta):
            rt = sanscript.transliterate(e.dhatu_entry.clean_text, sanscript.SLP1, sanscript.DEVANAGARI)
            if rt and rt not in dhatus:
              dhatus.append(rt)
        if basics or krts_derived or avyayas or dhatus:
          break
  except Exception:
    pass

  primary_prat = ""
  if basics:
    basics_sorted = sorted(
      basics,
      key=lambda b: (
        0 if b in _SARVANAMA_PRIORITY else 1,
        -len(os.path.commonprefix([b, surface_word])),
        -len(b) if len(b) <= len(surface_word) else len(b),
      ),
    )
    primary_prat = basics_sorted[0]
    basics = basics_sorted
  elif krts_derived:
    primary_prat = krts_derived[0]
  elif avyayas:
    primary_prat = avyayas[0]

  primary = primary_prat or surface_word
  alternatives: list[str] = []
  for cand in [surface_word, *basics, *krts_derived, *dhatus]:
    if cand and cand != primary and cand not in alternatives:
      alternatives.append(cand)

  return {
    "word": surface_word,
    "pratipadika": primary_prat,
    "primary": primary,
    "alternatives": alternatives[:3],
  }


def infer_hugo_base_dir(path: str) -> str:
  """Infer the Hugo workspace parent containing ``<site>/(content|static)`` from ``path``."""
  abs_p = os.path.abspath(path)
  cur = pathlib.Path(abs_p if os.path.isdir(abs_p) else os.path.dirname(abs_p))
  for parent in (cur, *cur.parents):
    if parent.name in ("content", "static") and len(parent.parents) >= 2:
      return str(parent.parent.parent)
  fallback = "/home/vvasuki/gitland/vishvAsa"
  return fallback if os.path.isdir(fallback) else str(cur.parent)


def vishvasa_rel_path(file_path: str | None, hugo_base_dir: str | None = None) -> str:
  """Return ``file_path`` relative to the ``vishvAsa`` root (or absolute path if outside it)."""
  if not file_path:
    return ""
  abs_f = os.path.normpath(os.path.abspath(file_path))
  candidates = []
  if hugo_base_dir:
    candidates.append(os.path.normpath(os.path.abspath(hugo_base_dir)))
  inferred = os.path.normpath(os.path.abspath(infer_hugo_base_dir(abs_f)))
  if inferred not in candidates:
    candidates.append(inferred)
  default_v = "/home/vvasuki/gitland/vishvAsa"
  if os.path.isdir(default_v) and default_v not in candidates:
    candidates.append(default_v)
  for root in candidates:
    try:
      if os.path.commonpath([root, abs_f]) == root and abs_f != root:
        return os.path.relpath(abs_f, root)
    except ValueError:
      continue
  return abs_f


def find_git_root(file_or_dir: str, _cache: dict[str, str | None] | None = None) -> str | None:
  """Return the enclosing git worktree root for ``file_or_dir``, or ``None`` if untracked/non-git."""
  abs_p = os.path.abspath(file_or_dir)
  d = abs_p if os.path.isdir(abs_p) else os.path.dirname(abs_p)
  if _cache is not None and d in _cache:
    return _cache[d]
  res: str | None = None
  if os.path.isdir(d):
    try:
      out = subprocess.check_output(
        ["git", "-C", d, "rev-parse", "--show-toplevel"],
        stderr=subprocess.DEVNULL,
        text=True,
      ).strip()
      if out:
        res = os.path.normpath(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
      res = None
  if _cache is not None:
    _cache[d] = res
  return res


def get_git_status_map(repo_root: str) -> tuple[dict[str, str], list[str]]:
  """Return ``({abs_path: porcelain_xy}, staged_rel_paths)`` for all dirty/untracked files in ``repo_root``."""
  st = subprocess.check_output(
    ["git", "-C", repo_root, "status", "--porcelain", "-uall"],
    text=True,
  )
  status_map: dict[str, str] = {}
  for ln in st.splitlines():
    if len(ln) < 4:
      continue
    xy = ln[:2]
    rel = ln[3:].split(" -> ")[-1].strip()
    if rel.startswith('"') and rel.endswith('"'):
      rel = rel[1:-1]
    abs_f = os.path.normpath(os.path.join(repo_root, rel))
    status_map[abs_f] = xy
  cached = subprocess.check_output(
    ["git", "-C", repo_root, "diff", "--cached", "--name-only"],
    text=True,
  )
  staged = [s for s in cached.splitlines() if s.strip()]
  return status_map, staged


def _strip_outer_parens(text: str) -> str:
  if not (text.startswith("(") and text.endswith(")")):
    return text
  depth = 0
  for idx, ch in enumerate(text):
    if ch == "(":
      depth += 1
    elif ch == ")":
      depth -= 1
      if depth == 0 and idx < len(text) - 1:
        return text
  return text[1:-1].strip() if depth == 0 else text


def format_feedback_comment(feedback_text: str) -> str:
  """Normalize user feedback into ``+++(FEEDBACK!!)+++`` (or ``""`` when cleared)."""
  raw = feedback_text.strip()
  if not raw:
    return ""
  if raw.startswith("+++") and raw.endswith("+++"):
    raw = raw[3:-3].strip()
  raw = _strip_outer_parens(raw)
  raw = re.sub(r"\s+", " ", raw).replace("+++", "...")
  if not raw:
    return ""
  if not raw.endswith("!!"):
    raw = f"{raw}!!"
  return f"+++({raw})+++"


def extract_feedback_inner(comment_tail: str) -> str:
  """Extract editable text from trailing ``+++(FEEDBACK!!)+++`` comment."""
  m = _INLINE_FEEDBACK_AT_RE.search(comment_tail or "")
  if not m:
    return ""
  return _strip_outer_parens(m.group(1).strip())


def _strip_frontmatter(text: str) -> tuple[str, str]:
  m = _FRONTMATTER_TOML_RE.match(text) or _FRONTMATTER_YAML_RE.match(text)
  if m:
    return m.group(1), text[m.end() :]
  return "", text


def _find_all_js_include_spans(markdown_text: str) -> list[tuple[int, int, str]]:
  """Return ``(start, end, url)`` for every balanced ``<div class="js_include" ...>`` (including nested ones)."""
  spans: list[tuple[int, int, str]] = []
  stack: list[tuple[int, bool, str]] = []
  for m in _DIV_TOKEN_RE.finditer(markdown_text):
    tok = m.group(0)
    if tok.lower().startswith("<div"):
      is_js = "js_include" in tok.lower()
      url = ""
      if is_js:
        mu = _JS_URL_RE.search(tok)
        if mu:
          url = mu.group("url").strip()
      stack.append((m.start(), is_js, url))
    elif stack:
      start_pos, is_js, url = stack.pop()
      if is_js and url:
        spans.append((start_pos, m.end(), url))
  return spans


def _innermost_js_include(pos: int, all_spans: Sequence[tuple[int, int, str]]) -> str | None:
  best: tuple[int, str] | None = None
  for s, e, url in all_spans:
    if s <= pos < e:
      width = e - s
      if best is None or width < best[0]:
        best = (width, url)
  return best[1] if best else None


def _is_accent_suggestion_pair(old_s: str, new_s: str) -> bool:
  if not reconciler.has_us_accents(old_s + new_s):
    return False
  return bool(re.search(r"[\u0900-\u097f]", old_s + new_s))


def _paired_static_sibling(fp: str, from_layer: str, to_layer: str) -> str | None:
  needle = f"/{from_layer}/"
  if needle not in fp:
    return None
  idx = fp.rfind(needle)
  cand = fp[:idx] + f"/{to_layer}/" + fp[idx + len(needle) :]
  return cand if os.path.isfile(cand) else None


def _strip_js_include_spans(body: str) -> str:
  """Remove nested ``<div class="js_include" ...>...</div>`` spans so a wrapper keeps only its own prose."""
  spans = _find_all_js_include_spans(body)
  if not spans:
    return body
  # Merge overlapping/nested spans into outermost ranges
  sorted_s = sorted(spans, key=lambda t: (t[0], -t[1]))
  outer: list[tuple[int, int]] = []
  for s, e, _ in sorted_s:
    if outer and s < outer[-1][1]:
      continue
    outer.append((s, e))
  parts: list[str] = []
  pos = 0
  for s, e in outer:
    parts.append(body[pos:s])
    pos = e
  parts.append(body[pos:])
  return "".join(parts).strip("\n")


def _extract_static_vp_body_text(txt: str) -> tuple[str, str]:
  """Extract ``(summary, body)`` from a ``vishvAsa-prastutiH`` markdown string (excluding child ``js_include`` spans)."""
  _, body = _strip_frontmatter(txt)
  stripped = body.strip()
  m_det = re.fullmatch(
    r"<details(?:\s+open)?><summary>([^<]*)</summary>(.*?)</details>",
    stripped,
    flags=re.S | re.I,
  )
  if m_det and m_det.group(1).strip().startswith("विश्वास-प्रस्तुतिः"):
    return m_det.group(1).strip(), _strip_js_include_spans(m_det.group(2).strip("\n"))
  leaves = [
    m
    for m in reconciler.LEAF_DETAILS_RE.finditer(body)
    if m.group(1).strip().startswith("विश्वास-प्रस्तुतिः")
  ]
  if len(leaves) == 1:
    return leaves[0].group(1).strip(), _strip_js_include_spans(leaves[0].group(2).strip("\n"))
  return "विश्वास-प्रस्तुतिः", _strip_js_include_spans(stripped)


def _extract_static_vp_body(fp: str) -> tuple[str, str]:
  """Read a ``vishvAsa-prastutiH`` static file's own body (excluding child ``js_include`` spans)."""
  return _extract_static_vp_body_text(open(fp, encoding="utf-8", errors="ignore").read())


def _extract_pp_blocks_from_file(fp: str) -> tuple[list[tuple[str, str, int]], str]:
  """Return ``([(summary, body, pp_block_idx), ...], mula_preview)`` from a file outside ``js_include``s."""
  txt = open(fp, encoding="utf-8", errors="ignore").read()
  inc = reconciler.find_js_include_spans(txt)
  pp_blocks: list[tuple[str, str, int]] = []
  mula_parts: list[str] = []
  pp_idx = 0
  for m in reconciler.LEAF_DETAILS_RE.finditer(txt):
    if inc and any(a <= m.start() < b for a, b in inc):
      continue
    hdr = m.group(1).strip()
    body = m.group(2).strip("\n")
    if hdr.startswith("पद-पाठः (यान्त्रिकः"):
      pp_blocks.append((hdr, body, pp_idx))
      pp_idx += 1
    elif hdr.startswith("मूलम्"):
      mula_parts.append(f"[{hdr}] {body.strip()}")
  return pp_blocks, "\n".join(mula_parts[:3])


def _nearest_heading(text: str, pos: int) -> str:
  last_h = ""
  for hm in _HEADING_RE.finditer(text, 0, pos):
    last_h = f"{hm.group(1)} {hm.group(2)}"
  return last_h


@dataclasses.dataclass
class _ClusterSpec:
  section_heading: str
  cluster_idx: int
  vp_summary: str
  vp_raw_body: str
  vp_file: str | None
  vp_is_inline: bool
  pp_summary: str
  pp_body: str
  pp_file: str | None
  pp_block_idx: int
  pp_is_inline: bool
  pp_shAkha_label: str | None
  mula_preview: str
  host_files: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class ReviewItem:
  item_id: str
  display_file: str
  rel_path: str
  section_heading: str
  cluster_idx: int
  kind: str  # "both" | "vp_only" | "pp_only"
  vp_file: str | None
  pp_file: str | None
  pp_block_idx: int
  pp_item_idx: int | None
  pp_line_core: str
  relevant_files: list[str]
  host_files: list[str]
  vp_summary: str
  vp_raw_body: str
  vp_sug_old: str
  vp_sug_new: str
  vp_sug_occ_idx: int
  vp_highlight_ranges: list[tuple[int, int]]
  pp_summary: str
  pp_shAkha_label: str | None
  pp_lines: list[str]
  pp_target_idx: int | None
  mula_preview: str
  existing_feedback: str
  feedback_target: str  # "pp" | "vp" | ""

  def to_dict(
    self,
    *,
    n_context: int = 3,
    decision: str = "pending",
    file_statuses: dict[str, str] | None = None,
    hugo_base_dir: str | None = None,
  ) -> dict[str, Any]:
    lines = self.pp_lines
    idx = self.pp_target_idx
    if lines and idx is not None and 0 <= idx < len(lines):
      start = max(0, idx - n_context)
      end = min(len(lines), idx + n_context + 1)
      ctx_before = lines[start:idx]
      target_line = lines[idx]
      ctx_after = lines[idx + 1 : end]
    else:
      ctx_before = []
      target_line = ""
      ctx_after = lines[: min(len(lines), n_context)]

    rel_infos = []
    for rf in self.relevant_files:
      xy = (file_statuses or {}).get(rf, "clean")
      v_rel = vishvasa_rel_path(rf, hugo_base_dir)
      if self.vp_file and os.path.normpath(rf) == os.path.normpath(self.vp_file):
        role = "विश्वास-प्रस्तुतिः"
      elif self.pp_file and os.path.normpath(rf) == os.path.normpath(self.pp_file):
        role = "सर्वाष् टीकाः / पद-पाठः"
      else:
        role = "File"
      rel_infos.append({
        "path": rf,
        "short": v_rel,
        "vishvasa_rel": v_rel,
        "role": role,
        "git_status": xy,
      })

    vp_rel = vishvasa_rel_path(self.vp_file, hugo_base_dir)
    pp_rel = vishvasa_rel_path(self.pp_file, hugo_base_dir)
    host_rel = [vishvasa_rel_path(hf, hugo_base_dir) for hf in self.host_files]
    display_rel = vishvasa_rel_path(self.display_file, hugo_base_dir)

    return {
      "item_id": self.item_id,
      "display_file": self.display_file,
      "display_rel": display_rel,
      "rel_path": vp_rel or display_rel or self.rel_path,
      "section_heading": self.section_heading,
      "cluster_idx": self.cluster_idx,
      "kind": self.kind,
      "vp_file": self.vp_file,
      "vp_rel": vp_rel,
      "pp_file": self.pp_file,
      "pp_rel": pp_rel,
      "pp_block_idx": self.pp_block_idx,
      "pp_item_idx": self.pp_item_idx,
      "relevant_files": rel_infos,
      "host_files": self.host_files,
      "host_files_rel": host_rel,
      "vp_summary": self.vp_summary,
      "vp_raw_body": self.vp_raw_body,
      "vp_sug_old": self.vp_sug_old,
      "vp_sug_new": self.vp_sug_new,
      "vp_highlight_ranges": self.vp_highlight_ranges,
      "pp_summary": self.pp_summary,
      "pp_shAkha_label": self.pp_shAkha_label,
      "pp_total_lines": len(lines),
      "pp_target_idx": idx,
      "pp_context_before": ctx_before,
      "pp_target_line": target_line,
      "pp_context_after": ctx_after,
      "pp_all_lines": lines,
      "mula_preview": self.mula_preview,
      "existing_feedback": self.existing_feedback,
      "feedback_target": self.feedback_target,
      "decision": decision,
      "pp_goldendict": resolve_goldendict_lookup(target_line or self.pp_line_core, self.vp_sug_new or self.vp_sug_old),
    }


def _bullet_lines_only(pp_body: str) -> list[str]:
  return [ln for ln in pp_body.splitlines() if ln.startswith("- ")]


def _fast_parse_pp_bullets(pp_lines: Sequence[str]) -> list[tuple[str, str, bool]]:
  """Fast parse ``(ar, ref, vyat)`` from bullet lines without running heavy provenance validation."""
  out: list[tuple[str, str, bool]] = []
  for raw_ln in pp_lines:
    ln, _ = reconciler.split_padapatha_line_comment(raw_ln)
    m_arr = re.match(r"^-\s+(.*?)\s+→\s+\*\*(.*?)\*\*\s+\((.*)\)$", ln)
    if m_arr:
      out.append((m_arr.group(1).strip(), m_arr.group(2).strip(), True))
    else:
      m_pl = re.match(r"^-\s+([^\s(]+)\s+\((.*)\)$", ln)
      if m_pl:
        p = m_pl.group(1).strip()
        out.append((p, p, False))
      else:
        p = ln[2:].split(" (")[0].strip()
        out.append((p, p, False))
  return out


def _bare_deva_fast(s: str) -> str:
  return re.sub(r"[^\u0905-\u0939\u093d-\u094d\u0958-\u0963]", "", s)


def _deva_cons_skel(s: str) -> str:
  """Return consonant + initial-vowel skeleton ignoring sandhi vowel/visarga variations."""
  s_clean = re.sub(r"[\s\-ऽःंँ\u0951-\u0954\u1cd0-\u1cff]", "", s)
  if not s_clean:
    return ""
  out: list[str] = []
  # Preserve an initial independent vowel (अ/आ/इ/ई/उ/ऊ/ऋ/ए/ओ/औ) so prefix matches stay distinct
  if "\u0904" <= s_clean[0] <= "\u0914":
    out.append("अ" if s_clean[0] == "आ" else s_clean[0])
  for ch in s_clean:
    if "\u0915" <= ch <= "\u0939" or "\u0958" <= ch <= "\u095f":
      out.append(ch)
  return "".join(out)


def _fallback_match_pp_index(
  old_s: str,
  new_s: str,
  pp_items: Sequence[reconciler.PadapathaItem],
) -> int | None:
  if not pp_items:
    return None
  old_b = _bare_deva_fast(old_s).rstrip("ःम्न्त्")
  old_sk = _deva_cons_skel(old_s)
  old_sk_yan = re.sub(r"([क-ह])[यव]", r"\1", old_sk)

  # Pass 1: bare Devanagari substring/exact match (prefer `vyat` arrow items)
  for want_vyat in (True, False):
    for idx, it in enumerate(pp_items):
      if want_vyat and not it.vyat:
        continue
      cb = _bare_deva_fast(it.ref).rstrip("ःम्न्त्")
      if cb and old_b and (cb == old_b or (len(cb) >= 2 and cb in old_b) or (len(old_b) >= 2 and old_b in cb)):
        return idx

  # Pass 2: single-item consonant skeleton (handles compounds / -s / -o sandhi like आचार्य-अधीनः == आचार्याधीनो)
  if len(old_sk) >= 3:
    for want_vyat in (True, False):
      for idx, it in enumerate(pp_items):
        if want_vyat and not it.vyat:
          continue
        sk = _deva_cons_skel(it.ar)
        if sk and (sk == old_sk or (len(sk) >= 3 and sk in old_sk)):
          return idx

  # Pass 3: adjacent merged pair `(pp_items[j], pp_items[j+1])` for visarga/vowel/yan sandhi
  if len(old_sk) >= 3:
    for j in range(len(pp_items) - 1):
      sk1 = _deva_cons_skel(pp_items[j].ar)
      sk2 = _deva_cons_skel(pp_items[j + 1].ar)
      # Strip initial 'अ' from second member on vowel coalescence (e.g. अ᳓पः + अशान -> अप + शन)
      sk2_join = sk2[1:] if sk2.startswith(("अ", "आ")) else sk2
      pair_sks = {sk1 + sk2, sk1 + sk2_join}
      pair_sks_yan = {re.sub(r"([क-ह])[यव]", r"\1", p) for p in pair_sks}
      if old_sk in pair_sks or old_sk_yan in pair_sks or old_sk_yan in pair_sks_yan:
        if pp_items[j].vyat:
          return j
        if pp_items[j + 1].vyat:
          return j + 1
        return j
  return None


def _align_cluster_to_items(
  spec: _ClusterSpec,
  *,
  display_file: str,
  base_dir: str,
  hugo_base_dir: str | None = None,
) -> list[ReviewItem]:
  vp_body = spec.vp_raw_body or ""
  pp_lines = _bullet_lines_only(spec.pp_body or "")
  fast_pp = _fast_parse_pp_bullets(pp_lines) if pp_lines else []

  relevant_files = [
    os.path.normpath(p)
    for p in dict.fromkeys([spec.vp_file, spec.pp_file])
    if p
  ]
  if not relevant_files:
    relevant_files = [os.path.normpath(display_file)]
  rel_path = vishvasa_rel_path(spec.vp_file or display_file, hugo_base_dir)

  vyat_indices = [idx for idx, (_, _, v) in enumerate(fast_pp) if v]
  fast_sugs: list[tuple[int, int, str, str, int]] = []
  occ_cnt: dict[str, int] = {}
  for m_s in _DEV_SUG_RE.finditer(vp_body):
    o_s, n_s = m_s.group(1), m_s.group(2)
    if _is_accent_suggestion_pair(o_s, n_s):
      raw_t = f"[[{o_s}|{n_s}]]"
      oi = occ_cnt.get(raw_t, 0)
      occ_cnt[raw_t] = oi + 1
      fast_sugs.append((m_s.start(), m_s.end(), o_s, n_s, oi))

  # Only show cases where विश्वास-प्रस्तुतिः has an accent fix suggestion
  if not fast_sugs:
    return []

  # Fast path when `[[OLD|NEW]]` spans and `→` lines match 1-to-1 cleanly in order
  if vp_body and fast_sugs and len(fast_sugs) == len(vyat_indices):
    matched_fast = True
    items_fast: list[ReviewItem] = []
    for ii, (s_pos, e_pos, o_s, n_s, oi) in zip(vyat_indices, fast_sugs):
      ar, ref, _ = fast_pp[ii]
      ar_b = _bare_deva_fast(ar).rstrip("ःम्न्त्")
      ob = _bare_deva_fast(o_s)
      # Tolerate single-syllable roots or final sandhi via >=2 char or prefix overlap
      if len(ar_b) >= 2 and ar_b[: min(3, len(ar_b))] not in ob and ob[: min(3, len(ob))] not in ar_b:
        matched_fast = False
        break
      raw_line = pp_lines[ii]
      core_line, comment_tail = reconciler.split_padapatha_line_comment(raw_line)
      existing_fb = extract_feedback_inner(comment_tail)
      id_cluster = 0 if (spec.vp_file and "/vishvAsa-prastutiH/" in spec.vp_file) else spec.cluster_idx
      id_src = f"vp|{spec.vp_file or display_file}|{id_cluster}|{o_s}|{n_s}|{oi}"
      item_id = hashlib.sha1(id_src.encode("utf-8")).hexdigest()[:16]
      items_fast.append(
        ReviewItem(
          item_id=item_id,
          display_file=os.path.normpath(display_file),
          rel_path=rel_path,
          section_heading=spec.section_heading,
          cluster_idx=spec.cluster_idx,
          kind="both",
          vp_file=os.path.normpath(spec.vp_file) if spec.vp_file else None,
          pp_file=os.path.normpath(spec.pp_file) if spec.pp_file else None,
          pp_block_idx=spec.pp_block_idx,
          pp_item_idx=ii,
          pp_line_core=core_line,
          relevant_files=relevant_files,
          host_files=list(spec.host_files),
          vp_summary=spec.vp_summary,
          vp_raw_body=vp_body,
          vp_sug_old=o_s,
          vp_sug_new=n_s,
          vp_sug_occ_idx=oi,
          vp_highlight_ranges=[(s_pos, e_pos)],
          pp_summary=spec.pp_summary,
          pp_shAkha_label=spec.pp_shAkha_label,
          pp_lines=pp_lines,
          pp_target_idx=ii,
          mula_preview=spec.mula_preview,
          existing_feedback=existing_fb,
          feedback_target="pp" if spec.pp_file else "vp",
        )
      )
    if matched_fast:
      return items_fast

  # Slow/precise path for merged sandhi, extra PP historical arrows, or unmatched cases
  pp_items = [
    reconciler.PadapathaItem(ar=ar, ref=ref, prov="", vyat=vyat, solid=True)
    for ar, ref, vyat in fast_pp
  ]
  vp_pieces = reconciler._extract_vp_pieces(vp_body) if vp_body else []

  pi_to_iis: dict[int, list[int]] = {}
  if vp_pieces and pp_items:
    pp_keys, pp_meta, _, _ = reconciler._flatten_pp_syllables(pp_items)
    vp_keys = [kv for pc in vp_pieces for kv in pc["keys"]]
    vp_meta = [(pi, si) for pi, pc in enumerate(vp_pieces) for si in range(len(pc["keys"]))]
    if pp_keys and vp_keys and len(pp_keys) <= 350 and len(vp_keys) <= 350:
      pc_syl_sources = reconciler._map_pp_to_vp_syllables(
        vp_body,
        vp_pieces,
        pp_keys,
        pp_meta,
        vp_keys,
        vp_meta,
        reconciler._pp_member_starts(pp_items),
      )
      for pi, syl_srcs in enumerate(pc_syl_sources):
        seen_ii: set[int] = set()
        for srcs in syl_srcs:
          for tup in srcs:
            for pp_si in tup:
              if 0 <= pp_si < len(pp_meta):
                ii = pp_meta[pp_si][0]
                if ii not in seen_ii:
                  seen_ii.add(ii)
                  pi_to_iis.setdefault(pi, []).append(ii)

  sug_pis = [
    pi
    for pi, pc in enumerate(vp_pieces)
    if pc["is_sug"] and _is_accent_suggestion_pair(pc["old"], pc["new"])
  ]
  sug_occ_of_pi: dict[int, int] = {}
  occ_counter: dict[str, int] = {}
  for pi in sug_pis:
    raw_tok = f"[[{vp_pieces[pi]['old']}|{vp_pieces[pi]['new']}]]"
    sug_occ_of_pi[pi] = occ_counter.get(raw_tok, 0)
    occ_counter[raw_tok] = sug_occ_of_pi[pi] + 1

  items_out: list[ReviewItem] = []
  for pi in sug_pis:
    pc = vp_pieces[pi]
    mapped_iis = [ii for ii in pi_to_iis.get(pi, []) if 0 <= ii < len(pp_items)]
    target_ii: int | None = None
    if mapped_iis:
      # Prefer mapped `→` arrow bullet when a sandhi-joined suggestion spans multiple padas
      vyat_mapped = [ii for ii in mapped_iis if pp_items[ii].vyat]
      target_ii = vyat_mapped[0] if vyat_mapped else mapped_iis[0]
    if target_ii is None and pp_items:
      target_ii = _fallback_match_pp_index(pc["old"], pc["new"], pp_items)

    core_line = ""
    existing_fb = ""
    fb_target = "vp"
    if target_ii is not None and 0 <= target_ii < len(pp_lines):
      core_line, comment_tail = reconciler.split_padapatha_line_comment(pp_lines[target_ii])
      existing_fb = extract_feedback_inner(comment_tail)
      if spec.pp_file:
        fb_target = "pp"
    else:
      after = vp_body[pc["end"] : min(len(vp_body), pc["end"] + 160)]
      m_after = re.match(r"^(?:\*\*)?\s*\+\+\+([^\n+]*?!![^\n+]*?)\+\+\+", after)
      if m_after:
        existing_fb = m_after.group(1).strip()

    occ_idx = sug_occ_of_pi[pi]
    id_cluster = 0 if (spec.vp_file and "/vishvAsa-prastutiH/" in spec.vp_file) else spec.cluster_idx
    id_src = f"vp|{spec.vp_file or display_file}|{id_cluster}|{pc['old']}|{pc['new']}|{occ_idx}"
    item_id = hashlib.sha1(id_src.encode("utf-8")).hexdigest()[:16]

    items_out.append(
      ReviewItem(
        item_id=item_id,
        display_file=os.path.normpath(display_file),
        rel_path=rel_path,
        section_heading=spec.section_heading,
        cluster_idx=spec.cluster_idx,
        kind="both" if target_ii is not None else "vp_only",
        vp_file=os.path.normpath(spec.vp_file) if spec.vp_file else None,
        pp_file=os.path.normpath(spec.pp_file) if spec.pp_file else None,
        pp_block_idx=spec.pp_block_idx,
        pp_item_idx=target_ii,
        pp_line_core=core_line,
        relevant_files=relevant_files,
        host_files=list(spec.host_files),
        vp_summary=spec.vp_summary,
        vp_raw_body=vp_body,
        vp_sug_old=pc["old"],
        vp_sug_new=pc["new"],
        vp_sug_occ_idx=occ_idx,
        vp_highlight_ranges=[(pc["start"], pc["end"])],
        pp_summary=spec.pp_summary,
        pp_shAkha_label=spec.pp_shAkha_label,
        pp_lines=pp_lines,
        pp_target_idx=target_ii,
        mula_preview=spec.mula_preview,
        existing_feedback=existing_fb,
        feedback_target=fb_target,
      )
    )

  return items_out


def _outer_details_spans(txt: str) -> list[tuple[int, int]]:
  """Return top-level ``<details>...</details>`` character spans (including nested children)."""
  spans: list[tuple[int, int]] = []
  stack: list[int] = []
  for m in re.finditer(r"<details\b[^>]*>|</details>", txt, re.I):
    tok = m.group(0)
    if tok.lower().startswith("<details"):
      stack.append(m.start())
    elif stack:
      start_pos = stack.pop()
      if not stack:
        spans.append((start_pos, m.end()))
  return spans


def _outer_heading_positions(txt: str) -> list[int]:
  """Return byte positions of top-level section headings outside ``<details>`` blocks."""
  det_spans = _outer_details_spans(txt)
  positions: list[int] = []
  for hm in re.finditer(r"^(?:#{1,3})\s+", txt, re.M):
    pos = hm.start()
    if any(a <= pos < b for a, b in det_spans):
      continue
    positions.append(pos)
  return positions


def _filter_pp_blocks_for_shAkha(
  pp_blocks: list[tuple[str, str, int]],
  ref_path: str,
) -> list[tuple[str, str, int]]:
  if len(pp_blocks) <= 1:
    return pp_blocks
  if "/kANvam/" in ref_path:
    cand = [b for b in pp_blocks if "काण्व" in (reconciler.parse_padapatha_header(b[0])[0] or "")]
    if cand:
      return cand
  if "/ekAgnikANDam/" in ref_path:
    cand = [b for b in pp_blocks if "एकाग्निकाण्ड" in (reconciler.parse_padapatha_header(b[0])[0] or "")]
    if cand:
      return cand
  unqual = [b for b in pp_blocks if reconciler.parse_padapatha_header(b[0])[0] is None]
  return unqual or pp_blocks


def _extract_clusters_from_static_sarvash(
  fp: str,
  *,
  vp_file_override: str | None = None,
  host_files: Sequence[str] = (),
) -> list[_ClusterSpec]:
  pp_blocks, mula_preview = _extract_pp_blocks_from_file(fp)
  vp_file = vp_file_override or _paired_static_sibling(fp, "sarvASh_TIkAH", "vishvAsa-prastutiH")
  if not vp_file:
    return []
  vp_summary, vp_raw_body = _extract_static_vp_body(vp_file)
  has_vp_sug = any(_is_accent_suggestion_pair(o, n) for o, n in _DEV_SUG_RE.findall(vp_raw_body))
  if not has_vp_sug:
    return []

  selected_pps = _filter_pp_blocks_for_shAkha(pp_blocks, vp_file or fp)
  specs: list[_ClusterSpec] = []
  for pp_hdr, pp_body, pp_idx in selected_pps[:1]:
    shAkha, _, _ = reconciler.parse_padapatha_header(pp_hdr)
    specs.append(
      _ClusterSpec(
        section_heading="",
        cluster_idx=pp_idx,
        vp_summary=vp_summary,
        vp_raw_body=vp_raw_body,
        vp_file=vp_file,
        vp_is_inline=True,
        pp_summary=pp_hdr,
        pp_body=pp_body,
        pp_file=fp,
        pp_block_idx=pp_idx,
        pp_is_inline=True,
        pp_shAkha_label=shAkha,
        mula_preview=mula_preview,
        host_files=list(host_files),
      )
    )
  if not specs:
    specs.append(
      _ClusterSpec(
        section_heading="",
        cluster_idx=0,
        vp_summary=vp_summary,
        vp_raw_body=vp_raw_body,
        vp_file=vp_file,
        vp_is_inline=True,
        pp_summary="",
        pp_body="",
        pp_file=None,
        pp_block_idx=0,
        pp_is_inline=True,
        pp_shAkha_label=None,
        mula_preview=mula_preview,
        host_files=list(host_files),
      )
    )
  return specs


def _extract_clusters_from_content_or_mixed(
  fp: str,
  txt: str,
  hugo_base_dir: str,
  *,
  extra_vp_to_tk: dict[str, list[str]] | None = None,
) -> list[_ClusterSpec]:
  """Extract ``(विश्वास-प्रस्तुतिः, पद-पाठः)`` clusters across inline blocks and ``js_include`` wrappers."""
  all_inc = _find_all_js_include_spans(txt)
  outer_headings = _outer_heading_positions(txt)
  resolved_cache: dict[str, str | None] = {}
  static_pp_cache: dict[str, tuple[list[tuple[str, str, int]], str]] = {}
  static_vp_cache: dict[str, tuple[str, str]] = {}

  def _res_url(u: str) -> str | None:
    if u not in resolved_cache:
      resolved_cache[u] = include_seeker.resolve_include_file_path(u, hugo_base_dir, fp)
    return resolved_cache[u]

  # Collect ordered block events from leaf <details> plus any unfilled empty leaf js_includes
  events: list[dict[str, Any]] = []
  leaf_spans: list[tuple[int, int]] = []
  for m in reconciler.LEAF_DETAILS_RE.finditer(txt):
    hdr = m.group(1).strip()
    inc_url = _innermost_js_include(m.start(), all_inc)
    src_file = _res_url(inc_url) if inc_url else fp
    leaf_spans.append((m.start(), m.end()))
    events.append({
      "start": m.start(),
      "end": m.end(),
      "hdr": hdr,
      "body": m.group(2).strip("\n"),
      "src_file": src_file or fp,
      "inc_url": inc_url,
    })

  # Include leaf js_include divs pointing to vishvAsa-prastutiH / sarvASh_TIkAH whose inner summary has tags (e.g. <h2>)
  for s, e, u in all_inc:
    if "/vishvAsa-prastutiH/" not in u and "/sarvASh_TIkAH/" not in u:
      continue
    if any(s <= ls and le <= e for ls, le in leaf_spans):
      continue
    tgt = _res_url(u)
    if not tgt or not os.path.isfile(tgt):
      continue
    if "/vishvAsa-prastutiH/" in u:
      if tgt not in static_vp_cache:
        static_vp_cache[tgt] = _extract_static_vp_body(tgt)
      v_hdr, v_body = static_vp_cache[tgt]
      events.append({
        "start": s,
        "end": e,
        "hdr": v_hdr,
        "body": v_body,
        "src_file": tgt,
        "inc_url": u,
      })
    elif "/sarvASh_TIkAH/" in u:
      if tgt not in static_pp_cache:
        static_pp_cache[tgt] = _extract_pp_blocks_from_file(tgt)
      p_list, _ = static_pp_cache[tgt]
      for ph, pb, _ in p_list:
        events.append({
          "start": s,
          "end": e,
          "hdr": ph,
          "body": pb,
          "src_file": tgt,
          "inc_url": u,
        })

  events.sort(key=lambda ev: ev["start"])

  # Track per-file sequential index of पद-पाठः (यान्त्रिकः) blocks inside the inline file
  pp_idx_counter: dict[str, int] = {}
  for ev in events:
    if ev["hdr"].startswith("पद-पाठः (यान्त्रिकः"):
      sf = ev["src_file"]
      if ev["inc_url"] is None:
        idx_val = pp_idx_counter.get(sf, 0)
        pp_idx_counter[sf] = idx_val + 1
        ev["pp_block_idx"] = idx_val
      else:
        ev["pp_block_idx"] = 0

  # Group into VP-led clusters separated only by headings outside <details>
  clusters_raw: list[dict[str, Any]] = []
  cur: dict[str, Any] | None = None
  last_heading_pos = -1

  for ev in events:
    hdr = ev["hdr"]
    if hdr.startswith("विश्वास-प्रस्तुतिः"):
      vp_sf = ev["src_file"]
      vp_body = ev["body"]
      vp_hdr = hdr
      if ev["inc_url"] and vp_sf and os.path.isfile(vp_sf) and vp_sf != fp:
        if vp_sf not in static_vp_cache:
          static_vp_cache[vp_sf] = _extract_static_vp_body(vp_sf)
        vp_hdr, vp_body = static_vp_cache[vp_sf]
      cur = {
        "start": ev["start"],
        "vp_hdr": vp_hdr,
        "vp_body": vp_body,
        "vp_file": vp_sf,
        "vp_inc_url": ev["inc_url"],
        "pps": [],
        "mulas": [],
      }
      clusters_raw.append(cur)
      last_heading_pos = ev["start"]
    elif hdr.startswith("पद-पाठः (यान्त्रिकः") or hdr.startswith("मूलम्"):
      crossed_heading = any(last_heading_pos < hb < ev["start"] for hb in outer_headings)
      if cur is not None and not crossed_heading:
        if hdr.startswith("पद-पाठः (यान्त्रिकः"):
          cur["pps"].append(ev)
        else:
          cur["mulas"].append(ev)

  specs: list[_ClusterSpec] = []
  for c_idx, cl in enumerate(clusters_raw):
    vp_body = cl["vp_body"]
    vp_file = cl["vp_file"]
    has_vp_sug = any(_is_accent_suggestion_pair(o, n) for o, n in _DEV_SUG_RE.findall(vp_body))
    if not has_vp_sug:
      continue

    pp_cands: list[tuple[str, str, str | None, int, bool, str]] = []
    mula_strs = [f"[{m['hdr']}] {m['body'].strip()}" for m in cl["mulas"][:3]]

    sib_tk = (
      _paired_static_sibling(vp_file, "vishvAsa-prastutiH", "sarvASh_TIkAH")
      if (cl["vp_inc_url"] and vp_file)
      else None
    )
    if sib_tk:
      if sib_tk not in static_pp_cache:
        static_pp_cache[sib_tk] = _extract_pp_blocks_from_file(sib_tk)
      s_pps, s_mula = static_pp_cache[sib_tk]
      if s_mula and not mula_strs:
        mula_strs = [s_mula]
      for sh, sb, s_idx in s_pps:
        pp_cands.append((sh, sb, sib_tk, s_idx, False, ""))

    if not pp_cands and cl["pps"]:
      seen_pp_srcs: set[str] = set()
      for pe in cl["pps"]:
        sf = pe["src_file"]
        if pe["inc_url"] and sf and os.path.isfile(sf) and sf != fp:
          if sf in seen_pp_srcs:
            continue
          seen_pp_srcs.add(sf)
          if sf not in static_pp_cache:
            static_pp_cache[sf] = _extract_pp_blocks_from_file(sf)
          s_pps, s_mula = static_pp_cache[sf]
          if s_mula and not mula_strs:
            mula_strs = [s_mula]
          for sh, sb, s_idx in s_pps:
            pp_cands.append((sh, sb, sf, s_idx, False, ""))
        else:
          pp_cands.append((pe["hdr"], pe["body"], sf, pe["pp_block_idx"], True, ""))
    elif not pp_cands and cl["vp_inc_url"] and vp_file and extra_vp_to_tk:
      for pf_cand in extra_vp_to_tk.get(os.path.normpath(vp_file), []):
        if pf_cand not in static_pp_cache:
          static_pp_cache[pf_cand] = _extract_pp_blocks_from_file(pf_cand)
        s_pps, s_mula = static_pp_cache[pf_cand]
        if s_mula and not mula_strs:
          mula_strs = [s_mula]
        for sh, sb, s_idx in s_pps:
          pp_cands.append((sh, sb, pf_cand, s_idx, False, ""))
        if pp_cands:
          break

    # Prefer matching śākhā block when shared file has multiple (Kāṇva vs Mādhyandina, Ekāgnikāṇḍa vs Kaṭha/RV/AV)
    ref_path = fp if "/kANvam/" in fp or "/ekAgnikANDam/" in fp else (vp_file or fp)
    if len(pp_cands) > 1:
      if "/kANvam/" in ref_path:
        k_cands = [c for c in pp_cands if "काण्व" in (reconciler.parse_padapatha_header(c[0])[0] or "")]
        if k_cands:
          pp_cands = k_cands
      elif "/ekAgnikANDam/" in ref_path:
        e_cands = [c for c in pp_cands if "एकाग्निकाण्ड" in (reconciler.parse_padapatha_header(c[0])[0] or "")]
        if e_cands:
          pp_cands = e_cands
      else:
        u_cands = [c for c in pp_cands if reconciler.parse_padapatha_header(c[0])[0] is None]
        if u_cands:
          pp_cands = u_cands

    sec_h = _nearest_heading(txt, cl["start"])
    mula_preview = "\n".join(mula_strs[:3])

    emitted_for_cl = False
    for ph, pb, pf, pidx, pis_inline, _ in pp_cands[:1]:
      shAkha, _, _ = reconciler.parse_padapatha_header(ph)
      emitted_for_cl = True
      specs.append(
        _ClusterSpec(
          section_heading=sec_h,
          cluster_idx=c_idx,
          vp_summary=cl["vp_hdr"],
          vp_raw_body=vp_body,
          vp_file=vp_file,
          vp_is_inline=(cl["vp_inc_url"] is None),
          pp_summary=ph,
          pp_body=pb,
          pp_file=pf,
          pp_block_idx=pidx,
          pp_is_inline=pis_inline,
          pp_shAkha_label=shAkha,
          mula_preview=mula_preview,
          host_files=[fp] if (cl["vp_inc_url"] is not None or not pis_inline) else [],
        )
      )

    if not emitted_for_cl:
      specs.append(
        _ClusterSpec(
          section_heading=sec_h,
          cluster_idx=c_idx,
          vp_summary=cl["vp_hdr"],
          vp_raw_body=vp_body,
          vp_file=vp_file,
          vp_is_inline=(cl["vp_inc_url"] is None),
          pp_summary="",
          pp_body="",
          pp_file=None,
          pp_block_idx=0,
          pp_is_inline=True,
          pp_shAkha_label=None,
          mula_preview=mula_preview,
          host_files=[fp] if cl["vp_inc_url"] is not None else [],
        )
      )
  return specs


def _build_host_include_index(
  abs_dir: str,
  hugo_base_dir: str,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
  """Index ``file -> host_files`` and cross-repo ``vp_file -> paired sarvASh_TIkAH files`` via ``js_include``s."""
  scan_roots: list[str] = [abs_dir]
  # Check matching sibling content tree when scanning static/
  norm_parts = list(pathlib.Path(abs_dir).parts)
  if "static" in norm_parts:
    st_idx = norm_parts.index("static")
    for layer in ("vishvAsa-prastutiH", "sarvASh_TIkAH"):
      if layer in norm_parts[st_idx:]:
        norm_parts = norm_parts[: norm_parts.index(layer, st_idx)]
        break
    content_parts = list(norm_parts)
    content_parts[st_idx] = "content"
    sib_content = os.path.join(*content_parts)
    if os.path.isdir(sib_content) and sib_content not in scan_roots:
      scan_roots.append(sib_content)

  file_to_hosts: dict[str, list[str]] = {}
  vp_to_paired_tk: dict[str, list[str]] = {}
  res_cache: dict[str, str | None] = {}
  seen_files: set[str] = set()

  def _add_host(tgt: str, host: str) -> None:
    lst = file_to_hosts.setdefault(tgt, [])
    if host not in lst:
      lst.append(host)

  for root in scan_roots:
    for hfp in sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True)):
      nhfp = os.path.normpath(hfp)
      if nhfp in seen_files or not os.path.isfile(nhfp):
        continue
      seen_files.add(nhfp)
      if os.path.basename(nhfp) in ("_index.md", "file_list.md"):
        continue
      txt = open(nhfp, encoding="utf-8", errors="ignore").read()
      if "js_include" not in txt or ("vishvAsa-prastutiH" not in txt and "sarvASh_TIkAH" not in txt):
        continue
      spans = sorted(_find_all_js_include_spans(txt), key=lambda t: (t[0], -(t[1] - t[0])))
      outer_h = _outer_heading_positions(txt)
      last_vp: str | None = None
      last_vp_pos = -1
      for s, _, u in spans:
        if u not in res_cache:
          t = include_seeker.resolve_include_file_path(u, hugo_base_dir, nhfp)
          res_cache[u] = os.path.normpath(t) if t and os.path.isfile(t) else None
        tgt = res_cache[u]
        if not tgt:
          continue
        _add_host(tgt, nhfp)
        if "/vishvAsa-prastutiH/" in u:
          last_vp = tgt
          last_vp_pos = s
        elif "/sarvASh_TIkAH/" in u and last_vp:
          if not any(last_vp_pos < hb < s for hb in outer_h):
            tks = vp_to_paired_tk.setdefault(last_vp, [])
            if tgt not in tks:
              tks.append(tgt)
  return file_to_hosts, vp_to_paired_tk


def scan_directory(dir_path: str) -> dict[str, Any]:
  """Scan ``dir_path`` recursively for ``विश्वास-प्रस्तुतिः`` accent fix suggestions and pair ``पद-पाठः``."""
  abs_dir = os.path.abspath(dir_path)
  if not os.path.isdir(abs_dir):
    raise FileNotFoundError(f"Directory not found: {dir_path}")

  hugo_base = infer_hugo_base_dir(abs_dir)
  file_to_hosts, vp_to_paired_tk = _build_host_include_index(abs_dir, hugo_base)
  md_files = sorted(glob.glob(os.path.join(abs_dir, "**", "*.md"), recursive=True))

  all_items: list[ReviewItem] = []
  seen_ids: dict[str, ReviewItem] = {}

  def _append_specs(specs: Sequence[_ClusterSpec], display_fp: str) -> None:
    for sp in specs:
      items = _align_cluster_to_items(sp, display_file=display_fp, base_dir=abs_dir, hugo_base_dir=hugo_base)
      for it in items:
        for ref_f in (it.vp_file, it.pp_file):
          if ref_f:
            for hf in file_to_hosts.get(os.path.normpath(ref_f), []):
              if hf not in it.host_files and hf != os.path.normpath(it.vp_file or "") and hf != os.path.normpath(it.pp_file or ""):
                it.host_files.append(hf)
        if it.item_id in seen_ids:
          prev = seen_ids[it.item_id]
          for hf in it.host_files:
            if hf not in prev.host_files and hf != os.path.normpath(prev.vp_file or "") and hf != os.path.normpath(prev.pp_file or ""):
              prev.host_files.append(hf)
          continue
        seen_ids[it.item_id] = it
        all_items.append(it)

  for fp in md_files:
    if not os.path.isfile(fp):
      continue
    base = os.path.basename(fp)
    if base in ("_index.md", "file_list.md"):
      continue

    if "/sarvASh_TIkAH/" in fp:
      sib_vp = _paired_static_sibling(fp, "sarvASh_TIkAH", "vishvAsa-prastutiH")
      if not sib_vp:
        continue
      vp_raw = open(sib_vp, encoding="utf-8", errors="ignore").read()
      if "[[" not in vp_raw:
        continue
      specs = _extract_clusters_from_static_sarvash(fp)
      _append_specs(specs, sib_vp)
    elif "/vishvAsa-prastutiH/" in fp:
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      if "[[" not in txt and "js_include" not in txt:
        continue
      if "js_include" in txt:
        inc_specs = _extract_clusters_from_content_or_mixed(
          fp,
          txt,
          hugo_base,
          extra_vp_to_tk=vp_to_paired_tk,
        )
        _append_specs(inc_specs, fp)

      vh, own_vb = _extract_static_vp_body(fp)
      has_own_sug = any(_is_accent_suggestion_pair(o, n) for o, n in _DEV_SUG_RE.findall(own_vb))
      if not has_own_sug:
        continue
      sib_pp = _paired_static_sibling(fp, "vishvAsa-prastutiH", "sarvASh_TIkAH")
      # Avoid duplicate work when paired sarvASh_TIkAH sibling is inside abs_dir
      if sib_pp and os.path.commonpath([abs_dir, os.path.abspath(sib_pp)]) == abs_dir:
        continue
      specs: list[_ClusterSpec] = []
      if sib_pp:
        specs = _extract_clusters_from_static_sarvash(sib_pp, vp_file_override=fp)
      else:
        for tk_fp in vp_to_paired_tk.get(os.path.normpath(fp), []):
          specs = _extract_clusters_from_static_sarvash(tk_fp, vp_file_override=fp)
          if specs:
            break
      if not specs:
        specs = [
          _ClusterSpec(
            section_heading="",
            cluster_idx=0,
            vp_summary=vh,
            vp_raw_body=own_vb,
            vp_file=fp,
            vp_is_inline=True,
            pp_summary="",
            pp_body="",
            pp_file=None,
            pp_block_idx=0,
            pp_is_inline=True,
            pp_shAkha_label=None,
            mula_preview="",
          )
        ]
      _append_specs(specs, fp)
    else:
      txt = open(fp, encoding="utf-8", errors="ignore").read()
      if "[[" not in txt and ("js_include" not in txt or "vishvAsa-prastutiH" not in txt):
        continue
      specs = _extract_clusters_from_content_or_mixed(fp, txt, hugo_base, extra_vp_to_tk=vp_to_paired_tk)
      _append_specs(specs, fp)

  # Collect git repo roots and batch git status across all referenced files
  git_cache: dict[str, str | None] = {}
  repo_roots: set[str] = set()
  dir_repo = find_git_root(abs_dir, git_cache)
  if dir_repo:
    repo_roots.add(dir_repo)
  for it in all_items:
    for rf in it.relevant_files:
      rr = find_git_root(rf, git_cache)
      if rr:
        repo_roots.add(rr)

  file_statuses: dict[str, str] = {}
  repo_staged: dict[str, list[str]] = {}
  for rr in sorted(repo_roots):
    smap, staged = get_git_status_map(rr)
    file_statuses.update(smap)
    repo_staged[rr] = staged

  return {
    "dir_path": abs_dir,
    "hugo_base_dir": hugo_base,
    "items": all_items,
    "file_statuses": file_statuses,
    "repo_roots": sorted(repo_roots),
    "repo_staged": repo_staged,
    "git_cache": git_cache,
  }


def _state_file_path(dir_path: str, cache_dir: str = DEFAULT_REVIEW_CACHE_DIR) -> str:
  os.makedirs(cache_dir, exist_ok=True)
  h = hashlib.sha1(os.path.abspath(dir_path).encode("utf-8")).hexdigest()[:16]
  return os.path.join(cache_dir, f"state_{h}.json")


def load_review_state(dir_path: str, cache_dir: str = DEFAULT_REVIEW_CACHE_DIR) -> dict[str, Any]:
  """Load persisted ``decisions`` and ``file_overrides`` for ``dir_path``."""
  p = _state_file_path(dir_path, cache_dir=cache_dir)
  if os.path.isfile(p):
    try:
      data = json.load(open(p, encoding="utf-8"))
      return {
        "decisions": dict(data.get("decisions", {})),
        "file_overrides": {k: bool(v) for k, v in data.get("file_overrides", {}).items()},
      }
    except Exception:
      pass
  return {"decisions": {}, "file_overrides": {}}


def save_review_state(dir_path: str, state: dict[str, Any], cache_dir: str = DEFAULT_REVIEW_CACHE_DIR) -> None:
  """Persist ``decisions`` and ``file_overrides`` for ``dir_path`` outside the git repo."""
  p = _state_file_path(dir_path, cache_dir=cache_dir)
  payload = {
    "dir_path": os.path.abspath(dir_path),
    "decisions": state.get("decisions", {}),
    "file_overrides": state.get("file_overrides", {}),
  }
  with open(p, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, ensure_ascii=False)


def _xy_label(xy: str) -> str:
  if not xy or xy == "clean":
    return "clean"
  if xy == "??":
    return "untracked"
  if "M" in xy or "R" in xy or "A" in xy:
    return "modified"
  return xy.strip() or "clean"


def _pair_sort_key(fp: str) -> tuple[str, int, str]:
  """Sort paired ``vishvAsa-prastutiH`` and ``sarvASh_TIkAH`` files adjacent to one another."""
  stem = fp.replace("/vishvAsa-prastutiH/", "/<PAIR>/").replace("/sarvASh_TIkAH/", "/<PAIR>/")
  rank = 0 if "/vishvAsa-prastutiH/" in fp else (1 if "/sarvASh_TIkAH/" in fp else 2)
  return (stem, rank, fp)


def compute_file_summaries(scan_data: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
  """Compute per-file review counts, git status, and commit marking across all relevant files."""
  items: list[ReviewItem] = scan_data["items"]
  decisions: dict[str, str] = state.get("decisions", {})
  overrides: dict[str, bool] = state.get("file_overrides", {})
  file_statuses: dict[str, str] = scan_data["file_statuses"]
  git_cache: dict[str, str | None] = scan_data["git_cache"]
  hugo_base: str | None = scan_data.get("hugo_base_dir")

  by_file: dict[str, dict[str, int]] = {}
  for it in items:
    dec = decisions.get(it.item_id, "pending")
    if dec not in _VALID_DECISIONS:
      dec = "pending"
    has_fb = bool(it.existing_feedback)
    fb_file: str | None = None
    if has_fb:
      if it.feedback_target == "pp" and it.pp_file:
        fb_file = os.path.normpath(it.pp_file)
      elif it.feedback_target == "vp" and it.vp_file:
        fb_file = os.path.normpath(it.vp_file)
      else:
        fb_file = os.path.normpath(it.pp_file or it.vp_file or it.display_file)
    for rf in it.relevant_files:
      c = by_file.setdefault(rf, {"accepted": 0, "rejected": 0, "pending": 0, "hold": 0, "with_feedback": 0, "total": 0})
      c["total"] += 1
      if dec == "accept":
        c["accepted"] += 1
      elif dec == "reject":
        c["rejected"] += 1
      elif dec == "hold":
        c["hold"] += 1
      elif not has_fb:
        c["pending"] += 1
      if has_fb and os.path.normpath(rf) == fb_file:
        c["with_feedback"] += 1

  out: list[dict[str, Any]] = []
  for rf in sorted(by_file, key=_pair_sort_key):
    counts = by_file[rf]
    xy = file_statuses.get(rf, "clean")
    dirty = xy != "clean"
    resolved = counts["accepted"] + counts["rejected"]
    auto_marked = dirty and resolved > 0 and counts["pending"] == 0 and counts["hold"] == 0 and counts["with_feedback"] == 0
    if rf in overrides:
      marked = dirty and bool(overrides[rf])
    else:
      marked = auto_marked
    repo_root = find_git_root(rf, git_cache)
    rel_to_repo = os.path.relpath(rf, repo_root) if repo_root else rf
    rel_display = vishvasa_rel_path(rf, hugo_base)
    out.append({
      "file_path": rf,
      "rel_display": rel_display,
      "repo_root": repo_root,
      "repo_name": os.path.basename(repo_root) if repo_root else "",
      "rel_to_repo": rel_to_repo,
      "git_xy": xy,
      "git_label": _xy_label(xy),
      "dirty": dirty,
      "counts": counts,
      "auto_marked": auto_marked,
      "marked": marked,
    })
  return out


def _sync_prefills_for_edited(
  edited_files: Sequence[str],
  item: ReviewItem,
  *,
  hugo_base_dir: str,
  scan_dir: str | None,
) -> list[str]:
  if not edited_files:
    return []
  roots = [
    r
    for r in (scan_dir, os.path.dirname(edited_files[0]), *(os.path.dirname(h) for h in item.host_files))
    if r and os.path.isdir(r)
  ]
  static_edited = [f for f in edited_files if "/static/" in f]
  if static_edited and roots:
    refreshed = include_transformer.surgical_prefill_transitive(
      list(dict.fromkeys(roots)),
      static_edited,
      hugo_base_dir=hugo_base_dir,
      only_if_prefilled=True,
      require_balanced_tags=True,
    )
    return sorted(refreshed)
  return []


def _find_non_include_occurrences(txt: str, needle: str) -> list[tuple[int, int]]:
  """Return ``[(start, end), ...]`` of ``needle`` in ``txt`` outside frontmatter and ``js_include`` spans."""
  if not needle:
    return []
  _, body_no_fm = _strip_frontmatter(txt)
  fm_end = len(txt) - len(body_no_fm)
  inc_spans = [(s, e) for s, e, _ in _find_all_js_include_spans(txt)]
  hits: list[tuple[int, int]] = []
  for m in re.finditer(re.escape(needle), txt):
    ms, me = m.start(), m.end()
    if ms < fm_end:
      continue
    if any(not (me <= is_ or ms >= ie_) for is_, ie_ in inc_spans):
      continue
    hits.append((ms, me))
  return hits


def _sync_sibling_vp_snapshots(
  sibling_items: Sequence[ReviewItem],
  item: ReviewItem,
  fp: str,
  old_body: str,
  new_body: str,
  edit_start: int,
  edit_end: int,
  delta: int,
  *,
  was_raw_sug: bool = False,
  will_be_raw_sug: bool = False,
  rescan_tokens: bool = False,
) -> None:
  """Update sibling items sharing the same VP file/block after an in-block edit."""
  for sib in sibling_items:
    if sib is item or os.path.normpath(sib.vp_file or sib.display_file) != os.path.normpath(fp):
      continue
    if sib.vp_raw_body != old_body:
      continue
    sib.vp_raw_body = new_body
    if rescan_tokens and (sib.vp_sug_old or sib.vp_sug_new):
      sib_tok = f"[[{sib.vp_sug_old}|{sib.vp_sug_new}]]"
      occs = [m for m in re.finditer(re.escape(sib_tok), new_body)]
      if occs and sib.vp_sug_occ_idx < len(occs):
        tm = occs[sib.vp_sug_occ_idx]
        sib.vp_highlight_ranges = [(tm.start(), tm.end())]
        continue
    shifted_ranges: list[tuple[int, int]] = []
    shifted_after = False
    for ss, se in sib.vp_highlight_ranges:
      if ss >= edit_end:
        shifted_ranges.append((ss + delta, se + delta))
        shifted_after = True
      else:
        shifted_ranges.append((ss, se))
    sib.vp_highlight_ranges = shifted_ranges
    if shifted_after and (sib.vp_sug_old, sib.vp_sug_new) == (item.vp_sug_old, item.vp_sug_new):
      if was_raw_sug and not will_be_raw_sug and sib.vp_sug_occ_idx > 0:
        sib.vp_sug_occ_idx -= 1
      elif not was_raw_sug and will_be_raw_sug:
        sib.vp_sug_occ_idx += 1


def apply_vp_decision_for_item(
  item: ReviewItem,
  action: str,
  *,
  sibling_items: Sequence[ReviewItem] = (),
  sync_prefills: bool = True,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  scan_dir: str | None = None,
) -> dict[str, Any]:
  """Apply ``accept`` / ``reject`` / ``pending`` ONLY to the ``विश्वास-प्रस्तुतिः`` block/file.

  ``accept`` replaces ``[[OLD|NEW]]`` -> ``NEW``; ``reject`` replaces ``[[OLD|NEW]]`` -> ``OLD``;
  ``pending`` restores ``[[OLD|NEW]]``. Never alters ``पद-पाठः`` or ``sarvASh_TIkAH``.
  """
  if action not in ("accept", "reject", "pending"):
    raise ValueError(f"Unsupported VP decision action: {action!r}")
  fp = item.vp_file or item.display_file
  if not fp or not os.path.isfile(fp):
    raise FileNotFoundError(f"Target विश्वास-प्रस्तुतिः file not found: {fp}")
  if not item.vp_highlight_ranges:
    raise ValueError(f"Missing VP highlight range for item {item.item_id}")

  s, e = item.vp_highlight_ranges[0]
  old_body = item.vp_raw_body
  if not (0 <= s <= e <= len(old_body)):
    raise ValueError(f"Invalid VP range {(s, e)} for body length {len(old_body)}")

  if action == "accept":
    rep = item.vp_sug_new
  elif action == "reject":
    rep = item.vp_sug_old
  else:
    rep = f"[[{item.vp_sug_old}|{item.vp_sug_new}]]"

  new_body = old_body[:s] + rep + old_body[e:]
  if new_body == old_body:
    return {
      "edited_files": [],
      "refreshed_hosts": [],
      "vp_raw_body": item.vp_raw_body,
      "vp_highlight_ranges": item.vp_highlight_ranges,
    }

  txt = open(fp, encoding="utf-8").read()
  new_txt: str | None = None
  fallback_used = False
  if "/vishvAsa-prastutiH/" in fp:
    if old_body in txt:
      new_txt = txt.replace(old_body, new_body, 1)
    else:
      stripped_old = old_body.strip()
      stripped_new = new_body.strip()
      if stripped_old and stripped_old in txt:
        new_txt = txt.replace(stripped_old, stripped_new, 1)
      else:
        old_tok = old_body[s:e]
        occ_idx = item.vp_sug_occ_idx if old_tok == f"[[{item.vp_sug_old}|{item.vp_sug_new}]]" else 0
        occ_list = _find_non_include_occurrences(txt, old_tok)
        if occ_idx < len(occ_list):
          ts, te = occ_list[occ_idx]
          new_txt = txt[:ts] + rep + txt[te:]
          fallback_used = True
  else:
    for vm in reconciler.LEAF_DETAILS_RE.finditer(txt):
      if not vm.group(1).strip().startswith("विश्वास-प्रस्तुतिः"):
        continue
      vb_raw = vm.group(2)
      vb_cmp = vb_raw.strip("\n")
      if vb_cmp == old_body or _strip_feedback_for_compare(vb_cmp) == _strip_feedback_for_compare(old_body):
        open_end = vm.group(0).find("</summary>") + len("</summary>")
        close_start = vm.group(0).rfind("</details>")
        if old_body in vb_raw:
          new_vb = vb_raw.replace(old_body, new_body, 1)
        else:
          old_tok = old_body[s:e]
          occ_idx = item.vp_sug_occ_idx if old_tok == f"[[{item.vp_sug_old}|{item.vp_sug_new}]]" else 0
          occ_list = [m for m in re.finditer(re.escape(old_tok), vb_raw)]
          if occ_idx >= len(occ_list):
            raise ValueError(
              f"Could not locate {old_tok!r} in विश्वास-प्रस्तुतिः block of {fp} (file changed on disk — press Ctrl+R to rescan)"
            )
          tm = occ_list[occ_idx]
          new_vb = vb_raw[: tm.start()] + rep + vb_raw[tm.end() :]
          fallback_used = True
        new_block = vm.group(0)[:open_end] + new_vb + vm.group(0)[close_start:]
        new_txt = txt[: vm.start()] + new_block + txt[vm.end() :]
        break

  if new_txt is None:
    raise ValueError(
      f"Could not locate target विश्वास-प्रस्तुतिः block in {fp} (file changed on disk since last scan — press Ctrl+R to rescan)"
    )
  if new_txt.count("<details") != txt.count("<details") or new_txt.count("</details>") != txt.count("</details>"):
    raise RuntimeError(f"Refused edit that would unbalance <details> in {fp}")

  with open(fp, "w", encoding="utf-8") as fh:
    fh.write(new_txt)

  # Keep in-memory snapshots & sibling offsets aligned within the same VP body
  delta = len(rep) - (e - s)
  was_raw_sug = old_body[s:e] == f"[[{item.vp_sug_old}|{item.vp_sug_new}]]"
  will_be_raw_sug = rep == f"[[{item.vp_sug_old}|{item.vp_sug_new}]]"

  if fallback_used and "/vishvAsa-prastutiH/" in fp:
    _, new_body = _extract_static_vp_body_text(new_txt)
    occ_idx_new = item.vp_sug_occ_idx if will_be_raw_sug else 0
    occ_new = [m for m in re.finditer(re.escape(rep), new_body)]
    if occ_idx_new < len(occ_new):
      item.vp_highlight_ranges = [(occ_new[occ_idx_new].start(), occ_new[occ_idx_new].end())]
    else:
      item.vp_highlight_ranges = [(s, s + len(rep))]
  else:
    item.vp_highlight_ranges = [(s, s + len(rep))]
  item.vp_raw_body = new_body

  _sync_sibling_vp_snapshots(
    sibling_items,
    item,
    fp,
    old_body,
    new_body,
    s,
    e,
    delta,
    was_raw_sug=was_raw_sug,
    will_be_raw_sug=will_be_raw_sug,
    rescan_tokens=fallback_used,
  )

  edited_files = [fp]
  refreshed_hosts = (
    _sync_prefills_for_edited(edited_files, item, hugo_base_dir=hugo_base_dir, scan_dir=scan_dir)
    if sync_prefills
    else []
  )
  return {
    "edited_files": edited_files,
    "refreshed_hosts": refreshed_hosts,
    "vp_raw_body": item.vp_raw_body,
    "vp_highlight_ranges": item.vp_highlight_ranges,
  }


def insert_feedback_for_item(
  item: ReviewItem,
  feedback_text: str,
  *,
  target_mode: str = "auto",
  sibling_items: Sequence[ReviewItem] = (),
  sync_prefills: bool = True,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  scan_dir: str | None = None,
) -> dict[str, Any]:
  """Insert, update, or clear a ``+++(FEEDBACK!!)+++`` comment on the target padapāṭha line or VP span."""
  comment = format_feedback_comment(feedback_text)
  mode = target_mode
  if mode == "auto":
    mode = "pp" if (item.pp_file and item.pp_line_core and item.pp_item_idx is not None) else "vp"

  edited_files: list[str] = []
  updated_line = item.pp_line_core

  if mode in ("pp", "both") and item.pp_file and item.pp_line_core and item.pp_item_idx is not None:
    fp = item.pp_file
    txt = open(fp, encoding="utf-8").read()
    pp_matches = [
      m
      for m in reconciler.LEAF_DETAILS_RE.finditer(txt)
      if m.group(1).strip().startswith("पद-पाठः (यान्त्रिकः")
    ]
    if not (0 <= item.pp_block_idx < len(pp_matches)):
      raise ValueError(f"Could not locate पद-पाठः block #{item.pp_block_idx} in {fp}")
    pm = pp_matches[item.pp_block_idx]
    block_full = pm.group(0)
    open_end = block_full.find("</summary>") + len("</summary>")
    close_start = block_full.rfind("</details>")
    body = block_full[open_end:close_start]

    body_lines = body.splitlines(keepends=True)
    bullet_pos_list = [idx for idx, ln in enumerate(body_lines) if ln.startswith("- ")]
    if not (0 <= item.pp_item_idx < len(bullet_pos_list)):
      raise ValueError(f"Could not locate bullet #{item.pp_item_idx} in {fp}")
    b_idx = bullet_pos_list[item.pp_item_idx]
    orig_ln = body_lines[b_idx]
    nl = "\n" if orig_ln.endswith("\n") else ""
    raw_core = orig_ln[:-1] if nl else orig_ln
    clean_core, _ = reconciler.split_padapatha_line_comment(raw_core)
    if clean_core != item.pp_line_core:
      raise ValueError(f"Line mismatch in {fp}: expected {item.pp_line_core!r}, found {clean_core!r}")
    new_raw = f"{clean_core} {comment}" if comment else clean_core
    body_lines[b_idx] = new_raw + nl
    updated_line = new_raw

    new_block = block_full[:open_end] + "".join(body_lines) + block_full[close_start:]
    new_txt = txt[: pm.start()] + new_block + txt[pm.end() :]
    if new_txt.count("<details") != txt.count("<details") or new_txt.count("</details>") != txt.count("</details>"):
      raise RuntimeError(f"Refused edit that would unbalance <details> in {fp}")
    with open(fp, "w", encoding="utf-8") as fh:
      fh.write(new_txt)
    edited_files.append(fp)

    # Refresh in-memory padapāṭha line snapshot
    if item.pp_target_idx is not None and 0 <= item.pp_target_idx < len(item.pp_lines):
      item.pp_lines[item.pp_target_idx] = new_raw

  if mode in ("vp", "both") and item.vp_file:
    fp = item.vp_file
    txt = open(fp, encoding="utf-8").read()
    new_txt: str | None = None

    target_m: tuple[int, int] | None = None
    if item.vp_highlight_ranges and item.vp_raw_body:
      shl, ehl = item.vp_highlight_ranges[0]
      if 0 <= shl <= ehl <= len(item.vp_raw_body) and item.vp_raw_body in txt:
        base_pos = txt.index(item.vp_raw_body)
        target_m = (base_pos + shl, base_pos + ehl)

    # Locate the matching [[OLD|NEW]] occurrence when exact raw_body substring wasn't found directly
    if target_m is None and (item.vp_sug_old or item.vp_sug_new):
      token = f"[[{item.vp_sug_old}|{item.vp_sug_new}]]"
      occurrences = [m for m in re.finditer(re.escape(token), txt)]
      if occurrences:
        if "/vishvAsa-prastutiH/" in fp:
          if item.vp_sug_occ_idx < len(occurrences):
            m_occ = occurrences[item.vp_sug_occ_idx]
            target_m = (m_occ.start(), m_occ.end())
        else:
          vp_blocks = [
            m
            for m in reconciler.LEAF_DETAILS_RE.finditer(txt)
            if m.group(1).strip().startswith("विश्वास-प्रस्तुतिः")
          ]
          for vm in vp_blocks:
            vb_inner = vm.group(2)
            inner_occ = [m for m in re.finditer(re.escape(token), vb_inner)]
            if item.vp_sug_occ_idx < len(inner_occ) and (
              _strip_feedback_for_compare(vb_inner.strip("\n")) == _strip_feedback_for_compare(item.vp_raw_body)
              or item.vp_raw_body[:40] in vb_inner
            ):
              m_rel = inner_occ[item.vp_sug_occ_idx]
              open_end = vm.group(0).find("</summary>") + len("</summary>")
              target_m = (vm.start() + open_end + m_rel.start(), vm.start() + open_end + m_rel.end())
              break

    if target_m is not None:
      _, e_tok = target_m
      if txt[e_tok : e_tok + 2] == "**":
        e_tok += 2
      after = txt[e_tok : min(len(txt), e_tok + 200)]
      m_ex = re.match(r"^[ \t]*\+\+\+[^\n+]*?!![^\n+]*?\+\+\+", after)
      if m_ex:
        if comment:
          new_txt = txt[:e_tok] + comment + txt[e_tok + m_ex.end() :]
        else:
          new_txt = txt[:e_tok] + txt[e_tok + m_ex.end() :]
      elif comment:
        new_txt = txt[:e_tok] + comment + txt[e_tok:]
      else:
        new_txt = txt

    if new_txt is None:
      # Fallback: append comment at end of the matched VP block body
      if "/vishvAsa-prastutiH/" in fp:
        base_body = txt.rstrip()
        core_vp, _ = reconciler.split_padapatha_line_comment(base_body)
        new_txt = f"{core_vp} {comment}\n" if comment else f"{core_vp}\n"
      else:
        vp_blocks = [
          m
          for m in reconciler.LEAF_DETAILS_RE.finditer(txt)
          if m.group(1).strip().startswith("विश्वास-प्रस्तुतिः")
        ]
        for vm in vp_blocks:
          vb_inner = vm.group(2)
          if _strip_feedback_for_compare(vb_inner.strip("\n")) == _strip_feedback_for_compare(item.vp_raw_body):
            open_end = vm.group(0).find("</summary>") + len("</summary>")
            close_start = vm.group(0).rfind("</details>")
            vb_core, _ = reconciler.split_padapatha_line_comment(vb_inner.rstrip("\n"))
            new_vb = f"{vb_core} {comment}\n" if comment else f"{vb_core}\n"
            new_block = vm.group(0)[:open_end] + new_vb + vm.group(0)[close_start:]
            new_txt = txt[: vm.start()] + new_block + txt[vm.end() :]
            break

    if new_txt is None:
      raise ValueError(f"Could not locate target विश्वास-प्रस्तुतिः span in {fp}")
    if new_txt.count("<details") != txt.count("<details") or new_txt.count("</details>") != txt.count("</details>"):
      raise RuntimeError(f"Refused edit that would unbalance <details> in {fp}")
    if new_txt != txt:
      with open(fp, "w", encoding="utf-8") as fh:
        fh.write(new_txt)
      if fp not in edited_files:
        edited_files.append(fp)

    # Refresh in-memory VP body snapshot (and any sibling suggestions in the same block)
    old_vp_snap = item.vp_raw_body
    if "/vishvAsa-prastutiH/" in fp:
      _, new_vp_snap = _extract_static_vp_body_text(new_txt)
      item.vp_raw_body = new_vp_snap
      _sync_sibling_vp_snapshots(
        sibling_items,
        item,
        fp,
        old_vp_snap,
        new_vp_snap,
        0,
        0,
        len(new_vp_snap) - len(old_vp_snap),
        rescan_tokens=True,
      )
    else:
      for vm in reconciler.LEAF_DETAILS_RE.finditer(new_txt):
        if vm.group(1).strip().startswith("विश्वास-प्रस्तुतिः"):
          vb_inner = vm.group(2).strip("\n")
          if _strip_feedback_for_compare(vb_inner) == _strip_feedback_for_compare(old_vp_snap):
            item.vp_raw_body = vb_inner
            _sync_sibling_vp_snapshots(
              sibling_items,
              item,
              fp,
              old_vp_snap,
              vb_inner,
              0,
              0,
              len(vb_inner) - len(old_vp_snap),
              rescan_tokens=True,
            )
            break

  refreshed_hosts = (
    _sync_prefills_for_edited(edited_files, item, hugo_base_dir=hugo_base_dir, scan_dir=scan_dir)
    if (sync_prefills and edited_files)
    else []
  )

  item.existing_feedback = extract_feedback_inner(comment) if comment else ""
  if not comment:
    item.feedback_target = ""
  elif mode in ("pp", "both"):
    item.feedback_target = "pp"
  elif mode == "vp":
    item.feedback_target = "vp"

  return {
    "edited_files": edited_files,
    "refreshed_hosts": refreshed_hosts,
    "comment": comment,
    "existing_feedback": item.existing_feedback,
    "pp_target_line": updated_line,
  }


def submit_review_item(
  item: ReviewItem,
  *,
  decision: str,
  feedback_text: str = "",
  sibling_items: Sequence[ReviewItem] = (),
  target_mode: str = "auto",
  sync_prefills: bool = True,
  hugo_base_dir: str = "/home/vvasuki/gitland/vishvAsa",
  scan_dir: str | None = None,
) -> dict[str, Any]:
  """Persist radio choice (``accept`` / ``reject`` / ``pending``) and/or ``+++(FEEDBACK!!)+++`` to files.

  ``accept`` / ``reject`` only alter the ``विश्वास-प्रस्तुतिः`` block/file; non-empty feedback is inserted at
  the end of the corresponding ``पद-पाठः`` line (or ``विश्वास-प्रस्तुतिः`` when unpaired).
  """
  if decision not in ("pending", "accept", "reject"):
    raise ValueError(f"Unsupported review decision: {decision!r}")

  edited_files: list[str] = []
  refreshed_hosts: list[str] = []

  vp_res = apply_vp_decision_for_item(
    item,
    decision,
    sibling_items=sibling_items,
    sync_prefills=sync_prefills,
    hugo_base_dir=hugo_base_dir,
    scan_dir=scan_dir,
  )
  edited_files.extend(vp_res["edited_files"])
  refreshed_hosts.extend(vp_res["refreshed_hosts"])

  fb_comment = format_feedback_comment(feedback_text)
  fb_res: dict[str, Any] = {
    "comment": format_feedback_comment(item.existing_feedback),
    "existing_feedback": item.existing_feedback,
    "pp_target_line": item.pp_lines[item.pp_target_idx] if (item.pp_target_idx is not None and 0 <= item.pp_target_idx < len(item.pp_lines)) else item.pp_line_core,
  }
  if fb_comment or item.existing_feedback:
    fb_res = insert_feedback_for_item(
      item,
      feedback_text,
      target_mode=target_mode,
      sibling_items=sibling_items,
      sync_prefills=sync_prefills,
      hugo_base_dir=hugo_base_dir,
      scan_dir=scan_dir,
    )
    for ef in fb_res["edited_files"]:
      if ef not in edited_files:
        edited_files.append(ef)
    for rh in fb_res["refreshed_hosts"]:
      if rh not in refreshed_hosts:
        refreshed_hosts.append(rh)

  return {
    "edited_files": edited_files,
    "refreshed_hosts": refreshed_hosts,
    "decision": decision,
    "vp_raw_body": item.vp_raw_body,
    "vp_highlight_ranges": item.vp_highlight_ranges,
    "comment": fb_res["comment"],
    "existing_feedback": item.existing_feedback,
    "pp_target_line": fb_res["pp_target_line"],
  }


def _strip_feedback_for_compare(s: str) -> str:
  return re.sub(r"\s*\+\+\+[^\n+]*?!![^\n+]*?\+\+\+", "", s).strip()


def commit_marked_files(
  file_paths: Sequence[str],
  commit_message: str,
) -> list[dict[str, Any]]:
  """Safely stage (untracked only if needed) and ``git commit --only`` marked files per enclosing git repository."""
  msg = commit_message.strip() or "Review accepted accent fix suggestions"
  git_cache: dict[str, str | None] = {}
  by_repo: dict[str, list[str]] = {}
  for fp in file_paths:
    abs_f = os.path.normpath(os.path.abspath(fp))
    rr = find_git_root(abs_f, git_cache)
    if not rr:
      raise ValueError(f"File is not inside a git repository: {fp}")
    by_repo.setdefault(rr, []).append(os.path.relpath(abs_f, rr))

  results: list[dict[str, Any]] = []
  for repo_root, rels in sorted(by_repo.items()):
    unique_rels = list(dict.fromkeys(rels))
    st_map, pre_staged = get_git_status_map(repo_root)
    dirty_rels = []
    untracked_rels = []
    for rel in unique_rels:
      abs_f = os.path.normpath(os.path.join(repo_root, rel))
      xy = st_map.get(abs_f, "clean")
      if xy == "clean":
        continue
      dirty_rels.append(rel)
      if xy == "??":
        untracked_rels.append(rel)

    if not dirty_rels:
      results.append({
        "repo_root": repo_root,
        "committed": [],
        "sha": None,
        "note": "No uncommitted changes among selected files.",
      })
      continue

    if untracked_rels:
      # Use `--intent-to-add` (`git add -N`) when unrelated pre-staged files exist so `git commit --only` keeps them untouched.
      flag = ["-N", "--"] if pre_staged else ["--"]
      for i in range(0, len(untracked_rels), 200):
        subprocess.check_call(["git", "-C", repo_root, "add", *flag, *untracked_rels[i : i + 200]])

    pathspec_file = os.path.join(repo_root, ".git", "accent_review_commit_paths.txt")
    with open(pathspec_file, "w", encoding="utf-8") as fh:
      fh.write("\n".join(dirty_rels) + "\n")
    try:
      out = subprocess.check_output(
        ["git", "-C", repo_root, "commit", "--only", f"--pathspec-from-file={pathspec_file}", "-m", msg],
        stderr=subprocess.STDOUT,
        text=True,
      )
    finally:
      if os.path.exists(pathspec_file):
        os.remove(pathspec_file)

    sha = subprocess.check_output(["git", "-C", repo_root, "rev-parse", "--short", "HEAD"], text=True).strip()
    results.append({
      "repo_root": repo_root,
      "committed": dirty_rels,
      "sha": sha,
      "output": out.strip(),
      "preserved_pre_staged": len(pre_staged),
    })
  return results


def get_file_diff(file_path: str) -> str:
  """Return unified ``git diff`` (or untracked content preview) for one file."""
  abs_f = os.path.normpath(os.path.abspath(file_path))
  rr = find_git_root(abs_f)
  if not rr:
    return "(not in a git repository)"
  rel = os.path.relpath(abs_f, rr)
  st = subprocess.check_output(["git", "-C", rr, "status", "--porcelain", "-uall", "--", rel], text=True)
  if st.startswith("?? "):
    txt = open(abs_f, encoding="utf-8", errors="replace").read()
    return f"=== NEW UNTRACKED FILE: {rel} ===\n" + txt[:8000]
  diff = subprocess.check_output(["git", "-C", rr, "diff", "HEAD", "--", rel], text=True)
  return diff or "(no diff vs HEAD)"
