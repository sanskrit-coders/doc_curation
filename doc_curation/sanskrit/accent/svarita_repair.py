"""Detect and repair spurious GRETIL / split-pāda initial svarita ``᳙`` leaks in US-accented Vedic corpora."""
from __future__ import annotations

import os
import pathlib
import re
from collections.abc import Sequence

from doc_curation.md.content_processor.include.transformer import surgical_prefill_transitive
from doc_curation.sanskrit.accent.us_converter import split_frontmatter_verbatim

US_UDATTA = "\u1cd3"
US_SVARITA = "\u1cd9"

_JS_INCLUDE_BLOCK_RE = re.compile(
  r'<div\s+class="js_include"[^>]*>.*?</div>(?:\s*</div>)*',
  re.DOTALL,
)
_SYL_1_SVARITA_RE = re.compile(r"^((?:[क-ह]्)*[अ-औक-ह][ा-ौःंँ]*)\u1cd9")
_DEV_SYL_RE = re.compile(
  r"(?:[क-ह]्)*[अ-औक-ह][ा-ौःंँ]*(?:[क-ह]्(?![अ-औक-ह]))?[\u0951\u0952\u1cd3\u1cd9\u1ce1]*"
)
_MATRA_MARK_RE = re.compile(r"[\u0951\u0952\u1cd3\u1cd9\u1ce1\u0901\u0902\u0903\u093e-\u094d]")
_ABHINIHITA_PREFIX_RE = re.compile(r"^(?:[क-ह]्)*[अ-औक-ह][ेो][ःंँ]*\u1cd9")
_CLASSICAL_MARKS_RE = re.compile(r"[\u0951\u0952\u1ce1१३]")


def _bare_no_marks(text: str) -> str:
  return re.sub(r"[\u0951-\u0957\u1cd0-\u1cff]", "", text)


def _norm_match_key(text: str) -> str:
  s = _bare_no_marks(text).replace("ऽ", "")
  return re.sub(r"[ंँ](?=[क-ह]|$)", "म्", s)


def _extract_details_body(text: str, summary_prefix: str) -> str:
  for m in re.finditer(r"<details(?:\s+open)?><summary>([^<]*)</summary>(.*?)</details>", text, re.DOTALL):
    if m.group(1).strip().startswith(summary_prefix):
      return m.group(2).strip()
  return ""


def _split_padapatha_words(pp_text: str) -> list[str]:
  """Split classical Devanagari padapāṭha (with ``।`` and ``इति``) into content padas."""
  if not pp_text:
    return []
  raw = re.split(r"[।॥\s]+", pp_text.strip())
  words: list[str] = []
  for tok in raw:
    clean_b = _bare_no_marks(tok).strip("ऽ")
    if not clean_b or clean_b == "इति" or re.fullmatch(r"[०-९0-9.]+", clean_b):
      continue
    words.append(tok)
  return words


def _classical_pada_syllables_udatta(pp_word: str) -> list[int]:
  """Return 0-based udātta syllable indices derived from dependent-svarita marks on a ``पदपाठः`` word."""
  # In Classical Vedavigraha padapāṭha:
  # - `᳡` directly marks independent/kampa svarita (preserve syllable index as svarita, not udātta here)
  # - In a contiguous run `... S1 S2(॑) ...`: dependent `॑` falls on the syllable AFTER udātta `S1`,
  #   unless syllable 0 itself carries `॑` (initial svarita/or Roth-Whitney `S1॑` ambiguity).
  syls = _DEV_SYL_RE.findall(pp_word.replace("ऽ", ""))
  if not syls:
    return []
  udatta_idxs: list[int] = []
  for idx, sy in enumerate(syls):
    if "\u0951" in sy:
      if idx == 0:
        # In AV/VS Padapāṭha, `॑` on syllable 0 means syllable 0 itself if `idx==0` AND not followed by `॒`
        # Wait: in classical AV PP, `अद॑ब्धः` puts `॑` on syl 1 (`द॑` -> udātta on syl 0 `अ`!).
        # When syl 0 carries `॑`, wait: `सूर्य॑` puts `॑` on `र्य॑` (syl 1 -> udātta syl 0!).
        # Syllable 0 carrying `॑` without preceding vowel occurs on monosyllables (`शम्`? no, `शम्।`).
        if len(syls) == 1 or "\u0952" not in syls[1]:
          udatta_idxs.append(0)
      else:
        udatta_idxs.append(idx - 1)
  if not udatta_idxs and len(syls) == 1 and "\u0952" not in syls[0] and "\u1ce1" not in syls[0]:
    # In AV Padapāṭha monosyllables (e.g. `शम्।`, `ताः।`) unmarked udātta has neither `॑` nor `॒`,
    # whereas anudātta monosyllables (`उ।`? No, `च॒`, `नः॒`, `मे॒`, `ते॒`) carry `॒`.
    udatta_idxs.append(0)
  return udatta_idxs


