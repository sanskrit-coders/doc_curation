import logging

from doc_curation.md.file import MdFile
from indic_transliteration import sanscript
import os.path
from doc_curation.md.library import combination, arrangement
from doc_curation.md import library
from doc_curation.md.content_processor import details_helper

STATIC_ROOT = "/home/vvasuki/gitland/vishvAsa/mahAbhAratam/static/vyAsaH/shlokashaH/06-bhIShma-parva/03-bhagavad-gItA-parva"

def import_bellamkonda():
  pass
  static_root = os.path.join(STATIC_ROOT, "saMskRtam/shankaraH/sarvASh_TIkAH")
  source_dir = "/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/vyAsaH/shlokashaH/bhagavad-gItA-parva/TIkA/bellamkoNDa-rAma-rAyaH/gItA-bhAShyam"
  md_files_in = library.get_md_files_from_path(dir_path=source_dir)
  ref_map = arrangement.get_sub_path_to_reference_map(ref_dir=static_root)
  
  for chapter_index, chapter_file in enumerate(md_files_in):
    (metadata, content) = chapter_file.read()
    chapter_index = chapter_index + 1
    pairs = details_helper.get_details(content=content)

    details = [pair[1] for pair in pairs]
    for index, detail in enumerate(details):
      id = detail.title.split("-")[-1].strip().split(",")[0].strip()
      id = sanscript.transliterate(id, _from=sanscript.DEVANAGARI, _to=sanscript.IAST)
      id = int(id)
      if id != index + 1:
        logging.warning(f"Mismatched index at {chapter_file.file_path} - {id} vs {index  +1}")
        break
      id = f"{chapter_index:02d}/{id:02d}"
      md_file_dest = MdFile(file_path=ref_map[id])
      # logging.info(md_file_dest)
      md_file_dest.replace_content_metadata(new_content=lambda c: f"{c}\n\n{detail.to_md_html()}\n", dry_run=False)


def combine_shAnkara():
  static_root = os.path.join(STATIC_ROOT, "saMskRtam/shankaraH")
  subpaths = ["mUlam", "english/gambhIrAnandaH", "hindI/harikRShNadAsaH", "AnandagiriH", "nIlakaNThaH", "dhanapatiH", "madhusUdana-sarasvatI"]
  subpaths = [os.path.join(static_root, x) for x in subpaths]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_root, "sarvASh_TIkAH"), mode="append", dry_run=False)


def combine_rAmAnujaH():
  static_root = os.path.join(STATIC_ROOT, "saMskRtam/rAmAnujaH")
  subpaths = ["mUlam", "venkaTanAthaH", "english/AdidevAnandaH",]
  subpaths = [os.path.join(static_root, x) for x in subpaths]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_root, "sarvASh_TIkAH"), mode="append", dry_run=False)

def combine_madhvaH():
  static_root = os.path.join(STATIC_ROOT, "saMskRtam/madhvaH")
  subpaths = ["mUlam", "jayatIrthaH"]
  subpaths = [os.path.join(static_root, x) for x in subpaths]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_root, "sarvASh_TIkAH"), mode="append", dry_run=False)

def combine_vallabhaH():
  static_root = os.path.join(STATIC_ROOT, "saMskRtam/vallabhaH")
  subpaths = ["mUlam", "puruShottamaH"]
  subpaths = [os.path.join(static_root, x) for x in subpaths]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_root, "sarvASh_TIkAH"), mode="append", dry_run=False)


def combine_abhinavaH():
  static_root = os.path.join(STATIC_ROOT, "saMskRtam/abhinava-guptaH")
  subpaths = ["mUlam", "english/shankaranArAyaNaH"]
  subpaths = [os.path.join(static_root, x) for x in subpaths]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_root, "sarvASh_TIkAH"), mode="append", dry_run=False)


def combine_english():
  static_root = os.path.join(STATIC_ROOT, "english")
  subpaths = ["AdidevAnandaH", "gambhIrAnandaH", "purohitasvAmI", "shankaranArAyaNaH", "shivAnandaH/anuvAdaH", "shivAnandaH/TIkA", ]
  subpaths = [os.path.join(static_root, x) for x in subpaths]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_root, "sarvASh_TIkAH"), mode="append", dry_run=False)


def combine_hindI():
  static_root = os.path.join(STATIC_ROOT, "hindI")
  subpaths = ["rAmasukhadAsaH/anuvAdaH", "rAmasukhadAsaH/TIkA", "chinmayAnandaH", "tejomayAnandaH/anuvAdaH", ]
  subpaths = [os.path.join(static_root, x) for x in subpaths]
  combination.combine_to_details(source_paths_or_content=subpaths, dest_path=os.path.join(static_root, "sarvASh_TIkAH"), mode="append", dry_run=False)


def fix_muula():
  pass
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/mahAbhAratam/static/vyAsaH/shlokashaH/06-bhIShma-parva/03-bhagavad-gItA-parva/saMskRtam/mUlam", content_transformer=lambda c, *args, **kwargs: details_helper.wrap_into_detail(content=c, title="मूलम् - प्रसिद्धम्", attributes_str=" open"))



if __name__ == '__main__':
  pass
  # combine_shAnkara()
  # combine_rAmAnujaH()
  # combine_madhvaH()
  # combine_vallabhaH()
  # combine_abhinavaH()
  # combine_english()
  # combine_hindI()
  # import_bellamkonda()
  fix_muula()