"""Proofreading, hyphenation, clause-newline, and structural SFT extractors.

Rebalanced for v5 so ~80%+ of prose examples use ``clause_newlines=True`` with
genuine multi-line clause/sentence ``  \\n`` soft breaks (never pairing unsplit
long multi-clause single-line prose with ``clause_newlines=True``), while keeping
~15-20% explicit ``clause_newlines=False`` contrastive examples and rich 1-2 typo
``[[OLD|NEW]]`` density across both multi-line and short passages.
"""
from __future__ import annotations

import random
import regex
from indic_transliteration.sanscript.schemes.brahmic import accent

from doc_curation.llm.proofreader.guards import wrap_silent_mutations
from doc_curation.llm.proofreader.prompts import build_system_prompt
from .text_normalizer import (
  ANY_ACCENT_RE,
  DETAILS_RE,
  MANIPRAVALA_RE,
  SUG_SPAN_RE,
  SYNTHETIC_CFG,
  clean_prastuti_target,
  collapse_prose_soft_breaks,
  has_meaningful_prose_clause_breaks,
  inject_realistic_ocr_typo,
  is_verse_block,
  msg_record,
  skeleton_old_side,
  unsplit_sanskrit_to_raw,
)


def _ensure_soft_breaks(para: str) -> str:
  lines = para.splitlines()
  return "\n".join(
    (l.rstrip() + "  ") if i < len(lines) - 1 and l.strip() else l.rstrip()
    for i, l in enumerate(lines)
  )