def _strip_syl1_svarita(word: str) -> str:
  return _SYL_1_SVARITA_RE.sub(r"\1", word, count=1)


def _set_udatta_on_syllable(word: str, target_idx: int) -> str:
  """Place ``᳓`` on 0-based Devanagari syllable index ``target_idx`` cleanly (stripping any syl-0 ``᳙``)."""
  clean = _strip_syl1_svarita(word)
  for idx, m in enumerate(_DEV_SYL_RE.finditer(clean)):
    if idx == target_idx:
      seg = m.group(0).replace(US_SVARITA, "").replace(US_UDATTA, "")
      coda_m = re.search(r"(?:[क-ह]्(?![अ-औक-ह]))+$", seg)
      if coda_m:
        head, tail = seg[: coda_m.start()], seg[coda_m.start() :]
        seg = head + US_UDATTA + tail
      else:
        seg = seg + US_UDATTA
      return clean[: m.start()] + seg + clean[m.end() :]
  return clean


def _find_matching_pp_slice(w_bare: str, pp_words: Sequence[str], start_search: int = 0) -> tuple[int, list[str]]:
  """Find slice of ``pp_words`` near ``start_search`` matching the start of ``w_bare``."""
  if not pp_words or not w_bare:
    return start_search, []
  w_n = _norm_match_key(w_bare)

  def _matches(pw: str, min_len: int = 2) -> bool:
    pw_n = _norm_match_key(pw)
    if not pw_n:
      return False
    # `तैः` (`तैरेनं`), `उ`/`ऊं`, exact monosyllables
    if w_n == "उ" and pw_n == "ऊम्":
      return True
    if pw_n == "न" and w_n.startswith(("नै", "ना", "ने", "नो")):
      return True
    if pw_n in ("तैः", "शम्") and w_n.startswith(pw_n[:-1]):
      return True
    pref_len = min(min_len, len(pw_n), len(w_n))
    return pref_len >= 2 and (w_n.startswith(pw_n[:pref_len]) or pw_n.startswith(w_n[:pref_len]))

  for idx in range(start_search, min(len(pp_words), start_search + 10)):
    if _matches(pp_words[idx], 3):
      return idx + 1, list(pp_words[idx : idx + 2])
  for idx in range(start_search, min(len(pp_words), start_search + 10)):
    if _matches(pp_words[idx], 2):
      return idx + 1, list(pp_words[idx : idx + 2])
  for idx, pw in enumerate(pp_words):
    if _matches(pw, 4):
      return idx + 1, list(pp_words[idx : idx + 2])
  for idx, pw in enumerate(pp_words):
    if _matches(pw, 2):
      return idx + 1, list(pp_words[idx : idx + 2])
  return start_search, []


