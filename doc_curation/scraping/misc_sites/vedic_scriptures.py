import logging
import os
import textwrap
from urllib.parse import urljoin
import requests
import regex
from doc_curation.utils import text_utils, patterns
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor import details_helper
from doc_curation.md.library import metadata_helper
import editdistance

from curation_utils import scraping, file_helper
from enum import Flag, auto

class ForceMode(Flag):
  NONE = 0
  PADA = auto()
  MANTRA_ONLY = auto()
  COMMENT_ONLY = auto()
  MANTRA = MANTRA_ONLY|PADA
  COMMENT = PADA | COMMENT_ONLY
  MANTRA_COMMENT = MANTRA|COMMENT


def fix_text(text, muula_text=True):
  if muula_text:
    text = text.replace(":", "ः").replace("", "᳡").replace("", "३॒॑").replace("", "१॒॑")
    text = regex.sub("।\s*", "।  \n", text)
  text = regex.sub("([३१]?)([३१]?)", r"\1\2॒॑", text)
  return text_utils.svara_post_yogavaaha(text)


def check_mantra_match(soup, dest_path, strip_svaras=False):
  mantra_svara = soup.select_one(".mantra-bhag h3.vs-mantra")
  mantra_svara = mantra_svara.text.strip()
  if "atharva" in dest_path:
    mantra_svara = fix_text(mantra_svara)
  mantra_svara = mantra_svara
  md_file = MdFile(file_path=dest_path.replace("sarvASh_TIkAH", "mUlam"))
  if not os.path.exists(md_file.file_path):
    logging.warning("Missing mUla. Writing.")
    md_file.dump_to_file(metadata={}, content=mantra_svara, dry_run=False)
    metadata_helper.set_title_from_filename(md_file)
    metadata_helper.add_init_words_to_title(md_file=md_file, num_words=2)
    return (False, mantra_svara, 0.0)
  [metadata, content] = md_file.read()
  if "मूलम् (VS)" in content:
    (_, detail) = details_helper.get_detail(content=content, metadata=metadata, title="मूलम् (VS)")
    content = detail.content
  content = regex.sub( patterns.DETAILS, "", content)
  (has_match, distance) = text_utils.edit_distance_match(a=content, b=mantra_svara, strip_svaras=strip_svaras, cutoff=.3)
  if not has_match:
    logging.warning(f"No match: {mantra_svara} vs {content}")
  return (has_match, mantra_svara, distance)



def dump_mantra_details(dest_path, url, commentaries_needed, mode=ForceMode.NONE, muula_insertion_mode="all_detail"):
  soup = scraping.get_soup(url=url)
  buttons = soup.select("a.rounded-sm.border-dark")
  if len(buttons) < 2:
    return None
  else:
    next_url = urljoin("https://vedicscriptures.in/atharvaveda/", buttons[-1]["href"])
  if "SKIP" in dest_path:
    logging.warning(f"Skipping dump for {url}")
    return next_url

  md_file = MdFile(file_path=dest_path)
  if not os.path.exists(dest_path):
    logging.warning(f"Not found! {dest_path}")
    content = ""
    # return next_url
  else:
    [metadata, content] = md_file.read()
  (has_match, mantra_svara, distance) = check_mantra_match(soup=soup, dest_path=dest_path)
  if not has_match:
    logging.warning(f"Could not match mantra: {url}, {dest_path}")
    return next_url
  # if (has_match or (ForceMode.MANTRA & mode)):
  if distance != 0 or muula_insertion_mode == "replace":
    update_muula(dest_path, mantra_svara, insertion_mode=muula_insertion_mode)
  
  # if not (ForceMode.COMMENT & mode) and not has_match:
  #   logging.warning(f"Could not match mantra: {url}, {dest_path}")
  #   return next_url


  comment_details = []
  pada_paaTha = None
  if ForceMode.PADA & mode:
    pada_paaTha = soup.select_one("p.pt-1.mb-2").text
    pada_paaTha = regex.sub(" *[।॥] *", "। ", pada_paaTha)
    pada_paaTha = fix_text(pada_paaTha)
    pada_paaTha = pada_paaTha


  # comments_divs = list(soup.select("div.bhashya-bhag card"))
  # 
  # for i in range(10):
  #   if len(comments_divs) >= 1:
  #     break
  #   soup = scraping.get_soup(url=url)
  #   comments_divs = list(soup.select("div.bhashya-bhag card"))
  # 
  # for comments_div in comments_divs:
  #   comment_details.extend(comments_from_div(comments_div, commentaries_needed=commentaries_needed))
  # 
  # new_content = "\n\n".join([x.to_html() for x in comment_details])
  if not os.path.exists(dest_path):
    md_file.dump_to_file(metadata={}, content=new_content, dry_run=False)
  else:
    if pada_paaTha is not None:
      content = details_helper.transform_details_with_soup(content=content, metadata=metadata, transformer=details_helper.detail_content_replacer_soup, title="पदपाठः", replacement=pada_paaTha)
    # md_file.replace_content_metadata(new_content=f"{content}\n\n{new_content}")
    md_file.replace_content_metadata(new_content=content)
  return next_url


def update_muula(dest_path, mantra_svara, insertion_mode="add_detail"):
  md_mantra = MdFile(file_path=dest_path.replace("sarvASh_TIkAH", "mUlam"))
  (metadata, content) = md_mantra.read()
  detail = details_helper.Detail(title="मूलम् (VS)", content=mantra_svara)
  if insertion_mode=="add_detail" and "मूलम् (VS)" not in content:
    content = f"{content}\n\n{detail.to_md_html()}"
  elif insertion_mode == "all_detail":
    old_detail = details_helper.Detail(title="मूलम् (VC)", content=content)
    content = f"{old_detail.to_md_html()}\n\n{detail.to_md_html()}"
  elif insertion_mode == "replace":
    content = detail.to_md_html()
  md_mantra.replace_content_metadata(new_content=content)


def comments_from_div(div, commentaries_needed):
  comment_details = []
  title_div = div.select_one(".card-header h3")
  title = title_div.text.strip()
  title = regex.sub("\s+", " ", title)
  title_needed = False
  for desired_title_key in commentaries_needed:
    if desired_title_key in title:
      title_needed = True
      break
  if title_needed is False:
    return comment_details
  if "Tulsi Ram" in title:
    title = "Tulsi Ram (AS, En)"

  body_div = div.select_one("div.bhashya-p")
  def append_detail_if_present(css, appendix):
    tag = body_div.select_one(css)
    if tag is not None:
      comment_details.append(details_helper.Detail(title=f"{title} - {appendix}", content=tag.text))
  append_detail_if_present(css=".alert p.mb-0", appendix="विषयः")
  append_detail_if_present(css='div[style*="font-size: 1.1rem;"]', appendix="विषयः")
  return comment_details


def dump_sequence(url, path_maker, max_mantras=99999, muula_insertion_mode="replace"):
  num_mantras = 1
  while url is not None and num_mantras <= max_mantras:
    (dest_path, mode) = path_maker(url)
    next_url = dump_mantra_details(dest_path=dest_path, url=url, mode=mode, commentaries_needed='[]', muula_insertion_mode=muula_insertion_mode)
    if url == next_url:
      logging.info(f"Finished at {url}")
      break
    url = next_url
    num_mantras += 1
