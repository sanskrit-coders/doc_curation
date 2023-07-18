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

import doc_curation.md
from curation_utils import scraping, file_helper
from enum import Flag, auto

class ForceMode(Flag):
  NONE = 0
  MANTRA = auto()
  PADA = auto()
  COMMENT_ONLY = auto()
  COMMENT = PADA | COMMENT_ONLY
  MANTRA_COMMENT = MANTRA|COMMENT


def audio_saver(soup, dest_path):
  audio_tag = soup.select_one("div.mantra-bhag audio source")
  if audio_tag is None:
    logging.info(f"No audio found for {dest_path}")
    return 
  audio_url = urljoin("https://xn--j2b3a4c.com/", audio_tag["src"])
  dest_path_audio = dest_path.replace("/home/vvasuki/gitland/vishvAsa/", "/mnt/vmedia/audio/curation/archive/veda_com/").replace("static/", "").replace("sarvASh_TIkAH/", "") + ".mp3"
  dest_path_audio = regex.sub("/vedAH/", "/vedAH_", dest_path_audio)
  if os.path.exists(dest_path_audio):
    return 
  audio_doc = requests.get(audio_url)
  os.makedirs(os.path.dirname(dest_path_audio), exist_ok=True)
  with open(dest_path_audio, 'wb') as f:
    f.write(audio_doc.content)

def fix_jaatya_svarita(text):
  text = regex.sub(f"([यव]{patterns.DEVANAGARI_MATRA_YOGAVAHA}*)", r"\1᳡", text)
  text = regex.sub("᳡([ःं])", "\1᳡", text)
  text = text.replace("[᳡]ऽ", "ऽ")
  return text


def check_mantra_match(soup, dest_path, strip_svaras=False):
  mantra = soup.select_one("div.block-mantra")
  mantra = mantra.text.strip()
  mantra_svara = soup.select_one("div.block-mantra-swara")
  if mantra_svara is None:
    mantra_svara = mantra
  else:
    [x.decompose() for x in mantra_svara.select("small")]
    mantra_svara = mantra_svara.text.strip()
    
  if "atharva" in dest_path:
    mantra = fix_jaatya_svarita(mantra)
  else:
    mantra = mantra.replace("", "ऽ")
  mantra = mantra.replace("", "३॒॑").replace("", "१॒॑")
  mantra = regex.sub("([३१]?)([३१]?)", r"\1\2॒॑", mantra)
  md_file = MdFile(file_path=dest_path.replace("sarvASh_TIkAH", "mUlam"))
  if not os.path.exists(md_file.file_path):
    logging.warning("Missing mUla. Writing.")
    md_file.dump_to_file(metadata={}, content=mantra_svara, dry_run=False)
    metadata_helper.set_title_from_filename(md_file)
    metadata_helper.add_init_words_to_title(md_file=md_file, num_words=2)
    return (False, mantra_svara, mantra, 0.0)
  [metadata, content] = md_file.read()
  content = regex.sub( patterns.DETAILS, "", content)
  (has_match, distance) = text_utils.edit_distance_match(a=content, b=mantra_svara, strip_svaras=strip_svaras, cutoff=.2)
  if not has_match:
    logging.warning(f"No match: {mantra_svara} vs {content}")
  return (has_match, mantra_svara, mantra, distance)


