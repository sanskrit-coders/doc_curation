import logging
import os
from pathlib import Path

import regex

from curation_utils import file_helper
from doc_curation.md.file import MdFile
from doc_curation.md.library import metadata_helper
from doc_curation.md.library.arrangement import get_md_files_from_path, migrate, fix_index_files
from indic_transliteration import sanscript


def import_md_recursive(source_dir, file_extension, source_format=None, dry_run=False):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  source_paths = sorted(Path(source_dir).glob("**/*." + file_extension))
  if source_format is None:
    source_format = file_extension
  for source_path in source_paths:
    md_path = str(source_path).replace("." + file_extension, ".md")
    md_path = file_helper.clean_file_path(md_path)
    if os.path.exists(md_path):
      logging.info("Skipping %s", md_path)
      continue
    logging.info("Processing %s to %s", source_path, md_path)
    md_file = MdFile(file_path=md_path, frontmatter_type=MdFile.TOML)
    md_file.import_with_pandoc(source_file=source_path, source_format=source_format, dry_run=dry_run)


def apply_function(fn, dir_path, file_pattern="**/*.md", file_name_filter=None, frontmatter_type="toml", start_file=None, silent_iteration=True, *args,
                   **kwargs):
  if not silent_iteration:
    logging.debug(list(Path(dir_path).glob(file_pattern)))
  if os.path.isfile(dir_path):
    logging.warning("Got a file actually. processing it!")
    md_files = [MdFile(file_path=dir_path)]
  else:
    md_files = get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern,
                                      file_name_filter=file_name_filter)
  start_file_reached = False

  logging.info("Processing %d files.", len(md_files))
  from tqdm import tqdm
  results_map = {}
  for md_file in tqdm(md_files):
    if start_file is not None and not start_file_reached:
      if str(md_file.file_path) != start_file:
        continue
      else:
        start_file_reached = True
    if md_file.get_title() is not None:
      # logging.info("Processing %s", md_file)
      result = fn(md_file, *args, **kwargs)
      results_map[md_file.file_path] = result
  return results_map


def get_audio_file_urls(md_files):
  # logging.debug(adhyaaya_to_mp3_map)
  logging.info("Getting audio file locations from %d files", len(md_files))
  for md_file in md_files:
    # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
    logging.debug(md_file.file_path)
    (metadata, md) = md_file.read()
    match = regex.match("<div class=\"audioEmbed\".+ src=\"([^\"]+)\"", md)
    if match:
      yield match.group(1)


def make_per_src_folder_content_files(dest_path, main_source_path, aux_source_list, source_script=sanscript.DEVANAGARI, h1_level=3, dry_run=False):
  md_files = get_md_files_from_path(dir_path=main_source_path, file_pattern="**/*.md")
  dest_file_path_to_source_paths = {}
  for md_file in md_files:
    dest_file_path = os.path.dirname(md_file.file_path).replace(main_source_path, dest_path) + ".md"
    main_source_paths = dest_file_path_to_source_paths.get(dest_file_path, [])
    main_source_paths.append(md_file.file_path)
    dest_file_path_to_source_paths[dest_file_path] = main_source_paths
  
  main_source_dir = os.path.basename(main_source_path)
  from doc_curation.md.content_processor import include_helper
  from doc_curation.md.library import metadata_helper
  for dest_file_path, main_source_paths in dest_file_path_to_source_paths.items():
    md_file = MdFile(file_path=dest_file_path)
    content = ""
    for main_source_path in main_source_paths:
      include_line = include_helper.vishvAsa_include_maker(file_path=main_source_path, h1_level=h1_level, classes=None, title="FILE_TITLE",)
      content = "%s\n\n%s" % (content, include_line)
      
      for aux_source in aux_source_list:
        aux_path = os.path.abspath(main_source_path.replace(main_source_dir, aux_source))
        if os.path.exists(aux_path):
          title = sanscript.transliterate(aux_source, _from=sanscript.OPTITRANS, _to=source_script, maybe_use_dravidian_variant=True)
          include_line = include_helper.vishvAsa_include_maker(file_path=aux_path, h1_level=h1_level+1, classes=["collapsed"], title=title,)
          content = "%s\n%s" % (content, include_line)

      md_file.dump_to_file(metadata={"title": metadata_helper.get_title_from_filename(file_path=md_file.file_path, transliteration_target=source_script)}, content=content, dry_run=dry_run)
  fix_index_files(dir_path=dest_path, transliteration_target=source_script, dry_run=dry_run)


def dump_word_cloud(src_path, dest_path, stop_words=None, font_path='siddhanta'):
  from collections import Counter
  from doc_curation.md.content_processor import patterns
  from wordcloud import WordCloud, STOPWORDS
  if stop_words is not None:
    stop_words = set(stop_words)
    stop_words.update(STOPWORDS)
  wc = WordCloud(width=1600, height=800, font_path=font_path, stopwords=stop_words, regexp=patterns.DEVANAGARI_OR_LATIN_WORD)
  counts_map = apply_function(fn=patterns.get_word_count, dir_path=src_path, wc=wc)
  counts = Counter()
  for file_path, file_counts in counts_map.items():
    counts.update(file_counts)
  wc.generate_from_frequencies(counts)
  if not dest_path.startswith("/"):
    dest_path = os.path.join(src_path, dest_path)
  os.makedirs(os.path.dirname(dest_path), exist_ok=True)
  wc.to_file(dest_path)
  return counts