def _process_vp_mula_pair(
  body: str,
  mula_body: str,
  rng: random.Random,
  vp_out: list[dict],
  sug_out: list[dict],
  clause_on_out: list[dict],
  clause_off_out: list[dict],
  idem_out: list[dict],
  limits: tuple[int, int, int, int],
) -> None:
  max_vp, max_sug, max_cl_on, max_cl_off = limits
  if MANIPRAVALA_RE.search(mula_body) or MANIPRAVALA_RE.search(body):
    return
  target = clean_prastuti_target(body)
  if not target or len(target) > 2200:
    return
  if "**" not in mula_body and "**" in target:
    target = target.replace("**", "")

  mula_acc, tgt_acc = bool(ANY_ACCENT_RE.search(mula_body)), bool(ANY_ACCENT_RE.search(target))
  if tgt_acc and not mula_acc:
    return
  if mula_acc and "\u1cd3" in target and ("\u0951" in mula_body or "\u0952" in mula_body):
    mula_in = accent.to_US_accents(mula_body, pauses=r"[।॥,;]+")
  elif not tgt_acc and mula_acc:
    mula_in = accent.strip_accents(mula_body)
  else:
    mula_in = mula_body

  skel_m = skeleton_old_side(mula_in.replace("*", ""))
  skel_t = skeleton_old_side(target.replace("*", ""))
  if not skel_m or abs(len(skel_m) - len(skel_t)) > max(4, int(0.06 * len(skel_m))):
    return

  target_wrapped = target if skel_m == skel_t else wrap_silent_mutations(mula_in, target, allow_suggestions=True)
  variant = rng.randint(0, 5)
  if has_meaningful_prose_clause_breaks(target_wrapped):
    soft_tgt = _ensure_soft_breaks(target_wrapped)
    if len(clause_on_out) < max_cl_on * 2:
      clause_on_out.append(msg_record(build_system_prompt(clause_newlines=True, variant=variant), mula_in, soft_tgt, "clause_newlines_on"))
    # Inject OCR typos directly into multi-line clause-broken blocks so [[OLD|NEW]] & clause breaks reinforce each other!
    if "[[" not in soft_tgt and len(sug_out) < max_sug * 2 and rng.random() < 0.65:
      inj = inject_realistic_ocr_typo(soft_tgt, rng)
      if inj:
        sug_out.append(msg_record(build_system_prompt(clause_newlines=True, suggest_corrections=True, variant=variant + 2), inj[0], inj[1], "proofread_suggestions"))
    if len(clause_off_out) < max_cl_off * 2 and rng.random() < 0.35:
      inline_only = collapse_prose_soft_breaks(soft_tgt, fuse_newline_sandhi_prob=1.0, rng=rng)
      clause_off_out.append(msg_record(build_system_prompt(clause_newlines=False, variant=variant + 1), mula_in, inline_only, "clause_newlines_off"))
    return

  is_v = is_verse_block(target_wrapped)
  norm_tgt = _ensure_soft_breaks(target_wrapped) if is_v else collapse_prose_soft_breaks(target_wrapped)
  # Only pair with clause_newlines=True if it is a verse OR a genuinely short single-clause sentence (<= 80 chars, <= 1 danda)!
  is_short_single_clause = (not is_v) and len(norm_tgt) <= 80 and norm_tgt.count("।") <= 1
  if is_v or is_short_single_clause:
    has_sug = "[[" in norm_tgt
    sys_p = build_system_prompt(clause_newlines=True, suggest_corrections=(True if has_sug else rng.random() < 0.8), variant=variant)
    vp_out.append(msg_record(sys_p, mula_in, norm_tgt, "proofread_vp"))
    if not has_sug and len(sug_out) < max_sug * 2 and rng.random() < 0.35:
      inj = inject_realistic_ocr_typo(norm_tgt, rng)
      if inj:
        sug_out.append(msg_record(build_system_prompt(clause_newlines=True, suggest_corrections=True, variant=variant + 2), inj[0], inj[1], "proofread_suggestions"))
    if not has_sug and rng.random() < 0.15 and len(idem_out) < max(30, max_vp // 6):
      idem_out.append(msg_record(sys_p, norm_tgt, norm_tgt, "idempotence"))
  elif len(clause_off_out) < max_cl_off * 2:
    # Long un-broken prose goes strictly under clause_newlines=False, NEVER polluting clause_newlines=True!
    clause_off_out.append(msg_record(build_system_prompt(clause_newlines=False, variant=variant), mula_in, norm_tgt, "clause_newlines_off"))


def _process_commentary_block(
  body: str,
  rng: random.Random,
  sug_out: list[dict],
  clause_on_out: list[dict],
  clause_off_out: list[dict],
  max_sug: int,
  max_cl_on: int,
  max_cl_off: int,
) -> None:
  if MANIPRAVALA_RE.search(body):
    return
  cleaned = clean_prastuti_target(body)
  if not (40 <= len(cleaned) <= 2200):
    return
  cleaned = SUG_SPAN_RE.sub(lambda m: m.group(2) if m.group(1).strip() == m.group(2).strip() else m.group(0), cleaned)
  for para in regex.split(r"\n\s*\n", cleaned):
    para = para.strip()
    if not (40 <= len(para) <= 1500):
      continue
    has_cl = has_meaningful_prose_clause_breaks(para)
    soft_para = _ensure_soft_breaks(para) if has_cl else para
    if "[[" in soft_para and len(sug_out) < max_sug * 2:
      # Only pair single-line commentary with clause_newlines=False so clause_newlines=True stays pure!
      raw_in = unsplit_sanskrit_to_raw(soft_para, rng, revert_suggestions_to_old=True, collapse_clause_newlines=True)
      sug_out.append(msg_record(build_system_prompt(clause_newlines=has_cl, suggest_corrections=True, variant=rng.randint(0, 5)), raw_in, soft_para, "proofread_suggestions"))
    elif has_cl:
      v = rng.randint(0, 5)
      raw_in = unsplit_sanskrit_to_raw(soft_para, rng, revert_suggestions_to_old=True, collapse_clause_newlines=True, hard_wrap_prob=0.3)
      if len(clause_on_out) < max_cl_on * 2:
        clause_on_out.append(msg_record(build_system_prompt(clause_newlines=True, variant=v), raw_in, soft_para, "clause_newlines_on"))
      if len(sug_out) < max_sug * 2 and rng.random() < 0.70:
        inj = inject_realistic_ocr_typo(soft_para, rng)
        if inj:
          sug_out.append(msg_record(build_system_prompt(clause_newlines=True, suggest_corrections=True, variant=v + 2), inj[0], inj[1], "proofread_suggestions"))
      if len(clause_off_out) < max_cl_off * 2 and rng.random() < 0.25:
        inline_tgt = collapse_prose_soft_breaks(soft_para, fuse_newline_sandhi_prob=1.0, rng=rng)
        clause_off_out.append(msg_record(build_system_prompt(clause_newlines=False, variant=v + 1), raw_in, inline_tgt, "clause_newlines_off"))


def extract_proofreading_examples(
  files: list[str],
  rng: random.Random,
  *,
  max_vp_pairs: int,
  max_sug_blocks: int,
  max_clause_on: int,
  max_clause_off: int,
) -> list[dict]:
  vp_ex, sug_ex, cl_on_ex, cl_off_ex, idem_ex = [], [], [], [], []
  shuffled = list(files)
  rng.shuffle(shuffled)
  for fp in shuffled:
    try:
      blocks = DETAILS_RE.findall(open(fp, encoding="utf-8").read())
    except OSError:
      continue
    for i, (lbl, body) in enumerate(blocks):
      ls = lbl.strip()
      if ls.startswith("विश्वास-प्रस्तुतिः"):
        mula = next((blocks[j][1].strip() for j in range(i + 1, min(i + 5, len(blocks))) if blocks[j][0].strip() == "मूलम्"), None)
        if mula and len(mula) >= 25:
          _process_vp_mula_pair(body, mula, rng, vp_ex, sug_ex, cl_on_ex, cl_off_ex, idem_ex, (max_vp_pairs, max_sug_blocks, max_clause_on, max_clause_off))
      if any(ls.startswith(k) for k in ("श्रुत-प्रकाशिका", "विश्वास-टिप्पनी", "नीलमेघः (सं)")):
        _process_commentary_block(body, rng, sug_ex, cl_on_ex, cl_off_ex, max_sug_blocks, max_clause_on, max_clause_off)
  for lst in (vp_ex, sug_ex, cl_on_ex, cl_off_ex):
    rng.shuffle(lst)
  return vp_ex[:max_vp_pairs] + sug_ex[:max_sug_blocks] + cl_on_ex[:max_clause_on] + cl_off_ex[:max_clause_off] + idem_ex


def extract_structural_and_mixed_examples(files: list[str], rng: random.Random, limit: int) -> list[dict]:
  en_paras, sa_paras = [], []
  for fp in files:
    try:
      blocks = DETAILS_RE.findall(open(fp, encoding="utf-8").read())
    except OSError:
      continue
    for lbl, body in blocks:
      ls, bs = lbl.strip(), body.strip()
      if ls in ("Thibaut", "P.R.Ramachander") and 80 <= len(bs) <= 600:
        en_paras.append(regex.sub(r"\s+", " ", bs))
      elif ls.startswith("विश्वास-प्रस्तुतिः") and 30 <= len(bs) <= 220 and not MANIPRAVALA_RE.search(bs):
        tgt = clean_prastuti_target(bs).replace("**", "")
        if tgt and "[[" not in tgt and "\n\n" not in tgt:
          sa_paras.append((unsplit_sanskrit_to_raw(tgt, rng, hard_wrap_prob=0.0), _ensure_soft_breaks(tgt)))
    if len(en_paras) >= limit and len(sa_paras) >= limit * 2:
      break

  rng.shuffle(en_paras)
  rng.shuffle(sa_paras)
  examples: list[dict] = []
  ias_pairs, iast_typos = SYNTHETIC_CFG["iast_compounds"], SYNTHETIC_CFG["iast_typos"]

  for idx in range(min(limit // 3, len(en_paras))):
    raw_c, hyp_c = rng.choice(ias_pairs)
    if rng.random() < 0.6:
      bad_t, good_t = rng.choice(iast_typos)
      inp = f"{en_paras[idx]} This doctrine of {raw_c} and {bad_t} is central here."
      out = f"{en_paras[idx]} This doctrine of {hyp_c} and [[{bad_t}|{good_t}]] is central here."
    else:
      inp = f"{en_paras[idx]} Compare the expression {raw_c} in the commentary."
      out = f"{en_paras[idx]} Compare the expression {hyp_c} in the commentary."
    examples.append(msg_record(build_system_prompt(clause_newlines=True, variant=idx), inp, out, "embedded_iast"))

  dev_digits = str.maketrans("0123456789", "०१२३४५६७८९")
  for idx in range(min(limit // 2, len(sa_paras) - 1)):
    (raw1, tgt1), (raw2, tgt2) = sa_paras[idx], sa_paras[idx + 1]
    sys_p = build_system_prompt(clause_newlines=True, markdown_cleanup=True, variant=idx)
    mode = idx % 5
    if mode == 0:
      pno = rng.randint(12, 240)
      examples.append(msg_record(sys_p, f"{raw1}\n{str(pno).translate(dev_digits)}\n{raw2}", f"{tgt1} [[P{pno}]]  \n{tgt2}", "page_marker"))
    elif mode == 1:
      garb = rng.choice(SYNTHETIC_CFG["illegible_markers"])
      examples.append(msg_record(sys_p, f"{raw1} {garb} {raw2}", f"{tgt1} [[??]]  \n{tgt2}", "illegible_marker"))
    elif mode == 2:
      inp = f"<!-- Proofreader-DETAIL-SPLIT 0001 -->\n{raw1}\n\n<<MULAM_0000>>\n\n<!-- Proofreader-DETAIL-SPLIT 0002 -->\n{raw2}"
      out = f"<!-- Proofreader-DETAIL-SPLIT 0001 -->\n{tgt1}\n\n<<MULAM_0000>>\n\n<!-- Proofreader-DETAIL-SPLIT 0002 -->\n{tgt2}"
      examples.append(msg_record(sys_p, inp, out, "marker_preservation"))
    elif mode == 3:
      pno = rng.randint(10, 95)
      examples.append(msg_record(sys_p, f"[[P{pno}]] {raw1}*\n\n* {raw2}", f"[[P{pno}]] {tgt1}[^{pno}_1]\n\n[^{pno}_1]: {tgt2}", "footnote_format"))
    else:
      if raw1.endswith("।") and tgt1.endswith("।") and "॥" not in raw1:
        examples.append(msg_record(sys_p, f"{raw1[:-1].rstrip()} {raw2}", f"{tgt1}  \n{tgt2}", "missing_danda_sentence_break"))
  return examples[:limit]
