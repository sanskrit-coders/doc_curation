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


def reduce_section_depth(lines_in, hashes_to_reduce):
  for line in lines_in:
    if line.startswith("#"):
      yield line[len(hashes_to_reduce):]
    else:
      yield line


class Section(object):
  def __init__(self, title, header_prefix, lines=[]):
    self.title = title
    self.lines = lines
    self.header_prefix = header_prefix

def get_section(lines_in):
  """
  
  :param lines_in: 
  :return: (title, lines_in_section, reamining)
  """
  lines = list(lines_in)
  if len(lines) == 0:
    return (None, [])
  if not lines[0].startswith("#"):
    header_prefix = "# "
    title = None
  else:
    header_prefix = lines[0].split()[0] + " "
    title = get_section_title(lines[0])
  section = Section(title=title, header_prefix=header_prefix)
  lines_in_section = []
  remaining = []
  if len(lines) > 1:
    # Below, we're careful to handle sections without titles - ie lines such as "##\n"
    is_non_section_start = lambda line: not (line.strip() + " ").startswith(header_prefix)
    section.lines = itertools.takewhile(is_non_section_start, lines[1:])
    remaining = itertools.dropwhile(lambda line: is_non_section_start(line), lines[1:])
  return (section, remaining)


def split_to_sections(lines_in):
  remaining = peekable(lines_in)
  sections = []
  while (remaining):
    (section, remaining) = get_section(remaining)
    if section is not None:
      sections.append(section)
  return sections


def get_section_lines(lines_in, section_title):
  sections = split_to_sections(lines_in=lines_in)
  for section in sections:
    if section == section.title:
      return section.lines
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
      return get_init_content_lines(lines_in=sections[0].lines)
    else:
      return []


def drop_sections(md_file, title_condition):
  [metadata, content] = md_file.read()
  lines = content.splitlines(keepends=False)
  (lines_till_section, remaining) = get_lines_till_section(lines)
  sections = split_to_sections(remaining)
  if len(sections) == 0:
    return
  sections = [section for section in sections if not title_condition(section.title)]

  lines_out = list(lines_till_section)
  for section_index, section in enumerate(sections):
    lines_out.append("\n## %s" % section.title)
    lines_out.extend(section.lines)
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
  for section_index, section in enumerate(sections):
    title = section.title
    if title is None:
      title = ""
    section_lines = list(section.lines)
    init_lines = get_init_content_lines(lines_in=section_lines)
    extra_title = content_processor.title_from_text(text=" ".join(init_lines), num_words=num_words, target_title_length=None)
    if extra_title is not None:
      title = "%s %s" % (title.strip(), extra_title)

    sections_out.append(Section(title=title, lines=section_lines, header_prefix=section.header_prefix))

  lines_out = list(lines_till_section)
  for section_index, section in enumerate(sections_out):
    if title_post_processor is not None:
      title = title_post_processor(section.title)
    lines_out.append("\n%s%s" % (section.header_prefix, title))
    lines_out.extend(section.lines)
  content = "\n".join(lines_out)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def autonumber_section_lines(lines, dest_script=sanscript.DEVANAGARI, recursive=True):
  (lines_till_section, remaining) = get_lines_till_section(lines)
  sections = split_to_sections(remaining)
  lines_out = list(lines_till_section)
  index_pattern = "%%0%dd" % (len(str(len(sections))))
  for section_index, section in enumerate(sections):
    title = section.title
    if title is None:
      title = ""
    title = regex.sub("^[0-9०-९೦-೯]+", "", title.strip())
    transliterated_index = index_pattern % (section_index + 1)
    if dest_script is not None:
      transliterated_index = sanscript.transliterate(data=transliterated_index, _to=dest_script, _from=sanscript.IAST)
    title = "%s %s" % (transliterated_index, title)
    lines_out.append("\n%s%s" % (section.header_prefix, title))
    if recursive:
      section.lines = autonumber_section_lines(lines=section.lines, dest_script=dest_script, recursive=recursive) 
    lines_out.extend(section.lines)
  return lines_out


def autonumber(md_file, dest_script=sanscript.DEVANAGARI, recursive=True, dry_run=False):
  [metadata, content] = md_file.read()
  lines = content.splitlines(keepends=False)
  lines = autonumber_section_lines(lines=lines, dest_script=dest_script, recursive=recursive)
  content = "\n".join(lines)
  content = regex.sub("\n\n+", "\n\n", content)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def create_sections_from_terminal_digits(md_file, digit_pattern="([०-९]+)", section_mark="##", dry_run=False):
  def replacement_maker(match):
    return "\n%s %s\n%s\n\n" %  (section_mark, match.group(1), match.group().strip())
  content_processor.replace_texts(md_file=md_file, patterns=[r"\n[\s\S]+?%s *\n" % (digit_pattern)], replacement=replacement_maker, dry_run=dry_run)