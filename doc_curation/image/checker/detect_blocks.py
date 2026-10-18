"""Detect core (top) vs commentary (body) blocks; write canonical data volumes (GT later).

Layout: URL (<4%), header + double rules (~4-10%), [core + rule when present], comm, footer (>94%).
Method: per-page DESKEW (scans tilt up to ~2deg; a tilted separator rule is eroded by the
wide horizontal opening, so the core was never split - see vol01 p0041/p0051, vol02 p0048).
Angle = argmax of dark px surviving a 0.6w horizontal opening (cached in metadata/skew.json).
Short centred mUlam-end rules (<0.6w, e.g. vol01 p0070) cannot win that metric; when no
separator is found the page is re-searched at fine angles for a thin short rule (refine_rule_angle).
Colour plates (front-matter photos, mean saturation>30) are skipped (bogus full-page core).
Ghost pages (plate/adhyAya backs showing only faint bleed-through; 0.5th-pct gray>100) too.
Then OTSU inv + horizontal MORPH_OPEN (kw=0.3w), keep cw>0.3w, merge collinear segs (dy<=6).
Only lines with clear space below (ink_below<0.15 in a 10px band) count as RULES; Devanagari
shirorekhas / Tamil ligature rows have text underneath and are rejected (vol01 p0059 had a
451px headline above the true 1005px separator). header = rule lines yc<14%, separator =
first rule line yc in [12%,92%] with width>0.32w.
Verified on eval (vol01): p0042 none; p0043 sep y=244; p0044 sep y=455.

Usage (canonical, from the doc_curation repo root; page data lives in the
maNipravALa-ocr repo, auto-detected as a sibling or via --root / $MANIPRAVALA_OCR_ROOT):
  python3 -m doc_curation.image.checker.detect_blocks --vol 01
  python3 -m doc_curation.image.checker.detect_blocks --vol 01 --subset 0:70
  python3 -m doc_curation.image.checker.detect_blocks --check-crops
Writes {root}/data/RTS_sb_0V/images/{core,comm}/pXXXX.jpg +
{root}/data/RTS_sb_0V/metadata/blocks.json (merged) + crop_errors.json.
GT deferred (no text here). Legacy --images/--out still supported.
"""
import argparse
import json
import glob
import os
import pathlib
import cv2
import numpy as np

def _default_root():
    """The maNipravALa-ocr repo: --root flag / $MANIPRAVALA_OCR_ROOT / sibling repo / cwd."""
    cands = []
    env = os.environ.get("MANIPRAVALA_OCR_ROOT")
    if env:
        cands.append(pathlib.Path(env).expanduser())
    for p in pathlib.Path(__file__).resolve().parents:
        cands.append(p / "maNipravALa-ocr")
        cands.append(p)
    cands.append(pathlib.Path.cwd())
    for c in cands:
        if (c / "data" / "RTS_sb_01" / "pages_raw").is_dir():
            return c
    return pathlib.Path.cwd()

# Scans are skewed by up to ~2deg. A tilted separator rule is eroded by the wide
# horizontal opening (no single row keeps a 0.35w run), so the core is never split
# from the commentary (e.g. vol01 p0041/p0051, vol02 p0048). Deskew each page first;
# page skew is uniform, so aligning to text baselines or rules yields the same angle.
def estimate_skew(gray, maxa=2.0, step=0.1, scale=0.5):
    h, w = gray.shape
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bw = cv2.resize(bw, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    hh, ww = bw.shape
    c = (ww / 2, hh / 2)
    kc = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (int(0.6 * ww), 1))
    best = (0.0, 0)
    for a in np.arange(-maxa, maxa + 1e-9, step):
        M = cv2.getRotationMatrix2D(c, float(a), 1.0)
        r = cv2.warpAffine(bw, M, (ww, hh), flags=cv2.INTER_NEAREST, borderValue=0)
        # NN rotation of a 1-2px line leaves aliasing gaps; bridge them or thin rules
        # never survive the 0.6w opening (e.g. vol01 p0086: 1deg tilt, score 0 -> no
        # deskew -> separator missed -> core merged into comm). 3px is below the
        # inter-letter gaps at 0.5 scale so text rows still do not survive the
        # opening; 5px already bridges word gaps on dense pages and creates spurious
        # full-width "rules" at wrong angles (vol02 p0264, p0595).
        r = cv2.morphologyEx(r, cv2.MORPH_CLOSE, kc)
        op = cv2.morphologyEx(r, cv2.MORPH_OPEN, k)
        score = int((op > 0).sum())
        if score > best[1]:
            best = (round(float(a), 2), score)
    # Pages with no long horizontal line (front matter, plates): leave unrotated.
    return best if best[1] >= 200 else (0.0, best[1])

def deskew_image(img, angle):
    if abs(angle) < 0.05:
        return img
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), float(angle), 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))

