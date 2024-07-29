from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.utils import text_utils


def translate_sentences(base_dir, source_language="es", dest_language="en"):
  library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: details_helper.sentences_to_translated_details(c, source_language=source_language, dest_language=dest_language), dry_run=False)


def translate_details(base_dir, source_language, dest_language):
  library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: details_helper.add_translation(c, source_language=source_language, dest_language=dest_language), dry_run=False)


def translate_partwise(base_dir, source_language, dest_language):
  library.apply_function(fn=MdFile.transform, dir_path=base_dir, content_transformer=lambda c, m: text_utils.translate_partwise(text=c, source_language=source_language, dest_language=dest_language), dry_run=False)


if __name__ == '__main__':
  # add_translation(base_dir="/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/static/rAmAnuja-sampradAyaH/vyakti-shlokAdi/gurubhyas_tad-gurubhyaH.md")
  # translate_sentences(base_dir="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/castellano/rangapuri-rAmAyaNam/", source_language="es", dest_language="en")
  translate_partwise(base_dir="/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/castellano/rangapuri-rAmAyaNam/0_Meta/01_Contenido/07_El_Libro_del_Gobernante_Ideal.md", source_language="es", dest_language="en")
  pass