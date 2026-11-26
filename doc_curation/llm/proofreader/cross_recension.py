"""Cross-recension viniyoga-guided splitting and Mahīdhara commentary interleaver.

Uses Mādhyandina Saṁhitā ``sarva-prastutiH`` (``मूलम्`` + ``महीधरः``) to:
1. Segment Mahīdhara's commentary cleanly into ``महीधरः - अवतारिका``,
   ``महीधरः - विनियोगः``, and ``महीधरः - टीका`` chunks (anchoring Kātyāyana
   Śrautasūtra ritual quotes to their sub-mantra pratīkas).
2. Identify split boundaries where a Kāṇva block spans multiple Mādhyandina
   mantras or distinct Mahīdhara viniyogas, splitting ``विश्वास-प्रस्तुतिः`` and
   ``मूलम्`` at non-sandhi word/daṇḍa boundaries with source byte fidelity.
3. Align and insert ``महीधरः - अवतारिका``, ``महीधरः - विनियोगः``, and
   ``महीधरः - टीका`` blocks for near-identical mantras.
"""
from __future__ import annotations

import difflib
from pathlib import Path
import regex
from indic_transliteration.sanscript.schemes.brahmic import accent

from .block_splitter import _ANNO_RE, _is_metrical_pair, _verse_chain_length, split_into_danda_segments
from .guards import canonical_sandhi_skeleton
from .interleave_aligner import (
  _clean_sanskrit_surface,
  _iti_candidates_from_match,
  _ITI_RE,
  align_commentary_segments,
)
from .interleave_helper import parse_markdown_clusters, split_quote_safe_segments

_TRAILING_ORD_RE = regex.compile(
  r"^(?:प्रथमा|द्वितीया|तृतीया|चतुर्थी|पञ्चमी|षष्ठी|सप्तमी|अष्टमी|नवमी|दशमी|"
  r"एकादशी|द्वादशी|त्रयोदशी|चतुर्दशी|[अ-ह]+दशी|[अ-ह]+विंशी|[अ-ह]+त्रिंशी|"
  r"[अ-ह]+चत्वारिंशी|[अ-ह]+पञ्चाशी|[अ-ह]+षष्टी|[अ-ह]+सप्तती|[अ-ह]+शीती|"
  r"[अ-ह]+नवती|शती)(?:\s*[।॥|\-]+)*$"
)
_KAT_SUTRA_RE = regex.compile(r"\(\s*का(?:त्या)?[०.]\s*[0-9०-९]|तत्र\s+कात्यायनः|कात्यायनः\s*['‘]")
_NOT_VINIYOGA_RE = regex.compile(r"विनियोगो\s+नास्ति|इति\s+श्रुतेः|\(\s*(?:पा|उ|निघ|निरु)[०.]")
_RITUAL_VERB_RE = regex.compile(
  r"(?:विनियोगः|विनियुज्यते|छिनत्ति|स्थाल्यादानम्|अधिश्रयति|बध्नाति|आस्तृणाति|"
  r"निदधाति|उत्सृजति|दोग्धि|उन्नयति|अवदधाति|आरोहणम्|अवरोहति|प्रोक्षति|प्रोक्षणम्|"
  r"आह्वयति|परिगृह्णाति|वीक्षते|स्पृशति|ह्वयति|अभिजुहोति|अभ्यादधाति|उपदधाति|"
  r"जुहोति|जुहुयात्|जपति|जपेत्|आदत्ते|उपतिष्ठते|गृह्णाति|अभिमन्त्रयते)"
)
_TIKA_START_RE = regex.compile(
  r"(?:^मन्त्रार्थः|अथ\s+मन्त्रार्थः|अथ\s+व्याकरण|(?<![अ-ह])हे\s+[अ-ह]+|देवताका|देवत्यम्|"
  r"गायत्री|त्रिष्टुप्|जगती|अनुष्टुप्|पङ्क्तिः|बृहती|उष्णिक्)\b"
)
_AVATARIKA_RE = regex.compile(
  r"(?:उपोद्घातम्|प्रणम्य|नमस्कृत्य|निरूपितम्|निरूप्यते|वितन्यते|कण्डिकायां|"
  r"अध्याये|अभिधेयसंबन्ध|कर्मकाण्डं|ज्ञानकाण्डम्|इदानीं\s+ते\s+मन्त्रा\s+व्याख्यायन्ते)"
)
_STRIP_TRAIL_NUM_RE = regex.compile(r"(?:॥\s*[०-९0-9()]+\s*॥?|\([०-९0-9]+\)|[०-९0-9]+)+\s*$")
_QUOTE_SPAN_RE = regex.compile(r"['‘]([^'\n‘’]{3,200})['’]")


