import itertools
import logging

import regex
from more_itertools import peekable

from doc_curation.md import content_processor
from indic_transliteration import sanscript


def get_lines_till_section(lines_in):
  lines = list(lines_in)
  lines_till_section = itertools.takewhile(lambda line: not line.startswith("#"), lines)
  remaining = itertools.dropwhile(lambda line: not line.startswith("#"), lines)
  return (peekable(lines_till_section), peekable(remaining))


def reduce_section_depth(lines_in):
  for line in lines_in:
    if line.startswith("#"):
      yield line[1:]
    else:
      yield line


def get_section(lines_in):
  """
  
  :param lines_in: 
  :return: (title, lines_in_section, reamining)
  """
  lines = list(lines_in)
  if not lines[0].startswith("#"):
    header_prefix = "#"
    # Below, we're careful to handle sections without titles - ie lines such as "##\n"
    is_non_section_start = lambda line: not (line.strip() + " ").startswith(header_prefix)
    lines_in_section = itertools.takewhile(is_non_section_start, lines[1:])
    remaining = itertools.dropwhile(lambda line: is_non_section_start(line), lines[1:])
    return (None, peekable(lines_in_section), peekable(remaining))
  header_prefix = lines[0].split()[0] + " "
  title = get_section_title(lines[0])
  lines_in_section = []
  remaining = []
  if len(lines) > 1:
    # Below, we're careful to handle sections without titles - ie lines such as "##\n"
    is_non_section_start = lambda line: not (line.strip() + " ").startswith(header_prefix)
    lines_in_section = itertools.takewhile(is_non_section_start, lines[1:])
    remaining = itertools.dropwhile(lambda line: is_non_section_start(line), lines[1:])
  return (title, peekable(lines_in_section), peekable(remaining))


def split_to_sections(lines_in):
  remaining = peekable(lines_in)
  sections = []
  while (remaining):
    (title, lines_in_section, remaining) = get_section(remaining)
    sections.append((title, lines_in_section))
  return sections


def get_section_lines(lines_in, section_title):
  sections = split_to_sections(lines_in=lines_in)
  for section in sections:
    if section[0] == section_title:
      return section[1]
  return None


def get_section_title(title_line):
  splits = title_line.split()
  if len(splits) == 1:
    return None
  title = " ".join(splits[1:])
  title = regex.sub("[।॥. ]+", " ", title)
  title = regex.sub("\\s+", " ", title)
  return title.strip()


def get_init_content_lines(lines_in):
  lines_in = list(lines_in)
  if len(lines_in) == 0:
    return lines_in
  (lines_till_section, remaining) = get_lines_till_section(lines_in=lines_in)
  lines_till_section = [line for line in lines_till_section if line.strip() != ""]
  if len(lines_till_section) != 0:
    return lines_till_section
  else:
    sections = split_to_sections(lines_in=remaining)
    if len(sections) > 0:
      return get_init_content_lines(lines_in=sections[0][1])
    else:
      return []


def drop_sections(md_file, title_condition):
  [metadata, content] = md_file.read()
  lines = content.splitlines(keepends=False)
  (lines_till_section, remaining) = get_lines_till_section(lines)
  sections = split_to_sections(remaining)
  if len(sections) == 0:
    return
  sections = [section for section in sections if not title_condition(section[0])]

  lines_out = list(lines_till_section)
  for section_index, (title, section_lines) in enumerate(sections):
    lines_out.append("\n## %s" % title)
    lines_out.extend(section_lines)
  return "\n".join(lines_out)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def add_init_words_to_section_titles(md_file, num_words=2, title_post_processor=None, dry_run=False):
  [metadata, content] = md_file.read()
  lines = content.splitlines(keepends=False)
  (lines_till_section, remaining) = get_lines_till_section(lines)
  sections = split_to_sections(remaining)
  if len(sections) == 0:
    return

  sections_out = []
  for section_index, (title, section_lines) in enumerate(sections):
    if title is None:
      title = ""
    section_lines = list(section_lines)
    init_lines = get_init_content_lines(lines_in=section_lines)
    extra_title = content_processor.title_from_text(text=" ".join(init_lines), num_words=num_words, target_title_length=None)
    if extra_title is not None:
      title = "%s %s" % (title.strip(), extra_title)

    sections_out.append((title, section_lines))

  lines_out = list(lines_till_section)
  for section_index, (title, section_lines) in enumerate(sections_out):
    if title_post_processor is not None:
      title = title_post_processor(title)
    lines_out.append("\n## %s" % title)
    lines_out.extend(section_lines)
  content = "\n".join(lines_out)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)