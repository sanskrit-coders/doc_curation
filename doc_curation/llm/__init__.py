from doc_curation.md import content_processor
from doc_curation.md.file import MdFile


def get_prompt(md_path, block_index=0):
  md_file = MdFile(md_path)
  metadata, content = md_file.read()
  return content_processor.extract_codeblock(content, block_index)