def _norm_surface_with_map(raw: str) -> tuple[str, list[int]]:
  """Normalize raw Vedic Devanagari into compact tokens while mapping back to ``raw`` indices."""
  out_chars: list[str] = []
  pos_map: list[int] = []
  skip_ch = set(" \t\r\n।॥,.()-–—'\"“”‘’0123456789०१२३४५६७८९")
  sv = set("\u0951\u0952\u0953\u0954\u1cd0\u1cf4\u1cf7\u1cf8\u1cf9\u1cfa\u1cfb\u1cfc\u1cfd\u1cfe\u1cff\u200c\u200d᳓᳙")
  nasals = set("ङञणनम")
  n = len(raw)
  for idx, ch in enumerate(raw):
    if ch in sv or ch in skip_ch or ("\u1cd0" <= ch <= "\u1cff"):
      continue
    if ch == "ऽ":
      prev_raw = raw[idx - 1] if idx > 0 else " "
      if prev_raw in (" ", "\t", "\n", "।", "॥", "ो", "े", "ऽ") or idx == 0:
        out_chars.append("अ")
        pos_map.append(idx)
      continue
    if ch == "्" and idx > 0 and raw[idx - 1] in nasals and out_chars:
      out_chars[-1] = "ं"
      continue
    if ch == "ँ":
      ch = "ं"
    elif ch == "ळ":
      ch = "ल"
    elif ch in ("ᳵ", "ᳶ"):
      ch = "ः"
    out_chars.append(ch)
    pos_map.append(idx)
  return "".join(out_chars), pos_map


def _clean_m_norm(text: str) -> str:
  return _norm_surface_with_map(_STRIP_TRAIL_NUM_RE.sub("", text or ""))[0]


def clean_mahidhara_raw(body: str) -> str:
  """Strip ``म०`` prefixes and orphan next-mantra ordinal line from raw Mahīdhara block."""
  txt = regex.sub(r"(?m)^\s*म[०॰]\.?\s*", "", (body or "").strip())
  lines = txt.splitlines()
  while lines and not lines[-1].strip():
    lines.pop()
  if lines and _TRAILING_ORD_RE.fullmatch(lines[-1].strip()):
    lines.pop()
  while lines and not lines[-1].strip():
    lines.pop()
  return "\n".join(lines).strip()


def parse_madhyandina_mahidhara_file(md_text: str) -> list[dict]:
  """Parse a Mādhyandina ``sarva-prastutiH`` chapter file into mantra records."""
  entries: list[dict] = []
  for sec in regex.split(r"(?m)^## ", md_text or "")[1:]:
    hdr = sec.splitlines()[0].strip()
    m_mu = regex.search(r"<summary>\s*(?:<h3>)?मूलम्[^<]*(?:</h3>)?\s*</summary>\s*(.*?)\s*</details>", sec, regex.DOTALL)
    m_mh = regex.search(r"<details><summary>महीधरः</summary>\s*(.*?)\s*</details>", sec, regex.DOTALL)
    if not (m_mu and m_mh):
      continue
    mula_raw = m_mu.group(1).strip()
    mah_clean = clean_mahidhara_raw(m_mh.group(1))
    entries.append({
      "heading": hdr,
      "mula": mula_raw,
      "mula_norm": _clean_m_norm(mula_raw),
      "mahidhara": mah_clean,
    })
  return entries