def _word_has_genuine_kampa_or_abhinihita(
  w: str,
  next_w: str,
  mula_text: str,
  pp_slice: Sequence[str],
  prev_w: str = "",
) -> bool:
  """Return ``True`` if syllable-1 ``᳙`` on ``w`` is a genuine abhinihita, kampa, or kṣaipra/jātya svarita."""
  # 0. Preceding word ending in yaṇ-sandhi half-consonant `[यव]्` (e.g. `पतयिष्ण्व् अ᳙र्वन्त᳓व`)
  if prev_w and re.search(r"[यव]्$", _bare_no_marks(prev_w)):
    return True
  # 1. Abhinihita `ऽ` in first 2 syllables or immediately after `w`
  if _ABHINIHITA_PREFIX_RE.match(w) and ("ऽ" in w[:10] or (next_w and next_w.startswith("ऽ"))):
    return True
  # 2. Kampa (`᳡`, `१`, `३`) matching word prefix in `मूलम्` or `पदपाठः`
  w_b = _bare_no_marks(w)
  stem = w_b[: min(4, len(w_b))]
  if stem:
    if any(re.search(rf"{re.escape(stem[:3])}[^\s।॥]*[\u1ce1१३]", m_src) for m_src in (mula_text,) if m_src):
      return True
    if pp_slice and any("\u1ce1" in p for p in pp_slice[:1]):
      if pp_slice[0].startswith(stem[:2]) and "\u1ce1" in pp_slice[0]:
        return True
  # 3. Genuine kṣaipra/jātya (`[क-ह]्[यव]` in syl 1 where `पदपाठः` does NOT mark syllable 1 anudātta `॒`)
  if re.match(r"^[क-ह]+्[यव]", w):
    if w_b.startswith(("स्विष्ट", "व्युष्ट्यै")):
      return True
    if pp_slice:
      p0 = pp_slice[0]
      p0_syls = _DEV_SYL_RE.findall(p0.replace("ऽ", ""))
      p0_b = _bare_no_marks(p0).replace("ऽ", "")
      if p0_syls and "\u0952" not in p0_syls[0]:
        if p0_b in ("वि", "नि", "नु", "सु", "स्वः", "क्व", "व्युष्ट्यै", "स्विष्टः", "स्विष्ट") or "\u0951" in p0 or "\u1ce1" in p0:
          return True
      if len(pp_slice) >= 2 and "ऽ" in p0 and p0_b.startswith("द्वि") and "\u0951" in p0:
        return True
    elif re.match(r"^(?:व्य|व्या|व्यु|व्यो|व्यृ|न्य|न्या|न्यू|न्वे|स्वर्|स्वि)", w_b):
      return True
  # Check hyphenated compounds (`महत्य्-अ᳙र्णवे`) where `[यव]्-` precedes `᳙`
  if re.search(r"[यव]्-", w):
    return True
  return False


def _fix_single_accent_clause_init_token(
  w: str,
  next_w: str,
  mula_text: str,
  pp_slice: Sequence[str],
  *,
  prev_w: str = "",
  vocative_syl1_words: frozenset[str] = frozenset({"ज्याके", "अग्ने", "इन्द्र", "सीदता", "द्यौः", "द्यौर्"}),
) -> str:
  """Repair a clause-initial word having ONLY syllable-1 ``᳙``, using ``पदपाठः`` and ``मूलम्``."""
  if _word_has_genuine_kampa_or_abhinihita(w, next_w, mula_text, pp_slice, prev_w=prev_w):
    return w
  w_b = _bare_no_marks(w)
  if w_b in vocative_syl1_words or re.match(r"^द्यौर्", w_b):
    return _set_udatta_on_syllable(w, 0)
  if not pp_slice:
    return w

  p0 = pp_slice[0]
  # Guard genuine `jātya` when syllable 0 of `PP` ITSELF is `्[यव]` carrying `॑`/`᳡`,
  # or known monosyllabic/disyllabic jātya stems (`कन्या`, `पथ्या`, `तन्व`, `अस्व`, `आस्ये`).
  if "\u0951" in p0 or "\u1ce1" in p0:
    p0_syls = _DEV_SYL_RE.findall(p0.replace("ऽ", ""))
    if p0_syls and ("\u0951" in p0_syls[0] or "\u1ce1" in p0_syls[0]) and re.search(r"्[यव]", _bare_no_marks(p0_syls[0])):
      if not re.match(r"^ज्या", w_b):
        return w
    if (
      w_b.startswith(("कन्या", "पथ्या", "तन्व", "अस्व", "आस्ये"))
      and len(p0_syls) >= 2
      and "\u0951" in p0_syls[-1]
      and re.search(r"्[यव]", _bare_no_marks(p0_syls[-1]))
    ):
      return w

  # In AV 11/3/37-38 (`तै᳙रेनं प्रा᳓शिषं`), PP `तैः।` omits `॒` even though `तैः` is unaccented.
  if w_b.startswith("तैरेनं"):
    return _strip_syl1_svarita(w)

  ud_idxs = _classical_pada_syllables_udatta(p0)
  if ud_idxs:
    target_idx = ud_idxs[0]
    if target_idx == 0:
      return _set_udatta_on_syllable(w, 0)
    w_syls = _DEV_SYL_RE.findall(w)
    if target_idx < len(w_syls):
      return _set_udatta_on_syllable(w, target_idx)

  if "\u0952" in p0 or _norm_match_key(p0) in ("उ", "ऊम्", "गमेम"):
    return _strip_syl1_svarita(w)
  return w


