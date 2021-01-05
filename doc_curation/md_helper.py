import codecs
import itertools
import logging
import os
import subprocess
from typing import Tuple, Dict

import regex
import toml
import yamldown
from indic_transliteration import sanscript
from more_itertools import peekable

# Remove all handlers associated with the root logger object.
import doc_curation
from curation_utils import file_helper

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


class MdFile(object):
  YAML = "yaml"
  TOML = "toml"

  def __init__(self, file_path, frontmatter_type="toml"):
    self.file_path = file_path
    self.frontmatter_type = frontmatter_type

  def __str__(self):
    return str(self.file_path)

  def _read_yml_md_file(self) -> Tuple[Dict, str]:
    yml = {}
    md = ""
    if os.path.exists(self.file_path):
      with codecs.open(self.file_path, "r", 'utf-8') as file:
        if file.readline().strip() == "---":
          file.seek(0)
          (yml, md) = yamldown.load(file)
        else:
          file.seek(0)
          md = file.read()
        # logging.info((yml, md))
        if yml is None: yml = {}
    return (yml, md)

  def _read_toml_md_file(self) -> Tuple[Dict, str]:
    metadata = {}
    md = ""
    if os.path.exists(self.file_path):
      with codecs.open(self.file_path, "r", 'utf-8') as file:
        first_line = file_helper.clear_bad_chars(file.readline()).strip()
        if first_line == "+++":
          file.seek(0)
          lines = file.readlines()
          lines = [file_helper.clear_bad_chars(line) for line in lines]
          toml_lines = itertools.takewhile(lambda x: x.strip() != "+++", lines[1:])
          metadata = toml.loads("".join(toml_lines))
          md_lines = list(itertools.dropwhile(lambda x: x.strip() != "+++", lines[1:]))
          md = "".join(md_lines[1:])
          # logging.info((toml, md))
          if metadata is None: metadata = {}
        else:
          logging.warning("No front-matter found.")
          file.seek(0)
          md = file.read()
    return (metadata, md)

  def import_content_with_pandoc(self, content, source_format, dry_run, metadata={},
                                 pandoc_extra_args=['--atx-headers']):
    import pypandoc
    filters = None
    md = pypandoc.convert_text(source=content, to="gfm-raw_html", format=source_format, extra_args=pandoc_extra_args,
                               filters=filters)
    md = regex.sub("</?div[^>]*?>", "", md)
    md = regex.sub("\n\n+", "\n\n", md)
    self.dump_to_file(metadata=metadata, md=md, dry_run=dry_run)

  def import_with_pandoc(self, source_file, source_format, dry_run, metadata={}, pandoc_extra_args=['--atx-headers']):
    if source_format == "rtf":
      html_path = str(source_file).replace(".rtf", ".html")
      subprocess.call(['Ted', '--saveTo', source_file, html_path])
      source_file = html_path
      source_format = "html"
      if not os.path.exists(html_path):
        logging.warning("Could not convert rtf to html, skipping %s", source_file)
        return

    with open(source_file, 'r') as fin:
      self.import_content_with_pandoc(content=fin.read(), source_file=source_file, source_format=source_format,
                                      dry_run=dry_run, metadata=metadata, pandoc_extra_args=pandoc_extra_args)

  def get_frontmatter_type(self):
    with open(self.file_path, 'r') as fin:
      first_line = fin.readline().strip()
      if first_line == "---":
        return MdFile.YAML
      elif first_line == "+++":
        return MdFile.TOML
      else:
        return None

  def read_md_file(self) -> Tuple[Dict, str]:
    file_helper.clear_bad_chars_in_file(file_path=self.file_path, dry_run=False)
    actual_frontmatter_type = self.get_frontmatter_type()
    if self.frontmatter_type != actual_frontmatter_type:
      logging.warning(
        "Frontmatter type mismatch: field value %s vs actual %s. Using the latter, but not updating field value.",
        self.frontmatter_type, actual_frontmatter_type)
    if actual_frontmatter_type == MdFile.YAML:
      return self._read_yml_md_file()
    elif actual_frontmatter_type == MdFile.TOML:
      return self._read_toml_md_file()
    elif actual_frontmatter_type == None:
      self.frontmatter_type = MdFile.TOML
      with open(self.file_path, 'r') as fin:
        md = fin.read()
      return ({}, md)

  def get_title(self, omit_chapter_id=True):
    (yml, md) = self.read_md_file()
    title = yml.get("title", None)
    if omit_chapter_id and title is not None:
      title = regex.sub("^[+०-९]+ +", "", title)
    title = regex.sub("^[+]+", "", title)
    return title

  def get_upaakhyaana(self, omit_id=True):
    upaakhyaana_optitrans = os.path.basename(os.path.dirname(self.file_path))
    upaakhyaana = sanscript.transliterate(data=upaakhyaana_optitrans, _from=sanscript.OPTITRANS,
                                          _to=sanscript.DEVANAGARI)
    if omit_id:
      upaakhyaana = regex.sub("^[+०-९]+-+", "", upaakhyaana)
    return upaakhyaana

  def set_title_from_filename(self, transliteration_target, dry_run):
    logging.info(self.file_path)
    if os.path.basename(self.file_path) == "_index.md":
      dir_name = os.path.basename(os.path.dirname(self.file_path)).replace(".md", "")
      title_optitrans = "+" + dir_name
    else:
      title_optitrans = os.path.basename(self.file_path).replace(".md", "")
    title = title_optitrans.replace("_", " ")
    if transliteration_target is not None:
      title = sanscript.transliterate(data=title, _from=sanscript.OPTITRANS, _to=transliteration_target)
    self.set_title(dry_run=dry_run, title=title)

  def prepend_file_index_to_title(self, dry_run):
    if os.path.basename(self.file_path) == "_index.md":
      return
    else:
      index = regex.sub("_.+", "", os.path.basename(self.file_path))
    title = index + " " + self.get_title(omit_chapter_id=False)
    self.set_title(dry_run=dry_run, title=title)

  def ensure_ordinal_in_title(self, transliteration_target, dry_run):
    title = self.get_title(omit_chapter_id=False)
    if regex.fullmatch("[+०-९0-9].+", title):
      return
    if os.path.basename(self.file_path) == "_index.md":
      if str(self.file_path).endswith("content/_index.md"):
        return
      files = os.listdir(os.path.dirname(os.path.dirname(self.file_path)))
    else:
      files = os.listdir(os.path.dirname(self.file_path))
    if "_index.md" in files:
      files.remove("_index.md")
    files.sort()
    index = files.index(os.path.basename(self.file_path))
    format = "%%0%dd" % (len(str(len(files))))
    index = format % index
    if transliteration_target:
      index = sanscript.transliterate(index, sanscript.OPTITRANS, transliteration_target)
    title = "%s %s" % (index, title)
    self.set_title(title=title, dry_run=dry_run)

  def set_filename_from_title(self, transliteration_source, dry_run):
    # logging.debug(self.file_path)
    title = self.get_title(omit_chapter_id=False)
    if transliteration_source is not None:
      title = sanscript.transliterate(data=title, _from=transliteration_source, _to=sanscript.OPTITRANS)
    if os.path.basename(self.file_path) == "_index.md":
      current_path = os.path.dirname(self.file_path)
      extension = ""
    else:
      current_path = self.file_path
      extension = ".md"
    file_name = title.strip()
    file_name = regex.sub("[ _.]+", "_", file_name)
    file_name = regex.sub("-+", "-", file_name)
    file_name = file_name + extension
    file_name = file_helper.clean_file_path(file_name)
    file_path = os.path.join(os.path.dirname(current_path), file_name)
    if str(current_path) != file_path:
      logging.info("Renaming %s to %s", current_path, file_path)
      if not dry_run:
        os.rename(src=current_path, dst=file_path)
    self.file_path = file_path

  def fix_title_numbering(self, dry_run):
    title = self.get_title()
    if title is None:
      return

    import regex
    new_title = regex.sub("(^[०-९][^०-९])", "०\\1", title)
    if title != new_title:
      logging.info("Changing '%s' to '%s'", title, new_title)
      self.set_title(title=new_title, dry_run=dry_run)

  def dump_mediawiki(self, outpath=None, dry_run=False):
    (yml, md) = self.read_md_file()
    import pypandoc
    output = pypandoc.convert_text(md, 'mediawiki', format='md')
    if outpath is None:
      outpath = self.file_path.replace(".md", ".wiki")
    if not dry_run:
      with codecs.open(outpath, "w", 'utf-8') as out_file_obj:
        out_file_obj.write(output)
    else:
      logging.info(output)

  def _dump_to_file_yamlmd(self, yml, md, dry_run):
    logging.info(self.file_path)
    if not dry_run:
      os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
      with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
        import yaml
        if yml == {}:
          yamlout = ""
        else:
          yamlout = yaml.dump(yml, default_flow_style=False, indent=2, allow_unicode=True, width=1000)
        dump = "---\n{yml}\n---\n{markdown}".format(yml=yamlout, markdown=md)
        out_file_obj.write(dump)
        # out_file_obj.write(yamldown.dump(yml, md)) has a bug - https://github.com/dougli1sqrd/yamldown/issues/5
    else:
      logging.info(yml)
      # logging.info(md)

  def _dump_to_file_tomlmd(self, metadata, md, dry_run):
    logging.info(self.file_path)
    if not dry_run:
      os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
      with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
        import toml
        tomlout = toml.dumps(metadata)
        dump = "+++\n{frontmatter}\n+++\n{markdown}".format(frontmatter=tomlout, markdown=md)
        out_file_obj.write(dump)
        # out_file_obj.write(yamldown.dump(yml, md)) has a bug - https://github.com/dougli1sqrd/yamldown/issues/5
    else:
      logging.info(metadata)
      # logging.info(md)

  def dump_to_file(self, metadata, md, dry_run):
    md = file_helper.clear_bad_chars(md)
    if len(metadata) > 0:
        if self.frontmatter_type == MdFile.YAML:
          self._dump_to_file_yamlmd(metadata, md, dry_run)
        elif self.frontmatter_type == MdFile.TOML:
          self._dump_to_file_tomlmd(metadata, md, dry_run)
    else:
        if not dry_run:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
                out_file_obj.write(md)

  def set_title(self, title, dry_run):
    logging.info("Setting title of %s to %s", self.file_path, title)
    if not dry_run:
      yml, md = self.read_md_file()
      yml["title"] = title
      os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
      self.dump_to_file(metadata=yml, md=md, dry_run=dry_run)

  def prepend_to_content(self, prefix_text, dry_run=True):
    (yml, md) = self.read_md_file()
    self.dump_to_file(metadata=yml, md=prefix_text + md, dry_run=dry_run)

  def replace_content(self, new_content, dry_run=True):
    (yml, _) = self.read_md_file()
    self.dump_to_file(metadata=yml, md=new_content, dry_run=dry_run)

  def replace_in_content(self, pattern, replacement, dry_run=True):
    (yml, md) = self.read_md_file()
    md = regex.sub(pattern=pattern, repl=replacement, string=md)
    self.dump_to_file(metadata=yml, md=md, dry_run=dry_run)

  def split_to_bits(self, source_script=sanscript.DEVANAGARI, indexed_title_pattern="%02d %s",
                    target_frontmantter_type=TOML, dry_run=False):
    """
    
    Implementation notes: md parsers oft convert to html or json. Processing that output would be more complicated than what we need here.
    :return: 
    """
    # TODO: Fix links upon splitting.
    logging.debug("Processing file: %s", self.file_path)
    if os.path.basename(self.file_path) == "_index.md":
      out_dir = os.path.dirname(self.file_path)
    else:
      out_dir = os.path.join(os.path.dirname(self.file_path), os.path.basename(self.file_path).replace(".md", ""))
    (metadata, md) = self.read_md_file()
    lines = md.splitlines(keepends=False)
    (lines_till_section, remaining) = get_lines_till_section(lines)
    sections = split_to_sections(remaining)
    if len(sections) == 0:
      return 
    for section_index, (title, section_lines) in enumerate(sections):
      if title == None:
        title = ""
      if indexed_title_pattern is not None:
        title = indexed_title_pattern % (section_index + 1, title)
        if source_script is not None:
          title = sanscript.transliterate(title, sanscript.OPTITRANS, source_script)
      title = title.strip()
      title_in_file_name = title
      if source_script is not None:
        title_in_file_name = sanscript.transliterate(title, source_script, sanscript.OPTITRANS)
      if title_in_file_name == "":
        raise ValueError(title_in_file_name)
      file_name = file_helper.clean_file_path("%s.md" % title_in_file_name)
      file_path = os.path.join(out_dir, file_name)
      section_yml = {"title": title}
      section_md = "\n".join(reduce_section_depth(section_lines))
      md_file = MdFile(file_path=file_path, frontmatter_type=target_frontmantter_type)
      md_file.dump_to_file(metadata=section_yml, md=section_md, dry_run=dry_run)

    remainder_file_path = os.path.join(out_dir, "_index.md")
    md = "\n".join(lines_till_section)
    logging.debug(metadata)
    if not metadata["title"].startswith("+"):
      metadata["title"] = "+" + metadata["title"]
    MdFile(file_path=remainder_file_path, frontmatter_type=target_frontmantter_type).dump_to_file(metadata=metadata,
                                                                                                  md=md,
                                                                                                  dry_run=dry_run)
    if str(self.file_path) != str(remainder_file_path):
      logging.info("Removing %s as %s is different ", self.file_path, remainder_file_path)
      if not dry_run:
        os.remove(path=self.file_path)

  def transliterate_content(self, source_scheme, dest_scheme=sanscript.DEVANAGARI, dry_run=False):
    (yml, md) = self.read_md_file()
    lines = md.split("\n")
    lines = [sanscript.transliterate(data=line, _from=source_scheme, _to=dest_scheme, togglers={}) for line in lines]
    md = "\n".join(lines)
    self.dump_to_file(yml, md=md, dry_run=dry_run)

  def fix_lazy_anusvaara(self, writing_scheme=sanscript.DEVANAGARI, dry_run=False, *args,
                         **kwargs):
    (yml, md) = self.read_md_file()
    # if len(yml) > len(md) and not str(self.file_path).endswith("_index.md"):
    #     raise ValueError("Something wrong with %s" % (self.file_path))
    lines = md.split("\n")
    lines = [sanscript.SCHEMES[writing_scheme].fix_lazy_anusvaara(data_in=line, *args,
                                                                  **kwargs) for
             line in lines]
    md = "\n".join(lines)
    self.dump_to_file(yml, md=md, dry_run=dry_run)

  @classmethod
  def get_md_files_from_path(cls, dir_path, file_pattern, file_name_filter=None, frontmatter_type="yaml"):
    from pathlib import Path
    # logging.debug(list(Path(dir_path).glob(file_pattern)))
    md_file_paths = sorted(filter(file_name_filter, Path(dir_path).glob(file_pattern)))
    return [MdFile(path, frontmatter_type=frontmatter_type) for path in md_file_paths]

  @classmethod
  def apply_function(cls, fn, dir_path, file_pattern="**/*.md", file_name_filter=None, frontmatter_type="yaml", start_file=None, *args,
                     **kwargs):
    # logging.debug(list(Path(dir_path).glob(file_pattern)))
    if os.path.isfile(dir_path):
      logging.warning("Got a file actually. processing it!")
      md_files = [MdFile(file_path=dir_path)]
    else:
      md_files = MdFile.get_md_files_from_path(dir_path=dir_path, file_pattern=file_pattern,
                                               file_name_filter=file_name_filter, frontmatter_type=frontmatter_type)
    start_file_reached = False

    from tqdm import tqdm
    for md_file in tqdm(md_files):
      if start_file is not None and not start_file_reached:
          if str(md_file.file_path) != start_file:
            continue
          else:
            start_file_reached = True
      logging.info("Processing %s", md_file)
      fn(md_file, *args, **kwargs)

  @classmethod
  def set_titles_from_filenames(cls, dir_path, transliteration_target, file_pattern="**/*.md", dry_run=False):
    cls.apply_function(fn=MdFile.set_title_from_filename, dir_path=dir_path, file_pattern=file_pattern,
                       transliteration_target=transliteration_target, dry_run=dry_run)

  @classmethod
  def set_filenames_from_titles(cls, dir_path, transliteration_source, file_pattern="**/*.md", file_name_filter=None,
                                dry_run=False):
    cls.apply_function(fn=MdFile.set_filename_from_title, dir_path=dir_path, file_pattern=file_pattern,
                       transliteration_source=transliteration_source, dry_run=dry_run,
                       file_name_filter=file_name_filter)

  @classmethod
  def fix_index_files(cls, dir_path, frontmatter_type=TOML, transliteration_target=sanscript.DEVANAGARI, dry_run=False):
    # Get all non hidden directories.
    dirs = [x[0] for x in os.walk(dir_path) if "/." not in x[0]]
    # set([os.path.dirname(path) for path in Path(dir_path).glob("**/")])
    for dir in dirs:
      index_file = MdFile(file_path=os.path.join(dir, "_index.md"), frontmatter_type=frontmatter_type)
      if not os.path.exists(index_file.file_path):
        index_file.dump_to_file(metadata={}, md="", dry_run=dry_run)
        index_file.set_title_from_filename(transliteration_target=transliteration_target, dry_run=dry_run)

  @classmethod
  def devanaagarify_titles(cls, md_files, dry_run=False):
    logging.info("Fixing titles of %d files", len(md_files))
    for md_file in md_files:
      # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
      logging.debug(md_file.file_path)
      title_fixed = sanscript.transliterate(data=md_file.get_title(), _from=sanscript.OPTITRANS,
                                            _to=sanscript.DEVANAGARI)
      md_file.set_title(title=title_fixed, dry_run=dry_run)

  @classmethod
  def fix_titles(cls, md_files,
                 spreadhsheet_id, worksheet_name, id_column, title_column,
                 md_file_to_id, google_key='/home/vvasuki/sysconf/kunchikA/google/sanskritnlp/service_account_key.json',
                 dry_run=False):
    # logging.debug(adhyaaya_to_mp3_map)
    logging.info("Fixing titles of %d files", len(md_files))
    from curation_utils.google import sheets
    doc_data = sheets.IndexSheet(spreadhsheet_id=spreadhsheet_id, worksheet_name=worksheet_name, google_key=google_key,
                                 id_column=id_column)
    for md_file in md_files:
      # md_file.replace_in_content("<div class=\"audioEmbed\".+?></div>\n", "")
      logging.debug(md_file.file_path)
      adhyaaya_id = md_file_to_id(md_file)
      if adhyaaya_id != None:
        logging.debug(adhyaaya_id)
        title = doc_data.get_value(adhyaaya_id, column_name=title_column)
        if title != None:
          md_file.set_title(title=title, dry_run=dry_run)


def import_md_recursive(source_dir, file_extension, source_format=None, dry_run=False):
  from pathlib import Path
  # logging.debug(list(Path(dir_path).glob(file_pattern)))
  source_paths = sorted(Path(source_dir).glob("**/*." + file_extension))
  if source_format is None:
    source_format = file_extension
  for source_path in source_paths:
    md_path = str(source_path).replace("." + file_extension, ".md")
    md_path = file_helper.clean_file_path(md_path)
    if os.path.exists(md_path):
      logging.info("Skipping %s", md_path)
      continue
    logging.info("Processing %s to %s", source_path, md_path)
    md_file = MdFile(file_path=md_path, frontmatter_type=MdFile.TOML)
    md_file.import_with_pandoc(source_file=source_path, source_format="rtf", dry_run=dry_run)
