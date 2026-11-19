"""SFT extractors for ``translation_matcher``, ``commentary_interleaver``, and ``padapatha_accent``."""
from __future__ import annotations

import json
import os
import random
import string
import regex

from doc_curation.llm.proofreader.accent_helper import (
  format_padapatha_user_prompt,
  retrieve_accent_candidates,
)
from doc_curation.llm.proofreader.interleave_helper import (
  annotate_translation_matcher_prompt,
  format_interleave_prompt,
  split_quote_safe_segments,
)
from doc_curation.llm.proofreader.prompts import (
  INTERLEAVER_SYSTEM_PROMPT,
  PADAPATHA_ACCENT_SYSTEM_PROMPT,
)
from .text_normalizer import DETAILS_RE, msg_record


def extract_translation_matcher_examples(files: list[str], rng: random.Random, limit: int) -> list[dict]:
  from doc_curation.llm.translation_matcher import _canon_text, _prompt_for_batch

  examples: list[dict] = []
  for fp in files:
    try:
      blocks = DETAILS_RE.findall(open(fp, encoding="utf-8").read())
    except OSError:
      continue
    clusters: list[tuple[str, str]] = []
    last_trans = ""
    for lbl, body in blocks:
      ls = lbl.strip()
      if ls in ("Thibaut", "Keith", "त्रिभुवनः", "P.R.Ramachander"):
        b_clean = regex.sub(r"^\d+\\\.\s*", "", regex.sub(r"\n\[[A-Za-z0-9_]+\]:.*", "", body.strip()))
        last_trans = _canon_text(b_clean)
      elif ls == "मूलम्":
        core = regex.sub(r"\s+", " ", body.strip())
        if core:
          clusters.append((core, last_trans))
        last_trans = ""
    if len(clusters) < 5:
      continue

    for start in range(0, len(clusters) - 4, 5):
      batch_sz = rng.randint(4, min(7, len(clusters) - start))
      batch = clusters[start:start + batch_sz]
      upcoming = clusters[start + batch_sz:start + batch_sz + 2]
      if sum(1 for _, en in batch if en) < 3:
        continue
      en_pieces, starts_map, skips, word_cursor = [], {}, [], 0
      for offset, (_, en_txt) in enumerate(batch):
        g_idx = start + offset
        starts_map[str(g_idx)] = word_cursor
        w = en_txt.split() if en_txt else []
        if not w:
          skips.append(g_idx)
        else:
          en_pieces.append(en_txt)
          word_cursor += len(w)
      next_en = word_cursor
      if upcoming and rng.random() < 0.65:
        en_pieces.extend(up_en for _, up_en in upcoming if up_en)
      en_words_list = " ".join(en_pieces).split()
      if not (10 <= len(en_words_list) <= 320):
        continue
      up_tuple = (start + batch_sz, [c for c, _ in upcoming]) if upcoming else None
      raw_prompt = _prompt_for_batch(
        [c for c, _ in batch],
        start,
        en_words_list,
        0,
        len(clusters),
        max(len(en_words_list), int(len(en_words_list) * len(clusters) / max(1, batch_sz))),
        prev_text=None,
        upcoming=up_tuple,
      )
      u_prompt = annotate_translation_matcher_prompt(raw_prompt)
      gold = json.dumps({"starts": starts_map, "skip": skips, "next_en": next_en}, ensure_ascii=False)
      examples.append({"task_type": "translation_matcher", "messages": [{"role": "user", "content": u_prompt}, {"role": "assistant", "content": gold}]})
      if len(examples) >= limit * 2:
        break
    if len(examples) >= limit * 2:
      break
  rng.shuffle(examples)
  return examples[:limit]


