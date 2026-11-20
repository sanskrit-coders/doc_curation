from doc_curation.md.content_processor.ocr_helper import (
  get_gemini_flash_mangled_sanskrit_files,
  validate_proofread_markdown,
)


def test_get_gemini_flash_mangled_sanskrit_files_filters_and_returns_paths(tmp_path):
  matching = tmp_path / "matching.md"
  matching.write_text(
    "धर्म " + " ".join(f"पूर्व-पश्चिम{i}" for i in range(20))
    + " " + " ".join(f"[[ref{i}|text]]" for i in range(5)),
    encoding="utf-8",
  )
  too_few_links = tmp_path / "too-few-links.md"
  too_few_links.write_text(
    "धर्म " + " ".join(f"पूर्व-पश्चिम{i}" for i in range(20))
    + " [[one|link]]",
    encoding="utf-8",
  )
  hindi = tmp_path / "hindi.md"
  hindi.write_text(
    "यह है और वह में नहीं क्या तुम लोग अपनी हैं थी थे होगा"
    + " " + " ".join(f"पूर्व-पश्चिम{i}" for i in range(20))
    + " " + " ".join(f"[[ref{i}|text]]" for i in range(5)),
    encoding="utf-8",
  )

  assert get_gemini_flash_mangled_sanskrit_files(tmp_path) == [str(matching)]


def test_validate_proofread_markdown_clean_and_flags():
  doc = (
    "[[P10]] Intro text with [[Prefect|Perfect]] flag and note.[^10_1]\n\n"
    "[^10_1]: Note citing MBh XII. 142. 364.\\*\n\n"
    "[[P11]] Second *italic* paragraph with [[??]] doubt."
  )
  report = validate_proofread_markdown(doc, expected_pages=[10, 11])
  assert report["ok"] is True
  assert report["missing_pages"] == []
  assert report["duplicate_pages"] == []
  assert report["out_of_order_pages"] == []
  assert report["fn_refs"] == 1
  assert report["fn_defs"] == 1
  assert report["flags"] == ["[[Prefect|Perfect]]", "[[??]]"]


def test_validate_proofread_markdown_detects_all_issue_types():
  bad = (
    "[[P12]] Text[[P12]]: with ([[P13]] and says[^12_1]: and [[CONT_HYPH]] <br> and *unclosed\n\n"
    "[[P11]] Out of order and orphan[^12_2].\n\n"
    "[^12_1]: 1. Duplicated prefix\n\n"
    "[^12_9]: Never referenced\n\n"
    "<details><summary>मूलम्</summary>\ntext\n</details>"
  )
  report = validate_proofread_markdown(bad, expected_pages=[10, 11, 12, 13], ignore_html_tags=("details", "summary"))
  assert report["ok"] is False
  assert report["missing_pages"] == ["10"]
  assert report["duplicate_pages"] == ["12"]
  assert report["out_of_order_pages"] == [11]
  assert report["unspaced_page_markers"] == ["Text[[P12]]:", "([[P13]]"]
  assert report["leftover_tags"] == ["[[CONT_HYPH]]"]
  assert report["missing_defs"] == ["12_2"]
  assert report["orphan_defs"] == ["12_1", "12_9"]
  assert report["duplicate_fn_prefixes"] == ["1"]
  assert report["html_tags"] == ["<br>"]
  assert report["odd_asterisk_paragraphs"] == [1]


def test_validate_proofread_markdown_check_headings_opt_in():
  bad_headings = (
    "## Jump\n\n"
    "[[P10]] First paragraph.\n\n"
    "#### Skipped H3\n\n"
    "Valid paragraph.\n"
  )
  default_report = validate_proofread_markdown(bad_headings, expected_pages=[10])
  assert default_report["ok"] is True
  assert "heading_issues" not in default_report

  strict_report = validate_proofread_markdown(bad_headings, expected_pages=[10], check_headings=True)
  assert strict_report["ok"] is False
  assert any("LEVEL_JUMP" in issue for issue in strict_report["heading_issues"])

  clean_headings = (
    "## Top Section\n\n"
    "[[P10]] First paragraph.\n\n"
    "### Subsection\n\n"
    "Valid paragraph.\n"
  )
  clean_report = validate_proofread_markdown(clean_headings, expected_pages=[10], check_headings=True)
  assert clean_report["ok"] is True
  assert clean_report["heading_issues"] == []
