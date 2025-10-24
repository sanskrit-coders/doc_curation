import logging
import os

import editdistance
import regex

from doc_curation.utils import sanskrit_helper, text_utils
from curation_utils import file_helper
from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper, footnote_helper, details_helper, section_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper, combination, arrangement
from doc_curation_projects.kaavya import divyaprabandha
from indic_transliteration import sanscript

def devanaagarify(dir_path, source_script):
  def content_transformer(c, m):
    # c = footnote_helper.define_footnotes_near_use(c)
    c = content_processor.transliterate(text=c, source_script=source_script)
    c = sanskrit_helper.fix_lazy_anusvaara(c)
    c = regex.sub(r"\|\|", "॥", c)
    c = regex.sub(r"\|", "।", c)
    return c
  
  library.apply_function(
    fn=MdFile.transform, dir_path=dir_path, 
    content_transformer=content_transformer,
    metadata_transformer=None,
  dry_run=False)


def _undo_structuring(dir_path):
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"\n</?details.+\n+","##.+"], replacement="\n\n")
  

def from_garani(dir_path):
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.merge_successive(content=c,  title_filter="गरणि.*"))

  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["(?<=\n|^)## "], replacement="### ")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["(?<=\n|^)### ०१"], replacement="## \n### ०१")

  # library.apply_function(fn=section_helper.autonumber, dir_path=dir_path, start_index=1)
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.autonumber_details(content=c))
  # library.apply_function(fn=MdFile.split_to_bits, dir_path=dir_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, title_index_pattern=None) # 
  # library.apply_function(fn=section_helper.add_init_words_to_section_titles, dir_path=dir_path, dry_run=False, num_words=2)

  # return

  # TODO: Manually ensure stray &.t, < and > characters don't exist, lest the mess with details tag processing.
  
  
  # devanaagarify(dir_path, source_script=sanscript.KANNADA)
  # library.apply_function(dir_path=dir_path, fn=metadata_helper.set_title_from_filename, maybe_use_dravidian_variant="yes", dry_run=False)
  # return 
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["\n\n\n+"], replacement="\n\n")

  ## TODO - Manually section - using the below?
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["^ತಿರುವಾಯ್.+(ೞಿ|ಳಿ)\s*$"], replacement="")
  # library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)\\\*\\\*\\\*\\\*.+"], replacement="## ")
  # Check shataka separation manually TODO
  library.apply_function(fn=MdFile.split_to_bits, dir_path=dir_path, frontmatter_type=MdFile.TOML, dry_run=False, source_script=sanscript.DEVANAGARI, title_index_pattern=None) # 

  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)[०-९]+\..+\n+(?=[०-९]+\.)"], replacement="")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[" (ऱ|न्द)"], replacement=r"\1")


  # return

  _undo_structuring(dir_path)
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=["(?<=\n)(.+=.+)(?=\n)"], replacement=r"\n<details><summary>गरणि-प्रतिपदार्थः</summary>\n\n\1\n</details>\n")
  # TODO: Note that the above will fail in case of lines split by page breaks. That will need to be resolved manually.
  
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=</details>\n)\s*(\S.+?)(?=\n|$)"], replacement=r"\n<details><summary>गरणि-गद्यानुवादः</summary>\n\n\1\n</details>\n\n")
  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=</details>\n)\s*(\S[^<#]+?)\s*(?=\n[०-९]+\.|$|\nअडिय *नड)"], replacement=r"\n<details><summary>गरणि-विस्तारः</summary>\n\n\1\n</details>\n\n")
  # TODO: Look for गरणि-विस्तारः.+[^<]+?\\\([०-१\d] to find missing/ misplaced गरणि-गद्यानुवादः sections?

  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n)अडिय *नडॆ[ \-]+(.+)(?=\n)"], replacement=r"\n<details><summary>गरणि-अडियनडे</summary>\n\n\1\n</details>\n")

  def _make_viprastuti(match):
    text = match.group(2)
    text = regex.sub(r"\n\s*", "  \n", text)
    detail_vi  = details_helper.Detail(title="विश्वास-प्रस्तुतिः", content=text)
    detail_mu = details_helper.Detail(title="मूलम्", content=text)
    index = sanscript.transliterate(match.group(1), _from=sanscript.DEVANAGARI, _to=sanscript.IAST)
    index = "%02d" % int(index)
    index = sanscript.transliterate(index, _from=sanscript.IAST, _to=sanscript.DEVANAGARI)
    return f"## {index}\n{detail_vi.to_md_html()}\n\n{detail_mu.to_md_html()}\n\n"

  library.apply_function(fn=content_processor.replace_texts, dir_path=dir_path, patterns=[r"(?<=\n|^)([०-९]+)\.\s*(\S[^<]+?)\s*(?=<details><summary>गरणि-प्रतिपदार्थः)"], replacement=_make_viprastuti)

  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.merge_successive(content=c,  title_filter="गरणि.*"))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.autonumber_details(content=c))
  library.apply_function(fn=section_helper.add_init_words_to_section_titles, dir_path=dir_path, dry_run=False, num_words=2)
  library.apply_function(fn=metadata_helper.add_init_words_to_title, dir_path=dir_path, target_title_length=30, num_words=2, script=sanscript.DEVANAGARI, dry_run=False)

  pass