def _merge_orphan_ref_segments(segs: list[str]) -> list[str]:
  """Re-attach trailing ``(का० ...)`` / ``(पा० ...)`` / ``इति ।`` citations broken by danda/quote glitches."""
  merged: list[str] = []
  for s in segs:
    ss = s.strip()
    if not ss:
      continue
    if merged and (
      regex.match(r"^(?:\([^)]*\)|इति\s*[।॥]*|इत्यर्थः\s*[।॥]*|[0-9०-९।॥\s]+)$", ss)
      or (merged[-1].count("'") % 2 == 1 and "'" in ss and len(ss) < 180)
    ):
      merged[-1] = f"{merged[-1]} {ss}"
    else:
      merged.append(ss)
  return merged


def _classify_mahidhara_seg(seg: str, *, seen_tika: bool, seen_vin: bool, prev_role: str | None) -> str:
  raw = seg.strip()
  if _NOT_VINIYOGA_RE.search(raw) and not _KAT_SUTRA_RE.search(raw):
    return "avatarika" if not seen_tika and not seen_vin and _AVATARIKA_RE.search(raw) else "tika"
  if _KAT_SUTRA_RE.search(raw):
    return "viniyoga"
  if not seen_tika and not seen_vin and _AVATARIKA_RE.search(raw) and not _TIKA_START_RE.search(raw):
    return "avatarika"
  if _RITUAL_VERB_RE.search(raw) and not _TIKA_START_RE.search(raw):
    return "viniyoga"
  if prev_role == "viniyoga" and regex.match(r"^(?:अस्यार्थः|तदर्थ|तथा\s*हि|एवं|पूर्वसूत्रा)", raw) and not _TIKA_START_RE.search(raw):
    return "viniyoga"
  if prev_role == "viniyoga" and ("इति सूत्रार्थः" in raw or "सूत्रार्थः" in raw) and not _TIKA_START_RE.search(raw):
    return "viniyoga"
  return "tika"


def segment_mahidhara_commentary(mahidhara_text: str) -> list[dict]:
  """Segment cleaned Mahīdhara text into ``avatarika``, ``viniyoga``, and ``tika`` units."""
  raw_segs = _merge_orphan_ref_segments(split_quote_safe_segments(mahidhara_text))
  out: list[dict] = []
  seen_tika = False
  seen_vin = False
  prev_role: str | None = None
  for seg in raw_segs:
    role = _classify_mahidhara_seg(seg, seen_tika=seen_tika, seen_vin=seen_vin, prev_role=prev_role)
    if role == "viniyoga":
      seen_vin = True
    elif role == "tika":
      seen_tika = True
    prev_role = role
    out.append({"role": role, "text": seg})
  return out


def _extract_quote_pratikas(seg_text: str) -> list[str]:
  """Extract normalized candidate pratīkas from quoted KŚS citations inside a viniyoga segment."""
  cands: list[str] = []
  for qm in _QUOTE_SPAN_RE.finditer(seg_text):
    inner = qm.group(1).strip()
    # 1. Check `... इति` inside the quote
    for im in _ITI_RE.finditer(inner):
      for c in _iti_candidates_from_match(inner, im, max_words=3):
        nc = _clean_m_norm(c)
        if len(nc) >= 4 and nc not in cands:
          cands.append(nc)
    # 2. Fallback: words after skipping leading Sanskrit ritual verb inside `'...'`
    words = [w for w in regex.findall(r"[ऀ-ॿ]+", _clean_sanskrit_surface(inner)) if regex.search(r"[अ-ह]", w)]
    if words:
      start_w = 1 if len(words) >= 2 and _RITUAL_VERB_RE.search(words[0]) else 0
      for span in (words[start_w:start_w + 3], words[-2:]):
        nc = _clean_m_norm("".join(span))
        if len(nc) >= 4 and nc not in cands:
          cands.append(nc)
  return cands


def _word_boundary_norm_starts(raw: str, pos_map: list[int]) -> dict[int, int]:
  """Return ``{norm_index: raw_index}`` only at clean non-sandhi boundary positions in ``raw``."""
  starts: dict[int, int] = {}
  for ni, r_idx in enumerate(pos_map):
    if r_idx == 0:
      starts[ni] = 0
      continue
    prev = raw[r_idx - 1]
    if prev.isspace() or prev in "।॥":
      # Walk back over whitespace right after a daṇḍa/space to point right at token start
      starts[ni] = r_idx
  return starts


