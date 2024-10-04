from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, details_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.utils import patterns


def migrate_and_include_shlokas():

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/kalpAntaram/content/smRtiH/manuH/12.md",
                         title_maker=lambda text, index: metadata_helper.shloka_title_maker(text=text), title_before_include="### %s", dry_run=False)


def shloka_formatting():
  pass
  library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/padma-purANam", patterns=[r"(?<=[^०-९])([०-९]{1,2}) *(?=\n)"], replacement=r"॥ \1 ॥\n\n")

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/skanda-purANam/8_ambikA-khaNDaH", content_transformer=lambda c, m: space_helper.make_md_verse_lines(text=c))

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/rAmacharitamAnasa/TIkA", content_transformer=lambda x, y: content_processor.numerify_shloka_numbering(x))


def details_fix(dir_path):
  pass
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=r"(?<=\n)(\d\d\.\d+\.\d\d)[a-z]* *(\S.+(\n\1.+)*)(?=\n)", id_position=0))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=patterns.PATTERN_2LINE_SHLOKA_NUM_END))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.shlokas_to_details(content=c, pattern=patterns.PATTERN_MULTI_LINE_SHLOKA, title_base="श्री-राम-देशिकः"))
  
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.non_detail_parts_to_detail(content=c, title="विश्वास-प्रस्तुतिः"))


if __name__ == '__main__':
  pass
  # shloka_formatting()
  details_fix(dir_path="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/prakIrNAryabhAShAH/padya/tulasIdAsa/rAmacharitamAnasa/goraxapura-pATha/hindy-anuvAda")
  # details_helper.interleave_from_file(md_file=MdFile("/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/sarva-prastutiH.md"), source_file="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/tiruk-kural/TIkA/sa/shrI-rAma-deshikaH.md", dest_pattern= "<details.+?summary>विश्वास-प्रस्तुतिः *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>.*?- *(\S+)</summary>[\s\S]+?</details>\n", detail_title=None, dry_run=False)