"""Multi-task SFT dataset builder for the Sanskrit proofreader / interleaver LLM.

Extracts a balanced, deduplicated, zero-leakage ``(train.jsonl, eval.jsonl)``
dataset from ``vishvAsa`` sources declared in ``rAmAnujIya-sources.toml`` plus
curated Vedic ``vedAH_yajuH`` files:

1. ``proofread_vp``: Aligned ``(मूलम् → विश्वास-प्रस्तुतिः)`` pairs (stripping
   editorial ``+++(...)+++`` glosses and wrapping genuine lexical edits as
   ``[[OLD|NEW]]``).
2. ``proofread_suggestions``: Real ``[[OLD|NEW]]`` commentary passages reconstructed
   into pre-proofread raw input via deterministic Devanāgarī forward-sandhi join.
3. ``clause_newlines_contrastive``: Same raw multi-clause prose sentence paired
   with ``clause_newlines=True`` (preserving curated soft-broken clause lines) AND
   ``clause_newlines=False`` (continuous paragraph), forcing prompt compliance.
4. ``structural_and_mixed``: Embedded IAST/Devanāgarī inside English prose,
   ``[[Pnnn]]`` page numbers, ``[[??]]`` illegible OCR spans, ``[^page_n]`` footnotes,
   ``<details><summary>मूलम्</summary>`` & ``DETAIL-SPLIT`` marker preservation,
   and idempotence on already-hyphenated text.
5. ``translation_matcher``: Exact cursor-index alignment batches formatted with
   ``doc_curation/llm/translation_matcher_prompt.md``.
6. ``commentary_interleaver``: Multi-role commentary & viniyoga/avatārikā/ṭīkā/note
   segment-to-core JSON alignment.
7. ``padapatha_accent``: Lexicon-grounded ``पद-पाठः (यान्त्रिकः)`` generation.
"""
from __future__ import annotations

import json
import os
import random
import string
import tomllib
import regex
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.sanskrit.hyphenator import constants as HC
from .accent_helper import format_padapatha_user_prompt, retrieve_accent_candidates
from .guards import canonical_sandhi_skeleton, wrap_silent_mutations
from .interleave_helper import format_interleave_prompt, split_quote_safe_segments
from .prompts import (
  INTERLEAVER_SYSTEM_PROMPT,
  PADAPATHA_ACCENT_SYSTEM_PROMPT,
  build_system_prompt,
)

_DETAILS_RE = regex.compile(
  r"<details(?:\s+open)?\s*>\s*<summary>([^<]+)</summary>(.*?)</details>",
  flags=regex.DOTALL,
)
_ANNO_PLUS_RE = regex.compile(r"\+\+\+\(.*?\)\+\+\+", flags=regex.DOTALL)
_SUG_SPAN_RE = regex.compile(r"\[\[([^|\]]+)\|([^\]]+)\]\]")
_MANIPRAVALA_RE = regex.compile(r"[\u090e\u0912\u0929\u0931\u0934]")
_ANY_ACCENT_RE = regex.compile(r"[\u0951-\u0954\u1cd0-\u1cff]")

_INDEP_TO_MATRA = {
  "अ": "", "आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
  "ऋ": "ृ", "ॠ": "ॄ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ",
}
# Legacy editor "+vowel" merger table for a/ā + independent vowel
_A_VOWEL_MERGER = {
  "अ": "ा", "आ": "ा", "इ": "े", "ई": "े", "उ": "ो", "ऊ": "ो",
  "ऋ": "र्", "ए": "ै", "ऐ": "ै", "ओ": "ौ", "औ": "ौ",
}


def clean_prastuti_target(text: str) -> str:
  """Strip ``+++(...)+++`` editorial glosses and normalize legacy ``--`` to ``–``."""
  t = _ANNO_PLUS_RE.sub("", text)
  # Legacy "X-+V" editor junctions -> merged vowel
  def _merge_plus(m: regex.Match) -> str:
    base, matra, vow = m.group(1), m.group(2) or "", m.group(3)
    if matra in ("", "ा") and vow in _A_VOWEL_MERGER:
      rep = _A_VOWEL_MERGER[vow]
      if rep == "र्":
        return base + "र्"
      return base + rep
    return base + matra + vow

  t = regex.sub(
    r"([\u0915-\u0939])([\u093e-\u094c])?[-–—]+\s*\+([\u0905-\u0914])",
    _merge_plus,
    t,
  )
  # Normalize space-separated multi-dashes ("-- -", "--") inside compounds to "–"
  t = regex.sub(r"(?<=\S)[-–—]+\s+[-–—]+(?=\S)", "–", t)
  t = regex.sub(r"(?<=\S)--(?=\S)", "–", t)
  # Collapse horizontal multi-spaces created by +++(...)+++ removal while keeping
  # trailing two-space Markdown soft breaks ("  \n").
  lines = []
  for line in t.splitlines():
    soft = line.endswith("  ")
    cleaned = regex.sub(r"[ \t]{2,}", " ", line.strip())
    if cleaned:
      lines.append(cleaned + ("  " if soft else ""))
    else:
      lines.append("")
  out = "\n".join(lines).strip()
  out = regex.sub(r"\n{3,}", "\n\n", out)
  return out