def find_viniyoga_split_offsets(mula_text: str, segmented_mah: list[dict]) -> list[tuple[int, int]]:
  """Return monotonic ``(vin_seg_idx, raw_split_offset)`` pairs anchored inside ``mula_text``."""
  m_norm, pos_map = _norm_surface_with_map(mula_text)
  if not m_norm:
    return []
  boundary_map = _word_boundary_norm_starts(mula_text, pos_map)
  anchors: list[tuple[int, int]] = []
  last_norm_pos = -1

  for idx, item in enumerate(segmented_mah):
    if item["role"] != "viniyoga" or idx > 0 and segmented_mah[idx - 1]["role"] == "viniyoga" and not _KAT_SUTRA_RE.search(item["text"]):
      continue
    pratikas = _extract_quote_pratikas(item["text"])
    best_norm_off: int | None = None
    for pr in pratikas:
      probe = pr[:min(len(pr), 10)]
      for n_off, raw_off in boundary_map.items():
        if n_off <= last_norm_pos:
          continue
        if m_norm.startswith(probe, n_off):
          best_norm_off = n_off
          break
      if best_norm_off is not None:
        break
    if best_norm_off is not None:
      raw_off = boundary_map[best_norm_off]
      # Ignore trailing small ref fragments (< 8 letters left or right)
      anchors.append((idx, raw_off))
      last_norm_pos = best_norm_off + 3
  return anchors


def _canonical_split_chunks(mula_text: str, raw_offsets: list[int]) -> list[str]:
  """Slice ``mula_text`` at valid non-sandhi word/daṇḍa offsets without dropping characters."""
  clean_offs = [0]
  n_len = len(mula_text)
  for off in sorted(set(raw_offsets)):
    if off <= clean_offs[-1] or off >= n_len:
      continue
    left = mula_text[clean_offs[-1]:off].strip()
    right = mula_text[off:].strip()
    left_lets = regex.sub(r"[^अ-ह]", "", accent.strip_accents(left))
    right_lets = regex.sub(r"[^अ-ह]", "", accent.strip_accents(_STRIP_TRAIL_NUM_RE.sub("", right)))
    if len(left_lets) >= 6 and len(right_lets) >= 6:
      clean_offs.append(off)
  if len(clean_offs) <= 1:
    return [mula_text]
  parts = [mula_text[clean_offs[k]:clean_offs[k + 1]].strip() for k in range(len(clean_offs) - 1)]
  parts.append(mula_text[clean_offs[-1]:].strip())
  # Verify 100% character preservation modulo whitespace
  orig_nw = regex.sub(r"\s+", "", mula_text)
  joined_nw = regex.sub(r"\s+", "", "".join(parts))
  return parts if orig_nw == joined_nw else [mula_text]


def _render_vp_mula_pair(mula_part: str, *, clause_newlines: bool = True) -> tuple[str, str]:
  """Generate ``(vp, mula)`` bodies for a split Kāṇva mantra slice via the local hyphenator."""
  from doc_curation.sanskrit.hyphenator import hyphene

  mula_clean = regex.sub(r"[ \t]{2,}", " ", _ANNO_RE.sub("", mula_part)).strip()
  vp_txt = mula_part.strip()
  segs = split_into_danda_segments(vp_txt)
  is_verse = False
  if len(segs) >= 2 and any(s.strip().endswith("।") for s in segs[:-1]) and regex.search(r"॥[०-९0-9\s()]*\s*$", segs[-1].strip()):
    is_verse = _is_metrical_pair(segs[0], segs[1]) if len(segs) == 2 else _verse_chain_length(segs, 0) == len(segs)
  if regex.search(r"[\u0951\u0952]", vp_txt):
    vp_txt = accent.to_US_accents(vp_txt, pauses=r"[।॥,;]+")
  vp_txt = hyphene(vp_txt, clause_newlines=(clause_newlines and not is_verse))
  return vp_txt, mula_clean


