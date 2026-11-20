import codecs
import logging
import os
import textwrap

from doc_curation.md.content_processor import section_helper


def get_lines(test_file_name):
    with codecs.open(os.path.join(os.path.dirname(__file__), "data", test_file_name), "r", 'utf-8') as file_obj:
        return list(file_obj.readlines())


def test_get_lines_till_section():
    test_lines = get_lines(test_file_name="test.md")
    (lines_till_section, remaining) = section_helper.get_lines_till_section(test_lines)
    lines_till_section = list(lines_till_section)
    remaining = list(remaining)
    logging.info(lines_till_section)
    logging.info(remaining)
    assert len(lines_till_section) + len(remaining) == len(test_lines)


def test_split_to_sections():
    test_lines = get_lines(test_file_name="test.md")
    (lines_till_section, remaining) = section_helper.get_lines_till_section(test_lines)
    sections = section_helper.split_to_sections(remaining)
    for section in sections:
        logging.info(section.title)
        logging.info(list(section.lines))
    assert len(sections) == 2


def test_split_to_sections_no_title():
    test_lines = get_lines(test_file_name="untitled_sections.md")
    (lines_till_section, remaining) = section_helper.get_lines_till_section(test_lines)
    sections = section_helper.split_to_sections(remaining)
    for section in sections:
        logging.info(section.title)
        logging.info(list(section.lines))
    assert len(sections) == 32


def test_get_section_title():
    assert section_helper.get_section_title("## 1") == "1"


def test_parse_outline_blocks_skips_multiblock_footnotes():
    md = textwrap.dedent("""\
        # Document Title[^1]

        First prose block.

        [^1]: First note paragraph.

            > Indented quote inside note.

            Second note paragraph.

        ## Existing Section

        Second prose block.
        """)
    blocks = section_helper.parse_outline_blocks(md)
    assert [(b["p_idx"], b["is_heading"], b["level"], b["text"]) for b in blocks] == [
        (-1, True, 1, "# Document Title[^1]"),
        (0, False, 0, "First prose block."),
        (-1, True, 2, "## Existing Section"),
        (1, False, 0, "Second prose block."),
    ]
    assert section_helper.prose_tokens_without_headings(md) == [
        "First", "prose", "block.", "Second", "prose", "block."
    ]


def test_audit_headings_detects_errors_and_allows_valid_cases():
    bad = textwrap.dedent("""\
        # Title

        ### Skipped H2

        Line fused to heading
        ## Unspaced

        ## Before Footnote

        [^9]: Unrelated footnote def.

        ## Before Continuation

        lowercase continuation words.

        ## On Attribution

        [First published: 1940.]
        """)
    issues = section_helper.audit_headings(bad)
    assert any("LEVEL_JUMP: H1 -> H3" in x for x in issues)
    assert any("UNSPACED_HEADING" in x for x in issues)
    assert any("HEADING_BEFORE_FOOTNOTE_DEF" in x for x in issues)
    assert any("HEADING_BEFORE_LOWERCASE" in x for x in issues)
    assert any("HEADING_BEFORE_ATTRIBUTION" in x for x in issues)

    valid = textwrap.dedent("""\
        # Title[^1]

        [^1]: Title note.

        ## Parent

        ### Stacked Child

        Opening paragraph.
        """)
    assert section_helper.audit_headings(valid) == []


def test_apply_heading_outline_splits_preserves_footnotes_and_checks_parity():
    raw = textwrap.dedent("""\
        Source: Book Title

        First sentence.[^1] Second topic starts here.[^2]

        Third paragraph.[^3]

        [^1]: Identical note.

        [^2]: Identical note.

        [^3]: Third note.
        """)
    headings = [
        {"para_idx": 1, "level": 2, "title": "Opening"},
        {"para_idx": 1, "level": 3, "title": "Subtopic", "split_before": "Second topic starts here."},
        {"para_idx": 2, "level": 2, "title": "Closing"},
    ]
    result, errors = section_helper.apply_heading_outline(raw, headings)
    assert errors == []
    assert section_helper.prose_tokens_without_headings(raw) == section_helper.prose_tokens_without_headings(result)
    assert "## Opening\n\nFirst sentence.[^1]\n\n[^1]: Identical note.\n\n### Subtopic" in result
    assert "### Subtopic\n\nSecond topic starts here.[^2]\n\n[^2]: Identical note.\n\n## Closing" in result
    assert "## Closing\n\nThird paragraph.[^3]\n\n[^3]: Third note." in result

    bad_headings = [
        {"para_idx": 1, "level": 4, "title": "Skipped Level"},
        {"para_idx": 1, "level": 3, "title": "Missing Split", "split_before": "Not present"},
    ]
    _, bad_errors = section_helper.apply_heading_outline(raw, bad_headings)
    assert any("LEVEL_JUMP" in e for e in bad_errors)
    assert any("SPLIT_NOT_UNIQUE" in e for e in bad_errors)
