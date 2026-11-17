"""Computer-vision Vedic accent detector and Drive/OCR akṣara aligner for scanned Telugu PDFs.

Detects printed udātta/svarita (vertical bar ``|``), dīrgha-svarita (double bar ``||``),
and anudātta (horizontal underline ``_``) marks independently of OCR, builds clean
accent-stripped line canvases for base-text OCR/proofing, aligns base akṣara tokens to
visual glyph slots via dynamic programming, and renders accented Telugu + Devanagari.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import numpy as np
from indic_transliteration import sanscript

TELUGU_CONSONANTS = set(chr(c) for c in range(0x0C15, 0x0C3A)) | set(chr(c) for c in range(0x0C58, 0x0C5B))
TELUGU_VOWELS = set(chr(c) for c in range(0x0C05, 0x0C15)) | {"\u0C60", "\u0C61"}
TELUGU_MATRAS = set(chr(c) for c in range(0x0C3E, 0x0C4D)) | {"\u0C55", "\u0C56", "\u0C62", "\u0C63"}
TELUGU_MODS = {"\u0C00", "\u0C01", "\u0C02", "\u0C03", "\u1CF6"}
TELUGU_VIRAMA = "\u0C4D"
TELUGU_AVAGRAHA = "\u0C3D"
TELUGU_DIGITS = set(chr(c) for c in range(0x0C66, 0x0C70))

SVARA_ANUDATTA = "\u0952"
SVARA_SVARITA = "\u0951"
SVARA_DIRGHA_SVARITA = "\u1CDA"

# Suspicious Sanskrit-in-Telugu OCR cluster patterns for Vision QA escalation
SUSPECT_TEXT_RE = re.compile(
    r"[A-Za-z]"
    r"|(?<=[\u0C05-\u0C4D])\u0C6F(?=[\u0C05-\u0C4D])"  # Telugu digit ౯ inside word
    r"|\u0C2B[\u0C41\u0C42]"  # ఫు / ఫూ (misread పు / పూ)
    r"|\u0C1C\u0C4D\u0C15"  # జ్క (misread ఙ్క)
    r"|\u0C2E\u0C38\u0C4D\u0C24\u0C4D\u0C30"  # మస్త్ర (misread మన్త్ర)
    r"|\u0C25\u0C43"  # థృ (misread థ్స / ధృ)
    r"|\u0C38\u0C4D\u0C26\u0C3F"  # స్ది (misread ఙ్గి)
    r"|\u0C30\u0C4D\u0C32"  # ర్ల (misread ర్స్)
)


def deskew_and_clean(gray: np.ndarray, threshold_floor: int = 140) -> tuple[np.ndarray, np.ndarray, float, list[int], bool]:
  """Deskew a scanned page image and strip specks, borders, and wide rules.

  Returns:
      (gray_rot, clean_bw, best_angle_deg, rule_ys, has_center_divider)
  """
  import cv2

  h, w = gray.shape
  thresh, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
  cut = max(int(thresh), threshold_floor)
  bw0 = (gray < cut).astype(np.uint8)

  small = cv2.resize(bw0, (max(1, w // 3), max(1, h // 3)), interpolation=cv2.INTER_NEAREST)
  sh, sw = small.shape
  best_angle, best_score = 0.0, -1.0
  for ang in np.arange(-2.5, 2.51, 0.15):
    rot_m = cv2.getRotationMatrix2D((sw / 2, sh / 2), ang, 1.0)
    rot = cv2.warpAffine(small, rot_m, (sw, sh), flags=cv2.INTER_NEAREST, borderValue=0)
    proj = rot.sum(axis=1, dtype=np.int64)
    score = float((proj * proj).sum())
    if score > best_score:
      best_score = score
      best_angle = float(ang)

  m_full = cv2.getRotationMatrix2D((w / 2, h / 2), best_angle, 1.0)
  gray_rot = cv2.warpAffine(gray, m_full, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
  bw = (gray_rot < cut).astype(np.uint8)

  num, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
  areas = stats[:, cv2.CC_STAT_AREA]
  xs = stats[:, cv2.CC_STAT_LEFT]
  ys = stats[:, cv2.CC_STAT_TOP]
  cws = stats[:, cv2.CC_STAT_WIDTH]
  chs = stats[:, cv2.CC_STAT_HEIGHT]

  # Detect wide horizontal footnote/table rules before stripping them
  rule_mask = (
      (np.arange(num) > 0)
      & (cws > 0.25 * w)
      & (chs <= 24)
      & (ys > int(0.18 * h))
      & (ys < int(0.95 * h))
  )
  rule_ys = [int(ys[cid] + chs[cid] / 2) for cid in np.where(rule_mask)[0]]

  # Detect vertical two-column table divider (errata / index pages)
  center_div = (
      (np.arange(num) > 0)
      & (chs > 0.25 * h)
      & (cws <= 25)
      & (xs >= int(0.42 * w))
      & (xs <= int(0.58 * w))
  )
  has_center_divider = bool(center_div.any())

  keep = np.ones(num, dtype=bool)
  keep[0] = False
  margin_crease = (cws <= 12) & (chs > 0.04 * h) & ((xs < 0.14 * w) | (xs + cws > 0.89 * w))
  bad = (
      (areas < 8)
      | (chs > 0.08 * h)
      | (cws > 0.25 * w)
      | (xs < 0.09 * w)
      | (xs + cws > 0.945 * w)
      | margin_crease
  )
  keep[bad] = False
  clean_bw = keep[labels].astype(np.uint8)
  return gray_rot, clean_bw, best_angle, rule_ys, has_center_divider


def _is_bimodal_double_bar(comp: np.ndarray, cw: int, ch: int) -> bool:
  """Return True if a fused vertical accent component shows two vertical bars (||)."""
  if cw < 11 or cw > 26 or (ch / cw) < 1.32:
    return False
  col_sums = comp.sum(axis=0)
  for k in range(2, cw - 2):
    lp = int(col_sums[:k].max())
    rp = int(col_sums[k + 1 :].max())
    min_peak = min(lp, rp)
    if min_peak < 0.55 * ch:
      continue
    if col_sums[k] <= 0.60 * min_peak:
      return True
  return False


def _merge_vertical_bar_fragments(frags: list[dict]) -> list[dict]:
  """Merge vertically collinear accent bar fragments split by a small ink break."""
  if len(frags) <= 1:
    return frags
  frags = sorted(frags, key=lambda d: (d["y"], d["cx"]))
  used = [False] * len(frags)
  merged = []
  for i, a in enumerate(frags):
    if used[i]:
      continue
    cur = dict(a)
    used[i] = True
    changed = True
    while changed:
      changed = False
      for j, b in enumerate(frags):
        if used[j]:
          continue
        gap = b["y"] - (cur["y"] + cur["h"])
        if -2 <= gap <= 6 and abs(b["cx"] - cur["cx"]) <= 2.5 and max(cur["w"], b["w"]) <= 8:
          x0 = min(cur["x"], b["x"])
          y0 = min(cur["y"], b["y"])
          x1 = max(cur["x"] + cur["w"], b["x"] + b["w"])
          y1 = max(cur["y"] + cur["h"], b["y"] + b["h"])
          cur = dict(
              x=x0,
              y=y0,
              w=x1 - x0,
              h=y1 - y0,
              cx=(x0 + x1) / 2.0,
              cy=(y0 + y1) / 2.0,
              area=cur["area"] + b["area"],
          )
          used[j] = True
          changed = True
    merged.append(cur)
  return merged


def _merge_horizontal_unders(unders: list[dict]) -> list[dict]:
  """Merge broken collinear anudātta (_) halves separated by a tiny horizontal gap."""
  if len(unders) <= 1:
    return unders
  unders = sorted(unders, key=lambda d: d["x"])
  merged = []
  for u in unders:
    if merged:
      prev = merged[-1]
      gap = u["x"] - (prev["x"] + prev["w"])
      tot_w = (u["x"] + u["w"]) - prev["x"]
      if -2 <= gap <= 6 and abs(u["cy"] - prev["cy"]) <= 4 and tot_w <= 52:
        x0 = min(prev["x"], u["x"])
        y0 = min(prev["y"], u["y"])
        x1 = max(prev["x"] + prev["w"], u["x"] + u["w"])
        y1 = max(prev["y"] + prev["h"], u["y"] + u["h"])
        merged[-1] = dict(
            x=x0,
            y=y0,
            w=x1 - x0,
            h=y1 - y0,
            cx=(x0 + x1) / 2.0,
            cy=(y0 + y1) / 2.0,
            area=prev["area"] + u["area"],
        )
        continue
    merged.append(u)
  return merged


def find_body_lines(bw: np.ndarray, stats: np.ndarray) -> list[int]:
  """Find horizontal baseline y-coordinates of printed lines, skipping running header."""
  import cv2
  from scipy.ndimage import gaussian_filter1d
  from scipy.signal import find_peaks

  h, _ = bw.shape
  proj = bw.sum(axis=1).astype(np.float64)
  s_proj = gaussian_filter1d(proj, sigma=7.0)
  if s_proj.max() == 0:
    return []
  peaks, _ = find_peaks(s_proj, distance=95, prominence=s_proj.max() * 0.10)
  peaks = [int(p) for p in peaks if 165 <= p <= h - 60]

  while len(peaks) >= 2 and peaks[0] < 440 and (peaks[1] - peaks[0]) > 168:
    peaks = peaks[1:]
  if not peaks:
    return []

  med_s = float(np.median(s_proj[peaks]))
  ys = stats[1:, cv2.CC_STAT_TOP]
  cws = stats[1:, cv2.CC_STAT_WIDTH]
  chs = stats[1:, cv2.CC_STAT_HEIGHT]
  areas = stats[1:, cv2.CC_STAT_AREA]

  body_peaks = []
  for p in peaks:
    if s_proj[p] < 0.22 * med_s:
      continue
    cross = (
        (ys <= p + 14)
        & (ys + chs >= p - 14)
        & (areas >= 45)
        & (chs <= 95)
        & ((cws >= 10) | (chs >= 16))
    )
    if int(cross.sum()) >= 2:
      body_peaks.append(p)
  return body_peaks


def detect_page_accents(
    img: np.ndarray | str | Path,
    return_arrays: bool = False,
) -> dict:
  """Detect line baselines and Vedic accent marks (|, ||, _) on a 300-DPI grayscale page."""
  import cv2

  if isinstance(img, (str, Path)):
    gray = cv2.imread(str(img), cv2.IMREAD_GRAYSCALE)
    if gray is None:
      raise FileNotFoundError(f"Could not read image: {img}")
  else:
    gray = img

  gray_rot, bw, angle, rule_ys, has_center_divider = deskew_and_clean(gray)
  num, labels, stats, centroids = cv2.connectedComponentsWithStats(bw, connectivity=8)
  peaks = find_body_lines(bw, stats)

  xs = stats[:, cv2.CC_STAT_LEFT]
  ys = stats[:, cv2.CC_STAT_TOP]
  cws = stats[:, cv2.CC_STAT_WIDTH]
  chs = stats[:, cv2.CC_STAT_HEIGHT]
  areas = stats[:, cv2.CC_STAT_AREA]
  glyph_mask = (np.arange(num) > 0) & (cws >= 10) & (areas >= 85) & (chs >= 10) & (chs <= 95)

  lines_out = []
  tot_bars = tot_dbars = tot_unders = 0

  for li, py in enumerate(peaks):
    next_py = peaks[li + 1] if li + 1 < len(peaks) else 99999
    line_glyphs = np.where(glyph_mask & (ys <= py + 26) & (ys + chs >= py - 20))[0]

    def has_core_support(x0: int, x1: int) -> bool:
      if len(line_glyphs) == 0:
        return False
      gx0 = xs[line_glyphs]
      gx1 = gx0 + cws[line_glyphs]
      ov = (gx1 >= x0 - 12) & (gx0 <= x1 + 12)
      return int(areas[line_glyphs[ov]].sum()) >= 150

    bar_frags, bars, dbars, unders = [], [], [], []
    y_lo = py - 84
    y_hi = min(py + 90, next_py - 22)
    in_band = np.where((np.arange(num) > 0) & (ys >= y_lo) & (ys <= y_hi))[0]

    for cid in in_band:
      x = int(xs[cid])
      y = int(ys[cid])
      cw = int(cws[cid])
      ch = int(chs[cid])
      area = int(areas[cid])
      cx, cy = float(centroids[cid][0]), float(centroids[cid][1])
      fill = area / float(cw * ch)

      if (py - 84 <= y <= py - 20) and (y + ch <= py - 14):
        if (1 <= cw <= 8) and (6 <= ch <= 54) and fill >= 0.35:
          if has_core_support(x, x + cw):
            bar_frags.append(dict(x=x, y=y, w=cw, h=ch, cx=cx, cy=cy, area=area))
          continue
        if (15 <= ch <= 54) and cw <= 26 and (ch / cw) >= 1.32 and fill >= 0.40:
          comp = (labels[y : y + ch, x : x + cw] == cid).astype(np.uint8)
          if _is_bimodal_double_bar(comp, cw, ch):
            if has_core_support(x, x + cw):
              dbars.append(dict(x=x, y=y, w=cw, h=ch, cx=cx, cy=cy, area=area))
            continue
          if (9 <= cw <= 12) and (ch / cw) >= 2.0 and (y <= py - 24):
            if has_core_support(x, x + cw):
              bars.append(dict(x=x, y=y, w=cw, h=ch, cx=cx, cy=cy, area=area))
            continue

      if (y >= py + 18) and (py + 24 <= cy <= py + 90) and (y + ch <= next_py - 18):
        if any(abs(cy - ry) <= 8 for ry in rule_ys):
          continue
        if (14 <= cw <= 58) and (2 <= ch <= 12) and (cw / ch >= 2.1) and fill >= 0.45:
          comp = (labels[y : y + ch, x : x + cw] == cid).astype(np.uint8)
          cs = comp.sum(axis=0)
          t = cw // 3
          if t >= 3:
            left_m = float(cs[:t].mean())
            mid_m = float(cs[t : 2 * t].mean())
            right_m = float(cs[2 * t :].mean())
            mn = min(left_m, mid_m, right_m)
            if mn > 0 and (max(left_m, mid_m, right_m) / mn) <= 2.2:
              if has_core_support(x, x + cw):
                unders.append(dict(x=x, y=y, w=cw, h=ch, cx=cx, cy=cy, area=area))

    for mb in _merge_vertical_bar_fragments(bar_frags):
      if (15 <= mb["h"] <= 54) and (1 <= mb["w"] <= 12) and (mb["h"] / mb["w"] >= 2.0) and (mb["y"] <= py - 24):
        bars.append(mb)

    bars.sort(key=lambda d: d["cx"])
    paired_dbars = list(dbars)
    single_bars = []
    i = 0
    while i < len(bars):
      if i + 1 < len(bars):
        a, b = bars[i], bars[i + 1]
        if (b["cx"] - a["cx"] <= 22) and abs(a["cy"] - b["cy"]) <= 14 and max(a["h"], b["h"]) >= 18:
          x0 = min(a["x"], b["x"])
          y0 = min(a["y"], b["y"])
          x1 = max(a["x"] + a["w"], b["x"] + b["w"])
          y1 = max(a["y"] + a["h"], b["y"] + b["h"])
          paired_dbars.append(
              dict(
                  x=x0,
                  y=y0,
                  w=x1 - x0,
                  h=y1 - y0,
                  cx=(a["cx"] + b["cx"]) / 2.0,
                  cy=(a["cy"] + b["cy"]) / 2.0,
              )
          )
          i += 2
          continue
      single_bars.append(bars[i])
      i += 1

    paired_dbars.sort(key=lambda d: d["cx"])
    unders = _merge_horizontal_unders(unders)
    tot_bars += len(single_bars)
    tot_dbars += len(paired_dbars)
    tot_unders += len(unders)
    lines_out.append(dict(py=py, bars=single_bars, dbars=paired_dbars, unders=unders))

  out = dict(
      angle=angle,
      peaks=peaks,
      lines=lines_out,
      n_bars=tot_bars,
      n_dbars=tot_dbars,
      n_unders=tot_unders,
      rule_ys=rule_ys,
      has_center_divider=has_center_divider,
      shape=list(gray_rot.shape),
  )
  if return_arrays:
    out.update(bw=bw, gray_rot=gray_rot, labels=labels, stats=stats)
  return out


def build_clean_line_canvases(
    page_res: dict,
    line_gap: int = 170,
    max_lines_per_canvas: int = 7,
    number_lines: bool = False,
) -> list[np.ndarray]:
  """Build separated, accent-stripped grayscale strips for cleaner OCR / Vision proofing."""
  import cv2

  if "gray_rot" not in page_res:
    raise ValueError("build_clean_line_canvases requires page_res with return_arrays=True")

  g = page_res["gray_rot"].copy()
  h, w = g.shape
  g[:, : int(0.09 * w)] = 255
  g[:, int(0.945 * w) :] = 255
  for ry in page_res["rule_ys"]:
    g[max(0, ry - 8) : min(h, ry + 8), :] = 255
  for ld in page_res["lines"]:
    for m in ld["bars"] + ld["dbars"] + ld["unders"]:
      g[max(0, m["y"] - 2) : min(h, m["y"] + m["h"] + 2), max(0, m["x"] - 2) : min(w, m["x"] + m["w"] + 2)] = 255

  lines = page_res["lines"]
  peaks = page_res["peaks"]
  if not lines:
    return []

  canvases = []
  x_l, x_r = int(0.09 * w), int(0.945 * w)
  for start in range(0, len(lines), max_lines_per_canvas):
    strips = []
    for i in range(start, min(start + max_lines_per_canvas, len(lines))):
      py = lines[i]["py"]
      y0 = max(0, py - 30, (peaks[i - 1] + 55) if i > 0 else 0)
      y1 = min(h, py + 60, (peaks[i + 1] - 28) if i + 1 < len(peaks) else h)
      strip = g[y0:y1, x_l:x_r]
      if number_lines:
        pad_l = np.full((strip.shape[0], 110), 255, dtype=np.uint8)
        cv2.putText(pad_l, f"{i + 1:02d})", (12, max(25, py - y0 + 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (40,), 2)
        strip = np.hstack([pad_l, strip])
      strips.append(strip)
      strips.append(np.full((line_gap, strip.shape[1]), 255, dtype=np.uint8))
    top_pad = np.full((60, strips[0].shape[1]), 255, dtype=np.uint8)
    canvases.append(np.vstack([top_pad] + strips))
  return canvases


def extract_visual_units(page_res: dict) -> tuple[list[list[dict]], list[dict]]:
  """Segment each body line into horizontal glyph units and bind detected accents to them."""
  import cv2

  if "bw" not in page_res:
    raise ValueError("extract_visual_units requires page_res with return_arrays=True")

  bw = page_res["bw"].copy()
  h, w = bw.shape
  for ry in page_res["rule_ys"]:
    bw[max(0, ry - 8) : min(h, ry + 8), :] = 0
  for ld in page_res["lines"]:
    for m in ld["bars"] + ld["dbars"] + ld["unders"]:
      bw[max(0, m["y"] - 1) : min(h, m["y"] + m["h"] + 1), max(0, m["x"] - 1) : min(w, m["x"] + m["w"] + 1)] = 0

  lines_units = []
  flat_units = []
  peaks = page_res["peaks"]
  for li, ld in enumerate(page_res["lines"]):
    py = ld["py"]
    y0 = max(0, py - 20)
    y1 = min(h, py + 26)
    band_core = bw[y0:y1, :]
    col = band_core.sum(axis=0) > 0
    raw = []
    in_run, s = False, 0
    for x in range(w):
      if col[x] and not in_run:
        in_run, s = True, x
      elif not col[x] and in_run:
        in_run = False
        raw.append([s, x])
    if in_run:
      raw.append([s, w])

    segs = []
    for a, b in raw:
      seg_w = b - a
      sub = band_core[:, a:b]
      mass = int(sub.sum())
      rows = np.where(sub.sum(axis=1) > 0)[0]
      core_h = int(rows[-1] - rows[0] + 1) if len(rows) else 0
      if mass < 20 and seg_w < 10 and core_h < 22:
        continue
      fill = mass / max(1, seg_w * core_h)
      is_d1 = (2 <= seg_w <= 11) and (core_h >= 24) and (fill >= 0.45)
      segs.append(dict(x0=a, x1=b, w=seg_w, h=core_h, mass=mass, is_d1=is_d1, line=li))

    while segs and segs[0]["w"] <= 38 and segs[0]["mass"] < 280 and len(segs) >= 2 and (segs[1]["x0"] - segs[0]["x1"] >= 55):
      segs.pop(0)
    while segs and segs[-1]["w"] <= 38 and segs[-1]["mass"] < 280 and len(segs) >= 2 and (segs[-1]["x0"] - segs[-2]["x1"] >= 55):
      segs.pop()

    # Rejoin detached left stem of r-ottu glyphs (ప్ర, బ్ర, శ్రీ, క్రీ, ద్రు) via full glyph CC
    prev_py = peaks[li - 1] if li > 0 else -999
    next_py = peaks[li + 1] if li + 1 < len(peaks) else 99999
    fy0 = max(0, py - 24, prev_py + 52)
    fy1 = min(h, py + 54, next_py - 28)
    if fy1 > fy0 + 10 and len(segs) > 1:
      band_full = bw[fy0:fy1, :]
      _, lbl_f, st_f, _ = cv2.connectedComponentsWithStats(band_full, connectivity=8)
      core_off_y0 = max(0, y0 - fy0)
      core_off_y1 = max(core_off_y0 + 1, min(band_full.shape[0], y1 - fy0))
      lbl_core = lbl_f[core_off_y0:core_off_y1, :]
      seg_cids = []
      for sg in segs:
        cids = set(np.unique(lbl_core[:, sg["x0"] : sg["x1"]])) - {0}
        good_cids = {c for c in cids if st_f[c, cv2.CC_STAT_AREA] >= 25 and st_f[c, cv2.CC_STAT_WIDTH] <= 135}
        seg_cids.append(good_cids)
      merged_segs = []
      k = 0
      while k < len(segs):
        cur = dict(segs[k])
        cur_cids = set(seg_cids[k])
        while k + 1 < len(segs) and (cur_cids & seg_cids[k + 1]) and (segs[k + 1]["x1"] - cur["x0"] <= 135):
          nxt = segs[k + 1]
          cur_cids |= seg_cids[k + 1]
          cur = dict(
              x0=cur["x0"],
              x1=nxt["x1"],
              w=nxt["x1"] - cur["x0"],
              h=max(cur["h"], nxt["h"]),
              mass=cur["mass"] + nxt["mass"],
              is_d1=False,
              line=li,
          )
          k += 1
        merged_segs.append(cur)
        k += 1
      segs = merged_segs

    units = []
    i = 0
    while i < len(segs):
      u = dict(segs[i])
      if i + 1 < len(segs) and u["is_d1"] and segs[i + 1]["is_d1"] and (segs[i + 1]["x0"] - u["x1"] <= 12):
        nxt = segs[i + 1]
        u = dict(
            x0=u["x0"],
            x1=nxt["x1"],
            w=nxt["x1"] - u["x0"],
            h=max(u["h"], nxt["h"]),
            mass=u["mass"] + nxt["mass"],
            is_d1=False,
            is_d2=True,
            line=li,
        )
        i += 2
      else:
        u["is_d2"] = False
        i += 1
      units.append(u)

    for ui, u in enumerate(units):
      u["unit_idx"] = ui
      u["line_start"] = ui == 0
      u["gap_before"] = 999 if ui == 0 else (u["x0"] - units[ui - 1]["x1"])
      u["space_before"] = u["line_start"] or (u["gap_before"] >= 14)
      u["accents"] = []

    all_marks = (
        [("||", m) for m in ld["dbars"]]
        + [("|", m) for m in ld["bars"]]
        + [("_", m) for m in ld["unders"]]
    )
    glyph_units = [u for u in units if not (u["is_d1"] or u["is_d2"])]
    if glyph_units:
      for mtype, m in all_marks:
        mx0, mx1, mcx = m["x"], m["x"] + m["w"], m["cx"]
        best_u = None
        best_score = 1e9
        for u in glyph_units:
          ov = max(0, min(mx1, u["x1"]) - max(mx0, u["x0"]))
          dist = 0 if ov > 0 else min(abs(mcx - u["x0"]), abs(mcx - u["x1"]))
          center_d = abs(mcx - (u["x0"] + u["x1"]) / 2.0)
          sc = dist * 10.0 + center_d - ov * 5.0 - (12.0 if u["w"] >= 22 else 0.0)
          if sc < best_score:
            best_score = sc
            best_u = u
        if best_u is not None and best_score < 600:
          best_u["accents"].append((mtype, m))

    lines_units.append(units)
    for u in units:
      u["flat_idx"] = len(flat_units)
      flat_units.append(u)
  return lines_units, flat_units


def clean_drive_markdown(raw: str) -> str:
  """Strip Google Drive Markdown escapes/emphasis and non-Telugu OCR speck lines."""
  s = re.sub(r"\\([!*\|\[\]_~`#>-])", r"\1", raw)
  s = re.sub(r"\*\*([^*]+?)\*\*", r"\1", s)
  s = s.replace("**", "")
  lines = []
  for ln in s.splitlines():
    st = ln.strip()
    if not st:
      continue
    if re.fullmatch(r"[>\s|!1IlL24.,\-/\\]+", st) and not any("\u0C00" <= c <= "\u0C7F" for c in st):
      continue
    lines.append(st)
  return "\n".join(lines)


def tokenize_telugu_aksaras(text: str) -> list[dict]:
  """Tokenize Telugu OCR text into akṣara, daṇḍa, numeral, and misc tokens with width priors."""
  tokens = []
  i = 0
  n = len(text)
  space_before = False

  while i < n:
    ch = text[i]
    if ch.isspace():
      space_before = True
      i += 1
      continue
    if text[i : i + 2] in ("||", "॥", "II", "|।", "।|"):
      tokens.append(dict(text="॥", kind="d2", space_before=space_before, pred_w=20.0, split_ok=True))
      space_before = False
      i += 2
      continue
    if ch in ("|", "।", "॥", "!"):
      kind = "d2" if ch == "॥" else "d1"
      tokens.append(
          dict(
              text="॥" if kind == "d2" else "।",
              kind=kind,
              space_before=space_before,
              pred_w=18.0 if kind == "d2" else 7.0,
              split_ok=(kind == "d2"),
          )
      )
      space_before = False
      i += 1
      continue
    if ch in TELUGU_DIGITS or ch.isdigit():
      tokens.append(dict(text=ch, kind="num", space_before=space_before, pred_w=38.0, split_ok=False))
      space_before = False
      i += 1
      continue
    if ch in TELUGU_CONSONANTS or ch in TELUGU_VOWELS:
      j = i + 1
      has_ottu = False
      if ch in TELUGU_CONSONANTS:
        while j + 1 < n and text[j] == TELUGU_VIRAMA and text[j + 1] in TELUGU_CONSONANTS:
          has_ottu = True
          j += 2
        if j < n and text[j] == TELUGU_VIRAMA:
          j += 1
      while j < n and text[j] in TELUGU_MATRAS:
        j += 1
      has_mod = False
      while j < n and text[j] in TELUGU_MODS:
        has_mod = True
        j += 1
      tok = text[i:j]
      pw = 40.0
      if has_ottu:
        pw += 16.0
      if any(m in tok for m in ("\u0C3E", "\u0C4A", "\u0C4B", "\u0C4C")):
        pw += 26.0
      elif any(m in tok for m in ("\u0C46", "\u0C47", "\u0C48")):
        pw += 14.0
      elif any(m in tok for m in ("\u0C3F", "\u0C40", "\u0C41", "\u0C42", "\u0C43")):
        pw += 6.0
      if "య" in tok:
        pw += 28.0
      elif any(c in tok for c in ("మ", "భ", "ష", "స", "వ", "హ")):
        pw += 12.0
      if has_mod:
        pw += 20.0
      split_ok = (
          has_mod
          or any(m in tok for m in ("\u0C3E", "\u0C43", "\u0C44", "\u0C46", "\u0C47", "\u0C48", "\u0C4A", "\u0C4B", "\u0C4C"))
          or any(sub in tok for sub in ("్య", "్మ", "్న", "్వ", "్ర", "్స"))
      )
      tokens.append(dict(text=tok, kind="ak", space_before=space_before, pred_w=pw, split_ok=split_ok))
      space_before = False
      i = j
      continue
    if ch in TELUGU_MODS or ch in TELUGU_MATRAS:
      if tokens and not space_before:
        tokens[-1]["text"] += ch
        tokens[-1]["pred_w"] += 16.0
        tokens[-1]["split_ok"] = True
      else:
        tokens.append(dict(text=ch, kind="other", space_before=space_before, pred_w=24.0, split_ok=False))
      space_before = False
      i += 1
      continue
    # Keep avagraha (ఽ) separate so an accent on the preceding vowel renders before ऽ
    if ch == TELUGU_AVAGRAHA:
      tokens.append(dict(text=ch, kind="other", space_before=space_before, pred_w=30.0, split_ok=False))
      space_before = False
      i += 1
      continue
    tokens.append(dict(text=ch, kind="other", space_before=space_before, pred_w=20.0, split_ok=False))
    space_before = False
    i += 1
  return tokens


def align_tokens_to_units(tokens: list[dict], units: list[dict]) -> tuple[float, list[tuple]]:
  """Align base Telugu tokens against segmented line glyph units via banded DP."""
  n = len(tokens)
  m = len(units)
  if n == 0 and m == 0:
    return 0.0, []
  inf = 1e12
  dp = [[inf] * (m + 1) for _ in range(n + 1)]
  bp: list[list[tuple | None]] = [[None] * (m + 1) for _ in range(n + 1)]
  dp[0][0] = 0.0

  # Pre-extract flat primitive arrays to avoid per-cell dict/slice overhead in the inner loop.
  kind_map = {"ak": 0, "num": 1, "d1": 2, "d2": 3}
  t_kind = [kind_map.get(t["kind"], 4) for t in tokens]
  t_pw = [float(t["pred_w"]) for t in tokens]
  t_sb = [bool(t["space_before"]) for t in tokens]
  t_sok = [bool(t.get("split_ok", False)) for t in tokens]
  t_skip_c = [22.0 if k in (0, 1, 3) else 6.0 for k in t_kind]
  pair_pw = [t_pw[i] + t_pw[i + 1] for i in range(max(0, n - 1))]
  pair_has_d = [((t_kind[i] in (2, 3)) or (t_kind[i + 1] in (2, 3))) for i in range(max(0, n - 1))]

  u_line = [u["line"] for u in units]
  u_x0 = [float(u["x0"]) for u in units]
  u_x1 = [float(u["x1"]) for u in units]
  u_w = [u["w"] for u in units]
  u_gap = [u["gap_before"] for u in units]
  u_sb = [bool(u["space_before"]) for u in units]
  u_ls = [bool(u["line_start"]) for u in units]
  u_d1 = [bool(u["is_d1"]) for u in units]
  u_d2 = [bool(u["is_d2"]) for u in units]
  u_skip_c = [44.0 if u["accents"] else (6.0 if u["w"] <= 14 else 26.0) for u in units]

  # Precompute valid 1/2/3-unit segment descriptors indexed by start unit j.
  u_segs: list[list[tuple]] = [[] for _ in range(m)]
  for j in range(m):
    segs = u_segs[j]
    s_pen = 5.0 if (u_sb[j] and (not u_ls[j]) and u_gap[j] >= 20) else 0.0
    sb_j = u_sb[j] or u_ls[j]
    d1_j = u_d1[j]
    d2_j = u_d2[j]
    segs.append((1, u_x1[j] - u_x0[j], sb_j, s_pen, d1_j, d2_j, 0.0, 0.0))
    if j + 1 < m and u_line[j + 1] == u_line[j] and u_gap[j + 1] <= 25:
      is_v_d2 = d1_j and u_d1[j + 1]
      gap_p2 = 0.0 if is_v_d2 else (max(0, u_gap[j + 1] - 7) * 0.6)
      base_p2 = 0.0 if is_v_d2 else 7.5
      sok_p2 = 0.0 if is_v_d2 else 1.0
      segs.append((2, u_x1[j + 1] - u_x0[j], sb_j, s_pen, False, is_v_d2, base_p2 + gap_p2, sok_p2 + gap_p2))
      if j + 2 < m and u_line[j + 2] == u_line[j] and u_gap[j + 2] <= 25:
        mg = max(u_gap[j + 1], u_gap[j + 2])
        gp3 = max(0, mg - 5) * 0.8
        segs.append((3, u_x1[j + 2] - u_x0[j], sb_j, s_pen, False, False, 12.0 + gp3, 5.0 + gp3))

  band = max(45, int(0.28 * max(n, m)))
  ratio = m / max(1, n)
  for i in range(n + 1):
    j_center = int(i * ratio)
    j_lo = max(0, j_center - band)
    j_hi = min(m, j_center + band)
    dp_i = dp[i]
    bp_i = bp[i]
    has_next1 = i < n
    if has_next1:
      dp_i1 = dp[i + 1]
      bp_i1 = bp[i + 1]
      sc = t_skip_c[i]
      tk = t_kind[i]
      tpw = t_pw[i]
      tsb = t_sb[i]
      tsok = t_sok[i]
    has_next2 = i + 2 <= n
    if has_next2:
      dp_i2 = dp[i + 2]
      bp_i2 = bp[i + 2]
      p_pw = pair_pw[i]
      p_has_d = pair_has_d[i]
      p_sb = t_sb[i]

    for j in range(j_lo, j_hi + 1):
      cur = dp_i[j]
      if cur >= inf:
        continue
      if has_next1:
        nc = cur + sc
        if nc < dp_i1[j]:
          dp_i1[j] = nc
          bp_i1[j] = (i, j, "skip_t")
      if j < m:
        nc = cur + u_skip_c[j]
        if nc < dp_i[j + 1]:
          dp_i[j + 1] = nc
          bp_i[j + 1] = (i, j, "skip_u")
      if has_next1 and j < m:
        for ku, vis_w, sb_j, s_pen, is_v_d1, is_v_d2, pen_no_sok, pen_sok in u_segs[j]:
          dw = vis_w - tpw
          if dw < 0.0:
            dw = -dw
          dw_c = 42.0 if dw > 42.0 else dw
          cost = dw * 0.05 + (dw_c * dw_c) * 0.0025
          if tsb:
            if not sb_j:
              cost += 5.0
          else:
            cost += s_pen
          if tk == 3:
            cost += -20.0 if is_v_d2 else (12.0 if is_v_d1 else 45.0)
          elif tk == 2:
            cost += -16.0 if is_v_d1 else (14.0 if is_v_d2 else 35.0)
          elif tk <= 1:
            if is_v_d1 or is_v_d2:
              cost += 45.0
          else:
            if is_v_d1 or is_v_d2:
              cost += 8.0
            elif vis_w > 45.0:
              cost += 12.0
          if ku > 1:
            cost += pen_sok if tsok else pen_no_sok
          nc = cur + cost
          if nc < dp_i1[j + ku]:
            dp_i1[j + ku] = nc
            bp_i1[j + ku] = (i, j, f"m_1_{ku}")
      if has_next2 and j < m:
        ku, vis_w, sb_j, s_pen, is_v_d1, is_v_d2, _, _ = u_segs[j][0]
        if not (is_v_d1 or is_v_d2):
          dw = vis_w - p_pw
          if dw < 0.0:
            dw = -dw
          dw_c = 42.0 if dw > 42.0 else dw
          cost = dw * 0.05 + (dw_c * dw_c) * 0.0025 + 6.0
          if p_sb:
            if not sb_j:
              cost += 5.0
          else:
            cost += s_pen
          if p_has_d:
            cost += 25.0
          if vis_w < 58.0:
            cost += 10.0
          nc = cur + cost
          if nc < dp_i2[j + 1]:
            dp_i2[j + 1] = nc
            bp_i2[j + 1] = (i, j, "m_2_1")

  ops = []
  i, j = n, m
  while i > 0 or j > 0:
    step = bp[i][j]
    if step is None:
      raise RuntimeError(f"DP alignment failed to reach (0, 0) from ({i}, {j}) with n={n}, m={m}")
    pi, pj, op = step
    ops.append((pi, i, pj, j, op))
    i, j = pi, pj
  ops.reverse()
  return float(dp[n][m]), ops


def _attach_accent_to_token(tok_text: str, mark: str) -> str:
  if not mark or not any(c in TELUGU_CONSONANTS or c in TELUGU_VOWELS for c in tok_text):
    return tok_text
  return tok_text + mark


def render_accented_lines(
    tokens: list[dict],
    units: list[dict],
    ops: Iterable[tuple],
    n_lines: int,
    replace_dirgha_svarita: bool = True,
) -> tuple[list[dict], list[tuple[int, dict]], list[dict], list[dict]]:
  """Reconstruct per-line Telugu and Devanagari strings and detect anomalies for Vision QA."""
  line_items: list[list[str]] = [[] for _ in range(n_lines)]
  skipped_tokens: list[tuple[int, dict]] = []
  skipped_units: list[dict] = []
  suspect_lines: dict[int, list[str]] = {}

  def flag_line(line_num: int, reason: str) -> None:
    suspect_lines.setdefault(line_num, [])
    if reason not in suspect_lines[line_num]:
      suspect_lines[line_num].append(reason)

  def mark_for_units(us: list[dict]) -> str:
    marks = [mt for u in us for mt, _ in u["accents"]]
    if not marks:
      return ""
    if "||" in marks:
      return SVARA_DIRGHA_SVARITA
    if "|" in marks:
      return SVARA_SVARITA
    return SVARA_ANUDATTA

  for t0, t1, u0, u1, op in ops:
    if op == "skip_t":
      skipped_tokens.append((t0, tokens[t0]))
      if tokens[t0]["kind"] == "ak":
        near_line = units[min(u0, len(units) - 1)]["line"] + 1 if units else 1
        flag_line(near_line, f"skipped_token:{tokens[t0]['text']}")
      continue
    if op == "skip_u":
      u = units[u0]
      if u["accents"] or u["w"] > 15:
        skipped_units.append(u)
        flag_line(u["line"] + 1, f"skipped_unit:w={u['w']},acc={len(u['accents'])}")
      continue
    li = units[u0]["line"]
    us = units[u0:u1]
    ts = tokens[t0:t1]
    mark = mark_for_units(us)
    if len(ts) == 1:
      if ts[0]["space_before"] and line_items[li]:
        line_items[li].append(" ")
      line_items[li].append(_attach_accent_to_token(ts[0]["text"], mark))
    else:
      if ts[0]["space_before"] and line_items[li]:
        line_items[li].append(" ")
      line_items[li].append(_attach_accent_to_token(ts[0]["text"], mark))
      if ts[1]["space_before"]:
        line_items[li].append(" ")
      line_items[li].append(ts[1]["text"])

  out_lines = []
  for li in range(n_lines):
    te = "".join(line_items[li]).strip()
    deva = sanscript.transliterate(te, sanscript.TELUGU, sanscript.DEVANAGARI)
    if replace_dirgha_svarita:
      deva = deva.replace(SVARA_DIRGHA_SVARITA, SVARA_SVARITA)
    m_susp = SUSPECT_TEXT_RE.search(te)
    if m_susp:
      flag_line(li + 1, f"suspect_text:{m_susp.group(0)}")
    out_lines.append(dict(line=li + 1, te=te, deva=deva))

  flags = [dict(line=ln, reasons=rs) for ln, rs in sorted(suspect_lines.items())]
  return out_lines, skipped_tokens, skipped_units, flags


def process_page_with_text(
    img: np.ndarray | str | Path,
    ocr_text: str,
    replace_dirgha_svarita: bool = True,
) -> dict:
  """End-to-end CV accent detection + OCR alignment for a single page."""
  page_res = detect_page_accents(img, return_arrays=True)
  lines_units, flat_units = extract_visual_units(page_res)
  cleaned = clean_drive_markdown(ocr_text)
  tokens = tokenize_telugu_aksaras(cleaned)
  dp_cost, ops = align_tokens_to_units(tokens, flat_units)
  out_lines, sk_t, sk_u, flags = render_accented_lines(
      tokens,
      flat_units,
      ops,
      len(lines_units),
      replace_dirgha_svarita=replace_dirgha_svarita,
  )
  return dict(
      angle=page_res["angle"],
      peaks=page_res["peaks"],
      n_bars=page_res["n_bars"],
      n_dbars=page_res["n_dbars"],
      n_unders=page_res["n_unders"],
      rule_ys=page_res["rule_ys"],
      has_center_divider=page_res["has_center_divider"],
      dp_cost=dp_cost,
      tokens_count=len(tokens),
      units_count=len(flat_units),
      skipped_tokens_count=len(sk_t),
      skipped_units_count=len(sk_u),
      flags=flags,
      lines=out_lines,
  )