def select_candidate_madhyandina_chapters(
  kanva_mulas: list[str],
  madhyandina_by_chapter: dict[int, list[dict]],
  fallback_num: int,
) -> list[int]:
  """Identify Mādhyandina chapter number(s) corresponding to one Kāṇva chapter."""
  k_full = _clean_m_norm("".join(kanva_mulas))
  hits: list[tuple[int, int]] = []
  for mn, entries in sorted(madhyandina_by_chapter.items()):
    h = sum(1 for e in entries if len(e["mula_norm"]) >= 15 and e["mula_norm"][:15] in k_full)
    if h > 0:
      hits.append((h, mn))
  if not hits:
    return [fallback_num] if fallback_num in madhyandina_by_chapter else []
  top_h = max(h for h, _ in hits)
  thresh = max(5, int(top_h * 0.25))
  chosen = sorted(mn for h, mn in hits if h >= thresh)
  return chosen or [max(hits)[1]]


def _best_aligned_similarity(k_norm: str, m_norm: str) -> float:
  """Symmetric similarity over the matched contiguous window inside ``m_norm``."""
  if not k_norm or not m_norm:
    return 0.0
  if k_norm in m_norm:
    return 1.0
  sm = difflib.SequenceMatcher(None, k_norm, m_norm, autojunk=False)
  blocks = [bl for bl in sm.get_matching_blocks() if bl.size > 0]
  if not blocks:
    return 0.0
  m_span = m_norm[blocks[0].b:blocks[-1].b + blocks[-1].size]
  if len(m_span) < len(k_norm) * 0.65:
    return sm.ratio()
  return difflib.SequenceMatcher(None, k_norm, m_span, autojunk=False).ratio()


def _detect_split_offsets_for_block(
  mula_txt: str,
  cand_entries: list[dict],
  anchor_idx: int,
  *,
  min_similarity: float = 0.85,
) -> list[int]:
  """Find split points where ``mula_txt`` crosses two Mādhyandina mantras or distinct viniyogas."""
  k_norm, pos_map = _norm_surface_with_map(_STRIP_TRAIL_NUM_RE.sub("", mula_txt))
  if len(k_norm) < 16:
    return []
  boundary_map = _word_boundary_norm_starts(mula_txt, pos_map)

  # 1. Cross-mantra split between adjacent M[j] and M[j+1]
  if anchor_idx >= 0:
    m_cur = cand_entries[anchor_idx]
    cur_sim = _best_aligned_similarity(k_norm, m_cur["mula_norm"])
    if cur_sim < min_similarity and anchor_idx + 1 < len(cand_entries):
      m_nxt = cand_entries[anchor_idx + 1]
      # Check every boundary in mula_txt
      best_off = None
      best_score = 0.0
      for n_off, raw_off in boundary_map.items():
        if n_off < 6 or len(k_norm) - n_off < 6:
          continue
        s1 = _best_aligned_similarity(k_norm[:n_off], m_cur["mula_norm"])
        s2 = _best_aligned_similarity(k_norm[n_off:], m_nxt["mula_norm"])
        if s1 >= min_similarity and s2 >= min_similarity and (s1 + s2) > best_score:
          best_score, best_off = s1 + s2, raw_off
      if best_off is not None:
        return [best_off]

  # 2. Multi-viniyoga split inside single matched M[j]
  if anchor_idx >= 0:
    m_cur = cand_entries[anchor_idx]
    if _best_aligned_similarity(k_norm, m_cur["mula_norm"]) >= min_similarity:
      segs = segment_mahidhara_commentary(m_cur["mahidhara"])
      anchors = find_viniyoga_split_offsets(mula_txt, segs)
      distinct_offs = [raw_off for _, raw_off in anchors if raw_off > 0]
      if len(distinct_offs) >= 1:
        return distinct_offs
  return []


