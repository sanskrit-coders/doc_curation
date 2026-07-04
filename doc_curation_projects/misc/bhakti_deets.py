import os

from curation_utils import scraping
from doc_curation.md import library
from doc_curation.md.content_processor import section_helper, space_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import arrangement


def dump_md(url, dest_path, title="UNKNOWN"):
  (soup, result) = scraping.get_soup(url=url)
  content = f"Source: [TW]({url})\n\n{result.text}"
  content = section_helper.convert_heading_style(text=content)
  content = space_helper.markdownify_newlines(text=content)
  md_file = MdFile(dest_path)
  md_file.dump_to_file(metadata={"title": title}, content=content, dry_run=False)
  arrangement.fix_index_files(os.path.dirname(dest_path), overwrite=False)


def get_all():
  pass
  # dump_md(url="https://repository.bhaktideets.org/Publications/EngSmsk/2025/ShriVishnuPuraana-Amsha6_with_Samskrta_Vivarana.txt", dest_path="/home/vvasuki/gitland/vishvAsa/purANam_vaiShNavam/content/viShNu-purANam/mAdhvAH/koDava-hari-kumAraH.md", title="कॊडव-हरि-कुमारः")
  # dump_md(url="https://repository.bhaktideets.org/Publications/EngSmsk/2024/Vaishnava-Mantra-Shloka-Stuti-Sangraha.txt", dest_path="/home/vvasuki/gitland/vishvAsa/mAdhvam/content/kriyA/koDava-hari-kumAra-sangrahaH.md", title="कॊडव-हरि-कुमार-सङ्ग्रहः")
  dump_md(url="https://repository.bhaktideets.org/Publications/EngSmsk/2026/Mahaabhaarata-Saara.txt", dest_path="/home/vvasuki/gitland/vishvAsa/mahAbhAratam/content/meta/mAdhvam/sAra-extracts.md", title="सारः (Extracts)")




if __name__ == '__main__':
  pass
  get_all()