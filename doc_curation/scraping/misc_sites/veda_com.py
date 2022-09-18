import logging
import os
import textwrap
from urllib.parse import urljoin
import requests
import regex
from doc_curation.utils import text_utils, patterns
from doc_curation.md.file import MdFile
from doc_curation.md.content_processor import details_helper
import editdistance

import doc_curation.md
from curation_utils import scraping, file_helper
from enum import Flag, auto

class ForceMode(Flag):
  NONE = 0
  MANTRA = auto()
  COMMENT = auto()
  MANTRA_COMMENT = MANTRA|COMMENT


def audio_saver(soup, dest_path):
  audio_tag = soup.select_one("div.mantra-bhag audio source")
  if audio_tag is None:
    logging.info(f"No audio found for {dest_path}")
    return 
  audio_url = urljoin("https://xn--j2b3a4c.com/", audio_tag["src"])
  dest_path_audio = dest_path.replace("/home/vvasuki/vishvAsa/", "/mnt/vmedia/audio/curation/archive/veda_com/").replace("static/", "").replace("sarvASh_TIkAH/", "") + ".mp3"
  dest_path_audio = regex.sub("/vedAH/", "/vedAH_", dest_path_audio)
  if os.path.exists(dest_path_audio):
    return 
  audio_doc = requests.get(audio_url)
  os.makedirs(os.path.dirname(dest_path_audio), exist_ok=True)
  with open(dest_path_audio, 'wb') as f:
    f.write(audio_doc.content)


def check_mantra_match(soup, dest_path):
  if "atharva" in dest_path:
    mantra = soup.select_one("div.block-mantra").text.strip()
    mantra = regex.sub(f"([यव]{patterns.DEVANAGARI_MATRA_YOGAVAHA}*)", r"\1᳡", mantra)
    mantra = mantra.replace("᳡ऽ", "ऽ").replace("", "३॒॑").replace("", "१॒॑")
  else:
    mantra = soup.select_one("div.block-mantra").text.strip().replace("", "ऽ")
  md_file = MdFile(file_path=dest_path.replace("sarvASh_TIkAH", "mUlam"))
  [metadata, content] = md_file.read()
  (has_match, distance) = text_utils.edit_distance_match(a=content, b=mantra, strip_svaras=True)
  if not has_match:
    logging.warning(f"No match: {mantra} vs {content}")
  return (has_match, mantra, distance)


def dump_mantra(dest_path, url, comment_detection_str, mode=ForceMode.NONE):
  soup = scraping.get_soup(url=url)
  next_url = urljoin("https://xn--j2b3a4c.com/", soup.select_one("li.next a")["href"])
  if "SKIP" in dest_path:
    logging.warning(f"Skipping dump for {url}")
    return next_url

  (has_match, mantra, distance) = check_mantra_match(soup=soup, dest_path=dest_path)
  if (has_match or (ForceMode.MANTRA & mode)) and distance != 0:
    md_file = MdFile(file_path=dest_path.replace("sarvASh_TIkAH", "mUlam"))
    md_file.replace_content_metadata(new_content=mantra)
  if not (ForceMode.COMMENT & mode) and not has_match:
    logging.warning(f"Could not match mantra: {url}, {dest_path}")
    return next_url
  if not os.path.exists(dest_path):
    logging.warning(f"Not found! {dest_path}")
    return next_url
  md_file = MdFile(file_path=dest_path)
  [metadata, content] = md_file.read()


  if comment_detection_str in content:
    logging.info(f"Skipping: {url}")
    # md_file.transform(content_transformer=lambda c, m: details_helper.insert_after_detail(content=c, metadata=m, title="पदपाठः", new_element=comment_details[-1].to_soup()))
    return next_url

  pada_paaTha = soup.select_one("div.block-pad p").text
  pada_paaTha = regex.sub(" *[।॥] *", "। ", pada_paaTha).replace(":", "ः")
  audio_saver(soup=soup, dest_path=dest_path)
  comments_div = soup.select_one("div.bhashya_show")

  for i in range(10):
    if comments_div is not None:
      break
    soup = scraping.get_soup(url=url)
    comments_div = soup.select_one("div.bhashya_show")
  titles = [x.text for x in comments_div.select("div.headline h3")]
  subjects = [x.text for x in comments_div.select("div.mb_subject")]
  padaarthas = [x.text for x in comments_div.select("div.padarth")]
  bhaavaaarthas = [x.text for x in comments_div.select("div.bhavarth")]
  footnotes = [x.text for x in comments_div.select("div.footnote")]

  comment_details = [details_helper.Detail(type="पदपाठः", content=pada_paaTha)]
  annotations = [x.text for x in soup.select("div.mantra-bhag>.alert a")]
  comment_details.append(details_helper.Detail(type=f"अधिमन्त्रम् (VC)", content="- " + "\n- ".join(annotations)))


  for title, subject, padaartha, bhaavaartha, footnote in zip(titles, subjects, padaarthas, bhaavaaarthas, footnotes):
    comment_details.append(details_helper.Detail(type=f"{title} - विषयः", content=subject))
    comment_details.append(details_helper.Detail(type=f"{title} - पदार्थः", content=padaartha))
    comment_details.append(details_helper.Detail(type=f"{title} - भावार्थः", content=bhaavaartha))
    comment_details.append(details_helper.Detail(type=f"{title} - पादटिप्पनी", content=footnote))
    
  new_content = "\n\n".join([x.to_html() for x in comment_details])
  md_file.replace_content_metadata(new_content=f"{content}\n\n{new_content}")
  return next_url


def dump_sequence(url, path_maker, comment_detection_str, max_mantras=99999):
  num_mantras = 1
  while url is not None and num_mantras <= max_mantras:
    (dest_path, mode) = path_maker(url)
    next_url = dump_mantra(dest_path=dest_path, url=url, comment_detection_str=comment_detection_str, mode=mode)
    url = next_url
    num_mantras += 1