def _hough_rule(gray):
    """Hough fallback for wavy short rules (local scan warp defeats row-run methods).

    Single-row run tests cannot see a rule whose slope varies along its length (vol01
    p0228: ink spreads over 20 rows, max run 311px < 0.3w even after a global deskew).
    HoughLinesP finds the collinear fragments; fragments at similar angle and intercept
    are merged, and the merged line must be THIN (median vertical extent <=9px; text
    rows are ~30px tall) with clear space below. Returns dict(angle, x0, x1, c, below)
    in raw-page coordinates or None.
    """
    h, w = gray.shape
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    lines = cv2.HoughLinesP(bw, 1, np.pi / 720, threshold=80,
                            minLineLength=int(0.08 * w), maxLineGap=12)
    if lines is None:
        return None
    segs = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        if x2 < x1:
            x1, y1, x2, y2 = x2, y2, x1, y1
        dx, dy = x2 - x1, y2 - y1
        if dx < 0.08 * w:
            continue
        ang = float(np.degrees(np.arctan2(dy, dx)))
        if abs(ang) > 2.5:
            continue
        yc = (y1 + y2) / 2
        if not (0.12 * h < yc < 0.92 * h):
            continue
        segs.append((ang, yc, x1, x2))
    best = None
    for a in np.arange(-2.0, 2.0 + 1e-9, 0.1):
        rad = float(np.radians(a))
        cand = [s for s in segs if abs(s[0] - a) <= 0.2]
        if not cand:
            continue
        proj = sorted((-((s[2] + s[3]) / 2) * np.sin(rad) + s[1] * np.cos(rad), s) for s in cand)
        clusters = []
        for c, s in proj:
            if clusters and c - clusters[-1][0] <= 10:
                clusters[-1][1].append(s)
            else:
                clusters.append([c, [s]])
        for c, members in clusters:
            members.sort(key=lambda s: s[2])
            x0, x1 = members[0][2], members[0][3]
            for s in members[1:]:
                if s[2] - x1 > 0.12 * w + 20:
                    x0, x1 = s[2], s[3]
                    continue
                x1 = max(x1, s[3])
            span = x1 - x0
            if span < 0.32 * w:
                continue
            ext, ink, above = [], [], []
            for x in range(x0, x1, 3):
                yl = int(round((c + x * np.sin(rad)) / np.cos(rad)))
                if yl - 15 < 0 or yl + 16 >= h:
                    continue
                ys = np.where(bw[yl - 15:yl + 16, x] > 0)[0]
                if len(ys):
                    ext.append(int(ys[-1] - ys[0]))
                b = bw[yl + 4:yl + 12, x]
                ink.append(float((b > 0).mean()))
                a = bw[yl - 9:yl - 2, x]
                above.append(float((a > 0).mean()))
            med = float(np.median(ext)) if ext else 999.0
            below = float(np.mean(ink)) if ink else 1.0
            # Clear space ABOVE too: a line tracking the lower strokes of a text row
            # (vol01 p0058/p0490) has the row's body just above it; a real rule has
            # whitespace above (end of the mUlam line's descender gap). Empirically
            # rules <=0.02, text-chained lines ~0.32.
            abv = float(np.mean(above)) if above else 1.0
            if med > 9 or below > 0.15 or abv > 0.10:
                continue
            if best is None or span > best["span"]:
                best = {"span": int(span), "angle": round(float(a), 2),
                        "x0": int(x0), "x1": int(x1), "c": float(c), "below": below}
    return best

