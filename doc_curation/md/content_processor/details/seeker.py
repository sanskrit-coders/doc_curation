import logging
import os
from collections import defaultdict

import regex
from doc_curation.md import content_processor
from doc_curation.md.content_processor.details.model import Detail
from doc_curation.md.file import MdFile


def extract_detail_tags_from_file(md_file):
  [metadata, content] = md_file.read()
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return []
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  details = soup.select("body>details", recursive=False)
  return details

def get_detail_bunches(md_file, bunch_start_pattern="विश्वास-प्रस्तुतिः.*", comment_title_pattern="मूलम्.*|.*भाष्यम्.*|.*टीका.*|English.*|Español.*|विश्वास-टिप्पनी.*|विषयः|भावः|स्रोतः", ignored_titles = ""):
  details = extract_detail_tags_from_file(md_file=md_file)
  bunches = []
  bunch = None
  for index, detail_tag in enumerate(details):
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    if detail_tag.parent.name == "div":
      # Likely to already be an include
      continue
    if regex.fullmatch(bunch_start_pattern, detail.title):
      if bunch is not None:
        bunches.append(bunch)
      bunch = [detail]
      gathering_commentaries = True
      comment_text = ""
    elif gathering_commentaries  and regex.match(comment_title_pattern, detail.title):
      bunch.append(detail)
    elif regex.fullmatch(ignored_titles, detail.title): 
      continue
    else:
      gathering_commentaries = False
      bunches.append(bunch)
      bunch = None
  if bunch is not None:
    bunches.append(bunch)
  return bunches

def get_details(content, title=".*", metadata=None):
  # Stray usage of < can fool the soup parser. Hence the below.
  if "details" not in content:
    return []
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return []
  details = soup.select("details")
  result = []
  for detail_tag in details:
    detail = Detail.from_soup_tag(detail_tag=detail_tag)
    if regex.match(title, detail.title):
      result.append((detail_tag, detail))
  return result

def get_detail(content, metadata, title):
  """
  
  :param content: 
  :param metadata: 
  :param title: 
  :return: (detail_tag, detail)
  """
  details = get_details(content=content, metadata=metadata, title=title)
  if len(details) == 0:
    return (None, None)
  else:
    return details[0]

def get_detail_content(content, titles, metadata=None):
  result = ""
  for title in titles:
    details = get_details(content=content, metadata=metadata, title=title)
    for detail_tuple in details:
      (tag, detail) = detail_tuple
      result = f"{result}  \n{detail.content}"
  return result

def dump_detail_content(source_md, dest_path, titles, dry_run=False):
  (metadata, content) = source_md.read()
  metadata["_file_path"] = source_md.file_path
  detail_content = get_detail_content(content=content, metadata=metadata, titles=titles)
  dest_md = MdFile(file_path=dest_path)
  dest_md.dump_to_file(metadata={"title": " ".join(titles)}, content=detail_content, dry_run=dry_run)

def count_details(content, metadata, *args, **kwargs):
  if "details" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    logging.info(f"No details found in {metadata['_file_path']}")
    return content
  # Don't pick up details within details.
  details = soup.find_all(lambda x: x.name == 'details' and x.find_parent("details") is None)
  details_dict = defaultdict(int)
  for detail_tag in details:
    title = Detail.from_soup_tag(detail_tag=detail_tag).title.split(" - ")[0]
    details_dict[title] += 1
  logging.info(f"{len(details_dict)} details found in {os.path.basename(metadata['_file_path'])} - {details_dict}")
  return content

def get_nieghbor_detail(detail_tag, seek_before=False):
  """Gets the neighboring detail tag based on seek direction.

  Args:
      detail_tag: The BeautifulSoup detail tag to start from
      seek_before: If True, look at previous siblings, else next siblings

  Returns:
      The neighboring Detail object or None if not found
  """
  if seek_before:
    sibling = detail_tag.find_previous_sibling("details")
  else:
    sibling = detail_tag.find_next_sibling("details")
  return sibling


# Correctly spelled alias (original name has a typo; keep both).
get_neighbor_detail = get_nieghbor_detail
