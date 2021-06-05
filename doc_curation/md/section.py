import itertools

import regex
from more_itertools import peekable

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
  lines = list(lines_in)
  if not lines[0].startswith("#"):
    return lines_in
  header_prefix = lines[0].split()[0] + " "
  title = get_section_title(lines[0])
  lines_in_section = []
  remaining = []
  if len(lines) > 1:
    lines_in_section = itertools.takewhile(lambda line: not line.startswith(header_prefix), lines[1:])
    remaining = itertools.dropwhile(lambda line: not line.startswith(header_prefix), lines[1:])
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
    

def add_init_words_to_section_titles(sections, num_words=2, target_title_length=24, depunctuate=True):
  """
  
  :param sections: [(title, section_lines)] list 
  :param num_words: 
  :param target_title_length:
  :param depunctuate: 
  :return: 
  """
  sections_out = []
  for section_index, (title, section_lines) in enumerate(sections):
    if title == None:
      title = ""
    section_lines = list(section_lines)
    init_lines = get_init_content_lines(lines_in=section_lines)
    init_words = " ".join(init_lines).split()[0:num_words]
    if len(init_words) > 0:
      init_words_str = " ".join(init_words)
      if depunctuate:
        devanaaagari_scheme = sanscript.SCHEMES[sanscript.DEVANAGARI]
        init_words_str = devanaaagari_scheme.remove_svaras(in_string=init_words_str)
        init_words_str = devanaaagari_scheme.remove_punctuation(in_string=init_words_str)
        init_words_str = devanaaagari_scheme.fix_lazy_anusvaara(data_in=init_words_str, omit_yrl=True)
        while len(init_words_str) > target_title_length and len(init_words_str.split()) > 1:
          init_words_str = " ".join(init_words_str.split()[:-1])

    title = "%s %s" % (title.strip(), init_words_str)
        
    sections_out.append((title, section_lines))
  return sections_out