def _find_best_cand_index(
  k_norm: str,
  cand_entries: list[dict],
  cursor: int,
  *,
  min_similarity: float = 0.85,
) -> tuple[int, float]:
  """Locate best candidate Mādhyandina mantra around monotonic ``cursor``."""
  if not k_norm or not cand_entries:
    return -1, 0.0
  # Check tight local window first (handles 1->many and minor transpositions), then chapter-wide
  win_indices = list(range(max(0, cursor - 2), min(len(cand_entries), cursor + 8)))
  best_i, best_s = -1, 0.0
  for idx in win_indices:
    sc = _best_aligned_similarity(k_norm, cand_entries[idx]["mula_norm"])
    if sc > best_s:
      best_s, best_i = sc, idx
  if best_s >= min_similarity:
    return best_i, best_s
  for idx in range(len(cand_entries)):
    sc = _best_aligned_similarity(k_norm, cand_entries[idx]["mula_norm"])
    if sc > best_s:
      best_s, best_i = sc, idx
  return best_i, best_s


def _format_cluster(
  *,
  pre: str,
  avatarika: list[str],
  viniyoga: list[str],
  vp: str,
  mula: str,
  tika: list[str],
  post: str,
) -> str:
  parts: list[str] = []
  if pre.strip():
    parts.append(pre.strip())
  if avatarika:
    parts.append("<details><summary>महीधरः - अवतारिका</summary>\n\n" + "\n\n".join(avatarika) + "\n</details>")
  if viniyoga:
    parts.append("<details><summary>महीधरः - विनियोगः</summary>\n\n" + "\n\n".join(viniyoga) + "\n</details>")
  parts.append(f"<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n{vp.strip()}\n</details>")
  parts.append(f"<details><summary>मूलम्</summary>\n\n{mula.strip()}\n</details>")
  if post.strip():
    parts.append(post.strip())
  if tika:
    parts.append("<details><summary>महीधरः - टीका</summary>\n\n" + "\n\n".join(tika) + "\n</details>")
  return "\n\n".join(parts)


def _assign_matched_run(
  cand_entry: dict,
  refined: list[dict],
  run_indices: list[int],
  ava_by_k: dict[int, list[str]],
  vin_by_k: dict[int, list[str]],
  tik_by_k: dict[int, list[str]],
) -> None:
  """Place Mahīdhara ``avatarika``, ``viniyoga``, and ``tika`` chunks onto ``run_indices``."""
  segs = segment_mahidhara_commentary(cand_entry["mahidhara"])
  avas = [s["text"] for s in segs if s["role"] == "avatarika"]
  non_avas = [s for s in segs if s["role"] != "avatarika"]
  if avas:
    ava_by_k[run_indices[0]].extend(avas)
  if not non_avas:
    return
  if len(run_indices) == 1:
    k0 = run_indices[0]
    for s in non_avas:
      (vin_by_k if s["role"] == "viniyoga" else tik_by_k)[k0].append(s["text"])
    return
  # Joint monotonic alignment of viniyoga + tika segments preserves Vin_k -> Tika_k pairing
  run_mulas = [refined[idx]["mula"] for idx in run_indices]
  plan = align_commentary_segments(run_mulas, [s["text"] for s in non_avas], is_sarvash_tikah=False)
  assigned = {a["seg"]: a["core"] for a in plan["assignments"]}
  last_core = 0
  for s_idx, item in enumerate(non_avas):
    core_rel = assigned.get(s_idx, last_core)
    last_core = core_rel
    dest = vin_by_k if item["role"] == "viniyoga" else tik_by_k
    dest[run_indices[core_rel]].append(item["text"])


def _align_refined_blocks(refined: list[dict], cand_entries: list[dict], min_similarity: float) -> list[int | None]:
  matches: list[int | None] = []
  m_cursor = 0
  for cl in refined:
    kn = _clean_m_norm(_STRIP_TRAIL_NUM_RE.sub("", cl["mula"]))
    if len(kn) < 8:
      matches.append(None)
      continue
    if len(kn) < 12:
      # Short yajus fragments only match within tight local window [cursor .. cursor + 2]
      win = range(m_cursor, min(len(cand_entries), m_cursor + 3))
      best_i, best_s = max(((i, _best_aligned_similarity(kn, cand_entries[i]["mula_norm"])) for i in win), key=lambda x: x[1], default=(-1, 0.0))
    else:
      best_i, best_s = _find_best_cand_index(kn, cand_entries, m_cursor, min_similarity=min_similarity)
    if best_i >= 0 and best_s >= min_similarity:
      matches.append(best_i)
      m_cursor = best_i
    else:
      matches.append(None)
  return matches