def refine_rule_angle(gray, maxa=2.0, step=0.2, scale=0.5):
    """Search for a SHORT body separator rule that estimate_skew cannot see.

    The book marks the end of a mUlam passage with a SHORT CENTRED rule (0.32-0.45w,
    e.g. vol01 p0070: 488px = 0.38w, tilted 1.4deg, y=411; or vol01 p0228 at y=278)
    before the passage's commentary starts. Such rules never survive estimate_skew's
    0.6w opening, so the page stays unrotated and find_hlines misses them -> the
    mUlam tail is merged into the comm crop. Pass 1 tries the whole page at fine
    angles with a thin+clear-below test; pass 2 (Hough) handles locally wavy rules.
    Returns dict(angle, x0, x1, c, below) in raw-page coordinates or None.
    """
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bws = cv2.resize(bw, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    hh, ww = bws.shape
    kc = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, int(0.30 * ww)), 1))
    best = None
    for a in np.arange(-maxa, maxa + 1e-9, step):
        M = cv2.getRotationMatrix2D((ww / 2, hh / 2), float(a), 1.0)
        r = cv2.warpAffine(bws, M, (ww, hh), flags=cv2.INTER_NEAREST, borderValue=0)
        rc = cv2.morphologyEx(r, cv2.MORPH_CLOSE, kc)
        op = cv2.morphologyEx(rc, cv2.MORPH_OPEN, k)
        contours, _ = cv2.findContours(op, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            if cw < 0.32 * ww or ch > 8 or not (hh * 0.12 < y < hh * 0.92):
                continue
            band = rc[y + ch + 1:y + ch + 5, x:x + cw]
            ink = float((band > 0).mean()) if band.size else 1.0
            if ink < 0.15 and (best is None or cw > best[1]):
                best = (round(float(a), 2), cw, x, x + cw, y + ch / 2, ink)
    if best:
        a, cw, x0, x1, yc, ink = best
        x0f, x1f = x0 / scale, x1 / scale
        ym = yc / scale
        xm = (x0f + x1f) / 2
        rad = float(np.radians(a))
        c = -xm * np.sin(rad) + ym * np.cos(rad)
        return {"span": int(cw / scale), "angle": a, "x0": int(x0f), "x1": int(x1f),
                "c": float(c), "below": ink}
    return _hough_rule(gray)

def header_and_seps(lines, frags, w, h):
    """Header bottom + separator candidates from detected lines/fragments."""
    # Header bottom: below detected double-rules when present; else just below the
    # archive.org URL (~2%) with margin. Fixed 10% fallback CUT the first text line
    # on front-matter pages without running headers (text starts ~7-8%), so use 4.5%.
    # Faded header rules (e.g. vol02 p0057: only ~200px fragments survive) would still
    # leak into the crop, so honour rule-like fragmentary header lines too (max bottom + 5).
    header_bottom = int(h * 0.045) + 8
    # Separator candidates first: header lines must lie strictly ABOVE the separator.
    # (A high separator, e.g. vol01 p0043 at yc=13.8%, would otherwise be counted as a
    # header line and swallow the core block.)
    # Only true rules (clear space below) are separator/header candidates; text strokes
    # (shirorekha/ligature rows) are ignored. See find_hlines for the vol01 p0059 story.
    rule_lines = [L for L in lines if L.get("rule")]
    seps = [L for L in rule_lines if h * 0.12 < L["yc"] < h * 0.92 and L["w"] > w * 0.32]
    sep_yc = seps[0]["yc"] if seps else None
    # find header lines strictly above the separator (and <14%h)
    hlim = h * 0.14 if sep_yc is None else min(h * 0.14, sep_yc - 10)
    top_lines = [L for L in rule_lines if L["yc"] < hlim]
    if not top_lines:
        top_lines = [L for L in lines if L["yc"] < hlim]
    if len(top_lines) >= 2:
        header_bottom = max(L["y"] + L["h"] for L in top_lines[:3]) + 5
    elif len(top_lines) == 1:
        header_bottom = top_lines[0]["y"] + top_lines[0]["h"] + 5
    else:
        frag_tops = [f for f in frags if f["yc"] < h * 0.14 and f.get("rule")]
        # Only rule-like fragments count: Devanagari shirorekhas are long horizontal
        # strokes (fragments) with text right below (ink_below >= 0.5), and letting
        # them move header_bottom cut the mUlam verse in half (vol02 p0598: verse
        # 74 line 2's top bar pushed header_bottom from 87 to 245).
        if frag_tops:
            header_bottom = max(header_bottom, max(f["y"] + f["h"] for f in frag_tops) + 5)
    return header_bottom, top_lines, seps

def find_hlines(gray):
    h, w = gray.shape
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kw = max(80, int(w * 0.3))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, 1))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(horiz, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    segs = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw > w * 0.15 and 1 <= ch <= 8:
            segs.append({"x": x, "y": y, "w": cw, "h": ch, "yc": y + ch / 2})
    # merge collinear segs (same line fragmented by scan skew/text): dy<=6 and x-overlap/gap small
    segs.sort(key=lambda d: (d["yc"], d["x"]))
    merged = []
    for s in segs:
        placed = False
        for m in merged:
            if abs(s["yc"] - m["yc"]) <= 6 and s["x"] <= m["x"] + m["w"] + 20 and m["x"] <= s["x"] + s["w"] + 20:
                x0 = min(m["x"], s["x"])
                x1 = max(m["x"] + m["w"], s["x"] + s["w"])
                m.update({"x": x0, "w": x1 - x0, "y": min(m["y"], s["y"]),
                          "h": max(m["y"] + m["h"], s["y"] + s["h"]) - min(m["y"], s["y"])})
                m["yc"] = m["y"] + m["h"] / 2
                placed = True
                break
        if not placed:
            merged.append(dict(s))
    lines = [m for m in merged if m["w"] > w * 0.3]
    lines.sort(key=lambda d: d["yc"])
    # A real rule has whitespace just below it; a Devanagari shirorekha (headline) or a
    # Tamil horizontal ligature stroke has letter bodies right underneath. Rejecting
    # non-rules matters: on vol01 p0059 a 451px headline sat above the true 1005px rule
    # and was picked as separator (core truncated) and as header line (core top cut).
    for m in lines:
        _b = bw[m["y"] + m["h"] + 2: m["y"] + m["h"] + 12, m["x"]:m["x"] + m["w"]]
        m["ink_below"] = float((_b > 0).mean()) if _b.size else 1.0
        m["rule"] = m["ink_below"] < 0.15
    # raw fragments for faded-header fallback (e.g. vol02 p0057 header rules survive only
    # as ~200px segments invisible to the 0.3-width opening which erodes them away).
    # Needs its own opening with a smaller kernel, else short segs never become contours.
    kw2 = max(60, int(w * 0.12))
    kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (kw2, 1))
    horiz2 = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel2)
    contours2, _ = cv2.findContours(horiz2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frags = []
    for cnt in contours2:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw > w * 0.12 and 1 <= ch <= 8:
            frags.append({"x": x, "y": y, "w": cw, "h": ch, "yc": y + ch / 2})
    for m in frags:
        _b = bw[m["y"] + m["h"] + 2: m["y"] + m["h"] + 12, m["x"]:m["x"] + m["w"]]
        m["ink_below"] = float((_b > 0).mean()) if _b.size else 1.0
        m["rule"] = m["ink_below"] < 0.15
    return lines, frags, w, h

def _row_runs(mask, min_len=1):
    """Return [(start, length), ...] of True runs in a 1-D boolean mask."""
    runs, s = [], None
    n = len(mask)
    for i, v in enumerate(mask):
        if v and s is None:
            s = i
        if (not v or i == n - 1) and s is not None:
            if i - s >= min_len:
                runs.append((s, i - s))
            s = None
    return runs


def cropped_over_line(img, dark=100):
    """Report crop boundaries that cut through ink (a text line or a rule).

    Crops are supposed to begin/end in whitespace; ink touching the outermost
    row/column means the boundary sits on a line. Returns None when all four
    edges are clear, else a dict of offending edges with details, e.g.
      {"top": {"ink": 195, "runs": 27, "maxrun": 29, "kind": "text-strokes"}}
    kind is "rule" for a through-running horizontal line (few, long runs), else
    "text-strokes". Left/right edges use runs >= 6px so scan-edge shading and
    speckle do not count as text.

    Callers with the source page at hand should annotate each edge with
    "cut" (via _edge_continues): True means ink continues just outside the
    boundary (a line is really severed), False means a line starts/ends exactly
    at the boundary (nothing lost). cropped_over_line alone cannot tell.
    """
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    bw = g < dark
    h, w = bw.shape
    out = {}
    for edge in ("top", "bottom"):
        row = bw[0] if edge == "top" else bw[-1]
        runs = _row_runs(row, 2)
        ink = int(row.sum())
        if ink < max(6, 0.0015 * w):
            continue
        mr = max((rl for _, rl in runs), default=0)
        out[edge] = {"ink": ink, "runs": len(runs), "maxrun": int(mr),
                     "kind": "rule" if (mr >= 0.10 * w and len(runs) <= 6) else "text-strokes"}
    for edge in ("left", "right"):
        col = bw[:, 0] if edge == "left" else bw[:, -1]
        runs = _row_runs(col, 1)
        long_runs = [rl for _, rl in runs if rl >= 6]
        ink = sum(long_runs)
        if len(long_runs) >= 2 and ink >= max(12, 0.004 * h):
            mr = max(long_runs)
            out[edge] = {"ink": ink, "runs": len(long_runs), "maxrun": int(mr),
                         "kind": "rule" if mr >= 0.10 * h else "text-strokes"}
    return out or None


def _edge_continues(page_bw, box, edge, dark_band=2):
    """True when ink continues just outside the crop box (the boundary severs a
    line); False when the line merely starts/ends at the boundary."""
    h, w = page_bw.shape
    x0, x1 = max(0, box["x0"]), min(w, box["x1"])
    y0, y1 = max(0, box["y0"]), min(h, box["y1"])
    if edge == "top":
        band = page_bw[max(0, y0 - dark_band):y0, x0:x1]
    elif edge == "bottom":
        band = page_bw[y1:min(h, y1 + dark_band), x0:x1]
    elif edge == "left":
        band = page_bw[y0:y1, max(0, x0 - dark_band):x0]
    else:
        band = page_bw[y0:y1, x1:min(w, x1 + dark_band)]
    return bool(band.size and band.any())


def _is_rule_row(runs, w, rule_frac):
    """A through-running rule row: few runs, at least one long (the wavy header
    rules and separators); text rows and shirorekha rows carry many strokes."""
    if not runs:
        return False
    return max(rl for _, rl in runs) >= rule_frac * w and len(runs) <= 6


def _row_has_strokes(r, w, rule_frac):
    rr = _row_runs(r)
    if not rr or int(r.sum()) <= 0.01 * w:
        return False
    return len(rr) > 6 or max(rl for _, rl in rr) < rule_frac * w


def _snap_top(bw, y0, margin=3, max_move=60, rule_frac=0.10):
    """Move a crop's top boundary off ink: below a rule band, or above the true
    top of a cut text line. Returns the adjusted y0."""
    h, w = bw.shape
    if y0 <= 0 or not (bw[y0] > 0).any():
        return y0
    runs = _row_runs(bw[y0])
    if not runs:
        return y0
    if _is_rule_row(runs, w, rule_frac):
        # A rule (decorative wavy header rule or separator) at the boundary, unless
        # glyph bodies sit right below (then it is a Devanagari top bar of a cut line).
        if not any(_row_has_strokes(r, w, rule_frac) for r in bw[y0 + 3:y0 + 9]):
            b1 = y0
            while b1 + 1 < h and b1 + 1 - y0 <= max_move:
                rr = _row_runs(bw[b1 + 1])
                if _is_rule_row(rr, w, rule_frac) or int(bw[b1 + 1].sum()) < 0.03 * w:
                    b1 += 1
                else:
                    break
            y_rule = min(h - 1, b1 + margin)
            # The next text line can begin inside the rule's dip (vol02 p0300/p0079:
            # the wave descends into the text's top rows). Excluding the whole rule
            # would then cut the text, so cover the text instead (the dip fragment
            # stays in the crop).
            for y in range(y0, min(h, y0 + max_move)):
                rr = _row_runs(bw[y])
                if rr and len(rr) > 6 and int(bw[y].sum()) > 0.03 * w:
                    if y < y_rule:
                        return max(1, y - margin)
                    break
            return y_rule
    # Cut text: trace each crossing stroke's top; stop where a rule row starts.
    tops = []
    for x, rl in runs:
        if rl >= rule_frac * w:
            continue
        c = x + rl // 2
        y = y0
        while y - 1 >= 0 and y0 - y < max_move:
            if not bw[y - 1, max(0, c - 2):c + 3].any():
                break
            if _is_rule_row(_row_runs(bw[y - 1]), w, rule_frac):
                break
            y -= 1
        tops.append(y)
    if not tops:
        return y0
    return max(1, int(np.percentile(tops, 10)) - margin)


def _fix_boundary_top(bw, y0, floor=1, max_steps=14):
    """Iteratively move a top boundary off the ink it sits on. Non-text ink
    (rule bands, AA fringes, halos, wavy rule fragments) is stepped past
    downwards; when sitting on a cut text line the boundary is moved above the
    line's true top (never below floor), then re-checked (the snap can land on
    another band, e.g. vol02 p0039)."""
    h, w = bw.shape
    y = y0
    if y <= 0 or not (bw[y] > 0).any() or int(bw[y].sum()) < max(6, 0.0015 * w):
        return y0  # below the cropped_over_line flag level: leave as is
    seen = set()
    for _ in range(max_steps):
        if y in seen:
            break
        seen.add(y)
        if y <= 0 or not (bw[y] > 0).any():
            break
        rr = _row_runs(bw[y])
        mr = max((rl for _, rl in rr), default=0)
        if int(bw[y].sum()) >= 6 and (len(rr) == 1 or not _row_has_strokes(bw[y], w, 0.08)
                                      or (len(rr) <= 3 and mr >= 0.02 * w)
                                      or (len(rr) <= 8 and mr >= 0.10 * w)):
            y = min(h - 1, y + 3)
            continue
        y2 = max(floor, _snap_top(bw, y))
        if y2 >= y or y2 in seen:
            return y if y2 in seen and y2 < y else y2
        y = y2
    return y


def _snap_bottom(bw, y1, margin=3, max_move=45, rule_frac=0.10, cap=None, up_only=False):
    """Move a crop's bottom boundary off ink: above a rule band, or below the
    true bottom of a cut text line. Returns the adjusted y1."""
    h, w = bw.shape
    if y1 >= h or y1 <= 1 or not (bw[y1 - 1] > 0).any():
        return y1
    runs = _row_runs(bw[y1 - 1])
    if not runs:
        return y1
    if up_only:
        # Core bottom: clear any non-text ink (rule crest/halo fragments) ending
        # at the boundary; never extend (the separator rule sits right below).
        # Single-run rows are the tapering crest of a wavy/thick rule (vol01
        # p0043: crest rows 236-238 have one 9-93px run each); text rows carry
        # several strokes. Runs shorter than 3px are AA specks and ignored.
        t = y1
        while t - 1 >= 0 and y1 - t < max_move:
            rr = _row_runs(bw[t - 1], 3)
            if not rr or sum(rl for _, rl in rr) < 6:
                break
            mr = max(rl for _, rl in rr)
            if not (len(rr) == 1 or _is_rule_row(rr, w, 0.08)
                    or (len(rr) <= 3 and mr >= 0.02 * w)
                    or (len(rr) <= 8 and mr >= 0.10 * w)):
                break
            t -= 1
        if t < y1:
            return max(1, t - margin)
        return y1
    below_strokes = any(_row_has_strokes(r, w, rule_frac) for r in bw[y1:min(h, y1 + 7)])
    if _is_rule_row(runs, w, rule_frac) and not below_strokes:
        # Boundary sits on a rule: move above the whole rule band.
        t0 = y1 - 1
        while t0 - 1 >= 0 and (y1 - 1) - t0 < max_move:
            if _is_rule_row(_row_runs(bw[t0 - 1]), w, rule_frac):
                t0 -= 1
            else:
                break
        return max(1, t0 - margin)
    # Cut text (or a rule with bodies right below): extend down past the line's
    # true bottom (first blank row or the next rule row).
    b1 = y1 - 1
    while b1 + 1 < h and b1 + 1 - (y1 - 1) < max_move:
        r = bw[b1 + 1]
        if int(r.sum()) == 0 or _is_rule_row(_row_runs(r), w, rule_frac):
            break
        b1 += 1
    y_new = min(h - 1, b1 + 1 + margin)
    if cap is not None:
        y_new = min(y_new, cap)
    return max(y1, y_new)


def _footer_cut(gray, w, h, dark=100):
    """Commentary bottom: just below the LAST REAL text line, scanning up from
    the foot zone. Faint mirrored bleed-through, the page number and the CC
    digitization footer must not count (vol02 p0079: real text ends mid-page,
    below is ghost text plus centered '48' + CC line).

    A real text row carries >=6 runs and spans a wide x-extent (>=0.15w;
    rules, marks and centered ornaments have fewer/short runs). The ink
    threshold self-calibrates from the page's own text rows (median ink of
    candidate rows): fixed fractions of w fail on small-font pages (vol01
    p0243: list lines carry 40-80px ink, well under 0.10w, and the old cut
    sliced through a line mid-glyph). A candidate band separated from the
    body by a far gap (>0.08h - vol02 p0079: the wide CC footer line) is
    discarded. The line's bottom is found by following descender rows down
    while they stay inked."""
    bw = gray < dark
    y_lim = int(h * 0.94)
    lo = int(h * 0.25)
    gap_thr = 0.08 * h

    def _cand_row(row):
        rr = _row_runs(row)
        if len(rr) < 6:
            return False, 0
        x0 = min(s for s, _ in rr)
        x1 = max(s + rl for s, rl in rr)
        return (x1 - x0) >= 0.15 * w, sum(rl for _, rl in rr)

    inks = sorted(i for y in range(lo, y_lim)
                  for ok, i in (_cand_row(bw[y]),) if ok)
    m = inks[len(inks) // 2] if inks else 0
    thr = max(8, 0.03 * w, 0.5 * m)
    c = None
    for y in range(y_lim - 1, lo, -1):
        ok, ink = _cand_row(bw[y])
        if not ok or ink < thr:
            continue
        if c is None or c - y > gap_thr:
            c = y
        else:
            break
    if c is None:
        return y_lim
    y2 = c
    while y2 + 1 < min(h, y_lim + 60) and int(bw[y2 + 1].sum()) >= max(3, 0.0025 * w):
        y2 += 1
    return int(min(y2 + 4, h - 1))


def split_page(img_path, out_dir, stem, angle=0.0):
    raw = cv2.imread(str(img_path))
    img = raw
    # Colour plates (front-matter deity/guru photos) have high saturation and put a
    # strong horizontal edge across the page that masquerades as a separator, yielding
    # a bogus full-page core. They carry no OCR text: skip them entirely.
    if float(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1].mean()) > 30:
        return {"plate": True, "core_box": None, "comm_box": None, "separator": None,
                "all_lines": [], "header_lines": [], "skew_angle": angle,
                "w": img.shape[1], "h": img.shape[0]}, img
    # Ghost pages: backs of plates / adhyAya title pages whose only "content" is faint
    # mirrored bleed-through from the reverse side (vol01 p0009/p0085/p0095/p0115,
    # vol02 p0143...). They used to yield bogus full-page comm crops. Real text pages,
    # even low-ink ones (vol01 p0307, p0262), have 0.5th-percentile gray <= ~3;
    # ghosts are > ~110 (measured over the body rows 5-94%h).
    _g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _body = _g[int(_g.shape[0] * 0.05):int(_g.shape[0] * 0.94)]
    if float(np.percentile(_body, 0.5)) > 100:
        return {"ghost": True, "core_box": None, "comm_box": None, "separator": None,
                "all_lines": [], "header_lines": [], "skew_angle": angle,
                "w": img.shape[1], "h": img.shape[0]}, img
    if abs(angle) >= 0.05:
        img = deskew_image(img, angle)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lines, frags, w, h = find_hlines(gray)
    header_bottom, top_lines, seps = header_and_seps(lines, frags, w, h)
    if not seps:
        # Two-stage skew: estimate_skew tracks LONG rules; short centred mUlam-end
        # rules need the targeted search (morphological pass, then Hough for locally
        # wavy rules -- vol01 p0228's rule sheds ink over 20 rows). Re-run the analysis
        # at the refined angle. A wavy rule still never passes find_hlines, so when
        # sp2 stays empty build the separator directly from the refined rule geometry
        # (rotate its endpoints into the deskewed frame); revert if that fails too.
        ref = refine_rule_angle(cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY))
        if ref is not None:
            ra = float(ref["angle"])
            img2 = deskew_image(raw, ra) if abs(ra - angle) >= 0.05 else img
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            lines2, frags2, w2, h2 = find_hlines(gray2)
            hb2, tl2, sp2 = header_and_seps(lines2, frags2, w2, h2)
            if not sp2:
                rad = float(np.radians(ra))
                M = cv2.getRotationMatrix2D((w2 / 2, h2 / 2), ra, 1.0)
                pts = []
                for xx in (ref["x0"], ref["x1"]):
                    pts.append([float(xx), (ref["c"] + xx * np.sin(rad)) / np.cos(rad)])
                tip = cv2.transform(np.array([pts], dtype=np.float64), M)[0]
                xa, xb = sorted((tip[0][0], tip[1][0]))
                yc = (tip[0][1] + tip[1][1]) / 2
                if 0.10 * h2 < yc < 0.92 * h2 and xb - xa > 0.28 * w2:
                    sp2 = [{"x": int(xa), "y": int(yc) - 2, "w": int(xb - xa), "h": 4,
                            "yc": float(yc), "ink_below": float(ref["below"]),
                            "rule": True}]
            if sp2:
                angle, img, gray, w, h = ra, img2, gray2, w2, h2
                lines, frags, header_bottom, top_lines, seps = lines2, frags2, hb2, tl2, sp2
    footer_top = int(h * 0.94)
    # (seps precomputed above so header lines stay strictly above the separator)
    blocks = {"header_lines": top_lines, "all_lines": lines, "w": w, "h": h, "skew_angle": angle}
    core_box = None
    comm_box = None
    if seps:
        sep = seps[0]
        # Pad around the rule itself (scans show 2-4px halo beyond the detected edge;
        # without padding the rule remnant leaks into crops, e.g. vol02 p0057/p0082).
        # Measure the rule's true vertical extent across the FULL text width: the
        # detected fragment is often partial (faded ends, slight skew), so scan rows
        # around it for rule-like rows (total dark > 60% width) and clear those too.
        _, _bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # True rule extent via connected component, DOWNWARD ONLY: the detected fragment
        # is often partial (faded ends, slight slope shed tail pixels, e.g. vol02 p0057
        # tail runs to y=623 while fragment says 609-611). The rule is one connected
        # dark blob, so flood from its centre (dilated 3x3 to bridge 1-2px fade gaps;
        # book line spacing is 15px+, so no leak into text below). Never extend UPWARD:
        # the fragment top is trustworthy, while upward growth demonstrably eats into
        # text descenders touching the rule (vol02 p0057 component reached y=603).
        # Cap downward growth to avoid runaways.
        rtop, rbot = sep["y"], sep["y"] + sep["h"]
        grew = False
        try:
            _dil = cv2.dilate(_bw, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
            _n, _lab, _stats, _cent = cv2.connectedComponentsWithStats(_dil, 8)
            _cy = min(max(sep["y"] + sep["h"] // 2, 0), h - 1)
            # Try several seed columns: a broken/faded rule can have gaps at the
            # centre (vol01 p0043), which used to silently disable the extent pass.
            _id = 0
            for _fx in (0.5, 0.35, 0.65, 0.2, 0.8):
                _cx = min(max(sep["x"] + int(sep["w"] * _fx), 0), w - 1)
                _id = int(_lab[_cy, _cx])
                if _id > 0:
                    break
            if _id > 0:
                _x, _yy, _ww, _hh, _area = _stats[_id]
                _bot = int(_yy + _hh) - 2  # undo dilation padding
                # Downward growth must stay rule-like: every row between the fragment
                # bottom and the component bottom needs a long run (the arc's dipping
                # ends do; the next text line's matras/strokes do not, vol02 p0300
                # where the component bridge reached the text tops and the comm crop
                # cut that line). Cap 28 (not 20) for the arc ends.
                if _ww > w * 0.3 and _bot - rbot <= 28 and _bot > rbot and \
                   all(max((rl for _, rl in _row_runs(_bw[_r, max(_x, 0):_x + _ww] > 0)),
                           default=0) >= 0.08 * w for _r in range(rbot + 1, _bot)):
                    rbot, grew = int(_bot), True
                # Lift rtop when the rule's true top is above the fragment: a locally
                # tilted rule's single-row run sits below its top (vol01 p0330: fragment
                # at 276 but the rule rises to 268, leaking a sliver into the core crop).
                # The topmost row is the tapering tip and may be tiny (p0268: run 7);
                # rows below it must be full rule rows (run >= 0.10w). Descender rows
                # touching the rule are short strokes and fail this (p0057 lesson); the
                # two rows above the tip must be blank so unconnected text cannot be cut.
                if _ww > w * 0.3 and _yy + 1 < rtop and rtop - (_yy + 1) <= 12 \
                   and not (_bw[_yy - 1] > 0).any() and not (_bw[_yy] > 0).any():
                    _ok = True
                    for _r in range(int(_yy) + 1, rtop):
                        _seg = _bw[_r, max(_x, 0):_x + _ww] > 0
                        _m = _run = 0
                        for _v in _seg:
                            _run = _run + 1 if _v else 0
                            if _run > _m:
                                _m = _run
                        if _m < (6 if _r == int(_yy) + 1 else 0.10 * w):
                            _ok = False
                            break
                    if _ok:
                        rtop = int(_yy) + 1
        except Exception:
            pass
        # Fallback row scan for halo rows the component missed (defensive; no-op normally)
        for yy in range(rbot, min(h, sep["y"] + sep["h"] + 15)):
            if int((_bw[yy, :] > 0).sum()) > w * 0.6:
                rbot, grew = max(rbot, yy + 1), True
        # When the extent grew (arc/tail), the rule can end just above the next text
        # line; keep the +4 margin only if it does not shave the line's tops
        # (vol02 p0323: tail ends 406, text tops start 408).
        if grew:
            for yy in range(rbot + 1, min(h, rbot + 40)):
                if float((_bw[yy, sep["x"]:sep["x"] + sep["w"]] > 0).mean()) > 0.10 \
                   and float((_bw[yy] > 0).mean()) > 0.10:
                    if rbot + 4 > yy - 1:
                        rbot = yy - 5
                    break
        # core = header_bottom .. rule top (if height > 30px, else no core)
        if rtop - 2 - header_bottom > 40:
            core_box = {"x0": 0, "y0": header_bottom, "x1": w, "y1": rtop - 2, "label": "core"}
        comm_box = {"x0": 0, "y0": rbot + 4, "x1": w, "y1": footer_top, "label": "commentary"}
        blocks["separator"] = sep
        blocks["rule_extent"] = {"y0": rtop, "y1": rbot}
    else:
        comm_box = {"x0": 0, "y0": header_bottom, "x1": w, "y1": footer_top, "label": "commentary"}
        blocks["separator"] = None
    # Crops must begin/end on whitespace: snap boundaries off ink (a text line or
    # the separator/decorative rule). The invariant is checked by cropped_over_line.
    _, _sbw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _sbw = _sbw > 0  # pixel-count mask: helper .sum() thresholds are in pixels
    _foot = _footer_cut(gray, w, h)
    if core_box:
        core_box["y0"] = _fix_boundary_top(_sbw, core_box["y0"], floor=1)
        core_box["y1"] = _snap_bottom(_sbw, core_box["y1"], cap=sep["y"] - 2, up_only=True)
        if core_box["y1"] - core_box["y0"] <= 30:
            core_box = None
    if comm_box:
        comm_box["y0"] = _fix_boundary_top(_sbw, comm_box["y0"], floor=rbot + 2 if seps else 1)
        comm_box["y1"] = _snap_bottom(_sbw, min(comm_box["y1"], _foot), cap=_foot)
        if comm_box["y1"] - comm_box["y0"] <= 30:
            comm_box = None
    blocks["core_box"] = core_box
    blocks["comm_box"] = comm_box
    # save crops (skip when out_dir None: caller writes canonical crops itself)
    if out_dir is None:
        return blocks, img
    out_dir = pathlib.Path(out_dir)
    if core_box:
        crop = img[core_box["y0"]:core_box["y1"], core_box["x0"]:core_box["x1"]]
        cv2.imwrite(str(out_dir / f"{stem}_core.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if comm_box:
        crop = img[comm_box["y0"]:comm_box["y1"], comm_box["x0"]:comm_box["x1"]]
        cv2.imwrite(str(out_dir / f"{stem}_comm.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return blocks, img

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", choices=["01", "02"], default="")
    ap.add_argument("--root", default="",
                    help="maNipravALa-ocr repo holding data/RTS_sb_0{1,2} "
                         "(default: $MANIPRAVALA_OCR_ROOT or sibling repo)")
    ap.add_argument("--subset", type=str, default="", help="e.g. 0:70")
    ap.add_argument("--images", default="", help="legacy input dir (root-relative or abs)")
    ap.add_argument("--glob", default="*.jpg")
    ap.add_argument("--out", default="", help="legacy output dir")
    ap.add_argument("--recompute-skew", action="store_true", help="ignore cached skew.json")
    ap.add_argument("--no-deskew", action="store_true", help="disable deskew (debug)")
    ap.add_argument("--check-crops", action="store_true",
                    help="only run cropped_over_line on the existing crop images")
    args = ap.parse_args()
    root = pathlib.Path(args.root).expanduser() if args.root else _default_root()
    if not (root / "data" / "RTS_sb_01" / "pages_raw").is_dir():
        ap.error(f"no data/RTS_sb_01/pages_raw under {root} (pass --root)")

    if args.check_crops:
        total = 0
        for vol in ("01", "02"):
            meta_p = root / "data" / f"RTS_sb_{vol}" / "metadata" / "blocks.json"
            entries = {}
            if meta_p.exists():
                for b in json.loads(meta_p.read_text(encoding="utf-8")).get("blocks", []):
                    if b.get("box"):
                        entries[f"{b['block']}_{b['page']}"] = b
            page_bw = {}
            bad = []
            for label in ("core", "comm"):
                for p in sorted((root / "data" / f"RTS_sb_{vol}" / "images" / label).glob("p*.jpg")):
                    img = cv2.imread(str(p))
                    if img is None:
                        continue
                    err = cropped_over_line(img)
                    if err:
                        e = entries.get(f"{label}_{p.stem}")
                        if e:
                            if p.stem not in page_bw:
                                pimg = cv2.imread(str(root / "data" / f"RTS_sb_{vol}" / "pages_raw" / f"{p.stem}.jpg"))
                                a = float(e.get("skew_angle") or 0.0)
                                if pimg is not None and abs(a) >= 0.05:
                                    pimg = deskew_image(pimg, a)
                                page_bw[p.stem] = (cv2.cvtColor(pimg, cv2.COLOR_BGR2GRAY) < 100) if pimg is not None else None
                            if page_bw[p.stem] is not None:
                                for edge in err:
                                    err[edge]["cut"] = _edge_continues(page_bw[p.stem], e["box"], edge)
                        bad.append((label, p.stem, err))
            print(f"vol{vol}: {len(bad)} crops with ink on an edge")
            for label, stem, err in bad:
                print(f"   {label}/{stem}: {err}")
            total += len(bad)
        print(f"total: {total} crops cropped over a line")
        return

    if args.vol:
        # canonical mode: pages_raw -> images/{core,comm} + metadata/blocks.json (GT later)
        vol = args.vol
        pages_dir = root / "data" / f"RTS_sb_{vol}" / "pages_raw"
        core_dir = root / "data" / f"RTS_sb_{vol}" / "images" / "core"
        comm_dir = root / "data" / f"RTS_sb_{vol}" / "images" / "comm"
        core_dir.mkdir(parents=True, exist_ok=True)
        comm_dir.mkdir(parents=True, exist_ok=True)
        meta_path = root / "data" / f"RTS_sb_{vol}" / "metadata" / "blocks.json"
        existing = {}
        if meta_path.exists():
            try:
                existing = {f"{b['page']}_{b['block']}": b for b in json.loads(meta_path.read_text(encoding="utf-8")).get("blocks", [])}
            except Exception:
                existing = {}
        files = sorted(pages_dir.glob("p*.jpg"))
        if args.subset:
            a, b = args.subset.split(":")
            files = [f for f in files if int(f.stem[1:]) >= int(a) and int(f.stem[1:]) < int(b)]
        crop_errors = []
        # Per-page deskew angle cache (pages_raw is immutable, so angle is stable).
        skew_path = root / "data" / f"RTS_sb_{vol}" / "metadata" / "skew.json"
        skew = {}
        if skew_path.exists() and not args.recompute_skew:
            try:
                skew = json.loads(skew_path.read_text(encoding="utf-8"))
            except Exception:
                skew = {}
        for f in files:
            stem = f.stem  # pXXXX
            if args.no_deskew:
                angle = 0.0
            elif stem in skew:
                angle = float(skew[stem])
            else:
                _g = cv2.cvtColor(cv2.imread(str(f)), cv2.COLOR_BGR2GRAY)
                angle = estimate_skew(_g)[0]
                skew[stem] = angle
            blocks, dimg = split_page(str(f), None, stem, angle=angle)
            eff = float(blocks.get("skew_angle", angle))
            if not args.no_deskew and abs(eff - angle) >= 0.05:
                skew[stem] = eff
            if blocks.get("plate") or blocks.get("ghost"):
                kind = "plate" if blocks.get("plate") else "ghost"
                for label in ("core", "comm"):
                    prev = existing.pop(f"{stem}_{label}", None)
                    if prev and prev.get("image"):
                        try:
                            (root / prev["image"]).unlink(missing_ok=True)
                        except Exception:
                            pass
                print(f"{vol}:{stem}: {kind} (no text; skipped)")
                continue
            # write canonical crops; every regenerated crop is checked so it does
            # not begin/end ON a line (the split boundaries must sit in whitespace)
            cb, mb = blocks["core_box"], blocks["comm_box"]
            img = dimg
            pg_bw = None
            for label, box, outdir in (("core", cb, core_dir), ("comm", mb, comm_dir)):
                if not box:
                    continue
                crop = img[box["y0"]:box["y1"], box["x0"]:box["x1"]]
                cv2.imwrite(str(outdir / f"{stem}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
                cut = cropped_over_line(crop)
                if cut:
                    if pg_bw is None:
                        pg_bw = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) < 100
                    for edge in cut:
                        cut[edge]["cut"] = _edge_continues(pg_bw, box, edge)
                    crop_errors.append({"page": stem, "block": label, "edges": cut})
                    print(f"CROP-CUT {vol}:{stem}:{label} {cut}")
            # Drop stale core entries (re-detect no longer finds a core: remove crop + record,
            # unless it is the curated absent-by-design marker which has no image/box).
            if not cb:
                prev = existing.get(f"{stem}_core")
                if prev and prev.get("image"):
                    try:
                        (root / prev["image"]).unlink(missing_ok=True)
                    except Exception:
                        pass
                    existing.pop(f"{stem}_core", None)
                    print(f"{vol}:{stem}: core dropped (stale crop removed)")
            for label, box in (("core", cb), ("comm", mb)):
                if not box:
                    continue
                # Preserve curated GT/status across re-runs (gold lives in splits + gt files;
                # re-detection must never silently wipe it back to auto-images-only).
                prev = existing.get(f"{stem}_{label}", {})
                entry = {"page": stem, "block": label,
                    "image": f"data/RTS_sb_{vol}/images/{label}/{stem}.jpg", "gt": prev.get("gt"),
                    "box": box, "separator": blocks.get("separator"),
                    "skew_angle": blocks.get("skew_angle"),
                    "has_core": cb is not None, "status": prev.get("status", "auto-images-only"),
                    "note": prev.get("note", "images first, GT later")}
                if "unit" in prev:
                    entry["unit"] = prev["unit"]
                existing[f"{stem}_{label}"] = entry
            print(f"{vol}:{stem}: has_core={cb is not None} n_lines={len(blocks['all_lines'])}")
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps({"blocks": [existing[k] for k in sorted(existing)], "status": "images-only-GT-later"}, indent=1), encoding="utf-8")
        if skew:
            skew_path.write_text(json.dumps(skew, indent=1, sort_keys=True), encoding="utf-8")
        err_path = meta_path.parent / "crop_errors.json"
        err_path.write_text(json.dumps(crop_errors, indent=1), encoding="utf-8")
        print(f"Wrote {meta_path} ({len(existing)} blocks)")
        print(f"cropped_over_line: {len(crop_errors)} crops with ink on an edge "
              f"(details in {err_path})")
        return

    # legacy mode
    img_dir = root / args.images if args.images and not os.path.isabs(args.images) else pathlib.Path(args.images)
    out_dir = root / args.out if not os.path.isabs(args.out) else pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    crops_dir = out_dir / "crops"
    crops_dir.mkdir(exist_ok=True)
    files = sorted(glob.glob(str(img_dir / args.glob)))
    index = []
    for f in files:
        stem = pathlib.Path(f).stem
        angle = 0.0 if args.no_deskew else estimate_skew(cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2GRAY))[0]
        blocks, _img = split_page(f, crops_dir, stem, angle=angle)
        (out_dir / f"{stem}_blocks.json").write_text(json.dumps(blocks, indent=2), encoding="utf-8")
        index.append({"image": os.path.basename(f), "has_core": blocks["core_box"] is not None,
                      "core_box": blocks["core_box"], "comm_box": blocks["comm_box"]})
        print(f"{stem}: has_core={blocks['core_box'] is not None} n_lines={len(blocks['all_lines'])}")
    (out_dir / "blocks_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"Wrote {len(index)} block JSONs to {out_dir}")

if __name__ == "__main__":
    main()
