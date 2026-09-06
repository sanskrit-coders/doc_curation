import textwrap

from doc_curation.md import content_processor
from doc_curation.md.file import MdFile


def get_prompt(md_path, block_index=0):
  md_file = MdFile(md_path)
  metadata, content = md_file.read()
  return content_processor.extract_codeblock(content, block_index)


def dump_to_md(dest_path, prompt:str, metadata: str, content: str):
  md_file = MdFile(dest_path)
  content = textwrap.dedent(f"""
  <details><summary>AI prompt</summary>
  
  ```markdown
  {prompt}
  ```
  </details>
  <details><summary>AI response</summary>
  
  ```json
  {metadata}
  ```
  </details>
  
  {content}
  """)
  md_file.dump_to_file(metadata={"title": "UNK"}, content=content, dry_run=False)
