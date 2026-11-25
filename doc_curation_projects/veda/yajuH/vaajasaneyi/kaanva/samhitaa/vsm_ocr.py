"""VSM Pune edition Drive-OCR markdown cleaner, chapter slicer, and Padapāṭha/bhāṣya splitter."""
from __future__ import annotations

import re

from doc_curation_projects.veda.yajuH.vaajasaneyi.kaanva.samhitaa.config import (
  _COMMENTARY_PROSE_RE,
  _DEV_ORDINAL_EXTRAS,
  _DEV_ORDINALS_CH,
  _VSM_APPARATUS_RE,
  _VSM_HEADER_RE,
)

_COLOPHON_KW_RE = re.compile(
  r"(?:[भम]ाष्यस[ंङ्][गप्र]हे|स[ंँ]हिता[भम]ाष्ये|वेदार्थदीपिकाया[मं]|वेदभावार्थदीपिकाया[मं]|भावार्थदीपिकाया[मं]|वेदापिकायां)"
)
_VSM_AUTHOR_RE = re.compile(
  r"^(?:(?P<sa>[<\"'‘\s]*(?:सा|[खल]ा(?=\s*[-–—:.]+\s*(?:कात्यायन|अथ|प्रथम|द्वितीय|तृतीय|चतुर्थ|पञ्चम|षष्ठ|सप्तम|अष्टम|नवम|दशम|एकादश|द्वादश|त्रयोदश|चतुर्दश|पञ्चदश|<<)))[-–—:.]+)|(?P<aa>[<\"'‘\s]*आ\s*[-–—:.]+)|(?P<an>[<\"'‘\s]*अ\s*[-–—:.]+))\s*(?P<rest>.*)$"
)
_SA_KAT_RE = re.compile(
  r"^[<\"'‘\s]*(?:कात्यायनः(?:\s*$|[-–—\"'‘“\s])|अथ\s+(?:प्रथम|द्वितीय|तृतीय|चतुर्थ|पञ्चम|षष्ठ|सप्तम|अष्टम|नवम|दशम|एकादश|द्वादश|त्रयोदश|चतुर्दश|पञ्चदश|षोडश|सप्तदश|अष्टादश|एकोनविंश|विंश))"
)


def clean_drive_ocr_markdown(txt: str) -> str:
  """Unescape Google Drive Markdown export artifacts without harming punctuation."""
  for esc, rep in (
    ("\\-", "-"), ("\\|", "|"), ("\\.", "."), ("\\+", "+"),
    ("\\(", "("), ("\\)", ")"), ("\\[", "["), ("\\]", "]"),
    ("\\*", "*"), ("\\`", "`"), ("\\!", "!"), ("\\~", "~"), ("\\_", "_"),
    ("\\\\", "\\"),
  ):
    txt = txt.replace(esc, rep)
  txt = txt.replace("\u200b", "").replace("\xa0", " ")
  return txt.replace("**", "")


def clean_vsm_lines(raw_text: str) -> list[str]:
  """Strip VSM Pune running headers, watermarks, margin line numbers, and critical apparatus footnotes."""
  out: list[str] = []
  skip_foot = False
  for raw in clean_drive_ocr_markdown(raw_text).splitlines():
    s = raw.strip()
    if not s or _VSM_HEADER_RE.match(s):
      continue
    if re.search(r"[A-Za-z]{4,}", s) or re.match(r"^(?:तुलना\s*[-–—]|पा\.?\s*भे\.?\s*[-–—])", s):
      skip_foot = True
      continue
    if (
      (s.startswith("[") or s.endswith("]"))
      and "अध्याय" not in s
      and "अनुवाक" not in s
      and len(s) < 60
      and not re.match(r"^(?:सा|आ|अ)\s*[-–—]", s)
    ):
      continue
    if _VSM_APPARATUS_RE.search(s):
      skip_foot = True
      continue
    if skip_foot and (re.search(r"\b(?:om\.|ins\.|adds?|for\b|does not)\b|[SPHMBCV]{1,3}\d", s) or re.match(r"^\d+\.\s*$", s)):
      continue
    skip_foot = False
    out.append(re.sub(r"\s+(?:५|१०|१५|२०|२५|३०)\s*$", "", s))
  return out


