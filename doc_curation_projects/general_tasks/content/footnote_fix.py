from doc_curation.md import library
from doc_curation.md.content_processor import footnote_helper
from doc_curation.md.file import MdFile


def fix_footnotes(dir_path):

  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/articles/homa-variations", content_transformer=lambda x, y: footnote_helper.fix_plain_footnotes(x))

  # Footnotes like (23) referring to definition (23. xyz)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: footnote_helper.fix_plain_footnotes(x, def_pattern=r"\((\d+)[\. ]*([^\d\)][^\)]+)\) *", def_replacement_pattern=r"\n[^\1]: \2\n", ref_pattern=r"\((\d+)\)"))

  # Footnotes like {23} referring to definition {23. xyz}
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: footnote_helper.fix_plain_footnotes(x, def_pattern=r"\{(\d+)[\. ]+([^\d\)][^\}]+)\}*", def_replacement_pattern=r"\n[^\1]: \2\n", ref_pattern=r"\{(\d+)\}"))

  # Footnotes like [23] referring to definition [23. xyz]
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: footnote_helper.fix_plain_footnotes(x, def_pattern=r"\[(\d+)[\. ]+([^\d\)][^\]]+)\]*", def_replacement_pattern=r"\n[^\1]: \2\n", ref_pattern=r"\[(\d+)\]"))

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.comments_to_footnotes(c), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.define_footnotes_near_use(c), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.fix_intra_word_footnotes(c), dry_run=False)
  pass

def fix_footnotes_ambuda(dir_path):
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.fix_ambuda_footnote_definition_groups(c), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.add_page_id_to_ref_ids(c), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.define_footnotes_near_use(c), dry_run=False)

def fix_footnotes_vod(dir_path):
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.fix_plain_footnotes(c, ref_pattern=r"\^\(\[\d+\]\(#(\d+)\)\)", def_pattern=None), dry_run=False)
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: footnote_helper.fix_plain_footnotes(c, ref_pattern=None, def_pattern=r"(?<=\n)\[.+?\]\(#(\d+)a?\)"), dry_run=False)



if __name__ == '__main__':
  pass
  # fix_footnotes(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/pAncharAtrAgamaH/laxmI-tantram/tmp")
  # fix_footnotes_ambuda(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/mAdhva-sampradAyaH/kriyA/madhva-tantra-sAra-sangrahaH/sarva-prastutiH")
  # fix_footnotes_vod(dir_path="/home/vvasuki/gitland/vishvAsa/notes/content/sapiens/branches/Aryan/satem/indo-iranian/indo-aryan/india/4_post-brit/politics/id/hindutva/articles/goel_sitArAm")
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/baudhAyanaH/shrautam/sarva-prastutiH", content_transformer=lambda c, m: footnote_helper.make_ids_unique_to_be_fixed(c), dry_run=False)
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/meta/kalpaH/shrautam/articles/yajna-tattva-prakAshaH/", content_transformer=lambda c, m: footnote_helper.add_page_id_to_ref_ids(c, page_pattern=r"[\s\S]+?\[\[([\d०-९]+)\]\]"), dry_run=False)
