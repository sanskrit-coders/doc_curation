import logging
import os

import doc_curation.md.library.metadata_helper
import regex
from bs4 import BeautifulSoup

from doc_curation.md.library import arrangement
from curation_utils import file_helper
from doc_curation.md import content_processor, library
from doc_curation.md.file import MdFile
from doc_curation.scraping.html_scraper import souper
from indic_transliteration import sanscript

class Include(object):
  def __init__(self, url, field_names=None, classes=None, title=None, h1_level=2, extra_attributes=""):
    self.url = url
    self.field_names=field_names
    self.classes = classes
    self.title = title
    self.h1_level = h1_level
    self.extra_attributes = extra_attributes


  def to_html_str(self):
    field_names_str = ""
    if self.field_names is not None:
      field_names_str = "fieldNames=\"%s\"" % (",".join(self.field_names))
    classes_str = ""
    if self.classes is not None:
      classes_str = " ".join(self.classes)
    extra_attributes =  "%s %s" % (self.extra_attributes, " ".join([field_names_str]))
    if self.title == "FILE_TITLE":
      title_str = 'includeTitle="true"'
    elif self.title is not None:
      title_str = "title=\"%s\"" % self.title
    else:
      title_str = None
    if title_str is not None:
      extra_attributes = "%s %s" % (title_str, extra_attributes)
    return """<div class="js_include %s" url="%s"  newLevelForH1="%d" %s> </div>"""  % (classes_str,self.url, self.h1_level, extra_attributes)

def static_include_path_maker(title, original_path, path_replacements={"content": "static", ".md": ""}, use_preexisting_file_with_prefix=True):
  include_path = str(original_path)
  for key, value in path_replacements.items():
    include_path = regex.sub(key, value, include_path)
  if include_path.endswith(".md"):
    return include_path
  else:
    dest_basename = file_helper.get_storage_name(text=title)
    if use_preexisting_file_with_prefix and os.path.exists(include_path):
      similar_files = [x for x in os.listdir(include_path) if x.startswith(dest_basename)]
      if len(similar_files) > 0:
        dest_basename = similar_files[0].replace(".md", "")
    return os.path.join(include_path, "%s.md" % dest_basename)


def vishvAsa_include_maker(file_path, h1_level=4, classes=None, title=None, extra_attributes=None):
  if not os.path.exists(file_path):
    logging.info(f"Does not exist - {file_path} . Skipping")
    return 
  url = file_path.replace("/home/vvasuki/gitland/vishvAsa/", "/").replace("/static/", "/")
  return Include(url=url, h1_level=h1_level, classes=classes, title=title, extra_attributes=extra_attributes).to_html_str()


def init_word_title_maker(text_matched, index, file_title):
  title = doc_curation.md.library.metadata_helper.title_from_text(text=text_matched, num_words=2, target_title_length=None,
                                                                  title_id="%02d"  % (index + 1))
  return title


def migrate_and_replace_texts(md_file, text_patterns, replacement_maker=vishvAsa_include_maker, migrated_text_processor=None, destination_path_maker=static_include_path_maker, title_maker=init_word_title_maker, dry_run=False):
  """
  
  :param md_file: 
  :param text_patterns: 
  :param replacement_maker: 
  :param migrated_text_processor: 
  :param destination_path_maker: To not have migration, pass: lambda x, y: None 
  :param title_maker: 
  :param dry_run: 
  :return: 
  """
  logging.info("Processing %s", md_file.file_path)
  [metadata, content] = md_file.read()
  # For some regexes to work prefectly.
  content = "\n" + content
  matches = []
  for text_pattern in text_patterns:
    matches.extend(regex.finditer(text_pattern, content))
  for index, match in enumerate(matches):
    text_matched = match.group(0)
    text = text_matched.strip()
    if migrated_text_processor is not None:
      text = migrated_text_processor(text)
    title = title_maker(text_matched=text_matched, index=index, file_title=metadata["title"])
    text_path = destination_path_maker(title, md_file.file_path)
    if text_path is not None:
      from doc_curation.md.file import MdFile
      md_file_dest = MdFile(file_path=text_path)
      if os.path.exists(md_file_dest.file_path):
        md_file_dest.replace_content_metadata(new_content=text, dry_run=dry_run)
      else:
        md_file_dest.dump_to_file(metadata={"title": title}, content=text, dry_run=dry_run)
    include_text = replacement_maker(text_matched, text_path)
    content = content.replace(text_matched.strip(), "%s\n" % include_text, 1)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def transform_include_lines(md_file, transformer, dry_run=False):
  [_, content] = md_file.read()
  content = regex.sub(r"<div.+js_include.+url=['\"](.+?)['\"][\s\S]+?</div>", transformer, content)
  md_file.replace_content_metadata(new_content=content, dry_run=dry_run)


