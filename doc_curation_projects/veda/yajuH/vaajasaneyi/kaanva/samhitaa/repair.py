"""VS-K raw Saṁhitā text repair, kaṇḍikā grouping, normalization, and clause splitting."""
from __future__ import annotations

import json
import pathlib
import re
from collections import defaultdict

import regex
from indic_transliteration import sanscript

from doc_curation.llm.proofreader import block_splitter
from doc_curation.sanskrit import fixer
from doc_curation.sanskrit.accent import us_converter
from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import (
  _ACCENTS_STR,
  _KANDIKA_40_16_HEADER_WORDS_CHECK,
  _VP_STRIP_RE,
  _VSK_40_16_MISSING_MULA,
  _VSK_40_16_MISSING_VP,
  VSK_SAMHITA_DIR,
)
from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina.samhitaa import bhashya_aligner


def to_devanagari_ordinal(n: int) -> str:
  """Format kaṇḍikā ordinal like VS-M (zero-padded 2 digits up to 99, 3 digits >= 100)."""
  ascii_num = f"{n:02d}" if n < 100 else str(n)
  return sanscript.transliterate(ascii_num, sanscript.IAST, sanscript.DEVANAGARI)


def build_kandika_heading(kandika_num: int, vp_text: str) -> str:
  """Create a clean ``## NN pratīka`` heading from a kaṇḍikā's opening words."""
  ord_dev = to_devanagari_ordinal(kandika_num)
  plain = _VP_STRIP_RE.sub("", vp_text)
  plain = re.sub(r"ओ३?म्", " ", plain)
  plain = re.sub(r"[।॥०-९0-9()\[\]\"'‘’\-–—]+", " ", plain)
  words = [w for w in plain.split() if len(w) >= 1 and re.search(r"[अ-ह]", w)]
  if words and words[0] == "ओम्" and len(words) > 1:
    words = words[1:]
  head = words[:2] if len(" ".join(words[:2])) >= 8 or len(words) < 3 else words[:3]
  pratika = " ".join(head).strip()
  return f"## {ord_dev} {pratika}".strip()


def normalize_vsk_text(text: str, *, is_vp: bool) -> str:
  """Normalize VS-K accents and pausa anusvāras while protecting mid-verse line-end ``ं`` before consonants."""
  if not text:
    return text
  # Protect genuine mid-verse line-end anusvāra before a consonant line so multiline regex `$`
  # in fixer.normalize_mAdhyandina does not turn e.g. `मे॒दसां \nपृथ॒क्` into `मेदसाम् \nपृथक्`.
  masked = regex.sub(
    rf"ं([{_ACCENTS_STR}]*)(?=[ \t]*\n[ \t]*[क-ह])",
    lambda m: f"\x00MIDN{m.group(1)}\x00",
    text,
  )
  normed = fixer.normalize_mAdhyandina(
    masked, normalize_pre_vowel_avagrahas=is_vp
  )
  return re.sub(r"\x00MIDN([^\x00]*)\x00", r"ं\1", normed)


def _norm_skel(text: str) -> str:
  """Accent/avagraha/anusvāra-folded Devanagari skeleton for robust mantra alignment."""
  s = re.sub(r"[॥।]\s*[०-९\s()॥]*$", "", text.strip())
  s = re.sub(r"\([^)]*\)", " ", s)
  s = re.sub(r"ओ३?म्", " ", s)
  s = bhashya_aligner.normalize_for_matching(s)
  s = s.replace("ऽ", "").replace("ऌ", "ल").replace("ळ", "ल").replace("ँ", "ं")
  return re.sub(r"\s+", "", s)


def load_indike_by_chapter(indike_all40_path: pathlib.Path) -> dict[int, list[dict]]:
  """Load authoritative 40-chapter VS-K kaṇḍikā entries from Indike JSON."""
  raw = json.loads(indike_all40_path.read_text())
  out: dict[int, list[dict]] = {}
  for ch in range(1, 41):
    entries = [
      s for s in raw[str(ch)]
      if s.get("kind") != "colophon" and ".p" not in s.get("loc", "")
    ]
    for idx, entry in enumerate(entries, 1):
      entry["_ch"] = ch
      entry["_k"] = idx
    out[ch] = entries
  return out


