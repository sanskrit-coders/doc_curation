from pathlib import Path

from indic_transliteration import sanscript

from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement


def test_split_to_bits_recursive_and_filter(tmp_path):
  src = tmp_path / "book" / "_index.md"
  src.parent.mkdir(parents=True)
  src.write_text(
    '+++\ntitle = "पुस्तकम्"\n+++\n\nIntro line\n\n'
    '## ० प्रास्ताविकम्\n\n'
    '### VORWORT\n\nGerman text\n\n#### English Translation\n\nEnglish text\n\n'
    '### EINLEITUNG\n\n'
    '#### § 1. Die Handschriften.\n\nMS info\n\n##### English Translation\n\nMS EN\n\n'
    '## १ प्रथमः\n\n'
    '### ०१ स्थानकम्\n\n'
    '#### ०१\n\nMantra 1[^1]\n\n[^1]: Note 1\n\n'
    '#### १३–१४\n\nMantra 13-14\n',
    encoding="utf-8",
  )

  md_file = MdFile(file_path=str(src), frontmatter_type=MdFile.TOML)
  md_file.split_to_bits(
    source_script=sanscript.DEVANAGARI,
    start_index=None,
    max_length=80,
    max_depth=3,
    split_sections_filter=lambda sections, *_: [s.title for s in sections] != ["English Translation"],
  )
  arrangement.fix_index_files(
    dir_path=str(src.parent),
    transliteration_target=sanscript.DEVANAGARI,
    dry_run=False,
  )

  # Level 1 & 2 indices preserved with '+' prefix
  assert MdFile(str(src)).read()[0]["title"] == "+पुस्तकम्"
  assert MdFile(str(tmp_path / "book" / "0_prAstAvikam" / "_index.md")).read()[0]["title"] == "+० प्रास्ताविकम्"
  assert MdFile(str(tmp_path / "book" / "1_prathamaH" / "01_sthAnakam" / "_index.md")).read()[0]["title"] == "+०१ स्थानकम्"

  # VORWORT was NOT split further into VORWORT/English_Translation.md
  vorwort = tmp_path / "book" / "0_prAstAvikam" / "VORWORT.md"
  assert vorwort.exists()
  assert not (tmp_path / "book" / "0_prAstAvikam" / "VORWORT").exists()
  assert "## English Translation" in MdFile(str(vorwort)).read()[1]

  # EINLEITUNG was split into § 1 with reduced English Translation and clean filename
  s1 = tmp_path / "book" / "0_prAstAvikam" / "EINLEITUNG" / "1_Die_Handschriften.md"
  assert s1.exists()
  s1_meta, s1_body = MdFile(str(s1)).read()
  assert s1_meta["title"] == "§ 1 Die Handschriften"
  assert "## English Translation" in s1_body

  # Range anuvāka heading preserved en-dash as hyphen
  a1 = tmp_path / "book" / "1_prathamaH" / "01_sthAnakam" / "01.md"
  a13 = tmp_path / "book" / "1_prathamaH" / "01_sthAnakam" / "13-14.md"
  assert a1.exists()
  assert a13.exists()
  assert MdFile(str(a13)).read()[0]["title"] == "१३–१४"
