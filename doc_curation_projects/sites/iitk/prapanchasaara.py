from doc_curation.md import library
from doc_curation.scraping import iitk
from indic_transliteration import sanscript


def dump_prapanchasaaraH():
  outfile_path = "/home/vvasuki/vvasuki-git/saMskAra/content/AgamaH/mishram/prapancha-sAraH/"
  url_base="https://www.sankara.iitk.ac.in/comprehensive-texts?language=dv&field_text2_tid=104"
  for chapter_id in range(1, 34):
    if chapter_id is None:
      item_url = url_base
    else:
      item_url = "%s&field_chapter_value=%s" % (url_base, str(chapter_id))
    title_maker = lambda soup, title_prefix : sanscript.transliterate("%02d" % chapter_id, sanscript.IAST, sanscript.DEVANAGARI)
    iitk.dump_item(item_url=item_url, outfile_path="%s/%02d.md" % (outfile_path, chapter_id), title_maker=title_maker)
  library.fix_index_files(dir_path=outfile_path, dry_run=False)


# dump_prapanchasaaraH()


