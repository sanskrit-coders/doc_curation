"""VSM block aligner, SSU 1978 Sāyaṇa parser, SSU 2011 Vol 4 Ānandabodha parser, and Indike fallback."""
from __future__ import annotations

import json
import pathlib
import re
from collections import defaultdict
from typing import Callable

from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import _DEV_ORDINALS_CH
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.padapatha import _subsequence_ratio
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.repair import _norm_skel
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.vsm_ocr import (
  _is_mula_line,
  _is_padapatha_line,
  clean_drive_ocr_markdown,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina.samhitaa import bhashya_aligner

_TAG_1978_RE = re.compile(
  r"\[\s*[-–—]?\s*अ[०॰]\s*([०-९]+)\s*[।|.]\s*([०-९]+)\s*[।|.]\s*([०-९]+)(?:\s*[-–]\s*([०-९]+))?\s*\]"
)


def _split_multi_mantra_gloss(block_text: str, kandikas: list[dict]) -> list[str]:
  """Distribute a combined commentary block across multiple consecutive kaṇḍikās `[k1..kN]` cleanly."""
  n = len(kandikas)
  if n == 0:
    return []
  if n == 1 or not block_text.strip():
    return [block_text.strip()] + [""] * (n - 1) if block_text.strip() else [""] * n
  segs = bhashya_aligner._split_ka_sentences(block_text)
  if len(segs) <= 1:
    return [block_text.strip()] + [""] * (n - 1)
  mulas = [k["mula_full"] for k in kandikas]
  assigned = bhashya_aligner._assign_segments_to_submantras(segs, mulas, author="kanva")
  return [" ".join(item["text"] for item in grp).strip() for grp in assigned]


def _expand_bhashya_span(
  span_src: str,
  start_i: int,
  kandikas: list[dict],
  k_skels: list[str],
  *,
  max_extra: int,
  require_overlap: bool = True,
) -> int:
  """Expand a multi-mantra block end index monotonically across overlapping kaṇḍikās."""
  end_i = start_i + 1
  n_k = len(kandikas)
  if span_src and len(_norm_skel(span_src)) > int(1.35 * len(k_skels[start_i])):
    s_sk = _norm_skel(span_src)
    acc_len = len(k_skels[start_i])
    while (
      end_i < min(n_k, start_i + max_extra)
      and len(s_sk) > acc_len + int(0.50 * len(k_skels[end_i]))
      and (not require_overlap or bhashya_aligner.pratika_overlap_score(span_src, kandikas[end_i]["mula_full"]) >= 0.45)
    ):
      acc_len += len(k_skels[end_i])
      end_i += 1
  return end_i


def _align_vsm_unanchored_block(
  blk: dict,
  k_cursor: int,
  kandikas: list[dict],
  authors: tuple[str, ...],
  out: dict[int, dict[str, str]],
) -> tuple[int, int, bool]:
  """Determine `(start_i, end_i, anuvaka_summary_only)` for a VSM block without Mūlam/Padapāṭha anchor."""
  n_k = len(kandikas)
  a_text = " ".join(line for a in authors for line in blk[a])
  prev_idx = max(0, k_cursor - 1)
  prev_k = kandikas[prev_idx]["k"]
  is_anu_trans = "नुवाक" in a_text or "उक्ताः" in a_text
  if k_cursor > 0 and not blk["pada_lines"]:
    if any(blk[a] and not out[prev_k][a] for a in authors) or is_anu_trans:
      ov_prev = bhashya_aligner.pratika_overlap_score(a_text[:250], kandikas[prev_idx]["mula_full"])
      ov_next = bhashya_aligner.pratika_overlap_score(a_text[:250], kandikas[min(n_k - 1, k_cursor)]["mula_full"]) if k_cursor < n_k else 0.0
      if is_anu_trans and k_cursor < n_k and not re.search(r"इति\s+.*नुवाकः\s*[।॥]*\s*$", a_text):
        return k_cursor, k_cursor + 1, True
      if ov_prev >= ov_next or is_anu_trans:
        return prev_idx, prev_idx + 1, False
  best_i, best_ov = min(n_k - 1, k_cursor), 0.0
  for idx in range(max(0, k_cursor - 1), min(n_k, k_cursor + 2)):
    ov = bhashya_aligner.pratika_overlap_score(a_text[:250], kandikas[idx]["mula_full"])
    if ov > best_ov:
      best_ov, best_i = ov, idx
  if best_ov >= 0.40:
    return best_i, best_i + 1, False
  fallback_i = prev_idx if k_cursor > 0 else 0
  return fallback_i, fallback_i + 1, False


def align_vsm_blocks_to_kandikas(
  ch: int,
  blocks: list[dict],
  kandikas: list[dict],
  authors: tuple[str, ...],
) -> dict[int, dict[str, str]]:
  """Align parsed VSM chapter blocks monotonically to kaṇḍikā numbers `1..len(kandikas)`."""
  out: dict[int, dict[str, str]] = defaultdict(lambda: {"pada": "", "sayana": "", "anandabodha": "", "anantacharya": ""})
  n_k, k_skels, k_cursor = len(kandikas), [_norm_skel(k["mula_full"]) for k in kandikas], 0
  leading_av: dict[str, list[str]] = defaultdict(list)

  for blk in blocks:
    mula_src = " ".join(l for l in blk["raw_lines"] if re.search(r"[॒॑]", l)).strip()
    pada_src = " ".join(blk["pada_lines"]).strip()
    anchor_src = mula_src if len(_norm_skel(mula_src)) >= 8 else re.sub(r"\S+इति\s+\S+", "", pada_src.replace("।", " "))
    end_nums = [
      x for x in (bhashya_aligner.dev_to_int(m.group(1)) for m in re.finditer(r"॥\s*([०-९]{1,3})\s*॥", mula_src or pada_src))
      if x is not None and 1 <= x <= n_k
    ]
    a_sk = _norm_skel(anchor_src)
    if not a_sk and not blk["pada_lines"] and k_cursor == 0:
      for a in authors:
        if blk[a]:
          leading_av[a].append("\n".join(blk[a]))
      continue

    anuvaka_summary_only = False
    if not a_sk:
      start_i, end_i, anuvaka_summary_only = _align_vsm_unanchored_block(blk, k_cursor, kandikas, authors, out)
    else:
      best_si, best_sc = min(n_k - 1, k_cursor), -1.0
      for idx in range(max(0, k_cursor - 1), min(n_k, k_cursor + 8)):
        raw_ov = bhashya_aligner.pratika_overlap_score(anchor_src[:220], kandikas[idx]["mula_full"])
        if len(a_sk) >= 10 and k_skels[idx]:
          raw_ov = max(raw_ov, 0.85 * _subsequence_ratio(a_sk[:120], k_skels[idx]))
        if idx >= k_cursor + 2 and raw_ov < 0.72:
          continue
        sc = raw_ov + (0.12 if idx == k_cursor else (0.03 if idx == k_cursor + 1 else (-0.08 * (idx - k_cursor) if idx > k_cursor + 1 else 0.0)))
        if sc > best_sc:
          best_sc, best_si = sc, idx
      start_i = best_si
      end_i = _expand_bhashya_span(mula_src, start_i, kandikas, k_skels, max_extra=20, require_overlap=True)
      if (
        end_i == start_i + 1
        and len(end_nums) >= 2 and end_nums[0] == start_i + 1 and end_nums[-1] <= min(n_k, start_i + 20)
        and bhashya_aligner.pratika_overlap_score(mula_src or pada_src, kandikas[end_nums[-1] - 1]["mula_full"]) >= 0.40
      ):
        end_i = max(end_i, end_nums[-1])

    if not anuvaka_summary_only:
      k_cursor = min(n_k, max(k_cursor, end_i))
    span_kandikas = kandikas[start_i:end_i]
    if pada_src:
      for kr in span_kandikas:
        k_num = kr["k"]
        if len(span_kandikas) == 1:
          out[k_num]["pada"] = f"{out[k_num]['pada']} {pada_src}".strip()
        elif not out[k_num]["pada"]:
          out[k_num]["pada"] = pada_src
    for a in authors:
      raw_a = "\n".join(blk[a]).strip()
      if raw_a:
        pieces = [raw_a] if len(span_kandikas) == 1 else _split_multi_mantra_gloss(raw_a, span_kandikas)
        for kr, pc in zip(span_kandikas, pieces):
          out[kr["k"]][a] = f"{out[kr['k']][a]}\n\n{pc or raw_a}".strip()

  if leading_av and kandikas:
    k1 = kandikas[0]["k"]
    for a, chunks in leading_av.items():
      out[k1][a] = f"{chr(10).join(chunks)}\n\n{out[k1][a]}".strip()
  return dict(out)


def _slice_chapter_colophons(
  body: list[str],
  ch_range: range,
  is_colophon: Callable[[str], bool],
  next_hdr_re_fn: Callable[[int], re.Pattern[str]],
  label: str,
) -> dict[int, list[str]]:
  """Slice `body` across `ch_range` by matching closing chapter colophon or next-chapter header."""
  slices: dict[int, list[str]] = {}
  pos, last_ch = 0, ch_range.stop - 1
  for ch in ch_range:
    if ch == last_ch:
      slices[ch] = body[pos:]
      break
    next_re = next_hdr_re_fn(ch + 1)
    end_j = None
    for j in range(pos + 20, len(body)):
      if is_colophon(body[j]):
        end_j = j + 1
        break
      if next_re.match(body[j]):
        end_j = j
        break
    if end_j is None:
      raise RuntimeError(f"Could not find end of {label} Ch {ch}")
    slices[ch] = body[pos:end_j]
    pos = end_j
  return slices


def _segment_ssu1978_chapter(ch_lines: list[str]) -> list[dict]:
  """Tokenize & segment one SSU 1978 chapter's lines into raw `{mula, pada, comm, end_tags}` dicts."""
  proc_lines: list[tuple[str, str]] = []
  for ln in ch_lines:
    if re.match(r"^[०-९\d]+\.\s+.*उ\.?\s*म्यु", ln):
      continue
    m_tag, rem = _TAG_1978_RE.search(ln), ln
    if m_tag:
      if ln[: m_tag.start()].strip():
        proc_lines.append(("line", ln[: m_tag.start()].strip()))
      proc_lines.append(("tag", m_tag.group(0)))
      rem = ln[m_tag.end() :].strip()
    if not rem:
      continue
    m_p = re.search(r"((?:तत्)?पाठस्तु\s*[-–—:]*\s*)(?![\"'‘“])([^\n]+)$", rem)
    if m_p and re.search(r"[॒॑]", m_p.group(2)):
      pre, rhs = rem[: m_p.start()].strip(), m_p.group(2).strip()
      if pre:
        proc_lines.append(("kat" if re.match(r"^कात्यायन", pre) else "line", pre))
      proc_lines.append(("line", rhs))
    else:
      proc_lines.append(("kat" if re.match(r"^कात्यायन", rem) else "line", rem))

  segments: list[dict] = []
  cur = {"mula": [], "pada": [], "comm": [], "end_tags": []}
  for kind, ln in proc_lines:
    if kind == "tag":
      cur["end_tags"].append(ln)
      if cur["mula"] or cur["pada"] or cur["comm"]:
        segments.append(cur)
        cur = {"mula": [], "pada": [], "comm": [], "end_tags": []}
    elif kind == "kat":
      if cur["mula"] or cur["pada"]:
        segments.append(cur)
        cur = {"mula": [], "pada": [], "comm": [], "end_tags": []}
      cur["comm"].append(ln)
    elif _is_padapatha_line(ln):
      if cur["comm"] and cur["pada"]:
        segments.append(cur)
        cur = {"mula": [], "pada": [], "comm": [], "end_tags": []}
      cur["pada"].append(ln)
    elif _is_mula_line(ln):
      if cur["pada"] or (cur["mula"] and cur["comm"]) or any(not re.match(r"^(?:अथ|कात्यायन|इति|[०-९]+\.|[१-९] )", c) for c in cur["comm"]):
        segments.append(cur)
        cur = {"mula": [], "pada": [], "comm": [], "end_tags": []}
      cur["mula"].append(ln)
    else:
      cur["comm"].append(ln)
  if cur["mula"] or cur["pada"] or cur["comm"] or cur["end_tags"]:
    segments.append(cur)
  return segments


def parse_ssu_1978_sayana(
  txt_path: pathlib.Path,
  kandikas_by_ch: dict[int, list[dict]],
) -> dict[tuple[int, int], dict[str, str]]:
  """Parse SSU 1978 [114] (`kANva-saMhitA-bhAShyam.pdf.txt`, Ch 21–40) into `(ch, k) -> {'pada', 'sayana'}`."""
  raw = clean_drive_ocr_markdown(txt_path.read_text(errors="ignore"))
  lines = [
    s for ln in raw.splitlines()
    if (s := ln.strip())
    and not (re.match(r"^(?:Digitized by|CC-0\.|ACC-0\.|शुक्लयजुर्वेद\s*काण्व\s*संहिता|सायणभाष्योपेता|[०-९]{1,4}|\[?\s*[०-९]{1,2}[।|][०-९].*\]?|तुलना\s*[-–—]|पा\.?\s*भे)", s) and "अ०" not in s and "अ॰" not in s)
    and not re.search(r"[A-Za-z]{3,}", s)
  ]
  start_21 = next(i for i, l in enumerate(lines) if "द्वादशाध्यायमारभ्य" in l)
  end_40 = next(
    i + 1 for i, l in enumerate(lines)
    if i > start_21 and "चत्वारिंशोऽध्यायः" in l and "एकोन" not in l and "ऊन" not in l and ("काण्व" in l or "वेदार्थ" in l)
  )
  ch_slices = _slice_chapter_colophons(
    lines[start_21:end_40],
    range(21, 41),
    lambda l: ("काण्वसंहिताभाष्ये" in l or "काण्व संहिताभाष्ये" in l or "वेदार्थप्रकाशे" in l or "वेदार्थप्रकाश" in l) and "ध्याय" in l,
    lambda nxt: re.compile(rf"^अथ\s+(?:{_DEV_ORDINALS_CH[nxt]})ो?ऽ?ध्याय"),
    "SSU 1978",
  )

  results: dict[tuple[int, int], dict[str, str]] = {}
  for ch in range(21, 41):
    kandikas, k_skels, cursor = kandikas_by_ch[ch], [_norm_skel(k["mula_full"]) for k in kandikas_by_ch[ch]], 0
    n_k = len(kandikas)
    for seg in _segment_ssu1978_chapter(ch_slices[ch]):
      c_txt, p_txt, m_txt = "\n".join(seg["comm"]).strip(), " ".join(seg["pada"]).strip(), " ".join(seg["mula"]).strip()
      if (not c_txt and not p_txt and not m_txt) or (not p_txt and not m_txt and len(c_txt) < 25):
        continue
      tag_m, tag_idx = _TAG_1978_RE.search(" ".join(seg["end_tags"]) or c_txt), None
      if tag_m:
        tc, ta, tk = (bhashya_aligner.dev_to_int(tag_m.group(x)) for x in (1, 2, 3))
        if tc == ch and ta and tk:
          tag_idx = next((idx for idx, kr in enumerate(kandikas) if kr["loc"] == f"{tc}.{ta}.{tk}"), None)
      probe = m_txt or re.sub(r"\S+इति\s+\S+", "", p_txt.replace("।", " ")) or c_txt[:220]
      probe_sk = _norm_skel(probe)
      best_i, best_ov, best_raw_ov = min(n_k - 1, cursor), 0.0, 0.0
      for idx in range(max(0, cursor - 2), min(n_k, cursor + 15)):
        ov = bhashya_aligner.pratika_overlap_score(probe, kandikas[idx]["mula_full"])
        if len(probe_sk) >= 10 and k_skels[idx]:
          ov = max(ov, 0.85 * _subsequence_ratio(probe_sk[:120], k_skels[idx]))
        if idx >= cursor + 2 and ov < 0.70 and not (tag_idx == idx and ov >= 0.45):
          continue
        score = ov + (0.08 if idx == cursor else (0.03 if idx == cursor + 1 else -0.06 * max(0, idx - cursor)))
        if tag_idx is not None and abs(idx - tag_idx) <= 1 and ov >= 0.35:
          score += 0.08
        if score > best_ov:
          best_ov, best_raw_ov, best_i = score, ov, idx
      if best_raw_ov >= 0.25 or m_txt or p_txt:
        start_i = best_i if best_raw_ov >= 0.25 else (tag_idx if (tag_idx is not None and cursor <= tag_idx <= cursor + 4) else min(n_k - 1, cursor))
        end_i = _expand_bhashya_span(m_txt or p_txt.replace("।", " "), start_i, kandikas, k_skels, max_extra=12)
        cursor = min(n_k, max(cursor, end_i))
      else:
        start_i = max(0, cursor - 1) if cursor > 0 else 0
        end_i = start_i + 1
      span_kandikas = kandikas[start_i:end_i]
      if p_txt:
        for kr in span_kandikas:
          if bhashya_aligner.pratika_overlap_score(p_txt.replace("।", " "), kr["mula_full"]) >= 0.45:
            rec = results.setdefault((ch, kr["k"]), {"pada": "", "sayana": ""})
            if len(span_kandikas) == 1 or not rec["pada"]:
              rec["pada"] = f"{rec['pada']} {p_txt}".strip() if len(span_kandikas) == 1 else p_txt
      if c_txt:
        pieces = [c_txt] if len(span_kandikas) == 1 else _split_multi_mantra_gloss(c_txt, span_kandikas)
        for kr, pc in zip(span_kandikas, pieces):
          rec = results.setdefault((ch, kr["k"]), {"pada": "", "sayana": ""})
          rec["sayana"] = f"{rec['sayana']}\n\n{pc or c_txt}".strip()
  return results


def parse_ssu_2011_vol4(
  txt_path: pathlib.Path,
  kandikas_by_ch: dict[int, list[dict]],
) -> dict[tuple[int, int], str]:
  """Parse SSU 2011 Vol 4 (`dvivedI_..._4.pdf.txt`, Ch 31–40) into `(ch, k) -> Ānandabodha bhāṣya`."""
  raw = clean_drive_ocr_markdown(txt_path.read_text(errors="ignore"))
  lines = [
    s for ln in raw.splitlines()
    if (s := ln.strip())
    and not re.match(r"^(?:Digitized by|CC-0\.|काण्व\s*संहिता\s*भाष्य\s*संग्रहः?|[०-९]{1,4}|\[?\s*(?:एकत्रिंश|द्वात्रिंश|त्रयस्त्रिंश|चतुस्त्रिंश|पञ्चत्रिंश|षट्त्रिंश|सप्तत्रिंश|अष्टत्रिंश|एकोनचत्वारिंश|चत्वारिंश)ः?.*\]?|(?:आनन्द|आनन्द्व)बोधभट्टोपाध्यायप्रणीतः.*)$", s)
    and not re.match(r"^(?:\(\s*मा[०.]?\s*[^\)]+\)|\[\s*मा[०.]?\s*[^\]]+\])$", s)
    and not re.search(r"[कखगघङचछजझञसाशां]०\s*[।.,]|पाठे|नास्ति\s*[-–]|स्थाने\s*[-–]|इत्यधिकम्", s)
    and not re.match(r"^[०-९\d]+(?:\s*\.\s*|\s+)(?:.*?[क-ह]०|.*?नास्ति|.*?इति)", s)
  ]
  start_31 = next(i for i, l in enumerate(lines) if "एकत्रिंशोऽध्यायः" in l)
  end_prat = next((i for i, l in enumerate(lines) if i > start_31 and "प्रत्यङ्गिरा" in l), len(lines))
  ch_slices = _slice_chapter_colophons(
    lines[start_31:end_prat],
    range(31, 41),
    lambda l: any(kw in l for kw in ("संग्रहे", "सङ्ग्रहे", "संप्रहे", "भाव्यसङ्ग्रहे")) and "ध्याय" in l,
    lambda nxt: re.compile(rf"^[\*\s]*(?:{_DEV_ORDINALS_CH[nxt]})ो?ऽ?ध्याय"),
    "Vol 4",
  )

  results: dict[tuple[int, int], str] = {}
  for ch in range(31, 41):
    kandikas, k_skels, cursor = kandikas_by_ch[ch], [_norm_skel(k["mula_full"]) for k in kandikas_by_ch[ch]], 0
    n_k = len(kandikas)
    entries: list[dict] = []
    cur = {"mula": [], "comm": []}
    for ln in ch_slices[ch]:
      if ("चत्वारिंशोऽध्याय" in ln and "इति" in ln) or "श्रीमदानन्दबोध" in ln or "मन्त्रव्याख्यानभूता" in ln or ln.startswith("* एकत्रिंशाध्याय"):
        continue
      if _is_mula_line(ln, allow_leading_quote=True) and not re.match(r"^\(\s*[कख]०\s*\)", ln):
        if cur["comm"]:
          entries.append(cur)
          cur = {"mula": [], "comm": []}
        cur["mula"].append(ln)
      else:
        cleaned_ln = re.sub(r"इति\s*।\s*\(\s*मा[०.]?\s*[^\)]+\)", "", ln).strip()
        if cleaned_ln and not re.match(r"^\(\s*मा[०.]?\s*[^\)]+\)\s*$", cleaned_ln):
          cur["comm"].append(cleaned_ln)
    if cur["mula"] or cur["comm"]:
      entries.append(cur)
    if len(entries) >= 2 and not entries[0]["mula"] and entries[0]["comm"]:
      entries[1]["comm"] = entries[0]["comm"] + entries[1]["comm"]
      entries = entries[1:]
    for ent in entries:
      m_txt, c_txt = " ".join(ent["mula"]).strip(), "\n".join(ent["comm"]).strip()
      if not c_txt:
        continue
      probe = m_txt or c_txt[:220]
      best_i, best_ov = min(n_k - 1, cursor), 0.0
      for idx in range(max(0, cursor - 1), min(n_k, cursor + 8)):
        score = bhashya_aligner.pratika_overlap_score(probe, kandikas[idx]["mula_full"]) + (0.06 if idx in (cursor, cursor + 1) else 0.0)
        if score > best_ov:
          best_ov, best_i = score, idx
      start_i = best_i if best_ov >= 0.25 else min(n_k - 1, cursor)
      end_i = _expand_bhashya_span(m_txt, start_i, kandikas, k_skels, max_extra=8, require_overlap=False)
      cursor = min(n_k, max(cursor, end_i))
      span_kandikas = kandikas[start_i:end_i]
      pieces = [c_txt] if len(span_kandikas) == 1 else _split_multi_mantra_gloss(c_txt, span_kandikas)
      for kr, pc in zip(span_kandikas, pieces):
        results[(ch, kr["k"])] = f"{results.get((ch, kr['k']), '')}\n\n{pc or c_txt}".strip()
  return results


def build_indike_sayana_fallback(
  indike_sayana_path: pathlib.Path,
  kandikas_by_ch: dict[int, list[dict]],
) -> dict[tuple[int, int], str]:
  """Match clean Ch 1–20 Sāyaṇa segments from `indike_kanva_sayana.json` by pratīka monotonically."""
  if not indike_sayana_path.exists():
    return {}
  data = json.loads(indike_sayana_path.read_text(encoding="utf-8"))
  segs = [s for s in data.get("segments", []) if (s.get("text") or "").strip()]
  flat_k = [kr for ch in range(1, 21) for kr in kandikas_by_ch.get(ch, [])]
  n_k, out, cursor = len(flat_k), {}, 0
  for seg in segs:
    txt, loc_str = seg["text"].strip(), str(seg.get("loc", ""))
    if re.search(r"\.p\d+$", loc_str):
      if flat_k:
        key = (flat_k[0]["ch"], flat_k[0]["k"])
        out[key] = f"{out.get(key, '')}\n\n{txt}".strip()
      continue
    m_loc_ch = re.match(r"^(\d+)\.", loc_str)
    best_i, best_ov = cursor, 0.0
    for idx in range(max(0, cursor - 2), min(n_k, cursor + 35)):
      ov = bhashya_aligner.pratika_overlap_score(txt[:280], flat_k[idx]["mula_full"]) + (0.05 if idx in (cursor, cursor + 1) else 0.0)
      if ov > best_ov:
        best_ov, best_i = ov, idx
    if best_ov < 0.25 and m_loc_ch:
      ch_g = min(20, int(m_loc_ch.group(1)))
      for idx in range(max(0, cursor - 30), min(n_k, cursor + 150)):
        if abs(flat_k[idx]["ch"] - ch_g) <= 2:
          ov = bhashya_aligner.pratika_overlap_score(txt[:280], flat_k[idx]["mula_full"])
          if ov > best_ov:
            best_ov, best_i = ov, idx
    cursor = best_i if best_ov >= 0.25 else min(n_k - 1, cursor)
    kr = flat_k[cursor]
    key = (kr["ch"], kr["k"])
    out[key] = f"{out.get(key, '')}\n\n{txt}".strip()
  return out
