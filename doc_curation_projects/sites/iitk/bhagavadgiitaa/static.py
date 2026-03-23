import os.path
from doc_curation.md.library import combination

STATIC_ROOT = "/home/vvasuki/gitland/vishvAsa/mahAbhAratam/static/vyAsaH/shlokashaH/06-bhIShma-parva/03-bhagavad-gItA-parva"

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


if __name__ == '__main__':
  pass
  # combine_shAnkara()
  # combine_rAmAnujaH()
  # combine_madhvaH()
  # combine_vallabhaH()
  # combine_abhinavaH()
  # combine_english()
  # combine_hindI()