def unsplit_sanskrit_to_raw(
  curated_text: str,
  rng: random.Random,
  *,
  revert_suggestions_to_old: bool = True,
  collapse_clause_newlines: bool = True,
  hard_wrap_prob: float = 0.25,
) -> str:
  """Reconstruct realistic raw un-hyphenated / OCR text from a curated passage."""
  t = curated_text
  if revert_suggestions_to_old:
    t = _SUG_SPAN_RE.sub(lambda m: m.group(1), t)

  if collapse_clause_newlines:
    # Collapse single soft-break newlines inside paragraphs while preserving \n\n
    paras = regex.split(r"\n\s*\n", t)
    collapsed = []
    for p in paras:
      if p.lstrip().startswith(">"):
        collapsed.append(p.strip())
      else:
        collapsed.append(regex.sub(r"[ \t]*\n[ \t]*", " ", p).strip())
    t = "\n\n".join(collapsed)

  # 1. Fuse C+् + (-/–/space) + independent vowel -> CV (e.g. इत्य् एवम् -> इत्येवम्,
  #    चिद्-अचिद् -> चिदचिद्, फलम् अश्नुते -> फलमश्नुते)
  def _fuse_cv(m: regex.Match) -> str:
    cons, vow = m.group(1), m.group(2)
    return cons + _INDEP_TO_MATRA.get(vow, vow)

  prev = None
  while prev != t:
    prev = t
    t = regex.sub(
      r"([\u0915-\u0939])\u094d(?:[-–—]+|[ \t]+)(?=[\u0905-\u0914])([\u0905-\u0914])",
      _fuse_cv,
      t,
    )

  # 2. Join avagraha spacing: रामो ऽस्ति -> रामोऽस्ति
  t = regex.sub(r"([ेो])\s+ऽ", r"\1ऽ", t)

  # 3. Join consonant assimilation / visarga-s/ś/ṣ/r across spaces:
  #    नमस् ते -> नमस्ते, तद् धि -> तद्धि, आश्रितत्वाच् च -> आश्रितत्वाच्च, वक्तुर् आ... (handled above)
  t = regex.sub(
    r"([सशषरदजचटडलबग]\u094d)[ \t]+(?=[\u0915-\u0939])",
    r"\1",
    t,
  )

  # 4. Remove compound hyphens (- and –) between word characters (both Devanāgarī & IAST)
  t = regex.sub(r"(?<=[\u0900-\u097fA-Za-z\u0100-\u017f\u1e00-\u1eff])[-–](?=[\u0900-\u097fA-Za-z\u0100-\u017f\u1e00-\u1eff])", "", t)

  # 5. Occasionally convert final म् before consonant to lazy anusvāra ं & hard-wrap
  if rng.random() < 0.35:
    t = regex.sub(r"म्(?=\s+[\u0915-\u0939])", "ं", t)

  if rng.random() < hard_wrap_prob and "\n\n" not in t and len(t) > 110:
    words = t.split(" ")
    lines, cur, cur_len = [], [], 0
    limit = rng.randint(58, 78)
    for w in words:
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


def _is_verse_block(text: str) -> bool:
  """Heuristic: metrical śloka/ṛk has pada-ending dandas (। ... ॥) with short lines."""
  lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
  if not (2 <= len(lines) <= 6) or "॥" not in lines[-1]:
    return False
  return any(l.endswith("।") or re.search(r"।\s*\[\d+\]$", l) for l in lines[:-1]) if False else any(
    l.endswith("।") for l in lines[:-1]
  )


def _has_meaningful_prose_clause_breaks(text: str) -> bool:
  """Return True if ``text`` is prose (not śloka verse) with >=2 clause lines."""
  if _is_verse_block(text):
    return False
  lines = [l.strip() for l in text.strip().splitlines() if l.strip() and not l.strip().startswith(">")]
  if len(lines) < 2:
    return False
  return any(not l.endswith(("।", "॥", ":", "-")) for l in lines[:-1])


def _skeleton_old_side(text: str) -> str:
  """Canonical skeleton using the OLD side of any ``[[OLD|NEW]]`` spans."""
  old_only = _SUG_SPAN_RE.sub(lambda m: m.group(1), text)
  old_only = regex.sub(r"\[\[(?:P\d+[a-zA-Z]?|\?\?)\]\]", "", old_only)
  return canonical_sandhi_skeleton(old_only)


_OCR_CONFUSIONS = (
  ("प्र", "प"),
  ("मा", "म"),
  ("पा", "प"),
  ("ू", ""),
  ("े", ""),
  ("ब", "व"),
  ("व", "ब"),
  ("म", "य"),
  ("प", "व"),
  ("ध", "घ"),
  ("द", "र"),
)


