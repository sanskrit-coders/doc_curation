import os
import textwrap

import doc_curation.md.content_processor.include_helper
from doc_curation.md.content_processor import include_helper
from doc_curation.utils import text_utils
from doc_curation.md import library
from doc_curation.md.file import MdFile
from indic_transliteration import sanscript

from doc_curation_projects.veda.yajuH.vaajasaneyi.maadhyandina import samhitaa

static_dir_base = "/home/vvasuki/gitland/vishvAsa/vedAH_yajuH/static/vAjasaneyam/mAdhyandinam/saMhitA"
content_dir_base = static_dir_base.replace("static/", "content/")
ref_dir = os.path.join(static_dir_base, "mUlam")




def dump(dry_run, start_id=None):
  for chapter_id in range(1, 41):
    if start_id is not None and chapter_id < start_id:
      continue
      
    chapter_md = textwrap.dedent("""
    %s
    """ % (
      get_include("sarvASh_TIkAH", chapter_id=chapter_id, ref_file_path=os.path.join(ref_dir, f"{chapter_id:02d}", "_index.md"), h1_level=2)))

    for mantra_path in samhitaa.get_mantras(chapter_id=chapter_id):
      mantra_md = MdFile(file_path=mantra_path)
      (metadata, content) = mantra_md.read()
      mantra_details = "\n\n## %s" % (metadata["title"])
      mantra_details += "\n%s" % get_include("vishvAsa-prastutiH", chapter_id=chapter_id,                                         ref_file_path=mantra_path, h1_level=3)
      mantra_details += "\n%s" % get_include("mUlam", chapter_id=chapter_id, ref_file_path=mantra_path,
                                         classes=["collapsed"], h1_level=3)
      mantra_details += "\n%s" % Include("sarvASh_TIkAH", chapter_id=chapter_id, ref_file_path=mantra_path, classes=["collapsed"], h1_level=3).to_html_str()

      # dump_content(metadata=title_only_metadata, content=mantra_details, chapter_id=chapter_id, mantra_id=mantra_id, base_dir=content_dir_base, destination_dir="sarva-prastutiH", dry_run=dry_run)

      chapter_md = chapter_md + mantra_details
    md_file_chapter = MdFile(file_path=os.path.join(content_dir_base, "sarva-prastutiH", f"{chapter_id:02d}.md"))
    title_chapter = sanscript.transliterate(f"{chapter_id:02d}", sanscript.IAST, sanscript.DEVANAGARI)
    md_file_chapter.dump_to_file(metadata={"title": title_chapter}, content=chapter_md, dry_run=dry_run)


def get_include(include_type, chapter_id, ref_file_path, h1_level, field_names=None, classes=None, title=None):
  ref_file_path = ref_file_path.replace("mUlam", include_type)
  if title is None:
    title = sanscript.transliterate(include_type.replace("_", " "), _from=sanscript.OPTITRANS, _to=sanscript.DEVANAGARI)
  if not os.path.exists(ref_file_path):
    return ""
  return include_helper.Include(field_names=field_names, classes=classes, title=title,
                                                                      url=os.path.join("/vedAH_yajuH/vAjasaneyam/mAdhyandinam/saMhitA/", include_type, f"{chapter_id:02d}", os.path.basename(ref_file_path).to_html_str()), h1_level=h1_level)


if __name__ == '__main__':
  # dump(dry_run=False)
  include_helper.prefill_includes(dir_path=os.path.join(content_dir_base, "sarva-prastutiH"))

  # md.library.fix_index_files(content_dir_base)