def dump_mantra_details(dest_path, url, comment_detection_str, mode=ForceMode.NONE):
  soup = scraping.get_soup(url=url)
  next_url = urljoin("https://xn--j2b3a4c.com/", soup.select_one("li.next a")["href"])
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
  (has_match, mantra_svara, mantra, distance) = check_mantra_match(soup=soup, dest_path=dest_path)
  if (has_match or (ForceMode.MANTRA & mode)) and distance != 0:
    update_muula(dest_path, mantra, mantra_svara)
  if "विस्वर-मूलम् (VC)" not in content:
    update_muula(dest_path, mantra, mantra_svara, visvara_only=True)
  if not (ForceMode.COMMENT & mode) and not has_match:
    logging.warning(f"Could not match mantra: {url}, {dest_path}")
    return next_url


  if comment_detection_str in content:
    # logging.info(f"Skipping: {url}")
    # md_file.transform(content_transformer=lambda c, m: details_helper.insert_after_detail(content=c, metadata=m, title="पदपाठः", new_element=comment_details[-1].to_soup()))
    return next_url

  comment_details = []
  if ForceMode.PADA & mode:
    pada_paaTha = soup.select_one("div.block-pad p").text
    pada_paaTha = regex.sub(" *[।॥] *", "। ", pada_paaTha).replace(":", "ः")
    pada_paaTha = fix_jaatya_svarita(text=pada_paaTha)
    comment_details.append(details_helper.Detail(title="पदपाठः", content=pada_paaTha))

  annotations = [x.text.strip() for x in soup.select("div.mantra-bhag>.alert a") if x.text.strip() != ""]
  comment_details.append(details_helper.Detail(title=f"अधिमन्त्रम् (VC)", content="- " + "\n- ".join(annotations)))

  audio_saver(soup=soup, dest_path=dest_path)

  comments_divs = list(soup.select("div.bhashya_show"))
  titles = []

  for i in range(10):
    if len(comments_divs) >= 1:
      break
    soup = scraping.get_soup(url=url)
    comments_divs = soup.select("div.bhashya_show")

  comments_divs.extend(soup.select("div.bhashya_hide"))
  for comments_div in comments_divs:
    comment_details.extend(comments_from_div(comments_div, titles=titles))

  new_content = "\n\n".join([x.to_md_html() for x in comment_details])
  if not os.path.exists(dest_path):
    md_file.dump_to_file(metadata={}, content=new_content, dry_run=False)
  else:
    md_file.replace_content_metadata(new_content=f"{content}\n\n{new_content}")
  return next_url


def update_muula(dest_path, mantra, mantra_svara, visvara_only=False):
  md_mantra = MdFile(file_path=dest_path.replace("sarvASh_TIkAH", "mUlam"))
  (metadata, content) = md_mantra.read()
  if "मूलम् (VC)" not in content:
    if not visvara_only:
      detail = details_helper.Detail(title="मूलम् (VC)", content=mantra_svara)
      content = f"{content}\n\n{detail.to_md_html()}"
    if mantra_svara != mantra:
      detail = details_helper.Detail(title="विस्वर-मूलम् (VC)", content=mantra)
      content = f"{content}\n\n{detail.to_md_html()}"
    md_mantra.replace_content_metadata(new_content=content)


def comments_from_div(div, titles):
  comment_details = []
  title_div = div.select_one("div.headline")
  body_divs = div.select("div.mantra-bhashya")
  title = title_div.text.strip()
  title = regex.sub("\s+", " ", title)
  if title == "स्वामी दयानन्द सरस्वती":
    if "स्वामी दयानन्द सरस्वती" in titles:
      title = "दयानन्द-सरस्वती (सं)"
    else:
      title = "दयानन्द-सरस्वती (हि)"
  elif "माता सविता जोशी (यह अनुवाद स्वामी दयानन्द सरस्वती जी के आधार पर किया गया है।)" in title:
    title = "सविता जोशी ← दयानन्द-सरस्वती (म)"

  titles.append(title)

  for body_div in body_divs:
    def append_detail_if_present(div, css, appendix):
      tag = div.select_one(css)
      if tag is not None:
        comment_details.append(details_helper.Detail(title=f"{title} - {appendix}", content=tag.text))

    append_detail_if_present(div=div, css="div.anavay", appendix="अन्वयः")
    append_detail_if_present(div=div, css="div.mb_subject", appendix="विषयः")
    append_detail_if_present(div=div, css="div.padarth", appendix="पदार्थः")
    append_detail_if_present(div=div, css="div.bhavarth", appendix="भावार्थः")
    append_detail_if_present(div=div, css="div.footnote", appendix="पादटिप्पनी")
  return comment_details


def dump_sequence(url, path_maker, comment_detection_str, max_mantras=99999):
  num_mantras = 1
  while url is not None and num_mantras <= max_mantras:
    (dest_path, mode) = path_maker(url)
    next_url = dump_mantra_details(dest_path=dest_path, url=url, comment_detection_str=comment_detection_str, mode=mode)
    if url == next_url:
      logging.info(f"Finished at {url}")
      break
    url = next_url
    num_mantras += 1
