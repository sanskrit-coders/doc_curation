import regex

from doc_curation.md.content_processor.commentary.helper import (
  wrap_commentaries_in_details,
  wrap_vedic_details,
)
from doc_curation.md.content_processor.details.common import (
  get_js_include_spans,
  get_top_level_detail_spans,
)


def _assert_balanced_and_idempotent(fn, src, out):
  assert out.count("<details") == out.count("</details>"), "Unbalanced <details> tags"
  assert len(regex.findall(r"<div\b", out, flags=regex.IGNORECASE)) == len(
    regex.findall(r"</div>", out, flags=regex.IGNORECASE)
  ), "Unbalanced <div> tags"
  assert fn(out) == out, "Transform must be strictly idempotent"


def test_get_js_include_spans_handles_nested_divs():
  text = (
    '<details><summary>A</summary>\n\nx\n</details>\n\n'
    '<div class="js_include" url="/outer.md">\n'
    '<details open><summary>outer</summary>\n'
    '<div class="js_include" url="/inner.md">\n'
    '<details><summary>inner</summary>\ny\n</details>\n'
    '</div>\n'
    '</details>\n'
    '</div>\n\n'
    '<details><summary>B</summary>\n\nz\n</details>\n'
  )
  inc_spans = get_js_include_spans(text)
  assert len(inc_spans) == 1
  assert text[inc_spans[0][0]:inc_spans[0][1]].startswith('<div class="js_include" url="/outer.md">')
  assert text[inc_spans[0][0]:inc_spans[0][1]].endswith("</div>")

  det_spans = get_top_level_detail_spans(text, skip_js_includes=True)
  assert len(det_spans) == 2
  assert [text[s:e].splitlines()[0] for s, e in det_spans] == [
    "<details><summary>A</summary>",
    "<details><summary>B</summary>",
  ]


def test_wrap_commentaries_in_details_skips_js_include_blocks():
  src = (
    "## ०१ समिधाग्निम्\n"
    "<details><summary>उवटः - विनियोगः</summary>\n\nआश्वत्थीः।\n</details>\n\n"
    '<div class="js_include" title="विश्वास-प्रस्तुतिः" url="/vp/01.md">\n'
    "<details open><summary><h3>विश्वास-प्रस्तुतिः ...{Loading}...</h3></summary>\n"
    "समिधाग्निम्\n"
    "</details>\n"
    "</div>\n"
    '<div class="js_include collapsed" title="सर्वाष् टीकाः" url="/tik/01.md">\n'
    "<details><summary><h3>सर्वाष् टीकाः ...{Loading}...</h3></summary>\n"
    "<details><summary>मूलम्</summary>\n\nसमिधाग्निम्\n</details>\n"
    "</details>\n"
    "</div>\n"
  )
  # Default single-wrapper call still skips js_include untouched
  out_single = wrap_commentaries_in_details(src)
  assert '<div class="js_include" title="विश्वास-प्रस्तुतिः"' in out_single
  assert '<details><summary><h3>सर्वाष् टीकाः ...{Loading}...</h3></summary>\n<details><summary>मूलम्</summary>' in out_single
  _assert_balanced_and_idempotent(wrap_commentaries_in_details, src, out_single)

  # Vedic two-tier wrap puts preceding viniyoga into सर्वा अवतारिकाः and preserves both js_includes verbatim
  out_vedic = wrap_vedic_details(src)
  assert "<details><summary>सर्वा अवतारिकाः</summary>\n\n<details><summary>उवटः - विनियोगः</summary>" in out_vedic
  assert out_vedic.count("<summary>सर्वाष् टीकाः</summary>") == 0
  assert src[src.index('<div class="js_include"'):] in out_vedic
  _assert_balanced_and_idempotent(wrap_vedic_details, src, out_vedic)


