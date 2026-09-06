import copy
import json
import textwrap
import io
import os
import tempfile

from google.genai.types import GenerateContentResponse
from google.genai import types
from pypdf import PdfReader, PdfWriter

from google import genai

from curation_utils import creds
from doc_curation import llm
from doc_curation.md.file import MdFile

client = None


def scrub_response(obj):
  """Remove nulls and large text fields from Gemini response."""
  if isinstance(obj, dict):
    out = {}

    for k, v in obj.items():
      # Drop null values
      if v is None:
        continue

      # Drop generated text and thought signatures
      if k in {"text", "thought_signature"}:
        continue

      v = scrub_response(v)

      # Drop empty containers
      if v in ({}, [], None):
        continue

      out[k] = v

    return out

  if isinstance(obj, list):
    return [x for item in obj if (x := scrub_response(item)) not in ({}, [], None)]

  return obj

def get_client(api_key_path, cred_path="/home/vvasuki/gitland/vvasuki-git/sysconf/kunchikA/tokens.toml"):
  global client
  if client is None:
    api_key = creds.get_toml_value(path=cred_path, key=api_key_path)
    client = genai.Client(api_key=api_key)
  return client


def process_file_page_chunks(file_in, prompt, dest_path, pages_per_chunk=5, model_id="gemini-3.5-flash", api_key_path="gemini.vv"):
  client = get_client(api_key_path=api_key_path)
  
  reader = PdfReader(file_in)
  total_pages = len(reader.pages)
  
  all_metadata = []
  all_text_parts = []
  
  # Load the detailed prompt once as a system instruction
  config = types.GenerateContentConfig(
      system_instruction=prompt,
  )
  chat = client.chats.create(model=model_id, config=config)
  
  for i in range(0, total_pages, pages_per_chunk):
    end_page = min(i + pages_per_chunk, total_pages)
    
    writer = PdfWriter()
    for j in range(i, end_page):
      writer.add_page(reader.pages[j])
      
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
      temp_path = temp_file.name
      writer.write(temp_file)
      
    try:
      uploaded = client.files.upload(file=temp_path)
      
      # Pass a minimal prompt for each chunk
      chunk_prompt = f"Convert pages {i + 1} to {end_page} into Markdown according to the system instructions."
      response = chat.send_message([uploaded, chunk_prompt])
      
      metadata = scrub_response(response.model_dump())
      all_metadata.append({f"pages_{i+1}_to_{end_page}": metadata})
      
      if response.text:
        all_text_parts.append(response.text)
        
    finally:
      if os.path.exists(temp_path):
        os.remove(temp_path)
  combined_metadata = json.dumps(all_metadata, ensure_ascii=False, indent=2)
  combined_text = "\n\n".join(all_text_parts)
  dump_to_md(dest_path, combined_metadata, combined_text)


def process_file(file_in, prompt, dest_path, model_id="gemini-3.5-flash", api_key_path="gemini.vv"):
  client = get_client(api_key_path=api_key_path)
  uploaded = client.files.upload(
    file=file_in
  )
  response = client.models.generate_content(
    model=model_id,
    contents=[
      uploaded,
      prompt
    ]
  )
  metadata = json.dumps(
    scrub_response(response.model_dump()),
    ensure_ascii=False,
    indent=2,
  )
  dump_to_md(dest_path, metadata, response.text)
  return response


def dump_to_md(dest_path, metadata: str, content: str):
  md_file = MdFile(dest_path)
  content = textwrap.dedent(f"""
  <details><summary>Gemini response</summary>
  
  ```json
  {metadata}
  ```
  </details>
  
  {content}
  """)
  md_file.dump_to_file(metadata={"title": "UNK"}, content=content, dry_run=False)


if __name__ == '__main__':
  pass
  process_file_page_chunks(file_in="/media/vvasuki/vData/text/granthasangrahaH/kAvyam/shrIvaiShNavakRtam/yatirAja-vijaya-nATakam.pdf", dest_path="/home/vvasuki/gitland/vishvAsa/rAmAnujIyam/content/kAvyam/rUpakam/naDAdUr-ghaTikA-shata-varadaH/yatirAja-vijaya-nATakam.md", prompt=llm.get_prompt("/home/vvasuki/gitland/sanskrit/sanskrit.github.io/content/groups/dyuganga/projects/text/proofreading/editing/AI-prompt/Sanskrit_devanAgarI_markdown.md") + "Start from the first page, don't skip a single page till the end.", api_key_path="gemini.kv")