def _inject_realistic_ocr_typo(curated_para: str, rng: random.Random) -> tuple[str, str] | None:
  """Inject 1 authentic Devanāgarī OCR corruption into a clean curated paragraph,
  returning ``(raw_input, target_with_suggestion)`` or None if no clean spot found."""
  if "[[" in curated_para or "<" in curated_para:
    return None
  words = curated_para.split(" ")
  candidates = [
    idx for idx, w in enumerate(words)
    if len(w) >= 6
    and "\n" not in w
    and not w.startswith(">")
    and regex.fullmatch(r"[\u0900-\u0963\u0971-\u097f\-–]+[।॥,]*", w)
  ]
  if not candidates:
    return None
  idx = rng.choice(candidates)
  orig_tok = words[idx]
  m_punc = regex.match(r"^(.*?)([।॥,]*)$", orig_tok)
  core_hyphenated, trail_punc = m_punc.group(1), m_punc.group(2)
  unsplit_core = unsplit_sanskrit_to_raw(core_hyphenated, rng, hard_wrap_prob=0.0)
  if len(unsplit_core) < 5:
    return None

  corrupted = None
  # Try repha transposition (र्य -> यर्) or glyph/matra corruption
  m_repha = regex.search(r"र्([\u0915-\u0939])([\u093e-\u094c])", unsplit_core)
  if m_repha and rng.random() < 0.35:
    s, e = m_repha.span()
    corrupted = unsplit_core[:s] + m_repha.group(1) + "र्" + m_repha.group(2) + unsplit_core[e:]
  else:
    rules = list(_OCR_CONFUSIONS)
    rng.shuffle(rules)
    for src_sub, dst_sub in rules:
      pos = unsplit_core.find(src_sub, 1)
      if pos != -1:
        cand = unsplit_core[:pos] + dst_sub + unsplit_core[pos + len(src_sub):]
        if cand != unsplit_core and canonical_sandhi_skeleton(cand) != canonical_sandhi_skeleton(unsplit_core):
          corrupted = cand
          break
  if not corrupted:
    return None

  sentinel = "§§TYPO§§"
  words_with_sug = list(words)
  words_with_sug[idx] = f"[[{corrupted}|{core_hyphenated}]]{trail_punc}"
  target_out = " ".join(words_with_sug)

  words_for_raw = list(words)
  words_for_raw[idx] = f"{sentinel}{trail_punc}"
  raw_in = unsplit_sanskrit_to_raw(" ".join(words_for_raw), rng, collapse_clause_newlines=True)
  raw_in = raw_in.replace(sentinel, corrupted)
  return raw_in, target_out


def _collapse_prose_soft_breaks(text: str) -> str:
  paras = regex.split(r"\n\s*\n", text)
  out = []
  for p in paras:
    if p.lstrip().startswith(">"):
      out.append(p.strip())
    else:
      out.append(regex.sub(r"[ \t]*\n[ \t]*", " ", p).strip())
  return "\n\n".join(out)


def _msg_record(system: str, user: str, assistant: str, task_type: str, meta: dict | None = None) -> dict:
  rec = {
    "task_type": task_type,
    "messages": [
      {"role": "system", "content": system},
      {"role": "user", "content": user},
      {"role": "assistant", "content": assistant},
    ],
  }
  if meta:
    rec["meta"] = meta
  return rec


def _collect_ra_files() -> tuple[list[str], list[str]]:
  with open(HC._RA_SOURCES_TOML, "rb") as f:
    cfg = tomllib.load(f)
  train_files: list[str] = []
  eval_files: list[str] = []
  for src in cfg.get("source", ()):
    root = src["path"]
    until = src.get("until")
    if os.path.isfile(root):
      if os.path.basename(root) != "_index.md":
        train_files.append(root)
    elif os.path.isdir(root):
      for dp, dns, fns in os.walk(root):
        dns.sort()
        for fn in sorted(fns):
          if not fn.endswith(".md") or fn == "_index.md":
            continue
          full = os.path.join(dp, fn)
          rel = os.path.relpath(full, root).replace(os.sep, "/")
          if until and rel >= until:
            eval_files.append(full)
          else:
            train_files.append(full)
  return train_files, eval_files


