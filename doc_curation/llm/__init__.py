import os
import textwrap


from doc_curation.md import content_processor
from doc_curation.md.content_processor import details_helper
from doc_curation.md.file import MdFile


def get_prompt(md_path, block_index=0):
  md_file = MdFile(md_path)
  metadata, content = md_file.read()
  return content_processor.extract_codeblock(content, block_index)


def dump_to_md(dest_path, prompt:str, response_headers: str, content: str, metadata):
  md_file = MdFile(dest_path)
  ai_details = [details_helper.Detail(title="AI Prompt", content=prompt), details_helper.Detail(title="AI Response Headers", content=response_headers)]
  ai_details = [x.to_md_html() for x in ai_details]
  content = f"{'\n\n'.join(ai_details)}\n\n{content}"
  if metadata is None and os.path.exists(dest_path):
    metadata, _ = md_file.read()
  md_file.dump_to_file(metadata=metadata, content=content, dry_run=False)
