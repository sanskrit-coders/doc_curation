from bs4 import BeautifulSoup, Tag, Comment
import logging

import regex
from doc_curation.md import content_processor
from doc_curation.md.content_processor import include_helper,details_helper


def migrate_and_include_Rk_details(md_file, rk_title_pattern="विश्वास-प्रस्तुतिः", comment_title_pattern="मूलम्|.*भाष्यम्|.*टीका|Keith", dry_run=False):
  logging.info("Processing %s", md_file.file_path)
  [metadata, content] = md_file.read()
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return []
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return []
  details = soup.select("details")
  gathering_commentaries = False
  rk_title = None
  rk_text_path = None
  for index, detail_tag in enumerate(details):
    detail = details_helper.Detail.from_soup_tag(detail_tag=detail_tag)
    if regex.fullmatch(rk_title_pattern, detail.title):
      rk_title = include_helper.init_word_title_maker(text_matched=detail.content, index=index, file_title=metadata["title"])
      rk_text_path = include_helper.static_include_path_maker(rk_title, md_file.file_path, path_replacements={"content": "static","(brAhmaNam|saMhitA|AraNyakam|kAThakam)/sarva-prastutiH":r"\1/Rk/vishvAsa-prastutiH", ".md": ""},)
      from doc_curation.md.file import MdFile
      md_file_dest = MdFile(file_path=rk_text_path)
      md_file_dest.replace_content_metadata(new_metadata={"title": rk_title}, new_content=detail.content, dry_run=dry_run)
      comment_text_path   = rk_text_path.replace("vishvAsa-prastutiH", "sarvASh_TIkAH")
      md_file_comment = MdFile(file_path=comment_text_path)
      md_file_comment.replace_content_metadata(new_metadata={"title": rk_title}, new_content="", dry_run=dry_run)
      
        
      include_text = f"{include_helper.vishvAsa_include_maker(rk_text_path, title='विश्वास-प्रस्तुतिः')}\n\n{include_helper.vishvAsa_include_maker(comment_text_path, title='सर्वाष् टीकाः')}"
      detail_tag.replace_with(BeautifulSoup(include_text, 'html.parser'))
      
      gathering_commentaries = True
      comment_text = ""
    elif gathering_commentaries  and regex.match(comment_title_pattern, detail.title):
      [md_metadata, md_content] = md_file_comment.read()
      md_content = f"{md_content}\n\n{detail.to_md_html()}"
      md_file_comment.replace_content_metadata(new_content=md_content, dry_run=dry_run)
      detail_tag.decompose()
      pass
    else:
      gathering_commentaries = False
  content = content_processor._make_content_from_soup(soup=soup)
  content = content.replace("<div", "\n<div")
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)