def _is_svarita_position_genuine(w: str, sv_start: int, sv_end: int) -> bool:
  """Return ``True`` when a mid-word ``᳙`` at ``[sv_start, sv_end)`` has a glide/sandhi/kampa cause."""
  pre_local = w[max(0, sv_start - 6) : sv_start]
  after_local = w[sv_end:]
  return bool(
    re.search(r"्[यव][ा-ौःंँ]*$", pre_local)
    or re.search(r"[ेोईी][ःंँ]*$", pre_local)
    or any(c in pre_local for c in "१३᳡")
    or "ऽ" in after_local[:3]
  )


def repair_gretil_svarita_leaks_in_vp(
  vp_body: str,
  *,
  mula_text: str = "",
  pp_text: str = "",
  fix_midline_double: bool = True,
) -> tuple[str, int]:
  """Repair spurious clause-initial (and GRETIL mid-line double-accent) ``᳙`` in one VP block."""
  pp_words = _split_padapatha_words(pp_text)
  pp_ptr = 0
  fixes = 0

  parts = re.split(r"([।॥\n]+)", vp_body)
  out_parts: list[str] = []

  for pi, part in enumerate(parts):
    if pi % 2 == 1 or not part.strip():
      out_parts.append(part)
      continue

    tok_parts = re.split(r"(\s+)", part)
    prev_word = ""
    for ti, tok in enumerate(tok_parts):
      if not tok or tok.isspace() or tok.startswith("<"):
        continue
      nxt_tok = ""
      for ni in range(ti + 1, len(tok_parts)):
        if tok_parts[ni] and not tok_parts[ni].isspace() and not tok_parts[ni].startswith("<"):
          nxt_tok = tok_parts[ni]
          break

      is_clause_start = prev_word == ""
      prior_w = prev_word
      prev_word = tok

      if US_SVARITA not in tok:
        if pp_words:
          pp_ptr, _ = _find_matching_pp_slice(_bare_no_marks(tok), pp_words, pp_ptr)
        continue

      lead_b = "**" if tok.startswith("**") else ""
      trail_b = "**" if tok.endswith("**") and len(tok) > 4 else ""
      w = tok[len(lead_b) : len(tok) - len(trail_b) if trail_b else len(tok)]
      w_b = _bare_no_marks(w)

      if pp_words:
        pp_ptr, pp_slice = _find_matching_pp_slice(w_b, pp_words, max(0, pp_ptr - 1))
      else:
        pp_slice = []

      new_w = w
      if is_clause_start and _SYL_1_SVARITA_RE.match(w):
        n_acc = w.count(US_SVARITA) + w.count(US_UDATTA)
        if n_acc >= 2:
          if not _word_has_genuine_kampa_or_abhinihita(w, nxt_tok, mula_text, pp_slice, prev_w=prior_w):
            if (
              pp_slice
              and re.match(r"^स्वा", w_b)
              and len(_DEV_SYL_RE.findall(w)) >= 3
              and "सस्थे" in w_b
            ):
              syls = _DEV_SYL_RE.findall(w)
              rebuilt = [syls[0].replace(US_SVARITA, "") + US_UDATTA, syls[1], syls[2].replace(US_UDATTA, "")]
              rebuilt.extend(syls[3:])
              new_w = "".join(rebuilt)
            elif (
              pp_slice
              and w_b.startswith("द्यावापृथिवी")
              and "\u0951" in pp_slice[0]
            ):
              new_w = _set_udatta_on_syllable(w, 0)
            else:
              new_w = _strip_syl1_svarita(w)
        elif n_acc == 1:
          new_w = _fix_single_accent_clause_init_token(
            w, nxt_tok, mula_text, pp_slice, prev_w=prior_w
          )
      elif fix_midline_double and w.count(US_SVARITA) + w.count(US_UDATTA) >= 2 and US_UDATTA in w:
        if not _word_has_genuine_kampa_or_abhinihita(w, nxt_tok, mula_text, pp_slice, prev_w=prior_w):
          has_unexplained_sv = any(
            not _is_svarita_position_genuine(w, m_sv.start(), m_sv.end())
            for m_sv in re.finditer(r"\u1cd9", w)
          )
          if has_unexplained_sv:
            cand_w = re.sub(
              r"\u1cd9",
              lambda m_sv: US_SVARITA if _is_svarita_position_genuine(w, m_sv.start(), m_sv.end()) else "",
              w,
            )
            if cand_w != w:
              new_w = cand_w
      elif (
        not _word_has_genuine_kampa_or_abhinihita(w, nxt_tok, mula_text, pp_slice, prev_w=prior_w)
        and _SYL_1_SVARITA_RE.match(w)
        and w_b in ("च", "गमेम")
        and (
          not pp_slice
          or (
            _norm_match_key(pp_slice[0]) == _norm_match_key(w_b)
            and ("\u0952" in pp_slice[0] or _norm_match_key(pp_slice[0]) in ("गमेम",))
            and "\u0951" not in pp_slice[0]
            and "\u1ce1" not in pp_slice[0]
          )
        )
      ):
        new_w = _strip_syl1_svarita(w)

      if new_w != w:
        tok_parts[ti] = f"{lead_b}{new_w}{trail_b}"
        fixes += 1
    out_parts.append("".join(tok_parts))

  return "".join(out_parts), fixes


