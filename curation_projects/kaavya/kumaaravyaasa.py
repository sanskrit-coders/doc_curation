import os
import regex

from curation_utils import file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

aux_source_list = ["vAchana", "gamaka-pariShat/gadya", "gamaka-pariShat/padArtha", "gamaka-pariShat/pAThAntara", "gamaka-pariShat/TippanI", "mUla"]
main_source_path = "/home/vvasuki/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata/vishvAsa-prastuti"

parva_to_data_id_map={"01_Adi": "01_Adi", "02_sabhA": "03", "03_araNya": "06", "04_virATa": "07", "05_udyOga": "10", "06_bhIShma": "08", "07_drONa": "02", "08_karNa": "09", "09_shalya": "05", "10_gadA": "04"}
parva_id_to_title_map = {}
for title in parva_to_data_id_map.keys():
  parva_id_to_title_map[title.split("_")[0]] = title


def get_doc_data(parva_num):
  from curation_utils.google import sheets
  doc_data = sheets.IndexSheet(spreadhsheet_id="1N9klz4d4sr5BRDlKU1jTCwZS9tC1s_h2HEvChIH5CAM", worksheet_name=str(parva_num), id_column="Id", google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json')
  return doc_data.get_df()


def dump_parva(parva_num, dir_path="/home/vvasuki/vishvAsa/kannaDa/static/padya/kumAra-vyAsa-bhArata", dry_run=False):
  doc_data = get_doc_data(parva_num=parva_num)
  for index, row in doc_data.iterrows():
    content = regex.sub("\n+", "  \n", row["P1_Padya"]).replace("||", "॥")
    title = content_processor.title_from_text(text=content, num_words=2, target_title_length=24, title_id="%02d" % int(row["Padya1"]), script=sanscript.KANNADA)
    metadata = {"title": title}
    file_subpath = "%02d/%02d/%s.md" % (parva_num, int(row["Sandhi_no"]), file_helper.get_storage_name(text=title))
    md_file_muula = MdFile(file_path=os.path.join(dir_path, "mUla", file_subpath))
    md_file_muula.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)

    md_file_gadya = MdFile(file_path=os.path.join(dir_path, "gamaka-pariShat/gadya", file_subpath))
    md_file_gadya.dump_to_file(metadata=metadata, content=regex.sub("\n+", "  \n", row["Gadya1"]), dry_run=dry_run)

    if row["Artha1"] != "":
      md_file_padaartha = MdFile(file_path=os.path.join(dir_path, "gamaka-pariShat/padArtha", file_subpath))
      md_file_padaartha.dump_to_file(metadata=metadata, content=regex.sub("\n+", "  \n", row["Artha1"]), dry_run=dry_run)

    if row["Patanthara1"] != "":
      md_file_paaThaantara = MdFile(file_path=os.path.join(dir_path, "gamaka-pariShat/pAThAntara", file_subpath))
      md_file_paaThaantara.dump_to_file(metadata=metadata, content=regex.sub("\n+", "  \n", row["Patanthara1"]), dry_run=dry_run)


    if row["Tippani1"] != "":
      md_file_tippanii = MdFile(file_path=os.path.join(dir_path, "gamaka-pariShat/TippanI", file_subpath))
      md_file_tippanii.dump_to_file(metadata=metadata, content=regex.sub("\n+", "  \n", row["Tippani1"]), dry_run=dry_run)
    pass


def make_sandhi_files(dest_path):
  library.make_per_src_folder_content_files(dest_path=dest_path, main_source_path=main_source_path, aux_source_list=aux_source_list, source_script=sanscript.KANNADA)
  pass
  

def fix_metadata_and_filename(dry_run=False):
  for aux_source in aux_source_list:
    metadata_helper.copy_metadata_and_filename(ref_dir=main_source_path, dest_dir=main_source_path.replace(os.path.basename(main_source_path), aux_source), dry_run=dry_run)
  

def make_audio_mds():
  mp3_path = "/home/vvasuki/Music/kumAra-vyAsa-bhArata_gaNaka-pariShat/mp3"
  sub_path_to_reference = library.get_sub_path_to_reference_map(ref_dir=main_source_path)
  target_dir = os.path.join(os.path.dirname(main_source_path), "vAchana")

  def id_maker(x):
    id = os.path.basename(x).replace(".mp3", "")
    id = id.replace("__", "/")
    id = library.get_sub_path_id(sub_path=id)
    return id

  import glob
  mp3_files = glob.glob(os.path.join(mp3_path, "*.mp3"))
  for mp3_file in mp3_files:
    id = id_maker(str(mp3_file))
    md_file_ref = sub_path_to_reference[id]
    (metadata, _) = md_file_ref.read()
    md_file = MdFile(file_path=md_file_ref.file_path.replace(main_source_path, target_dir))
    
    mp3_line = """<div class="audioEmbed"  src="https://archive.org/download/kumAra-vyAsa-bhArata_kaGaPa_with_metadata/%s" caption="ಗ-ಪ"></div>""" % os.path.basename(str(mp3_file))
    content = """%s""" % mp3_line
    md_file.dump_to_file(metadata=metadata, content=content, dry_run=False)


if __name__ == '__main__':
  # for parva_num in range(1,11):
  # for parva_num in [2]:
  #   dump_parva(parva_num=parva_num)
  make_sandhi_files(dest_path="/home/vvasuki/vishvAsa/kannaDa/content/padya/kumAra-vyAsa-bhArata")
  # make_audio_mds()
  # for x in aux_source_list + ["vishvAsa-prastuti"]:
  #   file_helper.rename_files(name_map=parva_id_to_title_map, path_prefix=os.path.join(os.path.dirname(main_source_path), x), dry_run=False)
  # fix_metadata_and_filename(dry_run=True)