def _ord_variants(ch: int) -> tuple[str, ...]:
  base = [p.strip() for p in _DEV_ORDINALS_CH[ch].split("|") if p.strip()]
  return tuple(dict.fromkeys(base + _DEV_ORDINAL_EXTRAS.get(ch, [])))


def _locate_colophon_end(lines: list[str], pos: int, ch: int) -> int:
  """Locate closing line index for VSM chapter `ch` starting at `pos`."""
  ords = _ord_variants(ch)
  next_ords = _ord_variants(ch + 1)
  next_hdr_re = re.compile(
    rf"^(?:ॐ\s*)?(?:(?:सा|आ|अ)\s*[-–—]+\s*)?(?:अथ\s+)?(?:{'|'.join(next_ords)})ो?ऽ?ध्यायः?(?:\s*[।॥.\-\s]*)$"
  )
  for j in range(pos + 30, len(lines)):
    ln = lines[j]
    if next_hdr_re.match(ln) and "इति" not in ln:
      return j
    win = " ".join(lines[j : min(len(lines), j + 6)])
    win_anu = " ".join(lines[j : min(len(lines), j + 3)])
    has_sam = "अध्यायः समाप्तः" in ln or (j + 1 < len(lines) and "अध्यायः समाप्तः" in lines[j + 1])
    if "नुवाक" in win_anu and not has_sam:
      continue
    if (_COLOPHON_KW_RE.search(ln) or "श्रीमज्जातवेदोपाध्याय" in ln or "अध्यायः समाप्तः" in ln) and (
      any(o in win for o in ords) and ("नुवाक" not in win_anu or has_sam)
    ):
      end_j = min(len(lines), j + 1)
      while end_j < min(len(lines), j + 6) and not any(o in lines[end_j - 1] for o in ords) and "समाप्त" not in lines[end_j - 1]:
        end_j += 1
      look_limit = min(len(lines), j + 95)
      k = end_j
      while k < look_limit:
        nxt_win = " ".join(lines[k : min(len(lines), k + 4)])
        if next_hdr_re.match(lines[k]) or "यस्य निःश्वसितं वेदा" in lines[k]:
          break
        if ("नुवाक" not in nxt_win or "अध्यायः समाप्तः" in nxt_win) and (
          _COLOPHON_KW_RE.search(lines[k])
          or "श्रीमज्जातवेदोपाध्याय" in lines[k]
          or "श्रीमन्नाग" in lines[k]
          or "अध्यायः समाप्तः" in lines[k]
          or (any(o in lines[k] for o in ords) and ("ध्याय" in lines[k] or "समाप्त" in lines[k]))
        ):
          end_j = k + 1
          while end_j < look_limit and (
            any(t in lines[end_j] for t in ("ध्याय", "समाप्त", "प्रकरण"))
            or any(o in lines[end_j] for o in ords)
            or re.match(r"^[॥०-९\s\-।]+$", lines[end_j])
          ):
            end_j += 1
          k = end_j
          continue
        k += 1
      return end_j
  for j in range(pos + 30, len(lines)):
    win = " ".join(lines[j : min(len(lines), j + 4)])
    if "नुवाक" not in win and (_COLOPHON_KW_RE.search(lines[j]) or "श्रीमज्जातवेदोपाध्याय" in lines[j]) and "ध्याय" in win:
      return j + 1
  raise RuntimeError(f"Could not locate end colophon for VSM chapter {ch} starting at line {pos}")


def slice_vsm_volume_chapters(lines: list[str], ch_range: range) -> dict[int, list[str]]:
  """Slice a cleaned VSM Pune volume into chapters via closing colophons & next-chapter headings."""
  ch_list = list(ch_range)
  first_ch = ch_list[0]
  start_idx = next(
    (
      i for i, l in enumerate(lines)
      if i > 150 and (
        "यस्य निःश्वसितं वेदा" in l
        or re.search(rf"^(?:अथ\s+)?(?:{_DEV_ORDINALS_CH[first_ch]})ो?ऽ?ध्याय", l)
        or (first_ch == 1 and ("तस्याः पर्णवृक्षशाखायाः" in l or "ॐ इ॒षे त्वो॒र्जे त्वा" in l))
        or (first_ch == 21 and "सौत्रामणी" in l)
      )
    ),
    0,
  )
  slices: dict[int, list[str]] = {}
  pos = start_idx
  for idx_c, ch in enumerate(ch_list):
    if idx_c == len(ch_list) - 1:
      slices[ch] = lines[pos:]
      break
    end_j = _locate_colophon_end(lines, pos, ch)
    slices[ch] = lines[pos:end_j]
    pos = end_j
  return slices