_VP_BLOCK_RE = re.compile(
  r"(<details(?:\s+open)?><summary>(विश्वास-प्रस्तुतिः[^<]*)</summary>\n?)(.*?)(\n?</details>)",
  re.DOTALL,
)


def _split_top_level_preserving_js_include(body: str) -> list[tuple[bool, str]]:
  """Split ``body`` into ``(is_js_include, chunk_text)`` segments preserving verbatim offsets."""
  segs: list[tuple[bool, str]] = []
  pos = 0
  for m in _JS_INCLUDE_BLOCK_RE.finditer(body):
    if m.start() > pos:
      segs.append((False, body[pos : m.start()]))
    segs.append((True, m.group(0)))
    pos = m.end()
  if pos < len(body):
    segs.append((False, body[pos:]))
  return segs


def repair_svarita_leaks_in_markdown(
  md_text: str,
  *,
  tk_text: str = "",
  is_sarva_prastuti: bool = False,
) -> tuple[str, int]:
  """Repair spurious GRETIL initial/midline ``᳙`` in one markdown document without touching ``js_include``s."""
  fm, body = split_frontmatter_verbatim(md_text)
  if US_SVARITA not in body:
    return md_text, 0

  total_fixes = 0
  if is_sarva_prastuti:
    segs = _split_top_level_preserving_js_include(body)
    # Assemble full body slices for read-only mūla/pp context search after each VP block
    out_segs: list[str] = []
    # Compute byte/char offsets for context slicing
    cursor = 0
    for is_inc, chunk in segs:
      chunk_end = cursor + len(chunk)
      if is_inc or US_SVARITA not in chunk:
        out_segs.append(chunk)
        cursor = chunk_end
        continue
      rebuilt: list[str] = []
      lpos = 0
      for vm in _VP_BLOCK_RE.finditer(chunk):
        rebuilt.append(chunk[lpos : vm.start()])
        abs_end = cursor + vm.end()
        tail_ctx = body[abs_end : min(len(body), abs_end + 40000)]
        # Truncate tail context at next VP block or heading
        m_next = re.search(r"\n## |<details(?:\s+open)?><summary>विश्वास-प्रस्तुतिः", tail_ctx)
        if m_next:
          tail_ctx = tail_ctx[: m_next.start()]
        mu_txt = _extract_details_body(tail_ctx, "मूलम् - काण्वम्") or _extract_details_body(tail_ctx, "मूलम् - माध्यन्दिनम्") or _extract_details_body(tail_ctx, "मूलम्")
        pp_txt = _extract_details_body(tail_ctx, "पदपाठः - काण्वः") or _extract_details_body(tail_ctx, "पदपाठः")
        fixed_vp, n_fx = repair_gretil_svarita_leaks_in_vp(
          vm.group(3),
          mula_text=mu_txt,
          pp_text=pp_txt,
        )
        total_fixes += n_fx
        rebuilt.append(f"{vm.group(1)}{fixed_vp}{vm.group(4)}")
        lpos = vm.end()
      rebuilt.append(chunk[lpos:])
      out_segs.append("".join(rebuilt))
      cursor = chunk_end
    return fm + "".join(out_segs), total_fixes

  mu_txt = _extract_details_body(tk_text, "मूलम् - शौनकम्") or _extract_details_body(tk_text, "मूलम्")
  pp_txt = _extract_details_body(tk_text, "पदपाठः")
  out_segs = []
  for is_inc, chunk in _split_top_level_preserving_js_include(body):
    if is_inc or US_SVARITA not in chunk:
      out_segs.append(chunk)
      continue
    fixed_c, n_fx = repair_gretil_svarita_leaks_in_vp(chunk, mula_text=mu_txt, pp_text=pp_txt)
    total_fixes += n_fx
    out_segs.append(fixed_c)
  return fm + "".join(out_segs), total_fixes


