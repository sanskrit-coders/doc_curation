import logging
import os

import regex

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import include_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from indic_transliteration import sanscript

PATTERN_RK = "\n[^#<>\[\(][^॥]+?॥\s*[०-९\d-:]+\s*॥.*?(?=\n|$)"
PATH_ALL_SAMHITA = "/home/vvasuki/vishvAsa/vedAH/content/sAma/kauthumam/saMhitA/"


def title_maker(text_matched, index, file_title):
  title_id = regex.search("॥\s*([०-९\d-:]+)\s*॥", text_matched).group(1)
  title_id = title_id.replace(":", "_")
  title = content_processor.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                            title_id=title_id)
  return title


def migrate_and_include_shlokas():

  def replacement_maker(text_matched, dest_path):
    return include_helper.vishvAsa_include_maker(dest_path, h1_level=2, title="FILE_TITLE")

  def destination_path_maker(title, original_path):
    return include_helper.static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": "", "saMhitA": "saMhitA/mUlam"}, use_preexisting_file_with_prefix=False)

  library.apply_function(fn=include_helper.migrate_and_replace_texts, text_patterns=[PATTERN_RK], dir_path=PATH_ALL_SAMHITA, destination_path_maker=destination_path_maker, title_maker=title_maker, replacement_maker=replacement_maker, dry_run=False)


def read_RV_map():
  rv_muula = "/home/vvasuki/vishvAsa/vedAH/static/Rk/shAkalam/saMhitA/mUlam"
  md_files = library.get_md_files_from_path(dir_path=rv_muula, file_pattern="**/[0-9][0-9]*.md")
  rv_map = {}
  for md_file in md_files:
    (metadata, content) = md_file.read()
    text = content_processor.get_comparison_text(text=content)
    rv_map[text] = md_file.file_path
  logging.info("Got RV map with %d items", len(md_files))
  return rv_map


def proximal_RV_text(saama_text, rv_map):
  import editdistance
  rv_texts = list(rv_map.keys())
  scores = [editdistance.eval(saama_text, rv_text) for rv_text in rv_texts]
  min_score = min(scores)
  match = rv_texts[scores.index(min_score)]
  normalized_score = round(min_score/len(saama_text), 3)
  return (match, rv_map[match], normalized_score)


def link_rv_texts():
  saama_muula = "/home/vvasuki/vishvAsa/vedAH/static/sAma/kauthumam/saMhitA/mUlam"
  muula_md_files = library.get_md_files_from_path(dir_path=saama_muula, file_pattern="**/[0-9][0-9]*.md")
  rv_map = read_RV_map()
  unmatched_files = []
  for muula_md in muula_md_files:
    (metadata, saama_content) = muula_md.read()
    saama_text = content_processor.get_comparison_text(text=saama_content)
    saama_text = regex.sub("(.+?)॥.+", "\\1", saama_text)
    (rv_text, rv_muula_path, score) = proximal_RV_text(saama_text=saama_text, rv_map=rv_map)
    logging.info("Edit distance: %s, %s to %s", score, os.path.basename(muula_md.file_path), os.path.basename(rv_muula_path))
    if score > 0.25:
      logging.info("No match between %s and %s", rv_text, saama_text)
      unmatched_files.append(str(muula_md.file_path))
      continue
    dest_path = str(muula_md.file_path).replace("mUlam", "vishvAsa-prastutiH")
    dest_md = MdFile(file_path=dest_path)
    rv_url = str(rv_muula_path).replace("/home/vvasuki/vishvAsa/vedAH/static", "/vedAH").replace("mUlam", "vishvAsa-prastutiH")
    metadata["similar_rv"] = rv_url
    metadata["edit_distance_to_rv"] = score
    (_, dest_content) = muula_md.read()
    dest_content = regex.sub("<div[\s\S]]+</div>", "", dest_content)
    content = "%s\n\n%s" % (dest_content, library.get_include(url=rv_url, h1_level=2, classes=None, title="विश्वास-शाकल-प्रस्तुतिः"))
    dest_md.dump_to_file(metadata=metadata, content=content, dry_run=False)

  unmatched_files_md = MdFile(file_path=os.path.join(os.path.dirname(saama_muula), "vishvAsa-prastutiH/unmatched.md"))
  unmatched_files_md.dump_to_file(metadata={"title": "Unmatched files"}, content="\n".join(sorted(unmatched_files)), dry_run=False)


if __name__ == '__main__':
  pass
  # migrate_and_include_shlokas()
  # library.apply_function(fn=metadata_helper.set_title_from_filename, dir_path=PATH_ALL_SAMHITA, dry_run=False)
  link_rv_texts()