def apply_mahidhara_to_kanva_markdown(
  kanva_md: str,
  cand_entries: list[dict],
  *,
  min_similarity: float = 0.85,
  clause_newlines: bool = True,
) -> dict:
  """Split multi-viniyoga Kāṇva blocks and interleave Mahīdhara blocks for near-identical text."""
  preamble, clusters, postamble, mula_bodies = parse_markdown_clusters(kanva_md)
  if not clusters or not cand_entries:
    return {"markdown": kanva_md, "splits_added": 0, "matched_clusters": 0}

  refined: list[dict] = []
  splits_added = 0
  m_cursor = 0
  for cl, mu in zip(clusters, mula_bodies):
    k_norm = _clean_m_norm(_STRIP_TRAIL_NUM_RE.sub("", mu))
    best_i, best_s = _find_best_cand_index(k_norm, cand_entries, m_cursor, min_similarity=min_similarity)
    anchor_i = best_i if best_i >= 0 else min(m_cursor, len(cand_entries) - 1)
    split_offs = _detect_split_offsets_for_block(mu, cand_entries, anchor_i, min_similarity=min_similarity)
    chunks = _canonical_split_chunks(mu, split_offs) if split_offs else [mu]
    m_vp = regex.search(r"<summary>\s*विश्वास-प्रस्तुतिः[^<]*</summary>\s*(.*?)\s*</details>", cl["vp"], regex.DOTALL)
    orig_vp = m_vp.group(1).strip() if m_vp else ""
    if len(chunks) > 1:
      splits_added += len(chunks) - 1
      for ci, ch in enumerate(chunks):
        vp_sub, mu_sub = _render_vp_mula_pair(ch, clause_newlines=clause_newlines)
        refined.append({
          "pre": cl["pre"] if ci == 0 else "",
          "vp": vp_sub,
          "mula": mu_sub,
          "post": cl["post"] if ci == len(chunks) - 1 else "",
        })
    else:
      refined.append({"pre": cl["pre"], "vp": orig_vp, "mula": mu.strip(), "post": cl["post"]})
    if best_i >= 0 and best_s >= min_similarity:
      m_cursor = best_i

  matches = _align_refined_blocks(refined, cand_entries, min_similarity)
  ava_by_k: dict[int, list[str]] = {i: [] for i in range(len(refined))}
  vin_by_k: dict[int, list[str]] = {i: [] for i in range(len(refined))}
  tik_by_k: dict[int, list[str]] = {i: [] for i in range(len(refined))}

  k_i, matched_clusters = 0, 0
  while k_i < len(refined):
    mi = matches[k_i]
    if mi is None:
      k_i += 1
      continue
    k_end = k_i
    while k_end + 1 < len(refined) and matches[k_end + 1] == mi:
      k_end += 1
    run_indices = list(range(k_i, k_end + 1))
    matched_clusters += len(run_indices)
    _assign_matched_run(cand_entries[mi], refined, run_indices, ava_by_k, vin_by_k, tik_by_k)
    k_i = k_end + 1

  rendered = [
    _format_cluster(
      pre=cl["pre"],
      avatarika=ava_by_k[idx],
      viniyoga=vin_by_k[idx],
      vp=cl["vp"],
      mula=cl["mula"],
      tika=tik_by_k[idx],
      post=cl["post"],
    )
    for idx, cl in enumerate(refined)
  ]
  body = "\n\n".join(rendered)
  full_md = (preamble.rstrip() + "\n\n" if preamble.strip() else preamble) + body + (
    "\n\n" + postamble.lstrip() if postamble.strip() else "\n"
  )
  return {"markdown": full_md, "splits_added": splits_added, "matched_clusters": matched_clusters}
