import os

import regex

from doc_curation.md import library

from doc_curation.md.library import arrangement
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript


def title_fix(dir_path, overwrite=True, dry_run=False):
  # arrangement.fix_index_files(dir_path=dir_path, overwrite=overwrite, dry_run=dry_run)
  ## DEVANAGARI
  # library.apply_function(dir_path=dir_path, fn=MdFile.ensure_ordinal_in_title, transliteration_target=sanscript.DEVANAGARI, dry_run=dry_run)
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, overwrite=overwrite, dry_run=dry_run)
  # library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=dir_path, skip_dirs=False, source_script=sanscript.DEVANAGARI, overwrite=overwrite, dry_run=dry_run)
  
  ##### General
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.strip_index_from_title, dry_run=dry_run)
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.prepend_file_index_to_title, dry_run=dry_run)


  # library.apply_function(fn=MdFile.prepend_file_index_to_title, dir_path="/home/vvasuki/hindutva/hindutva-hugo/content/main/books/vivekAnanda", dry_run=dry_run)
  
  # md_files = library.get_md_files_from_path(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH/content/yajuH/taittirIyam/sUtram/ApastambaH/gRhyam/TIkA", file_pattern="**/*.md", file_name_filter=lambda x: len(regex.findall("\\d\\d_\\d\\d", os.path.basename(x))) > 0)
  # library.metadata_helper.add_init_words_to_title(md_files=md_files, target_title_length=30, dry_run=dry_run)
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/shrI-sampradAyaH/tattvam/parichaya-sanxepAH/yatIndra-mata-dIpikA/sarva-prastutiH", fn=metadata_helper.set_filename_from_title, dry_run=dry_run)

  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/bhAgavatam", fn=metadata_helper.remove_adhyaaya_word_from_title, dry_run=dry_run)

  # library.apply_function(fn=metadata_helper.set_title_from_content, dir_path=dir_path, title_extractor=metadata_helper.iti_naama_title_extractor)
  # library.apply_function(fn=metadata_helper.set_title_from_content, dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_shaivaH/content/sampradAyaH/vIra-shaivaH/tattvam/siddhAnta-shikhA-maNiH", title_extractor=metadata_helper.iti_naama_title_extractor, conclusion_pattern=".+\n?.+परिच्छेदः")


  ## KANNADA
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti", fn=metadata_helper.transliterate_title, transliteration_target=sanscript.KANNADA, dry_run=dry_run)
  pass


def file_name_fix(dir_path, overwrite=False, dry_run=False):
  pass
  library.apply_function(fn=metadata_helper.set_filename_from_title, dir_path=dir_path, skip_dirs=False, dry_run=dry_run, overwrite=overwrite)


if __name__ == '__main__':
  # title_fix("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/tattvam/jIva-gosvAmI/ShaT-sandarbhaH/en/satya-nArAyaNaH", overwrite=False, dry_run=False)
  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/gauDIyaH/tattvam/jIva-gosvAmI/ShaT-sandarbhaH/en/satya-nArAyaNaH", fn=metadata_helper.set_title_from_filename, transliteration_target=sanscript.DEVANAGARI, overwrite=True, dry_run=False)

  # file_name_fix("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/vaikhAnasaH/AgamaH/marIchiH/vimAnArchanA-kalpaH/", overwrite=True, dry_run=False)

  # arrangement.shift_indices(dir_path="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/vaikhAnasaH/kriyA/tirupati-mandiram/N-ramesha/05_mUrtis/02_DHRUVABERA", start_index=25, new_index_offset=-24, dry_run=False)
  library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/gItam_vaiShNavam/content/te/tALlapAka_annamAchArya/sankalanAni/advitIya-sankalanam", fn=metadata_helper.set_index_from_filename, dest_script=sanscript.DEVANAGARI, dry_run=False, overwrite=True)

  # library.apply_function(dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/brAhmaNam/sarva-prastutiH/1/", fn=metadata_helper.set_filename_from_title, source_script=sanscript.DEVANAGARI, dry_run=False, overwrite=False)

  # library.apply_function(
  #   fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/purANam/content/rAmAyaNam/goraxapura-pAThaH/kannaDAnuvAda",
  #   content_transformer=None,
  #   metadata_transformer=lambda c, m: metadata_helper.add_value_to_field(m, "unicode_script", "kannada"),
  #   dry_run=dry_run)

  # library.apply_function(
  #   fn=MdFile.transform, dir_path="/home/vvasuki/gitland/sanskrit/raw_etexts/mixed/ebhAratI-sampat",
  #   content_transformer=None,
  #   metadata_transformer=lambda c, m: metadata_helper.standardize_metadata(m),
  #   dry_run=False)

  # metadata_helper.copy_metadata_and_filename(ref_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/shrautam/meta/thITe-gaNeshaH/viShaya-vibhAgaH", dest_dir="/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/content/taittirIyam/sUtram/ApastambaH/shrautam/sarva-prastutiH", dry_run=dry_run)

  pass

