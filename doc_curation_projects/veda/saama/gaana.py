from doc_curation.md import library
import os.path
from doc_curation.md import content_processor
from doc_curation.md.content_processor import include_helper, details_helper
from doc_curation.md.file import MdFile

import regex
from indic_transliteration import sanscript
from doc_curation_projects.veda import saama




def extract_gaana_1rk(md_file, dest_dir, dry_run=False):
  (metadata, content) = md_file.read()
  matches = regex.finditer(r"(?<=^|\n)([०-९]+)-([०-९])।[\s\S]+?(?=\s*([०-९]+-[०-९]|#|\[\[)|$)", content)
  (_, Rk_num_to_name_map) = saama.get_Rk_id_to_name_map_from_muulam()
  for match in matches:
    rk_id = int(sanscript.transliterate(match.group(1), _from=sanscript.DEVANAGARI, _to=sanscript.IAST))
    rk_id = f"{rk_id:04}"
    saama_id = int(sanscript.transliterate(match.group(2), _from=sanscript.DEVANAGARI, _to=sanscript.IAST))


    dest_path = os.path.join(dest_dir, os.path.basename(md_file.file_path)[-3], f"{Rk_num_to_name_map[rk_id]}/{saama_id:02}.md")
    dump_saama(dest_path, match, rk_metadata, saama_id, dry_run)


    include_lines = ""
    if saama_id == 1:
      include_lines, rk_metadata = insert_yoni(Rk_num_to_name_map, [rk_id])
    include = include_helper.vishvAsa_include_maker(extra_attributes="open", file_path=dest_path, h1_level=6)
    include_lines += f"\n\n{include}"
    content = content.replace(match.group().strip(), include_lines)
  md_file.replace_content_metadata(new_content=content)


def extract_gaana_multi_rk(md_file, dest_dir, dry_run=False):
  (metadata, content) = md_file.read()
  matches = regex.finditer(r"(?<=^|\n)([०-९]+)-([०-९]+)-([०-९])।[\s\S]+?(?=\s*([०-९]+-[०-९]|#|\[\[)|$)", content)
  (_, Rk_num_to_name_map) = saama.get_Rk_id_to_name_map_from_muulam()
  for match in matches:
    rk_id_start = int(sanscript.transliterate(match.group(2), _from=sanscript.DEVANAGARI, _to=sanscript.IAST))
    rk_id_end = int(sanscript.transliterate(match.group(2), _from=sanscript.DEVANAGARI, _to=sanscript.IAST))
    rk_ids = [f"{rk_id:04}" for rk_id in range(rk_id_start, rk_id_end + 1)]
    saama_id = int(sanscript.transliterate(match.group(3), _from=sanscript.DEVANAGARI, _to=sanscript.IAST))


    dest_path = os.path.join(dest_dir, os.path.basename(md_file.file_path)[-3], f"{Rk_num_to_name_map[rk_ids[0]]}/{saama_id:02}.md")
    dump_saama(dest_path, match, rk_metadata, saama_id, dry_run)

    include_lines = ""
    if saama_id == 1:
      include_lines, rk_metadata = insert_yoni(Rk_num_to_name_map, rk_ids)
    include = include_helper.vishvAsa_include_maker(extra_attributes="open", file_path=dest_path, h1_level=6)
    include_lines += f"\n\n{include}"
    content = content.replace(match.group().strip(), include_lines)
  md_file.replace_content_metadata(new_content=content)


def dump_saama(dest_path, match, rk_metadata, saama_id, dry_run):
  saama_md = MdFile(file_path=dest_path)
  saama_content = details_helper.Detail(title="लिखितम्", content=match.group()).to_md_html(attributes_str="open")
  saama_md.dump_to_file(metadata={"title": f"{rk_metadata['title']} - {saama_id:02}"}, content=saama_content,
                        dry_run=dry_run)


def insert_yoni(Rk_num_to_name_map, rk_ids):
  include_lines = ""
  for rk_id in rk_ids:
    rk_path_vish = os.path.join(saama.SAMHITA_DIR_STATIC, f"vishvAsa-prastutiH/{Rk_num_to_name_map[rk_id]}.md")
    rk_md = MdFile(file_path=rk_path_vish)
    (rk_metadata, _) = rk_md.read()
    include = include_helper.vishvAsa_include_maker(file_path=rk_path_vish, classes=["collapsed"],
                                                    title="योनि-प्रस्तुतिः", h1_level=6)
    include_lines += f"\n\n{include}"
    include = include_helper.vishvAsa_include_maker(
      file_path=os.path.join(saama.SAMHITA_DIR_STATIC, f"sarvASh_TIkAH/{Rk_num_to_name_map[rk_id]}.md"),
      title="सर्वाष् टीकाः", classes=["collapsed"], h1_level=6)
    include_lines += f"\n\n{include}"
  return include_lines, rk_metadata


if __name__ == '__main__':
  pass
  # library.apply_function(fn=extract_gaana, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/kauthumam/prakRti-araNya-gAnAni/01_pUrvArchika-prakRti-gAnam", dry_run=False, dest_dir="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/static/kauthumam/prakRti-araNya-gAnAni/01_pUrvArchika-prakRti-gAnam")
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/kauthumam/prakRti-araNya-gAnAni/01_pUrvArchika-prakRti-gAnam", content_transformer=lambda x, y: include_helper.transform_includes_with_soup(x, y,transformer=include_helper.prefill_include))
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/kauthumam/prakRti-araNya-gAnAni/01_pUrvArchika-prakRti-gAnam", patterns=[r"h4"], replacement="h6")
  # library.apply_function(fn=content_processor.replace_texts, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/content/kauthumam/prakRti-araNya-gAnAni/01_pUrvArchika-prakRti-gAnam", patterns=[r"unfilled title=\"साम\""], replacement="unfilled")
  # library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/vedAH_sAma/static/kauthumam/prakRti-araNya-gAnAni/01_pUrvArchika-prakRti-gAnam", content_transformer=lambda c, m: details_helper.wrap_into_detail(c, title="लिखितम्", attributes_str="open"))
