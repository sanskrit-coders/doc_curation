import logging

import regex
from bs4 import NavigableString
from tqdm import tqdm

from doc_curation.md import content_processor
from doc_curation.md.content_processor.details import Detail, _normalize_spaces


def translate(text, source_language="en", dest_language="es", translator="google"):
  import translators
  if not regex.search(r"[^\d\s*&%\^$#@!~`';:\[\]{}\-]", text):
    return text
  return translators.translate_text(text, from_language=source_language, to_language=dest_language, translator=translator)


def translate_partwise(text, part_pattern=r"\n", result_pattern = "%s  \n{%s}\n", source_language="en", dest_language="es", translator="google"):
  result = ""
  parts = regex.split(part_pattern, text)
  for part in parts:
    if not regex.search(r"[^\d\s*&%\^$#@!~`';:\[\]{}\-]", part):
      result += part + "\n"
    else:
      result += result_pattern % (part, translate(part, source_language, dest_language, translator))
  return result


def sentences_to_translated_details(content, source_language="en", dest_language="es"):
  from nltk.tokenize import sent_tokenize
  if f"<details><summary>{dest_language}</summary>" in content:
    logging.debug("Skipping translation because <summary>%s</summary>", dest_language)
    return content
  subcontents = regex.split(r"((?<=\n|^)[#\-<!]+[^\n]+(?=\n|$))", content)
  content_out = ""
  for subcontent in tqdm(subcontents, desc='Sec', ):
    if regex.match(r"[#\-<! ]+", subcontent):
      translation = translate(text=subcontent, source_language=source_language, dest_language=dest_language)
      content_out += f"{subcontent}  \n  {{{translation}}}\n"
      continue
    soup = content_processor._soup_from_content(content=subcontent)
    if soup is None:
      return subcontent
    for element in soup.select_one("body").children:
      if isinstance(element, NavigableString):
        tokenizer_language = {"en": "english", "es": "spanish"}
        sentences = sent_tokenize(element.text, language=tokenizer_language[source_language])
        detail_pairs = []
        for sentence in tqdm(sentences, desc='Sent', ):
          detail_muula = Detail(title = source_language, content=sentence)
          translation = translate(text=sentence, source_language=source_language, dest_language=dest_language)
          detail_trans = Detail(title = dest_language, content=translation)
          detail_pairs.append([detail_muula, detail_trans])
        detail_pairs.reverse()
        for [detail_muula, detail_trans] in detail_pairs:
          element.insert_after(NavigableString("\n\n"))
          element.insert_after(detail_trans.to_soup())
          element.insert_after(NavigableString("\n\n"))
          element.insert_after(detail_muula.to_soup(attributes_str="open"))
        element.extract()
        if element.name == "details":
          detail = Detail.from_soup_tag(detail_tag=element)
          translation = translate(text=detail.content, source_language=source_language, dest_language=dest_language)
          detail_trans = Detail(title = f"{detail.title} {dest_language}", content=translation)
          element.insert_after(NavigableString("\n\n"))
          element.insert_after(detail_trans.to_soup())
          element.insert_after(NavigableString("\n\n"))
    subcontent = content_processor._make_content_from_soup(soup=soup)
    content_out = content_out + subcontent + "\n\n"
  content_out = _normalize_spaces(content_out)
  return content_out


def add_translation_detail(content, src_detail_pattern="English", source_language="en", dest_language="es"):
  def _title_from_detail(detail):
    title = f"{detail.title} {dest_language}"
    if detail.title == "English":
      title = "Español"
    return title
  soup = content_processor._soup_from_content(content=content)
  if soup is None:
    return content
  content_modified = False
  elements = [element for element in soup.select_one("body").children if element.name == "details" and regex.match(src_detail_pattern, Detail.from_soup_tag(detail_tag=element).title)]
  dest_elements = [element for element in soup.select_one("body").children if element.name == "details" and _title_from_detail(Detail.from_soup_tag(detail_tag=elements[0])) == Detail.from_soup_tag(detail_tag=element).title]
  if len(dest_elements) > 0:
    logging.debug("Skipping translation")
    return content
  for element in tqdm(elements):
    detail = Detail.from_soup_tag(detail_tag=element)
    title = _title_from_detail(detail)
    translation = translate(text=detail.content, source_language=source_language, dest_language=dest_language)
    translation = regex.sub(r"\[^", fr"\[^{dest_language}", translation)
    translation = regex.sub(r"(?<=\n|^) (\[^.+?\]:|>)", fr"\1", translation)
    detail_trans = Detail(title=title, content=translation)
    element.insert_after(detail_trans.to_soup())
    content_modified = True
  if content_modified:
    content = content_processor._make_content_from_soup(soup=soup)
    content = _normalize_spaces(content)
  return content
