from pathlib import Path

import pytest

from doc_curation.md.content_processor.details import common, maker
from doc_curation.md.file import MdFile


def test_top_level_detail_spans_and_nested_parsing():
  text = (
    "# शीर्षकम्\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "अग्निमीळे\n"
    "</details>\n\n"
    "<details><summary>व्याख्या</summary>\n\n"
    "व्याख्या-वाक्यम्\n\n"
    "<details><summary>विश्वास-टिप्पनी</summary>\n\n"
    "टिप्पनी-वाक्यम्\n"
    "</details>\n\n"
    "उत्तर-वाक्यम्\n"
    "</details>\n"
  )
  spans = common.get_top_level_detail_spans(text)
  assert len(spans) == 2
  parsed = common.parse_top_level_details(text)
  assert [p[2] for p in parsed] == ["विश्वास-प्रस्तुतिः", "व्याख्या"]
  assert "<details><summary>विश्वास-टिप्पनी</summary>" in parsed[1][3]
  assert "उत्तर-वाक्यम्" in parsed[1][3]


def test_generic_sanskrit_vipra_mUla_accents_and_nested_details():
  content = (
    "+++\n"
    "title = \"01\"\n"
    "+++\n\n"
    "<details><summary>पूर्वम्</summary>\n\n"
    "<details><summary>अन्तः</summary>\n\n"
    "रक्ष्यम्\n"
    "</details>\n"
    "</details>\n\n"
    "## 1.1\n\n"
    "आशा॑स्स॒मस्ताः॑ । स्वाहाा॑ ॥\n\n"
    "---\n\n"
    "नमो भगवते ॥\n"
  )
  out = maker.generic_sanskrit_vipra_mUla(
    content,
    split_sentences=False,
    to_us_accents=True,
    unaccented_vishvaasa_title="विश्वास-प्रस्तुतिः (स्वराः पूर्याः)",
    vishvaasa_preprocessor=lambda s: s.replace("ाा", "ा"),
  )
  assert out.startswith("+++\ntitle = \"01\"\n+++\n\n")
  # Existing nested <details> block stays intact
  assert "<details><summary>अन्तः</summary>\n\nरक्ष्यम्\n</details>" in out
  # Horizontal rule `---` mid-file is kept verbatim and later unaccented mantra is wrapped
  assert "\n---\n\n<details open><summary>विश्वास-प्रस्तुतिः (स्वराः पूर्याः)</summary>\n\nनमो भगवते ॥\n</details>" in out
  # Internal sentence not split (`split_sentences=False`), preprocessor fixed `ाा` in विश्वास only
  assert out.count("<summary>मूलम्</summary>") == 2
  assert "स्वाहाा॑ ॥" in out
  parsed = common.parse_top_level_details(out)
  vipra_1 = [b for _, _, t, b in parsed if t == "विश्वास-प्रस्तुतिः"][0]
  assert "।" in vipra_1 and "॥" in vipra_1
  assert "ाा" not in vipra_1
  assert "᳓" in vipra_1 or "᳙" in vipra_1


def test_interleave_from_file_callable_source_multiple_files(tmp_path):
  target_dir = tmp_path / "target"
  source_dir = tmp_path / "source"
  target_dir.mkdir()
  source_dir.mkdir()

  target_body = (
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "मन्त्रः ॥ १ ॥\n"
    "</details>\n\n"
    "<details><summary>मूलम्</summary>\n\n"
    "मन्त्रः ॥ १ ॥\n"
    "</details>\n"
  )
  (target_dir / "01.md").write_text(f"+++\ntitle = '01'\n+++\n\n{target_body}", encoding="utf-8")
  (target_dir / "02.md").write_text(f"+++\ntitle = '02'\n+++\n\n{target_body}", encoding="utf-8")
  (source_dir / "01.md").write_text("1 Commentary one\n", encoding="utf-8")
  (source_dir / "02.md").write_text("1 Commentary two\n", encoding="utf-8")

  md_files = [
    MdFile(file_path=str(target_dir / "01.md")),
    MdFile(file_path=str(target_dir / "02.md")),
  ]
  maker.interleave_from_file(
    md_files=md_files,
    source_file=lambda fp: str(source_dir / Path(fp).name),
    detail_title="टीका",
    dry_run=False,
  )

  _, c1 = MdFile(file_path=str(target_dir / "01.md")).read()
  _, c2 = MdFile(file_path=str(target_dir / "02.md")).read()
  assert "Commentary one" in c1 and "Commentary two" not in c1
  assert "Commentary two" in c2 and "Commentary one" not in c2


