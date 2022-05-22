import glob
import logging
import os
import shutil
from collections import OrderedDict

from doc_curation.md.content_processor.details_helper import Detail
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation_projects.puraaNa import raamaayana
from doc_curation_projects.puraaNa.raamaayana import get_adhyaaya_id
from indic_transliteration import sanscript


def get_sarga_id_to_path(base_dir_ref, sarga_identifier=get_adhyaaya_id):
  paths_ref = sorted(glob.glob(base_dir_ref + "/**/*.md", recursive=True))
  sarga_id_to_path = OrderedDict()

  for p in paths_ref:
    sarga_id = sarga_identifier(p)
    if sarga_id is not None:
      sarga_id_to_path[sarga_id] = p
  return sarga_id_to_path

def fix_metadata_and_paths(base_dir, base_dir_ref, sarga_identifier=get_adhyaaya_id, dry_run=False):

  paths = sorted(glob.glob(base_dir + "/**/*.md", recursive=True))
  paths = [path for path in paths if os.path.basename(path) != "_index.md" and "0/" not in path]
  sarga_id_to_path = get_sarga_id_to_path(base_dir_ref=base_dir_ref, sarga_identifier=sarga_identifier)
  for p in paths:
    sarga_id = sarga_identifier(p)
    ref_md_path = sarga_id_to_path.get(sarga_id, None)
    if ref_md_path is None:
      logging.info(f"Could not find ref for {p}")
      continue
    dest_path = ref_md_path.replace(base_dir_ref, base_dir)
    logging.info("Moving to %s from %s", dest_path, p)
    if not dry_run:
      os.makedirs(os.path.dirname(dest_path), exist_ok=True)
      shutil.move(p, dest_path)
      ref_md_file = MdFile(file_path=ref_md_path)
      [metadata, _] = ref_md_file.read()
      md_file = MdFile(file_path=dest_path)
      [_, content] = md_file.read()
      md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)



def update_from_spreadsheet_data(doc_data, base_dir, dry_run=False):
  sarga_id_to_path = get_sarga_id_to_path(base_dir_ref=base_dir)
  for adhyaaya_id, file_path in sarga_id_to_path.items():
    md_file = MdFile(file_path=file_path)
    (metadata, content) = md_file.read()
    metadata["title"] = doc_data.get_value(id=adhyaaya_id, column_name="साङ्क-शीर्षिका")
    if metadata["title"] is None:
      logging.info(f"Skipping {file_path}")
      continue
    metadata["title"] = sanscript.transliterate(data=metadata["title"], _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
    if "<summary>वाचनम्</summary>" not in content:
      audio_url = doc_data.get_value(id=adhyaaya_id, column_name="Audio url")
      audio_tag = '<div class="audioEmbed"  caption="श्रीराम-हरिसीताराममूर्ति-घनपाठिभ्यां वचनम्" src="%s"></div>' % (audio_url)
      audio_detail = Detail(type="वाचनम्", content=audio_tag)
      content = f"{audio_detail.to_html(attributes_str='open')}\n\n{content}"
    md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)
    metadata_helper.set_filename_from_title(md_file=md_file, dry_run=dry_run)