def _parse_role_clusters(blocks: list[tuple[str, str]]) -> list[dict]:
  clusters, pending_top, cur = [], [], None
  for lbl, body in blocks:
    ls, bs = lbl.strip(), body.strip()
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
      (cur["items"] if cur is not None else pending_top).append(("note", bs))
    elif ls == "मूलम्":
      if cur is not None:
        clusters.append(cur)
      cur = {"mula": bs, "items": list(pending_top)}
      pending_top = []
    elif ls == "विनियोगसङ्ग्रहः" and cur is not None:
      cur["items"].append(("viniyoga_sangraha", bs))
    elif cur is not None and any(k in ls for k in ("टीका", "श्रुत-प्रकाशिका", "भाष्यम्")):
      sents = split_quote_safe_segments(bs)
      if 1 <= len(sents) <= 8:
        cur["items"].extend(("tika", s) for s in sents)
      elif len(sents) > 8:
        # Merge adjacent pairs to keep coherent multi-clause chunks without midpoint slicing
        for k in range(0, len(sents), 2):
          cur["items"].append(("tika", " ".join(sents[k:k + 2])))
      clusters.append(cur)
      cur = None
  if cur is not None:
    clusters.append(cur)
  return [c for c in clusters if c["items"] and len(c["mula"]) <= 600]


def extract_commentary_interleaver_examples(sources: list[str], rng: random.Random, limit: int) -> list[dict]:
  shuffled = list(sources)
  rng.shuffle(shuffled)
  out: list[dict] = []
  for fp in shuffled:
    if len(out) >= limit * 2:
      break
    try:
      usable = _parse_role_clusters(DETAILS_RE.findall(open(fp, encoding="utf-8").read()))
    except OSError:
      continue
    for st in range(0, len(usable) - 1, 3):
      win_end = st + rng.randint(2, min(4, len(usable) - st))
      window = usable[st:win_end]
      upcoming = [u["mula"] for u in usable[win_end:win_end + 2]]
      tail = usable[win_end]["items"][:2] if (upcoming and rng.random() < 0.45) else []
      segs, assignments = [], []
      for c_idx, w in enumerate(window):
        for role, seg_txt in w["items"]:
          if len(seg_txt) <= 700:
            assignments.append({"seg": len(segs), "core": c_idx, "role": role})
            segs.append(seg_txt)
      unmatched_from = len(segs)
      segs.extend(t for _, t in tail if len(t) <= 700)
      if 2 <= len(assignments) and len(segs) <= 16:
        u_p = format_interleave_prompt(
          [w["mula"] for w in window],
          segs,
          upcoming_cores=upcoming,
          author_label=("भट्टभास्कर-टीका" if "vedAH" in fp else "श्रुत-प्रकाशिका"),
          is_sarvash_tikah=("sarvASh_TIkAH" in fp),
          include_hints=True,
        )
        ans = json.dumps({"assignments": assignments, "unmatched_from": unmatched_from}, ensure_ascii=False)
        out.append(msg_record(INTERLEAVER_SYSTEM_PROMPT, u_p, ans, "commentary_interleaver"))
  rng.shuffle(out)
  return out[:limit]


def extract_padapatha_examples(vedic_files: list[str], rng: random.Random, limit: int) -> list[dict]:
  out: list[dict] = []
  for fp in vedic_files:
    if len(out) >= limit * 2:
      break
    try:
      txt = open(fp, encoding="utf-8").read()
    except OSError:
      continue
    if "पद-पाठः (यान्त्रिकः" not in txt:
      continue
    blocks = DETAILS_RE.findall(txt)
    for i, (lbl, body) in enumerate(blocks):
      ls = lbl.strip()
      if not ls.startswith("पद-पाठः (यान्त्रिकः"):
        continue
      mula = next((blocks[j][1].strip() for j in range(i - 1, max(-1, i - 5), -1) if blocks[j][0].strip() == "मूलम्"), "")
      trans = next((blocks[j][1].strip() for j in range(max(0, i - 4), i) if blocks[j][0].strip() in ("त्रिभुवनः", "Keith")), "")
      comm = next((blocks[j][1].strip() for j in range(i + 1, min(len(blocks), i + 3)) if "टीका" in blocks[j][0] or "भाष्य" in blocks[j][0]), "")
      if mula and len(mula) <= 600 and len(body.strip()) <= 1800:
        u_p = format_padapatha_user_prompt(mula, commentary_text=comm, translation_text=trans, lexicon_hits=retrieve_accent_candidates(mula))
        out.append(msg_record(PADAPATHA_ACCENT_SYSTEM_PROMPT, u_p, f"<details><summary>{ls}</summary>\n\n{body.strip()}\n</details>", "padapatha_accent"))
  rng.shuffle(out)
  return out[:limit]
