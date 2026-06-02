import glob
import json

from doc_curation.md import library
from doc_curation.md.content_processor import details_helper
from doc_curation.md.content_processor.details_helper import Detail
from doc_curation.md.file import MdFile


DEST_PATH = "/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/aNNam-bhaTTaH_tarka-sangrahaH/kalyANa-prastutiH"


def find_section_by_id(data_list, section_id):
  """
  Finds a section in a list of dictionaries based on its sectionId.

  Args:
    data_list: A list of dictionaries, where each dictionary is a section.
    section_id: The integer ID of the section to find.

  Returns:
    The dictionary of the matching section, or None if no match is found.
  """
  for section in data_list:
    if section.get('sectionId') == section_id:
      return section
  return None


def dump_mUla():
  with open("/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/aNNam-bhaTTaH_tarka-sangrahaH/kalyANa-prastutiH.json", 'r', encoding='utf-8') as f:
    data = json.load(f)
  parts = []
  for section in data:
    parts.extend([f"## {section['sectionId']:02d} {section['title']}", Detail(title=f"मूलम् - {section['title']} - {section['sectionId']}", content=section['content']).to_md_html(), Detail(title=f"Tags - {section['sectionId']}", content=", ".join(section['tags'])).to_md_html()])
  
  content = "\n\n".join(parts)
  md_file = MdFile(file_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/aNNam-bhaTTaH_tarka-sangrahaH/kalyANa-prastutiH.md")
  md_file.dump_to_file(metadata={"title": "कल्याण-प्रस्तुतिः"}, content=content, dry_run=False)


def count_comments():
  library.apply_function(fn=MdFile.transform, dir_path=DEST_PATH, content_transformer=details_helper.count_details)


def add_commentary(file_path, title):
  with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
  for section in data:
    detail = Detail(title=f"{title} - {section['title']}", content=section['content'].replace("\n", "  \n"))
    target_id = section['tarkasangraha_sectionId']
    file_path = glob.glob(f"{dest_path}/{target_id:02d}_*.md")[0]
    md_file = MdFile(file_path=file_path)
    [_, content] = md_file.read()
    if detail.title not in content:
      md_file.replace_content_metadata(new_content=f"{content}\n\n{detail.to_md_html()}", dry_run=False)


# --- Main execution block ---
if __name__ == "__main__":
  # dump_mUla()
  # add_commentary(file_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/aNNam-bhaTTaH_tarka-sangrahaH/TIkA-mUlAni/sa/tarkasangrahadeepika_mapping.json", title="दीपिका")
  # add_commentary(file_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/aNNam-bhaTTaH_tarka-sangrahaH/TIkA-mUlAni/sa/varadAchArya-AlokaH/mUlam.json", title="वरदाचार्य आलोके")
  pass
  # add_commentary(file_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/aNNam-bhaTTaH_tarka-sangrahaH/TIkA-mUlAni/sa/apariShkRtam/govardhanaH_nyAyabodhinI/mUlam.json", title="गोवर्धन-न्यायबोधिनी")
  # add_commentary(file_path="/home/vvasuki/gitland/vishvAsa/AgamaH/content/AryaH/hinduism/branches/nyAya-vaisheShike/aNNam-bhaTTaH_tarka-sangrahaH/TIkA-mUlAni/sa/sarvasva.json", title="कुरुगण्टि-श्रीनिवास-दीपिका-सर्वस्वम्")
  count_comments()