def _is_padapatha_line(s: str, *, require_accent: bool = False) -> bool:
  """Return True only when `s` looks like a genuine word-by-word Padapāṭha line (never prose or Mūlam)."""
  if not s or s.startswith(("[", "(", "*", "<", "\"", "'", "‘", "“")):
    return False
  if require_accent and any(q in s for q in ("'", "‘", "“", "\"")):
    return False
  if re.match(r"^(?:[०-९\d]+\.|(?:सा|खा|आ|अ)\s*[-–—:.]+|तुलना|पा\.?\s*भे)", s) or re.search(r"[A-Za-z]{3,}", s):
    return False
  if _COMMENTARY_PROSE_RE.search(s) or "पाठस्तु" in s:
    return False
  t = re.sub(r"।{2,}", "॥", re.sub(r"(?<!\|)\|(?!\|)", "।", re.sub(r"\|\|", "॥", s)))
  has_syllable_tag = bool(re.search(r"॥\s*[^\s॥]{1,6}\s*॥\s*[०-९\s()\-]*॥?\s*$", t))
  t_body = re.sub(r"॥\s*[^\s॥]{0,6}\s*॥\s*[०-९\s()\-]*॥?\s*$", "", t)
  t_body = re.sub(r"॥\s*[०-९\s()\-]*॥?\s*$", "", t_body).strip()
  if "।" not in t_body:
    return False
  parts = [p.strip() for p in t_body.split("।") if p.strip()]
  if len(parts) < 2:
    return False
  has_acc = bool(re.search(r"[॒॑]", s))
  if require_accent and not has_acc:
    return False
  norm_lens = [len(re.sub(r"[॒॑ँंः\s]", "", p)) for p in parts]
  max_len, avg_len = max(norm_lens), sum(norm_lens) / len(norm_lens)
  word_counts = [len(p.split()) for p in parts]
  if any(wc >= 4 and "इति" not in p for p, wc in zip(parts, word_counts)):
    return False
  if len(parts) == 2:
    return (
      has_syllable_tag
      or ("इति" in t_body and max_len <= 24)
      or (max_len <= 16 and all(wc <= 2 for wc in word_counts))
    )
  if max_len > 36 or avg_len > 19 or (sum(word_counts) / len(parts)) > 1.85:
    return False
  if sum(1 for wc in word_counts if wc <= 2) < max(2, int(0.75 * len(parts))):
    return False
  return has_acc or ("इति" in t_body) or has_syllable_tag or (sum(1 for wc in word_counts if wc == 1) >= 2)


def _is_mula_line(s: str, *, allow_leading_quote: bool = False) -> bool:
  """Return True when `s` is an accented Samhitā mūlam line (not Padapāṭha or commentary prose)."""
  if not s or not re.search(r"[॒॑]", s):
    return False
  chk = re.sub(r"^['‘\"“\*०-९\s]+", "", s) if allow_leading_quote else s
  if not allow_leading_quote and s.startswith(("'", "‘", "“", "\"", "(", "*", "[", "<")):
    return False
  if s.startswith(("(", "[", "<")) or _COMMENTARY_PROSE_RE.search(chk) or _is_padapatha_line(chk):
    return False
  if re.search(r"(?:इति|अर्थः|भवति|उच्यते|शेषः|प्राप्नोति|कुरु|कुर्यात्)\s*[।॥]?\s*$", chk) and not re.search(r"॥\s*[०-९]+\s*॥\s*$", chk):
    return False
  return True


