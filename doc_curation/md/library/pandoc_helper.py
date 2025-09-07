import logging
import os
import subprocess

import regex
import yaml

from doc_curation.md.file import MdFile


def get_md_with_pandoc(content_in, source_format="html-native_divs-native_spans", pandoc_extra_args=['--markdown-headings=atx']):
  """
  
  :param content_in: 
  :param source_format: html-native_divs-native_spans ensures that there are no divs and span tags in the output. 
  :param pandoc_extra_args: 
  :return: 
  """
  import pypandoc
  logger = logging.getLogger('pypandoc')
  logger.setLevel(logging.CRITICAL)

  filters = None
  content = pypandoc.convert_text(source=content_in, to="gfm-raw_html", format=source_format,
                                  extra_args=pandoc_extra_args,
                                  filters=filters)
  # content = regex.sub(r"</?div[^>]*?>", "", content)
  content = regex.sub(r"\n\n+", "\n\n", content)
  # Careful to exclude |-ending-lines in tables.
  content = regex.sub(r"([^\s|])\n([^\-\s|>])", r"\1 \2", content)
  return content


def pandoc_dump_md(md_file, content, source_format, dry_run, metadata={},
                               pandoc_extra_args=['--markdown-headings=atx']):
  content = get_md_with_pandoc(content_in=content, source_format=source_format, pandoc_extra_args=pandoc_extra_args)
  md_file.dump_to_file(metadata=metadata, content=content, dry_run=dry_run)

def import_with_pandoc(md_file, source_file, source_format, dry_run, metadata={},
                       pandoc_extra_args=['--markdown-headings=atx']):
  if source_format == "rtf":
    html_path = str(source_file).replace(".rtf", ".html")
    subprocess.call(['Ted', '--saveTo', source_file, html_path])
    source_file = html_path
    source_format = "html"
    if not os.path.exists(html_path):
      logging.warning("Could not convert rtf to html, skipping %s", source_file)
      return

  with open(source_file, 'r') as fin:
    md_file.import_content_with_pandoc(content=fin.read(), source_file=source_file, source_format=source_format,
                                    dry_run=dry_run, metadata=metadata, pandoc_extra_args=pandoc_extra_args)




def pandoc_from_md_file(md_file, dest_path, dest_format="epub", metadata=None, pandoc_extra_args=[], content_maker=None):
  import pypandoc
  logger = logging.getLogger('pypandoc')
  logger.setLevel(logging.CRITICAL)
  logger.info(f"Converting {md_file} to {dest_path}...")
  [metadata_in, content_in] = md_file.read()
  if metadata is not None:
    metadata.update(metadata_in)
  if content_maker is not None:
    content_in = content_maker(content_in)
  filters = None
  # prepend metadata as yaml string to content_in
  content_in = "\n".join([f"---\n{yaml.dump(metadata)}\n---", content_in])

  os.makedirs(os.path.dirname(dest_path), exist_ok=True)
  pypandoc.convert_text(source=content_in, to=dest_format, format="gfm-raw_html-smart",extra_args=pandoc_extra_args,filters=filters, outputfile=dest_path)
  logging.info(f"Successfully created '{dest_path}'!")


if __name__ == '__main__':
  pandoc_from_md_file(md_file=MdFile(file_path="/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation/md/library/test_local.md"), dest_path="/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation/md/library/test_local.md.epub", dest_format="epub", css_path="/home/vvasuki/gitland/sanskrit-coders/doc_curation/doc_curation/md/epub_style.css", metadata={"title": "mUlam-1.1", "author": "mUlam"})