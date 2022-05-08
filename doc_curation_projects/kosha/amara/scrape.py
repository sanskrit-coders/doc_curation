from curation_utils import scraping
from doc_curation.md.file import MdFile
from curation_utils.file_helper import get_storage_name
import os
import regex


def dump_varga(sa_name, kaanda_id, dest_dir, en_name=None):
  url = "http://amara.aupasana.com/varga?varga=%s" % sa_name
  soup = scraping.get_soup(url)
  content_div = soup.select_one("div.content")
  content = ""
  shloka_id = ""
  for child_tag in content_div.children:
    if isinstance(child_tag, str):
      continue
    if child_tag.attrs["class"][0] == "artha":
      shloka_id_old = shloka_id
      shloka_id = child_tag.attrs["id"].strip()
      if shloka_id_old == shloka_id:
        line_id = line_id + 1
      else:
        line_id = 1
      id = "%s.%d" % (shloka_id, line_id)
      text = child_tag.text.strip()
      text = regex.sub("\s+\n\s*", "  \n", text)
      if text == "":
        continue
      content += "\n+++(%s ॥%s॥)+++  \n" % (text, id)
    elif child_tag.attrs["class"][0] == "sloka":
      text = child_tag.select_one(".sloka-text").text.strip()
      id = child_tag.select("div")[1].text.strip()
      content += "%s ॥%s॥  \n" % (text, id)
  md_file = MdFile(file_path=os.path.join(dest_dir, "%s_%s.md" % (kaanda_id, get_storage_name(sa_name))))
  md_file.dump_to_file(metadata={"title": "%s %s" % (kaanda_id, sa_name), "title_en": en_name}, content=content, dry_run=False)


if __name__ == '__main__':
  from doc_curation_projects.kosha import amara
  for id, row in amara.varga_names.iterrows():
    dump_varga(sa_name=row["sa_name"], kaanda_id=id, dest_dir="/home/vvasuki/vishvAsa/sanskrit/content/koshaH/amarakoshaH", en_name=row["en_name"])