def _convert_indike_to_vp_mula(raw_mula: str, anu_num: int, k_in_anu: int, ch_k: int, *, is_anu_end: bool = False) -> tuple[str, str]:
  """Convert clean Indike mūlam into normalized `(vp, mula)` preserving kaṇḍikā end numbering."""
  m_clean = raw_mula.strip()
  dev_ka = to_devanagari_ordinal(k_in_anu).lstrip("०") or "०"
  dev_ch = sanscript.transliterate(str(ch_k), sanscript.IAST, sanscript.DEVANAGARI)
  dev_anu = sanscript.transliterate(str(anu_num), sanscript.IAST, sanscript.DEVANAGARI)
  suffix = f"॥{dev_ka}॥ ({dev_anu}) {dev_ch} ॥" if is_anu_end else f"॥{dev_ka}॥ {dev_ch}"
  if m_clean.endswith("॥"):
    m_clean = m_clean[:-1].rstrip()
  mula_txt = normalize_vsk_text(f"{m_clean} {suffix}".strip(), is_vp=False)
  vp_raw = us_converter.to_us_accents_markdown(mula_txt)
  vp_txt = normalize_vsk_text(vp_raw, is_vp=True)
  return vp_txt, mula_txt


def _dedup_and_repair_raw_chapter(ch: int, md_text: str, ind_k: list[dict]) -> list[tuple[str, str]]:
  """Extract cleaned `(vp, mula)` raw pairs for chapter `ch`, fixing known corruptions in Ch 06, 21, 40."""
  if ch == 6:
    lines = md_text.splitlines()
    dup_idx = next(
      (i for i, l in enumerate(lines) if i > 10 and l.startswith("## अथ षष्ठोऽध्यायः")),
      len(lines),
    )
    md_text = "\n".join(lines[:dup_idx])

  vps = [v.strip() for v in re.findall(r"<summary>विश्वास-प्रस्तुतिः</summary>\s*(.*?)\s*</details>", md_text, flags=re.S)]
  mulas = [m.strip() for m in re.findall(r"<summary>मूलम्</summary>\s*(.*?)\s*</details>", md_text, flags=re.S)]
  assert len(vps) == len(mulas), f"Ch {ch}: VP count {len(vps)} != Mula count {len(mulas)}"

  pairs = [
    (normalize_vsk_text(vp, is_vp=True), normalize_vsk_text(m, is_vp=False))
    for vp, m in zip(vps, mulas)
  ]

  if ch == 21 and ("TODO" in md_text or len(pairs) < len(ind_k) - 10):
    # Raw 21.md stopped mid-21.4.17; restore 21.4.17–21.7.14 cleanly from Indike when incomplete
    cut_idx = next(i for i, s in enumerate(ind_k) if s["loc"] == "21.4.17")
    pairs = pairs[:-1]
    anu_sizes = defaultdict(int)
    for s in ind_k:
      anu_sizes[int(s["loc"].split(".")[1])] += 1
    for idx_i in range(cut_idx, len(ind_k)):
      s = ind_k[idx_i]
      _, anu_s, ka_s = s["loc"].split(".")
      anu_n, ka_n = int(anu_s), int(ka_s)
      pairs.append(
        _convert_indike_to_vp_mula(s["text"], anu_n, ka_n, idx_i + 1, is_anu_end=(ka_n == anu_sizes[anu_n]))
      )

  if ch == 40:
    for idx, (vp, m) in enumerate(pairs):
      sk = _norm_skel(m)
      if sk.startswith("तेजोयत्ते") and _KANDIKA_40_16_HEADER_WORDS_CHECK not in sk:
        ind_40_16 = ind_k[15]["text"]
        vp_miss, _ = _convert_indike_to_vp_mula(ind_40_16, 1, 16, 16, is_anu_end=False)
        new_m = normalize_vsk_text(f"{_VSK_40_16_MISSING_MULA}\n{m}", is_vp=False)
        open_vp_line = vp_miss.split("ते᳓जो", 1)[0].strip() if "ते᳓जो" in vp_miss else _VSK_40_16_MISSING_VP.strip()
        pairs[idx] = (normalize_vsk_text(f"{open_vp_line}  \n{vp}", is_vp=True), new_m)
        break

  return pairs