def transform_includes_with_soup(content, metadata, transformer, *args, **kwargs):
  # Stray usage of < can fool the soup parser. Hence the below.
  # This will still pass through md files with non js_inclde tags which can be messed up, like  
  # {{< figure src="images/vaidika-puM-deva-jAlam.jpg" title="" class="thumbnail">}}  
    # but that will be fixed later.
  if "js_include" not in content:
    return content
  soup = content_processor._soup_from_content(content=content, metadata=metadata)
  if soup is None:
    return content
  includes = soup.select("div.js_include")
  # logging.debug(f"Processing {metadata['_file_path']}")
  for inc in includes:
    top_level_include = True
    parents = list(inc.parents)
    if len(parents) == 0:
      # Decomposed include?
      continue
    for parent in parents:
      if "js_include" in parent.get("class", []):
        top_level_include = False
        break
    if top_level_include:
      transformer(inc, metadata["_file_path"], *args, **kwargs)
  content = content_processor._make_content_from_soup(soup=soup)
  content = content.replace("{{&lt;", "{{<").replace("&gt;}}", ">}}")
  content = regex.sub("(?<=\s)&gt;", ">", content)
  return  content


def old_include_remover(inc, *args, **kwargs):
  """To be used with transform_include_lines.
  
  :param inc: 
  :return: 
  """
  if not "includetitle" in inc.attrs:
    return inc.decompose()


def make_alt_include(url, file_path, target_dir, h1_level, source_dir, classes=["collapsed"], title=None):
  alt_file_path = file_path.replace(source_dir, target_dir)
  if source_dir not in url:
    logging.fatal("%s %s - no %s found", url, file_path, source_dir)
  alt_url = url.replace(source_dir, target_dir)
  if title is None:
    index_file_path = regex.sub("%s/.+" % target_dir, "%s/_index.md" % target_dir, alt_file_path)
    if os.path.exists(index_file_path):
      md_file = MdFile(file_path=index_file_path)
      title = md_file.get_title()
    else:
      title = sanscript.transliterate(target_dir, sanscript.OPTITRANS, sanscript.DEVANAGARI)
  if os.path.exists(alt_file_path):
    html = include_helper.Include(url=alt_url, h1_level=h1_level, classes=classes, title=title).to_html_str()
    html = f"<body>{html}</body>"
    return BeautifulSoup(html, 'html.parser').select_one("div")
  else:
    logging.error(f"{alt_file_path} not found!")
    return None




def prefill_include(inc, container_file_path, h1_level_offset=0, hugo_base_dir="/home/vvasuki/gitland/vishvAsa"):
  """To be used with transform_include_lines.
  
  :param match: 
  :param source_dir: Eg. "vishvAsa-prastutiH"
  :param alt_dirs: Eg: ["commentary-1", "commentary-2"]
  :return: 
  """
  inc["unfilled"] = None
  souper.empty_tag(inc)

  url = inc["url"]
  if not url.startswith("/"):
    # TODO: fix this.
    logging.info(f"Skipping relative path in {container_file_path}")
    return 
  file_path = file_path_from_url(url=url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path)
  if file_path is None:
    if url.endswith(".md"):
      new_url = url[:-3]
    elif url.endswith(".md/"):
      new_url = url[:-1]
    else:
      new_url = regex.sub("/$", "", url) + ".md"
    url = new_url.replace("/content/", "/").replace("/static/", "/")
    file_path = file_path_from_url(url=new_url, hugo_base_dir=hugo_base_dir, current_file_path=container_file_path)
    if file_path is None:
      logging.warning(f"Could not fix: {url} in {container_file_path}")
      return 
    else:
      logging.info(f"Corrected url to: {new_url} in {container_file_path}")
      url = new_url
      inc["url"] = url
  md_file = MdFile(file_path=file_path)
  (metadata, content) = md_file.read()
  metadata["_file_path"] = file_path
  h1_level = h1_level_offset + int(inc.get("newlevelforh1", 2))
  if "newlevelforh1" not in inc.attrs:
    logging.warning(f"No newlevelforh1 for {file_path} in {container_file_path}")
  content = regex.sub("^#", f"{'#' * h1_level}", content)
  content = regex.sub("\n#", f"\n{'#' * h1_level}", content)
  # TODO: Handle images, spreadsheets, relative urls in includes
  if file_path == container_file_path:
    logging.fatal(f"Circular include in {container_file_path}")
    return 
  content = transform_includes_with_soup(content=content, metadata=metadata, h1_level_offset=h1_level, transformer=prefill_include)

  title = inc.get("title", metadata.get("title", "UNKNOWN_TITLE")) + " ...{Loading}..."
  if "UNKNOWN_TITLE" in title:
    logging.warning(f"Could not get title for {file_path} in {container_file_path}")
  details = BeautifulSoup(f"<body><details><summary><h{h1_level}>{title}</h{h1_level}></summary>\n\n{content}\n</details></body>", 'html.parser').select_one("details")
  if "collapsed" not in inc["class"]:
    details["open"] = None
  inc.append("\n")
  inc.append(details)
  inc.append("\n")