def repair_tree_svarita_leaks(
  root_dirs: Sequence[str | os.PathLike[str]],
  *,
  refresh_host_dirs: Sequence[str | os.PathLike[str]] = (),
  hugo_base_dir: str | os.PathLike[str] = "/home/vvasuki/gitland/vishvAsa",
  file_filter: Sequence[str] | None = None,
  dry_run: bool = True,
) -> dict[str, object]:
  """Batch-repair spurious GRETIL ``᳙`` across VP/sarva trees and refresh transitive ``js_include`` hosts."""
  changed_files: list[str] = []
  total_token_fixes = 0
  sample_changes: list[tuple[str, str, str]] = []

  for r_dir in root_dirs:
    r_path = pathlib.Path(r_dir)
    if not r_path.exists():
      continue
    is_sarva = "sarva-prastutiH" in str(r_path)
    candidates = [r_path / f for f in file_filter] if file_filter else sorted(r_path.rglob("*.md"))
    for fp in candidates:
      if not fp.is_file() or fp.name == "_index.md":
        continue
      orig = fp.read_text(encoding="utf-8", errors="ignore")
      if US_SVARITA not in orig:
        continue
      tk_text = ""
      if not is_sarva and "/vishvAsa-prastutiH/" in str(fp):
        tk_fp = pathlib.Path(str(fp).replace("/vishvAsa-prastutiH/", "/sarvASh_TIkAH/"))
        if tk_fp.is_file():
          tk_text = tk_fp.read_text(encoding="utf-8", errors="ignore")
      new_txt, n_fx = repair_svarita_leaks_in_markdown(
        orig, tk_text=tk_text, is_sarva_prastuti=is_sarva
      )
      if n_fx > 0 and new_txt != orig:
        changed_files.append(str(fp))
        total_token_fixes += n_fx
        for old_l, new_l in zip(orig.splitlines(), new_txt.splitlines()):
          if old_l != new_l:
            sample_changes.append((str(fp), old_l.strip(), new_l.strip()))
        if not dry_run:
          fp.write_text(new_txt, encoding="utf-8")

  updated_hosts: list[str] = []
  if not dry_run and changed_files and refresh_host_dirs:
    res = surgical_prefill_transitive(
      [str(h) for h in refresh_host_dirs],
      changed_files,
      hugo_base_dir=str(hugo_base_dir),
      dry_run=False,
    )
    if isinstance(res, dict):
      updated_hosts = list(res.get("updated_files", []))
    elif res:
      updated_hosts = sorted(str(x) for x in res)

  return {
    "changed_files": changed_files,
    "token_fixes": total_token_fixes,
    "line_diffs": sample_changes,
    "updated_hosts": updated_hosts,
  }

