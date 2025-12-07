from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile
from doc_curation.utils import patterns


def make_details(dir_path):
  pass
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args,  **kwargs: details_helper.shlokas_to_muula_viprastuti_details(content=c, pattern=fr"(?<=\n)सूत्र *[\–\.०॰]+ *{patterns.PATTERN_SUTRA_DANDA}(?=\nपद)"))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args,  **kwargs: details_helper.pattern_to_details(content=c, pattern=fr"(?<=>\n)पदच्छेद *[\–\.०॰]+ *(.+)(?=\n)", title="पदच्छेदः"))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, *args,  **kwargs: details_helper.pattern_to_details(content=c, pattern=fr"(?<=\n)સૂત્ર ભૂમિકા *[\–\.०॰]+ *([\s\S]+?)(?=\n+<)", title="सूत्र-भूमिका"))


if __name__ == '__main__':
  pass
  make_details("/home/vvasuki/gitland/vishvAsa/AgamaH_vaiShNavaH/content/bhakti-sUtrANi/shANDilyaH/sarva-prastutiH/_index.md")