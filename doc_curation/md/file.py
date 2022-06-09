import codecs
import itertools
import logging
import os
import subprocess
from typing import Tuple, Dict

import regex
import toml
import yamldown

from doc_curation.md import get_md_with_pandoc
from doc_curation.md.content_processor.section_helper import get_lines_till_section, reduce_section_depth, split_to_sections
from indic_transliteration import sanscript

# Remove all handlers associated with the root logger object.
from curation_utils import file_helper
import regex

for handler in logging.root.handlers[:]:
  logging.root.removeHandler(handler)
logging.basicConfig(
  level=logging.DEBUG,
  format="%(levelname)s:%(asctime)s:%(module)s:%(lineno)d %(message)s")

CHUNK_SIZE = 2000

class MdFile(object):
  YAML = "yaml"
  TOML = "toml"

  def __init__(self, file_path, frontmatter_type=None):
    self.file_path = str(file_path)
    self.frontmatter_type = frontmatter_type

  def __str__(self):
    return str(self.file_path)

  def _read_yml_md_file(self) -> Tuple[Dict, str]:
    metadata = {}
    content = ""
    if os.path.exists(self.file_path):
      with codecs.open(self.file_path, "r", 'utf-8') as file:
        if file.readline().strip() == "---":
          file.seek(0)
          full_content = file.read()
          full_content = regex.sub("^--- *\n", "---\n", full_content)
          full_content = regex.sub("\n--- *\n", "\n---\n", full_content)
          from yaml.composer import ComposerError
          try:
            import io
            (metadata, content) = yamldown.load(io.StringIO(full_content))
          except Exception as e:
            logging.fatal("Error in %s: %s" % (self.file_path, str(e)))
        else:
          file.seek(0)
          content = file.read()
        # logging.info((metadata, content))
        if metadata is None: metadata = {}
    return (metadata, content)

  def _read_toml_md_file(self) -> Tuple[Dict, str]:
    metadata = {}
    content = ""
    if os.path.exists(self.file_path):
      with codecs.open(self.file_path, "r", 'utf-8') as file:
        first_line = file_helper.clear_bad_chars(file.readline()).strip()
        if first_line == "+++":
          file.seek(0)
          lines = file.readlines()
          lines = [file_helper.clear_bad_chars(line) for line in lines]
          toml_lines = itertools.takewhile(lambda x: x.strip() != "+++", lines[1:])
          from toml import TomlDecodeError
          try:
            metadata = toml.loads("".join(toml_lines))
          except TomlDecodeError as e:
            logging.fatal("Error in %s: %s" % (self.file_path, str(e)))
          content_lines = list(itertools.dropwhile(lambda x: x.strip() != "+++", lines[1:]))
          content = "".join(content_lines[1:])
          # logging.info((toml, content))
          if metadata is None: metadata = {}
        else:
          logging.warning("No front-matter found.")
          file.seek(0)
          content = file.read()
    return (metadata, content)

  def import_content_with_pandoc(self, content, source_format, dry_run, metadata={},
                                 pandoc_extra_args=['--atx-headers']):
    content = get_md_with_pandoc(content_in=content, source_format=source_format, pandoc_extra_args=pandoc_extra_args)
    self.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)

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
      if first_line.strip() == "---":
        return MdFile.YAML
      elif first_line.strip() == "+++":
        return MdFile.TOML
      else:
        return None

  def read(self) -> Tuple[Dict, str]:
    file_helper.clear_bad_chars_in_file(file_path=self.file_path, dry_run=False)
    actual_frontmatter_type = self.get_frontmatter_type()
    if self.frontmatter_type is None:
      self.frontmatter_type = actual_frontmatter_type
    elif self.frontmatter_type != actual_frontmatter_type:
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
        content = fin.read()
      return ({}, content)

  def get_title(self, omit_chapter_id=True, ref_dir_for_ancestral_title=None):
    (metadata, content) = self.read()
    if not isinstance(metadata, dict):
      logging.fatal(f"Crazy metadata - {self.file_path}")
    title = metadata.get("title", None)
    title = str(title) # Might be mistakenly numeric!
    if ref_dir_for_ancestral_title is not None:
      while ref_dir_for_ancestral_title.endswith("/"):
        ref_dir_for_ancestral_title = ref_dir_for_ancestral_title[:-1]
      from doc_curation.md import library
      parent_md = library.get_parent_md(md_file=self)
      if parent_md is not None:
        parent_dir = os.path.dirname(parent_md.file_path)
        if parent_dir != ref_dir_for_ancestral_title:
          parent_title = parent_md.get_title(omit_chapter_id=omit_chapter_id, ref_dir_for_ancestral_title=ref_dir_for_ancestral_title)
          title = "%s// %s" % (parent_title, title)
          title = regex.sub("(?:^| )\+", "", title)
    
    if title is None:
      logging.fatal("%s has None title", self.file_path)
    if title.startswith("+"):
      title = title[1:]
    
    if omit_chapter_id and title is not None:
      title = regex.sub("^[+०-९]+ +", "", title)
    return title

  def dump_mediawiki(self, outpath=None, dry_run=False):
    (metadata, content) = self.read()
    import pypandoc
    output = pypandoc.convert_text(content, 'mediawiki', format='md')
    if outpath is None:
      outpath = self.file_path.replace(".md", ".wiki")
    if not dry_run:
      with codecs.open(outpath, "w", 'utf-8') as out_file_obj:
        chunks = [dump[i:i+CHUNK_SIZE] for i in range(0, len(dump), CHUNK_SIZE)]
        for chunk in chunks:
          out_file_obj.write(chunk)
    else:
      logging.info(output)

  def _dump_to_file_yamlmd(self, metadata, content, dry_run):
    logging.info(self.file_path)
    if not dry_run:
      os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
      with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
        import yaml
        if metadata == {}:
          yamlout = ""
        else:
          yamlout = yaml.dump(metadata, default_flow_style=False, indent=2, allow_unicode=True, width=1000)
        dump = "---\n{metadata}\n---\n{markdown}".format(metadata=yamlout, markdown=content)
        chunks = [dump[i:i+CHUNK_SIZE] for i in range(0, len(dump), CHUNK_SIZE)]
        for chunk in chunks:
          out_file_obj.write(chunk)
        # out_file_obj.write(yamldown.dump(metadata, content)) has a bug - https://github.com/dougli1sqrd/yamldown/issues/5
    else:
      logging.info(metadata)
      # logging.info(content)

  def _dump_to_file_tomlmd(self, metadata, content, dry_run):
    # logging.info(self.file_path)
    if not dry_run:
      os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
      with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
        import toml
        tomlout = toml.dumps(metadata)
        dump = "+++\n{frontmatter}\n+++\n{markdown}".format(frontmatter=tomlout, markdown=content)
        chunks = [dump[i:i+CHUNK_SIZE] for i in range(0, len(dump), CHUNK_SIZE)]
        for chunk in chunks:
          out_file_obj.write(chunk)
    else:
      logging.info(metadata)
      # logging.info(content)

  def dump_to_file(self, metadata, content, dry_run, silent=False):
    if not silent:
      logging.info("Writing %s", self.file_path)
    content = file_helper.clear_bad_chars(content)
    if len(metadata) > 0:
        if self.frontmatter_type is None:
          self.frontmatter_type = MdFile.TOML # Default
        if self.frontmatter_type == MdFile.YAML:
          self._dump_to_file_yamlmd(metadata, content, dry_run)
        elif self.frontmatter_type == MdFile.TOML:
          self._dump_to_file_tomlmd(metadata, content, dry_run)
    else:
        if not dry_run:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with codecs.open(self.file_path, "w", 'utf-8') as out_file_obj:
              chunks = [content[i:i+CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]
              for chunk in chunks:
                out_file_obj.write(chunk)

  def set_title(self, title, dry_run):
    self.set_frontmatter_field_value(field_name="title", value=title, dry_run=dry_run)
    
  def set_frontmatter_field_value(self, field_name, value, dry_run):
    metadata, content = self.read()
    if field_name in metadata and metadata[field_name] == value:
      return 
    logging.info("Setting %s of %s to %s (was %s)", field_name, self.file_path, value, metadata.get(field_name, "None"))
    if not dry_run:
      metadata[field_name] = value
      os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
      self.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)

  def replace_content_metadata(self, new_content=None, new_metadata=None, dry_run=False, silent=False):
    (metadata, content) = self.read()
    if new_metadata is None:
      new_metadata = metadata
    if new_content is None:
      new_content = content
    self.dump_to_file(metadata=new_metadata, content=new_content, dry_run=dry_run, silent=silent)

  def split_to_bits(self, source_script=sanscript.DEVANAGARI, mixed_languages_in_titles=True, title_index_pattern="%02d", bits_dir_url=None,
                    target_frontmantter_type=TOML, add_short_title=False, dry_run=False):
    """Splits this md file into separate files - one for each section.
    
    Implementation notes: md parsers oft convert to html or json. Processing that output would be more complicated than what we need here.
    :return: 
    """
    # TODO: Fix links upon splitting.
    logging.debug("Processing file: %s", self.file_path)
    if os.path.basename(self.file_path) == "_index.md":
      out_dir = os.path.dirname(self.file_path)
    else:
      out_dir = os.path.join(os.path.dirname(self.file_path), os.path.basename(self.file_path).replace(".md", ""))
      
    (metadata, content) = self.read()
    lines = content.splitlines(keepends=False)
    (lines_till_section, remaining) = get_lines_till_section(lines)
    sections = split_to_sections(remaining)
    if len(sections) == 0:
      return
    section_md_urls = []
    for section_index, section in enumerate(sections):
      title = section.title
      if title == None:
        title = ""
      if title_index_pattern is not None:
        title_index = title_index_pattern % (section_index + 1)
        if source_script is not None:
          ## Transliterate the number
          title_index = sanscript.transliterate(title_index, sanscript.OPTITRANS, source_script)
        title = "%s %s" % (title_index, title)
      title = title.strip()

      from doc_curation import text_utils
      short_title = text_utils.title_from_text(text=title, num_words=6, target_title_length=24)
      title_in_file_name = title
      if source_script is not None:
        title_in_file_name = file_helper.get_storage_name(text=title, source_script=source_script, maybe_use_dravidian_variant=True, mixed_languages_in_titles=mixed_languages_in_titles)
      if title_in_file_name == "":
        raise ValueError(title_in_file_name)
      file_name = file_helper.clean_file_path("%s.md" % title_in_file_name)
      file_path = os.path.join(out_dir, file_name)
      if bits_dir_url is not None:
        section_md_urls.append(os.path.join(bits_dir_url, file_name.replace(".md", "")))
      section_metadata = {"title": title}
      hashes_to_reduce = section.header_prefix.strip()[:-1]
      section_md = "\n".join(reduce_section_depth(section.lines, hashes_to_reduce=hashes_to_reduce))
      if short_title != title and add_short_title:
        section_metadata["short_title"] = short_title
        section_md = "%s\n\n%s" % (title, section_md)
      md_file = MdFile(file_path=file_path, frontmatter_type=target_frontmantter_type)
      md_file.dump_to_file(metadata=section_metadata, content=section_md, dry_run=dry_run)

    if bits_dir_url is not None:
      remainder_file_path = self.file_path
    else:
      remainder_file_path = os.path.join(out_dir, "_index.md")
    content = "\n".join(lines_till_section)
    if len(section_md_urls) > 0:
      section_md_includes = ["""<div class="js_include" url="%s"  newLevelForH1="2" includeTitle="false"> </div>""" % url for url in section_md_urls]
      content = content + "\n" + "\n".join(section_md_includes)
    logging.debug(metadata)
    if not metadata["title"].startswith("+"):
      metadata["title"] = "+" + metadata["title"]
    MdFile(file_path=remainder_file_path, frontmatter_type=target_frontmantter_type).dump_to_file(metadata=metadata, content=content, dry_run=dry_run)
    if str(self.file_path) != str(remainder_file_path):
      logging.info("Removing %s as %s is different ", self.file_path, remainder_file_path)
      if not dry_run and remainder_file_path != self.file_path:
        os.remove(path=self.file_path)

  def transform(self, content_transformer=None, metadata_transformer=None, dry_run=False):
    [metadata, content] = self.read()
    metadata["_file_path"] = self.file_path
    update_needed = False
    if content_transformer is not None:
      content_new = content_transformer(content, metadata)
      update_needed |= content.strip() != content_new.strip()
      content = content_new
    if metadata_transformer is not None:
      metadata_new = metadata_transformer(content, metadata.copy())
      update_needed |= metadata != metadata_new
      metadata = metadata_new
    del metadata["_file_path"]
    if update_needed:
      self.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)

  def append_content_from_mds(self, source_mds, dry_run=False):
    (_, dest_content) = self.read()
    new_content = dest_content
    for source_md in source_mds:
      (metadata, source_content) = source_md.read()
      source_content = regex.sub("(?<=^|\n)#", "##", source_content)
      new_content += "\n\n## %s\n%s" % (metadata["title"], source_content)
    if new_content != dest_content:
      self.replace_content_metadata(new_content=new_content, dry_run=dry_run)