def insert_garani(dir_path):
  # library.apply_function(fn=details_helper.interleave_from_file, dir_path=dir_path, source_file=lambda x: x.replace("_index", "garaNi"), detail_title=None, dest_pattern= "<details.+?summary>विश्वास-प्रस्तुतिः *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>मूलम् *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)
  # library.apply_function(fn=details_helper.interleave_from_file, dir_path=dir_path, source_file=lambda x: x.replace("_index", "garaNi"), detail_title=None, dest_pattern= "<details.+?summary>मूलम् *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>गरणि-विस्तारः *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)
  # library.apply_function(fn=details_helper.interleave_from_file, dir_path=dir_path, source_file=lambda x: x.replace("_index", "garaNi"), detail_title=None, dest_pattern= "<details.+?summary>मूलम् *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>गरणि-प्रतिपदार्थः *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)
  library.apply_function(fn=details_helper.interleave_from_file, md_files=dir_path, source_file=lambda x: x.replace("_index", "garaNi"), detail_title=None, dest_pattern= r"<details.+?summary>गरणि-प्रतिपदार्थः *- *(\S+)</summary>[\s\S]+?</details>\n", source_pattern= r"<details.+?summary>गरणि-गद्यानुवादः *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)
  

def insert_uv(dest_dir):
  # library.apply_function(fn=details_helper.interleave_from_file, dir_path=dest_dir, source_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/mUlam_UV.md", detail_title=None, dest_pattern= "<details.+?summary>विश्वास-प्रस्तुतिः *- *DP_([०-९]+).*?</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>मूलम् \(विभक्तम्\) *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)

  # details_helper.interleave_from_file(md_files=dest_dir, source_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/mUlam_UV.md", detail_title=None, dest_pattern= "<details.+?summary>मूलम् *- *DP_([०-९]+).*?</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>अर्थः \(UV\) *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)

  # details_helper.interleave_from_file(md_files=dest_dir, source_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/mUlam_UV.md", detail_title=None, dest_pattern= "<details.+?summary>मूलम् *- *DP_([०-९]+).*?</summary>[\s\S]+?</details>\n", source_pattern= "<details.+?summary>Info *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)


  details_helper.interleave_from_file(md_files=MdFile("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/mUlam_UV.md"), source_file="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/synonyms_ta.md", detail_title=None, dest_pattern= r"<details.+?summary>मूलम् \(UV\) *- *([०-९]+).*?</summary>[\s\S]+?</details>\n", source_pattern= r"<details.+?summary>प्रतिपदार्थः \(UV\) *- *(\S+)</summary>[\s\S]+?</details>\n", dry_run=False)


def set_id(dir_path):
  id_mUla = get_madurai_mUla()

  def match_id(content):
    best_id = None
    best_dist = 1
    def normalize_text(text):
      text = regex.sub(r"\s+", "", text)
      text = regex.sub(r"ऩ", "न", text)
      return text
    content = normalize_text(content)
    for id_, text in id_mUla.items():
      dist = text_utils.normalized_edit_distance(normalize_text(text), content, strip_svaras=False)
      if dist < best_dist: 
        best_id = id_
        best_dist = dist
    return best_id, best_dist

  
  def id_to_tag(detail_tag, *args, **kwargs):
    detail = details_helper.Detail.from_soup_tag(detail_tag)
    (id_, dist) = match_id(detail.content)
    if dist > 0.3:
      logging.warning(f"Could not match id for {detail.content.replace('\n', '  ')} - score {dist} for {id_mUla.get(id_, '')}")
      return
    title = detail_tag.select_one("summary").text
    title_parts = regex.split(" *- *", title)
    title = ' - '.join([title_parts[0], id_] + title_parts[1:])
    detail_tag.select_one("summary").string = title
    
    
  def set_ids_for_file(file_path):
    md_file = MdFile(file_path=file_path)
    (metadata, content) = md_file.read()
    
    # content = details_helper.transform_detail_tags_with_soup(title_pattern="मूलम्.*", content=content, transformer=id_to_tag, metadata=metadata)
    content = details_helper.set_id_from_neighbor(target_title_pattern="विश्वास-प्रस्तुतिः.*", seek_before=False, content=content, )
    content = details_helper.set_id_from_neighbor(target_title_pattern="गरणि-.*", seek_before=True, content=content, )
    md_file.replace_content_metadata(new_content=content)
  
  library.apply_function(fn=set_ids_for_file, dir_path=dir_path, file_pattern="**/*.md")


def get_madurai_mUla():
  mUla_md = MdFile(
    file_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/mUlam.md")
  (_, content_mUla) = mUla_md.read()
  matches = regex.finditer(r"(?<=\n)([०-९]+): +\n((.*\S.+\n)+)", content_mUla, overlapped=False)
  id_mUla = {f"DP_{match.group(1)}": match.group(2) for match in matches}
  logging.info(f"Got {len(id_mUla)} mUla entries")
  return id_mUla


def update_content(dir_path):
  id_mUla = get_madurai_mUla()
  def update(detail_tag, *args, **kwargs):
    detail = details_helper.Detail.from_soup_tag(detail_tag)
    id_match = regex.findall(r"(DP_\S+)", detail.title)
    if len(id_match) == 1:
      id_ = id_match[0]
      if "+++(" in detail.content:
        logging.warning(f"Skipping {detail.title} - has +++")
        return 
      details_helper.detail_content_replacer_soup(detail_tag=detail_tag, replacement=id_mUla[id_])
    else:
      logging.warning(f"Could not match id for {detail.title}")
  
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.transform_detail_tags_with_soup(title_pattern="मूलम्.*|विश्वास-प्रस्तुतिः.*", content=c, transformer=update, metadata=m))


def insert_hart(dir_path):
  id_to_hart = {}
  def get_hart(content):
    matches = regex.finditer(r"(?<=\n)(\d+)\. (([^\d\n]*\S.+\n){2,}?)(?=\n\d|$)", content)
    for match in matches:
      text = match.group(2)
      text = regex.sub(r"\n\s*", "  \n", text)
      text = regex.sub(r"\.", ":", text)
      id_dev = content_processor.transliterate(match.group(1), source_script=sanscript.IAST, dest_script=sanscript.DEVANAGARI)
      id_to_hart[f"DP_{id_dev}"] = text
    return None
  
  library.apply_function(fn=MdFile.transform, dir_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/hart", content_transformer=lambda c, m: get_hart(c))

  logging.info(f"Got {len(id_to_hart)} harts")
  
  def neighbor_maker(detail):
    id_ = regex.findall(r"(DP_\S+)", detail.title)[0]
    if id_ in id_to_hart:
      new_detail = details_helper.Detail(title=f"Hart - {id_}", content=id_to_hart[id_])
      return new_detail.to_soup()
    else:
      return None

  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda c, m: details_helper.transform_detail_tags_with_soup(title_pattern="मूलम्.*DP_.+", content=c, metadata=m, transformer=details_helper.adjascent_inserter, neighbor_maker=neighbor_maker))


def reorg_comments(base_dir, dry_run=False):
  divyaprabandha.move_files_increment_dir(base_dir=base_dir, dry_run=dry_run)
  arrangement.fix_index_files(os.path.dirname(base_dir), dry_run=dry_run)



if __name__ == '__main__':
  pass
  # insert_garani("/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/4k-divya-prabandha/sarva-prastutiH/02_tiruppAvai_aNDaL_474_-503/_index.md")
  # from_garani("/home/vvasuki/gitland/vishvAsa/bhAShAntaram/content/tamiL/padyam/4k-divya-prabandha/sarva-prastutiH/20_tiruveLHuku.Rh.Rhirukkai_tirumangai-ALHvAr_2672")
  # set_id("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH")
  # update_content("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH")
  # insert_hart("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH")
  # insert_uv("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH")
  # reorg_comments("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/10_pEriya_tirumOLHi_tirumangai-ALHvAr_948-2031/aNNangarAchAryaH/padav-urai", dry_run=False)  
  # reorg_comments("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/10_pEriya_tirumOLHi_tirumangai-ALHvAr_948-2031/aNNangarAchAryaH/viLakkav-urai", dry_run=False)
  # reorg_comments("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/aNNangarAchAryaH/padav-urai", dry_run=False)
  # reorg_comments("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/aNNangarAchAryaH/viLakkav-urai", dry_run=False)

  # reorg_comments("/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/drAviDam/4k-divya-prabandha/sarva-prastutiH/23_tiruvAymoLHi_-_nammALHvAr_2791-3892/bhagavad-viShayam/aNNangarAchAryaH")
