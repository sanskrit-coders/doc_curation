import doc_curation.md.library
from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript



dest_files = doc_curation.md.library.get_md_files_from_path(dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kuraL/sarva-prastutiH/")


def sa():
  # details_fix(dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/sa/shrI-rAma-deshikaH.md")
  details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/sa/shrI-rAma-deshikaH.md", dest_pattern= "<details.+?summary>विश्वास-प्रस्तुतिः *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>.*?- *(\S+)</summary>[\s\S]+?</details>\n", detail_title=None, dry_run=False)

def en():
  pass
  # details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/en/shuddhAnanda-bhAratI.md", dest_pattern= "<details.+?summary>श्री-राम-देशिकः *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n)\d+[\s\S]+?(\d+) +(?=\n)", detail_title="शुद्धानन्द-भारती", dry_run=False)
  details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kuraL/TIkA/en/rAmachandra-dIxitaH.md", dest_pattern= "<details.+?summary>रामचन्द्र-दीक्षितः.+- (\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n)(4\d)\.\D[\s\S]+?(?=\n[\n\\])", detail_title="रामचन्द्र-दीक्षितः (en)", overwrite=True, dry_run=False)
  # details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/en/ashraf-choice.md", dest_pattern= "<details.+?summary>श्री-राम-देशिकः *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n)([०-९]{4})\n\D[\s\S]+?(?=\n\n|[०-९])", detail_title="NVK Ashraf choice (en)", dry_run=False)
  # details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/en/ashraf-choice.md", dest_pattern= "<details.+?summary>NVK Ashraf choice.* *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n)([०-९]+)[\.:]\D.+(?=\n)", detail_title="NVK Ashraf notes (en)", dry_run=False)
  # details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/hi.md", dest_pattern= "<details.+?summary>शुद्धानन्द-भारती.+ *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n)(\d+)\n\D[\s\S]+?(?=\n\n|\d)", detail_title="वेङ्कटकृष्ण (हि)", dry_run=False)
  # details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/hi.md", dest_pattern= "<details.+?summary>शुद्धानन्द-भारती.+ *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n)(\d+)\n\D[\s\S]+?(?=\n\n|\d)", detail_title="वेङ्कटकृष्ण (हि)", dry_run=False)
  # details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/kn.md", dest_pattern= "<details.+?summary>वेङ्कटकृष्ण.+ *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"(?<=\n)(\d+)\.\D[\s\S]+?(?=\n\n|\d)", detail_title="श्रीनिवास (क)", dry_run=False)


def fix_muula():
  details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/mUlam.md", dest_pattern= "<details.+?summary>विश्वास-प्रस्तुतिः *- *([०-९]+)</summary>[\s\S]+?</details>(?=\n|$)", source_pattern= r"(?<=\n)[^#\s].+?\n.+? +([०-९]+)(?=\n)", detail_title="विश्वास-प्रस्तुतिः", overwrite=True, dry_run=False)
  # details_helper.interleave_from_file(md_files=dest_files, source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/mUlam.md", dest_pattern= r"<details.+?summary>मूलम् *- *([०-९]+)</summary>[\s\S]+?</details>(?=\n|$)", source_pattern= r"(?<=\n)[^#\s].+?\n.+? +([०-९]+)(?=\n)", detail_title="मूलम्", overwrite=True, dry_run=False)


if __name__ == '__main__':
  pass
  # fix_muula()
  en()
  # library.apply_function(fn=MdFile.split_to_bits, dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/sarva-prastutiH", frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI,  title_index_pattern=None) # 