def test_wrap_vedic_details_splits_contiguous_tika_and_viniyoga_between_vps():
  src = (
    "+++\ntitle = 'test'\n+++\n\n"
    "<details><summary>भास्करोक्त-विनियोगः</summary>\n\nविनियोग १।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nमन्त्र १।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nमन्त्र १।\n</details>\n\n"
    "<details><summary>पद-पाठः (यान्त्रिकः)</summary>\n\nमन्त्र । १ ।\n</details>\n\n"
    "<details><summary>भट्टभास्कर-टीका</summary>\n\nटीका १।\n</details>\n\n"
    "<details><summary>भास्करोक्त-विनियोगः</summary>\n\nविनियोग २।\n</details>\n\n"
    "<details><summary>सायणोक्त-विनियोगः</summary>\n\nसायण-विनियोग २।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः - ऋक्</summary>\n\nमन्त्र २।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nमन्त्र २।\n</details>\n\n"
    "<details><summary>सायण-टीका</summary>\n\nटीका २।\n</details>\n\n"
    "<details><summary>विनियोगसङ्ग्रहः</summary>\n\nअत्र विनियोगसंग्रहः।\n</details>\n"
  )
  out = wrap_vedic_details(src)
  _assert_balanced_and_idempotent(wrap_vedic_details, src, out)

  assert out.count("<summary>सर्वा अवतारिकाः</summary>") == 2
  assert out.count("<summary>सर्वाष् टीकाः</summary>") == 2

  # First Mantra's टीका stays in सर्वाष् टीकाः, second Mantra's विनियोगः in सर्वा अवतारिकाः
  t1_pos = out.index("<summary>सर्वाष् टीकाः</summary>")
  av2_pos = out.index("<summary>सर्वा अवतारिकाः</summary>", t1_pos)
  vp2_pos = out.index("<summary>विश्वास-प्रस्तुतिः - ऋक्</summary>")
  assert t1_pos < out.index("टीका १।") < av2_pos < out.index("विनियोग २।") < out.index("सायण-विनियोग २।") < vp2_pos

  # विनियोगसङ्ग्रहः sits outside the last सर्वाष् टीकाः
  last_tika_close = out.rindex("</details>", 0, out.index("<summary>विनियोगसङ्ग्रहः</summary>"))
  assert out.index("टीका २।") < last_tika_close < out.index("<details><summary>विनियोगसङ्ग्रहः</summary>")


def test_wrap_vedic_details_mula_samyukta_context_sensitivity():
  src = (
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nमन्त्र १।\n</details>\n\n"
    "<details><summary>Keith</summary>\n\nMantra 1.\n</details>\n\n"
    "<details><summary>मूलम् (संयुक्तम्)</summary>\n\nसंयुक्त १।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nमन्त्र १।\n</details>\n\n"
    "<details><summary>भट्टभास्कर-टीका</summary>\n\nटीका १।\n</details>\n\n"
    "<details><summary>मूलम् (संयुक्तम्)</summary>\n\nसंयुक्त २।\n</details>\n\n"
    "<details><summary>भास्करोक्त-विनियोगः</summary>\n\nविनियोग २।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nमन्त्र २।\n</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nमन्त्र २।\n</details>\n\n"
    "<details><summary>मूलम् (संयुक्तम्)</summary>\n\nसंयुक्त ३।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nमन्त्र ३।\n</details>\n"
  )
  out = wrap_vedic_details(src)
  _assert_balanced_and_idempotent(wrap_vedic_details, src, out)

  # संयुक्त १ (between Keith and मूलम्) stays inside first सर्वाष् टीकाः
  # संयुक्त २ (before भास्करोक्त-विनियोगः + VP2) joins सर्वा अवतारिकाः of VP2
  # संयुक्त ३ (immediately before VP3 after मूलम्) goes into सर्वा अवतारिकाः of VP3
  assert out.count("<summary>सर्वाष् टीकाः</summary>") == 2
  assert out.count("<summary>सर्वा अवतारिकाः</summary>") == 2
  av1 = out.index("<summary>सर्वा अवतारिकाः</summary>")
  av2 = out.index("<summary>सर्वा अवतारिकाः</summary>", av1 + 1)
  assert out.index("संयुक्त १।") < out.index("टीका १।") < av1 < out.index("संयुक्त २।") < out.index("विनियोग २।")
  assert out.index("मन्त्र २।") < av2 < out.index("संयुक्त ३।") < out.index("मन्त्र ३।")


