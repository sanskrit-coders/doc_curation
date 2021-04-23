import itertools
import logging

import regex
from more_itertools import peekable

# Remove all handlers associated with the root logger object.

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")


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


def get_section_title(title_line):
  splits = title_line.split()
  if len(splits) == 1:
    return None
  title = " ".join(splits[1:])
  title = regex.sub("[।॥. ]+", " ", title)
  title = regex.sub("\\s+", " ", title)
  return title.strip()


def markdownify_plain_text(text_in):
  text = text_in.replace("\n", "  \n")
  text = regex.sub("^  $", "", text)
  return text