def test_interleave_paired_mUla_commentary_and_file_removal(tmp_path):
  target = (
    "# प्रथमः\n\n"
    "## 1.1\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "मन्त्रः एकः ॥ १ ॥\n"
    "</details>\n\n"
    "<details><summary>मूलम्</summary>\n\n"
    "मन्त्रः एकः ॥ १ ॥\n"
    "</details>\n\n"
    "## 1.2\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "मन्त्रः द्वौ ॥ २ ॥\n"
    "</details>\n\n"
    "<details><summary>मूलम्</summary>\n\n"
    "मन्त्रः द्वौ ॥ २ ॥\n"
    "</details>\n\n"
    "## 1.3 हयग्रीव\n\n"
    "## 1.4 कोरवै\n\n"
    "<details open><summary>विश्वास-प्रस्तुतिः</summary>\n\n"
    "अन्तः ॥\n"
    "</details>\n\n"
    "<details><summary>मूलम्</summary>\n\n"
    "अन्तः ॥\n"
    "</details>\n"
  )
  source = (
    "<details open><summary>मूलम्</summary>\n\n"
    "> मन्त्रः एकः ॥ १ ॥\n"
    "</details>\n\n"
    "<details><summary>व्याख्या</summary>\n\n"
    "प्रथम-व्याख्या\n"
    "</details>\n\n"
    "<details open><summary>मूलम्</summary>\n\n"
    "> मन्त्रः द्वौ पाठान्तरम् ॥ २ ॥\n"
    "</details>\n\n"
    "<details><summary>व्याख्या</summary>\n\n"
    "द्वितीय-व्याख्या\n\n"
    "<details><summary>विश्वास-टिप्पनी</summary>\n\n"
    "अन्तर्निहितम्\n"
    "</details>\n"
    "</details>\n\n"
    "<details open><summary>मूलम्</summary>\n\n"
    "> हयग्रीव-मन्त्रः ॥ ३ ॥\n"
    "</details>\n\n"
    "<details><summary>व्याख्या</summary>\n\n"
    "तृतीय-व्याख्या\n"
    "</details>\n\n"
    "<details open><summary>मूलम्</summary>\n\n"
    "[[मातृकायामेतावदेवोपलभ्यम्]]\n"
    "</details>\n"
  )

  new_target, new_source = maker.interleave_paired_mUla_commentary(
    target_content=target,
    source_content=source,
    commentary_title="श्रीनिवास-यज्वा",
    variant_mUla_title="मूलम् - श्रीनिवास-यज्वा",
    mUla_clean_fn=lambda s: "\n".join(line.lstrip("> ") for line in s.splitlines()).strip(),
  )

  details = common.parse_top_level_details(new_target)
  titles = [t for _, _, t, _ in details]
  assert titles == [
    "विश्वास-प्रस्तुतिः",
    "मूलम्",
    "श्रीनिवास-यज्वा",
    "विश्वास-प्रस्तुतिः",
    "मूलम्",
    "मूलम् - श्रीनिवास-यज्वा",
    "श्रीनिवास-यज्वा",
    "मूलम् - श्रीनिवास-यज्वा",
    "श्रीनिवास-यज्वा",
    "विश्वास-प्रस्तुतिः",
    "मूलम्",
  ]
  # Nested details inside 1.2 commentary stayed intact
  assert "<details><summary>विश्वास-टिप्पनी</summary>" in details[6][3]
  # 1.3 हयग्रीव received both variant mUla and commentary
  idx_13 = new_target.index("## 1.3 हयग्रीव")
  idx_14 = new_target.index("## 1.4 कोरवै")
  section_13 = new_target[idx_13:idx_14]
  assert "हयग्रीव-मन्त्रः ॥ ३ ॥" in section_13
  assert "तृतीय-व्याख्या" in section_13

  # Identical mUla 1 and unpaired trailing mUla note stay in source;
  # inserted mUla 2 & 3 and all 3 commentaries removed
  rem_titles = [t for _, _, t, _ in common.parse_top_level_details(new_source)]
  assert rem_titles == ["मूलम्", "मूलम्"]
  assert "मन्त्रः एकः" in new_source
  assert "[[मातृकायामेतावदेवोपलभ्यम्]]" in new_source
  assert "[[मातृकायामेतावदेवोपलभ्यम्]]" not in new_target

  # Empty source file deletion check via file API
  t_path = tmp_path / "t.md"
  s_path = tmp_path / "s.md"
  t_path.write_text(
    "+++\ntitle = 't'\n+++\n\n<details><summary>मूलम्</summary>\n\nकः\n</details>\n",
    encoding="utf-8",
  )
  s_path.write_text(
    "+++\ntitle = 's'\n+++\n\n<details open><summary>मूलम्</summary>\n\nखः\n</details>\n\n"
    "<details><summary>व्याख्या</summary>\n\nटीका\n</details>\n",
    encoding="utf-8",
  )
  maker.interleave_paired_mUla_commentary_file(
    target_md_file=MdFile(file_path=str(t_path)),
    source_file=s_path,
    commentary_title="श्रीनिवास-यज्वा",
    variant_mUla_title="मूलम् - श्रीनिवास-यज्वा",
    remove_from_source=True,
    delete_empty_source=True,
  )
  assert not s_path.exists()
  _, final_t = MdFile(file_path=str(t_path)).read()
  assert "मूलम् - श्रीनिवास-यज्वा" in final_t
  assert "टीका" in final_t


def test_interleave_paired_rejects_unbalanced_details():
  with pytest.raises(ValueError, match="Unbalanced <details>"):
    maker.extract_paired_details(
      "<details><summary>व्याख्या</summary>\n\nअपूर्णम्\n",
    )
