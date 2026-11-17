import pytest

cv2 = pytest.importorskip("cv2")
scipy = pytest.importorskip("scipy")
import numpy as np

from doc_curation.pdf.ocr.vedic_accent_cv import (
    align_tokens_to_units,
    build_clean_line_canvases,
    clean_drive_markdown,
    detect_page_accents,
    extract_visual_units,
    process_page_with_text,
    render_accented_lines,
    tokenize_telugu_aksaras,
)


def _draw_synthetic_telugu_page():
  """Construct a 300-DPI-scaled synthetic page with body lines, marks, and noise."""
  h, w = 1400, 1800
  gray = np.full((h, w), 255, dtype=np.uint8)

  # Running header (wide gap to body line 1 -> must be filtered)
  cv2.rectangle(gray, (700, 220), (1100, 260), 0, -1)

  # Left margin vertical border streak -> must be ignored
  cv2.rectangle(gray, (40, 200), (45, 1200), 0, -1)
  cv2.rectangle(gray, (1715, 300), (1718, 1200), 0, -1)

  # 3 body lines separated by 140px
  ys = [500, 640, 780]
  # Line 1: 4 aksaras + danda + 2 aksaras
  # Slot centers around x = 420, 500, 580, 660, (715 danda), 780, 860
  for ly in ys:
    for gx in [400, 480, 560, 640, 760, 840]:
      cv2.rectangle(gray, (gx, ly - 15), (gx + 42, ly + 20), 0, 3)  # glyph box with midline crossbar
      cv2.line(gray, (gx, ly + 2), (gx + 42, ly + 2), 0, 4)
    # Single danda '|' at x=715
    cv2.rectangle(gray, (715, ly - 18), (720, ly + 22), 0, -1)

  # Line 1 accents:
  # - slot 0 (x=400..442): anudatta '_'
  cv2.rectangle(gray, (406, 540), (436, 546), 0, -1)
  # - slot 1 (x=480..522): broken anudatta '_' (two 14px halves, 3px gap)
  cv2.rectangle(gray, (485, 540), (499, 546), 0, -1)
  cv2.rectangle(gray, (502, 540), (516, 546), 0, -1)
  # - slot 2 (x=560..602): broken vertical svarita '|' (13px + 13px, 3px vertical gap)
  cv2.rectangle(gray, (578, 438), (583, 451), 0, -1)
  cv2.rectangle(gray, (578, 454), (583, 467), 0, -1)
  # - slot 5 (x=840..882): fused bimodal dirgha-svarita '||' (touching at top)
  cv2.rectangle(gray, (852, 436), (857, 472), 0, -1)
  cv2.rectangle(gray, (861, 436), (866, 472), 0, -1)
  cv2.rectangle(gray, (852, 436), (866, 441), 0, -1)  # top ink bridge -> top_cov=1.0

  # Line 2 accents:
  # - slot 0 (x=400..442): paired separate dirgha-svarita '||'
  cv2.rectangle(gray, (412, 578), (417, 614), 0, -1)
  cv2.rectangle(gray, (421, 578), (426, 614), 0, -1)
  # - slot 3 (x=640..682): non-uniform curved 'ta'-ottu bulb below glyph -> must NOT become '_'
  cv2.rectangle(gray, (640, 675), (685, 680), 0, -1)
  cv2.circle(gray, (682, 682), 10, 0, -1)

  # Line 3: footnote divider rule below line 3 -> must NOT become '_'
  cv2.rectangle(gray, (350, 860), (1400, 865), 0, -1)

  return gray


def test_clean_drive_markdown_and_tokenize():
  raw = "1\n> >\n**మా** న్తరిక్షే\\! యో\\*ఽహమస్మి \\| స్వాహా\\|\\| ౧౮౬\\|\\|"
  cleaned = clean_drive_markdown(raw)
  assert "1" not in cleaned.splitlines()
  assert ">" not in cleaned
  assert "**" not in cleaned
  toks = tokenize_telugu_aksaras("యోఽహమస్మి । స్వాహా॥ ౧౮౬॥")
  texts = [t["text"] for t in toks]
  assert texts == ["యో", "ఽ", "హ", "మ", "స్మి", "।", "స్వా", "హా", "॥", "౧", "౮", "౬", "॥"]


def test_cv_detects_broken_and_bimodal_accents_and_filters_noise():
  gray = _draw_synthetic_telugu_page()
  res = detect_page_accents(gray, return_arrays=True)
  assert len(res["peaks"]) == 3
  # Line 1: 2 unders (one whole, one stitched), 1 single bar (stitched), 1 fused bimodal dbar
  l1, l2, l3 = res["lines"]
  assert len(l1["unders"]) == 2
  assert len(l1["bars"]) == 1
  assert len(l1["dbars"]) == 1
  # Line 2: 1 paired dbar, 0 unders (curved ottu bulb rejected)
  assert len(l2["dbars"]) == 1
  assert len(l2["unders"]) == 0
  # Line 3: footnote rule excluded
  assert len(l3["unders"]) == 0
  assert len(res["rule_ys"]) >= 1

  canvases = build_clean_line_canvases(res, number_lines=True)
  assert len(canvases) == 1
  assert canvases[0].shape[0] > 500


def test_end_to_end_alignment_and_devanagari_replacement():
  gray = _draw_synthetic_telugu_page()
  ocr = (
      "సత్యాత్మన । దేవా\n"
      "యోఽహమ । స్మితా\n"
      "పురుషాయ । నమ"
  )
  out_norm = process_page_with_text(gray, ocr, replace_dirgha_svarita=True)
  assert len(out_norm["lines"]) == 3
  assert out_norm["skipped_tokens_count"] == 0
  # Line 1: slots 0('_'), 1('_'), 2('|'), 3(none), (danda), 4(none), 5('||'->'\u0951')
  l1_deva = out_norm["lines"][0]["deva"]
  assert "स॒त्या॒त्म॑न ।" in l1_deva
  assert l1_deva.endswith("वा॑")
  # Line 2: '||' on slot 0 ('यो') -> '\u0951' BEFORE 'ऽ' avagraha!
  l2_deva = out_norm["lines"][1]["deva"]
  assert "यो॑ऽहम । स्मिता" == l2_deva
  assert "᳚" not in l1_deva and "᳚" not in l2_deva

  # Verify preserving dirgha-svarita when requested
  out_raw = process_page_with_text(gray, ocr, replace_dirgha_svarita=False)
  assert "᳚" in out_raw["lines"][0]["deva"]
  assert "᳚" in out_raw["lines"][1]["deva"]


def test_suspect_text_flagging():
  toks = tokenize_telugu_aksaras("ఫుణ్యా మస్త్రసన్ద్రుహణా")
  _, flat_units = extract_visual_units(detect_page_accents(_draw_synthetic_telugu_page(), return_arrays=True))
  # Simple check that suspect patterns trigger via render_accented_lines
  from doc_curation.pdf.ocr.vedic_accent_cv import SUSPECT_TEXT_RE

  assert SUSPECT_TEXT_RE.search("ఫుణ్యా")
  assert SUSPECT_TEXT_RE.search("మస్త్రసన్ద్రుహణా")
  assert SUSPECT_TEXT_RE.search("సజ్క్రీ")
  assert SUSPECT_TEXT_RE.search("ధ౯రణీ")
  assert not SUSPECT_TEXT_RE.search("పుణ్యాయ సఙ్క్రీడాత్మనే")