def _process_vsm_author_line(s: str, cur: dict, blocks: list[dict], authors: tuple[str, ...]) -> dict:
  """Update parser state `cur` and return current active record for one segmented VSM line."""
  def _new_blk() -> dict:
    return {"raw_lines": [], "pada_lines": [], "sayana": [], "anandabodha": [], "anantacharya": [], "mode": "pre"}

  def _flush() -> dict:
    if any(cur[k] for k in ("pada_lines", "sayana", "anandabodha", "anantacharya", "raw_lines")):
      blocks.append(cur)
    return _new_blk()

  m_auth = _VSM_AUTHOR_RE.match(s)
  if m_auth:
    for grp, auth in (("sa", "sayana"), ("aa", "anandabodha"), ("an", "anantacharya")):
      if m_auth.group(grp) is not None and auth in authors:
        if auth == "sayana" and (cur["anandabodha"] or cur["anantacharya"]):
          cur = _flush()
        elif auth == "anandabodha" and cur["anantacharya"]:
          cur = _flush()
        cur["mode"] = auth
        if m_auth.group("rest"):
          cur[auth].append(m_auth.group("rest"))
        return cur
  if cur["mode"] in ("anandabodha", "anantacharya") and _SA_KAT_RE.match(s) and "sayana" in authors:
    cur = _flush()
    cur["mode"] = "sayana"
    cur["sayana"].append(s)
    return cur
  if cur["mode"] in ("sayana", "anandabodha", "anantacharya"):
    is_pada_ln = _is_padapatha_line(s, require_accent=True)
    if is_pada_ln or _is_mula_line(s):
      cur = _flush()
      cur["mode"] = "pada" if is_pada_ln else "mula_or_pada"
      cur["pada_lines" if is_pada_ln else "raw_lines"].append(s)
      return cur
    if s.startswith("[ इति") and ("अध्याय" in s or "अनुवाक" in s):
      return _flush()
  if cur["mode"] in ("pre", "mula_or_pada"):
    if _SA_KAT_RE.match(s) and "sayana" in authors and cur["raw_lines"]:
      cur["mode"] = "sayana"
      cur["sayana"].append(s)
    elif _is_padapatha_line(s) or (cur["pada_lines"] and "।" in s and not _COMMENTARY_PROSE_RE.search(s)):
      cur["pada_lines"].append(s)
      cur["mode"] = "pada"
    else:
      cur["raw_lines"].append(s)
    return cur
  if cur["mode"] == "pada":
    if _SA_KAT_RE.match(s) and "sayana" in authors:
      cur["mode"] = "sayana"
      cur["sayana"].append(s)
    elif s.startswith("[ इति") and "अनुवाक" in s:
      return _flush()
    elif (
      cur["pada_lines"]
      and re.search(r"॥[^॥\n]{1,6}॥\s*[०-९\-\s()]+॥?\s*$", cur["pada_lines"][-1])
      and len(s) > 12 and not _is_padapatha_line(s) and not _is_mula_line(s)
    ):
      cur["mode"] = authors[0]
      cur[authors[0]].append(s)
    elif _is_padapatha_line(s) or re.search(r"[।॥]", s):
      cur["pada_lines"].append(s)
    elif len(s) > 14 and re.search(r"[अ-ह]{3,}", s):
      cur["mode"] = authors[0]
      cur[authors[0]].append(s)
    return cur
  cur[cur["mode"]].append(s)
  return cur


def _split_author_blocks_vsm(ch_lines: list[str], authors: tuple[str, ...]) -> list[dict]:
  """Split a VSM chapter's cleaned lines into sequential raw records containing pada & author texts."""
  blocks: list[dict] = []
  cur = {"raw_lines": [], "pada_lines": [], "sayana": [], "anandabodha": [], "anantacharya": [], "mode": "pre"}
  for ln in ch_lines:
    s = ln.strip()
    if not s:
      continue
    m_p = re.search(r"((?:तत्)?पाठस्तु\s*[-–—:]*\s*)(?![\"'‘“])([^\n]+)$", s)
    sub_lines = [s]
    if m_p and re.search(r"[॒॑]", m_p.group(2)):
      sub_lines = [x for x in (s[: m_p.start()].strip(), m_p.group(2).strip()) if x]
    for seg_ln in sub_lines:
      if seg_ln.strip():
        cur = _process_vsm_author_line(seg_ln.strip(), cur, blocks, authors)
  if any(cur[k] for k in ("pada_lines", "sayana", "anandabodha", "anantacharya", "raw_lines")):
    blocks.append(cur)
  return blocks