def load_vsk_repaired_kandikas(
  indike_all40_path: pathlib.Path,
  *,
  vsk_dir: pathlib.Path = VSK_SAMHITA_DIR,
) -> dict[int, list[dict]]:
  """Repair local VS-K chapters and group each chapter's blocks 1-to-1 into the 2,086 kaṇḍikās."""
  ind_by_ch = load_indike_by_chapter(indike_all40_path)
  result: dict[int, list[dict]] = {}

  for ch in range(1, 41):
    md_path = vsk_dir / f"{ch:02d}.md"
    if not md_path.exists():
      md_path = vsk_dir / "sarva-prastutiH" / f"{ch:02d}.md"
    ind_k = ind_by_ch[ch]
    pairs = _dedup_and_repair_raw_chapter(ch, md_path.read_text(), ind_k)
    m_skels = [_norm_skel(m) for _, m in pairs]
    i_skels = [_norm_skel(s["text"]) for s in ind_k]
    has_num = [bool(re.search(r"॥\s*[०-९\s()]+॥?\s*$", m)) for _, m in pairs]

    k_list: list[dict] = []
    idx = 0
    for k_idx, (s, tgt) in enumerate(zip(ind_k, i_skels), 1):
      rem_k = len(i_skels) - k_idx
      max_end = len(m_skels) - rem_k
      best_j = idx + 1
      best_err = 10**9
      cur_s = ""
      for j in range(idx + 1, min(max_end + 1, idx + 20)):
        cur_s += m_skels[j - 1]
        err = abs(len(cur_s) - len(tgt)) - (25 if has_num[j - 1] else 0)
        if err < best_err:
          best_err = err
          best_j = j
        if len(cur_s) > len(tgt) + 90:
          break
      k_pairs = pairs[idx:best_j]
      idx = best_j
      k_list.append({
        "ch": ch,
        "k": k_idx,
        "loc": s["loc"],
        "kind": s.get("kind") or "prose",
        "heading": build_kandika_heading(k_idx, k_pairs[0][0]),
        "raw_pairs": k_pairs,
        "mula_full": " ".join(m for _, m in k_pairs),
        "vp_full": " ".join(vp for vp, _ in k_pairs),
      })
    assert idx == len(pairs), f"Ch {ch}: consumed {idx} != {len(pairs)}"
    result[ch] = k_list
  return result


def split_kandika_clauses(kandika_rec: dict) -> list[tuple[str, str]]:
  """Split a kaṇḍikā's `(vp, mula)` pairs finely into sense units without losing verse pairing."""
  is_prose = kandika_rec.get("kind") != "verse"
  out_pairs: list[tuple[str, str]] = []
  for vp, mula in kandika_rec["raw_pairs"]:
    vp_segs = block_splitter.split_into_danda_segments(vp)
    m_segs = block_splitter.split_into_danda_segments(mula)
    if len(vp_segs) > 1 and len(vp_segs) == len(m_segs):
      m_flags = block_splitter._group_units_with_flags(
        m_segs, use_local_hyphenator=True, allow_metrical_merge=(not is_prose)
      )
      if len(m_flags) > 1:
        pos = 0
        split_ok = True
        new_vp_units: list[str] = []
        new_m_units: list[str] = []
        for m_txt, is_v in m_flags:
          cnt = 1
          acc = m_segs[pos]
          while pos + cnt < len(m_segs) and _norm_skel(acc) != _norm_skel(m_txt) and len(_norm_skel(acc)) < len(_norm_skel(m_txt)):
            acc += " " + m_segs[pos + cnt]
            cnt += 1
          if _norm_skel(acc) != _norm_skel(m_txt) or pos + cnt > len(vp_segs):
            split_ok = False
            break
          sep = "  \n" if is_v else " "
          new_vp_units.append(sep.join(vp_segs[pos : pos + cnt]))
          new_m_units.append((" \n" if is_v else " ").join(m_segs[pos : pos + cnt]))
          pos += cnt
        if split_ok and pos == len(vp_segs):
          out_pairs.extend(zip(new_vp_units, new_m_units))
          continue
    out_pairs.append((vp, mula))
  return out_pairs
