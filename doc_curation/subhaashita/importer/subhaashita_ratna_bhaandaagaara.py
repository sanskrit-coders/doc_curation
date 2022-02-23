import os

import regex
from indic_transliteration import sanscript

from doc_curation.md import library, content_processor
from doc_curation.md.content_processor import patterns
from doc_curation.subhaashita import Subhaashita

PATH_SRB = "/home/vvasuki/vishvAsa/kAvyam/content/laxyam/padyam/subhAShitam/subhAShita-ratna-bhANDAgAram/"


def from_file(md_file, deduce_from_title="topics"):
  (metadata, content) = md_file.read()
  full_title = md_file.get_title(ref_dir_for_ancestral_title=PATH_SRB)
  content = "\n" + content_processor.remove_non_content_text(content=content)
  matches = regex.findall(patterns.PATTERN_SHLOKA, content)
  quotes = []
  for match in matches:
    source_descriptor = "सुभाषितरत्नभाण्डागारः// %s// %s" % (full_title, match[1])
    text = match[0] + "॥"
    text = sanscript.SCHEMES[sanscript.DEVANAGARI].fix_lazy_anusvaara(text, omit_sam=True, omit_yrl=True, ignore_padaanta=True)
    metadata_out = {}
    deduce_metadata(deduce_from_title, metadata_out, metadata)
    
    quote = Subhaashita(variants=[text], secondary_sources=[source_descriptor], **metadata_out)
    quotes.append(quote)
  return quotes


def deduce_metadata(deduce_from_title, metadata_out, metadata):
  for field in ["topics", "types"]:
    if field in metadata:
      metadata_out[field] = metadata[field]
    elif field == deduce_from_title:
      metadata_out[field] = [regex.sub("\d+ +", "", metadata["title"])]


def from_dir(sub_dir, deduce_from_title="topics"):
  base_path = os.path.join(PATH_SRB, sub_dir)
  quotes_map = library.apply_function(fn=from_file, dir_path=base_path, deduce_from_title=deduce_from_title)
  quotes = []
  for file_path, quote_list  in quotes_map.items():
    quotes.extend(quote_list)
  return quotes