def prefill_includes(dir_path):
  logging.info(f"Prefilling includes in {dir_path}")
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, content_transformer=lambda x, y: transform_includes_with_soup(x, y,transformer=prefill_include))


def alt_include_adder(inc, current_file_path, source_dir, alt_dirs, hugo_base_dir="/home/vvasuki/gitland/vishvAsa"):
  """To be used with transform_include_lines.
  
  :param match: 
  :param source_dir: Eg. "vishvAsa-prastutiH"
  :param alt_dirs: Eg: ["commentary-1", "commentary-2"]
  :return: 
  """
  url = inc["url"]
  file_path = file_path_from_url(url=url, hugo_base_dir=hugo_base_dir, current_file_path=current_file_path)
  h1_level = inc["newlevelforh1"]
  h1_level = int(h1_level) + 1
  for x in alt_dirs:
    new_include = make_alt_include(url=url, source_dir=source_dir, file_path=file_path, h1_level=h1_level, target_dir=x)
    inc.insert_after("\n\n", new_include, "\n\n")


def file_path_from_url(url, hugo_base_dir, current_file_path):
  if url.startswith("http"):
    return
  file_path = None
  if url.startswith("/"):
    if url.endswith(".md"):
      file_path = regex.sub(r"(/.+?)(/.+)", f"{hugo_base_dir}\\1/static\\2", url)
    else:
      file_path = regex.sub(r"(/.+?)(/.+)/?", f"{hugo_base_dir}\\1/content\\2.md", url).replace("/.md", ".md")
      file_path = regex.sub("//+", "/", file_path)
      if not os.path.exists(file_path):
        file_path = regex.sub(r"(/.+?)(/.+)/?", f"{hugo_base_dir}\\1/content\\2/_index.md", url)
  else:
    # relative path
    # TODO: Handle this
    logging.warning(f"Skipping relative path {url} in {current_file_path}")
    pass
  if file_path is not None:
    file_path = regex.sub("//+", "/", file_path)
    if os.path.exists(file_path):
      return file_path
    # logging.debug(f"Could not find: {file_path} in {current_file_path}")
    return None


def include_basename_fixer(inc, ref_dir):
  """To be used with transform_include_lines.
  
  :param match: 
  :param ref_dir: 
  :return: 
  """
  sub_path_to_reference = arrangement.get_sub_path_to_reference_map(ref_dir=ref_dir)
  url = inc["url"]
  sub_path_id = arrangement.get_sub_path_id(regex.sub(".+?/%s(/.+)" % os.path.basename(ref_dir), "\\1", url))
  base_url = regex.sub("(.+?/%s)/.+" % os.path.basename(ref_dir), "\\1", url)
  new_sub_path = regex.sub(".+?/%s(/.+)" % os.path.basename(ref_dir), "\\1", str(sub_path_to_reference[sub_path_id].file_path))
  new_url = os.path.abspath(base_url + new_sub_path)
  inc["url"] = new_url


def include_core_with_commentaries(dir_path, alt_dirs, file_pattern="**/*.md", source_dir="vishvAsa-prastutiH"):
  def include_fixer(inc, file_path, *args, **kwargs):
    return alt_include_adder(inc=inc, current_file_path=file_path, source_dir=source_dir, alt_dirs=alt_dirs)

  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, file_pattern=file_pattern, content_transformer=lambda x, y: transform_includes_with_soup(x, y,transformer=old_include_remover))
  library.apply_function(fn=MdFile.transform, dir_path=dir_path, file_pattern=file_pattern, content_transformer=lambda x, y: transform_includes_with_soup(x, y,transformer=include_fixer))
  # library.apply_function(fn=MdFile.transform, dir_path=dir_path, file_pattern=file_pattern, content_transformer=lambda content, m: regex.sub("\n\n+", "\n\n", content), dry_run=False)

