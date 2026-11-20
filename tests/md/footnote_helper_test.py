import textwrap

from doc_curation.md.content_processor.footnote import helper


def test_multiparagraph_definition_moves_wholly_near_use():
  content = textwrap.dedent("""\
    Early para mentioning the vessel.[^9] More text here.

    Unrelated middle para.

    ## Notes

    [^9]: [(a) First paragraph of the note,
    lazy continuation line of the same paragraph.

        Second paragraph, indented.

        > A quoted line inside the note.

        [[P107]]
    """)
  new_content = helper.define_footnotes_near_use(content)
  use_para, _, tail = new_content.partition("Unrelated middle para.")
  # Whole definition (all four parts, in order) sits between use and tail.
  for part in ("[(a) First paragraph", "lazy continuation",
               "Second paragraph, indented.", "A quoted line", "[[P107]]"):
    assert part in use_para, part
  assert use_para.index("[(a) First paragraph") < use_para.index("[[P107]]")
  # Nothing orphaned where the notes used to be.
  assert "[^9]:" not in tail
  assert "Second paragraph" not in tail
  assert "[[P107]]" not in tail


def test_single_line_and_pure_multiline_defs_still_work():
  content = textwrap.dedent("""\
    First claim.[^1] Second claim.[^2]

    ## Notes

    [^1]: Short note.

    [^2]:

        Pure multiline note.
    """)
  new_content = helper.define_footnotes_near_use(content)
  assert new_content.index("[^1]: Short note.") < new_content.index("## Notes")
  assert new_content.index("[^2]:") < new_content.index("## Notes")
  assert "Pure multiline note." in new_content
  tail = new_content.split("## Notes")[1]
  assert "[^1]:" not in tail and "[^2]:" not in tail


def test_shared_paragraph_gets_defs_in_ascending_order():
  content = textwrap.dedent("""\
    Claim one.[^1] Claim two.[^2]

    ## Notes

    [^1]: First note.

    [^2]: Second note.
    """)
  new_content = helper.define_footnotes_near_use(content)
  assert new_content.index("[^1]: First note.") < new_content.index("[^2]: Second note.")


def test_to_latex_footnotes_uses_content_not_id():
  content = textwrap.dedent("""\
    A claim.[^12]

    [^12]: The actual note text.
    """)
  assert helper.to_latex_footnotes(content).strip() == \
      r"A claim.\footnote{The actual note text.}".strip()


def test_preserve_ids_keeps_identical_definitions_distinct_and_spaces_headings():
  content = textwrap.dedent("""\
    First paragraph claims X.[^10_1]

    ## Next Section

    Second paragraph also claims X.[^12_5]

    [^10_1]: *Op. cit.*, p. 10.

    [^12_5]: *Op. cit.*, p. 10.
    """)
  preserved = helper.define_footnotes_near_use(content, preserve_ids=True)
  assert "[^10_1]: *Op. cit.*, p. 10." in preserved
  assert "[^12_5]: *Op. cit.*, p. 10." in preserved
  assert "[^10_1]: *Op. cit.*, p. 10.\n\n## Next Section" in preserved
  assert preserved.index("[^10_1]:") < preserved.index("## Next Section") < preserved.index("[^12_5]:")

  deduped = helper.define_footnotes_near_use(content)
  assert "[^12_5]" not in deduped
  assert deduped.count("[^10_1]: *Op. cit.*, p. 10.") == 1
  assert "also claims X.[^10_1]" in deduped