def test_wrap_vedic_details_file_top_bhumika_vs_post_include_tika_and_open_tippani():
  # File-top bhūmikā (TB 1.1.1 pattern) -> all in सर्वा अवतारिकाः
  bhumika_src = (
    "---\ntitle: test\n---\n"
    "<details><summary>विस्तारः (द्रष्टुं नोद्यम्)</summary>\n\nविस्तार।\n</details>\n\n"
    "<details><summary>भट्टभास्कर-टीका</summary>\n\nभट्टभास्करभाष्यभूमिका।\n</details>\n\n"
    "<details><summary>भास्करोक्त-विनियोगः</summary>\n\nअथ विनियोगः।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nब्रह्म सन्धत्तम्।\n</details>\n"
  )
  out_bh = wrap_vedic_details(bhumika_src)
  _assert_balanced_and_idempotent(wrap_vedic_details, bhumika_src, out_bh)
  assert out_bh.count("<summary>सर्वा अवतारिकाः</summary>") == 1
  assert out_bh.count("<summary>सर्वाष् टीकाः</summary>") == 0

  # Mid-file after js_include(सर्वाष् टीकाः): local सायण-टीका must stay सर्वाष् टीकाः, NOT join next अवतारिका
  mid_src = (
    '<div class="js_include" title="सर्वाष् टीकाः" url="/tik/1.md">\n'
    "<details><summary><h3>सर्वाष् टीकाः ...{Loading}...</h3></summary>\n</details>\n"
    "</div>\n\n"
    "<details><summary>सायण-टीका</summary>\n\nमन्त्र १ सायण।\n</details>\n\n"
    "<details><summary>भास्करोक्त-विनियोगः</summary>\n\nमन्त्र २ विनियोग।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nमन्त्र २।\n</details>\n"
  )
  out_mid = wrap_vedic_details(mid_src)
  _assert_balanced_and_idempotent(wrap_vedic_details, mid_src, out_mid)
  assert out_mid.count("<summary>सर्वाष् टीकाः</summary>") == 1
  assert out_mid.count("<summary>सर्वा अवतारिकाः</summary>") == 1
  assert out_mid.index("मन्त्र १ सायण।") < out_mid.index("<summary>सर्वा अवतारिकाः</summary>") < out_mid.index("मन्त्र २ विनियोग।")

  # Open विश्वास-टिप्पनी stays unwrapped while open मूलम् IS wrapped
  open_src = (
    "<details open><summary>विश्वास-टिप्पनी</summary>\n\nसम्पादक-टिप्पनी।\n</details>\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nमन्त्र।\n</details>\n\n"
    "<details open><summary>मूलम्</summary>\n\nमन्त्र मूलम्।\n</details>\n"
  )
  out_open = wrap_vedic_details(open_src)
  _assert_balanced_and_idempotent(wrap_vedic_details, open_src, out_open)
  assert out_open.startswith("<details open><summary>विश्वास-टिप्पनी</summary>")
  assert "<details><summary>सर्वाष् टीकाः</summary>\n\n<details open><summary>मूलम्</summary>" in out_open


def test_wrap_vedic_details_js_include_nested_inside_details_blocks():
  src = (
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    'ततो वाचयिता - <div class="js_include" includetitle="false" url="/m/1.md">\n'
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअन्तःमन्त्रः।\n</details>\n"
    "</div>\n"
    "</details>\n\n"
    "<details><summary>मूलम्</summary>\n\nमूलपाठः।\n</details>\n\n"
    "<details><summary>भट्टभास्कर-टीका</summary>\n\n"
    'व्याख्यातम् - <div class="js_include" includetitle="false" url="/t/1.md">\n'
    "उद्धरणम्।\n"
    "</div>\n"
    "</details>\n\n"
    "<details open><summary>आन्ध्रपाठे ऽधिकाः</summary>\n"
    '<div class="js_include" title="विश्वास-प्रस्तुतिः" url="/a/1.md">\n'
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\nअधिकमन्त्रः।\n</details>\n"
    "</div>\n"
    "</details>\n"
  )
  out = wrap_vedic_details(src)
  _assert_balanced_and_idempotent(wrap_vedic_details, src, out)
  assert out.count('url="/m/1.md"') == 1
  assert out.count('url="/t/1.md"') == 1
  assert out.count('url="/a/1.md"') == 1
  assert out.count("<summary>सर्वाष् टीकाः</summary>") == 1
  # आन्ध्रपाठे ऽधिकाः (contains विश्वास-प्रस्तुतिः include) stays unwrapped
  assert "<details open><summary>आन्ध्रपाठे ऽधिकाः</summary>" in out
  assert out.index("</details>\n\n<details open><summary>आन्ध्रपाठे ऽधिकाः</summary>") > out.index('url="/t/1.md"')

