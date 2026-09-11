"""PDF chunk processing with Gemini."""
import json
import logging
import os
import tempfile

import regex
from google.genai import types
from pypdf import PdfReader, PdfWriter
from tqdm import tqdm

from doc_curation.llm import dump_to_md
from doc_curation.md.file import MdFile

from .keys import get_client


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


def process_pdf_chunks(file_in, prompt, dest_path, pages_per_chunk=5, model_id="gemini-3.5-flash", api_key_path="gemini.vv", overwrite=False):
  client = get_client(api_key_path=api_key_path)

  reader = PdfReader(file_in)
  total_pages = len(reader.pages)

  full_response_metadata = []
  all_text_parts = []

  metadata = {"title": "UNK", "continue_page": 1}
  if not overwrite and os.path.exists(dest_path):
    md_file = MdFile(dest_path)
    metadata, content = md_file.read()
    all_text_parts.append(content)
  start_page = metadata.get("continue_page", 1)

  # Load the detailed prompt once as a system instruction
  config = types.GenerateContentConfig(
    system_instruction=prompt,
  )
  chat = client.chats.create(model=model_id, config=config)

  # Convert 1-indexed start_page to 0-indexed for Python logic
  start_index = max(0, start_page - 1)
  combined_prompt = f"PROMPT 0:  \n{prompt}\n"
  try:
    for i in tqdm(range(start_index, total_pages, pages_per_chunk), desc="Processing PDF Chunks"):
      end_page = min(i + pages_per_chunk, total_pages)
  
      writer = PdfWriter()
      for j in range(i, end_page):
        writer.add_page(reader.pages[j])
  
      with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_path = temp_file.name
        writer.write(temp_file)
  
      try:
        uploaded = client.files.upload(file=temp_path)
  
        chunk_prompt = f"Convert pages {i + 1} to {end_page} into Markdown according to the system instructions."
        response = chat.send_message([uploaded, chunk_prompt])
  
        chunk_metadata = scrub_response(response.model_dump())
        full_response_metadata.append({f"pages_{i+1}_to_{end_page}": chunk_metadata})
  
        if response.text:
          all_text_parts.append(response.text)
          all_text_parts[-1] = regex.sub("```.*", "", all_text_parts[-1])
          metadata["continue_page"] = end_page + 1
  
      finally:
        if os.path.exists(temp_path):
          os.remove(temp_path)
    metadata.pop("continue_page", None)
  except Exception as e:
    logging.error(f"\n[Error encountered: {e}]. Saving partial progress up to this point... Continue from start page : {metadata.get('continue_page')}")
    raise
  
  finally:
    combined_metadata = json.dumps(full_response_metadata, ensure_ascii=False, indent=2)
    combined_text = "\n\n".join(all_text_parts)
    dump_to_md(dest_path, prompt=combined_prompt, response_headers=combined_metadata, content=combined_text, metadata=metadata)


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
  dump_to_md(dest_path, prompt, metadata, response.text)
  return response
