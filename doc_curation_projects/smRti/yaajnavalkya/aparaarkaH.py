import regex

from doc_curation_projects.smRti.yaajnavalkya import content
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper


def title_maker(text_matched, index, file_title):
  title_id = content.get_title_id(text_matched=text_matched)
  return title_id + "_"


def migrate_and_include_commentary(chapter_id):
  text_processor = lambda x: regex.sub("^.+?\n", "", x)

  def replacement_maker(text_matched, dest_path):
    id_line = regex.match("(.+॥.+\n)\n", text_matched).group(1)
    include_line = include_helper.vishvAsa_include_maker(dest_path, h1_level=4, classes=["collapsed"], title="मिताक्षरा")
    return "%s\n%s" % (id_line, include_line)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/yAjJNavalkyaH/aparArkaH/%s" % chapter_id, text_patterns = ["[॥ ०-९]+\.[०-९\.]+? *॥.+\n[^>][\\s\\S]+?(?=\n>|$)"], migrated_text_processor=text_processor, replacement_maker=replacement_maker,
                         title_maker=title_maker, dry_run=False)


if __name__ == '__main__':
  pass
  # library.combine_files_in_dir(md_file=MdFile(file_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/yAjJNavalkyaH/aparArkaH/08/_index.md"))
  # library.defolderify_single_md_dirs(dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/yAjJNavalkyaH/aparArkaH")
  # metadata_helper.ensure_ordinal_in_title("/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/yAjJNavalkyaH/aparArkaH/01_AchAraH")
  # library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/yAjJNavalkyaH/aparArkaH/01_AchAraH", dry_run=False)
  metadata_helper.copy_metadata_and_filename(ref_dir="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/yAjJNavalkyaH/prastutiH", dest_dir="/home/vvasuki/vishvAsa/kalpAntaram/content/smRtiH/yAjJNavalkyaH/aparArkaH")

  # migrate_and_include_commentary(chapter_id="01_AchAraH")
