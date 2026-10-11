import textwrap

from doc_curation.md.content_processor.footnote import cleaner


def test_numbered_lane_moves_tail_defs_into_blocks():
  content = textwrap.dedent("""\
    <details><summary>सर्वाष् टीकाः</summary>

    <details><summary>अनुवाद (हिन्दी)</summary>

    जो पुरुष मनको[१] और बुद्धिको[२] लगाता है॥१॥
    </details>
    </details>

    [१]:मनका अर्थ यहाँ चित्त है।

    [२]:बुद्धिका अर्थ यहाँ निश्चय है।
    """)
  new_content, report = cleaner.match_dangling_footnotes_sequentially(content)
  assert new_content != content
  assert len(report["placed"]) == 2
  assert not report["unmatched_defs"]
  # Both defs land inside the hindi block, after the use para.
  hindi = new_content.split("<details><summary>अनुवाद (हिन्दी)</summary>")[1]
  assert hindi.index("[१]:मनका अर्थ") < hindi.index("</details>")
  assert hindi.index("[२]:बुद्धिका अर्थ") < hindi.index("</details>")
  # Tail is clean and the result is a fixpoint.
  assert "[१]:" not in new_content.split("</details>")[-1]
  check, _ = cleaner.match_dangling_footnotes_sequentially(new_content)
  assert check == new_content


def test_star_lane_pairs_in_order():
  content = textwrap.dedent("""\
    <details><summary>अनुवाद (हिन्दी)</summary>

    नख और दाँत काले हों,[*] उन सबको प्रायश्चित्त करना चाहिये॥३॥
    </details>

    [*]: क्योंकि वे पूर्व जन्ममें चोर होते हैं।
    """)
  new_content, report = cleaner.match_dangling_star_footnotes(content)
  assert new_content != content
  assert len(report["placed"]) == 1
  assert "[*]:" in new_content.split("</details>")[0]
  check, _ = cleaner.match_dangling_star_footnotes(new_content)
  assert check == new_content


def test_cross_file_moves_defs_to_prev_refs():
  prev = textwrap.dedent("""\
    <details><summary>अनुवाद (हिन्दी)</summary>

    विदुरजीको मन्त्रणा[१], तथा छहों[२] गुणोंके चिन्तनमें नियुक्त किया॥१०॥
    </details>
    """)
  curr = textwrap.dedent("""\
    <details><summary>अनुवाद (हिन्दी)</summary>

    कुछ और कथा॥१॥
    </details>

    [१]:गुप्त सलाह देना मन्त्रणा है।

    [२]:सन्धि आदि छः गुण हैं।
    """)
  new_prev, new_curr, report = cleaner.match_cross_file_footnotes(prev, curr)
  assert len(report["placed"]) == 2
  assert "[१]:गुप्त सलाह" in new_prev
  assert "[१]:" not in new_curr


def test_unstable_landscape_left_untouched():
  # Bare order (२, १) fights ref order (१, २): whichever pair round one
  # picks, round two pairs the leftovers differently, so no round is a
  # fixpoint and the tool must refuse (fixpoint guard).
  content = textwrap.dedent("""\
    <details><summary>अनुवाद (हिन्दी)</summary>

    पहला[१] और दूसरा[२]॥१॥
    </details>

    [२]:दूसरे पदकी टिप्पणी।

    [१]:पहले पदकी टिप्पणी।
    """)
  new_content, report = cleaner.match_dangling_footnotes_sequentially(content)
  assert new_content == content
  assert any(n.startswith("unstable") for n in report["notes"])


def test_wrapper_gap_def_moves_into_content_block():
  content = textwrap.dedent("""\
    <details><summary>सर्वाष् टीकाः</summary>

    <details><summary>अनुवाद (हिन्दी)</summary>

    पृथ्वीको शम्यापातके[*] द्वारा नापा॥९५॥
    </details>

    * ‘शम्या’ एक काठके डंडेको कहते हैं।

    </details>
    """)
  new_content, report = cleaner.match_dangling_footnotes_sequentially(content)
  assert new_content != content
  assert len(report["placed"]) == 1
  hindi = new_content.split("<details><summary>अनुवाद (हिन्दी)</summary>")[1]
  assert "[*]: ‘शम्या’" in hindi.split("</details>")[0]
  check, _ = cleaner.match_dangling_footnotes_sequentially(new_content)
  assert check == new_content


def test_list_bullets_are_not_footnote_defs():
  content = textwrap.dedent("""\
    <details><summary>अनुवाद (हिन्दी)</summary>

    कथा समाप्त हुई।
    </details>

    * पहला प्रकार
    * दूसरा प्रकार
    * तीसरा प्रकार
    """)
  new_content, report = cleaner.match_dangling_footnotes_sequentially(content)
  assert new_content == content
  assert not report["placed"]