def _extract_proofreading_examples(
  files: list[str],
  rng: random.Random,
  *,
  max_vp_pairs: int,
  max_sug_blocks: int,
  max_clause_pairs: int,
) -> list[dict]:
  vp_examples: list[dict] = []
  sug_examples: list[dict] = []
  clause_examples: list[dict] = []
  idempotent_examples: list[dict] = []

  shuffled = list(files)
  rng.shuffle(shuffled)

  for fp in shuffled:
    try:
      raw_md = open(fp, encoding="utf-8").read()
    except OSError:
      continue
    blocks = _DETAILS_RE.findall(raw_md)

    # 1. Aligned (विश्वास-प्रस्तुतिः, मूलम्) pairs
    for i, (lbl, body) in enumerate(blocks):
      lbl_s = lbl.strip()
      if lbl_s.startswith("विश्वास-प्रस्तुतिः") and len(vp_examples) < max_vp_pairs * 2:
        mula_body = None
        for j in range(i + 1, min(i + 5, len(blocks))):
          if blocks[j][0].strip() == "मूलम्":
            mula_body = blocks[j][1].strip()
            break
        if mula_body and len(mula_body) >= 25:
          if _MANIPRAVALA_RE.search(mula_body) or _MANIPRAVALA_RE.search(body):
            continue
          target = clean_prastuti_target(body)
          if not target or len(target) > 2200:
            continue
          # Strip editorial bolding added only in VP when mUla itself had no bolding
          if "**" not in mula_body and "**" in target:
            target = target.replace("**", "")

          mula_has_acc = bool(_ANY_ACCENT_RE.search(mula_body))
          tgt_has_acc = bool(_ANY_ACCENT_RE.search(target))
          if tgt_has_acc and not mula_has_acc:
            continue  # Never train model to invent accents onto unaccented mUla
          if mula_has_acc and "\u1cd3" in target and ("\u0951" in mula_body or "\u0952" in mula_body):
            from indic_transliteration.sanscript.schemes.brahmic import accent as acc_mod
            mula_in = acc_mod.to_US_accents(mula_body, pauses=r"[।॥,;]+")
          elif not tgt_has_acc and mula_has_acc:
            mula_in = accent.strip_accents(mula_body)
          else:
            mula_in = mula_body

          # Ensure 1-to-1 coverage between mUla and VP (reject combined mUla covering multiple VPs!)
          skel_mula = _skeleton_old_side(mula_in.replace("*", ""))
          skel_tgt = _skeleton_old_side(target.replace("*", ""))
          if not skel_mula or abs(len(skel_mula) - len(skel_tgt)) > max(4, int(0.06 * len(skel_mula))):
            continue

          # Wrap genuine lexical diffs as [[OLD|NEW]]; if bare skeletons match, target is already exact!
          if skel_mula == skel_tgt:
            target_wrapped = target
          else:
            target_wrapped = wrap_silent_mutations(mula_in, target, allow_suggestions=True)
          has_clause_nl = _has_meaningful_prose_clause_breaks(target_wrapped)

          variant = rng.randint(0, 5)
          if has_clause_nl:
            # Contrastive pair! Same input under clause_newlines=True AND False!
            if len(clause_examples) < max_clause_pairs * 2:
              sys_on = build_system_prompt(clause_newlines=True, suggest_corrections=True, variant=variant)
              sys_off = build_system_prompt(clause_newlines=False, suggest_corrections=True, variant=variant + 1)
              clause_examples.append(_msg_record(sys_on, mula_in, target_wrapped, "clause_newlines_on"))
              clause_examples.append(
                _msg_record(sys_off, mula_in, _collapse_prose_soft_breaks(target_wrapped), "clause_newlines_off")
              )
          else:
            # Guarantee non-verse prose under clause_newlines=False has no stray single-newline breaks
            norm_tgt = target_wrapped if _is_verse_block(target_wrapped) else _collapse_prose_soft_breaks(target_wrapped)
            has_sug = "[[" in norm_tgt
            sug_flag = True if has_sug else (rng.random() < 0.75)
            sys_p = build_system_prompt(
              clause_newlines=False,
              suggest_corrections=sug_flag,
              markdown_cleanup=(rng.random() < 0.7),
              variant=variant,
            )
            vp_examples.append(_msg_record(sys_p, mula_in, norm_tgt, "proofread_vp"))
            if not has_sug and len(sug_examples) < max_sug_blocks * 2 and rng.random() < 0.45:
              injected = _inject_realistic_ocr_typo(norm_tgt, rng)
              if injected is not None:
                inj_in, inj_out = injected
                sug_examples.append(
                  _msg_record(
                    build_system_prompt(clause_newlines=False, suggest_corrections=True, variant=variant + 2),
                    inj_in,
                    inj_out,
                    "proofread_suggestions",
                  )
                )
            if not has_sug and rng.random() < 0.12 and len(idempotent_examples) < max(40, max_vp_pairs // 8):
              idempotent_examples.append(_msg_record(sys_p, norm_tgt, norm_tgt, "idempotence"))

      # 2. Commentary blocks with real [[OLD|NEW]] suggestions or clause newlines
      if any(lbl_s.startswith(k) for k in ("श्रुत-प्रकाशिका", "विश्वास-टिप्पनी", "नीलमेघः (सं)")):
        if _MANIPRAVALA_RE.search(body):
          continue
        cleaned_comm = clean_prastuti_target(body)
        if not (40 <= len(cleaned_comm) <= 2200):
          continue
        # Remove degenerate [[X|X]] spans where OLD == NEW
        cleaned_comm = _SUG_SPAN_RE.sub(
          lambda m: m.group(2) if m.group(1).strip() == m.group(2).strip() else m.group(0),
          cleaned_comm,
        )
        sugs = _SUG_SPAN_RE.findall(cleaned_comm)
        if sugs and len(sug_examples) < max_sug_blocks * 2:
          # Slice per paragraph if long so examples are crisp
          for para in regex.split(r"\n\s*\n", cleaned_comm):
            para = para.strip()
            if "[[" not in para or not (35 <= len(para) <= 1600):
              continue
            has_cl = _has_meaningful_prose_clause_breaks(para)
            raw_in = unsplit_sanskrit_to_raw(
              para, rng, revert_suggestions_to_old=True, collapse_clause_newlines=True
            )
            sys_p = build_system_prompt(
              clause_newlines=has_cl,
              suggest_corrections=True,
              variant=rng.randint(0, 5),
            )
            sug_examples.append(_msg_record(sys_p, raw_in, para, "proofread_suggestions"))
        elif _has_meaningful_prose_clause_breaks(cleaned_comm) and len(clause_examples) < max_clause_pairs * 2:
          for para in regex.split(r"\n\s*\n", cleaned_comm):
            para = para.strip()
            if not _has_meaningful_prose_clause_breaks(para) or not (50 <= len(para) <= 1400):
              continue
            raw_in = unsplit_sanskrit_to_raw(
              para, rng, revert_suggestions_to_old=True, collapse_clause_newlines=True, hard_wrap_prob=0.3
            )
            v = rng.randint(0, 5)
            clause_examples.append(
              _msg_record(build_system_prompt(clause_newlines=True, suggest_corrections=True, variant=v), raw_in, para, "clause_newlines_on")
            )
            clause_examples.append(
              _msg_record(
                build_system_prompt(clause_newlines=False, suggest_corrections=True, variant=v + 1),
                raw_in,
                _collapse_prose_soft_breaks(para),
                "clause_newlines_off",
              )
            )

  rng.shuffle(vp_examples)
  rng.shuffle(sug_examples)
  return (
    vp_examples[:max_vp_pairs]
    + sug_examples[:max_sug_blocks]
    + clause_examples[:max_clause_pairs * 2]
    + idempotent_examples
  )


def _extract_structural_and_mixed_examples(files: list[str], rng: random.Random, limit: int) -> list[dict]:
  """Synthesize high-precision structural examples:
  - English prose (Thibaut) with embedded Sanskrit compounds & [[OLD|NEW]] IAST typos,
  - ``[[Pnnn]]`` page numbers & ``[^12_1]`` footnotes & ``[[??]]`` illegible OCR spans,
  - ``<<MULAM_0000>>`` and ``<!-- Proofreader-DETAIL-SPLIT 0001 -->`` marker preservation.
  """
  examples: list[dict] = []
  ias_pairs = [
    ("jagatkāraṇatvam", "jagat-kāraṇatvam"),
    ("brahmajijñāsā", "brahma-jijñāsā"),
    ("svaprakāśādvitīya", "svaprakāśādvitīya"),  # non-separable dīrgha veto in IAST!
    ("dharmārtha", "dharmārtha"),
    ("mahotsava", "mahotsava"),
    ("puṇyapāpaiḥ", "puṇya-pāpaiḥ"),
    ("cidacidvilakṣaṇa", "cid-acid-vilakṣaṇa"),
    ("śarīrātmasambandha", "śarīrātma-sambandha"),
    ("karmamīmāṁsā", "karma-mīmāṁsā"),
    ("nityaśuddhabuddhamuktasvabhāva", "nitya-śuddha-buddha-mukta-svabhāva"),
  ]
  iast_typos = [
    ("prarabvaṁ", "prārabdhaṁ"),
    ("sarvajnatva", "sarvajñatva"),
    ("antaryamin", "antaryāmin"),
    ("apahatapapman", "apahata-pāpman"),
    ("satyakama", "satya-kāma"),
  ]

  en_paras: list[str] = []
  sa_paras: list[tuple[str, str]] = []
  for fp in files:
    try:
      txt = open(fp, encoding="utf-8").read()
    except OSError:
      continue
    for lbl, body in _DETAILS_RE.findall(txt):
      if lbl.strip() in ("Thibaut", "P.R.Ramachander") and 80 <= len(body.strip()) <= 600:
        en_paras.append(regex.sub(r"\s+", " ", body.strip()))
      elif lbl.strip().startswith("विश्वास-प्रस्तुतिः") and 60 <= len(body.strip()) <= 500:
        tgt = clean_prastuti_target(body)
        if tgt and "[[" not in tgt and "\n\n" not in tgt:
          raw = unsplit_sanskrit_to_raw(tgt, rng, hard_wrap_prob=0.0)
          sa_paras.append((raw, _collapse_prose_soft_breaks(tgt)))
    if len(en_paras) >= limit and len(sa_paras) >= limit * 2:
      break

  rng.shuffle(en_paras)
  rng.shuffle(sa_paras)

  # A. Embedded IAST + English + optional IAST typo + surrounding English never hyphenated
  for idx in range(min(limit // 3, len(en_paras))):
    base_en = en_paras[idx]
    raw_c, hyp_c = rng.choice(ias_pairs)
    if rng.random() < 0.5:
      bad_t, good_t = rng.choice(iast_typos)
      inp = f"{base_en} This doctrine of {raw_c} and {bad_t} is central here."
      out = f"{base_en} This doctrine of {hyp_c} and [[{bad_t}|{good_t}]] is central here."
    else:
      inp = f"{base_en} Compare the expression {raw_c} in the commentary."
      out = f"{base_en} Compare the expression {hyp_c} in the commentary."
    examples.append(
      _msg_record(build_system_prompt(clause_newlines=False, suggest_corrections=True, variant=idx), inp, out, "embedded_iast")
    )

  # B. Page markers [[P64]], footnotes [^12_1], illegible [[??]], and DETAIL-SPLIT / MULAM placeholders
  dev_digits = str.maketrans("0123456789", "०१२३४५६७८९")
  for idx in range(min(limit // 2, len(sa_paras) - 1)):
    raw1, tgt1 = sa_paras[idx]
    raw2, tgt2 = sa_paras[idx + 1]
    mode = idx % 4
    sys_p = build_system_prompt(clause_newlines=False, suggest_corrections=True, markdown_cleanup=True, variant=idx)
    if mode == 0:
      # Page break number mid-flow
      pno = rng.randint(12, 240)
      dev_pno = str(pno).translate(dev_digits)
      w_raw = raw1.split()
      w_tgt = tgt1.split()
      if len(w_raw) >= 4 and len(w_tgt) >= 4:
        inp = " ".join(w_raw[:2]) + f"\n{dev_pno}\n" + " ".join(w_raw[2:])
        # Place [[P...]] at corresponding spot; build clean pair where raw1 + raw2 separated by page num
        inp = f"{raw1}\n{dev_pno}\n{raw2}"
        out = f"{tgt1} [[P{pno}]] {tgt2}"
        examples.append(_msg_record(sys_p, inp, out, "page_marker"))
    elif mode == 1:
      # Illegible OCR garbage -> [[??]]
      garb = rng.choice(["@#%??", "क्ष्म्ष्ट्र्@#", "\ufffd\ufffd##"])
      inp = f"{raw1} {garb} {raw2}"
      out = f"{tgt1} [[??]] {tgt2}"
      examples.append(_msg_record(sys_p, inp, out, "illegible_marker"))
    elif mode == 2:
      # <<MULAM_0000>> and <!-- Proofreader-DETAIL-SPLIT 0001 --> preservation
      inp = f"<!-- Proofreader-DETAIL-SPLIT 0001 -->\n{raw1}\n\n<<MULAM_0000>>\n\n<!-- Proofreader-DETAIL-SPLIT 0002 -->\n{raw2}"
      out = f"<!-- Proofreader-DETAIL-SPLIT 0001 -->\n{tgt1}\n\n<<MULAM_0000>>\n\n<!-- Proofreader-DETAIL-SPLIT 0002 -->\n{tgt2}"
      examples.append(_msg_record(sys_p, inp, out, "marker_preservation"))
    else:
      # Footnote formatting with page context
      pno = rng.randint(10, 95)
      inp = f"[[P{pno}]] {raw1}*\n\n* {raw2}"
      out = f"[[P{pno}]] {tgt1}[^{pno}_1]\n\n[^{pno}_1]: {tgt2}"
      examples.append(_msg_record(sys_p, inp, out, "footnote_format"))

  return examples[:limit]


def _extract_translation_matcher_examples(files: list[str], rng: random.Random, limit: int) -> list[dict]:
  """Build exact ``translation_matcher`` cursor-index JSON examples using the
  literal ``translation_matcher_prompt.md`` template."""
  from doc_curation.llm.translation_matcher import _canon_text

  prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "translation_matcher_prompt.md")
  raw_tpl = open(prompt_path, encoding="utf-8").read()
  raw_tpl = regex.sub(r"^<!--.*?-->\s*", "", raw_tpl, flags=regex.DOTALL).rstrip("\n")
  tpl = string.Template(raw_tpl)

  examples: list[dict] = []
  for fp in files:
    try:
      txt = open(fp, encoding="utf-8").read()
    except OSError:
      continue
    blocks = _DETAILS_RE.findall(txt)
    # Group sequential clusters around मूलम्
    clusters: list[tuple[str, str]] = []  # (core_mula, en_trans_or_empty)
    last_trans = ""
    for lbl, body in blocks:
      ls = lbl.strip()
      if ls in ("Thibaut", "Keith", "त्रिभुवनः", "P.R.Ramachander"):
        # Strip inline [P...]: footnote defs from translation window
        b_clean = regex.sub(r"\n\[[A-Za-z0-9_]+\]:.*", "", body.strip())
        b_clean = regex.sub(r"^\d+\\\.\s*", "", b_clean)
        last_trans = _canon_text(b_clean)
      elif ls == "मूलम्":
        core = regex.sub(r"\s+", " ", body.strip())
        if core:
          clusters.append((core, last_trans))
        last_trans = ""

    if len(clusters) < 5:
      continue

    step = 5
    for start in range(0, len(clusters) - 4, step):
      batch_sz = rng.randint(4, min(8, len(clusters) - start))
      batch = clusters[start:start + batch_sz]
      upcoming = clusters[start + batch_sz:start + batch_sz + 2]
      if sum(1 for _, en in batch if en) < 3:
        continue

      en_pieces: list[str] = []
      starts_map: dict[str, int] = {}
      skips: list[int] = []
      word_cursor = 0
      c_start = start
      c_last = start + batch_sz - 1

      for offset, (core_txt, en_txt) in enumerate(batch):
        g_idx = c_start + offset
        starts_map[str(g_idx)] = word_cursor
        w = en_txt.split() if en_txt else []
        if not w:
          skips.append(g_idx)
        else:
          en_pieces.append(en_txt)
          word_cursor += len(w)

      next_en = word_cursor
      # Append upcoming translation tail ~65% of the time to teach early stopping!
      if upcoming and rng.random() < 0.65:
        for _, up_en in upcoming:
          if up_en:
            en_pieces.append(up_en)

      en_window = " ".join(en_pieces)
      e_window_count = len(en_window.split())
      if e_window_count < 10 or e_window_count > 1200:
        continue

      core_lines = "\n".join(f"[{c_start + k}] {c}" for k, (c, _) in enumerate(batch))
      up_block = ""
      if upcoming:
        up_lines = "\n".join(f"[{c_last + 1 + k}] {c}" for k, (c, _) in enumerate(upcoming))
        up_block = f"UPCOMING CORES (read-only context — do NOT map these):\n{up_lines}"

      user_prompt = tpl.substitute(
        total_core_m1=len(clusters) - 1,
        total_core=len(clusters),
        total_en_m1=e_window_count - 1,
        total_en=e_window_count,
        c_start=c_start,
        c_last=c_last,
        e_start=0,
        e_window_count=e_window_count,
        anchor="",
        pacing="",
        core_lines=core_lines,
        en_words=en_window,
        upcoming=up_block,
      )
      gold_json = json.dumps({"starts": starts_map, "skip": skips, "next_en": next_en}, ensure_ascii=False)
      examples.append(
        {
          "task_type": "translation_matcher",
          "messages": [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": gold_json},
          ],
        }
      )
      if len(examples) >= limit * 2:
        break
    if len(examples) >= limit * 2:
      break

  rng.shuffle(examples)
  return examples[:limit]


def _extract_interleaver_and_padapatha_examples(
  ra_files: list[str],
  vedic_files: list[str],
  rng: random.Random,
  *,
  interleave_limit: int,
  padapatha_limit: int,
) -> tuple[list[dict], list[dict]]:
  interleave_ex: list[dict] = []
  padapatha_ex: list[dict] = []

  all_interleave_sources = list(vedic_files) + list(ra_files)
  rng.shuffle(all_interleave_sources)

  for fp in all_interleave_sources:
    if len(interleave_ex) >= interleave_limit * 2:
      break
    try:
      txt = open(fp, encoding="utf-8").read()
    except OSError:
      continue
    blocks = _DETAILS_RE.findall(txt)

    # Parse clusters that have मूलम् + surrounding viniyoga/avatarika/tika/note
    clusters = []
    pending_top: list[tuple[str, str]] = []
    cur: dict | None = None
    for lbl, body in blocks:
      ls = lbl.strip()
      bs = body.strip()
      if not bs:
        continue
      if ls.endswith("विनियोगः"):
        if cur is not None:
          clusters.append(cur)
          cur = None
        pending_top.append(("viniyoga", bs))
      elif ls.endswith("अवतारिका"):
        if cur is not None:
          clusters.append(cur)
          cur = None
        pending_top.append(("avatarika", bs))
      elif ls.endswith("- Note"):
        if cur is not None:
          cur["items"].append(("note", bs))
        else:
          pending_top.append(("note", bs))
      elif ls == "मूलम्":
        if cur is not None:
          clusters.append(cur)
        cur = {"mula": bs, "items": list(pending_top)}
        pending_top = []
      elif cur is not None and any(k in ls for k in ("टीका", "श्रुत-प्रकाशिका", "भाष्यम्")):
        # Split commentary into 1-3 quote-safe chunks so LLM practices multi-sentence grouping
        sents = split_quote_safe_segments(bs)
        if 1 <= len(sents) <= 6:
          for s in sents:
            cur["items"].append(("tika", s))
        elif len(sents) > 6:
          mid = len(sents) // 2
          cur["items"].append(("tika", " ".join(sents[:mid])))
          cur["items"].append(("tika", " ".join(sents[mid:])))
        clusters.append(cur)
        cur = None
    if cur is not None:
      clusters.append(cur)

    usable = [c for c in clusters if c["items"] and len(c["mula"]) <= 600]
    for st in range(0, len(usable) - 1, 3):
      window = usable[st:st + rng.randint(2, min(4, len(usable) - st))]
      tail_extra = usable[st + len(window)]["items"][:1] if (st + len(window) < len(usable) and rng.random() < 0.4) else []
      cores = [w["mula"] for w in window]
      segs: list[str] = []
      assignments: list[dict] = []
      for c_idx, w in enumerate(window):
        for role, seg_txt in w["items"]:
          if len(seg_txt) > 700:
            continue
          assignments.append({"seg": len(segs), "core": c_idx, "role": role})
          segs.append(seg_txt)
      unmatched_from = len(segs)
      for _, extra_txt in tail_extra:
        if len(extra_txt) <= 700:
          segs.append(extra_txt)
      if len(assignments) < 2 or len(segs) > 16:
        continue
      u_prompt = format_interleave_prompt(
        cores,
        segs,
        author_label="भट्टभास्कर-टीका" if "vedAH" in fp else "श्रुत-प्रकाशिका",
        is_sarvash_tikah=("sarvASh_TIkAH" in fp),
      )
      ans = json.dumps({"assignments": assignments, "unmatched_from": unmatched_from}, ensure_ascii=False)
      interleave_ex.append(_msg_record(INTERLEAVER_SYSTEM_PROMPT, u_prompt, ans, "commentary_interleaver"))

  # Extract पद-पाठः (यान्त्रिकः...) examples from curated Vedic files
  for fp in vedic_files:
    if len(padapatha_ex) >= padapatha_limit * 2:
      break
    try:
      txt = open(fp, encoding="utf-8").read()
    except OSError:
      continue
    if "पद-पाठः (यान्त्रिकः" not in txt:
      continue
    blocks = _DETAILS_RE.findall(txt)
    for i, (lbl, body) in enumerate(blocks):
      ls = lbl.strip()
      if not ls.startswith("पद-पाठः (यान्त्रिकः"):
        continue
      # Find preceding मूलम्, optional translation, and adjacent टीका
      mula_txt, trans_txt, comm_txt = "", "", ""
      for j in range(max(0, i - 4), i):
        jl, jb = blocks[j][0].strip(), blocks[j][1].strip()
        if jl == "मूलम्":
          mula_txt = jb
        elif jl in ("त्रिभुवनः", "Keith"):
          trans_txt = jb
      for j in range(i + 1, min(len(blocks), i + 3)):
        jl, jb = blocks[j][0].strip(), blocks[j][1].strip()
        if "टीका" in jl or "भाष्य" in jl:
          comm_txt = jb
          break
      if not mula_txt or len(mula_txt) > 600 or len(body.strip()) > 1800:
        continue
      lex_hits = retrieve_accent_candidates(mula_txt)
      u_prompt = format_padapatha_user_prompt(
        mula_txt,
        commentary_text=comm_txt,
        translation_text=trans_txt,
        lexicon_hits=lex_hits,
      )
      target_blk = f"<details><summary>{ls}</summary>\n\n{body.strip()}\n</details>"
      padapatha_ex.append(_msg_record(PADAPATHA_ACCENT_SYSTEM_PROMPT, u_prompt, target_blk, "padapatha_accent"))

  rng.shuffle(interleave_ex)
  rng.shuffle(padapatha_ex)
  return interleave_ex[:interleave_limit], padapatha_ex[:padapatha_limit]


def build_sft_datasets(
  out_dir: str,
  *,
  seed: int = 42,
  vedic_root: str = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content",
) -> dict[str, int]:
  """Build ``train.jsonl`` and ``eval.jsonl`` under ``out_dir`` and return counts."""
  os.makedirs(out_dir, exist_ok=True)
  rng = random.Random(seed)

  ra_train_files, ra_eval_files = _collect_ra_files()

  # Collect curated Vedic files (holding out last 15% deterministically by path)
  vedic_all: list[str] = []
  if os.path.isdir(vedic_root):
    for dp, dns, fns in os.walk(vedic_root):
      dns.sort()
      for fn in sorted(fns):
        if not fn.endswith(".md") or fn == "_index.md":
          continue
        fp = os.path.join(dp, fn)
        try:
          head = open(fp, encoding="utf-8", errors="ignore").read(12000)
        except OSError:
          continue
        if "पद-पाठः (यान्त्रिकः" in head or "विनियोगः</summary>" in head or "अवतारिका</summary>" in head:
          vedic_all.append(fp)

  split_pt = max(1, int(len(vedic_all) * 0.85))
  vedic_train = vedic_all[:split_pt]
  vedic_eval = vedic_all[split_pt:]

  # Build TRAIN split (~3,000 high-signal examples across all skills)
  train_recs: list[dict] = []
  train_recs.extend(
    _extract_proofreading_examples(
      ra_train_files, rng, max_vp_pairs=950, max_sug_blocks=650, max_clause_pairs=300
    )
  )
  train_recs.extend(_extract_structural_and_mixed_examples(ra_train_files, rng, limit=250))
  train_recs.extend(_extract_translation_matcher_examples(ra_train_files + vedic_train[:60], rng, limit=300))
  il_train, pp_train = _extract_interleaver_and_padapatha_examples(
    ra_train_files, vedic_train, rng, interleave_limit=280, padapatha_limit=260
  )
  train_recs.extend(il_train)
  train_recs.extend(pp_train)
  rng.shuffle(train_recs)

  # Build strictly HELD-OUT EVAL split (~240 examples)
  eval_recs: list[dict] = []
  eval_recs.extend(
    _extract_proofreading_examples(
      ra_eval_files, rng, max_vp_pairs=80, max_sug_blocks=30, max_clause_pairs=30
    )
  )
  eval_recs.extend(_extract_structural_and_mixed_examples(ra_eval_files, rng, limit=30))
  eval_recs.extend(_extract_translation_matcher_examples(ra_eval_files + vedic_eval[:20], rng, limit=30))
  il_eval, pp_eval = _extract_interleaver_and_padapatha_examples(
    ra_eval_files, vedic_eval, rng, interleave_limit=30, padapatha_limit=30
  )
  eval_recs.extend(il_eval)
  eval_recs.extend(pp_eval)

  train_path = os.path.join(out_dir, "train.jsonl")
  eval_path = os.path.join(out_dir, "eval.jsonl")
  with open(train_path, "w", encoding="utf-8") as f:
    for r in train_recs:
      f.write(json.dumps(r, ensure_ascii=False) + "\n")
  with open(eval_path, "w", encoding="utf-8") as f:
    for r in eval_recs:
      f.write(json.dumps(r, ensure_ascii=False) + "\n")

  summary: dict[str, int] = {"train_total": len(train_recs), "eval_total": len(eval_recs)}
  for r in train_recs:
    k = f"train_{r['task_type']}"
    summary[k] = summary.get(k, 0) + 1
  for r in eval_recs:
    k = f"eval_{r['task_type']}"
    summary[k] = summary.get(k, 0) + 1

  with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)
  return summary


if __name__ == "__main__":
  import argparse

  ap = argparse.ArgumentParser(description="Build Sanskrit Proofreader/Interleaver SFT JSONL dataset.")
  ap.add_argument("--out-dir", required=True)
  ap.add_argument("--seed", type=int, default=42)
  args = ap.parse_args()
  stats = build_sft_datasets(args.out_dir, seed=args.seed)
  print(json.dumps(stats, indent=2, ensure_ascii=False))
